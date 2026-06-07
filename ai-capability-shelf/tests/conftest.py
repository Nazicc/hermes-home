"""
tests/conftest.py — 共享测试 fixtures
=======================================
高内聚：所有 fixture 集中定义，测试函数可组合按需依赖。
低耦合：每个 fixture 只创建自身所需数据，不混杂跨层依赖。
崩溃安全验证：crash_recovery_dir fixture 模拟断电场景。
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

import pytest

from ai_capability_shelf.models import (
    AtomicComponent,
    CapabilityShelfState,
    CapabilityStatus,
    CompositeSkill,
    ErrorCategory,
    InterfaceSpec,
    InvokeProtocol,
    ScenarioSolution,
    WorkflowStep,
)
from ai_capability_shelf.governance import GovernancePolicy
from ai_capability_shelf.exceptions import (
    CapabilityNotFoundError,
    DuplicateCapabilityError,
    GovernanceError,
    CompositionError,
    InvalidCapabilityError,
    StandardizationError,
    PersistenceError,
)
from ai_capability_shelf.persistence import CapabilityStore
from ai_capability_shelf.registry import CapabilityRegistry
from ai_capability_shelf.composition import CompositionValidator
from ai_capability_shelf.persistence import AuditLogger
from ai_capability_shelf.governance import (
    GovernanceGuard,
    TokenBucket,
    RateLimiter,
    CircuitBreaker,
)
from ai_capability_shelf.standardization import (
    StandardizationService,
    VersionManager,
    InterfaceValidator,
)
from ai_capability_shelf.runtime import RuntimeEngine, AtomicExecutor
from ai_capability_shelf.lifecycle import LifecycleManager, PipelineContext


# ═══════════════════════════════════════════════════════════════
#  环境 & 目录
# ═══════════════════════════════════════════════════════════════

@pytest.fixture
def tmp_data_dir() -> Generator[Path, None, None]:
    """临时数据目录，测试后自动清理"""
    path = Path(tempfile.mkdtemp(prefix="cap_shelf_test_"))
    yield path
    shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def crash_recovery_dir() -> Generator[Path, None, None]:
    """
    崩溃恢复测试专用目录。
    不清理 tmp 文件以模拟断电后的遗留状态，由生产代码的 clean_orphaned_tmp 清理。
    测试自行在 teardown 中清理 final 文件，残留 tmp 用于验证 clean 逻辑。
    """
    path = Path(tempfile.mkdtemp(prefix="crash_recovery_"))
    yield path
    # 清理 final 文件，保留可能的 .tmp 残留（由生产 clean 负责）
    for f in path.iterdir():
        if f.suffix == ".json" and not f.name.startswith("."):
            f.unlink(missing_ok=True)


# ═══════════════════════════════════════════════════════════════
#  样本数据 — 原子组件
# ═══════════════════════════════════════════════════════════════

@pytest.fixture
def sample_interface() -> InterfaceSpec:
    return InterfaceSpec(
        input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
        output_schema={"type": "object", "properties": {"result": {"type": "string"}}},
        error_definitions=[
            {"code": "TIMEOUT", "message": "执行超时", "category": "system"},
            {"code": "INVALID_INPUT", "message": "输入无效", "category": "input"},
        ],
        example_input={"query": "test"},
        example_output={"result": "ok"},
    )


@pytest.fixture
def sample_atomic() -> AtomicComponent:
    return AtomicComponent(
        id="atomic.test.qa_bot",
        name="QA Bot",
        description="智能问答机器人",
        category="conversation",
        version="1.0.0",
        status=CapabilityStatus.DRAFT,
        invoke=InvokeProtocol.FUNCTION,
        interface=InterfaceSpec(
            input_schema={"type": "object", "properties": {}},
            output_schema={"type": "object", "properties": {}},
            error_definitions=[
                {"code": "INTERNAL_ERROR", "message": "内部错误", "category": "INTERNAL_ERROR"},
            ],
        ),
        tags=["qa", "conversation", "bot"],
        documentation="## QA Bot\n智能问答能力",
    )


@pytest.fixture
def sample_atomic_on_shelf(sample_atomic: AtomicComponent) -> AtomicComponent:
    """已上架的原子组件"""
    sample_atomic.status = CapabilityStatus.ON_SHELF
    return sample_atomic


@pytest.fixture
def another_atomic() -> AtomicComponent:
    return AtomicComponent(
        id="atomic.test.translator",
        name="Translator",
        description="翻译服务",
        category="nlp",
        version="0.5.0",
        status=CapabilityStatus.DRAFT,
        invoke=InvokeProtocol.HTTP,
        invoke_config={"endpoint": "https://translate.example.com/api"},
        interface=InterfaceSpec(
            input_schema={"type": "object", "properties": {"text": {"type": "string"}}},
            output_schema={"type": "object", "properties": {"translated": {"type": "string"}}},
            error_definitions=[
                {"code": "API_ERROR", "message": "翻译API错误", "category": "INTERNAL_ERROR"},
            ],
        ),
        tags=["nlp", "translate"],
    )


@pytest.fixture
def atomic_mcp() -> AtomicComponent:
    return AtomicComponent(
        id="atomic.test.file_search",
        name="File Search",
        description="MCP 文件搜索工具",
        category="tool",
        version="0.1.0",
        status=CapabilityStatus.ON_SHELF,
        invoke=InvokeProtocol.MCP,
        invoke_config={"tool": "search_files", "server": "filesystem"},
        interface=InterfaceSpec(
            input_schema={"type": "object", "properties": {"pattern": {"type": "string"}}},
            output_schema={"type": "object", "properties": {"matches": {"type": "array"}}},
            error_definitions=[],
        ),
    )


# ═══════════════════════════════════════════════════════════════
#  样本数据 — 组合技能 & 场景方案
# ═══════════════════════════════════════════════════════════════

@pytest.fixture
def sample_composite(sample_atomic: AtomicComponent,
                     another_atomic: AtomicComponent) -> CompositeSkill:
    return CompositeSkill(
        id="composite.test.qa_pipeline",
        name="QA Pipeline",
        description="问答翻译管线",
        version="0.2.0",
        status=CapabilityStatus.DRAFT,
        steps=[
            WorkflowStep(component_id=sample_atomic.id, label="问答"),
            WorkflowStep(component_id=another_atomic.id, label="翻译"),
        ],
    )


@pytest.fixture
def sample_scenario(sample_atomic: AtomicComponent) -> ScenarioSolution:
    return ScenarioSolution(
        id="scenario.test.customer_service",
        name="Customer Service",
        description="客服场景",
        version="0.1.0",
        status=CapabilityStatus.DRAFT,
        required_capabilities=[sample_atomic.id],
    )


@pytest.fixture
def component_a() -> AtomicComponent:
    return AtomicComponent(
        id="atomic.test.comp_a",
        name="Component A",
        description="组件 A",
        category="test",
        version="0.1.0",
        status=CapabilityStatus.ON_SHELF,
        invoke=InvokeProtocol.FUNCTION,
        interface=InterfaceSpec(
            input_schema={}, output_schema={}, error_definitions=[],
        ),
    )


@pytest.fixture
def component_b() -> AtomicComponent:
    return AtomicComponent(
        id="atomic.test.comp_b",
        name="Component B",
        description="组件 B",
        category="test",
        version="0.1.0",
        status=CapabilityStatus.ON_SHELF,
        invoke=InvokeProtocol.FUNCTION,
        interface=InterfaceSpec(
            input_schema={}, output_schema={}, error_definitions=[],
        ),
    )


@pytest.fixture
def component_c() -> AtomicComponent:
    return AtomicComponent(
        id="atomic.test.comp_c",
        name="Component C",
        description="组件 C",
        category="test",
        version="0.1.0",
        status=CapabilityStatus.ON_SHELF,
        invoke=InvokeProtocol.FUNCTION,
        interface=InterfaceSpec(
            input_schema={}, output_schema={}, error_definitions=[],
        ),
    )


@pytest.fixture
def dag_components(component_a, component_b, component_c) -> Dict[str, AtomicComponent]:
    return {
        component_a.id: component_a,
        component_b.id: component_b,
        component_c.id: component_c,
    }


# ═══════════════════════════════════════════════════════════════
#  样本数据 — 管控策略
# ═══════════════════════════════════════════════════════════════

@pytest.fixture
def sample_policy() -> GovernancePolicy:
    return GovernancePolicy(
        rate_limit_rps=100,
        rate_limit_burst=200,
        timeout_seconds=30,
        retry_enabled=True,
        max_retries=3,
        circuit_breaker_enabled=True,
        circuit_breaker_threshold=5,
        log_enabled=True,
        audit_required=False,
    )


@pytest.fixture
def strict_policy() -> GovernancePolicy:
    return GovernancePolicy(
        rate_limit_rps=5,
        rate_limit_burst=10,
        timeout_seconds=10,
        retry_enabled=True,
        max_retries=1,
        circuit_breaker_enabled=True,
        circuit_breaker_threshold=2,
        log_enabled=True,
        audit_required=True,
    )


# ═══════════════════════════════════════════════════════════════
#  样本数据 — 货架状态 & 注册表 & 存储
# ═══════════════════════════════════════════════════════════════

@pytest.fixture
def shelf_state() -> CapabilityShelfState:
    return CapabilityShelfState()


@pytest.fixture
def registry(shelf_state: CapabilityShelfState) -> CapabilityRegistry:
    return CapabilityRegistry(shelf_state)


@pytest.fixture
def populated_registry(
    registry: CapabilityRegistry,
    sample_atomic: AtomicComponent,
    another_atomic: AtomicComponent,
    sample_composite: CompositeSkill,
    sample_scenario: ScenarioSolution,
) -> CapabilityRegistry:
    """预填充了数据的注册表"""
    registry.register_atomic(sample_atomic)
    registry.register_atomic(another_atomic)
    registry.register_composite(sample_composite)
    registry.register_scenario(sample_scenario)
    return registry


@pytest.fixture
def store(tmp_data_dir: Path) -> CapabilityStore:
    """CapabilityStore 实例，使用临时目录"""
    return CapabilityStore(str(tmp_data_dir))


@pytest.fixture
def saved_store(
    store: CapabilityStore,
    populated_registry: CapabilityRegistry,
) -> CapabilityStore:
    """已保存了一次状态的 CapabilityStore"""
    store.save(populated_registry.state)
    return store


# ═══════════════════════════════════════════════════════════════
#  样本数据 — 管控层
# ═══════════════════════════════════════════════════════════════

@pytest.fixture
def governance_guard() -> GovernanceGuard:
    return GovernanceGuard()


@pytest.fixture
def token_bucket(sample_policy: GovernancePolicy) -> TokenBucket:
    return TokenBucket(
        rps=sample_policy.rate_limit_rps,
        burst=sample_policy.rate_limit_burst,
    )


@pytest.fixture
def rate_limiter() -> RateLimiter:
    return RateLimiter()


@pytest.fixture
def circuit_breaker(sample_policy: GovernancePolicy) -> CircuitBreaker:
    return CircuitBreaker(sample_policy)


@pytest.fixture
def audit_logger(tmp_path: Path) -> AuditLogger:
    return AuditLogger(log_dir=tmp_path)


# ═══════════════════════════════════════════════════════════════
#  样本数据 — 标准化
# ═══════════════════════════════════════════════════════════════

@pytest.fixture
def version_manager() -> VersionManager:
    return VersionManager()


@pytest.fixture
def interface_validator() -> InterfaceValidator:
    return InterfaceValidator()


@pytest.fixture
def standardization_service() -> StandardizationService:
    return StandardizationService()


# ═══════════════════════════════════════════════════════════════
#  样本数据 — 运行时
# ═══════════════════════════════════════════════════════════════

@pytest.fixture
def runtime_engine(
    populated_registry: CapabilityRegistry,
    governance_guard: GovernanceGuard,
) -> RuntimeEngine:
    return RuntimeEngine(populated_registry.state, governance_guard)


@pytest.fixture
def engine_with_checkpoint(
    runtime_engine: RuntimeEngine,
    crash_recovery_dir: Path,
) -> RuntimeEngine:
    """配置了检查点目录的运行时引擎"""
    return RuntimeEngine(populated_registry.state, governance_guard, checkpoint_dir=str(crash_recovery_dir))


# ═══════════════════════════════════════════════════════════════
#  样本数据 — 生命周期
# ═══════════════════════════════════════════════════════════════

@pytest.fixture
def lifecycle_manager(
    populated_registry: CapabilityRegistry,
    store: CapabilityStore,
    crash_recovery_dir: Path,
) -> LifecycleManager:
    mgr = LifecycleManager(
        registry=populated_registry,
        store=store,
        work_dir=str(crash_recovery_dir),
    )
    return mgr


# ═══════════════════════════════════════════════════════════════
#  样本数据 — 管线上下文（适用于 build_pipeline）
# ═══════════════════════════════════════════════════════════════

@pytest.fixture
def pipeline_capabilities() -> List[Dict[str, Any]]:
    return [
        {
            "name": "智能问答",
            "description": "基于知识库的自动问答",
            "category": "conversation",
            "complexity": "high",
        },
        {
            "name": "文档翻译",
            "description": "多语言文档翻译",
            "category": "nlp",
            "complexity": "medium",
        },
    ]


@pytest.fixture
def pipeline_test_cases() -> List[Dict[str, Any]]:
    return [
        {"cap_id": "atomic.test.qa_bot", "input_data": {"query": "hello"}},
        {"cap_id": "atomic.test.translator", "input_data": {"text": "你好"}},
    ]


# ═══════════════════════════════════════════════════════════════
#  模拟断电数据（用于崩溃恢复测试）
# ═══════════════════════════════════════════════════════════════

@pytest.fixture
def crash_checkpoint_data() -> Dict[str, Any]:
    return {
        "project": "crash_project",
        "step": 3,
        "total": 7,
        "description": "封装",
        "timestamp": "2025-01-01T00:00:00+00:00",
    }
