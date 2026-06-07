"""
evaluation — AI Agent 自动化评估体系
======================================

五层架构：环境层 → 数据集层 → 引擎层 → 分析层 → 流转层

九阶段落地流程：
1. 范围与目标梳理 → 2. 定制指标与阈值 → 3. 搭建标准化数据集
4. 开发对接评估引擎 → 5. 部署独立评测环境 → 6. 小批量试运行调优
7. 全量自动化跑测 → 8. 接入CI/CD流水线 → 9. 配置常态化定时巡检

崩溃安全：AtomicWriter + SentinelManager + 阶段检查点
"""

from .exceptions import (
    EvalError,
    EvalConfigError,
    EvalDatasetError,
    EvalDatasetCorruptionError,
    EvalEngineError,
    EvalComparisonError,
    EvalBehaviorError,
    EvalSecurityError,
    EvalPipelineError,
    EvalPhaseError,
    EvalCheckpointError,
    EvalRedlineError,
    EvalWarningError,
)

from .models import (
    EvalCase,
    EvalCaseResult,
    EvalDataset,
    EvalDimension,
    EvalDimensionType,
    EvalMetric,
    EvalScore,
    EvalStandard,
    EvalConfig,
    EvalPhaseName,
    EvalStatus,
    EvalReport,
)

from .standards import (
    default_standard,
    lightweight_standard,
    ci_pipeline_standard,
    get_standard,
    register_standard,
    list_standards,
    list_standard_ids,
)

from .engine import (
    EvalEngine,
)

from .pipeline import (
    EvalPipeline,
    run_evaluation,
    trial_evaluation,
    PHASE_NAMES,
    PHASE_LABELS,
)

__all__ = [
    # Exceptions
    "EvalError",
    "EvalConfigError",
    "EvalDatasetError",
    "EvalDatasetCorruptionError",
    "EvalEngineError",
    "EvalComparisonError",
    "EvalBehaviorError",
    "EvalSecurityError",
    "EvalPipelineError",
    "EvalPhaseError",
    "EvalCheckpointError",
    "EvalRedlineError",
    "EvalWarningError",
    # Models
    "EvalCase",
    "EvalCaseResult",
    "EvalDataset",
    "EvalDimension",
    "EvalDimensionType",
    "EvalMetric",
    "EvalScore",
    "EvalStandard",
    "EvalConfig",
    "EvalPhaseName",
    "EvalStatus",
    "EvalReport",
    # Standards
    "default_standard",
    "lightweight_standard",
    "ci_pipeline_standard",
    "get_standard",
    "register_standard",
    "list_standards",
    "list_standard_ids",
    # Engine
    "EvalEngine",
    # Pipeline
    "EvalPipeline",
    "run_evaluation",
    "trial_evaluation",
    "PHASE_NAMES",
    "PHASE_LABELS",
]
