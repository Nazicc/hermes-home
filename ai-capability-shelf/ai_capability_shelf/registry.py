"""
注册表层 — 能力货架核心 CRUD
===========================
- 注册/注销原子组件
- 注册/注销组合技能
- 注册/注销场景方案
- 按技术视角（类型/标签）和业务视角（场景）查询
- 全量/增量导出

高内聚：只处理能力注册与查询
低耦合：通过 CapabilityShelfState 纯数据类传递
崩溃安全：委托 persistence 层的原子写入
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Set, Callable, TYPE_CHECKING
from datetime import datetime, timezone

from ai_capability_shelf.exceptions import (
    DuplicateCapabilityError,
)
from ai_capability_shelf.models import (
    AtomicComponent,
    CompositeSkill,
    ScenarioSolution,
    CapabilityShelfState,
    CapabilityStatus,
)

if TYPE_CHECKING:
    from ai_capability_shelf.persistence import PersistenceProvider


class CapabilityRegistry:
    """
    能力注册表 — 货架核心
    """

    def __init__(
        self,
        state: Optional[CapabilityShelfState] = None,
        persistence_provider: Optional[PersistenceProvider] = None,
    ):
        self._state = state or CapabilityShelfState()
        self._provider = persistence_provider

    # ── 内部持久化辅助 ──

    def _save(self, operation: str = "registry_mutation") -> None:
        """突变后原子保存（provider 为 None 时静默跳过）"""
        if self._provider is not None:
            self._provider.save_state(self._state, operation=operation)

    # ── 状态访问 ──

    @property
    def state(self) -> CapabilityShelfState:
        return self._state

    # ── 原子组件注册 ──

    def register_atomic(self, component: AtomicComponent) -> bool:
        """注册原子组件（重复 ID 抛出 DuplicateCapabilityError）"""
        if component.id in self._state.atomic_components:
            raise DuplicateCapabilityError(
                component.id,
                detail=f"原子组件 '{component.id}' 已注册",
                context={"kind": "atomic", "existing": self._state.atomic_components[component.id].name},
            )
        self._state.atomic_components[component.id] = component
        self._state.last_modified = datetime.now(timezone.utc).isoformat()
        self._save("register_atomic")
        return True

    def unregister_atomic(self, component_id: str) -> bool:
        """注销原子组件（同时清除引用它的组合技能引用）"""
        if component_id not in self._state.atomic_components:
            return False
        del self._state.atomic_components[component_id]

        # 清理引用该组件的组合技能
        stale_skills: List[str] = []
        for sid, skill in self._state.composite_skills.items():
            refs = {s.component_id for s in skill.steps}
            if component_id in refs:
                stale_skills.append(sid)
        for sid in stale_skills:
            del self._state.composite_skills[sid]

        self._state.last_modified = datetime.now(timezone.utc).isoformat()
        self._save("unregister_atomic")
        return True

    def get_atomic(self, component_id: str) -> Optional[AtomicComponent]:
        return self._state.atomic_components.get(component_id)

    def list_atomic(
        self,
        category: Optional[str] = None,
        status: Optional[CapabilityStatus] = None,
        tags: Optional[Set[str]] = None,
    ) -> List[AtomicComponent]:
        """按条件列出原子组件"""
        results: List[AtomicComponent] = []
        for comp in self._state.atomic_components.values():
            if category and comp.category != category:
                continue
            if status and comp.status != status:
                continue
            if tags and not tags.intersection(comp.tags):
                continue
            results.append(comp)
        return results

    # ── 组合技能注册 ──

    def register_composite(self, skill: CompositeSkill) -> bool:
        """注册组合技能（重复 ID 抛出 DuplicateCapabilityError）"""
        if skill.id in self._state.composite_skills:
            raise DuplicateCapabilityError(
                skill.id,
                detail=f"组合技能 '{skill.id}' 已注册",
                context={"kind": "composite", "existing": self._state.composite_skills[skill.id].name},
            )
        self._state.composite_skills[skill.id] = skill
        self._state.last_modified = datetime.now(timezone.utc).isoformat()
        self._save("register_composite")
        return True

    def unregister_composite(self, skill_id: str) -> bool:
        if skill_id not in self._state.composite_skills:
            return False
        del self._state.composite_skills[skill_id]
        self._state.last_modified = datetime.now(timezone.utc).isoformat()
        self._save("unregister_composite")
        return True

    def get_composite(self, skill_id: str) -> Optional[CompositeSkill]:
        return self._state.composite_skills.get(skill_id)

    def list_composite(
        self,
        status: Optional[CapabilityStatus] = None,
    ) -> List[CompositeSkill]:
        if status:
            return [s for s in self._state.composite_skills.values() if s.status == status]
        return list(self._state.composite_skills.values())

    # ── 场景方案注册 ──

    def register_scenario(self, scenario: ScenarioSolution) -> bool:
        """注册场景方案（重复 ID 抛出 DuplicateCapabilityError）"""
        if scenario.id in self._state.scenario_solutions:
            raise DuplicateCapabilityError(
                scenario.id,
                detail=f"场景方案 '{scenario.id}' 已注册",
                context={"kind": "scenario", "existing": self._state.scenario_solutions[scenario.id].name},
            )
        self._state.scenario_solutions[scenario.id] = scenario
        self._state.last_modified = datetime.now(timezone.utc).isoformat()
        self._save("register_scenario")
        return True

    def unregister_scenario(self, scenario_id: str) -> bool:
        if scenario_id not in self._state.scenario_solutions:
            return False
        del self._state.scenario_solutions[scenario_id]
        self._state.last_modified = datetime.now(timezone.utc).isoformat()
        self._save("unregister_scenario")
        return True

    def get_scenario(self, scenario_id: str) -> Optional[ScenarioSolution]:
        return self._state.scenario_solutions.get(scenario_id)

    def list_scenarios(self) -> List[ScenarioSolution]:
        return list(self._state.scenario_solutions.values())

    # ── 查询 ──

    def search(self, keyword: str) -> Dict[str, List[str]]:
        """
        全文搜索（名称/描述）
        返回 {atomic: [id, ...], composite: [id, ...], scenario: [id, ...]}
        """
        kw = keyword.lower()
        result: Dict[str, List[str]] = {"atomic": [], "composite": [], "scenario": []}

        for cid, comp in self._state.atomic_components.items():
            if kw in comp.name.lower() or kw in comp.description.lower():
                result["atomic"].append(cid)

        for sid, skill in self._state.composite_skills.items():
            if kw in skill.name.lower() or kw in skill.description.lower():
                result["composite"].append(sid)

        for scid, scenario in self._state.scenario_solutions.items():
            if kw in scenario.name.lower() or kw in scenario.description.lower():
                result["scenario"].append(scid)

        return result

    def export_snapshot(self) -> Dict[str, Any]:
        """导出状态快照（用于序列化/备份）"""
        return self._state.model_dump(mode="json")

    def count(self) -> Dict[str, int]:
        """货架统计"""
        return {
            "atomic_components": len(self._state.atomic_components),
            "composite_skills": len(self._state.composite_skills),
            "scenario_solutions": len(self._state.scenario_solutions),
        }
