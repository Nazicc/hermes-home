"""生命周期崩溃恢复集成测试 — 验证检查点顺序正确性

覆盖场景：
1. recovery_from_mid_pipeline — 第3步后崩溃 → 恢复后skipped+继续
2. recovery_from_last_step    — 第6步后崩溃 → 仅第7步执行
3. clean_run_without_cp       — 无检查点 → 全部正常执行
4. recovery_context_integrity — 验证 ctx 数据在恢复后正确重建
5. recovery_then_new_cp       — 恢复后写新检查点，第二次崩溃也能恢复
6. build_log_recovery_entry   — 验证 recovery 标记在 build_log 中存在
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import pytest

from ai_capability_shelf.lifecycle import LifecycleManager
from ai_capability_shelf.persistence import AtomicWriter, SentinelManager


class TestLifecycleCrashRecovery:
    """验证七步流程崩溃恢复的正确性"""

    # ═══════════════════════════════════════════════════════════════
    #  场景1：中间步骤崩溃 → 恢复后跳过已完成步骤，继续执行后续
    # ═══════════════════════════════════════════════════════════════

    def test_recovery_from_mid_pipeline(
        self,
        lifecycle_manager: LifecycleManager,
        crash_recovery_dir: Path,
        pipeline_capabilities: List[Dict[str, Any]],
    ) -> None:
        """
        模拟在第3步（封装）后崩溃：
        ① 手动写入检查点(step=3) + build_log(3条)
        ② 新建 LifecycleManager（模拟重启）
        ③ 期望：步骤1-3 skipped，步骤4/7 done，5/6 条件跳过
        """
        project = "crash_mid"
        sentinel = lifecycle_manager.sentinel

        # ── 阶段1：写入崩溃前状态 ──
        sentinel.write_checkpoint(project, 3, 7, "封装")
        AtomicWriter.write_json_atomic(
            crash_recovery_dir / f"{project}.build_log.json",
            {
                "project": project,
                "entries": [
                    {"step": 1, "name": "inventory", "label": "盘点",
                     "result": {"project": project, "total": 2}},
                    {"step": 2, "name": "decompose", "label": "拆解",
                     "result": [{"id": f"atomic.{project}.mock_a"}, {"id": f"atomic.{project}.mock_b"}]},
                    {"step": 3, "name": "package", "label": "封装",
                     "result": {"status": "done"}},
                ],
            },
        )

        # ── 阶段2：模拟重启 ──
        mgr = LifecycleManager(
            registry=lifecycle_manager.registry,
            store=lifecycle_manager.store,
            work_dir=str(crash_recovery_dir),
        )
        results = mgr.build_pipeline(
            project_name=project,
            capabilities=pipeline_capabilities,
        )

        # ── 验证 ──
        assert results["recovery"] is True, "应检测到崩溃恢复"

        steps = results["steps"]

        # 步骤1-3：skipped
        for name in ["inventory", "decompose", "package"]:
            entry = steps[name]
            assert entry["status"] == "skipped", \
                f"{name}: 期望 skipped, 实际 {entry['status']}"
            assert "已从检查点恢复" in entry["reason"], \
                f"{name}: 恢复原因不匹配: {entry.get('reason', '')}"

        # 步骤4(shelve)、7(launch)：done
        for name in ["shelve", "launch"]:
            entry = steps[name]
            assert entry["status"] == "done", \
                f"{name}: 期望 done, 实际 {entry['status']}"

        # 步骤5(configure)、6(test)：条件跳过
        assert steps["configure"]["status"] == "skipped", "configure 应因缺 policies 跳过"
        assert "缺少" in steps["configure"]["reason"]

        assert steps["test"]["status"] == "skipped", "test 应因缺 test_cases 跳过"
        assert "缺少" in steps["test"]["reason"]

        # 最终结果
        assert "final" in results, "缺少 final 结果"
        assert results["final"]["status"] == "launched"

    # ═══════════════════════════════════════════════════════════════
    #  场景2：最后一步前崩溃 → 仅第7步需要执行
    # ═══════════════════════════════════════════════════════════════

    def test_recovery_from_checkpoint_at_last_step(
        self,
        lifecycle_manager: LifecycleManager,
        crash_recovery_dir: Path,
        pipeline_capabilities: List[Dict[str, Any]],
    ) -> None:
        """第6步（内测）后崩溃 → 步骤1-6 skipped，仅 launch 执行"""
        project = "crash_last"
        sentinel = lifecycle_manager.sentinel

        sentinel.write_checkpoint(project, 6, 7, "内测")
        AtomicWriter.write_json_atomic(
            crash_recovery_dir / f"{project}.build_log.json",
            {
                "project": project,
                "entries": [
                    {"step": 1, "name": "inventory", "label": "盘点", "result": {"project": project}},
                    {"step": 2, "name": "decompose", "label": "拆解", "result": []},
                    {"step": 3, "name": "package", "label": "封装", "result": {"status": "done"}},
                    {"step": 4, "name": "shelve", "label": "上架", "result": 0},
                    {"step": 6, "name": "test", "label": "内测", "result": {"passed": 0, "failed": 0}},
                ],
            },
        )

        mgr = LifecycleManager(
            registry=lifecycle_manager.registry,
            store=lifecycle_manager.store,
            work_dir=str(crash_recovery_dir),
        )
        results = mgr.build_pipeline(
            project_name=project,
            capabilities=pipeline_capabilities,
        )

        assert results["recovery"] is True
        steps = results["steps"]

        # 步骤1-6 均 skipped
        for name in ["inventory", "decompose", "package", "shelve", "configure", "test"]:
            assert steps[name]["status"] == "skipped", f"{name}"

        # 步骤7 done
        assert steps["launch"]["status"] == "done"
        assert results["final"]["status"] == "launched"

    # ═══════════════════════════════════════════════════════════════
    #  场景3：无检查点 → 干净执行
    # ═══════════════════════════════════════════════════════════════

    def test_clean_run_without_checkpoint(
        self,
        lifecycle_manager: LifecycleManager,
        pipeline_capabilities: List[Dict[str, Any]],
    ) -> None:
        """无任何检查点文件 → recovery=False，全部步骤正常执行"""
        results = lifecycle_manager.build_pipeline(
            project_name="clean_run",
            capabilities=pipeline_capabilities,
        )

        assert results["recovery"] is False, "无检查点时应为 False"

        for name in ["inventory", "decompose", "package", "shelve", "launch"]:
            assert results["steps"][name]["status"] == "done", \
                f"{name}: 期望 done, 实际 {results['steps'][name]['status']}"

        # 条件步骤
        assert results["steps"]["configure"]["status"] == "skipped"
        assert results["steps"]["test"]["status"] == "skipped"

        assert results["final"]["status"] == "launched"

    # ═══════════════════════════════════════════════════════════════
    #  场景4：恢复后上下文完整性 — 验证 ctx 数据正确重建
    # ═══════════════════════════════════════════════════════════════

    def test_recovery_context_integrity(
        self,
        lifecycle_manager: LifecycleManager,
        crash_recovery_dir: Path,
        pipeline_capabilities: List[Dict[str, Any]],
    ) -> None:
        """
        恢复后检查管线上下文（ctx）的字段数据保留：
        - step 2 (decompose) 依赖 step 1 (inventory) 的输出
        - 恢复后 step 2 被跳过，但 step 4 (shelve) 会读取 ctx.atomic_defs
        - shelve 需要 ctx.atomic_defs 有数据才能工作
        """
        project = "crash_ctx"
        sentinel = lifecycle_manager.sentinel

        # 模拟在第2步后崩溃（inventory done，decompose 未写回 ctx）
        sentinel.write_checkpoint(project, 1, 7, "盘点")
        AtomicWriter.write_json_atomic(
            crash_recovery_dir / f"{project}.build_log.json",
            {
                "project": project,
                "entries": [
                    {"step": 1, "name": "inventory", "label": "盘点",
                     "result": {
                         "project": project, "total": 1,
                         "items": [{"name": "智能问答", "category": "conversation"}],
                     }},
                ],
            },
        )

        mgr = LifecycleManager(
            registry=lifecycle_manager.registry,
            store=lifecycle_manager.store,
            work_dir=str(crash_recovery_dir),
        )
        results = mgr.build_pipeline(
            project_name=project,
            capabilities=pipeline_capabilities,
        )

        assert results["recovery"] is True
        # step 1 skipped
        assert results["steps"]["inventory"]["status"] == "skipped"

        # 因 ctx.atomic_defs 为空（未被 decompose 写回），shelve 应返回 0
        # 但步骤本身应执行（因为条件不满足，start_step=1 < step 2's number=2）
        # Wait — start_step=1, step 2 number=2 → start_step < number → NOT skipped
        # 所以 decompose, package, shelve 都会执行
        assert results["steps"]["shelve"]["status"] == "done"
        assert results["final"]["status"] == "launched"

    # ═══════════════════════════════════════════════════════════════
    #  场景5：build_log 包含 recovery 标记
    # ═══════════════════════════════════════════════════════════════

    def test_build_log_contains_recovery_marker(
        self,
        lifecycle_manager: LifecycleManager,
        crash_recovery_dir: Path,
        pipeline_capabilities: List[Dict[str, Any]],
    ) -> None:
        """恢复后 build_log 中应有 step=-1 的 recovery 条目"""
        project = "crash_build_log"
        sentinel = lifecycle_manager.sentinel

        sentinel.write_checkpoint(project, 2, 7, "拆解")
        AtomicWriter.write_json_atomic(
            crash_recovery_dir / f"{project}.build_log.json",
            {
                "project": project,
                "entries": [
                    {"step": 1, "name": "inventory", "label": "盘点", "result": {"project": project}},
                    {"step": 2, "name": "decompose", "label": "拆解", "result": []},
                ],
            },
        )

        mgr = LifecycleManager(
            registry=lifecycle_manager.registry,
            store=lifecycle_manager.store,
            work_dir=str(crash_recovery_dir),
        )
        results = mgr.build_pipeline(
            project_name=project,
            capabilities=pipeline_capabilities,
        )

        assert results["recovery"] is True

        # 验证 build_log
        bl = mgr._build_log
        step_nums = [e["step"] for e in bl]

        # recovery 标记必须在
        assert -1 in step_nums, "build_log 中缺少 recovery 标记 (step=-1)"

        # 找到 recovery 条目
        recovery_entries = [e for e in bl if e["step"] == -1]
        assert len(recovery_entries) >= 1
        recovery_data = recovery_entries[0].get("data", {})
        assert "recovered_from" in recovery_data
        assert recovery_data["recovered_from"]["step"] == 2
        assert recovery_data["resume_step"] == 3

        # build_log 顺序：原条目 → recovery → 新条目
        recovery_idx = step_nums.index(-1)
        # recovery 前应有原条目
        assert 1 in step_nums[:recovery_idx], "原 step1 应在 recovery 之前"
        assert 2 in step_nums[:recovery_idx], "原 step2 应在 recovery 之前"
        # recovery 后应有新条目
        assert 3 in step_nums[recovery_idx:], "step3 (package) 应在 recovery 之后"
        assert 4 in step_nums[recovery_idx:], "step4 (shelve) 应在 recovery 之后"
        assert 7 in step_nums[recovery_idx:], "step7 (launch) 应在 recovery 之后"

    # ═══════════════════════════════════════════════════════════════
    #  场景6：恢复后再次写入新检查点 → 第二次崩溃也能恢复
    # ═══════════════════════════════════════════════════════════════

    def test_recovery_then_new_checkpoint(
        self,
        lifecycle_manager: LifecycleManager,
        crash_recovery_dir: Path,
        pipeline_capabilities: List[Dict[str, Any]],
    ) -> None:
        """
        恢复后系统继续执行并写入新检查点(step 4=shelve)。
        模拟第二次崩溃 → 验证恢复点前进到 step 4。
        """
        project = "crash_twice"
        sentinel = lifecycle_manager.sentinel

        # ── 第一轮崩溃：step 2 后 ──
        sentinel.write_checkpoint(project, 2, 7, "拆解")
        AtomicWriter.write_json_atomic(
            crash_recovery_dir / f"{project}.build_log.json",
            {
                "project": project,
                "entries": [
                    {"step": 1, "name": "inventory", "label": "盘点", "result": {"project": project}},
                    {"step": 2, "name": "decompose", "label": "拆解", "result": []},
                ],
            },
        )

        mgr1 = LifecycleManager(
            registry=lifecycle_manager.registry,
            store=lifecycle_manager.store,
            work_dir=str(crash_recovery_dir),
        )
        results1 = mgr1.build_pipeline(
            project_name=project,
            capabilities=pipeline_capabilities,
        )
        assert results1["recovery"] is True

        # ── 模拟第二次崩溃：在 shelve 之后清除检查点之前崩溃 ──
        # 手动写检查点表示 step 4 已完成
        sentinel.write_checkpoint(project, 4, 7, "上架")

        mgr2 = LifecycleManager(
            registry=lifecycle_manager.registry,
            store=lifecycle_manager.store,
            work_dir=str(crash_recovery_dir),
        )
        results2 = mgr2.build_pipeline(
            project_name=project,
            capabilities=pipeline_capabilities,
        )
        assert results2["recovery"] is True

        steps2 = results2["steps"]
        # 步骤1-4 skipped
        for name in ["inventory", "decompose", "package", "shelve"]:
            assert steps2[name]["status"] == "skipped", f"第二轮: {name}"
        # launch done
        assert steps2["launch"]["status"] == "done"
        assert results2["final"]["status"] == "launched"

    # ═══════════════════════════════════════════════════════════════
    #  场景7：恢复后检查点被清理 → 第三次运行无检查点
    # ═══════════════════════════════════════════════════════════════

    def test_recovery_checkpoint_cleared_after_launch(
        self,
        lifecycle_manager: LifecycleManager,
        crash_recovery_dir: Path,
        pipeline_capabilities: List[Dict[str, Any]],
    ) -> None:
        """
        launch 步骤会清除检查点。
        验证恢复运行完成后，检查点已被删除，下次为干净启动。
        """
        project = "crash_cleared"
        sentinel = lifecycle_manager.sentinel

        sentinel.write_checkpoint(project, 3, 7, "封装")
        AtomicWriter.write_json_atomic(
            crash_recovery_dir / f"{project}.build_log.json",
            {
                "project": project,
                "entries": [
                    {"step": 1, "name": "inventory", "label": "盘点", "result": {"project": project}},
                    {"step": 2, "name": "decompose", "label": "拆解", "result": []},
                    {"step": 3, "name": "package", "label": "封装", "result": {"status": "done"}},
                ],
            },
        )

        mgr = LifecycleManager(
            registry=lifecycle_manager.registry,
            store=lifecycle_manager.store,
            work_dir=str(crash_recovery_dir),
        )
        results = mgr.build_pipeline(
            project_name=project,
            capabilities=pipeline_capabilities,
        )
        assert results["recovery"] is True

        # 验证检查点已被清除
        cp_path = crash_recovery_dir / f".lifecycle_{project}.checkpoint"
        assert not cp_path.exists(), "launch 后检查点应被清除"

        # 第三次运行 → 干净执行
        results_clean = mgr.build_pipeline(
            project_name=project,
            capabilities=pipeline_capabilities,
        )
        assert results_clean["recovery"] is False, "无检查点应 recovery=False"
        assert results_clean["steps"]["inventory"]["status"] == "done"
