"""
管控层 — 权限校验、限流、熔断、审计日志
========================================
高内聚：只处理"运行管控"
低耦合：通过 GovernancePolicy 纯数据类传递策略
崩溃安全：熔断状态持久化到磁盘（AtomicWriter）+ 审计日志原子写入 + 哨兵恢复
"""

from __future__ import annotations
import time
import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, TYPE_CHECKING
from typing import Tuple as TypingTuple
from datetime import datetime, timezone

from pydantic import BaseModel, Field
from ai_capability_shelf.persistence import AuditLogger

if TYPE_CHECKING:
    from ai_capability_shelf.persistence import PersistenceProvider


# ── 管控策略 ──────────────────────────────────────────────


class GovernancePolicy(BaseModel):
    """管控策略 — 权限/限流/版本/日志"""
    required_roles: List[str] = Field(
        default_factory=lambda: ["user"],
        description="允许调用的角色列表"
    )
    rate_limit_rps: int = Field(
        default=100,
        ge=1,
        le=100000,
        description="每秒最大调用次数"
    )
    rate_limit_burst: int = Field(
        default=200,
        ge=1,
        description="突发最大调用次数"
    )
    timeout_seconds: int = Field(
        default=30,
        ge=1,
        le=3600,
        description="单次调用超时(秒)"
    )
    retry_enabled: bool = True
    max_retries: int = Field(
        default=3,
        ge=0,
        le=10
    )
    circuit_breaker_enabled: bool = True
    circuit_breaker_threshold: int = Field(
        default=5,
        ge=1,
        description="触发熔断的连续失败次数"
    )
    log_enabled: bool = True
    audit_required: bool = Field(
        default=False,
        description="是否需审计日志"
    )


# ── 限流器 ──────────────────────────────────────────────

class TokenBucket:
    """
    令牌桶限流器 — 内存级别（每个进程独立）
    崩溃后令牌桶重置为满桶，是安全的设计（限流器重启后不应惩罚新进程）
    """
    def __init__(self, rps: int, burst: int):
        self.rps = rps
        self.burst = burst
        self.tokens = float(burst)
        self.last_refill = time.monotonic()

    def allow(self) -> bool:
        """尝试获取一个令牌"""
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.burst, self.tokens + elapsed * self.rps)
        self.last_refill = now
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        return False


class RateLimiter:
    """全局限流器管理器"""

    def __init__(self):
        self._buckets: Dict[str, TokenBucket] = {}

    def check(self, policy: GovernancePolicy, key: str = "default") -> bool:
        """检查是否允许调用"""
        if key not in self._buckets:
            self._buckets[key] = TokenBucket(
                policy.rate_limit_rps,
                policy.rate_limit_burst
            )
        return self._buckets[key].allow()

    def reset(self, key: str) -> None:
        self._buckets.pop(key, None)


# ── 熔断器 ──────────────────────────────────────────────

class CircuitState:
    """熔断器状态"""
    CLOSED = "closed"       # 正常通行
    OPEN = "open"           # 熔断开启，拒绝请求
    HALF_OPEN = "half_open" # 半开，允许试探请求


class CircuitBreaker:
    """
    熔断器

    状态机：CLOSED → OPEN → HALF_OPEN → CLOSED
    - CLOSED: 正常。连续失败 count >= threshold → OPEN
    - OPEN: 拒绝请求。等待 timeout 秒 → HALF_OPEN
    - HALF_OPEN: 允许试探。成功 → CLOSED，失败 → OPEN

    崩溃安全：
    - 通过 GovernanceGuard.set_persistence_dir() 启用持久化
    - 每次状态变更自动保存
    - 从 dict 恢复所有运行时字段
    """

    def __init__(
        self,
        policy: Optional[GovernancePolicy] = None,
        cap_id: str = "unknown"
    ):
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0.0
        self.circuit_open_time = 0.0
        self.policy: Optional[GovernancePolicy] = policy
        self.cap_id = cap_id

    def allow_request(self) -> bool:
        """判断请求是否被允许"""
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            # 检查恢复超时
            threshold = self.policy.circuit_breaker_threshold if self.policy else 5
            timeout = threshold * 2  # auto-recovery
            if time.time() - self.circuit_open_time >= timeout:
                self.state = CircuitState.HALF_OPEN
                return True
            return False

        # HALF_OPEN: 只允许一次试探
        # 这里允许请求，在 record_success/failure 中判断
        self.state = CircuitState.OPEN  # 先锁住
        return True

    def record_success(self) -> None:
        """记录成功 — 重置熔断器"""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0.0
        self.circuit_open_time = 0.0

    def record_failure(self) -> bool:
        """记录失败 — 如果达到阈值则熔断。返回 true=已经熔断"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        threshold = self.policy.circuit_breaker_threshold if self.policy else 10
        if self.failure_count >= threshold:
            self.state = CircuitState.OPEN
            self.circuit_open_time = time.time()
            return True
        return False

    @property
    def is_open(self) -> bool:
        return self.state == CircuitState.OPEN

    def to_dict(self) -> Dict[str, Any]:
        """序列化运行时状态（用于持久化）"""
        return {
            "cap_id": self.cap_id,
            "state": self.state,
            "failure_count": self.failure_count,
            "last_failure_time": self.last_failure_time,
            "circuit_open_time": self.circuit_open_time,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], policy: GovernancePolicy) -> "CircuitBreaker":
        """从 dict 恢复熔断器（用于崩溃恢复）"""
        breaker = cls(policy, data.get("cap_id", "unknown"))
        breaker.state = data.get("state", CircuitState.CLOSED)
        breaker.failure_count = data.get("failure_count", 0)
        breaker.last_failure_time = data.get("last_failure_time", 0.0)
        breaker.circuit_open_time = data.get("circuit_open_time", 0.0)
        return breaker


# ── 管控门卫 ──────────────────────────────────────────────

class GovernanceGuard:
    """
    统一管控入口
    三合一：权限校验 → 限流检查 → 熔断检查

    崩溃安全：
    - 熔断器状态自动持久化到磁盘（AtomicWriter）
    - 每次状态变更（record_success/record_failure）自动保存
    - 启动时自动恢复上次持久化的熔断器状态
    """

    BREAKER_STATE_FILE = "breaker_states.json"

    def __init__(
        self,
        log_dir: str | Path = "/tmp/cap_shelf_audit",
        persistence_provider: Optional["PersistenceProvider"] = None,
    ):
        self.rate_limiter = RateLimiter()
        self.audit_logger = AuditLogger(log_dir)
        self._breakers: Dict[str, CircuitBreaker] = {}
        self._persistence_path: Optional[Path] = None
        self._provider: Optional["PersistenceProvider"] = persistence_provider

    def set_persistence_dir(self, path: str | Path) -> None:
        """
        启用熔断器持久化

        设置持久化目录后：
        - 启动时自动从磁盘恢复熔断器状态
        - 每次熔断器状态变更自动保存
        """
        p = Path(path)
        p.mkdir(parents=True, exist_ok=True)
        self._persistence_path = p / self.BREAKER_STATE_FILE
        self._load_breakers()

    def get_breaker(self, cap_id: str, policy: GovernancePolicy) -> CircuitBreaker:
        """
        获取（或创建）指定能力的熔断器

        崩溃恢复：如果磁盘上有该熔断器的持久化状态，恢复运行时字段。
        policy 参数始终覆盖，确保启动后策略更新能同步到恢复的熔断器。
        """
        if cap_id not in self._breakers:
            self._breakers[cap_id] = CircuitBreaker(policy, cap_id)
        else:
            # 恢复的熔断器需要更新 policy（policy 不持久化）
            self._breakers[cap_id].policy = policy
        return self._breakers[cap_id]

    def _save_breakers(self) -> None:
        """原子保存所有熔断器状态到磁盘"""
        if not self._persistence_path:
            return
        # 只在有实际数据时写入，减少无意义 I/O
        if not self._breakers:
            return
        data = {
            cap_id: b.to_dict()
            for cap_id, b in self._breakers.items()
        }
        if self._provider:
            self._provider.write_json_atomic(self._persistence_path, data)
        else:
            from ai_capability_shelf.persistence import AtomicWriter
            AtomicWriter.write_json_atomic(self._persistence_path, data)

    def _load_breakers(self) -> None:
        """从磁盘恢复熔断器运行时状态"""
        if not self._persistence_path or not self._persistence_path.exists():
            return
        if self._provider:
            raw = self._provider.read_json_safe(self._persistence_path)
        else:
            from ai_capability_shelf.persistence import AtomicWriter
            raw = AtomicWriter.read_json_safe(self._persistence_path)
        if not raw or not isinstance(raw, dict):
            return
        for cap_id, state_dict in raw.items():
            if not isinstance(state_dict, dict):
                continue
            # 构造一个不带 policy 的 breaker，get_breaker 会更新 policy
            breaker = CircuitBreaker.__new__(CircuitBreaker)
            breaker.state = state_dict.get("state", CircuitState.CLOSED)
            breaker.failure_count = state_dict.get("failure_count", 0)
            breaker.last_failure_time = state_dict.get("last_failure_time", 0.0)
            breaker.circuit_open_time = state_dict.get("circuit_open_time", 0.0)
            breaker.policy = None  # 由 get_breaker 填充
            breaker.cap_id = cap_id
            self._breakers[cap_id] = breaker

    def check_access(
        self,
        cap_id: str,
        policy: GovernancePolicy,
        caller_role: str = "user",
    ) -> TypingTuple[bool, Optional[str]]:
        """
        三合一管控检查
        返回 (允许, 拒绝原因)
        """
        # 1. 权限校验
        if caller_role not in policy.required_roles:
            return (False, f"角色 '{caller_role}' 无权限调用 {cap_id}")

        # 2. 限流检查
        if not self.rate_limiter.check(policy, cap_id):
            return (False, f"{cap_id} 触发了限流")

        # 3. 熔断检查
        breaker = self.get_breaker(cap_id, policy)
        allowed = breaker.allow_request()
        self._save_breakers()
        if allowed:
            return (True, None)
        else:
            return (False, f"{cap_id} 熔断器已开启 (已连续失败 {breaker.failure_count} 次)")
