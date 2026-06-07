"""
生命周期层 — 七步搭建流程
========================
全链路运转闭环：
  盘点 → 拆解 → 封装 → 上架 → 配置管控 → 内测 → 上线迭代

每步通过统一的 _run_step + PipelineContext 调度
崩溃后重启可通过哨兵检测恢复进度（从检查点继续）

高内聚：只处理"搭建流程编排"
低耦合：通过 PipelineContext 传递数据，步骤间无直接依赖
崩溃安全：SentinelManager 原子写入 + fsync
"""

from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, NamedTuple, Optional, Tuple
from datetime import datetime, timezone
from dataclasses import dataclass, field

from ai_capability_shelf.models import (
    AtomicComponent,
    CompositeSkill,
    ScenarioSolution,
    CapabilityStatus,
    InterfaceSpec,
    InvokeProtocol,
    ErrorCategory,
)
from ai_capability_shelf.governance import GovernancePolicy
from ai_capability_shelf.persistence import AtomicWriter, CapabilityStore, SentinelManager
from ai_capability_shelf.standardization import StandardizationService
from ai_capability_shelf.registry import CapabilityRegistry
from ai_capability_shelf.composition import CompositionValidator
from ai_capability_shelf.governance import GovernanceGuard
from ai_capability_shelf.runtime import RuntimeEngine


# ═══════════════════════════════════════════════
# 管线上下文 & 步骤定义（高内聚数据载体）
# ═══════════════════════════════════════════════

@dataclass
class PipelineContext:
    """
    管线上下文 — 步骤间数据传递的单一载体。

    输入字段由调用方填充，输出字段由各步骤方法写入。
    新增步骤只需在 dataclass 中新增字段，不改其他代码。
    """
    # ── 输入参数（build_pipeline 调用方传入） ──
    project_name: str
    capabilities: List[Dict[str, Any]]
    policies: Optional[Dict[str, GovernancePolicy]] = None
    test_cases: Optional[List[Dict[str, Any]]] = None
    composites: Optional[List[CompositeSkill]] = None
    scenarios: Optional[List[ScenarioSolution]] = None
    skip_validation: bool = False

    # ── 步骤输出（由 step_* 方法写入） ──
    # 步骤 1
    inventory_report: Dict[str, Any] = field(default_factory=dict)
    # 步骤 2
    atomic_defs: List[Dict[str, Any]] = field(default_factory=list)
    # 步骤 3
    package_success: int = 0
    package_total: int = 0
    package_errors: List[str] = field(default_factory=list)
    # 步骤 4
    shelve_count: int = 0
    # 步骤 5
    configure_result: Dict[str, Any] = field(default_factory=dict)
    # 步骤 6
    test_result: Dict[str, Any] = field(default_factory=dict)
    # 步骤 7
    launch_result: Dict[str, Any] = field(default_factory=dict)


class StepDef(NamedTuple):
    """步骤元数据定义 — 每行定义一个步骤"""
    number: int               # 步骤编号（1-7）
    name: str                 # 方法后缀 → step_<name>
    label: str                # 中文标签
    condition: Optional[str] = None  # ctx 字段名；为 None 时无条件执行


# ═══════════════════════════════════════════════
# 七步生命周期管理器
# ═══════════════════════════════════════════════

class LifecycleManager:
    """
    七步搭建流程管理器。

    STEPS 表 + _run_step 统一调度实现低耦合：
    - 所有 step_* 方法签名统一为 (self, ctx: PipelineContext)
    - 检查点写入 / build_log 记录由 _run_step 统一完成
    - 新增步骤只需：① 向 STEPS 加一行；② 实现 step_<name>(ctx)
    """

    STEPS: List[StepDef] = [
        StepDef(1, "inventory",  "盘点"),
        StepDef(2, "decompose",  "拆解"),
        StepDef(3, "package",    "封装"),
        StepDef(4, "shelve",     "上架"),
        StepDef(5, "configure",  "配置管控", condition="policies"),
        StepDef(6, "test",       "内测",     condition="test_cases"),
        StepDef(7, "launch",     "上线"),
    ]

    def __init__(
        self,
        registry: CapabilityRegistry,
        store: CapabilityStore,
        work_dir: str | Path = "~/.cap_shelf/checkpoints",
    ):
        self.registry = registry
        self.store = store
        self.sentinel = SentinelManager(Path(work_dir).expanduser())
        self._build_log: List[Dict[str, Any]] = []

    # ── 步骤方法（全部签名统一：self, ctx -> Any） ──────────────────

    def step_inventory(self, ctx: PipelineContext) -> Dict[str, Any]:
        """盘点现有能力"""
        items = [
            {
                "name": cap.get("name", "unknown"),
                "description": cap.get("description", ""),
                "category": cap.get("category", "unclassified"),
                "complexity": cap.get("complexity", "medium"),
            }
            for cap in ctx.capabilities
        ]
        return {
            "project": ctx.project_name,
            "total": len(items),
            "items": items,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def step_decompose(self, ctx: PipelineContext) -> List[Dict[str, Any]]:
        """拆解能力至原子组件"""
        atomics: List[Dict[str, Any]] = []
        for item in ctx.inventory_report.get("items", []):
            name = item.get("name", "unknown")
            slug = name.lower().replace(" ", "_")
            atomics.append({
                "id": f"atomic.{ctx.project_name}.{slug}",
                "name": name,
                "description": item.get("description", ""),
                "category": item.get("category", "unclassified"),
                "version": "0.1.0",
                "status": CapabilityStatus.DRAFT,
                "invoke": InvokeProtocol.FUNCTION,
                "interface": {
                    "input_schema": {"type": "object", "properties": {}},
                    "output_schema": {"type": "object", "properties": {}},
                    "error_definitions": [
                        {"code": "INTERNAL_ERROR", "message": "内部错误",
                         "category": ErrorCategory.INTERNAL.value},
                    ],
                },
                "tags": [ctx.project_name, item.get("category", "")],
            })
        return atomics

    def step_package(self, ctx: PipelineContext) -> Tuple[int, int, List[str]]:
        """封装原子组件并注册到货架"""
        success = 0
        errors: List[str] = []
        for defn in ctx.atomic_defs:
            try:
                component = AtomicComponent(**defn)
                if not ctx.skip_validation:
                    valid, val_errors = StandardizationService.check_atomic(component)
                    if not valid:
                        errors.append(f"{component.id}: 标准化校验失败 — {'; '.join(val_errors)}")
                        continue
                self.registry.register_atomic(component)
                success += 1
            except Exception as e:
                errors.append(f"封装失败: {e!s}")
        return success, len(ctx.atomic_defs), errors

    def step_shelve(self, ctx: PipelineContext) -> int:
        """上架到货架（设为 ON_SHELF）"""
        count = 0
        for defn in ctx.atomic_defs:
            comp = self.registry.get_atomic(defn.get("id", ""))
            if comp:
                comp.status = CapabilityStatus.ON_SHELF
                self.registry.register_atomic(comp)
                count += 1
        for skill in (ctx.composites or []):
            skill.status = CapabilityStatus.ON_SHELF
            self.registry.register_composite(skill)
            count += 1
        for scenario in (ctx.scenarios or []):
            scenario.status = CapabilityStatus.ON_SHELF
            self.registry.register_scenario(scenario)
            count += 1
        return count

    def step_configure(self, ctx: PipelineContext) -> Dict[str, Any]:
        """为能力配置管控策略"""
        applied: List[str] = []
        for cap_id, policy in (ctx.policies or {}).items():
            self.registry.state.governance_policies[cap_id] = policy
            applied.append(cap_id)
        return {"applied_to": applied, "count": len(applied),
                "timestamp": datetime.now(timezone.utc).isoformat()}

    def step_test(self, ctx: PipelineContext) -> Dict[str, Any]:
        """内测能力"""
        engine = RuntimeEngine(self.registry.state)
        results: List[Dict[str, Any]] = []
        passed = 0
        failed = 0
        for tc in (ctx.test_cases or []):
            cap_id = tc.get("cap_id", "")
            comp = self.registry.get_atomic(cap_id)
            if not comp:
                results.append({"cap_id": cap_id, "success": False, "error": "未注册"})
                failed += 1
                continue
            r = engine.execute_atomic(cap_id, tc.get("input_data"))
            r_dict = r.to_dict()
            results.append(r_dict)
            if r_dict["success"]:
                passed += 1
            else:
                failed += 1
        return {
            "project": ctx.project_name,
            "passed": passed,
            "failed": failed,
            "total": len(ctx.test_cases or []),
            "results": results,
        }

    def step_launch(self, ctx: PipelineContext) -> Dict[str, Any]:
        """上线迭代 — 持久化 + 清理检查点"""
        self.store.save(self.registry.state)
        self.sentinel.clear_checkpoint(ctx.project_name)
        self._save_build_log(ctx.project_name)
        result = {
            "project": ctx.project_name,
            "status": "launched",
            "stats": self.registry.count(),
            "build_log": list(self._build_log),
        }
        return result

    # ── 统一调度核心 ──────────────────────────────────

    def _run_step(
        self,
        step_def: StepDef,
        ctx: PipelineContext,
        start_step: int,
    ) -> Dict[str, Any]:
        """
        统一步骤执行器。

        职责：
        1. 检查点跳过判断（start_step >= 当前步骤 → 跳过）
        2. 条件步跳过判断（condition 字段指向的 ctx 属性为 None → 跳过）
        3. 反射调用 step_<name>(ctx)
        4. 回写 ctx 输出字段（约定：step_<name> 的返回值写入 ctx.<name>_<field>）
        5. 记录 build_log
        6. 原子写入检查点（步骤执行后写入 → 崩溃时未完成步骤不会留下已完成标记）
        7. 持久化 build_log（原子 fsync 写入）

        返回给 build_pipeline 的摘要字典。
        """
        # ── 跳过判断 ──
        if start_step >= step_def.number:
            return {"status": "skipped", "reason": "已从检查点恢复"}
        if step_def.condition and getattr(ctx, step_def.condition, None) is None:
            return {"status": "skipped", "reason": f"缺少 {step_def.condition}"}

        # ── 反射调用步骤方法 ──
        result = getattr(self, f"step_{step_def.name}")(ctx)

        # ── 回写 ctx 输出字段 ──
        self._write_step_result(step_def, ctx, result)

        # ── 记录 build_log ──
        self._build_log.append({
            "step": step_def.number,
            "name": step_def.name,
            "label": step_def.label,
            "result": result,
        })

        # ── 写检查点（步骤执行后 — 崩溃时步骤未完成 → 不写检查点，重启重做） ──
        # 最后一步（step 7/launch）不写检查点：step_launch 内部已调 clear_checkpoint
        if step_def.number < 7:
            self.sentinel.write_checkpoint(ctx.project_name, step_def.number, 7, step_def.label)

        # ── 持久化 build_log ──
        self._save_build_log(ctx.project_name)

        return {"status": "done", "result": result}

    def _write_step_result(
        self,
        step_def: StepDef,
        ctx: PipelineContext,
        result: Any,
    ) -> None:
        """
        将步骤返回值回写到 ctx 对应字段，供后续步骤读取。

        映射规则（按步骤编号）：
        step 1 → ctx.inventory_report
        step 2 → ctx.atomic_defs
        step 3 → ctx.package_success / package_total / package_errors
        step 4 → ctx.shelve_count
        step 5 → ctx.configure_result
        step 6 → ctx.test_result
        step 7 → ctx.launch_result
        """
        n = step_def.number
        if n == 1:
            ctx.inventory_report = result
        elif n == 2:
            ctx.atomic_defs = result
        elif n == 3:
            ok, total, errors = result
            ctx.package_success = ok
            ctx.package_total = total
            ctx.package_errors = errors
        elif n == 4:
            ctx.shelve_count = result
        elif n == 5:
            ctx.configure_result = result
        elif n == 6:
            ctx.test_result = result
        elif n == 7:
            ctx.launch_result = result

    # ── build_log 持久化（原子 fsync 写入） ────────────

    def _build_log_path(self, project_name: str) -> Path:
        """返回 build_log 文件路径"""
        return self.sentinel.data_dir / f"{project_name}.build_log.json"

    def _save_build_log(self, project_name: str) -> None:
        """原子写入 build_log 到磁盘，供崩溃后重建上下文"""
        AtomicWriter.write_json_atomic(
            self._build_log_path(project_name),
            {"project": project_name, "entries": self._build_log},
        )

    def _load_build_log(self, project_name: str) -> None:
        """从磁盘重建 build_log（崩溃恢复路径调用）"""
        path = self._build_log_path(project_name)
        if path.exists():
            try:
                data = json.loads(path.read_text())
                self._build_log = data.get("entries", [])
            except (json.JSONDecodeError, OSError):
                self._build_log = []

    # ── 全流程入口 ──

    def build_pipeline(
        self,
        project_name: str,
        capabilities: List[Dict[str, Any]],
        policies: Optional[Dict[str, GovernancePolicy]] = None,
        test_cases: Optional[List[Dict[str, Any]]] = None,
        composites: Optional[List[CompositeSkill]] = None,
        scenarios: Optional[List[ScenarioSolution]] = None,
        skip_validation: bool = False,
    ) -> Dict[str, Any]:
        """
        七步全流程 — 循环调度 STEPS

        崩溃恢复：
        - 启动时读取检查点，从已完成的下一步继续
        - 每步完成写检查点 + fsync

        输出格式：
        {
            "project": ...,
            "recovery": bool,
            "steps": {
                "inventory":  {"status": "done", "result": ...},
                "decompose":  {"status": "done", "result": ...},
                ...
            },
            "final": {...}    # 仅 launch 完成后出现
        }
        """
        # ── 崩溃恢复检测 ──
        cp = self.sentinel.read_checkpoint(project_name)
        start_step = 0
        if cp:
            start_step = cp["step"]
            # 必须先加载持久化的 build_log，再追加 recovery 标记
            # 否则 recovery 条目会被 _load_build_log 覆盖丢失
            self._load_build_log(project_name)
            self._build_log.append({
                "step": -1, "name": "recovery",
                "data": {"recovered_from": cp, "resume_step": start_step + 1},
            })

        # ── 构造管线上下文 ──
        ctx = PipelineContext(
            project_name=project_name,
            capabilities=capabilities,
            policies=policies,
            test_cases=test_cases,
            composites=composites,
            scenarios=scenarios,
            skip_validation=skip_validation,
        )

        # ── 结果容器 ──
        results: Dict[str, Any] = {
            "project": project_name,
            "recovery": bool(cp),
            "steps": {},
        }

        # ── 循环调度所有步骤 ──
        for step_def in self.STEPS:
            step_result = self._run_step(step_def, ctx, start_step)
            results["steps"][step_def.name] = step_result

        # ── 组装最终结果 ──
        launch = results["steps"].get("launch", {})
        if launch.get("status") == "done":
            results["final"] = launch["result"]

        return results
