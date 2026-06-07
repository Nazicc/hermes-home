"""
运行时层 — 全链路执行引擎
========================
- 执行原子组件（模拟调用）
- 执行组合技能（按拓扑排序顺序执行）
- 执行场景方案
- 超时控制
- 结果记录

高内聚：只处理"能力执行"
低耦合：通过 InterfaceSpec、GovernancePolicy 等纯数据类传递
崩溃安全：哨兵检查点记录执行进度，断电/重启后自动恢复
"""

from __future__ import annotations
import time
import threading
from typing import Any, Callable, Dict, List, Optional, Tuple, TYPE_CHECKING
from datetime import datetime, timezone
from pathlib import Path

from ai_capability_shelf.models import (
    AtomicComponent,
    CompositeSkill,
    ScenarioSolution,
    CapabilityShelfState,
    InvokeProtocol,
    CapabilityStatus,
)
from ai_capability_shelf.composition import DagBuilder, TopologicalSort
from ai_capability_shelf.governance import GovernanceGuard, GovernancePolicy

if TYPE_CHECKING:
    from ai_capability_shelf.persistence import PersistenceProvider


# ── 执行结果 ──────────────────────────────────────────────

class ExecutionResult:
    """单次执行结果"""

    def __init__(
        self,
        cap_id: str,
        success: bool,
        output: Any = None,
        error: Optional[str] = None,
        duration_ms: float = 0.0,
    ):
        self.cap_id = cap_id
        self.success = success
        self.output = output
        self.error = error
        self.duration_ms = duration_ms
        self.timestamp = datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cap_id": self.cap_id,
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp.isoformat(),
        }


# ── 超时控制 ──────────────────────────────────────────────

def with_timeout(
    func: Callable[[], Any],
    timeout_seconds: float,
    default_return: Any = None,
) -> Any:
    """带超时的函数执行"""
    result: List[Any] = [default_return]
    error: List[Optional[Exception]] = [None]

    def wrapper():
        try:
            result[0] = func()
        except Exception as e:
            error[0] = e

    thread = threading.Thread(target=wrapper, daemon=True)
    thread.start()
    thread.join(timeout=timeout_seconds)

    if thread.is_alive():
        return None  # 超时

    exc = error[0]
    if exc is not None:
        raise exc
    return result[0]


# ── 原子执行器 ──────────────────────────────────────────────

class AtomicExecutor:
    """
    原子组件执行器
    真实环境应替换为实际模型/API 调用
    """

    @staticmethod
    def execute(
        component: AtomicComponent,
        input_data: Optional[Dict[str, Any]] = None,
        governor: Optional[GovernanceGuard] = None,
        policy: Optional[GovernancePolicy] = None,
    ) -> ExecutionResult:
        """执行原子组件"""
        start = time.monotonic()

        # 管控检查
        if governor and policy:
            allowed, reason = governor.check_access(
                component.id, policy, caller_role="user"
            )
            if not allowed:
                return ExecutionResult(
                    cap_id=component.id,
                    success=False,
                    error=reason,
                    duration_ms=(time.monotonic() - start) * 1000,
                )

        try:
            # 按调用协议路由
            if component.invoke == InvokeProtocol.FUNCTION:
                output = component.interface.example_output or {"status": "ok"}

            elif component.invoke == InvokeProtocol.HTTP:
                endpoint = component.invoke_config.get("endpoint", "unknown")
                output = {"status": "ok", "endpoint": endpoint}

            elif component.invoke == InvokeProtocol.MCP:
                tool = component.invoke_config.get("tool", "unknown")
                output = {"status": "ok", "mcp_tool": tool}

            elif component.invoke == InvokeProtocol.GRPC:
                endpoint = component.invoke_config.get("endpoint", "unknown")
                method = component.invoke_config.get("method", "unknown")
                output = {"status": "ok", "grpc_endpoint": endpoint, "method": method}

            elif component.invoke == InvokeProtocol.SCRIPT:
                script = component.invoke_config.get("script", "unknown")
                output = {"status": "ok", "script": script}

            else:
                output = component.interface.example_output or {"status": "ok"}

            duration = (time.monotonic() - start) * 1000
            return ExecutionResult(
                cap_id=component.id,
                success=True,
                output=output,
                duration_ms=duration,
            )

        except Exception as e:
            duration = (time.monotonic() - start) * 1000
            return ExecutionResult(
                cap_id=component.id,
                success=False,
                error=str(e),
                duration_ms=duration,
            )


# ── 运行时引擎 ──────────────────────────────────────────────

class RuntimeEngine:
    """
    运行时引擎 — 全链路执行

    崩溃安全设计：
    - 每次步骤执行前原子写入哨兵检查点
    - 启动时自动检测检查点并恢复
    - 正常完成时清空检查点
    - 无检查点 = 无中断，直接从头执行
    """

    def __init__(
        self,
        state: CapabilityShelfState,
        governor: Optional[GovernanceGuard] = None,
        checkpoint_dir: Optional[str] = None,
        persistence_provider: Optional["PersistenceProvider"] = None,
    ):
        self.state = state
        self.governor = governor or GovernanceGuard()
        self.results: Dict[str, List[ExecutionResult]] = {}
        self.checkpoint_dir: Optional[str] = checkpoint_dir
        self._provider: Optional["PersistenceProvider"] = persistence_provider
        if checkpoint_dir:
            cp_dir = Path(checkpoint_dir)
            if self._provider:
                self._provider.clean_orphaned_tmp(cp_dir, ".checkpoint_")
            else:
                from ai_capability_shelf.persistence import AtomicWriter
                AtomicWriter.clean_orphaned_tmp(cp_dir, ".checkpoint_")

    def _recover_from_checkpoint(
        self, run_id: str
    ) -> Tuple[Optional[int], Optional[str]]:
        """
        从检查点恢复执行进度

        检查点中 step 字段是即将执行但可能被中断的步骤编号（1-indexed）。
        恢复时从 step - 1（0-indexed）开始重试该步骤。

        Returns:
            (start_idx, last_cap_id): 从 start_idx 开始恢复
            (None, None): 无检查点或检查点无效
        """
        if not self.checkpoint_dir:
            return None, None
        cp = Path(self.checkpoint_dir) / f".checkpoint_{run_id}.json"
        if not cp.exists():
            return None, None
        if self._provider:
            data = self._provider.read_json_safe(cp)
        else:
            from ai_capability_shelf.persistence import AtomicWriter
            data = AtomicWriter.read_json_safe(cp)
        if not data or "step" not in data:
            return None, None
        # step 是 1-indexed，转换为 0-indexed 作为起始重试下标
        start_idx = max(0, data["step"] - 1)
        return start_idx, data.get("current")

    def _write_checkpoint(self, run_id: str, step: int, total: int, cap_id: str) -> None:
        """原子写入哨兵检查点（委托 AtomicWriter）"""
        if not self.checkpoint_dir:
            return
        cp = Path(self.checkpoint_dir) / f".checkpoint_{run_id}.json"
        data = {
            "run_id": run_id,
            "step": step,
            "total": total,
            "current": cap_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if self._provider:
            self._provider.write_json_atomic(cp, data)
        else:
            from ai_capability_shelf.persistence import AtomicWriter
            AtomicWriter.write_json_atomic(cp, data)

    def _clear_checkpoint(self, run_id: str) -> None:
        """正常完成时清除检查点"""
        if not self.checkpoint_dir:
            return
        cp = Path(self.checkpoint_dir) / f".checkpoint_{run_id}.json"
        if cp.exists():
            cp.unlink()

    # ── 执行方法 ────────────────────────────────────────────

    def execute_atomic(
        self,
        component_id: str,
        input_data: Optional[Dict[str, Any]] = None,
        policy: Optional[GovernancePolicy] = None,
    ) -> ExecutionResult:
        """执行单个原子组件"""
        component = self.state.atomic_components.get(component_id)
        if not component:
            return ExecutionResult(
                cap_id=component_id,
                success=False,
                error=f"原子组件 '{component_id}' 未注册",
            )
        result = AtomicExecutor.execute(component, input_data, self.governor, policy)
        self.results.setdefault(component_id, []).append(result)
        return result

    def execute_composite(
        self,
        skill_id: str,
        input_data: Optional[Dict[str, Any]] = None,
        policy: Optional[GovernancePolicy] = None,
        run_id: Optional[str] = None,
    ) -> List[ExecutionResult]:
        """
        执行组合技能（按拓扑排序顺序）
        每个步骤独立执行

        崩溃恢复：如果 checkpoint_dir 已配置，启动时会自动检测
        并恢复未完成的执行。
        """
        skill = self.state.composite_skills.get(skill_id)
        if not skill:
            return [ExecutionResult(
                cap_id=skill_id, success=False,
                error=f"组合技能 '{skill_id}' 未注册",
            )]

        # 构建 DAG 执行顺序
        adjacency = DagBuilder.from_composite(skill)
        ok, order, err_msg = TopologicalSort.sort(adjacency)
        if not ok:
            return [ExecutionResult(
                cap_id=skill_id, success=False, error=err_msg,
            )]

        _run_id = run_id or f"run_{skill_id}_{int(time.time())}"
        results: List[ExecutionResult] = []

        # ── 检测检查点，恢复进度 ──
        recovered_idx, recovered_cap = self._recover_from_checkpoint(_run_id)
        start_idx = recovered_idx if recovered_idx is not None else 0
        if recovered_idx is not None:
            # 恢复时：将中断前已成功执行的步骤计入 results（占位标记）
            for j in range(recovered_idx):
                cap_id = order[j]
                results.append(
                    ExecutionResult(
                        cap_id=cap_id,
                        success=True,
                        output={"recovered": True},
                        duration_ms=0.0,
                    )
                )

        for i in range(start_idx, len(order)):
            cap_id = order[i]
            self._write_checkpoint(_run_id, i + 1, len(order), cap_id)
            result = self.execute_atomic(cap_id, input_data, policy)
            results.append(result)
            if not result.success:
                break  # 失败即停止

        # 正常完成 → 清除检查点
        if all(r.success for r in results):
            self._clear_checkpoint(_run_id)

        return results

    def execute_scenario(
        self,
        scenario_id: str,
        input_data: Optional[Dict[str, Any]] = None,
        policy: Optional[GovernancePolicy] = None,
    ) -> Dict[str, Any]:
        """执行场景方案"""
        scenario = self.state.scenario_solutions.get(scenario_id)
        if not scenario:
            return {"success": False, "error": f"场景方案 '{scenario_id}' 未注册"}

        results: Dict[str, Any] = {}
        all_ok = True
        for cap_id in scenario.required_capabilities:
            # 判断是原子还是组合
            if cap_id in self.state.composite_skills:
                sub_results = self.execute_composite(cap_id, input_data, policy)
                results[cap_id] = [r.to_dict() for r in sub_results]
                if not all(r.success for r in sub_results):
                    all_ok = False
                    break
            elif cap_id in self.state.atomic_components:
                r = self.execute_atomic(cap_id, input_data, policy)
                results[cap_id] = r.to_dict()
                if not r.success:
                    all_ok = False
                    break
            else:
                results[cap_id] = {"success": False, "error": f"能力 '{cap_id}' 未注册"}
                all_ok = False
                break

        return {"success": all_ok, "results": results}

    def get_history(self, cap_id: str) -> List[ExecutionResult]:
        """获取某个能力的执行历史"""
        return self.results.get(cap_id, [])
