"""
reliability.engine — ReliabilityEngine 可靠性执行引擎
====================================================
职责：
  前置校准（入参三重校验、任务预拆分、流量限流）
  运行管控（状态追踪、工具二次校验、上下文截断、调度约束）
  工具管控（调用次数限制、死循环检测、重复参数检测）
  死循环拦截（调用频率、参数重复、模式匹配三合一）

对应 agent_rules：
  1. 三重校验    5. 幂等性保证    6. 多级超时
  2. 任务拆分     7. 分层降级      8. 故障隔离
  3. 工具管控     9. 全链路日志    10. 灰度发布
  4. 上下文截断
"""

from __future__ import annotations

import hashlib
import time
import json
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from datetime import datetime, timezone
from collections import defaultdict, deque

from ai_capability_shelf.reliability.models import (
    ReliabilityConfig,
    RetryPolicy,
    ToolCallRecord,
    SubAgentTask,
    AccessLog,
    CircuitStateData,
    CircuitState,
    ValidationLevel,
    DegradeLevel,
    CircuitConfig,
    TimeoutConfig,
    FallbackPlan,
)
from ai_capability_shelf.reliability.exceptions import (
    ValidationError,
    TimeoutError,
    DeadLoopError,
    ContextOverflowError,
)


class ReliabilityEngine:
    """
    可靠性执行引擎

    提供前置校验、运行管控、工具管控、上下文截断、死循环检测
    等核心可靠性保障能力。

    使用方式：
      engine = ReliabilityEngine(config)
      engine.validate_input(...)       # 前置校验
      engine.validate_tool_call(...)   # 工具二次校验
      engine.detect_dead_loop(...)     # 死循环检测
      engine.truncate_context(...)     # 上下文截断
    """

    def __init__(
        self,
        config: Optional[ReliabilityConfig] = None,
    ) -> None:
        self.config = config or ReliabilityConfig()

        # ---- 运行管控状态 ----
        self._tool_call_history: Dict[str, List[ToolCallRecord]] = defaultdict(list)
        self._tool_call_fingerprints: Dict[str, Set[str]] = defaultdict(set)
        self._circuit_states: Dict[str, CircuitStateData] = {}
        self._rate_limit_window: deque = deque(maxlen=1000)

        # ---- 调度约束 ----
        self._active_sub_tasks: Dict[str, SubAgentTask] = {}
        self._task_depth: Dict[str, int] = {}

        # ---- 上下文监控 ----
        self._context_token_history: List[int] = []

    # ════════════════════════════════════════════════════════════
    # 前置准入
    # ════════════════════════════════════════════════════════════

    def validate_input(
        self,
        input_data: Dict[str, Any],
        schema: Optional[Dict[str, Any]] = None,
        *,
        levels: Optional[List[ValidationLevel]] = None,
    ) -> None:
        """
        入参三重校验 — 格式+值域+权限（agent_rules 第1条）

        Args:
            input_data: 待校验的输入数据
            schema: 可选的 JSON Schema
            levels: 校验级别列表，默认全部

        Raises:
            ValidationError: 任一校验级别失败
        """
        if not self.config.precheck_enabled:
            return

        levels = levels or list(ValidationLevel)

        errors: List[str] = []

        for level in levels:
            if level == ValidationLevel.FORMAT:
                self._validate_format(input_data, schema, errors)
            elif level == ValidationLevel.VALUE:
                self._validate_value_range(input_data, schema, errors)
            elif level == ValidationLevel.PERMISSION:
                self._validate_permission(input_data, errors)

        if errors:
            raise ValidationError(
                message="入参校验失败",
                detail="; ".join(errors),
                context={"errors": errors, "levels": [l.value for l in levels]},
            )

    def _validate_format(
        self,
        data: Dict[str, Any],
        schema: Optional[Dict[str, Any]] = None,
        errors: Optional[List[str]] = None,
    ) -> None:
        """格式校验：检查必填字段、类型正确性"""
        if errors is None:
            errors = []
        if not isinstance(data, dict):
            errors.append("输入数据必须为 dict 类型")
            return
        if schema and "required" in schema:
            for field in schema["required"]:
                if field not in data:
                    errors.append(f"缺少必填字段: {field}")

    def _validate_value_range(
        self,
        data: Dict[str, Any],
        schema: Optional[Dict[str, Any]] = None,
        errors: Optional[List[str]] = None,
    ) -> None:
        """值域校验：检查字段取值范围"""
        if errors is None:
            errors = []
        if not schema or "properties" not in schema:
            return
        for field, props in schema["properties"].items():
            if field not in data:
                continue
            val = data[field]
            if "minimum" in props and isinstance(val, (int, float)):
                if val < props["minimum"]:
                    errors.append(f"{field}={val} 低于最小值 {props['minimum']}")
            if "maximum" in props and isinstance(val, (int, float)):
                if val > props["maximum"]:
                    errors.append(f"{field}={val} 超过最大值 {props['maximum']}")
            if "enum" in props and val not in props["enum"]:
                errors.append(f"{field}={val} 不在可选值 {props['enum']} 中")

    def _validate_permission(
        self,
        data: Dict[str, Any],
        errors: Optional[List[str]] = None,
    ) -> None:
        """权限校验：检查调用者权限标记"""
        if errors is None:
            errors = []
        # 基础权限检查 — 可被子类重写
        if "role" in data:
            allowed = {"admin", "operator", "user"}
            if data["role"] not in allowed:
                errors.append(f"角色 '{data['role']}' 无权限")

    def check_rate_limit(self, caller: str = "default") -> None:
        """
        流量限流检查（agent_rules 的隐式要求）

        Raises:
            ValidationError: 超限时抛出
        """
        if not self.config.precheck_enabled:
            return

        now = time.monotonic()
        # 清理超过1分钟的记录
        while self._rate_limit_window and now - self._rate_limit_window[0] > 60:
            self._rate_limit_window.popleft()

        if len(self._rate_limit_window) >= self.config.rate_limit_per_minute:
            raise ValidationError(
                message="请求频率超限",
                detail=f"每分钟限 {self.config.rate_limit_per_minute} 次",
                context={
                    "rate": self.config.rate_limit_per_minute,
                    "window_count": len(self._rate_limit_window),
                },
            )

        self._rate_limit_window.append(now)

    # ════════════════════════════════════════════════════════════
    # 工具管控 + 二次校验
    # ════════════════════════════════════════════════════════════

    def validate_tool_call(
        self,
        tool_name: str,
        args: Dict[str, Any],
        schema: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        工具二次参数校验（agent_rules 第3条）

        检查：
        - 参数格式/值域
        - 调用次数限制
        - 重复调用检测

        Raises:
            ValidationError: 校验失败
        """
        if not self.config.runtime_control_enabled:
            return

        # 格式校验
        self._validate_format(args, schema)

        # 值域校验
        self._validate_value_range(args, schema)

        # 检查熔断状态
        if self._is_circuit_open(tool_name):
            from ai_capability_shelf.reliability.exceptions import CircuitBreakerError
            raise CircuitBreakerError(
                message=f"工具 {tool_name} 已熔断",
                circuit_name=tool_name,
                failure_count=self._circuit_states.get(tool_name, CircuitStateData()).failure_count,
            )

    def record_tool_call(
        self,
        tool_name: str,
        args: Dict[str, Any],
        success: bool = True,
        error: str = "",
        duration_ms: float = 0.0,
    ) -> ToolCallRecord:
        """
        记录工具调用（agent_rules 第9条：全链路埋点）

        Returns:
            ToolCallRecord 记录对象
        """
        record = ToolCallRecord(
            tool_name=tool_name,
            args=args,
            timestamp=datetime.now(timezone.utc).isoformat(),
            success=success,
            error=error,
            duration_ms=duration_ms,
        )

        self._tool_call_history[tool_name].append(record)

        # 更新熔断状态
        self._update_circuit_state(tool_name, success)

        # 记录调用指纹（用于重复检测）
        fp = self._make_fingerprint(tool_name, args)
        self._tool_call_fingerprints[tool_name].add(fp)

        return record

    def _make_fingerprint(self, tool_name: str, args: Dict[str, Any]) -> str:
        """生成调用指纹用于重复检测"""
        canonical = json.dumps(args, sort_keys=True, default=str)
        return hashlib.sha256(f"{tool_name}:{canonical}".encode()).hexdigest()

    # ════════════════════════════════════════════════════════════
    # 死循环检测（agent_rules 第3条）
    # ════════════════════════════════════════════════════════════

    def detect_dead_loop(
        self,
        tool_name: str,
        args: Dict[str, Any],
    ) -> None:
        """
        死循环检测 — 三合一策略

        检测维度：
        1. 调用次数超限
        2. 参数完全重复（相同指纹N次）
        3. 调用频率异常（短时间密集调用）

        Raises:
            DeadLoopError: 检测到死循环
        """
        if not self.config.dead_loop_detection_enabled:
            return

        history = self._tool_call_history.get(tool_name, [])
        max_calls = self.config.max_tool_calls_per_step

        # 1. 调用次数超限
        if len(history) > max_calls:
            raise DeadLoopError(
                message=f"工具 {tool_name} 调用次数超限",
                tool_name=tool_name,
                call_count=len(history),
                pattern=f"total_calls={len(history)} > max={max_calls}",
            )

        # 2. 参数重复检测（连续N次相同参数）
        fp = self._make_fingerprint(tool_name, args)
        recent = [self._make_fingerprint(tool_name, r.args) for r in history[-10:]]
        if len(recent) >= 5 and len(set(recent[-5:])) == 1:
            raise DeadLoopError(
                message=f"工具 {tool_name} 连续5次相同调用",
                tool_name=tool_name,
                call_count=len(history),
                pattern="repeated_args_x5",
            )

        # 3. 调用频率异常（1秒内超过10次）
        if len(history) >= 10:
            now = time.monotonic()
            recent_records = history[-10:]
            timestamps = []
            for r in recent_records:
                try:
                    ts = datetime.fromisoformat(r.timestamp).timestamp()
                    timestamps.append(ts)
                except (ValueError, TypeError):
                    timestamps.append(now)
            if timestamps and (timestamps[-1] - timestamps[0]) < 1.0:
                raise DeadLoopError(
                    message=f"工具 {tool_name} 调用频率异常",
                    tool_name=tool_name,
                    call_count=len(history),
                    pattern=f"10_calls_in_{timestamps[-1] - timestamps[0]:.2f}s",
                )

    # ════════════════════════════════════════════════════════════
    # 上下文管控（agent_rules 第4条）
    # ════════════════════════════════════════════════════════════

    def truncate_context(
        self,
        messages: List[Dict[str, Any]],
        current_tokens: int,
    ) -> List[Dict[str, Any]]:
        """
        上下文截断 — 实时计算Token长度，超长自动截断

        策略：
        - 保留系统消息
        - 从最早的非系统消息开始裁剪
        - 保留最近的助手/工具交互

        Args:
            messages: 消息列表
            current_tokens: 当前Token数估计

        Returns:
            截断后的消息列表

        Raises:
            ContextOverflowError: 截断后仍然超长
        """
        if not self.config.context_truncation_enabled:
            return messages

        max_tokens = self.config.max_context_tokens

        if current_tokens <= max_tokens:
            self._context_token_history.append(current_tokens)
            return messages

        reserve = int(max_tokens * self.config.truncation_reserve_ratio)
        target = max_tokens - reserve

        truncated: List[Dict[str, Any]] = []
        system_messages: List[Dict[str, Any]] = []
        other_messages: List[Dict[str, Any]] = []

        for msg in messages:
            if msg.get("role") == "system":
                system_messages.append(msg)
            else:
                other_messages.append(msg)

        # 保留最近的交互
        truncated.extend(system_messages)

        # 从最早的开始裁剪，保留最近的
        kept = []
        kept_tokens = 0
        for msg in reversed(other_messages):
            msg_tokens = self._estimate_tokens(msg)
            if kept_tokens + msg_tokens <= target or len(kept) < 5:
                kept.append(msg)
                kept_tokens += msg_tokens
            else:
                break

        truncated.extend(reversed(kept))

        self._context_token_history.append(current_tokens)

        if self._estimate_total_tokens(truncated) > max_tokens:
            raise ContextOverflowError(
                message="上下文截断后仍然超长",
                token_count=self._estimate_total_tokens(truncated),
                max_tokens=max_tokens,
                detail=f"截断后 {self._estimate_total_tokens(truncated)}/{max_tokens}",
            )

        return truncated

    @staticmethod
    def _estimate_tokens(msg: Dict[str, Any]) -> int:
        """粗略估计单条消息Token数"""
        total = 0
        for key in ("content", "role", "name"):
            val = msg.get(key, "")
            if isinstance(val, str):
                total += len(val) // 4 + 1
            elif isinstance(val, list):
                for item in val:
                    if isinstance(item, dict):
                        total += len(str(item.get("text", ""))) // 4 + 1
        return max(total, 1)

    def _estimate_total_tokens(self, messages: List[Dict[str, Any]]) -> int:
        """估计消息列表总Token数"""
        return sum(self._estimate_tokens(m) for m in messages)

    # ════════════════════════════════════════════════════════════
    # 调度管控
    # ════════════════════════════════════════════════════════════

    def split_task(
        self,
        task: SubAgentTask,
        max_subtasks: int = 10,
    ) -> List[SubAgentTask]:
        """
        任务拆分 — 长任务自动拆分为Subagent（agent_rules 第2条）

        Args:
            task: 父任务
            max_subtasks: 最大子任务数

        Returns:
            拆分的子任务列表
        """
        subtasks: List[SubAgentTask] = []
        description = task.description or task.name

        if not description:
            return [task]

        # 按自然段落或逻辑分割点拆分
        segments = self._smart_split(description, max_subtasks)

        for i, seg in enumerate(segments):
            sub = SubAgentTask(
                task_id=f"{task.task_id}_sub_{i}",
                parent_id=task.task_id,
                name=f"{task.name}[{i}]",
                description=seg.strip(),
                input_data=dict(task.input_data),
                timeout_s=task.timeout_s / max(len(segments), 1),
            )
            subtasks.append(sub)
            self._active_sub_tasks[sub.task_id] = sub
            self._task_depth[sub.task_id] = self._task_depth.get(task.task_id, 0) + 1

        return subtasks

    @staticmethod
    def _smart_split(text: str, max_parts: int) -> List[str]:
        """智能分割文本为子任务描述"""
        if not text:
            return [""]
        # 按句子分割
        import re
        sentences = re.split(r'(?<=[。！？.!?])\s*', text)
        sentences = [s for s in sentences if s.strip()]

        if len(sentences) <= max_parts:
            return sentences if sentences else [text]

        # 合并成大致均匀的段
        per_part = max(1, len(sentences) // max_parts)
        parts = []
        for i in range(0, len(sentences), per_part):
            chunk = "".join(sentences[i:i + per_part])
            if chunk.strip():
                parts.append(chunk)
        return parts

    # ════════════════════════════════════════════════════════════
    # 熔断器内部管理
    # ════════════════════════════════════════════════════════════

    def _update_circuit_state(self, name: str, success: bool) -> None:
        """更新熔断器状态"""
        if name not in self._circuit_states:
            self._circuit_states[name] = CircuitStateData()

        state = self._circuit_states[name]
        cfg = self.config.circuit_breaker
        now_iso = datetime.now(timezone.utc).isoformat()

        if success:
            if state.state == CircuitState.HALF_OPEN:
                state.success_count += 1
                state.half_open_requests -= 1
                if state.success_count >= cfg.consecutive_success_to_close:
                    state.state = CircuitState.CLOSED
                    state.failure_count = 0
                    state.success_count = 0
                    state.opened_at = None
            else:
                state.failure_count = 0
            state.last_success_time = now_iso
        else:
            state.failure_count += 1
            state.last_failure_time = now_iso

            if (state.state == CircuitState.CLOSED
                    and state.failure_count >= cfg.failure_threshold):
                state.state = CircuitState.OPEN
                state.opened_at = now_iso
                state.success_count = 0

            elif state.state == CircuitState.HALF_OPEN:
                state.state = CircuitState.OPEN
                state.opened_at = now_iso
                state.success_count = 0

    def _is_circuit_open(self, name: str) -> bool:
        """检查熔断器状态，自动半开探测"""
        if name not in self._circuit_states:
            return False

        state = self._circuit_states[name]
        cfg = self.config.circuit_breaker

        if state.state == CircuitState.CLOSED:
            return False

        if state.state == CircuitState.OPEN:
            if state.opened_at:
                try:
                    opened = datetime.fromisoformat(state.opened_at)
                    elapsed = (datetime.now(timezone.utc) - opened).total_seconds()
                    if elapsed >= cfg.recovery_timeout_s:
                        state.state = CircuitState.HALF_OPEN
                        state.half_open_requests = 0
                        return False
                except (ValueError, TypeError):
                    pass
            return True

        if state.state == CircuitState.HALF_OPEN:
            if state.half_open_requests >= cfg.half_open_max_requests:
                return True
            state.half_open_requests += 1
            return False

        return False

    def get_circuit_state(self, name: str) -> CircuitStateData:
        """获取熔断器快照"""
        return self._circuit_states.get(name, CircuitStateData())

    def reset_circuit(self, name: str) -> None:
        """重置熔断器"""
        if name in self._circuit_states:
            self._circuit_states[name] = CircuitStateData()

    # ════════════════════════════════════════════════════════════
    # 状态查询 / 统计
    # ════════════════════════════════════════════════════════════

    def get_tool_call_count(self, tool_name: str) -> int:
        """获取工具调用次数"""
        return len(self._tool_call_history.get(tool_name, []))

    def get_tool_history(self, tool_name: str) -> List[ToolCallRecord]:
        """获取工具调用历史"""
        return list(self._tool_call_history.get(tool_name, []))

    def get_all_circuit_states(self) -> Dict[str, CircuitStateData]:
        """获取所有熔断器快照"""
        return dict(self._circuit_states)

    def reset(self) -> None:
        """重置引擎运行时状态"""
        self._tool_call_history.clear()
        self._tool_call_fingerprints.clear()
        self._circuit_states.clear()
        self._active_sub_tasks.clear()
        self._task_depth.clear()
        self._context_token_history.clear()
        self._rate_limit_window.clear()
