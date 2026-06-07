"""
lottery — 崩溃安全抽奖组件
==========================

基于加权随机抽奖算法（sqrt(总字数) × log₂(评论条数+1)）。
支持 DB 直连与缓存文件两种数据源，原子写入 + 哨兵检测保障断电安全。

模块结构（高内聚低耦合）:
  models.py      纯数据模型（Pydantic）
  exceptions.py  lottery 专属异常层次
  config.py      环境变量配置
  providers.py   数据源抽象（ABC）+ DBProvider + CacheProvider
  aggregator.py  用户聚合 + 权重公式
  engine.py      种子生成 + 加权执行
  runner.py      崩溃安全管线（哨兵+检查点+阶段恢复）
  cli.py         Click 命令组

公开 API:
  run_lottery_from_db(), run_lottery_from_cache(), calculate_weights()
"""

from ai_capability_shelf.lottery.models import (
    Comment,
    UserData,
    WeightTable,
    WeightEntry,
    LotteryResult,
    LotteryConfig,
)
from ai_capability_shelf.lottery.exceptions import (
    LotteryError,
    DataExtractionError,
    WeightComputationError,
    SeedGenerationError,
    LotteryEngineError,
)
from ai_capability_shelf.lottery.engine import (
    WeightedEngine,
    generate_seed,
    calculate_weights,
    run_weighted_lottery,
)
from ai_capability_shelf.lottery.runner import (
    LotteryRunner,
    run_lottery_from_db,
    run_lottery_from_cache,
    resolve_lottery_source,
)
# CLI 命令组（集成到主 cli.py 使用）
from ai_capability_shelf.lottery.cli import cli as lottery_cli_group

__all__ = [
    # models
    "Comment", "UserData", "WeightTable", "WeightEntry",
    "LotteryResult", "LotteryConfig",
    # exceptions
    "LotteryError", "DataExtractionError",
    "WeightComputationError", "SeedGenerationError", "LotteryEngineError",
    # engine
    "WeightedEngine", "generate_seed", "calculate_weights", "run_weighted_lottery",
    # runner
    "LotteryRunner", "run_lottery_from_db", "run_lottery_from_cache",
    "resolve_lottery_source",
    # CLI
    "lottery_cli_group",
]
