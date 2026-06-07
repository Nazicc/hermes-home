"""
reliability.models — 可靠性模块 Pydantic 数据模型
==================================================
设计原则：
  - 纯数据模型，零业务逻辑
  - 使用 Pydantic v2 BaseModel
  - 全部 JSON 可序列化
  - 每个模型中文化注释便于团队理解

涵盖：引擎、管线、兜底、监控四个子模块的模型
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from pydantic import BaseModel, Field


# ════════════════════════════════════════════════════════════
# 枚举定义
# ════════════════════════════════════════════════════════════


class ValidationLevel(str, Enum):
    """前置准入校验级别（agent_rules 第1条：三重校验）"""
    FORMAT = "format"          # 入参格式校验
    VALUE = "value"            # 值域校验
    PERMISSION = "permission"  # 权限校验


class RetryMode(str, Enum):
    """重试模式（agent_rules 第5条：幂等）"""
    FIXED = "fixed"                # 固定间隔
    EXPONENTIAL = "exponential"    # 指数退避
    JITTER = "jitter"              # 抖动退避


class DegradeLevel(str, Enum):
    """降级级别（agent_rules 第7条：简化→兜底话术）"""
    NONE = "none"                    # 无降级
    SIMPLIFY = "simplify"            # 简化处理
    CACHE = "cache"                  # 走缓存
    FALLBACK_TOOL = "fallback_tool"  # 备用工具
    FALLBACK_TEXT = "fallback_text"  # 兜底话术


class CircuitState(str, Enum):
    """熔断器状态"""
    CLOSED = "closed"        # 正常
    OPEN = "open"            # 熔断打开
    HALF_OPEN = "half_open"  # 半开探测


class IsolationScope(str, Enum):
    """故障隔离范围"""
    TOOL = "tool"          # 单工具隔离
    SUBAGENT = "subagent"  # 子代理隔离
    MODEL = "model"        # 模型隔离
    CONTEXT = "context"    # 上下文隔离


class AlertLevel(str, Enum):
    """告警等级"""
    DEBUG = "debug"
    INFO = "info"
    WARN = "warn"
    ERROR = "error"
    CRITICAL = "critical"


class MetricType(str, Enum):
    """监控指标类型"""
    LATENCY_P99 = "latency_p99"
    LATENCY_AVG = "latency_avg"
    ERROR_RATE = "error_rate"
    TOKEN_USAGE = "token_usage"
    REQUEST_COUNT = "request_count"
    SUCCESS_RATE = "success_rate"


class PhaseStatus(str, Enum):
    """管线段状态"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


# ════════════════════════════════════════════════════════════
# 配置模型
# ════════════════════════════════════════════════════════════


class RetryPolicy(BaseModel):
    """重试策略 — 对应 agent_rules 第5条（幂等重试）"""
    enabled: bool = True
    mode: RetryMode = RetryMode.EXPONENTIAL
    max_attempts: int = 3
    base_delay_ms: float = 1000.0
    max_delay_ms: float = 30000.0
    jitter_factor: float = 0.1
    idempotent: bool = True  # 强制幂等


class CircuitConfig(BaseModel):
    """熔断器配置 — 对应 agent_rules 第6条"""
    enabled: bool = True
    failure_threshold: int = 5           # 连续失败N次后打开
    recovery_timeout_s: float = 30.0     # 熔断恢复等待秒数
    half_open_max_requests: int = 3      # 半开状态最大探测请求
    consecutive_success_to_close: int = 2  # 半开状态下连续成功N次后关闭


class TimeoutConfig(BaseModel):
    """多级超时配置 — 对应 agent_rules 第6条"""
    enabled: bool = True
    tool_timeout_s: float = 30.0         # 工具级超时
    subagent_timeout_s: float = 120.0    # 子代理级超时
    pipeline_timeout_s: float = 300.0    # 管线级超时
    model_response_timeout_s: float = 60.0  # 模型响应超时


class FallbackPlan(BaseModel):
    """降级兜底方案 — 对应 agent_rules 第7、11条"""
    degrade_levels: List[DegradeLevel] = Field(
        default_factory=lambda: [
            DegradeLevel.SIMPLIFY,
            DegradeLevel.CACHE,
            DegradeLevel.FALLBACK_TOOL,
            DegradeLevel.FALLBACK_TEXT,
        ]
    )
    fallback_tools: Dict[str, str] = Field(
        default_factory=dict,
        description="主工具→备用工具映射: {'primary_id': 'fallback_id'}",
    )
    cache_ttl_s: float = 300.0  # 缓存降级有效期


class ReliabilityConfig(BaseModel):
    """可靠性模块全局配置"""
    enabled: bool = True
    precheck_enabled: bool = True         # 前置准入
    runtime_control_enabled: bool = True  # 运行管控
    context_truncation_enabled: bool = True  # 上下文截断
    dead_loop_detection_enabled: bool = True  # 死循环检测
    max_tool_calls_per_step: int = 20     # 单步最大工具调用次数
    max_context_tokens: int = 128000      # 最大上下文Token数
    truncation_reserve_ratio: float = 0.2  # 截断保留比例
    rate_limit_per_minute: int = 60       # 每分钟最大请求数
    retry: RetryPolicy = Field(default_factory=RetryPolicy)
    circuit_breaker: CircuitConfig = Field(default_factory=CircuitConfig)
    timeout: TimeoutConfig = Field(default_factory=TimeoutConfig)
    fallback: FallbackPlan = Field(default_factory=FallbackPlan)


# ════════════════════════════════════════════════════════════
# 运行时数据模型
# ════════════════════════════════════════════════════════════


class ToolCallRecord(BaseModel):
    """工具调用记录 — 用于二次校验 + 死循环检测"""
    tool_name: str
    args: Dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    call_id: str = ""
    success: bool = False
    error: str = ""
    duration_ms: float = 0.0
    token_cost: int = 0


class SubAgentTask(BaseModel):
    """子代理任务 — 对应 agent_rules 第2条：长任务拆分"""
    task_id: str
    parent_id: str = ""             # 父任务ID
    name: str = ""
    description: str = ""
    input_data: Dict[str, Any] = Field(default_factory=dict)
    status: str = "pending"         # pending → running → success/failed
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    retry_count: int = 0
    timeout_s: float = 120.0


class AccessLog(BaseModel):
    """全链路接入日志 — 对应 agent_rules 第9条"""
    request_id: str
    caller: str = "system"
    action: str = ""
    resource: str = ""
    input_summary: str = ""
    status: str = "pending"
    validation_passed: bool = False
    validation_errors: List[str] = Field(default_factory=list)
    tool_calls: List[ToolCallRecord] = Field(default_factory=list)
    sub_tasks: List[SubAgentTask] = Field(default_factory=list)
    start_time: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    end_time: Optional[str] = None
    duration_ms: float = 0.0
    degrade_level: DegradeLevel = DegradeLevel.NONE
    error: Optional[str] = None


class MonitorMetrics(BaseModel):
    """多维度监控指标 — 对应"观测溯源"维度"""
    total_requests: int = 0
    avg_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    max_latency_ms: float = 0.0
    total_token_usage: int = 0
    success_rate: float = 1.0
    tool_stats: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class CircuitStateData(BaseModel):
    """熔断器运行时状态"""
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: Optional[str] = None
    last_success_time: Optional[str] = None
    opened_at: Optional[str] = None
    half_open_requests: int = 0


class IsolatedComponent(BaseModel):
    """被隔离的组件记录"""
    component_id: str
    scope: IsolationScope = IsolationScope.TOOL
    isolated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    reason: str = ""
    auto_recover: bool = True
    recover_after_s: float = 60.0


class PipelinePhase(BaseModel):
    """管线阶段记录 — 用于 checkpointed pipeline"""
    phase_name: str
    phase_index: int = 0
    total_phases: int = 0
    status: PhaseStatus = PhaseStatus.PENDING
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    checkpoint_data: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


class AlertRule(BaseModel):
    """告警规则（用于 monitoring 模块规则引擎）"""
    name: str
    metric: MetricType = MetricType.ERROR_RATE
    condition: str = "gt"         # gt/lt/gte/lte
    threshold: float = 0.0
    level: AlertLevel = AlertLevel.WARN
    message_template: str = "[{name}] 当前值 {current}，阈值 {threshold}"
    actions: List[str] = Field(default_factory=lambda: ["log"])
    enabled: bool = True
    cooldown_s: float = 300.0
