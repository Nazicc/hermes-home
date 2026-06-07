"""
lottery.config — 环境变量配置
=============================
将环境变量解析为 LotteryConfig，提供统一配置入口。
高内聚：只处理环境变量 → 配置对象。
低耦合：仅依赖 models.LotteryConfig。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from ai_capability_shelf.lottery.models import LotteryConfig
from ai_capability_shelf.lottery.exceptions import ConfigError

# 默认值常量
DEFAULT_CACHE_PATH = "/tmp/roleplay_comments_with_uid.json"
DEFAULT_DATA_DIR = str(Path.home() / ".hermes" / "lottery-data")
DEFAULT_MIN_COMMENT_LENGTH = 5
DEFAULT_DB_PORT = 5432
DEFAULT_DB_NAME = "xhs"
DEFAULT_DB_TIMEOUT = 10


def load_config_from_env(
    note_id: str = "",
    lottery_time: str = "",
    *,
    override_cache_path: Optional[str] = None,
    override_data_dir: Optional[str] = None,
) -> LotteryConfig:
    """
    从环境变量加载配置。

    环境变量:
      LOTTERY_NOTE_ID         帖子 ID
      LOTTERY_TIME            抽奖时间字符串
      LOTTERY_EXCLUDE_USER_ID 排除的 user_id
      LOTTERY_CACHE_PATH      缓存文件路径
      LOTTERY_DATA_DIR        数据目录（崩溃安全用）
      XHS_DB_HOST             数据库主机
      XHS_DB_PORT             数据库端口
      XHS_DB_NAME             数据库名
      XHS_DB_USER             数据库用户
      XHS_DB_PASSWORD         数据库密码

    参数可覆盖环境变量。
    """
    note_id_actual = note_id or os.environ.get("LOTTERY_NOTE_ID", "")
    time_actual = lottery_time or os.environ.get("LOTTERY_TIME", "")

    if not note_id_actual:
        raise ConfigError(
            "缺少帖子 ID",
            detail="请设置 LOTTERY_NOTE_ID 环境变量或传入 note_id 参数",
        )
    if not time_actual:
        raise ConfigError(
            "缺少抽奖时间",
            detail="请设置 LOTTERY_TIME 环境变量或传入 lottery_time 参数",
        )

    config = LotteryConfig(
        note_id=note_id_actual,
        lottery_time_str=time_actual,
        exclude_user_id=os.environ.get(
            "LOTTERY_EXCLUDE_USER_ID",
        ),
        min_comment_length=int(
            os.environ.get("LOTTERY_MIN_LENGTH", str(DEFAULT_MIN_COMMENT_LENGTH))
        ),
        cache_path=(
            override_cache_path
            or os.environ.get("LOTTERY_CACHE_PATH", DEFAULT_CACHE_PATH)
        ),
        data_dir=(
            override_data_dir
            or os.environ.get("LOTTERY_DATA_DIR", DEFAULT_DATA_DIR)
        ),
        db_host=os.environ.get("XHS_DB_HOST", ""),
        db_port=int(os.environ.get("XHS_DB_PORT", str(DEFAULT_DB_PORT))),
        db_name=os.environ.get("XHS_DB_NAME", DEFAULT_DB_NAME),
        db_user=os.environ.get("XHS_DB_USER", ""),
        db_password=os.environ.get("XHS_DB_PASSWORD", ""),
        db_connect_timeout=int(
            os.environ.get("XHS_DB_CONNECT_TIMEOUT", str(DEFAULT_DB_TIMEOUT))
        ),
        enable_sentinel=os.environ.get("LOTTERY_SENTINEL", "1") != "0",
        enable_checkpoint=os.environ.get("LOTTERY_CHECKPOINT", "1") != "0",
    )

    return config


def has_db_config(config: LotteryConfig) -> bool:
    """检查是否有足够的 DB 连接配置"""
    return bool(config.db_host and config.db_user)


def has_cache_file(config: LotteryConfig) -> bool:
    """检查缓存文件是否存在"""
    return bool(config.cache_path and os.path.isfile(config.cache_path))
