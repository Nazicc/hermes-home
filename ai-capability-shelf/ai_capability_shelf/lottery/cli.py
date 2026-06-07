"""
lottery.cli — Click 命令组
==========================
五条命令：
  run          自动选择数据源（优先 DB → 回退缓存）
  run-db       强制数据库模式
  run-cache    强制缓存文件模式
  show-config  显示当前配置
  check-data   检查可用数据源

高内聚：每条命令只处理单一职责，不混入计算/提取逻辑。
低耦合：通过 runner/config 公开 API 调用，不直接访问内部数据结构。
崩溃安全：继承 runner 的哨兵 + 检查点机制，断电/重启自动恢复。
"""

from __future__ import annotations

import json
import os
import sys
from typing import Optional

import click

from ai_capability_shelf.lottery.config import (
    has_cache_file,
    has_db_config,
    load_config_from_env,
)
from ai_capability_shelf.lottery.exceptions import LotteryError
from ai_capability_shelf.lottery.models import LotteryResult
from ai_capability_shelf.lottery.runner import (
    resolve_lottery_source,
    run_lottery_from_cache,
    run_lottery_from_db,
)

# ── 共享选项（通过对象复用避免重复定义）─────────────────

_NOTE_ID_OPT = click.option(
    "--note-id", "-n",
    default="",
    metavar="ID",
    help="帖子 ID（覆盖 LOTTERY_NOTE_ID 环境变量）",
)
_TIME_OPT = click.option(
    "--lottery-time", "-t",
    default="",
    metavar="TIME",
    help="抽奖时间（覆盖 LOTTERY_TIME 环境变量）",
)
_EXCLUDE_OPT = click.option(
    "--exclude-user", "-e",
    default="",
    metavar="USER_ID",
    help="排除的 user_id（覆盖 LOTTERY_EXCLUDE_USER_ID 环境变量）",
)
_CACHE_OPT = click.option(
    "--cache-path", "-c",
    default="",
    metavar="PATH",
    help="缓存文件路径（覆盖 LOTTERY_CACHE_PATH 环境变量）",
)
_JSON_OPT = click.option(
    "--json", "output_json",
    is_flag=True,
    help="以 JSON 格式输出结果",
)
_SAVE_OPT = click.option(
    "--save", "-s",
    default="",
    metavar="FILE",
    help="保存结果到文件",
)

# ── 辅助函数 ─────────────────────────────────────────────


def _set_exclude_if_given(exclude_user: str) -> None:
    """如提供了 --exclude-user，注入环境变量以便 runner 通过 load_config_from_env 读取"""
    if exclude_user:
        os.environ["LOTTERY_EXCLUDE_USER_ID"] = exclude_user


def _output_result(
    result: LotteryResult,
    *,
    output_json: bool = False,
    save_path: str = "",
) -> None:
    """统一输出抽奖结果。

    当 --json 或 --save 指定时额外输出结构化格式。
    终端输出始终存在（来自 runner 的 print）—— 此函数仅附加输出。
    """
    if output_json or save_path:
        dump = result.model_dump_json(indent=2)
        if output_json:
            print(dump)
        if save_path:
            _atomic_write(save_path, dump)
            print(f"\n✅ 结果已保存到: {save_path}")


def _atomic_write(path: str, content: str) -> None:
    """原子写入 + fsync"""
    import tempfile

    dirpath = os.path.dirname(path) or "."
    os.makedirs(dirpath, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=dirpath, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        # fsync 父目录
        parent_fd = os.open(dirpath, os.O_RDONLY)
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _config_summary(config) -> str:
    """生成配置摘要文本"""
    lines = [
        "📋 抽奖配置：",
        f"    帖子 ID: {config.note_id}",
        f"    抽奖时间: {config.lottery_time_str}",
    ]
    if config.exclude_user_id:
        lines.append(f"    排除 user_id: {config.exclude_user_id}")
    lines.append(f"    最小评论长度: {config.min_comment_length}")
    lines.append(f"    缓存文件: {config.cache_path}")
    lines.append(f"    数据目录: {config.data_dir}")
    lines.append(f"    数据库: {'已配置' if config.db_host else '未配置'}")
    lines.append(f"    哨兵模式: {'启用' if config.enable_sentinel else '禁用'}")
    lines.append(f"    检查点: {'启用' if config.enable_checkpoint else '禁用'}")
    if config.db_host:
        lines.append(f"    DB 主机: {config.db_host}:{config.db_port}/{config.db_name}")
    return "\n".join(lines)


def _check_sources() -> None:
    """检查数据源状态"""
    # 不需要 note_id/time 的检查，但需要配置加载
    # 这里只做通用检查
    db_configured = bool(os.environ.get("XHS_DB_HOST"))
    cache_default = "/tmp/roleplay_comments_with_uid.json"
    cache_exists = os.path.isfile(cache_default)
    env_cache = os.environ.get("LOTTERY_CACHE_PATH", "")
    env_cache_exists = bool(env_cache) and os.path.isfile(env_cache)

    print("🔍 数据源检查：")
    print(f"    DB 配置: {'✅ 已配置' if db_configured else '❌ 未配置'}")

    specific_cache = ""
    if env_cache and env_cache != cache_default:
        specific_cache = f"   自定义缓存 [{env_cache}]: {'✅ 存在' if env_cache_exists else '❌ 不存在'}"

    print(f"   默认缓存 [{cache_default}]: {'✅ 存在' if cache_exists else '❌ 不存在'}")
    if specific_cache:
        print(specific_cache)
    print(f"   可用模式: ", end="")
    modes = []
    if db_configured:
        modes.append("DB (将优先尝试)")
    if cache_exists or env_cache_exists:
        modes.append("缓存文件 (自动回退)")
    if not modes:
        print("❌ 无可用数据源 — 请配置 XHS_DB_HOST 或准备缓存文件")
    else:
        print(" + ".join(modes))
    print()


# ══════════════════════════════════════════════════════════
#  命令组
# ══════════════════════════════════════════════════════════


@click.group(name="lottery")
def cli() -> None:
    """🎲 崩溃安全抽奖工具

    加权随机抽奖（sqrt(字数) × log₂(条数+1)），
    支持哨兵检测 + 检查点恢复，断电/重启不丢失进度。
    """


# ── 命令 1: run —————————————————————————————————————————


@cli.command()
@_NOTE_ID_OPT
@_TIME_OPT
@_EXCLUDE_OPT
@_JSON_OPT
@_SAVE_OPT
def run(
    note_id: str,
    lottery_time: str,
    exclude_user: str,
    output_json: bool,
    save: str,
) -> None:
    """自动选择数据源执行抽奖（优先 DB → 回退缓存）"""
    try:
        _set_exclude_if_given(exclude_user)
        result = resolve_lottery_source(
            note_id=note_id,
            lottery_time=lottery_time,
        )
        _output_result(result, output_json=output_json, save_path=save)
    except LotteryError as e:
        _handle_error(e)


# ── 命令 2: run-db ——————————————————————————————————————


@cli.command(name="run-db")
@_NOTE_ID_OPT
@_TIME_OPT
@_EXCLUDE_OPT
@_JSON_OPT
@_SAVE_OPT
def run_db(
    note_id: str,
    lottery_time: str,
    exclude_user: str,
    output_json: bool,
    save: str,
) -> None:
    """从数据库提取评论并执行加权抽奖"""
    try:
        _set_exclude_if_given(exclude_user)
        result = run_lottery_from_db(
            note_id=note_id,
            lottery_time=lottery_time,
            exclude_user_id=exclude_user,
        )
        _output_result(result, output_json=output_json, save_path=save)
    except LotteryError as e:
        _handle_error(e)


# ── 命令 3: run-cache ——————————————————————————————————


@cli.command(name="run-cache")
@_NOTE_ID_OPT
@_TIME_OPT
@_EXCLUDE_OPT
@_CACHE_OPT
@_JSON_OPT
@_SAVE_OPT
def run_cache(
    note_id: str,
    lottery_time: str,
    exclude_user: str,
    cache_path: str,
    output_json: bool,
    save: str,
) -> None:
    """从缓存文件提取评论并执行加权抽奖"""
    try:
        _set_exclude_if_given(exclude_user)
        result = run_lottery_from_cache(
            note_id=note_id,
            lottery_time=lottery_time,
            cache_path=cache_path,
            exclude_user_id=exclude_user,
        )
        _output_result(result, output_json=output_json, save_path=save)
    except LotteryError as e:
        _handle_error(e)


# ── 命令 4: show-config ———————————————————————————————─


@cli.command(name="show-config")
@_NOTE_ID_OPT
@_TIME_OPT
@click.option(
    "--show-passwords", is_flag=True, hidden=True,
    help="显示密码（仅调试用）",
)
def show_config(
    note_id: str,
    lottery_time: str,
    show_passwords: bool,
) -> None:
    """显示当前抽奖配置"""
    try:
        config = load_config_from_env(
            note_id=note_id,
            lottery_time=lottery_time,
        )
        summary = _config_summary(config)
        if show_passwords and config.db_password:
            summary += f"\n    DB 密码: {config.db_password}"
        print(summary)
    except LotteryError as e:
        _handle_error(e)


# ── 命令 5: check-data —————————————————————————————───


@cli.command(name="check-data")
def check_data() -> None:
    """检查可用数据源并显示状态"""
    _check_sources()


def _handle_error(e: LotteryError) -> None:  # noqa: E306 — 保持与 CLI 风格一致
    """统一错误处理：以红色输出错误信息并退出。"""
    click.secho(f"\n❌ {e.message}", fg="red", err=True)
    if e.detail:
        click.echo(f"    {e.detail}", err=True)
    sys.exit(1)
