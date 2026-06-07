"""
统一异常层次 — CapabilityShelfError 基类 + 子类体系
=================================================
设计原则：
- 所有异常继承 CapabilityShelfError，调用方只需捕获这一个基类
- 每层/模块有专属子类，精准定位问题来源
- 异常附带结构化上下文（code, detail, context）方便日志/CLI 展示
- 支持链式异常（__cause__），保留完整回溯
"""

from __future__ import annotations

from typing import Any, Dict, Optional


# ════════════════════════════════════════════════════════════
# 基类
# ════════════════════════════════════════════════════════════


class CapabilityShelfError(Exception):
    """
    所有异常的基类。

    调用方只需捕获 CapabilityShelfError 即可覆盖全系统异常。
    附带 code/detail/context 供 CLI 及日志系统结构化展示。
    """

    def __init__(
        self,
        message: str = "",
        *,
        code: str = "UNKNOWN",
        detail: str = "",
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.code = code
        self.detail = detail
        self.context = context or {}
        super().__init__(message)

    @property
    def message(self) -> str:
        """获取人类可读的消息（第一个参数）"""
        return str(self.args[0]) if self.args else ""

    def to_dict(self) -> Dict[str, Any]:
        """结构化输出，适合日志/CLI 展示"""
        return {
            "code": self.code,
            "message": self.message,
            "detail": self.detail,
            "context": self.context,
        }


# ════════════════════════════════════════════════════════════
# 持久化层异常
# ════════════════════════════════════════════════════════════


class PersistenceError(CapabilityShelfError):
    """
    持久化层异常 — IO 失败、序列化故障、存储损毁。
    对应 persistence.py 中的各种 IO/JSON 错误。
    """


class AtomicWriteError(PersistenceError):
    """原子写入失败 — 临时文件写入/重命名/fsync 任一环节出错"""

    def __init__(
        self,
        path: str = "",
        *,
        detail: str = "",
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        ctx = dict(context or {})
        if path:
            ctx["path"] = path
        super().__init__(
            f"原子写入失败: {path}" if path else "原子写入失败",
            code="ATOMIC_WRITE",
            detail=detail,
            context=ctx,
        )


class SentinelError(PersistenceError):
    """哨兵文件操作失败 — 创建/释放/读取问题"""


class StoreError(PersistenceError):
    """存储操作失败 — 加载/保存/清理失败"""

    def __init__(
        self,
        operation: str = "store",
        *,
        detail: str = "",
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        ctx = dict(context or {})
        ctx["operation"] = operation
        super().__init__(
            f"存储操作失败 ({operation})",
            code="STORE_ERROR",
            detail=detail,
            context=ctx,
        )


class StoreCorruptionError(StoreError):
    """存储数据损毁 — JSON 解析失败、数据结构异常"""

    def __init__(
        self,
        path: str = "",
        *,
        detail: str = "",
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        ctx = dict(context or {})
        if path:
            ctx["path"] = path
        super().__init__(
            "store_corruption",
            detail=f"数据损毁: {detail}",
            context=ctx,
        )


# ════════════════════════════════════════════════════════════
# 注册表异常
# ════════════════════════════════════════════════════════════


class RegistryError(CapabilityShelfError):
    """注册表操作异常 — 对应 registry.py"""


class RegistrationError(RegistryError):
    """注册冲突/重复 — 能力已存在"""

    def __init__(
        self,
        cap_id: str = "",
        *,
        detail: str = "",
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            f"注册冲突: {cap_id}" if cap_id else "注册冲突",
            code="REGISTRATION_CONFLICT",
            detail=detail,
            context=dict(context or {}),
        )


class NotFoundError(RegistryError):
    """能力/组件未找到"""

    def __init__(
        self,
        cap_id: str = "",
        kind: str = "capability",
        *,
        detail: str = "",
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            f"{kind} 未找到: {cap_id}" if cap_id else f"{kind} 未找到",
            code="NOT_FOUND",
            detail=detail,
            context=dict(context or {}),
        )


# ════════════════════════════════════════════════════════════
# 校验/标准化异常
# ════════════════════════════════════════════════════════════


class ValidationError(CapabilityShelfError):
    """校验/标准化失败 — 对应 standardization.py"""

    def __init__(
        self,
        message: str = "",
        *,
        code: str = "VALIDATION",
        detail: str = "",
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message or "校验失败",
            code=code,
            detail=detail,
            context=context,
        )


class VersionError(ValidationError):
    """版本号格式/操作非法 — 应替代 VersionManager 中的 ValueError"""

    def __init__(
        self,
        version: str = "",
        part: str = "",
        *,
        detail: str = "",
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        ctx = dict(context or {})
        if version:
            ctx["version"] = version
        if part:
            ctx["part"] = part
        super().__init__(
            f"无效版本号: {version}" if version else "版本号错误",
            code="VERSION_ERROR",
            detail=detail,
            context=ctx,
        )


class InterfaceError(ValidationError):
    """接口校验失败"""


# ════════════════════════════════════════════════════════════
# 模型层异常
# ════════════════════════════════════════════════════════════


class ModelError(CapabilityShelfError):
    """模型数据校验/构造失败 — 对应 models.py"""

    def __init__(
        self,
        message: str = "",
        *,
        code: str = "MODEL_ERROR",
        detail: str = "",
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message or "模型数据错误",
            code=code,
            detail=detail,
            context=context,
        )


# ════════════════════════════════════════════════════════════
# 运行时异常
# ════════════════════════════════════════════════════════════


class RuntimeError_(CapabilityShelfError):
    """
    运行时执行异常 — 对应 runtime.py。

    注意：使用 RuntimeError_ 避免与内置 RuntimeError 冲突。
    """


class TimeoutError(RuntimeError_):
    """执行超时 — with_timeout 超时返回 None"""

    def __init__(
        self,
        func_name: str = "",
        timeout: float = 0,
        *,
        detail: str = "",
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        ctx = dict(context or {})
        if timeout:
            ctx["timeout"] = timeout
        super().__init__(
            f"执行超时: {func_name}" if func_name else "执行超时",
            code="TIMEOUT",
            detail=detail,
            context=ctx,
        )


class ExecutionFailure(RuntimeError_):
    """组件执行失败 — 运行时调用出错"""

    def __init__(
        self,
        component_id: str = "",
        *,
        detail: str = "",
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            f"组件执行失败: {component_id}" if component_id else "组件执行失败",
            code="EXECUTION_FAILURE",
            detail=detail,
            context=dict(context or {}),
        )


class CircuitBreakerOpenError(RuntimeError_):
    """熔断器已打开 — 拒绝请求"""

    def __init__(
        self,
        circuit_name: str = "",
        *,
        detail: str = "",
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            f"熔断器已打开: {circuit_name}" if circuit_name else "熔断器已打开",
            code="CIRCUIT_OPEN",
            detail=detail,
            context=dict(context or {}),
        )


# ════════════════════════════════════════════════════════════
# 生命周期/管线异常
# ════════════════════════════════════════════════════════════


class LifecycleError(CapabilityShelfError):
    """生命周期编排异常 — 对应 lifecycle.py"""


class CheckpointError(LifecycleError):
    """检查点读写失败"""

    def __init__(
        self,
        project: str = "",
        *,
        detail: str = "",
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            f"检查点失败: {project}" if project else "检查点失败",
            code="CHECKPOINT_ERROR",
            detail=detail,
            context=dict(context or {}),
        )


class PipelineError(LifecycleError):
    """管线步骤执行失败"""

    def __init__(
        self,
        step: str = "",
        *,
        detail: str = "",
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        ctx = dict(context or {})
        if step:
            ctx["step"] = step
        super().__init__(
            f"管线步骤失败: {step}" if step else "管线步骤失败",
            code="PIPELINE_ERROR",
            detail=detail,
            context=ctx,
        )


# ════════════════════════════════════════════════════════════
# 组合层异常
# ════════════════════════════════════════════════════════════


class CompositionError(CapabilityShelfError):
    """组合/DAG 编排异常 — 对应 composition.py"""


class CycleError(CompositionError):
    """DAG 循环依赖检测到"""

    def __init__(
        self,
        cycle: str = "",
        *,
        detail: str = "",
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            f"DAG 循环依赖: {cycle}" if cycle else "DAG 循环依赖",
            code="CYCLE_DETECTED",
            detail=detail,
            context=dict(context or {}),
        )


# ════════════════════════════════════════════════════════════
# 管控层异常
# ════════════════════════════════════════════════════════════


class GovernanceError(CapabilityShelfError):
    """管控策略违规 — 对应 governance.py"""


class RateLimitError(GovernanceError):
    """限流触发"""

    def __init__(
        self,
        cap_id: str = "",
        *,
        detail: str = "",
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            f"限流触发: {cap_id}" if cap_id else "限流触发",
            code="RATE_LIMIT",
            detail=detail,
            context=dict(context or {}),
        )


class AccessDeniedError(GovernanceError):
    """权限不足"""

    def __init__(
        self,
        role: str = "",
        required: str = "",
        *,
        detail: str = "",
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            f"权限不足: role={role}, required={required}",
            code="ACCESS_DENIED",
            detail=detail,
            context=dict(context or {}),
        )


class DuplicateCapabilityError(RegistrationError):
    """重复注册能力 — 能力 ID 已存在"""

    def __init__(
        self,
        cap_id: str = "",
        *,
        detail: str = "",
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            cap_id,
            detail=detail or f"能力 '{cap_id}' 已注册",
            context=context,
        )


class CapabilityNotFoundError(NotFoundError):
    """能力未找到 — 封装 NotFoundError 的语义别名"""

    def __init__(
        self,
        cap_id: str = "",
        *,
        detail: str = "",
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            cap_id,
            kind="capability",
            detail=detail,
            context=context,
        )


class InvalidCapabilityError(ValidationError):
    """能力数据校验不通过 — 字段缺失/类型错误/规则违反"""

    def __init__(
        self,
        cap_id: str = "",
        *,
        detail: str = "",
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            f"能力数据校验不通过: {cap_id}" if cap_id else "能力数据校验不通过",
            code="INVALID_CAPABILITY",
            detail=detail,
            context=context,
        )


class StandardizationError(ValidationError):
    """标准化处理失败 — 接口/版本/格式标准化异常"""

    def __init__(
        self,
        message: str = "",
        *,
        detail: str = "",
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message or "标准化处理失败",
            code="STANDARDIZATION_ERROR",
            detail=detail,
            context=context,
        )


# ════════════════════════════════════════════════════════════
# 简化工厂函数
# ════════════════════════════════════════════════════════════


def raise_with_context(
    exc_class: type,
    message: str,
    *,
    code: str = "",
    detail: str = "",
    context: Optional[Dict[str, Any]] = None,
) -> None:
    """一行内 raise 带上下文的异常"""
    kwargs: Dict[str, Any] = {"detail": detail, "context": context}
    if code:
        kwargs["code"] = code
    raise exc_class(message, **kwargs)
