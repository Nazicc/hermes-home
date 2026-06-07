"""
reliability — AI Agent调用可靠性全维度保障方案
===============================================
架构：前置校验 → 运行管控 → 异常兜底 → 观测溯源 → 架构优化

模块概览：
  exceptions.py  可靠性异常层次（继承 CapabilityShelfError）
  models.py      所有 Pydantic 数据模型
  engine.py      前置校验 + 运行管控 + 死循环检测
  pipeline.py    全生命周期 checkpointed pipeline
  fallback.py    分级重试 + 熔断 + 降级 + 隔离
  monitoring.py  全链路日志 + 指标 + 告警

崩溃安全：
  所有写操作通过 AtomicWriter(fsync=True)
  长流程使用 SentinelManager 分阶段保护
  所有异常继承 CapabilityShelfError

公开 API（推荐导入方式）：
  from ai_capability_shelf.reliability import (
      ReliabilityEngine, ReliabilityPipeline,
      FallbackManager, Monitor,
      ReliabilityError, ...
  )
"""

from __future__ import annotations

from ai_capability_shelf.reliability.exceptions import (
    ReliabilityError,
    ValidationError,
    TimeoutError,
    RetryExhaustedError,
    CircuitBreakerError,
    FallbackError,
    IsolationError,
    DeadLoopError,
    ContextOverflowError,
    MonitorError,
)

from ai_capability_shelf.reliability.models import (
    # 枚举
    ValidationLevel,
    RetryMode,
    DegradeLevel,
    CircuitState,
    IsolationScope,
    AlertLevel,
    MetricType,
    PhaseStatus,
    # 配置
    RetryPolicy,
    CircuitConfig,
    TimeoutConfig,
    FallbackPlan,
    ReliabilityConfig,
    # 运行时数据
    ToolCallRecord,
    SubAgentTask,
    AccessLog,
    MonitorMetrics,
    CircuitStateData,
    IsolatedComponent,
    PipelinePhase,
    AlertRule,
)

from ai_capability_shelf.reliability.engine import ReliabilityEngine

from ai_capability_shelf.reliability.pipeline import ReliabilityPipeline

from ai_capability_shelf.reliability.fallback import FallbackManager

from ai_capability_shelf.reliability.monitoring import Monitor

__all__ = [
    # 异常
    "ReliabilityError",
    "ValidationError",
    "TimeoutError",
    "RetryExhaustedError",
    "CircuitBreakerError",
    "FallbackError",
    "IsolationError",
    "DeadLoopError",
    "ContextOverflowError",
    "MonitorError",
    # 枚举
    "ValidationLevel",
    "RetryMode",
    "DegradeLevel",
    "CircuitState",
    "IsolationScope",
    "AlertLevel",
    "MetricType",
    "PhaseStatus",
    # 配置
    "RetryPolicy",
    "CircuitConfig",
    "TimeoutConfig",
    "FallbackPlan",
    "ReliabilityConfig",
    # 运行时数据
    "ToolCallRecord",
    "SubAgentTask",
    "AccessLog",
    "MonitorMetrics",
    "CircuitStateData",
    "IsolatedComponent",
    "PipelinePhase",
    "AlertRule",
    # 核心类
    "ReliabilityEngine",
    "ReliabilityPipeline",
    "FallbackManager",
    "Monitor",
]
