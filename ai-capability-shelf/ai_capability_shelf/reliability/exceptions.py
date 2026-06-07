"""
reliability.exceptions — 可靠性模块专属异常层次
=================================================
继承 CapabilityShelfError 基类，保持与父项目的异常体系一致。

异常层级:
  ReliabilityError
    ├─ ValidationError      入参/值域/权限校验失败
    ├─ TimeoutError         多级超时触发
    ├─ RetryExhaustedError  重试耗尽
    ├─ CircuitBreakerError  熔断器已打开
    ├─ FallbackError        降级/兜底失败
    ├─ IsolationError       故障隔离触发
    ├─ DeadLoopError        死循环拦截
    ├─ ContextOverflowError 上下文溢出/截断
    └─ MonitorError         监控/告警异常
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from ai_capability_shelf.exceptions import CapabilityShelfError


class ReliabilityError(CapabilityShelfError):
    """可靠性模块基类异常"""


class ValidationError(ReliabilityError):
    """入参/值域/权限三重校验失败 — 对应 agent_rules 第1条"""

    def __init__(
        self,
        message: str = "",
        *,
        field: str = "",
        detail: str = "",
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        ctx = dict(context or {})
        if field:
            ctx["field"] = field
        super().__init__(
            message or f"校验失败: {field}" if field else "校验失败",
            code="RELIABILITY_VALIDATION",
            detail=detail,
            context=ctx,
        )


class TimeoutError(ReliabilityError):
    """多级超时触发 — 对应 agent_rules 第6条"""

    def __init__(
        self,
        message: str = "",
        *,
        level: str = "",
        timeout: float = 0,
        detail: str = "",
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        ctx = dict(context or {})
        if level:
            ctx["level"] = level
        if timeout:
            ctx["timeout"] = timeout
        super().__init__(
            message or f"超时触发 [level={level}]" if level else "超时触发",
            code="RELIABILITY_TIMEOUT",
            detail=detail,
            context=ctx,
        )


class RetryExhaustedError(ReliabilityError):
    """幂等重试耗尽 — 对应 agent_rules 第5条"""

    def __init__(
        self,
        message: str = "",
        *,
        operation: str = "",
        attempts: int = 0,
        detail: str = "",
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        ctx = dict(context or {})
        if operation:
            ctx["operation"] = operation
        if attempts:
            ctx["attempts"] = attempts
        super().__init__(
            message or f"重试耗尽: {operation}" if operation else "重试耗尽",
            code="RETRY_EXHAUSTED",
            detail=detail,
            context=ctx,
        )


class CircuitBreakerError(ReliabilityError):
    """熔断器已打开 — 连续失败触发熔断，拒绝请求"""

    def __init__(
        self,
        message: str = "",
        *,
        circuit_name: str = "",
        failure_count: int = 0,
        detail: str = "",
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        ctx = dict(context or {})
        if circuit_name:
            ctx["circuit_name"] = circuit_name
        if failure_count:
            ctx["failure_count"] = failure_count
        super().__init__(
            message or f"熔断已打开: {circuit_name}" if circuit_name else "熔断已打开",
            code="CIRCUIT_OPEN",
            detail=detail,
            context=ctx,
        )


class FallbackError(ReliabilityError):
    """降级/兜底策略执行失败 — 对应 agent_rules 第7条"""

    def __init__(
        self,
        message: str = "",
        *,
        level: str = "",
        fallback_name: str = "",
        detail: str = "",
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        ctx = dict(context or {})
        if level:
            ctx["level"] = level
        if fallback_name:
            ctx["fallback_name"] = fallback_name
        super().__init__(
            message or f"降级失败 [{level}]: {fallback_name}" if level else "降级失败",
            code="FALLBACK_ERROR",
            detail=detail,
            context=ctx,
        )


class IsolationError(ReliabilityError):
    """故障隔离触发 — 对应 agent_rules 第8条"""

    def __init__(
        self,
        message: str = "",
        *,
        component: str = "",
        detail: str = "",
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        ctx = dict(context or {})
        if component:
            ctx["component"] = component
        super().__init__(
            message or f"故障隔离: {component}" if component else "故障隔离",
            code="ISOLATION_ERROR",
            detail=detail,
            context=ctx,
        )


class DeadLoopError(ReliabilityError):
    """死循环拦截 — 工具调用次数/重复模式超限"""

    def __init__(
        self,
        message: str = "",
        *,
        tool_name: str = "",
        call_count: int = 0,
        pattern: str = "",
        detail: str = "",
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        ctx = dict(context or {})
        if tool_name:
            ctx["tool_name"] = tool_name
        if call_count:
            ctx["call_count"] = call_count
        if pattern:
            ctx["pattern"] = pattern
        super().__init__(
            message or f"死循环拦截: {tool_name}" if tool_name else "死循环拦截",
            code="DEAD_LOOP",
            detail=detail,
            context=ctx,
        )


class ContextOverflowError(ReliabilityError):
    """上下文溢出/截断触发"""

    def __init__(
        self,
        message: str = "",
        *,
        token_count: int = 0,
        max_tokens: int = 0,
        detail: str = "",
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        ctx = dict(context or {})
        if token_count:
            ctx["token_count"] = token_count
        if max_tokens:
            ctx["max_tokens"] = max_tokens
        super().__init__(
            message or f"上下文溢出: {token_count}/{max_tokens}",
            code="CONTEXT_OVERFLOW",
            detail=detail,
            context=ctx,
        )


class MonitorError(ReliabilityError):
    """监控/告警异常 — 日志写入失败、指标上报失败"""
