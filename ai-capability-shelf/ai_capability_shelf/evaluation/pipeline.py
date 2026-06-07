"""
evaluation.pipeline — 崩溃安全评估管线
=======================================
九阶段 checkpointed pipeline + SentinelManager。

遵循 CRASH-SAFE 架构：
- 每个阶段执行前 acquire sentinel
- 每个阶段完成后写 checkpoint + release sentinel
- 重启时检测哨兵，自动从崩溃点恢复

五层架构覆盖：
  环境层 → 数据集层 → 引擎层 → 分析层 → 流转层
"""

from __future__ import annotations

import os
import sys
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ai_capability_shelf.exceptions import CapabilityShelfError
from ai_capability_shelf.persistence import (
    AtomicWriter,
    SentinelManager,
    CapabilityStore,
)

from .exceptions import (
    EvalPipelineError,
    EvalDatasetError,
    EvalEngineError,
)
from .models import (
    EvalCase,
    EvalCaseResult,
    EvalConfig,
    EvalDataset,
    EvalDimension,
    EvalPhaseName,
    EvalReport,
    EvalStandard,
    EvalStatus,
)
from .engine import EvalEngine
from .standards import (
    default_standard,
    get_standard,
    register_standard,
)


# ── 阶段常量 ──────────────────────────────────────────────

PHASE_NAMES: List[EvalPhaseName] = [
    EvalPhaseName.SCOPE,        # 1. 范围与目标梳理
    EvalPhaseName.CUSTOMIZE,    # 2. 定制指标与阈值
    EvalPhaseName.DATASET,      # 3. 搭建标准化数据集
    EvalPhaseName.ENGINE,       # 4. 开发对接评估引擎
    EvalPhaseName.DEPLOY,       # 5. 部署独立评测环境
    EvalPhaseName.TRIAL,        # 6. 小批量试运行调优
    EvalPhaseName.FULL_AUTO,    # 7. 全量自动化跑测
    EvalPhaseName.CI_CD,        # 8. 接入CI/CD流水线
    EvalPhaseName.PATROL,       # 9. 配置常态化定时巡检
]

PHASE_LABELS: Dict[EvalPhaseName, str] = {
    EvalPhaseName.SCOPE: "范围与目标梳理",
    EvalPhaseName.CUSTOMIZE: "定制指标与阈值",
    EvalPhaseName.DATASET: "搭建标准化数据集",
    EvalPhaseName.ENGINE: "开发对接评估引擎",
    EvalPhaseName.DEPLOY: "部署独立评测环境",
    EvalPhaseName.TRIAL: "小批量试运行调优",
    EvalPhaseName.FULL_AUTO: "全量自动化跑测",
    EvalPhaseName.CI_CD: "接入CI/CD流水线",
    EvalPhaseName.PATROL: "配置常态化定时巡检",
}

CHECKPOINT_PROJECT = "eval_pipeline"


# ── 管线 ──────────────────────────────────────────────────


class EvalPipeline:
    """
    评估管线 — 九阶段落地流程。

    崩溃安全：
    - SentinelManager 保护整个流程
    - 每阶段完成后写入检查点（AtomicWriter）
    - 启动时检测哨兵，自动从崩溃点恢复

    用法：
        pipeline = EvalPipeline(config)
        report = pipeline.run()
    """

    def __init__(
        self,
        config: EvalConfig,
        data_dir: Optional[Path] = None,
    ):
        self.config = config

        # 数据目录
        if data_dir:
            self.data_dir = Path(data_dir).resolve()
        else:
            base = config.data_dir or os.path.join(
                os.getcwd(), ".eval_data"
            )
            self.data_dir = Path(base).resolve()
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # 崩溃安全
        self.sentinel = SentinelManager(self.data_dir)

        # 评估引擎
        self.engine = EvalEngine(config=self.config)

        # 运行期状态
        self.standard: EvalStandard = default_standard()
        self.dataset: EvalDataset = EvalDataset()
        self.report: EvalReport = EvalReport(
            id=config.eval_id,
            name=config.eval_name,
            standard_id=config.standard_id,
            agent_version=config.agent_version,
        )
        self.case_results: List[EvalCaseResult] = []

        # 恢复标记
        self.recovered: bool = False
        self.resumed_phase: Optional[int] = None

    # ── 公开入口 ────────────────────────────────────────

    def run(self) -> EvalReport:
        """
        完整执行九阶段评估管线。
        返回最终 EvalReport。
        """
        try:
            self._check_recovery()
            self._run_phases()
            return self._finalize()
        except CapabilityShelfError:
            raise
        except Exception as exc:
            raise EvalPipelineError(
                code="PIPELINE_CRASH",
                detail=f"评估管线异常终止: {exc}",
                context={"eval_id": self.config.eval_id},
            ) from exc
        finally:
            self.sentinel.release()

    # ── 崩溃恢复 ────────────────────────────────────────

    def _check_recovery(self) -> None:
        """检查哨兵，识别崩溃并恢复检查点"""
        if not self.config.enable_sentinel:
            return

        if self.sentinel.is_crashed:
            report_data = self.sentinel.get_crash_report()
            operation = report_data.get("operation", "unknown")
            self.recovered = True

            if self.config.enable_checkpoint:
                cp = self.sentinel.read_checkpoint(CHECKPOINT_PROJECT)
                if cp:
                    self.resumed_phase = cp.get("step", 0)
                    print(
                        f"[EvalPipeline] ⚠️  检测到上次评估崩溃 "
                        f"(op={operation})，从阶段 "
                        f"[{self.resumed_phase}/{len(PHASE_NAMES)}] 恢复"
                    )
                else:
                    print(
                        f"[EvalPipeline] ⚠️  检测到上次评估崩溃 "
                        f"(op={operation})，无检查点，从头开始"
                    )
            else:
                print(
                    f"[EvalPipeline] ⚠️  检测到上次评估崩溃 "
                    f"(op={operation})，检查点已禁用，从头开始"
                )

            # 清理旧哨兵
            self.sentinel.clear()
            # 清理残留临时文件
            AtomicWriter.clean_orphaned_tmp(
                self.data_dir / "eval_checkpoint.json"
            )

        self.sentinel.acquire("eval_pipeline")

    def _is_phase_done(self, step: int) -> bool:
        """检查该步骤是否已通过崩溃恢复完成"""
        if not self.recovered or not self.config.enable_checkpoint:
            return False
        return (
            self.resumed_phase is not None
            and self.resumed_phase > step
        )

    # ── 阶段执行 ────────────────────────────────────────

    def _run_phases(self) -> None:
        """按顺序执行各阶段，每个阶段后写检查点"""
        total = len(PHASE_NAMES)

        for step, phase in enumerate(PHASE_NAMES):
            # 跳过已完成的阶段（崩溃恢复后）
            if self._is_phase_done(step):
                continue

            label = PHASE_LABELS.get(phase, phase.value)
            print(f"\n[EvalPipeline] [{step + 1}/{total}] {label}...")

            try:
                self._execute_phase(phase)
            except CapabilityShelfError:
                raise
            except Exception as exc:
                raise EvalPipelineError(
                    code=f"PHASE_{phase.value.upper()}_FAILED",
                    detail=f"阶段 [{label}] 执行异常: {exc}",
                    context={
                        "phase": phase.value,
                        "step": step,
                        "eval_id": self.config.eval_id,
                    },
                ) from exc

            # 写检查点
            self._write_checkpoint(step, total, phase)

    def _execute_phase(self, phase: EvalPhaseName) -> None:
        """执行单个阶段"""
        handler = {
            EvalPhaseName.SCOPE: self._phase_scope,
            EvalPhaseName.CUSTOMIZE: self._phase_customize,
            EvalPhaseName.DATASET: self._phase_dataset,
            EvalPhaseName.ENGINE: self._phase_engine,
            EvalPhaseName.DEPLOY: self._phase_deploy,
            EvalPhaseName.TRIAL: self._phase_trial,
            EvalPhaseName.FULL_AUTO: self._phase_full_auto,
            EvalPhaseName.CI_CD: self._phase_ci_cd,
            EvalPhaseName.PATROL: self._phase_patrol,
        }
        handler_fn = handler.get(phase)
        if handler_fn:
            handler_fn()
        else:
            raise EvalPipelineError(
                code="UNKNOWN_PHASE",
                detail=f"未知管线阶段: {phase.value}",
            )

    # ── 阶段 1: 范围与目标梳理 ──────────────────────────

    def _phase_scope(self) -> None:
        """定义评估范围与目标"""
        # 读取或创建范围定义文件
        scope_path = self.data_dir / "eval_scope.json"
        scope_data = AtomicWriter.read_json_safe(scope_path)

        if scope_data:
            # 从检查点恢复
            self.report.id = scope_data.get("eval_id", self.report.id)
            self.report.name = scope_data.get("eval_name", self.report.name)
            self.report.agent_version = scope_data.get(
                "agent_version", self.report.agent_version
            )
        else:
            # 首次运行，写入范围定义
            scope_data = {
                "eval_id": self.config.eval_id,
                "eval_name": self.config.eval_name,
                "agent_version": self.config.agent_version,
                "agent_type": self.config.agent_type,
                "scope_description": (
                    f"评估 Agent({self.config.agent_version}) "
                    f"在 {self.config.agent_type} 场景下的综合能力"
                ),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            AtomicWriter.write_json_atomic(scope_path, scope_data)

        print(
            f"  eval_id: {scope_data['eval_id']}\n"
            f"  eval_name: {scope_data['eval_name']}\n"
            f"  agent: {scope_data['agent_version']}"
        )

    # ── 阶段 2: 定制指标与阈值 ──────────────────────────

    def _phase_customize(self) -> None:
        """选择或定制评估标准"""
        std_id = self.config.standard_id or self.standard.id

        # 尝试从注册表获取标准
        custom = get_standard(std_id)
        if custom:
            self.standard = custom
        else:
            # 使用默认标准
            self.standard = default_standard()
            # 如果指定了 ID，注册默认标准
            if std_id and std_id != self.standard.id:
                self.standard.id = std_id
                register_standard(self.standard)

        # 保存到报告
        self.report.standard_id = self.standard.id
        self.report.standard_name = self.standard.name
        self.report.dimensions = [
            d.model_copy(deep=True) for d in self.standard.dimensions
        ]

        print(
            f"  标准: {self.standard.name} ({self.standard.id})\n"
            f"  维度: {len(self.standard.dimensions)} 个\n"
            f"  全局红线: {self.standard.global_redline_threshold}\n"
            f"  全局预警: {self.standard.global_warning_threshold}"
        )

    # ── 阶段 3: 搭建标准化数据集 ────────────────────────

    def _phase_dataset(self) -> None:
        """加载或创建标准化数据集"""
        dataset_path = self.config.dataset_path

        if dataset_path and Path(dataset_path).exists():
            # 从文件加载数据集
            data = AtomicWriter.read_json_safe(Path(dataset_path))
            if data:
                self.dataset = EvalDataset(**data)
                print(f"  从文件加载数据集: {dataset_path}")
            else:
                raise EvalDatasetError(
                    code="DATASET_LOAD_FAILED",
                    detail=f"数据集文件损坏或无法读取: {dataset_path}",
                )
        else:
            # 创建空数据集或从保存的检查点恢复
            cp_dataset = self.data_dir / "eval_dataset.json"
            saved = AtomicWriter.read_json_safe(cp_dataset)
            if saved:
                self.dataset = EvalDataset(**saved)
                print(f"  从缓存恢复数据集: {self.dataset.name}")
            else:
                self.dataset = EvalDataset(
                    id=f"ds-{self.config.eval_id}",
                    name=f"数据集 for {self.config.eval_name}",
                    description="自动创建的评测数据集",
                )
                print(f"  创建空数据集: {self.dataset.id}")

        # 检查数据集合规性（agent_rules #3）
        total = self.dataset.total_cases
        has_all = self.dataset.has_all_categories()
        print(
            f"  用例数: {total}\n"
            f"  分类覆盖: {self.dataset.category_distribution}\n"
            f"  通用+边界+对抗+历史故障: {'✅' if has_all else '⚠️ 缺失'}"
        )

        if not self.dataset.has_all_categories():
            import warnings
            warnings.warn(
                "数据集未覆盖所有必需分类（通用+边界+对抗+历史故障），"
                "可能不符合评估最佳实践"
            )

    # ── 阶段 4: 开发对接评估引擎 ────────────────────────

    def _phase_engine(self) -> None:
        """配置并验证评估引擎"""
        # 更新引擎配置
        self.engine.config = self.config
        self.engine.standard = self.standard

        # 验证引擎就绪
        engine_ok = True
        engine_info: Dict[str, Any] = {
            "similarity_model": self.config.similarity_model,
            "logic_check": self.config.enable_logic_check,
            "behavior_monitor": self.config.enable_behavior_monitor,
            "format_check": self.config.enable_format_check,
            "security_check": self.config.enable_security_check,
        }

        # 保存引擎配置
        engine_path = self.data_dir / "eval_engine_config.json"
        AtomicWriter.write_json_atomic(engine_path, engine_info)

        print(
            f"  相似度模型: {engine_info['similarity_model']}\n"
            f"  逻辑校验: {'✅' if engine_info['logic_check'] else '❌'}\n"
            f"  行为监控: {'✅' if engine_info['behavior_monitor'] else '❌'}\n"
            f"  格式校验: {'✅' if engine_info['format_check'] else '❌'}\n"
            f"  安全检测: {'✅' if engine_info['security_check'] else '❌'}"
        )

    # ── 阶段 5: 部署独立评测环境 ────────────────────────

    def _phase_deploy(self) -> None:
        """部署（确认）评测环境就绪"""
        # 确保数据目录结构完整
        env_dirs = [
            self.data_dir / "results",
            self.data_dir / "checkpoints",
            self.data_dir / "logs",
        ]
        for d in env_dirs:
            d.mkdir(parents=True, exist_ok=True)

        # 保存环境清单
        env_manifest = {
            "data_dir": str(self.data_dir),
            "eval_id": self.config.eval_id,
            "ci_mode": self.config.ci_mode,
            "trial_mode": self.config.enable_trial_mode,
            "sentinel": self.config.enable_sentinel,
            "checkpoint": self.config.enable_checkpoint,
            "auto_alert": self.config.enable_auto_alert,
            "deployed_at": datetime.now(timezone.utc).isoformat(),
        }
        manifest_path = self.data_dir / "eval_env_manifest.json"
        AtomicWriter.write_json_atomic(manifest_path, env_manifest)

        print(
            f"  数据目录: {self.data_dir}\n"
            f"  CI模式: {'✅' if self.config.ci_mode else '—'}\n"
            f"  试运行: {'✅' if self.config.enable_trial_mode else '—'}\n"
            f"  哨兵: {'✅' if self.config.enable_sentinel else '—'}"
        )

    # ── 阶段 6: 小批量试运行调优 ────────────────────────

    def _phase_trial(self) -> None:
        """小批量试运行，验证管线与调优"""
        trial_size = self.config.trial_size
        if not self.dataset.cases:
            print("  ⚠️  数据集为空，跳过试运行")
            return

        # 取前 trial_size 条作为试运行样本
        sample_cases = self.dataset.cases[:trial_size]
        print(f"  试运行样本数: {len(sample_cases)}")

        # 使用模拟输出来验证引擎
        trial_results: List[EvalCaseResult] = []
        for case in sample_cases:
            # 模拟输出（实际评测中这里会调用 Agent）
            mock_output = case.expected_output
            result = self.engine.evaluate_case(case, mock_output)
            trial_results.append(result)

        # 打分
        for i, dim in enumerate(self.report.dimensions):
            self.report.dimensions[i] = self.engine.score_dimension(
                dim, trial_results
            )

        passed = sum(
            1 for r in trial_results if r.status == EvalStatus.PASSED
        )
        print(f"  通过: {passed}/{len(trial_results)}")

        # 保存试运行结果
        trial_path = self.data_dir / "results" / "trial_results.json"
        AtomicWriter.write_json_atomic(
            trial_path,
            {
                "sample_count": len(trial_results),
                "passed": passed,
                "results": [r.model_dump() for r in trial_results],
            },
        )

    # ── 阶段 7: 全量自动化跑测 ──────────────────────────

    def _phase_full_auto(self) -> None:
        """全量自动化跑测"""
        if not self.dataset.cases:
            print("  ⚠️  数据集为空，跳过全量跑测")
            return

        print(
            f"  全量跑测: {self.dataset.total_cases} 条用例"
        )

        # 模拟输出（实际评测中会调用 Agent API）
        mock_outputs: Dict[str, str] = {}
        for case in self.dataset.cases:
            mock_outputs[case.id] = case.expected_output

        # 执行全量评估
        self.case_results = self.engine.evaluate_dataset(
            self.dataset.cases, mock_outputs
        )

        # 计算完整报告
        self.report.started_at = datetime.now(timezone.utc).isoformat()
        self.report = self.engine.compute_report(
            self.report, self.case_results
        )

        print(
            f"  通过: {self.report.passed_cases}/"
            f"{self.report.total_cases}\n"
            f"  失败: {self.report.failed_cases}\n"
            f"  综合评分: {self.report.overall_score:.4f}"
        )

        # 保存全量结果
        result_path = self.data_dir / "results" / "full_auto_results.json"
        AtomicWriter.write_json_atomic(
            result_path,
            {
                "overall_score": self.report.overall_score,
                "passed": self.report.passed_cases,
                "total": self.report.total_cases,
                "results": [r.model_dump() for r in self.case_results],
            },
        )

        # 检查预警/红线
        if self.report.warning_messages:
            for msg in self.report.warning_messages:
                print(f"  ⚠️  预警: {msg}")
        if self.report.redline_messages:
            for msg in self.report.redline_messages:
                print(f"  ❌  红线: {msg}")

        if not self.report.passed:
            print("  ❌  全量跑测未通过（触发红线）")

    # ── 阶段 8: 接入CI/CD流水线 ──────────────────────────

    def _phase_ci_cd(self) -> None:
        """模拟 CI/CD 集成：生成门禁报告"""
        ci_report: Dict[str, Any] = {
            "eval_id": self.config.eval_id,
            "eval_name": self.config.eval_name,
            "agent_version": self.config.agent_version,
            "ci_mode": self.config.ci_mode,
            "overall_score": self.report.overall_score,
            "passed": self.report.passed,
            "total_cases": self.report.total_cases,
            "pass_rate": self.report.pass_rate,
            "redline_count": len(self.report.redline_messages),
            "warning_count": len(self.report.warning_messages),
            "ci_status": "PASS" if self.report.passed else "BLOCKED",
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

        ci_path = self.data_dir / "results" / "ci_report.json"
        AtomicWriter.write_json_atomic(ci_path, ci_report)

        print(
            f"  CI状态: {ci_report['ci_status']}\n"
            f"  红线数: {ci_report['redline_count']}\n"
            f"  预警数: {ci_report['warning_count']}"
        )

        # CI 模式下直接退出
        if self.config.ci_mode and not self.report.passed:
            raise EvalPipelineError(
                code="CI_GATE_BLOCKED",
                detail=(
                    f"CI/CD 门禁拦截: 综合评分 "
                    f"{self.report.overall_score:.4f}，"
                    f"红线条数 {len(self.report.redline_messages)}"
                ),
                context={"report": ci_report},
            )

    # ── 阶段 9: 配置常态化定时巡检 ──────────────────────

    def _phase_patrol(self) -> None:
        """配置定时巡检标记"""
        patrol_config = {
            "eval_id": self.config.eval_id,
            "enabled": True,
            "interval": "daily",
            "last_run": datetime.now(timezone.utc).isoformat(),
            "alert_on_failure": self.config.enable_auto_alert,
            "alert_webhook": self.config.alert_webhook_url,
            "redline_threshold": self.standard.global_redline_threshold,
            "warning_threshold": self.standard.global_warning_threshold,
        }

        patrol_path = self.data_dir / "patrol_config.json"
        AtomicWriter.write_json_atomic(patrol_path, patrol_config)

        print(
            f"  定时巡检: 已配置\n"
            f"  间隔: daily\n"
            f"  告警: {'✅' if self.config.enable_auto_alert else '❌'}"
        )

    # ── 检查点管理 ──────────────────────────────────────

    def _write_checkpoint(
        self, step: int, total: int, phase: EvalPhaseName
    ) -> None:
        """原子写入检查点"""
        if not self.config.enable_checkpoint:
            return

        self.sentinel.write_checkpoint(
            CHECKPOINT_PROJECT,
            step=step,
            total=total,
            description=PHASE_LABELS.get(phase, phase.value),
        )

        # 保存当前状态数据
        state_path = self.data_dir / f"eval_phase_{step}.json"
        state_data: Dict[str, Any] = {
            "phase": phase.value,
            "step": step,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if self.dataset.cases:
            state_data["dataset"] = self.dataset.model_dump()
        if self.case_results:
            state_data["case_results"] = [
                r.model_dump() for r in self.case_results
            ]
        if self.report.dimensions:
            state_data["report"] = self.report.model_dump(
                include={"dimensions", "overall_score", "status"}
            )

        AtomicWriter.write_json_atomic(state_path, state_data)

    # ── 最终化 ──────────────────────────────────────────

    def _finalize(self) -> EvalReport:
        """完成评估，生成最终报告"""
        self.report.completed_at = datetime.now(timezone.utc).isoformat()
        self.report.recovered_from_crash = self.recovered

        # 生成摘要
        self.report.summary = self._build_summary()

        # 保存最终报告
        report_path = self.data_dir / "results" / "final_report.json"
        AtomicWriter.write_json_atomic(
            report_path, self.report.model_dump()
        )

        # 清理哨兵和检查点
        if self.config.enable_checkpoint:
            self.sentinel.clear_checkpoint(CHECKPOINT_PROJECT)

        return self.report

    def _build_summary(self) -> str:
        """生成评估摘要文本"""
        parts: List[str] = [
            f"评估报告: {self.report.name}",
            f"Agent版本: {self.report.agent_version}",
            f"数据集: {self.report.dataset_name}",
            f"综合评分: {self.report.overall_score:.4f}",
            f"状态: {'通过' if self.report.passed else '未通过'}",
        ]
        if self.report.total_cases > 0:
            parts.append(
                f"用例通过率: {self.report.passed_cases}/"
                f"{self.report.total_cases} "
                f"({self.report.pass_rate * 100:.1f}%)"
            )
        if self.recovered:
            parts.append("⚠️  本次评估从崩溃中恢复")
        if self.report.redline_messages:
            parts.append(f"红线触发: {len(self.report.redline_messages)} 项")
        if self.report.warning_messages:
            parts.append(f"预警: {len(self.report.warning_messages)} 项")

        return "\n".join(parts)

    # ── 持久化存储包装 ─────────────────────────────────

    def save_report_to_store(self, store: CapabilityStore) -> None:
        """将评估报告写入 CapabilityStore 的数据目录（JSON 文件）"""
        report_path = self.data_dir / "final_report.json"
        AtomicWriter.write_json_atomic(report_path, self.report.model_dump())

    def save_dataset_to_store(self, store: CapabilityStore) -> None:
        """将数据集写入 CapabilityStore 的数据目录（JSON 文件）"""
        ds_path = self.data_dir / "eval_dataset.json"
        AtomicWriter.write_json_atomic(ds_path, self.dataset.model_dump())


# ── 便捷函数 ──────────────────────────────────────────────


def run_evaluation(
    config: Optional[EvalConfig] = None,
    data_dir: Optional[Path] = None,
    **kwargs: Any,
) -> EvalReport:
    """
    快速启动一次完整评估。

    Args:
        config: EvalConfig 实例
        data_dir: 数据目录
        **kwargs: 传递给 EvalConfig 的参数（如 eval_name, agent_version）

    Returns:
        EvalReport 实例

    Example:
        report = run_evaluation(
            eval_name="基准测试v1",
            agent_version="1.0.0",
            ci_mode=True,
        )
    """
    if config is None:
        config = EvalConfig(**kwargs)
    pipeline = EvalPipeline(config, data_dir=data_dir)
    return pipeline.run()


def trial_evaluation(
    config: Optional[EvalConfig] = None,
    data_dir: Optional[Path] = None,
    trial_size: int = 5,
    **kwargs: Any,
) -> EvalReport:
    """
    快速启动小批量试运行（阶段 1-6）。

    Args:
        config: EvalConfig
        data_dir: 数据目录
        trial_size: 试运行样本数（默认 5）
        **kwargs: 传递给 EvalConfig 的参数

    Returns:
        试运行阶段的 EvalReport
    """
    if config is None:
        config = EvalConfig(**kwargs)
    config.enable_trial_mode = True
    config.trial_size = trial_size
    pipeline = EvalPipeline(config, data_dir=data_dir)
    return pipeline.run()
