"""
AI场景能力货架 — AI Capability Shelf
======================================

五层架构：底层基座 → 原子组件 → 组合技能 → 场景方案 → 管控接入

核心原则：
- 高内聚：每层只关注自身职责
- 低耦合：层间通过标准化接口交互
- 崩溃安全：原子写入 + 哨兵检查点
"""

from ai_capability_shelf.exceptions import (
    CapabilityShelfError,
    PersistenceError, AtomicWriteError, SentinelError, StoreError,
    RegistryError, NotFoundError,
    ValidationError, VersionError, InterfaceError,
    ModelError,
    RuntimeError_ as RuntimeError,
    TimeoutError, ExecutionFailure, CircuitBreakerOpenError,
    LifecycleError, CheckpointError, PipelineError,
    CompositionError, CycleError,
    GovernanceError, RateLimitError, AccessDeniedError,
)
from ai_capability_shelf.models import (
    CapabilityTier,
    CapabilityStatus,
    AtomicComponent,
    CompositeSkill,
    ScenarioSolution,
    BaseInfra,
    CapabilityShelfState,
    InterfaceSpec,
    RuntimeMetrics,
)
from ai_capability_shelf.governance import GovernancePolicy
from ai_capability_shelf.registry import CapabilityRegistry
from ai_capability_shelf.standardization import (
    InterfaceValidator,
    VersionManager,
    StandardizationService,
)
from ai_capability_shelf.governance import (
    GovernanceGuard,
    RateLimiter,
    CircuitBreaker,
)
from ai_capability_shelf.composition import (
    DagBuilder,
    TopologicalSort,
    CycleDetector,
    CompositionValidator,
    CompositeAssembler,
)
from ai_capability_shelf.runtime import (
    RuntimeEngine,
    ExecutionResult,
)
from ai_capability_shelf.persistence import (
    AtomicWriter,
    SentinelManager,
    CapabilityStore,
    AuditLogger,
)
from ai_capability_shelf.lifecycle import (
    LifecycleManager,
)

__all__ = [
    # Exceptions
    "CapabilityShelfError",
    "PersistenceError", "AtomicWriteError", "SentinelError", "StoreError",
    "RegistryError", "NotFoundError",
    "ValidationError", "VersionError", "InterfaceError",
    "ModelError",
    "RuntimeError", "TimeoutError", "ExecutionFailure", "CircuitBreakerOpenError",
    "LifecycleError", "CheckpointError", "PipelineError",
    "CompositionError", "CycleError",
    "GovernanceError", "RateLimitError", "AccessDeniedError",
    # Models
    "CapabilityTier", "CapabilityStatus",
    "AtomicComponent", "CompositeSkill", "ScenarioSolution",
    "BaseInfra", "CapabilityShelfState",
    "InterfaceSpec", "GovernancePolicy", "RuntimeMetrics",
    # Registry
    "CapabilityRegistry",
    # Standardization
    "InterfaceValidator", "VersionManager", "StandardizationService",
    # Governance
    "GovernanceGuard", "RateLimiter",
    "CircuitBreaker",
    # Composition
    "DagBuilder", "TopologicalSort", "CycleDetector",
    "CompositionValidator", "CompositeAssembler",
    # Runtime
    "RuntimeEngine", "ExecutionResult",
    # Persistence
    "AtomicWriter", "SentinelManager", "CapabilityStore",
    "AuditLogger",
    # Lifecycle
    "LifecycleManager",
]
