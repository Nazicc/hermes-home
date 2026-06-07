"""
组合层 — 原子→组合→场景编排
============================
支持有向无环图（DAG）编排
检查循环依赖
构建执行拓扑顺序

高内聚：只处理能力组合逻辑
低耦合：通过 AtomicComponent, CompositeSkill 纯数据类传递
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Set, Tuple
from collections import deque

from ai_capability_shelf.models import (
    AtomicComponent,
    CompositeSkill,
    ScenarioSolution,
    WorkflowStep,
    CapabilityShelfState,
)


# ── 循环依赖检测 ──────────────────────────────────────────

class CycleDetector:
    """DAG 循环依赖检测 — 拓扑排序 + DFS"""

    @staticmethod
    def find_cycle(
        adjacency: Dict[str, List[str]]
    ) -> Optional[List[str]]:
        """
        检测有向图中的环
        返回环路径（如有），否则 None
        """
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {node: WHITE for node in adjacency}

        def dfs(node: str, path: List[str]) -> Optional[List[str]]:
            color[node] = GRAY
            path.append(node)
            for neighbor in adjacency.get(node, []):
                if neighbor not in color:
                    continue
                if color[neighbor] == GRAY:
                    # 找到环 — 从 neighbor 到当前
                    cycle_start = path.index(neighbor)
                    return path[cycle_start:] + [neighbor]
                if color[neighbor] == WHITE:
                    result = dfs(neighbor, path)
                    if result:
                        return result
            path.pop()
            color[node] = BLACK
            return None

        for node in adjacency:
            if color[node] == WHITE:
                result = dfs(node, [])
                if result:
                    return result
        return None


# ── 拓扑排序 ──────────────────────────────────────────────

class TopologicalSort:
    """拓扑排序 — 确定 DAG 执行顺序"""

    @staticmethod
    def sort(adjacency: Dict[str, List[str]]) -> Tuple[bool, List[str], str]:
        """
        拓扑排序
        返回 (是否有环, 执行顺序, 错误信息)
        """
        # 先检测环
        cycle = CycleDetector.find_cycle(adjacency)
        if cycle:
            return (
                False,
                [],
                f"检测到循环依赖: {' → '.join(cycle)}"
            )

        # Kahn 算法
        in_degree: Dict[str, int] = {n: 0 for n in adjacency}
        for node, neighbors in adjacency.items():
            for n in neighbors:
                if n in in_degree:
                    in_degree[n] += 1

        queue = deque([n for n, d in in_degree.items() if d == 0])
        result = []

        while queue:
            node = queue.popleft()
            result.append(node)
            for neighbor in adjacency.get(node, []):
                if neighbor in in_degree:
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        queue.append(neighbor)

        if len(result) != len(adjacency):
            return (False, [], "拓扑排序不完整（可能存在孤立环）")

        return (True, result, "")


# ── 组合校验器 ──────────────────────────────────────────────

class CompositionValidator:
    """校验组合的合法性"""

    @staticmethod
    def validate_composite(
        skill: CompositeSkill,
        state: CapabilityShelfState,
    ) -> Tuple[bool, List[str]]:
        """
        校验组合技能的所有步骤引用的原子组件是否存在
        """
        errors: List[str] = []
        for i, step in enumerate(skill.steps):
            if step.component_id not in state.atomic_components:
                errors.append(
                    f"步骤 {i+1} ('{step.label or step.component_id}'): "
                    f"原子组件 '{step.component_id}' 未注册"
                )
        return (len(errors) == 0, errors)

    @staticmethod
    def validate_scenario(
        scenario: ScenarioSolution,
        state: CapabilityShelfState,
    ) -> Tuple[bool, List[str]]:
        """
        校验场景方案的所有依赖是否存在
        """
        errors: List[str] = []
        for cap_id in scenario.required_capabilities:
            exists = (
                cap_id in state.atomic_components
                or cap_id in state.composite_skills
            )
            if not exists:
                errors.append(f"依赖的能力 '{cap_id}' 未注册")
        return (len(errors) == 0, errors)


# ── DAG 构建 ──────────────────────────────────────────────

class DagBuilder:
    """从组合技能/场景方案构建执行 DAG"""

    @staticmethod
    def from_composite(
        skill: CompositeSkill,
    ) -> Dict[str, List[str]]:
        """
        从组合技能的 WorkflowStep 构建邻接表
        步骤按顺序连接 (step_i → step_{i+1})
        """
        adjacency: Dict[str, List[str]] = {}
        step_ids = [s.component_id for s in skill.steps]
        for i, sid in enumerate(step_ids):
            adjacency[sid] = []
            if i + 1 < len(step_ids):
                adjacency[sid].append(step_ids[i + 1])
        return adjacency

    @staticmethod
    def from_scenario(
        scenario: ScenarioSolution,
    ) -> Dict[str, List[str]]:
        """
        从场景方案构建邻接表
        """
        adjacency: Dict[str, List[str]] = {}
        order = scenario.workflow_order or scenario.required_capabilities
        for i, cap_id in enumerate(order):
            adjacency[cap_id] = []
            if i + 1 < len(order):
                adjacency[cap_id].append(order[i + 1])
        # 补全未在 order 中的能力（作为孤立节点）
        for cap_id in scenario.required_capabilities:
            if cap_id not in adjacency:
                adjacency[cap_id] = []
        return adjacency


# ── 组合装配器 ──────────────────────────────────────────────

class CompositeAssembler:
    """
    组合装配器 — 将原子组件编排为组合技能

    功能：
    - 校验引用是否有效
    - 检测循环依赖
    - 拓扑排序
    - 返回执行计划
    """

    @staticmethod
    def assemble(
        skill: CompositeSkill,
        state: CapabilityShelfState,
    ) -> dict:
        """
        装配组合技能
        返回执行计划
        """
        # 1. 校验组件引用
        valid, errors = CompositionValidator.validate_composite(skill, state)
        if not valid:
            return {"success": False, "errors": errors}

        # 2. 构建 DAG
        adjacency = DagBuilder.from_composite(skill)

        # 3. 拓扑排序
        ok, order, err_msg = TopologicalSort.sort(adjacency)
        if not ok:
            return {"success": False, "errors": [err_msg]}

        return {
            "success": True,
            "skill_id": skill.id,
            "steps": len(skill.steps),
            "execution_order": order,
            "components": [
                state.atomic_components[sid].model_dump()
                for sid in order
                if sid in state.atomic_components
            ],
        }
