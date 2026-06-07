"""
标准化层 — 接口规范校验、版本管理、异常标准化
============================================
四大强制规则：
1. 接口标准化 — 统一入参/出参/格式（JSON Schema）
2. 文档标准化 — 强制 documentation 字段
3. 版本标准化 — 语义化版本 + 回滚支持
4. 异常标准化 — 兜底配置、超时熔断、自动重试

高内聚：只处理"标准化规则"
低耦合：通过 InterfaceSpec, GovernancePolicy 等纯数据类传递
"""

from __future__ import annotations
import re
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timezone

from ai_capability_shelf.exceptions import ValidationError, VersionError
from ai_capability_shelf.models import (
    AtomicComponent,
    CompositeSkill,
    ScenarioSolution,
    InterfaceSpec,
    ErrorCategory,
)
from ai_capability_shelf.governance import GovernancePolicy


# ── 版本管理 ──────────────────────────────────────────────

class VersionManager:
    """
    语义化版本管理
    格式: MAJOR.MINOR.PATCH (如 1.2.3)
    支持自动递增、已验证回滚
    """

    VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")

    @staticmethod
    def validate(version: str) -> bool:
        """校验版本格式"""
        return bool(VersionManager.VERSION_PATTERN.match(version))

    @staticmethod
    def bump(version: str, part: str = "patch") -> str:
        """
        递增版本号
        part: major | minor | patch
        """
        if not VersionManager.validate(version):
            raise VersionError(version=version, detail=f"无效版本号: {version}")
        major, minor, patch = map(int, version.split("."))
        if part == "major":
            return f"{major + 1}.0.0"
        elif part == "minor":
            return f"{major}.{minor + 1}.0"
        elif part == "patch":
            return f"{major}.{minor}.{patch + 1}"
        raise VersionError(part=part, detail=f"无效版本部位: {part}, 可选: major/minor/patch")

    @staticmethod
    def compare(a: str, b: str) -> int:
        """版本比较: a < b → -1, a == b → 0, a > b → 1"""
        va = tuple(map(int, a.split(".")))
        vb = tuple(map(int, b.split(".")))
        if va < vb: return -1
        if va > vb: return 1
        return 0


# ── 接口校验 ──────────────────────────────────────────────

class InterfaceValidator:
    """
    接口规范校验器
    验证 InterfaceSpec 是否满足标准化要求
    """

    @staticmethod
    def validate(spec: InterfaceSpec) -> Tuple[bool, List[str]]:
        """
        校验接口规范
        返回 (是否通过, 错误列表)
        """
        errors: List[str] = []

        # 入参必须至少定义类型
        if not spec.input_schema:
            errors.append("input_schema 不可为空，必须定义入参类型")
        elif "type" not in spec.input_schema:
            errors.append("input_schema 缺少 'type' 字段")

        # 出参同样
        if not spec.output_schema:
            errors.append("output_schema 不可为空，必须定义出参类型")
        elif "type" not in spec.output_schema:
            errors.append("output_schema 缺少 'type' 字段")

        # 异常定义
        if not spec.error_definitions:
            errors.append("error_definitions 不可为空，至少定义一个标准异常")
        else:
            codes = [e.get("code") for e in spec.error_definitions]
            if len(codes) != len(set(codes)):
                errors.append("异常码定义存在重复")

            valid_categories = {e.value for e in ErrorCategory}
            for e in spec.error_definitions:
                if e.get("category") not in valid_categories:
                    errors.append(
                        f"异常分类无效: {e.get('category')}, "
                        f"可选: {valid_categories}"
                    )

        return (len(errors) == 0, errors)


# ── 能力标准化校验 ──────────────────────────────────────────

class StandardizationService:
    """
    标准化服务 — 统一校验所有层级的标准化合规
    """

    MIN_DESCRIPTION_LENGTH = 10

    @staticmethod
    def check_atomic(component: AtomicComponent) -> Tuple[bool, List[str]]:
        """校验原子组件是否满足标准化要求"""
        errors: List[str] = []

        # 基本必填字段
        if not component.id:
            errors.append("id 不可为空")
        if not component.name:
            errors.append("name 不可为空")
        if len(component.description) < StandardizationService.MIN_DESCRIPTION_LENGTH:
            errors.append(f"description 至少需要 {StandardizationService.MIN_DESCRIPTION_LENGTH} 字符")

        # 版本
        if not VersionManager.validate(component.version):
            errors.append(f"版本格式无效: {component.version} (需 MAJOR.MINOR.PATCH)")

        # 接口规范
        spec_ok, spec_errors = InterfaceValidator.validate(component.interface)
        if not spec_ok:
            errors.extend([f"interface: {e}" for e in spec_errors])

        # 文档
        if not component.documentation:
            errors.append("documentation 不可为空")

        return (len(errors) == 0, errors)

    @staticmethod
    def check_composite(skill: CompositeSkill) -> Tuple[bool, List[str]]:
        """校验组合技能"""
        errors: List[str] = []

        if not skill.id:
            errors.append("id 不可为空")
        if not skill.name:
            errors.append("name 不可为空")
        if not skill.steps:
            errors.append("steps 不可为空（至少一个工作流步骤）")

        spec_ok, spec_errors = InterfaceValidator.validate(skill.interface)
        if not spec_ok:
            errors.extend([f"interface: {e}" for e in spec_errors])

        return (len(errors) == 0, errors)

    @staticmethod
    def check_scenario(scenario: ScenarioSolution) -> Tuple[bool, List[str]]:
        """校验场景方案"""
        errors: List[str] = []

        if not scenario.id:
            errors.append("id 不可为空")
        if not scenario.name:
            errors.append("name 不可为空")
        if not scenario.required_capabilities:
            errors.append("required_capabilities 至少需要一个能力引用")

        return (len(errors) == 0, errors)

    @staticmethod
    def check_governance(policy: GovernancePolicy) -> Tuple[bool, List[str]]:
        """校验管控策略参数边界"""
        errors: List[str] = []

        if policy.rate_limit_rps < 1:
            errors.append("rate_limit_rps 必须 ≥ 1")
        if policy.timeout_seconds < 1:
            errors.append("timeout_seconds 必须 ≥ 1")
        if policy.circuit_breaker_threshold < 1:
            errors.append("circuit_breaker_threshold 必须 ≥ 1")

        return (len(errors) == 0, errors)
