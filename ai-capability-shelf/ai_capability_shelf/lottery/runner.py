"""
lottery.runner — 崩溃安全管线
=============================
哨兵检测 + 检查点恢复 + 分阶段执行。
高内聚：只做"执行编排"。
低耦合：依赖 providers / aggregator / engine，但不关心各阶段内部实现。
"""

from __future__ import annotations

import os
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ai_capability_shelf.lottery.models import (
    Comment,
    LotteryResult,
    WeightTable,
    UserData,
)
from ai_capability_shelf.lottery.config import (
    LotteryConfig,
    load_config_from_env,
    has_db_config,
    has_cache_file,
)
from ai_capability_shelf.lottery.providers import (
    DataProvider,
    DBProvider,
    CacheProvider,
)
from ai_capability_shelf.lottery.aggregator import (
    aggregate_users,
    get_display_names,
    calculate_weights,
    build_weight_table,
    get_duplicate_nicknames,
)
from ai_capability_shelf.lottery.engine import (
    generate_seed,
    WeightedEngine,
    SeedInfo,
)
from ai_capability_shelf.lottery.exceptions import (
    LotteryError,
    NoParticipantsError,
    DataExtractionError,
)

from ai_capability_shelf.persistence import (
    AtomicWriter,
    SentinelManager,
)


# ── 阶段定义 ────────────────────────────────────────────────

PHASE_EXTRACT = "extract"
PHASE_AGGREGATE = "aggregate"
PHASE_WEIGHT = "weight"
PHASE_SEED = "seed"
PHASE_LOTTERY = "lottery"
PHASE_DONE = "done"

PHASES: List[str] = [
    PHASE_EXTRACT,
    PHASE_AGGREGATE,
    PHASE_WEIGHT,
    PHASE_SEED,
    PHASE_LOTTERY,
    PHASE_DONE,
]

PHASE_LABELS: Dict[str, str] = {
    PHASE_EXTRACT: "提取评论数据",
    PHASE_AGGREGATE: "用户聚合（排除帖主+过滤短评论）",
    PHASE_WEIGHT: "计算权重（sqrt(字数)×log₂(条数+1)）",
    PHASE_SEED: "生成随机种子",
    PHASE_LOTTERY: "执行抽奖",
    PHASE_DONE: "完成",
}


# ── 崩溃安全管线 ────────────────────────────────────────────


class LotteryRunner:
    """
    抽奖执行器 — 分阶段执行 + 哨兵检测 + 检查点恢复。

    用法：
        runner = LotteryRunner(config)
        result = runner.run()
    """

    CHECKPOINT_NAME = "lottery"

    def __init__(self, config: LotteryConfig) -> None:
        self.config = config
        self.data_dir = Path(config.data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # 崩溃安全
        self.sentinel = SentinelManager(self.data_dir)

        # 运行期状态（跨阶段传递）
        self.comments: List[Comment] = []
        self.user_data: Dict[str, UserData] = {}
        self.display_names: Dict[str, str] = {}
        self.weights: Dict[str, float] = {}
        self.seed_info: Optional[SeedInfo] = None
        self.weight_table: WeightTable = WeightTable()
        self.winner_uid: str = ""
        self.winner_weight: float = 0.0
        self.winner_probability: float = 0.0
        self.recovered = False

        # 统计
        self.comment_count: int = 0

    # ── 公开入口 ──

    def run(self) -> LotteryResult:
        """完整执行管线"""
        try:
            self._check_recovery()
            self._run_phases()
            return self._build_result()
        finally:
            self.sentinel.release()

    # ── 崩溃恢复 ──

    def _check_recovery(self) -> None:
        """检查哨兵，识别崩溃并恢复检查点"""
        if not self.config.enable_sentinel:
            return

        if self.sentinel.is_crashed:
            report = self.sentinel.get_crash_report()
            self.recovered = True

            if self.config.enable_checkpoint:
                cp = self.sentinel.read_checkpoint(self.CHECKPOINT_NAME)
                if cp:
                    self._restore_from_checkpoint(cp)
                    print(f"⚠️  检测到上次抽奖崩溃，从阶段 [{cp.get('step', 0)}] 恢复")
                else:
                    print("⚠️  检测到上次抽奖崩溃（无检查点，从头开始）")
            else:
                print("⚠️  检测到上次抽奖崩溃（检查点已禁用，从头开始）")

            # 清理旧哨兵
            self.sentinel.clear()

        self.sentinel.acquire("lottery")

    def _restore_from_checkpoint(self, cp: dict) -> None:
        """从检查点恢复中间状态"""
        step = cp.get("step", 0)
        path = self.data_dir / f"lottery_phase_{step}.json"
        data = AtomicWriter.read_json_safe(path)
        if data:
            self._load_phase_data(step, data)

    def _load_phase_data(self, step: int, data: dict) -> None:
        """加载指定阶段的检查点数据"""
        # 各阶段保存了不同的中间数据
        if PHASES[step] == PHASE_AGGREGATE and "comments" in data:
            self.comments = [Comment(**c) for c in data["comments"]]
        if "user_data" in data:
            self.user_data = {
                k: UserData(**v) for k, v in data["user_data"].items()
            }
        if "display_names" in data:
            self.display_names = data["display_names"]
        if "weights" in data:
            self.weights = data["weights"]
        if "weight_table" in data:
            self.weight_table = WeightTable(**data["weight_table"])

    # ── 阶段执行 ──

    def _run_phases(self) -> None:
        """按顺序执行各阶段，每个阶段后写检查点"""
        total = len(PHASES)

        for step, phase in enumerate(PHASES):
            if phase == PHASE_DONE:
                self._write_checkpoint(step, total, phase)
                break

            # 跳过已完成的阶段（崩溃恢复后）
            if self._is_phase_done(step):
                continue

            label = PHASE_LABELS.get(phase, phase)
            print(f"\n[{step + 1}/{total}] {label}...")

            try:
                self._execute_phase(phase)
            except LotteryError:
                raise
            except Exception as e:
                raise LotteryError(
                    detail=f"阶段 [{phase}] 执行异常: {e}",
                )

            self._write_checkpoint(step, total, phase)

    def _is_phase_done(self, step: int) -> bool:
        """检查该阶段是否已通过崩溃恢复完成"""
        if not self.recovered or not self.config.enable_checkpoint:
            return False
        try:
            cp = self.sentinel.read_checkpoint(self.CHECKPOINT_NAME)
            return cp is not None and cp.get("step", 0) > step
        except Exception:
            return False

    def _execute_phase(self, phase: str) -> None:
        """执行单个阶段"""
        if phase == PHASE_EXTRACT:
            self._do_extract()
        elif phase == PHASE_AGGREGATE:
            self._do_aggregate()
        elif phase == PHASE_WEIGHT:
            self._do_weight()
        elif phase == PHASE_SEED:
            self._do_seed()
        elif phase == PHASE_LOTTERY:
            self._do_lottery()

    # ── 各阶段实现 ──

    def _do_extract(self) -> None:
        """提取评论数据"""
        provider: DataProvider
        if has_db_config(self.config):
            provider = DBProvider(
                note_id=self.config.note_id,
                host=self.config.db_host,
                port=self.config.db_port,
                dbname=self.config.db_name,
                user=self.config.db_user,
                password=self.config.db_password,
                connect_timeout=self.config.db_connect_timeout,
            )
        else:
            if not has_cache_file(self.config):
                raise DataExtractionError(
                    detail="无可用数据源：既未配置数据库连接，缓存文件也不存在",
                    context={"cache_path": self.config.cache_path},
                )
            provider = CacheProvider(path=self.config.cache_path)

        self.comments = provider.extract_comments()
        self.comment_count = len(self.comments)
        print(f"      来源: {provider.source_label()}")
        print(f"      共 {self.comment_count} 条评论")

        # 保存阶段性结果
        self._save_phase_data(PHASE_EXTRACT)

    def _do_aggregate(self) -> None:
        """用户聚合"""
        self.user_data = aggregate_users(
            self.comments,
            exclude_user_id=self.config.exclude_user_id or "",
            min_comment_length=self.config.min_comment_length,
        )
        self.display_names = get_display_names(self.user_data)

        total_comments = sum(d.count for d in self.user_data.values())
        duplicates = get_duplicate_nicknames(self.user_data)

        print(f"      合格参与者: {len(self.user_data)} 人")
        print(f"      有效评论: {total_comments} 条")
        if duplicates:
            total_dup = sum(duplicates.values())
            print(f"      同昵称用户: {total_dup} 人涉及 {len(duplicates)} 个昵称")
            mum = duplicates.get("momo", 0)
            if mum > 0:
                print(f"      其中 'momo' 有 {mum} 位不同用户")

        # 释放 comments（不再需要，减少内存）
        self._save_phase_data(PHASE_AGGREGATE)

    def _do_weight(self) -> None:
        """权重计算"""
        self.weights = calculate_weights(self.user_data)
        self.weight_table = build_weight_table(
            self.weights, self.user_data, self.display_names
        )

        # 打印 Top 20
        print(f"\n      权重 Top 20:")
        print(f"      {'排名':<4} {'用户':<28} {'评论数':<6} {'总字数':<7} {'概率'}")
        print(f"      {'─' * 65}")
        for i, entry in enumerate(self.weight_table.sorted_by_weight_desc()[:20], 1):
            print(
                f"      {i:<4} {entry.display_name:<28} "
                f"{entry.comment_count:<6} {entry.total_length:<7} "
                f"{entry.probability_percent:.3f}%"
            )

        self._save_phase_data(PHASE_WEIGHT)

    def _do_seed(self) -> None:
        """种子生成"""
        self.seed_info = generate_seed(
            self.config.lottery_time_str,
            note_id=self.config.note_id,
        )
        print(f"      抽奖时间: {self.config.lottery_time_str}")
        print(f"      种子字符串: {self.seed_info.seed_str}")
        print(f"      SHA-256: {self.seed_info.seed_hash}")
        print(f"      种子数值: {self.seed_info.seed_int}")

    def _do_lottery(self) -> None:
        """执行抽奖"""
        engine = WeightedEngine(self.weights, self.seed_info.seed_int)
        self.winner_uid, self.winner_weight, self.winner_probability = (
            engine.pick_with_details()
        )

        winner_data = self.user_data.get(self.winner_uid, UserData())
        winner_name = self.display_names.get(self.winner_uid, winner_data.nickname)
        winner_comments = winner_data.comments

        print(f"\n{'=' * 60}")
        print(f"  🎉 中奖用户: 【{winner_name}】")
        print(f"{'=' * 60}")
        print(f"  user_id: {self.winner_uid}")
        print(f"  昵称: {winner_data.nickname}")
        print(f"  评论数: {winner_data.count} 条")
        print(f"  总字数: {winner_data.total_length} 字")
        print(f"  权重: {self.winner_weight:.2f}")
        print(f"  中奖概率: {self.winner_probability:.3f}%\n")
        print(f"  该用户的评论:")
        for i, comment in enumerate(winner_comments, 1):
            truncated = comment[:120] + ("..." if len(comment) > 120 else "")
            print(f"  {i}. {truncated}")

    # ── 检查点管理 ──

    def _write_checkpoint(self, step: int, total: int, phase: str) -> None:
        """原子写入检查点"""
        if not self.config.enable_checkpoint:
            return
        self.sentinel.write_checkpoint(
            self.CHECKPOINT_NAME,
            step=step,
            total=total,
            description=PHASE_LABELS.get(phase, phase),
        )

    def _save_phase_data(self, phase: str) -> None:
        """保存阶段中间数据到文件（崩溃恢复用）"""
        if not self.config.enable_checkpoint:
            return
        step = PHASES.index(phase)
        path = self.data_dir / f"lottery_phase_{step}.json"
        data: dict = {
            "phase": phase,
            "step": step,
        }
        if self.comments:
            data["comments"] = [
                c.model_dump() for c in self.comments
            ]
        if self.user_data:
            data["user_data"] = {
                k: v.model_dump() for k, v in self.user_data.items()
            }
        if self.display_names:
            data["display_names"] = self.display_names
        if self.weights:
            data["weights"] = self.weights
        if self.weight_table.entries:
            data["weight_table"] = self.weight_table.model_dump()
        AtomicWriter.write_json_atomic(path, data)

    def _build_result(self) -> LotteryResult:
        """构建最终输出"""
        winner_data = self.user_data.get(self.winner_uid, UserData())
        seed = self.seed_info  # 始终非 None（仅到 lottery 阶段后才调用）

        return LotteryResult(
            lottery_time=self.config.lottery_time_str,
            note_id=self.config.note_id,
            seed_str=seed.seed_str if seed else "",
            seed_hash=seed.seed_hash if seed else "",
            seed_int=seed.seed_int if seed else 0,
            total_comments=self.comment_count,
            total_participants=len(self.user_data),
            weight_table=self.weight_table,
            winner_user_id=self.winner_uid,
            winner_display_name=self.display_names.get(
                self.winner_uid, winner_data.nickname
            ),
            winner_weight=self.winner_weight,
            winner_probability=self.winner_probability,
            winner_comments=winner_data.comments,
            data_source="db" if has_db_config(self.config) else "cache",
            recovered_from_crash=self.recovered,
        )


# ── 便捷函数 ────────────────────────────────────────────────


def run_lottery_from_db(
    note_id: str,
    lottery_time: str,
    *,
    exclude_user_id: str = "",
) -> LotteryResult:
    """从数据库提取评论并执行抽奖"""
    config = load_config_from_env(note_id=note_id, lottery_time=lottery_time)
    if exclude_user_id:
        config.exclude_user_id = exclude_user_id
    runner = LotteryRunner(config)
    return runner.run()


def run_lottery_from_cache(
    note_id: str,
    lottery_time: str,
    cache_path: str = "",
    *,
    exclude_user_id: str = "",
) -> LotteryResult:
    """从缓存文件提取评论并执行抽奖"""
    config = load_config_from_env(
        note_id=note_id,
        lottery_time=lottery_time,
        override_cache_path=cache_path or None,
    )
    if exclude_user_id:
        config.exclude_user_id = exclude_user_id
    runner = LotteryRunner(config)
    return runner.run()


def resolve_lottery_source(
    note_id: str,
    lottery_time: str,
) -> LotteryResult:
    """
    智能选择数据源：优先 DB，DB 不可用时自动回退缓存文件。
    """
    config = load_config_from_env(note_id=note_id, lottery_time=lottery_time)

    has_db = has_db_config(config)
    has_cache = has_cache_file(config)

    if not has_db and not has_cache:
        raise DataExtractionError(
            detail="无可用数据源：既未配置数据库连接，缓存文件也不存在",
            context={
                "db_host_set": bool(config.db_host),
                "cache_exists": has_cache,
                "cache_path": config.cache_path,
            },
        )

    if has_db:
        try:
            provider = DBProvider(
                note_id=config.note_id,
                host=config.db_host,
                port=config.db_port,
                dbname=config.db_name,
                user=config.db_user,
                password=config.db_password,
                connect_timeout=config.db_connect_timeout,
            )
            provider.extract_comments()
            print("✅  DB 连接成功，使用数据库数据源")
        except Exception as e:
            if has_cache:
                print(f"⚠️  DB 连接失败 ({e})，回退到缓存文件")
                config.cache_path = ""
                config.db_host = ""
            else:
                raise DataExtractionError(
                    detail=f"DB 连接失败且无缓存文件可回退: {e}",
                )

    runner = LotteryRunner(config)
    return runner.run()
