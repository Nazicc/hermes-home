"""
evaluation.models — 评估体系纯数据模型
========================================
Pydantic v2 模型，零外部依赖（仅 pydantic + datetime）。
高内聚：只定义数据结构，不含业务逻辑。
低耦合：不引用任何其他 evaluation 模块。
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ── 枚举定义 ──────────────────────────────────────────────


class EvalDatasetCategory(str, Enum):
    """数据集分类"""
    GENERAL = "general"                  # 通用用例
    INDUSTRY = "industry"                # 行业场景
    BOUNDARY = "boundary"                # 边界极端
    ADVERSARIAL = "adversarial"          # 对抗性
    HISTORICAL_BUG = "historical_bug"    # 历史故障用例


class EvalDimensionType(str, Enum):
    """评估维度分类"""
    FUNCTIONAL = "functional"             # 功能指标
    BEHAVIOR = "behavior"                 # 行为指标
    TOOL_CALL = "tool_call"               # 工具调用
    MEMORY = "memory"                     # 记忆指标
    OUTPUT_QUALITY = "output_quality"     # 输出质量
    PERFORMANCE = "performance"           # 性能指标
    SECURITY = "security"                 # 安全合规


class EvalPhaseName(str, Enum):
    """评估管线九阶段"""
    SCOPE = "scope"                           # 1. 范围与目标梳理
    CUSTOMIZE = "customize"                   # 2. 定制指标与阈值
    DATASET = "dataset"                       # 3. 搭建标准化数据集
    ENGINE = "engine"                         # 4. 开发对接评估引擎
    DEPLOY = "deploy"                         # 5. 部署独立评测环境
    TRIAL = "trial"                           # 6. 小批量试运行调优
    FULL_AUTO = "full_auto"                   # 7. 全量自动化跑测
    CI_CD = "ci_cd"                           # 8. 接入CI/CD流水线
    PATROL = "patrol"                         # 9. 配置常态化定时巡检


class EvalStatus(str, Enum):
    """评估状态"""
    PENDING = "pending"           # 待执行
    RUNNING = "running"           # 执行中
    PASSED = "passed"             # 通过
    FAILED = "failed"             # 不通过
    WARNING = "warning"           # 预警触发
    ERROR = "error"               # 执行异常
    CANCELLED = "cancelled"       # 已取消


# ── 数据模型 ──────────────────────────────────────────────


class EvalMetric(BaseModel):
    """单一指标定义"""
    id: str = ""
    name: str = ""
    description: str = ""
    unit: str = ""                    # 单位（如 %, ms, count）
    higher_is_better: bool = True     # 是否越大越好
    warning_threshold: Optional[float] = None   # 预警线
    redline_threshold: Optional[float] = None   # 不合格红线


class EvalScore(BaseModel):
    """单个指标的评分结果"""
    metric_id: str = ""
    metric_name: str = ""
    value: float = 0.0
    normalized: float = 0.0          # 归一化 0-1
    passed: bool = True
    warning_triggered: bool = False
    redline_triggered: bool = False
    detail: str = ""


class EvalDimension(BaseModel):
    """评估维度"""
    type: EvalDimensionType = EvalDimensionType.FUNCTIONAL
    name: str = ""
    description: str = ""
    weight: float = 1.0              # 综合权重
    metrics: List[EvalMetric] = Field(default_factory=list)
    scores: List[EvalScore] = Field(default_factory=list)

    def aggregate_score(self) -> float:
        """计算本维度综合得分（0-1）"""
        if not self.scores:
            return 0.0
        valid = [s for s in self.scores if s.metric_id]
        if not valid:
            return 0.0
        return sum(s.normalized for s in valid) / len(valid)


class EvalStandard(BaseModel):
    """评估标准 — 维度配置表与阈值模板"""
    id: str = ""
    name: str = ""
    description: str = ""
    dimensions: List[EvalDimension] = Field(default_factory=list)
    global_warning_threshold: float = 0.7    # 整体预警线
    global_redline_threshold: float = 0.5    # 整体不合格红线
    agent_type: str = ""                     # 适用 Agent 类型（通用/客服/编程等）
    version: str = "1.0.0"
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class EvalCase(BaseModel):
    """单条评测用例"""
    id: str = ""
    title: str = ""
    description: str = ""
    category: EvalDatasetCategory = EvalDatasetCategory.GENERAL
    input: str = ""                  # 输入内容
    expected_output: str = ""        # 预期输出
    expected_behavior: Dict[str, Any] = Field(default_factory=dict)  # 预期行为模式
    tags: List[str] = Field(default_factory=list)
    priority: int = 0                # 优先级 0-5
    metadata: Dict[str, Any] = Field(default_factory=dict)


class EvalDataset(BaseModel):
    """标准化评测数据集"""
    id: str = ""
    name: str = ""
    description: str = ""
    cases: List[EvalCase] = Field(default_factory=list)
    category_distribution: Dict[str, int] = Field(default_factory=dict)  # 各类别用例数
    total_cases: int = 0
    version: str = "1.0.0"
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def model_post_init(self, __context: Any) -> None:
        """自动计算统计信息"""
        self.total_cases = len(self.cases)
        dist: Dict[str, int] = {}
        for c in self.cases:
            key = c.category.value if isinstance(c.category, Enum) else str(c.category)
            dist[key] = dist.get(key, 0) + 1
        self.category_distribution = dist

    def by_category(self, category: EvalDatasetCategory) -> List[EvalCase]:
        """按分类筛选用例"""
        return [c for c in self.cases if c.category == category]

    def has_all_categories(self) -> bool:
        """检查是否覆盖所有必需分类（通用+边界+对抗+历史故障）"""
        required = {
            EvalDatasetCategory.GENERAL,
            EvalDatasetCategory.BOUNDARY,
            EvalDatasetCategory.ADVERSARIAL,
            EvalDatasetCategory.HISTORICAL_BUG,
        }
        present = set(c.category for c in self.cases)
        return required.issubset(present)


class EvalCaseResult(BaseModel):
    """单条用例的评测结果"""
    case_id: str = ""
    case_title: str = ""
    status: EvalStatus = EvalStatus.PENDING
    actual_output: str = ""
    similarity_score: float = 0.0        # 语义相似度
    logic_score: float = 0.0             # 逻辑校验得分
    format_compliant: bool = True        # 格式合规
    behavior_anomalies: List[str] = Field(default_factory=list)  # 行为异常列表
    security_issues: List[str] = Field(default_factory=list)     # 安全问题列表
    execution_time_ms: float = 0.0
    tool_calls: int = 0
    error_message: str = ""
    details: Dict[str, Any] = Field(default_factory=dict)


class EvalReport(BaseModel):
    """完整评估报告"""
    id: str = ""
    name: str = ""
    standard_id: str = ""
    standard_name: str = ""
    dataset_id: str = ""
    dataset_name: str = ""
    agent_version: str = ""
    status: EvalStatus = EvalStatus.PENDING
    dimensions: List[EvalDimension] = Field(default_factory=list)
    case_results: List[EvalCaseResult] = Field(default_factory=list)
    overall_score: float = 0.0
    passed: bool = True
    warning_messages: List[str] = Field(default_factory=list)
    redline_messages: List[str] = Field(default_factory=list)
    summary: str = ""
    pipeline_phase: str = ""
    recovered_from_crash: bool = False
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @property
    def total_cases(self) -> int:
        return len(self.case_results)

    @property
    def passed_cases(self) -> int:
        return sum(1 for r in self.case_results if r.status == EvalStatus.PASSED)

    @property
    def failed_cases(self) -> int:
        return sum(1 for r in self.case_results if r.status == EvalStatus.FAILED)

    @property
    def pass_rate(self) -> float:
        if not self.case_results:
            return 0.0
        return self.passed_cases / self.total_cases


class EvalConfig(BaseModel):
    """评估运行配置"""
    # 运行控制
    eval_id: str = ""
    eval_name: str = ""
    agent_version: str = ""
    agent_type: str = "general"

    # 数据
    data_dir: str = ""
    dataset_path: str = ""
    standard_id: str = ""

    # 引擎选项
    similarity_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    enable_logic_check: bool = True
    enable_behavior_monitor: bool = True
    enable_format_check: bool = True
    enable_security_check: bool = True
    enable_trial_mode: bool = False          # 小批量试运行
    trial_size: int = 10

    # CI/CD 模式
    ci_mode: bool = False                    # CI 模式（严格红线）
    ci_fail_on_warning: bool = False         # CI 预警是否视为失败

    # 崩溃安全
    enable_sentinel: bool = True
    enable_checkpoint: bool = True

    # 性能
    timeout_per_case_ms: int = 30000
    max_concurrency: int = 1

    # 告警
    enable_auto_alert: bool = True
    alert_webhook_url: str = ""
