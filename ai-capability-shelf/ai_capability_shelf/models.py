"""
AI能力货架 — 五层架构纯数据模型
================================
高内聚：每个数据类只封装自身责任
低耦合：纯数据类，零业务依赖
崩溃安全：全部 JSON 可序列化 + Pydantic 校验
"""

from __future__ import annotations
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Set
from datetime import datetime, timezone

from typing import TYPE_CHECKING

from ai_capability_shelf.exceptions import ModelError
from pydantic import BaseModel, Field, field_validator

if TYPE_CHECKING:
    from ai_capability_shelf.governance import GovernancePolicy


# ── 枚举定义 ──────────────────────────────────────────────

class CapabilityTier(str, Enum):
    """五层架构层级"""
    BASE_INFRA    = "base_infra"      # 底层基座：大模型、向量库、数据库、运行环境
    ATOMIC        = "atomic"          # 原子组件：最小不可拆分能力单元
    COMPOSITE     = "composite"       # 组合技能：多个原子串联高频工作流
    SCENARIO      = "scenario"        # 场景方案：按岗位/行业打包完整方案
    GOVERNANCE    = "governance"      # 管控接入：权限、限流、版本、日志


class CapabilityStatus(str, Enum):
    """能力生命周期状态"""
    DRAFT        = "draft"          # 创建待标准化
    STANDARDIZED = "standardized"   # 已完成标准化封装
    ON_SHELF     = "on_shelf"       # 上架可用
    DEPRECATED   = "deprecated"     # 已废弃（但仍可用）
    RETIRED      = "retired"        # 彻底下线


class InvokeProtocol(str, Enum):
    """调用协议类型"""
    FUNCTION = "function"             # 本地函数调用
    HTTP     = "http"                 # REST API 调用
    MCP      = "model_context_protocol"  # MCP 工具调用
    GRPC     = "grpc"                 # gRPC 调用
    SCRIPT   = "script"              # 脚本执行


class ErrorCategory(str, Enum):
    """标准异常分类"""
    VALIDATION     = "VALIDATION_ERROR"       # 输入参数校验失败
    AUTH           = "AUTH_ERROR"             # 权限/认证错误
    RATE_LIMIT     = "RATE_LIMIT_ERROR"       # 限流触发
    TIMEOUT        = "TIMEOUT_ERROR"          # 超时
    INTERNAL       = "INTERNAL_ERROR"         # 内部执行错误
    DEPENDENCY     = "DEPENDENCY_ERROR"       # 依赖调用失败
    NOT_FOUND      = "NOT_FOUND_ERROR"        # 能力/资源未找到
    CIRCUIT_BREAK  = "CIRCUIT_BREAKER_ERROR"  # 熔断触发


# ── 接口规范 ──────────────────────────────────────────────

class InterfaceSpec(BaseModel):
    """统一接口规范 — 入参/出参/异常三位一体"""
    input_schema: Dict[str, Any] = Field(
        default_factory=dict,
        description="入参 JSON Schema"
    )
    output_schema: Dict[str, Any] = Field(
        default_factory=dict,
        description="出参 JSON Schema"
    )
    error_definitions: List[Dict[str, str]] = Field(
        default_factory=list,
        description="异常码定义列表: [{'code': str, 'message': str, 'category': str}]"
    )
    example_input: Optional[Dict[str, Any]] = None
    example_output: Optional[Dict[str, Any]] = None

    @field_validator("error_definitions")
    @classmethod
    def check_error_categories(cls, v: List[Dict]) -> List[Dict]:
        valid = {e.value for e in ErrorCategory}
        for err in v:
            if err.get("category") not in valid:
                raise ModelError(f"无效异常分类: {err.get('category')}, 可选: {valid}")
        return v


# ── 运行时指标 ──────────────────────────────────────────────

class RuntimeMetrics(BaseModel):
    """运行时调用统计（不持久化到能力定义）"""
    total_calls: int = 0
    success_calls: int = 0
    failed_calls: int = 0
    avg_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    last_called_at: Optional[str] = None
    circuit_open: bool = False


# ── 五层能力模型 ──────────────────────────────────────────

class BaseInfra(BaseModel):
    """
    底层基座
    大模型、向量库、数据库、运行环境、API 网关的配置模型
    """
    name: str
    provider: str                          # 提供商: openai, deepseek, chroma, postgres...
    version: str = "1.0.0"
    endpoint: Optional[str] = None         # API 端点
    api_key_ref: Optional[str] = None      # 密钥引用（不存实际密钥）
    config: Dict[str, Any] = Field(default_factory=dict)
    health_check_endpoint: Optional[str] = None

    def model_dump_serializable(self) -> Dict[str, Any]:
        """排除敏感字段的序列化"""
        d = self.model_dump()
        d.pop("api_key_ref", None)
        return d


class AtomicComponent(BaseModel):
    """
    原子组件 — 最小不可拆分能力单元
    类别：文本处理、工具脚本、多媒体、Agent调度、RAG能力
    """
    id: str                                    # 唯一标识: text.summarize.v1
    name: str
    tier: CapabilityTier = CapabilityTier.ATOMIC
    status: CapabilityStatus = CapabilityStatus.DRAFT
    version: str = "0.1.0"
    category: str = "text"                     # text, tool, multimedia, agent, rag
    description: str = ""
    interface: InterfaceSpec = Field(default_factory=InterfaceSpec)
    invoke: InvokeProtocol = InvokeProtocol.FUNCTION
    invoke_config: Dict[str, Any] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)
    documentation: str = ""
    owner: str = "unassigned"
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class WorkflowStep(BaseModel):
    """组合技能中的单个工作流步骤"""
    component_id: str
    label: str = ""
    input_mapping: Dict[str, str] = Field(
        default_factory=dict,
        description="前序输出 → 本步骤输入 映射"
    )
    retry_on_failure: bool = True
    timeout_override: Optional[int] = None     # 覆盖全局超时(秒)


class CompositeSkill(BaseModel):
    """
    组合技能 — 多个原子组件串联形成高频固定工作流
    """
    id: str
    name: str
    tier: CapabilityTier = CapabilityTier.COMPOSITE
    status: CapabilityStatus = CapabilityStatus.DRAFT
    version: str = "0.1.0"
    description: str = ""
    steps: List[WorkflowStep] = Field(default_factory=list)
    interface: InterfaceSpec = Field(default_factory=InterfaceSpec)
    tags: List[str] = Field(default_factory=list)
    documentation: str = ""
    owner: str = "unassigned"
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class ScenarioSolution(BaseModel):
    """
    场景方案 — 按岗位/行业打包完整业务流程
    包含一个或多个组合技能、原子组件
    """
    id: str
    name: str
    tier: CapabilityTier = CapabilityTier.SCENARIO
    status: CapabilityStatus = CapabilityStatus.DRAFT
    version: str = "0.1.0"
    description: str = ""
    industry: str = ""
    target_role: str = ""
    required_capabilities: List[str] = Field(  # 引用的组合技能/原子组件ID
        default_factory=list
    )
    workflow_order: List[str] = Field(
        default_factory=list,
        description="能力调用顺序"
    )
    interface: InterfaceSpec = Field(default_factory=InterfaceSpec)
    tags: List[str] = Field(default_factory=list)
    documentation: str = ""
    owner: str = "unassigned"
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# ── 货架持久化状态 ────────────────────────────────────────

class CapabilityShelfState(BaseModel):
    """
    货架全局状态 — 用于崩溃后恢复
    """
    version: str = "1.0.0"
    last_modified: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    infrastructure: Dict[str, BaseInfra] = Field(default_factory=dict)
    atomic_components: Dict[str, AtomicComponent] = Field(default_factory=dict)
    composite_skills: Dict[str, CompositeSkill] = Field(default_factory=dict)
    scenario_solutions: Dict[str, ScenarioSolution] = Field(default_factory=dict)
    governance_policies: Dict[str, GovernancePolicy] = Field(default_factory=dict)
    runtime_metrics: Dict[str, RuntimeMetrics] = Field(default_factory=dict)

    def get_tier_capabilities(self, tier: CapabilityTier) -> int:
        """获取指定层级的能力数量"""
        return {
            CapabilityTier.BASE_INFRA: len(self.infrastructure),
            CapabilityTier.ATOMIC: len(self.atomic_components),
            CapabilityTier.COMPOSITE: len(self.composite_skills),
            CapabilityTier.SCENARIO: len(self.scenario_solutions),
            CapabilityTier.GOVERNANCE: len(self.governance_policies),
        }.get(tier, 0)

    @property
    def summary(self) -> Dict[str, Any]:
        """货架概览摘要"""
        return {
            "version": self.version,
            "last_modified": self.last_modified,
            "total_capabilities": (
                len(self.infrastructure)
                + len(self.atomic_components)
                + len(self.composite_skills)
                + len(self.scenario_solutions)
            ),
            "by_tier": {
                "base_infra": len(self.infrastructure),
                "atomic": len(self.atomic_components),
                "composite": len(self.composite_skills),
                "scenario": len(self.scenario_solutions),
                "governance_policies": len(self.governance_policies),
            },
        }


# ── 能力唯一标识引用 ──────────────────────────────────────

class CapabilityRef(BaseModel):
    """能力引用 — 统一查找任意层级能力"""
    tier: CapabilityTier
    cap_id: str
    version: Optional[str] = None


# ── 修正 Pydantic 前向引用 ─────────────────────────────────
# CapabilityShelfState 引用了 governance.py 中的 GovernancePolicy，
# 必须在 governance 模块加载后调用 model_rebuild() 解析 forward ref
from ai_capability_shelf.governance import GovernancePolicy

CapabilityShelfState.model_rebuild()
