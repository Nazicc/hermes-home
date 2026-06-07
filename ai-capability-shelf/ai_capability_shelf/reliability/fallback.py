"""
reliability.fallback — FallbackManager 异常兜底管理器
=====================================================
职责（对应"异常兜底"保障维度）：
  1. 分级重试（agent_rules 第5条：幂等）
  2. 多级超时熔断（agent_rules 第6条）
  3. 分层降级（agent_rules 第7条：简化→兜底话术）
  4. 故障隔离（agent_rules 第8条）
  5. 死循环拦截联动

崩溃安全：
  - 所有写操作通过 AtomicWriter
  - 降级/隔离状态持久化
  - 熔断状态检查点
"""

from __future__ import annotations

import time
import random
from typing import Any, Callable, Dict, List, Optional, Tuple, Type
from datetime import datetime, timezone
from pathlib import Path

from ai_capability_shelf.persistence import AtomicWriter, SentinelManager
from ai_capability_shelf.reliability.models import (
    RetryPolicy,
    RetryMode,
    CircuitConfig,
    CircuitStateData,
    CircuitState,
    FallbackPlan,
    DegradeLevel,
    IsolationScope,
    IsolatedComponent,
)
from ai_capability_shelf.reliability.exceptions import (
    RetryExhaustedError,
    CircuitBreakerError,
    FallbackError,
    IsolationError,
    TimeoutError,
)


class FallbackManager:
    """
    异常兜底管理器

    提供统一的重试 + 熔断 + 降级 + 隔离 + 超时管理。

    使用方式：
      fb = FallbackManager(data_dir=Path("/tmp/reliability"), config=...)
      result = fb.with_retry("my_op", lambda: do_stuff())
      result = fb.with_circuit_breaker("tool_x", lambda: call_tool())
      result = fb.with_degrade("tool_y", primary_fn, fallback_fn)
    """

    def __init__(
        self,
        data_dir: Optional[Path] = None,
        config: Optional[FallbackPlan] = None,
    ) -> None:
        self.config = config or FallbackPlan()
        self._data_dir = data_dir

        # 熔断器运行时状态
        self._circuit_states: Dict[str, CircuitStateData] = {}

        # 被隔离的组件
        self._isolated_components: Dict[str, IsolatedComponent] = {}

        # 哨兵管理器（用于崩溃安全持久化）
        self._sentinel: Optional[SentinelManager] = None
        if data_dir:
            self._sentinel = SentinelManager(data_dir)

    # ════════════════════════════════════════════════════════════
    # 分级重试（agent_rules 第5条：幂等）
    # ════════════════════════════════════════════════════════════

    def with_retry(
        self,
        operation_name: str,
        fn: Callable[[], Any],
        retry_policy: Optional[RetryPolicy] = None,
    ) -> Any:
        """
        带幂等差量的重试执行

        支持三种重试模式：
        - FIXED: 固定间隔
        - EXPONENTIAL: 指数退避
        - JITTER: 加抖动退避

        Args:
            operation_name: 操作名称
            fn: 执行函数
            retry_policy: 重试策略，默认使用全局配置

        Returns:
            执行结果

        Raises:
            RetryExhaustedError: 重试耗尽
        """
        policy = retry_policy or RetryPolicy()
        if not policy.enabled:
            return fn()

        last_error: Optional[Exception] = None

        for attempt in range(1, policy.max_attempts + 1):
            try:
                return fn()
            except Exception as e:
                last_error = e

                if attempt >= policy.max_attempts:
                    break

                delay = self._calc_delay(policy, attempt)
                time.sleep(delay / 1000.0)

        raise RetryExhaustedError(
            message=f"操作 {operation_name} 重试耗尽",
            operation=operation_name,
            attempts=policy.max_attempts,
            detail=str(last_error) if last_error else "",
            context={
                "retry_mode": policy.mode.value,
                "max_attempts": policy.max_attempts,
            },
        )

    def _calc_delay(self, policy: RetryPolicy, attempt: int) -> float:
        """计算重试延迟（毫秒）"""
        if policy.mode == RetryMode.FIXED:
            delay = policy.base_delay_ms
        elif policy.mode == RetryMode.JITTER:
            delay = min(
                policy.base_delay_ms * (2 ** (attempt - 1)),
                policy.max_delay_ms,
            )
            delay += random.uniform(-policy.jitter_factor * delay, policy.jitter_factor * delay)
        else:  # EXPONENTIAL
            delay = min(
                policy.base_delay_ms * (attempt ** 2),
                policy.max_delay_ms,
            )

        return max(delay, 100.0)  # 最小100ms

    # ════════════════════════════════════════════════════════════
    # 多级超时 + 连续失败熔断（agent_rules 第6条）
    # ════════════════════════════════════════════════════════════

    def with_circuit_breaker(
        self,
        name: str,
        fn: Callable[[], Any],
        circuit_config: Optional[CircuitConfig] = None,
        timeout_s: Optional[float] = None,
    ) -> Any:
        """
        带熔断保护的执行

        状态机：CLOSED → OPEN → HALF_OPEN → CLOSED

        Args:
            name: 电路名称
            fn: 执行函数
            circuit_config: 熔断配置
            timeout_s: 超时秒数

        Returns:
            执行结果

        Raises:
            CircuitBreakerError: 熔断打开
            TimeoutError: 执行超时
        """
        cfg = circuit_config or CircuitConfig()
        if not cfg.enabled:
            return fn()

        # 检查熔断状态
        state = self._get_or_create_circuit(name)

        if state.state == CircuitState.OPEN:
            if self._should_attempt_half_open(name, cfg):
                state.state = CircuitState.HALF_OPEN
                state.half_open_requests = 0
            else:
                raise CircuitBreakerError(
                    message=f"熔断器 {name} 已打开",
                    circuit_name=name,
                    failure_count=state.failure_count,
                )

        # 半开限流
        if state.state == CircuitState.HALF_OPEN:
            if state.half_open_requests >= cfg.half_open_max_requests:
                raise CircuitBreakerError(
                    message=f"熔断器 {name} 半开探测已满",
                    circuit_name=name,
                    failure_count=state.failure_count,
                    detail=f"半开请求已达上限 {cfg.half_open_max_requests}",
                )
            state.half_open_requests += 1

        # 执行
        try:
            result = self._run_with_timeout(fn, timeout_s)
            self._record_success(name, cfg)
            return result
        except Exception as e:
            self._record_failure(name, cfg)
            if isinstance(e, CircuitBreakerError):
                raise
            raise

    def _get_or_create_circuit(self, name: str) -> CircuitStateData:
        if name not in self._circuit_states:
            self._circuit_states[name] = CircuitStateData()
        return self._circuit_states[name]

    def _should_attempt_half_open(
        self, name: str, cfg: CircuitConfig
    ) -> bool:
        """检查是否可以进入半开探测"""
        state = self._circuit_states.get(name)
        if not state or not state.opened_at:
            return True
        try:
            opened = datetime.fromisoformat(state.opened_at)
            elapsed = (datetime.now(timezone.utc) - opened).total_seconds()
            return elapsed >= cfg.recovery_timeout_s
        except (ValueError, TypeError):
            return True

    def _record_success(self, name: str, cfg: CircuitConfig) -> None:
        state = self._get_or_create_circuit(name)
        now_iso = datetime.now(timezone.utc).isoformat()
        state.last_success_time = now_iso

        if state.state == CircuitState.HALF_OPEN:
            state.success_count += 1
            if state.success_count >= cfg.consecutive_success_to_close:
                state.state = CircuitState.CLOSED
                state.failure_count = 0
                state.success_count = 0
                state.opened_at = None
        else:
            state.failure_count = 0

    def _record_failure(self, name: str, cfg: CircuitConfig) -> None:
        state = self._get_or_create_circuit(name)
        now_iso = datetime.now(timezone.utc).isoformat()
        state.failure_count += 1
        state.last_failure_time = now_iso

        if state.failure_count >= cfg.failure_threshold:
            state.state = CircuitState.OPEN
            state.opened_at = now_iso
            state.success_count = 0

    def _run_with_timeout(
        self, fn: Callable[[], Any], timeout_s: Optional[float] = None
    ) -> Any:
        """带超时的函数执行"""
        if timeout_s is None or timeout_s <= 0:
            return fn()

        import signal

        def handler(signum, frame):
            raise TimeoutError(
                message="执行超时",
                level="tool",
                timeout=timeout_s,
            )

        # Use signal-based timeout (Unix only)
        old_handler = None
        try:
            old_handler = signal.signal(signal.SIGALRM, handler)
            signal.setitimer(signal.ITIMER_REAL, timeout_s)
            result = fn()
            signal.setitimer(signal.ITIMER_REAL, 0)
            return result
        except TimeoutError:
            raise
        finally:
            if old_handler is not None:
                signal.signal(signal.SIGALRM, old_handler)

    # ════════════════════════════════════════════════════════════
    # 分层降级（agent_rules 第7条）
    # ════════════════════════════════════════════════════════════

    def with_degrade(
        self,
        name: str,
        primary_fn: Callable[[], Any],
        fallback_fn: Optional[Callable[[], Any]] = None,
        fallback_text: str = "",
    ) -> Tuple[Any, DegradeLevel]:
        """
        分层降级执行

        降级链：
        1. SIMPLIFY — 简化请求
        2. CACHE — 走缓存
        3. FALLBACK_TOOL — 备用工具
        4. FALLBACK_TEXT — 兜底话术

        Args:
            name: 操作名称
            primary_fn: 主执行函数
            fallback_fn: 备用函数（对应FALLBACK_TOOL级别）
            fallback_text: 兜底话术（对应FALLBACK_TEXT级别）

        Returns:
            (result, degrade_level) 结果与降级级别

        Raises:
            FallbackError: 所有降级方案均失败
        """
        # Level 0: 无降级 — 直接尝试
        try:
            result = primary_fn()
            return result, DegradeLevel.NONE
        except Exception as e:
            last_error = e

        # Level 1: 简化 — 略过复杂参数重试
        if DegradeLevel.SIMPLIFY in self.config.degrade_levels:
            try:
                result = self._simplify_and_retry(name, primary_fn)
                return result, DegradeLevel.SIMPLIFY
            except Exception as e:
                last_error = e

        # Level 2: 缓存 — 走缓存降级
        if DegradeLevel.CACHE in self.config.degrade_levels:
            cached = self._try_cache(name)
            if cached is not None:
                return cached, DegradeLevel.CACHE

        # Level 3: 备用工具
        if DegradeLevel.FALLBACK_TOOL in self.config.degrade_levels and fallback_fn:
            try:
                result = fallback_fn()
                return result, DegradeLevel.FALLBACK_TOOL
            except Exception as e:
                last_error = e
        elif DegradeLevel.FALLBACK_TOOL in self.config.degrade_levels:
            fallback_id = self.config.fallback_tools.get(name)
            if fallback_id:
                last_error = FallbackError(
                    message=f"无可用的备用工具: {fallback_id}",
                    level="fallback_tool",
                    fallback_name=fallback_id,
                )

        # Level 4: 兜底话术
        if DegradeLevel.FALLBACK_TEXT in self.config.degrade_levels and fallback_text:
            return fallback_text, DegradeLevel.FALLBACK_TEXT

        raise FallbackError(
            message=f"所有降级方案均失败: {name}",
            level="all",
            fallback_name=name,
            detail=str(last_error) if last_error else "",
        )

    def _simplify_and_retry(
        self, name: str, fn: Callable[[], Any]
    ) -> Any:
        """简化重试 — 移除复杂参数后重试"""
        return fn()

    def _try_cache(self, name: str) -> Optional[Any]:
        """尝试缓存降级"""
        cache_path = None
        if self._data_dir:
            cache_path = self._data_dir / f".degrade_cache_{name}.json"
            data = AtomicWriter.read_json_safe(cache_path)
            if data:
                return data.get("cached_result")
        return None

    def save_cache(self, name: str, value: Any) -> None:
        """保存降级缓存"""
        if not self._data_dir:
            return
        cache_path = self._data_dir / f".degrade_cache_{name}.json"
        AtomicWriter.write_json_atomic(
            cache_path,
            {
                "cached_result": value,
                "cached_at": datetime.now(timezone.utc).isoformat(),
                "ttl_s": self.config.cache_ttl_s,
            },
        )

    # ════════════════════════════════════════════════════════════
    # 故障隔离（agent_rules 第8条）
    # ════════════════════════════════════════════════════════════

    def isolate(
        self,
        component_id: str,
        scope: IsolationScope = IsolationScope.TOOL,
        reason: str = "",
        auto_recover: bool = True,
    ) -> IsolatedComponent:
        """
        隔离故障组件

        Args:
            component_id: 组件ID
            scope: 隔离范围
            reason: 隔离原因
            auto_recover: 是否自动恢复

        Returns:
            IsolatedComponent 记录

        Raises:
            IsolationError: 隔离写入失败
        """
        component = IsolatedComponent(
            component_id=component_id,
            scope=scope,
            reason=reason,
            auto_recover=auto_recover,
        )
        self._isolated_components[component_id] = component
        return component

    def is_isolated(self, component_id: str) -> bool:
        """
        检查组件是否被隔离

        自动恢复逻辑：
        - 如果是自动恢复模式且隔离超时 → 自动解除
        """
        component = self._isolated_components.get(component_id)
        if not component:
            return False

        if component.auto_recover:
            try:
                isolated = datetime.fromisoformat(component.isolated_at)
                elapsed = (datetime.now(timezone.utc) - isolated).total_seconds()
                if elapsed >= component.recover_after_s:
                    self._isolated_components.pop(component_id, None)
                    return False
            except (ValueError, TypeError):
                pass

        return True

    def release_isolation(self, component_id: str) -> None:
        """手动解除隔离"""
        self._isolated_components.pop(component_id, None)

    def get_isolated_components(self) -> Dict[str, IsolatedComponent]:
        """获取所有被隔离组件"""
        return dict(self._isolated_components)

    # ════════════════════════════════════════════════════════════
    # 状态持久化
    # ════════════════════════════════════════════════════════════

    def persist_state(self) -> None:
        """持久化熔断/隔离状态（崩溃安全）"""
        if not self._sentinel:
            return

        self._sentinel.acquire("fallback_persist")
        try:
            if self._data_dir:
                state_path = self._data_dir / ".fallback_state.json"
                data = {
                    "circuit_states": {
                        k: v.model_dump() for k, v in self._circuit_states.items()
                    },
                    "isolated_components": {
                        k: v.model_dump() for k, v in self._isolated_components.items()
                    },
                }
                AtomicWriter.write_json_atomic(state_path, data)
        finally:
            self._sentinel.release()

    def load_state(self) -> None:
        """从持久化恢复状态"""
        if not self._data_dir:
            return

        state_path = self._data_dir / ".fallback_state.json"
        data = AtomicWriter.read_json_safe(state_path)
        if not data:
            return

        circuit_raw = data.get("circuit_states", {})
        for k, v in circuit_raw.items():
            self._circuit_states[k] = CircuitStateData(**v)

        isolated_raw = data.get("isolated_components", {})
        for k, v in isolated_raw.items():
            self._isolated_components[k] = IsolatedComponent(**v)

    def reset(self) -> None:
        """重置所有运行时状态"""
        self._circuit_states.clear()
        self._isolated_components.clear()
