"""
evaluation.exceptions — 评估体系专属异常层次
==============================================
继承 CapabilityShelfError 基类，保持与父项目的异常体系一致。
高内聚：只定义异常类。
低耦合：仅依赖父项目 exceptions，不引用其他 evaluation 模块。
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from ai_capability_shelf.exceptions import CapabilityShelfError


class EvalError(CapabilityShelfError):
    """评估模块基类异常"""


class EvalConfigError(EvalError):
    """评估配置错误 — 缺少必需参数或配置冲突"""

    def __init__(
        self,
        message: str = "",
        *,
        detail: str = "",
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message or "评估配置错误",
            code="EVAL_CONFIG",
            detail=detail,
            context=context,
        )


class EvalDatasetError(EvalError):
    """数据集操作失败 — 加载/校验/分类错误"""

    def __init__(
        self,
        message: str = "",
        *,
        detail: str = "",
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message or "数据集操作失败",
            code="EVAL_DATASET",
            detail=detail,
            context=context,
        )


class EvalDatasetCorruptionError(EvalDatasetError):
    """数据集数据损毁 — 格式错误、字段缺失"""


class EvalEngineError(EvalError):
    """评估引擎执行失败"""

    def __init__(
        self,
        message: str = "",
        *,
        detail: str = "",
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message or "评估引擎执行失败",
            code="EVAL_ENGINE",
            detail=detail,
            context=context,
        )


class EvalComparisonError(EvalEngineError):
    """内容比对失败 — 语义/逻辑比对异常"""


class EvalBehaviorError(EvalEngineError):
    """行为监控检测到异常模式 — 死循环、异常中断"""

    def __init__(
        self,
        message: str = "",
        *,
        detail: str = "",
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        ctx = dict(context or {})
        if "pattern" not in ctx:
            ctx["pattern"] = "unknown"
        super().__init__(
            message or "行为监控异常",
            code="EVAL_BEHAVIOR",
            detail=detail,
            context=ctx,
        )


class EvalSecurityError(EvalEngineError):
    """安全检测失败 — 注入/越权检出异常"""


class EvalPipelineError(EvalError):
    """管线执行失败 — 阶段检查点/恢复错误"""

    def __init__(
        self,
        message: str = "",
        *,
        detail: str = "",
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        ctx = dict(context or {})
        super().__init__(
            message or "管线执行失败",
            code="EVAL_PIPELINE",
            detail=detail,
            context=ctx,
        )


class EvalPhaseError(EvalPipelineError):
    """某阶段执行失败（附带阶段名）"""

    def __init__(
        self,
        phase: str = "",
        *,
        detail: str = "",
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        ctx = dict(context or {})
        ctx["phase"] = phase
        super().__init__(
            f"阶段 [{phase}] 执行失败" if phase else "阶段执行失败",
            code="EVAL_PHASE",
            detail=detail,
            context=ctx,
        )


class EvalCheckpointError(EvalPipelineError):
    """检查点读写失败 — 数据保存/恢复错误"""

    def __init__(
        self,
        phase: str = "",
        *,
        detail: str = "",
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        ctx = dict(context or {})
        ctx["phase"] = phase
        super().__init__(
            f"检查点失败: [{phase}]" if phase else "检查点失败",
            code="EVAL_CHECKPOINT",
            detail=detail,
            context=ctx,
        )


class EvalRedlineError(EvalError):
    """不合格红线触发 — 指标跌破阈值"""

    def __init__(
        self,
        metric: str = "",
        threshold: float = 0.0,
        actual: float = 0.0,
        *,
        detail: str = "",
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        ctx = dict(context or {})
        ctx["metric"] = metric
        ctx["threshold"] = threshold
        ctx["actual"] = actual
        super().__init__(
            f"红线触发: {metric} 阈值={threshold} 实际={actual}",
            code="EVAL_REDLINE",
            detail=detail,
            context=ctx,
        )


class EvalWarningError(EvalError):
    """预警线触发 — 指标接近阈值需要关注"""

    def __init__(
        self,
        metric: str = "",
        threshold: float = 0.0,
        actual: float = 0.0,
        *,
        detail: str = "",
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        ctx = dict(context or {})
        ctx["metric"] = metric
        ctx["threshold"] = threshold
        ctx["actual"] = actual
        super().__init__(
            f"预警触发: {metric} 预警线={threshold} 实际={actual}",
            code="EVAL_WARNING",
            detail=detail,
            context=ctx,
        )
