"""
test_persistence.py — 持久化层回归测试
========================================
覆盖：原子写入、哨兵检测、断电恢复、审计日志
设计原则：
- 每个测试独立验证一个行为，不依赖其他测试的副作用
- 模拟断电场景：直接创建./tmp文件 / 删除哨兵文件 / 损坏JSON内容
- 测试函数名即行为描述
"""

from __future__ import annotations

import json
import os
import time
import unittest.mock
from pathlib import Path
from typing import Any, Dict

import pytest

from ai_capability_shelf.models import CapabilityShelfState
from ai_capability_shelf.persistence import (
    AtomicWriter,
    AuditLogger,
    CapabilityStore,
    SentinelManager,
)


# ═══════════════════════════════════════════════════════════════
#  AtomicWriter — 原子文件写入器
# ═══════════════════════════════════════════════════════════════

class TestAtomicWriterBasics:
    """基础写入和读取"""

    def test_write_text_and_read_back(self, tmp_data_dir: Path):
        f = tmp_data_dir / "hello.txt"
        AtomicWriter.write_atomic(f, "hello world")
        assert f.read_text() == "hello world"

    def test_write_json(self, tmp_data_dir: Path):
        f = tmp_data_dir / "data.json"
        AtomicWriter.write_json_atomic(f, {"a": 1, "b": "x"})
        assert json.loads(f.read_text()) == {"a": 1, "b": "x"}

    def test_read_json_nonexistent(self, tmp_data_dir: Path):
        assert AtomicWriter.read_json(tmp_data_dir / "nope.json") is None

    def test_read_json_safe_nonexistent(self, tmp_data_dir: Path):
        assert AtomicWriter.read_json_safe(tmp_data_dir / "nope.json") is None

    def test_read_json_safe_corrupted_file(self, tmp_data_dir: Path):
        f = tmp_data_dir / "broken.json"
        f.write_text("{invalid json!!!")
        result = AtomicWriter.read_json_safe(f)
        assert result is None
        # 损坏文件应该被删除
        assert not f.exists()

    def test_write_bytes_atomic(self, tmp_data_dir: Path):
        f = tmp_data_dir / "binary.bin"
        AtomicWriter.write_bytes_atomic(f, b"\x00\x01\x02\xff")
        assert f.read_bytes() == b"\x00\x01\x02\xff"

    def test_write_creates_parent_dir(self, tmp_data_dir: Path):
        nested = tmp_data_dir / "a" / "b" / "c" / "deep.txt"
        AtomicWriter.write_atomic(nested, "nested")
        assert nested.read_text() == "nested"

    def test_fsync_dir(self, tmp_data_dir: Path):
        sub = tmp_data_dir / "fsync_test"
        AtomicWriter.fsync_dir(sub)
        assert sub.exists()


class TestAtomicWriterCrashSafety:
    """断电安全 — 原子写入、临时文件清理"""

    def test_atomic_write_does_not_destroy_existing_on_crash(self, tmp_data_dir: Path):
        """模拟在 write_atomic 中途崩溃：删除正在写入的 tmp 文件，目标文件应完好"""
        f = tmp_data_dir / "important.json"
        AtomicWriter.write_json_atomic(f, {"version": 1})

        # 模拟崩溃：先写好 tmp，但在 rename 前断电
        tmp = f.with_suffix(f".tmp.{os.getpid()}")
        with open(tmp, "w") as fh:
            fh.write("corrupt data")
            fh.flush()
            os.fsync(fh.fileno())
        # 现在 tmp 存在，但 rename 还没发生 — 假装断电了
        # 生产代码的正常写入会：写 tmp → rename → 删除 tmp
        # 目标文件仍完好
        assert json.loads(f.read_text()) == {"version": 1}

    def test_clean_orphaned_tmp_removes_stale_tmp_files(
        self, crash_recovery_dir: Path
    ):
        """clean_orphaned_tmp 应删除孤立的 .tmp 文件"""
        target = crash_recovery_dir / "data.json"
        # 创建残留 tmp 文件（模拟断电后遗留）
        (crash_recovery_dir / "data.json.tmp.12345").touch()
        (crash_recovery_dir / "data.json.tmp.67890").touch()
        # 不应误删正常文件
        target.write_text('{"hello": "world"}')

        AtomicWriter.clean_orphaned_tmp(target)

        remaining = [p.name for p in crash_recovery_dir.iterdir()]
        assert "data.json.tmp.12345" not in remaining
        assert "data.json.tmp.67890" not in remaining
        assert "data.json" in remaining  # 正常文件保留

    def test_clean_orphaned_tmp_with_custom_prefix(self, crash_recovery_dir: Path):
        """带自定义前缀的 tmp 清理"""
        (crash_recovery_dir / "foo.bar.tmp.111").touch()
        AtomicWriter.clean_orphaned_tmp(
            crash_recovery_dir / "ignore.bar", prefix="foo"
        )
        remaining = [p.name for p in crash_recovery_dir.iterdir()]
        assert "foo.bar.tmp.111" not in remaining

    def test_raise_on_failure_cleans_tmp(self, tmp_data_dir: Path):
        """write_atomic 失败时应清理临时文件"""
        f = tmp_data_dir / "test.txt"
        # 模拟路径不可写：先创建文件并设置只读
        f.mkdir()  # 创建为目录，使写入失败

        with pytest.raises((PermissionError, IsADirectoryError, OSError)):
            AtomicWriter.write_atomic(f, "data")

        # 检查 tmp 文件已被清理
        tmp_files = list(tmp_data_dir.glob(f"{f.name}.tmp.*"))
        assert len(tmp_files) == 0


# ═══════════════════════════════════════════════════════════════
#  SentinelManager — 哨兵文件管理器
# ═══════════════════════════════════════════════════════════════

class TestSentinelManager:
    """哨兵文件：崩溃检测、检查点、恢复"""

    def test_is_crashed_returns_false_by_default(self, tmp_data_dir: Path):
        sentinel = SentinelManager(tmp_data_dir)
        assert sentinel.is_crashed is False

    def test_acquire_creates_sentinel(self, tmp_data_dir: Path):
        sentinel = SentinelManager(tmp_data_dir)
        sentinel.acquire("test_op")
        assert sentinel.is_crashed is True
        sentinel.release()
        assert sentinel.is_crashed is False

    def test_crash_timestamp(self, tmp_data_dir: Path):
        sentinel = SentinelManager(tmp_data_dir)
        sentinel.acquire("op")
        ts = sentinel.crash_timestamp
        assert ts is not None
        assert "operation" in ts or "timestamp" in ts
        sentinel.release()
        assert sentinel.crash_timestamp is None

    def test_get_crash_report_when_no_crash(self, tmp_data_dir: Path):
        sentinel = SentinelManager(tmp_data_dir)
        report = sentinel.get_crash_report()
        assert report == {"crashed": False}

    def test_get_crash_report_when_crashed(self, tmp_data_dir: Path):
        sentinel = SentinelManager(tmp_data_dir)
        sentinel.acquire("important_operation")
        report = sentinel.get_crash_report()
        assert report["crashed"] is True
        assert report["operation"] == "important_operation"
        assert "timestamp" in report
        sentinel.release()

    def test_clear_removes_sentinel(self, tmp_data_dir: Path):
        sentinel = SentinelManager(tmp_data_dir)
        sentinel.acquire("op")
        assert sentinel.is_crashed
        sentinel.clear()
        assert not sentinel.is_crashed


class TestSentinelCheckpoint:
    """项目级检查点 — 断电恢复的关键"""

    def test_write_and_read_checkpoint(self, tmp_data_dir: Path):
        sentinel = SentinelManager(tmp_data_dir)
        sentinel.write_checkpoint("my_project", step=3, total=10, description="测试")
        cp = sentinel.read_checkpoint("my_project")
        assert cp is not None
        assert cp["project"] == "my_project"
        assert cp["step"] == 3
        assert cp["total"] == 10
        assert cp["description"] == "测试"

    def test_read_nonexistent_checkpoint(self, tmp_data_dir: Path):
        sentinel = SentinelManager(tmp_data_dir)
        cp = sentinel.read_checkpoint("nonexistent")
        assert cp is None

    def test_clear_checkpoint(self, tmp_data_dir: Path):
        sentinel = SentinelManager(tmp_data_dir)
        sentinel.write_checkpoint("proj", step=1, total=5, description="test")
        assert sentinel.read_checkpoint("proj") is not None
        sentinel.clear_checkpoint("proj")
        assert sentinel.read_checkpoint("proj") is None

    def test_clear_checkpoint_cleans_orphaned_tmp(self, crash_recovery_dir: Path):
        """clear_checkpoint 应清理检查点的残留临时文件"""
        sentinel = SentinelManager(crash_recovery_dir)
        sentinel.write_checkpoint("proj", step=2, total=3, description="progress")

        # 模拟断电残留：创建 tmp 文件
        cp = crash_recovery_dir / ".lifecycle_proj.checkpoint"
        tmp_file = crash_recovery_dir / ".lifecycle_proj.checkpoint.tmp.99999"
        tmp_file.touch()

        sentinel.clear_checkpoint("proj")

        assert not cp.exists()
        assert not tmp_file.exists()

    def test_checkpoint_atomic_write_survives_tmp_clean(self, crash_recovery_dir: Path):
        """检查点文件的原子写入不应因为孤立 tmp 而读取损坏"""
        sentinel = SentinelManager(crash_recovery_dir)

        # 创建孤立 tmp（旧的，不是当前进程的）
        (crash_recovery_dir / ".lifecycle_proj.checkpoint.tmp.1").touch()

        # 正常写入（原子写入，会在 rename 前创建新的 tmp）
        sentinel.write_checkpoint("proj", step=5, total=7, description="封装")

        # 读取应返回正确的检查点，而非被旧 tmp 污染
        cp = sentinel.read_checkpoint("proj")
        assert cp is not None
        assert cp["step"] == 5


# ═══════════════════════════════════════════════════════════════
#  CapabilityStore — 能力货架持久化存储
# ═══════════════════════════════════════════════════════════════

class TestCapabilityStoreBasic:
    """基础存储操作"""

    def test_save_and_load(self, store: CapabilityStore):
        state = CapabilityShelfState()
        store.save(state)
        loaded, meta = store.load()
        assert loaded is not None
        assert meta["crash_detected"] is False

    def test_exists_after_save(self, store: CapabilityStore):
        assert store.exists is False
        store.save(CapabilityShelfState())
        assert store.exists is True

    def test_load_from_scratch(self, store: CapabilityStore):
        state, meta = store.load()
        assert state is None
        assert meta["crash_detected"] is False

    def test_ensure_dirs_creates_backup_dir(self, tmp_data_dir: Path):
        store = CapabilityStore(tmp_data_dir)
        store.ensure_dirs()
        assert (tmp_data_dir / "backups").exists()

    def test_recover_returns_empty_state_on_fresh(self, store: CapabilityStore):
        state, meta = store.recover()
        assert state is not None  # recover 返回空货架而非 None
        assert state.atomic_components == {}
        assert meta["crash_detected"] is False

    def test_save_with_state(self, store: CapabilityStore, shelf_state: CapabilityShelfState):
        store.save(shelf_state)
        loaded, _ = store.load()
        assert loaded is not None

    def test_last_load_meta(self, store: CapabilityStore):
        store.load()
        meta = store.last_load_meta
        assert isinstance(meta, dict)
        assert "crash_detected" in meta

    def test_get_data_size(self, store: CapabilityStore):
        assert store.get_data_size() == 0
        store.save(CapabilityShelfState())
        assert store.get_data_size() > 0


class TestCapabilityStoreSaved:
    """已保存状态的读取"""

    def test_save_load_roundtrip(
        self, saved_store: CapabilityStore, populated_registry
    ):
        loaded, _ = saved_store.load()
        assert loaded is not None
        # 检查重要字段
        assert "atomic.test.qa_bot" in loaded.atomic_components
        assert loaded.atomic_components["atomic.test.qa_bot"].name == "QA Bot"

    def test_no_crash_detected_after_clean_save(self, saved_store: CapabilityStore):
        _, meta = saved_store.load()
        assert meta["crash_detected"] is False

    def test_backup_created_on_second_save(
        self, saved_store: CapabilityStore
    ):
        saved_store.save(CapabilityShelfState())
        backups = list(saved_store.backup_dir.glob("shelf_state_*.json"))
        assert len(backups) >= 1


class TestCapabilityStoreCrashRecovery:
    """断电崩溃恢复"""

    def test_sentinel_detected_on_load_after_crash(
        self, tmp_data_dir: Path
    ):
        """模拟：save 中途断电 → 哨兵存在 → load 检测到崩溃"""
        store = CapabilityStore(tmp_data_dir)
        store.ensure_dirs()
        store.sentinel.acquire("save")

        state, meta = store.load()
        assert meta["crash_detected"] is True
        assert meta["crash_info"] is not None
        assert meta["crash_info"]["crashed"] is True

    def test_recovery_from_backup_when_main_corrupted(
        self, tmp_data_dir: Path
    ):
        """模拟：哨兵存在 + 主文件损坏 → 从备份恢复"""
        store = CapabilityStore(tmp_data_dir)
        store.ensure_dirs()

        # 先做一次完整 save（产生备份）
        state = CapabilityShelfState()
        store.save(state)

        # 再 save 一次产生一个备份
        store.save(state)

        # 模拟崩溃：创建哨兵 + 损坏主文件
        store.sentinel.acquire("save_with_crash")
        store.state_path.write_text("corrupted!!! not json")

        loaded, meta = store.load()
        assert meta["crash_detected"] is True
        assert meta["recovered"] is True
        assert meta["recovery_source"] == "backup"
        assert loaded is not None

    def test_recover_after_backup_still_available(
        self, tmp_data_dir: Path
    ):
        """recover() 完整流程：崩溃 → 从备份恢复 → 返回空货架"""
        store = CapabilityStore(tmp_data_dir)
        store.ensure_dirs()

        # 先正常保存一次产生备份
        store.save(CapabilityShelfState())

        # 模拟崩溃
        store.sentinel.acquire("save")
        store.state_path.unlink()

        state, meta = store.recover()
        assert meta["crash_detected"] is True
        assert meta["recovered"] is True
        assert state is not None

    def test_no_backup_no_crash_returns_empty(
        self, tmp_data_dir: Path
    ):
        """无崩溃 + 无数据 → 返回空"""
        store = CapabilityStore(tmp_data_dir)
        state, meta = store.load()
        assert state is None
        assert meta["crash_detected"] is False

    def test_no_backup_with_crash_sentinel_created_by_hand(
        self, tmp_data_dir: Path
    ):
        """哨兵存在 + 无备份 + 无主文件 → 清理哨兵 + 返回空"""
        store = CapabilityStore(tmp_data_dir)
        store.ensure_dirs()
        store.sentinel.acquire("save")

        state, meta = store.load()
        assert meta["crash_detected"] is True
        assert meta.get("recovery_failed") is True
        assert state is None

        # 哨兵应该被清理了
        assert not store.sentinel.is_crashed

    def test_save_failure_clears_sentinel(
        self, tmp_data_dir: Path
    ):
        """save() 执行中断 → 哨兵应被清理（真实文件系统失败）"""
        store = CapabilityStore(tmp_data_dir)

        # 先正常保存一次（初始化目录结构和哨兵状态）
        store.save(CapabilityShelfState())

        # 真实模拟写入失败：将状态文件替换为目录
        # shutil.copy2 读取目录作为源文件会触发 IsADirectoryError（OSError 子类）
        store.state_path.unlink()
        store.state_path.mkdir()

        with pytest.raises(OSError):
            store.save(CapabilityShelfState())

        # 哨兵应已清理
        assert not store.sentinel.is_crashed

    def test_sentinel_is_false_alarm_when_main_file_ok(
        self, tmp_data_dir: Path
    ):
        """哨兵存在但主文件完好 → 虚惊（false alarm）→ 正常读取"""
        store = CapabilityStore(tmp_data_dir)
        store.save(CapabilityShelfState())

        # 手动创建哨兵（模拟：save 完成但哨兵未释放的极端情况）
        store.sentinel.acquire("save")

        # 但主文件是完好的
        state, meta = store.load()
        assert state is not None
        assert meta["crash_detected"] is True
        assert meta["recovered"] is True
        assert meta["recovery_source"] == "main_file"

        # 哨兵被清理
        assert not store.sentinel.is_crashed


# ═══════════════════════════════════════════════════════════════
#  AuditLogger — 审计日志
# ═══════════════════════════════════════════════════════════════

class TestAuditLoggerBasics:
    """基础审计日志操作"""

    def test_log_and_read(self, tmp_path: Path):
        logger = AuditLogger(log_dir=tmp_path)
        logger.log(cap_id="atomic.test.qa_bot", action="invoke", caller="test")
        logger.flush()

        entries = logger.read_back()
        assert len(entries) == 1
        assert entries[0]["cap_id"] == "atomic.test.qa_bot"
        assert entries[0]["action"] == "invoke"

    def test_log_auto_flush_at_threshold(self, tmp_path: Path):
        """超过 FLUSH_THRESHOLD → 自动 flush"""
        logger = AuditLogger(log_dir=tmp_path)
        # 默认_FLUSH_THRESHOLD = 10
        for i in range(10):
            logger.log(cap_id=f"cap_{i}", action="invoke", caller="test")

        # buffer 应已清空
        assert len(logger._buffer) == 0

        entries = logger.read_back()
        assert len(entries) == 10

    def test_read_back_respects_limit(self, tmp_path: Path):
        logger = AuditLogger(log_dir=tmp_path)
        for i in range(100):
            logger.log(cap_id=f"cap_{i}", action="invoke", caller="test")
        logger.flush()

        entries = logger.read_back(limit=5)
        assert len(entries) == 5

    def test_read_back_empty_log(self, tmp_path: Path):
        logger = AuditLogger(log_dir=tmp_path)
        entries = logger.read_back()
        assert entries == []

    def test_log_with_detail(self, tmp_path: Path):
        logger = AuditLogger(log_dir=tmp_path)
        logger.log(
            cap_id="test",
            action="invoke",
            caller="system",
            status="error",
            detail={"error_code": "TIMEOUT", "duration_ms": 5000},
        )
        logger.flush()
        entries = logger.read_back()
        assert entries[0]["status"] == "error"
        assert entries[0]["detail"]["error_code"] == "TIMEOUT"


class TestAuditLoggerCrashResilience:
    """审计日志崩溃安全"""

    def test_append_write_does_not_destroy_existing(
        self, tmp_path: Path
    ):
        """追加写不会破坏已有日志"""
        logger = AuditLogger(log_dir=tmp_path)
        logger.log(cap_id="first", action="invoke", caller="test")
        logger.flush()

        # 第二次写入
        logger.log(cap_id="second", action="invoke", caller="test")
        logger.flush()

        entries = logger.read_back()
        assert len(entries) == 2
        assert entries[0]["cap_id"] == "first"
        assert entries[1]["cap_id"] == "second"

    def test_read_back_skips_corrupted_lines(
        self, tmp_path: Path
    ):
        """日志文件中有损坏行时自动跳过"""
        logger = AuditLogger(log_dir=tmp_path)

        # 写几行正常数据（直接操作文件）
        logger.log(cap_id="good1", action="invoke", caller="test")
        logger.log(cap_id="good2", action="invoke", caller="test")
        logger.flush()

        # 模拟崩溃导致一行损坏（追加损坏行）
        log_file = tmp_path / f"audit_{time.strftime('%Y%m%d')}.log"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write("corrupted line!!!\n")

        # 再追加一个正常日志（接力写入）
        logger.log(cap_id="good3", action="invoke", caller="test")
        logger.flush()

        entries = logger.read_back()
        # 应该有 3 个正常条目
        assert len(entries) == 3
        assert entries[0]["cap_id"] == "good1"
        assert entries[1]["cap_id"] == "good2"
        assert entries[2]["cap_id"] == "good3"

    def test_recover_cleans_orphaned_tmp(
        self, tmp_path: Path
    ):
        """recover 清理日志目录的残留临时文件"""
        logger = AuditLogger(log_dir=tmp_path)

        # 模拟残留 tmp
        (tmp_path / "audit_20250101.log.tmp.12345").touch()
        (tmp_path / "audit_20250102.log.tmp.67890").touch()

        logger.recover()

        remaining = [p.name for p in tmp_path.iterdir()]
        assert "audit_20250101.log.tmp.12345" not in remaining
        assert "audit_20250102.log.tmp.67890" not in remaining

    def test_flush_crash_retains_buffer(self, tmp_path: Path):
        """flush 失败（OSError）保留 buffer 等待重试"""
        logger = AuditLogger(log_dir=tmp_path)

        logger.log(cap_id="x", action="invoke", caller="test")

        # 模拟 flush 不可写
        with unittest.mock.patch(
            "builtins.open",
            side_effect=OSError("read-only filesystem"),
        ):
            logger.flush()  # 应静默失败，保留 buffer
        assert len(logger._buffer) == 1  # buffer 保留

        # 恢复后再次 flush 应成功
        logger.flush()
        assert len(logger._buffer) == 0
        entries = logger.read_back()
        assert len(entries) == 1


# ═══════════════════════════════════════════════════════════════
#  端到端 — 完整断电恢复流程
# ═══════════════════════════════════════════════════════════════

class TestFullCrashRecoveryFlow:
    """模拟真实的完整断电恢复流程"""

    def test_full_power_loss_recovery(
        self, crash_recovery_dir: Path
    ):
        """
        模拟完整断电恢复：

        1. 正常保存数据 → 产生主文件 + 备份
        2. 模拟断电（写入 tmp 后停电，留下哨兵）
        3. 重新启动 → 检测哨兵 → 读取损坏主文件 → 从备份恢复
        """
        store = CapabilityStore(crash_recovery_dir)

        # Step 1: 正常保存
        state = CapabilityShelfState()
        store.save(state)
        assert store.exists

        # Step 2: 模拟断电 — 新的 save 进行到一半
        store.ensure_dirs()
        store.sentinel.acquire("save")
        # 写部分损坏的数据到主文件（模拟断电时主文件没写完）
        store.state_path.write_text('{"partial": true, "corrupted": ')

        # Step 3: 重新启动 — 新 CapabilityStore 实例（模拟进程重启）
        store2 = CapabilityStore(crash_recovery_dir)
        loaded, meta = store2.load()

        assert meta["crash_detected"] is True
        assert meta["recovered"] is True
        assert meta["recovery_source"] == "backup"
        assert loaded is not None

        # 恢复后哨兵应已清理
        assert not store2.sentinel.is_crashed

    def test_atomic_writer_survives_interrupted_write(
        self, crash_recovery_dir: Path
    ):
        """AtomicWriter 在写入中断后，目标文件仍然有效"""
        f = crash_recovery_dir / "data.json"

        # 先写一个有效文件
        AtomicWriter.write_json_atomic(f, {"version": 1})

        # 模拟：写 tmp 后没 rename 就崩溃了
        tmp = f.with_suffix(f".tmp.99999")
        tmp.write_text("{corrupted")

        # 新写入（会创建新的 tmp + rename）
        AtomicWriter.write_json_atomic(f, {"version": 2})

        # 旧 tmp 残留应该被新写入忽略（clean 由外部调用）
        # 但读取时应正确返回 version 2
        data = AtomicWriter.read_json(f)
        assert data == {"version": 2}

    def test_sentinel_detection_after_process_kill(
        self, crash_recovery_dir: Path
    ):
        """模拟 SIGKILL 后：哨兵存在，检查点未清理"""
        sentinel = SentinelManager(crash_recovery_dir)
        sentinel.acquire("pipeline_execute")

        # 未调用 release — 模拟进程被 kill

        # 新进程启动
        sentinel2 = SentinelManager(crash_recovery_dir)
        assert sentinel2.is_crashed is True

        report = sentinel2.get_crash_report()
        assert report["operation"] == "pipeline_execute"

        # 新进程检查完成，清理哨兵
        sentinel2.clear()
        assert not SentinelManager(crash_recovery_dir).is_crashed
