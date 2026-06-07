"""
持久化层 — 原子写入 + 哨兵文件 + 崩溃恢复
==========================================
设计原则：
- 原子写入：写临时文件 → fsync → 重命名 → fsync 父目录
- 哨兵检测：启动时检查哨兵文件判断上次是否崩溃
- 高内聚：只关心"如何安全读写数据"，不关心数据业务含义
- 低耦合：通过 CapabilityShelfState 纯数据类传递状态
"""

from __future__ import annotations
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timezone

from ai_capability_shelf.models import CapabilityShelfState


# ── 原子文件写入 ──────────────────────────────────────────

class AtomicWriter:
    """
    原子化文件写入器
    保证写操作要么完整完成，要么完全不写
    """

    @staticmethod
    def write_atomic(path: Path, content: str) -> None:
        """原子写入文本内容"""
        path = Path(path).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(f".tmp.{os.getpid()}")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
            # 原子重命名
            os.replace(str(tmp), str(path))
            # fsync 父目录（保证目录元数据落盘）
            fd = os.open(str(path.parent), os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        except BaseException:
            if tmp.exists():
                tmp.unlink(missing_ok=True)
            raise

    @staticmethod
    def write_json_atomic(path: Path, data: Any) -> None:
        """原子写入 JSON 数据"""
        AtomicWriter.write_atomic(
            path, json.dumps(data, ensure_ascii=False, indent=2, default=str)
        )

    @staticmethod
    def read_json(path: Path) -> Optional[Dict[str, Any]]:
        """安全读取 JSON 文件，不存在返回 None"""
        path = Path(path).resolve()
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def read_json_safe(path: Path) -> Optional[Dict[str, Any]]:
        """安全读取 JSON 文件，损坏自动清理并返回 None"""
        path = Path(path).resolve()
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError, OSError):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
            return None

    @staticmethod
    def clean_orphaned_tmp(path: Path, prefix: str = "") -> None:
        """清理孤立的 .tmp 文件（崩溃残留）"""
        path = Path(path).resolve()
        pattern = f"{prefix}{path.suffix}.tmp.*" if prefix else f"{path.name}.tmp.*"
        for p in path.parent.glob(pattern):
            try:
                p.unlink(missing_ok=True)
            except OSError:
                pass

    @staticmethod
    def fsync_dir(path: Path) -> None:
        """原子化 fsync 目录（确保目录元数据落盘）"""
        p = Path(path).resolve()
        p.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(p), os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    @staticmethod
    def write_bytes_atomic(path: Path, data: bytes) -> None:
        """原子写入二进制内容"""
        path = Path(path).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(f".tmp.{os.getpid()}")
        try:
            with open(tmp, "wb") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            os.replace(str(tmp), str(path))
            fd = os.open(str(path.parent), os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        except BaseException:
            if tmp.exists():
                tmp.unlink(missing_ok=True)
            raise


# ── 哨兵文件管理 ──────────────────────────────────────────

class SentinelManager:
    """
    哨兵文件管理器 — 崩溃检测与恢复标记

    哨兵文件是一个空标记文件，在操作开始时创建，完成后删除。
    如果启动时发现哨兵文件存在 → 上次操作被中断 → 需要恢复。
    """

    SENTINEL_NAME = ".shelf_sentinel"

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir).resolve()
        self.sentinel_path = self.data_dir / self.SENTINEL_NAME

    # ── 状态判别 ──

    @property
    def is_crashed(self) -> bool:
        """检查上次操作是否异常中断"""
        return self.sentinel_path.exists()

    @property
    def crash_timestamp(self) -> Optional[str]:
        """获取崩溃时间戳"""
        if not self.is_crashed:
            return None
        try:
            return self.sentinel_path.read_text().strip()
        except (OSError, IOError):
            return "unknown"

    # ── 生命周期操作 ──

    def acquire(self, operation: str = "unknown") -> None:
        """获取哨兵锁（标记操作开始）"""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        AtomicWriter.write_atomic(
            self.sentinel_path,
            json.dumps({
                "operation": operation,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "pid": os.getpid(),
            })
        )

    def release(self) -> None:
        """释放哨兵锁（标记操作安全结束）"""
        try:
            self.sentinel_path.unlink(missing_ok=True)
        except (OSError, IOError):
            pass

    def clear(self) -> None:
        """强制清除哨兵（恢复后清理）"""
        self.release()

    def get_crash_report(self) -> Dict[str, Any]:
        """生成崩溃报告"""
        if not self.is_crashed:
            return {"crashed": False}
        info = {"crashed": True}
        try:
            data = json.loads(self.sentinel_path.read_text())
            info.update(data)
        except (json.JSONDecodeError, OSError):
            pass
        return info

    # ── 检查点读写（项目级崩溃恢复） ──

    def _checkpoint_path(self, project_name: str) -> Path:
        """返回项目检查点文件路径"""
        return self.data_dir / f".lifecycle_{project_name}.checkpoint"

    def write_checkpoint(
        self, project_name: str, step: int, total: int, description: str
    ) -> None:
        """原子写入项目检查点（断电安全）"""
        data = {
            "project": project_name,
            "step": step,
            "total": total,
            "description": description,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        AtomicWriter.write_json_atomic(self._checkpoint_path(project_name), data)

    def read_checkpoint(self, project_name: str) -> Optional[Dict[str, Any]]:
        """读取项目检查点，不存在返回 None"""
        cp = self._checkpoint_path(project_name)
        if not cp.exists():
            return None
        return AtomicWriter.read_json_safe(cp)

    def clear_checkpoint(self, project_name: str) -> None:
        """清除项目检查点及残留临时文件"""
        cp = self._checkpoint_path(project_name)
        # 传文件路径 cp 而非目录 self.data_dir，让 clean_orphaned_tmp 内部
        # 用 path.parent.glob() 在正确目录搜索 .tmp.* 残留
        AtomicWriter.clean_orphaned_tmp(cp)
        if cp.exists():
            cp.unlink(missing_ok=True)
            AtomicWriter.fsync_dir(cp.parent)


# ── 能力货架持久化存储 ────────────────────────────────────

class CapabilityStore:
    """
    能力货架的完整持久化存储

    功能：
    - 将 CapabilityShelfState → JSON 文件（原子写入）
    - 从 JSON 文件 → CapabilityShelfState（崩溃恢复）
    - 哨兵文件检测崩溃
    - 自动备份保护
    """

    STATE_FILENAME = "shelf_state.json"
    BACKUP_DIRNAME = "backups"

    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir).resolve()
        self.state_path = self.data_dir / self.STATE_FILENAME
        self.backup_dir = self.data_dir / self.BACKUP_DIRNAME
        self.sentinel = SentinelManager(self.data_dir)
        self._last_load_meta: Dict[str, Any] = {}  # 最近一次 load 的 meta（含崩溃恢复信息）

    # ── 初始化和目录管理 ──

    def ensure_dirs(self) -> None:
        """确保数据目录存在"""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    # ── 保存（原子写入 + 哨兵保护） ──

    def save(self, state: CapabilityShelfState, operation: str = "save") -> None:
        """
        原子保存货架状态
        写入前创建哨兵，写入完成后删除哨兵

        崩溃安全保证：
        - 写入前备份旧状态（回退保护）
        - 写入后同步备份确保首次保存也有备份副本
        - 任何异常清理哨兵避免阻塞下次启动
        """
        self.ensure_dirs()
        self.sentinel.acquire(operation)
        try:
            # 检查当前是否有旧状态（决定后续是否首次保存需要补备份）
            had_state = self.state_path.exists()

            # 备份旧状态（仅当存在）
            if had_state:
                self._backup_if_exists()

            # 原子写入新状态
            AtomicWriter.write_json_atomic(
                self.state_path, state.model_dump()
            )

            # 首次保存：写入成功后创建初始备份副本
            # 确保崩溃恢复时至少有一个可用备份
            if not had_state:
                self._sync_backup()

            # 完成 — 释放哨兵
            self.sentinel.release()
        except BaseException:
            self.sentinel.clear()  # 崩溃了也要清理，避免阻塞下次启动
            raise

    # ── 加载（含崩溃恢复） ──

    def load(self) -> Tuple[Optional[CapabilityShelfState], Dict[str, Any]]:
        """
        加载货架状态，返回 (state, meta)

        meta 包含崩溃恢复信息。

        加载优先级：
        1. 主文件（shelf_state.json）— 只要有效即返回
        2. 备份文件（backups/）— 主文件不存在或损坏时回退
        3. None — 无任何有效数据

        哨兵存在时，先验证主文件而非直接回退备份，避免 save()
        写主文件成功但未释放哨兵时的误恢复（数据丢失 bug）。
        """
        meta: Dict[str, Any] = {
            "recovered": False,
            "crash_detected": False,
            "crash_info": None,
        }

        crash_detected = self.sentinel.is_crashed
        if crash_detected:
            meta["crash_detected"] = True
            meta["crash_info"] = self.sentinel.get_crash_report()

        # ── 第一阶段：尝试主文件 ──
        state, err = self._try_load_main()
        if state is not None:
            # 主文件有效 — 哨兵是误报（虚惊）
            if crash_detected:
                meta["recovered"] = True
                meta["recovery_source"] = "main_file"
                self.sentinel.clear()
            self._last_load_meta = dict(meta)
            return state, meta

        # ── 第二阶段：主文件不可用，尝试备份 ──
        if crash_detected:
            backup_state = self._restore_from_backup()
            if backup_state is not None:
                meta["recovered"] = True
                meta["recovery_source"] = "backup"
                self.sentinel.clear()
                self._last_load_meta = dict(meta)
                return backup_state, meta
            # 哨兵存在但无备份 → 清理哨兵后返回空状态
            self.sentinel.clear()
            self._last_load_meta = {**meta, "recovery_failed": True}
            return None, {**meta, "recovery_failed": True}

        # ── 第三阶段：无崩溃标记，正常读取主文件 ──
        # （_try_load_main 已尝试过，这里复用结果）
        if err:
            meta["parse_error"] = str(err)
        self._last_load_meta = dict(meta)
        return None, meta

    def _try_load_main(
        self,
    ) -> Tuple[Optional[CapabilityShelfState], Optional[str]]:
        """尝试从主文件加载并校验状态。返回 (state, error_msg)。"""
        try:
            raw = AtomicWriter.read_json(self.state_path)
        except (json.JSONDecodeError, ValueError) as e:
            return None, f"main file corrupted: {e}"
        if raw is None:
            return None, None  # 文件不存在（不是损坏）

        try:
            return CapabilityShelfState(**raw), None
        except (json.JSONDecodeError, ValueError) as e:
            return None, f"main file corrupted: {e}"

    # ── 完整恢复（含哨兵清理） ──

    def recover(self) -> Tuple[Optional[CapabilityShelfState], Dict[str, Any]]:
        """
        完整恢复流程：检测 → 尝试恢复 → 清理哨兵
        返回 (state, recovery_report)
        """
        state, meta = self.load()

        # 如果恢复成功但状态为空 → 返回空货架
        if state is None:
            state = CapabilityShelfState()

        # 确保哨兵已清理
        self.sentinel.clear()

        return state, meta

    # ── 备份与恢复 ──

    def _backup_if_exists(self) -> None:
        """如果当前状态文件存在，备份到备份目录"""
        if not self.state_path.exists():
            return
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        backup_path = self.backup_dir / f"shelf_state_{timestamp}.json"
        shutil.copy2(str(self.state_path), str(backup_path))
        # 清理旧备份（保留最近 20 个）
        self._prune_backups(keep=20)

    def _sync_backup(self) -> None:
        """写入完成后同步备份：将当前主文件复制一份到备份目录"""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        backup_path = self.backup_dir / f"shelf_state_{timestamp}.json"
        shutil.copy2(str(self.state_path), str(backup_path))
        self._prune_backups(keep=20)

    def _restore_from_backup(self) -> Optional[CapabilityShelfState]:
        """从最近的备份恢复"""
        backups = sorted(self.backup_dir.glob("shelf_state_*.json"))
        if not backups:
            return None
        # 用最新的备份
        latest = backups[-1]
        try:
            raw = json.loads(latest.read_text(encoding="utf-8"))
            return CapabilityShelfState(**raw)
        except (json.JSONDecodeError, Exception):
            return None

    def _prune_backups(self, keep: int) -> None:
        """保留最近的 N 个备份"""
        backups = sorted(self.backup_dir.glob("shelf_state_*.json"))
        if len(backups) > keep:
            for old in backups[:-keep]:
                old.unlink(missing_ok=True)

    # ── 工具方法 ──

    @property
    def last_load_meta(self) -> Dict[str, Any]:
        """最近一次 load() 的 meta 信息（崩溃恢复状态）"""
        return dict(self._last_load_meta)

    @property
    def exists(self) -> bool:
        """检查货架数据是否存在"""
        return self.state_path.exists()

    def get_data_size(self) -> int:
        """数据文件大小（字节）"""
        if self.state_path.exists():
            return self.state_path.stat().st_size
        return 0


# ── 审计日志 ──────────────────────────────────────────────

class AuditLogger:
    """
    审计日志 — 每次能力调用的完整记录

    崩溃安全：
    - 追加写 JSON Lines：每次 flush 只追加新行，不覆写已有数据
    - 文件损坏容忍：read_back() 自动跳过 JSON 解析失败的行
    - 写失败不丢数据：OSError 时保留 buffer，下次重试
    - 按日期分文件
    """

    _FLUSH_THRESHOLD = 10

    def __init__(self, log_dir: str | Path):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._buffer: list[Dict[str, Any]] = []

    @staticmethod
    def _today() -> str:
        """当前日期 YYYYMMDD（UTC）"""
        return datetime.now(timezone.utc).strftime("%Y%m%d")

    def log(
        self,
        cap_id: str,
        action: str,
        caller: str = "system",
        status: str = "success",
        detail: Dict[str, Any] | None = None,
    ) -> None:
        """记录审计事件（先 buffer，达阈值后 flush 追加写）"""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "cap_id": cap_id,
            "action": action,
            "caller": caller,
            "status": status,
            "detail": detail or {},
        }
        self._buffer.append(entry)

        if len(self._buffer) >= self._FLUSH_THRESHOLD:
            self.flush()

    def flush(self) -> None:
        """
        追加写 JSON Lines（崩溃安全）

        不再读整个文件→追加→覆写，直接追加新行。
        若写失败（OSError），保留 buffer 下次重试。
        O_APPEND 追加写天然崩溃安全：即使崩溃末尾残缺，read_back() 自动跳过损坏行。
        """
        if not self._buffer:
            return
        log_file = self.log_dir / f"audit_{self._today()}.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)

        lines = [json.dumps(e, ensure_ascii=False) for e in self._buffer]
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                for line in lines:
                    f.write(line + "\n")
                f.flush()
                os.fsync(f.fileno())
            # fsync 父目录
            fd = os.open(str(log_file.parent), os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        except OSError:
            return  # 写失败保留 buffer，下次 flush 重试

        self._buffer.clear()

    def recover(self) -> None:
        """崩溃恢复 — 清理可能残留的临时文件"""
        for p in self.log_dir.glob("audit_*.log.tmp.*"):
            try:
                p.unlink(missing_ok=True)
            except OSError:
                pass

    def read_back(self, date: str = "", limit: int = 100) -> list[Dict[str, Any]]:
        """回读审计日志（按日期）"""
        if not date:
            date = self._today()
        log_file = self.log_dir / f"audit_{date}.log"
        if not log_file.exists():
            return []
        entries: list[Dict[str, Any]] = []
        try:
            raw = log_file.read_text(encoding="utf-8")
            for line in raw.strip().split("\n"):
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue  # 跳过损坏行（崩溃容忍）
                if len(entries) >= limit:
                    break
        except OSError:
            pass
        return entries


# ── 持久化提供方协议 ────────────────────────────────────────────


class PersistenceProvider:
    """
    持久化提供方协议 — Registry/Governance/Runtime 通过此接口
    进行所有持久化操作，实现低耦合。

    DefaultPersistenceProvider 封装 CapabilityStore + AuditLogger + AtomicWriter。
    测试时可注入 InMemoryPersistenceProvider 避免文件 I/O。
    """

    # ── CapabilityShelfState 持久化（含哨兵崩溃恢复） ──

    def save_state(self, state: CapabilityShelfState, operation: str = "save") -> None:
        """原子保存货架状态"""
        raise NotImplementedError

    def load_state(self) -> Tuple[Optional[CapabilityShelfState], Dict[str, Any]]:
        """加载货架状态（含崩溃恢复）"""
        raise NotImplementedError

    # ── 纯文件 I/O（熔断器状态、检查点） ──

    def write_json_atomic(self, path: Path, data: Any) -> None:
        """原子写入 JSON 文件"""
        raise NotImplementedError

    def read_json_safe(self, path: Path) -> Optional[Dict[str, Any]]:
        """安全读取 JSON 文件，损坏返回 None"""
        raise NotImplementedError

    def clean_orphaned_tmp(self, path: Path, prefix: str = "") -> None:
        """清理孤立 .tmp 文件"""
        raise NotImplementedError

    # ── 审计日志 ──

    def log_audit(
        self,
        cap_id: str,
        action: str,
        caller: str = "system",
        status: str = "success",
        detail: Optional[Dict[str, Any]] = None,
    ) -> None:
        """记录审计事件"""
        ...

    def flush_audit(self) -> None:
        """强制刷审计缓冲区"""
        raise NotImplementedError

    def read_audit(self, date: str = "") -> List[Dict[str, Any]]:
        """回读审计日志"""
        raise NotImplementedError


# ── 默认持久化实现 ──────────────────────────────────────────────


class DefaultPersistenceProvider:
    """
    默认持久化实现 — 封装 CapabilityStore + AuditLogger + AtomicWriter

    用法:
        provider = DefaultPersistenceProvider("/path/to/data")
        registry = CapabilityRegistry(state, persistence_provider=provider)
        guard = GovernanceGuard(persistence_provider=provider)
        engine = RuntimeEngine(state, guard, persistence_provider=provider)
    """

    def __init__(
        self,
        data_dir: str | Path,
        log_dir: Optional[str | Path] = None,
    ):
        self._store = CapabilityStore(data_dir)
        self._audit = AuditLogger(log_dir or Path(data_dir) / "audit")

    # ── CapabilityShelfState ──

    def save_state(self, state: CapabilityShelfState, operation: str = "save") -> None:
        self._store.save(state, operation)

    def load_state(self) -> Tuple[Optional[CapabilityShelfState], Dict[str, Any]]:
        return self._store.recover()

    # ── 纯文件 I/O ──

    def write_json_atomic(self, path: Path, data: Any) -> None:
        AtomicWriter.write_json_atomic(path, data)

    def read_json_safe(self, path: Path) -> Optional[Dict[str, Any]]:
        return AtomicWriter.read_json_safe(path)

    def clean_orphaned_tmp(self, path: Path, prefix: str = "") -> None:
        AtomicWriter.clean_orphaned_tmp(path, prefix)

    # ── 审计日志 ──

    def log_audit(
        self,
        cap_id: str,
        action: str,
        caller: str = "system",
        status: str = "success",
        detail: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._audit.log(cap_id, action, caller, status, detail)

    def flush_audit(self) -> None:
        self._audit.flush()

    def read_audit(self, date: str = "") -> List[Dict[str, Any]]:
        return self._audit.read_back(date)
