"""
reliability.monitoring — Monitor 观测与监控
============================================
职责（对应"观测溯源"保障维度）：
  1. 全链路日志（agent_rules 第9条：强制埋点）
  2. 多维度监控指标收集
  3. 分级告警规则引擎
  4. 现场快照

设计原则：
  - 日志：结构化的 JSON Lines 追加写（崩溃安全）
  - 指标：时间序列的 RollingWindow
  - 告警：规则引擎模式（条件 → 动作）
  - 快照：原子写入 + 哨兵保护
"""

from __future__ import annotations

import json
import time
import os
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import defaultdict, deque
from dataclasses import dataclass, field

from ai_capability_shelf.persistence import AtomicWriter, SentinelManager
from ai_capability_shelf.reliability.models import (
    MonitorMetrics,
    AlertRule,
    AlertLevel,
    MetricType,
    AccessLog,
)
from ai_capability_shelf.reliability.exceptions import MonitorError


# ════════════════════════════════════════════════════════════
# 内部辅助：滑动窗口指标
# ════════════════════════════════════════════════════════════

@dataclass
class RollingMetric:
    """滑动窗口指标（线程安全无锁）"""
    values: deque = field(default_factory=lambda: deque(maxlen=10000))
    min_window_s: float = 60.0

    def add(self, value: float, now: Optional[float] = None) -> None:
        now = now or time.monotonic()
        self.values.append((now, value))

    def sum(self, window_s: float = 60.0) -> float:
        cutoff = time.monotonic() - window_s
        return sum(v for t, v in self.values if t >= cutoff)

    def count(self, window_s: float = 60.0) -> int:
        cutoff = time.monotonic() - window_s
        return sum(1 for t, _ in self.values if t >= cutoff)

    def avg(self, window_s: float = 60.0) -> float:
        c = self.count(window_s)
        return self.sum(window_s) / c if c > 0 else 0.0

    def max(self, window_s: float = 60.0) -> float:
        cutoff = time.monotonic() - window_s
        vals = [v for t, v in self.values if t >= cutoff]
        return max(vals) if vals else 0.0

    def pct(self, percentile: float, window_s: float = 60.0) -> float:
        cutoff = time.monotonic() - window_s
        vals = sorted(v for t, v in self.values if t >= cutoff)
        if not vals:
            return 0.0
        idx = int(len(vals) * percentile / 100.0)
        return vals[min(idx, len(vals) - 1)]


class Monitor:
    """
    全链路观测监控

    能力：
    - 全链路结构化日志（JSON Lines，按天分文件）
    - 多维度指标（延迟、成功率、QPS、Token消耗）
    - 分级告警规则引擎
    - 现场快照（崩溃安全持久化）

    使用方式：
      mon = Monitor(log_dir=Path("/tmp/logs"), metric_dir=Path("/tmp/metrics"))
      mon.log_access(...)            # 全链路日志
      mon.record_tool_metrics(...)   # 工具指标
      mon.check_alerts()             # 告警检查
      mon.save_snapshot(...)         # 现场快照
    """

    def __init__(
        self,
        log_dir: Optional[Path] = None,
        metric_dir: Optional[Path] = None,
        snapshot_dir: Optional[Path] = None,
    ) -> None:
        self._log_dir = log_dir
        self._metric_dir = metric_dir
        self._snapshot_dir = snapshot_dir

        # 指标收集
        self._latency: RollingMetric = RollingMetric()
        self._token_usage: RollingMetric = RollingMetric()
        self._round_trip_count: int = 0

        # 工具级指标
        self._tool_metrics: Dict[str, Dict[str, RollingMetric]] = defaultdict(
            lambda: defaultdict(RollingMetric)
        )

        # 告警规则
        self._alert_rules: Dict[str, AlertRule] = {}
        self._alert_history: deque = deque(maxlen=500)

        # 日志缓冲区（批量 flush）
        self._log_buffer: List[Dict[str, Any]] = []
        self._flush_threshold = 10

        # 哨兵
        self._sentinel: Optional[SentinelManager] = None
        if snapshot_dir:
            self._sentinel = SentinelManager(snapshot_dir)

    # ════════════════════════════════════════════════════════════
    # 全链路日志（agent_rules 第9条）
    # ════════════════════════════════════════════════════════════

    def log_access(
        self,
        access: AccessLog,
    ) -> None:
        """
        日志接入请求（全链路强制埋点）

        格式：JSON Lines，按日期分文件
        崩溃安全：追加写 + buffer 容错
        """
        entry = {
            "type": "access",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": access.model_dump(),
        }

        self._log_buffer.append(entry)
        self._round_trip_count += 1

        if len(self._log_buffer) >= self._flush_threshold:
            self.flush_logs()

    def log_event(
        self,
        event_type: str,
        event_name: str,
        detail: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        记录任意事件（告警、故障、降级等）

        Args:
            event_type: 事件类型（alert / degrade / retry / error）
            event_name: 事件名称
            detail: 事件详情
        """
        entry = {
            "type": event_type,
            "event": event_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "detail": detail or {},
        }
        self._log_buffer.append(entry)

        if len(self._log_buffer) >= self._flush_threshold:
            self.flush_logs()

    def flush_logs(self) -> None:
        """强制刷日志到磁盘"""
        if not self._log_buffer or not self._log_dir:
            return

        log_path = self._get_log_path()

        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(log_path, "a", encoding="utf-8") as f:
                for entry in self._log_buffer:
                    f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
                    f.flush()
                os.fsync(f.fileno())
            self._log_buffer.clear()
        except (OSError, IOError) as e:
            # 写失败不丢数据 — buffer 保留，下次重试
            raise MonitorError(
                message=f"日志写入失败: {e}",
                context={"buffer_size": len(self._log_buffer)},
            )

    def _get_log_path(self) -> Path:
        """获取当天日志文件路径"""
        assert self._log_dir is not None
        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        return self._log_dir / f"reliability_{today}.jsonl"

    def read_logs(
        self,
        date_str: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        读取日志（自动跳过损坏行）

        Args:
            date_str: 日期 YYYYMMDD，默认今天
            limit: 最大行数
            offset: 跳过行数

        Returns:
            日志条目列表
        """
        if not self._log_dir:
            return []

        date = date_str or datetime.now(timezone.utc).strftime("%Y%m%d")
        log_path = self._log_dir / f"reliability_{date}.jsonl"

        if not log_path.exists():
            return []

        entries: List[Dict[str, Any]] = []
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                for i, line in enumerate(f):
                    if i < offset:
                        continue
                    if len(entries) >= limit:
                        break
                    try:
                        entries.append(json.loads(line))
                    except (json.JSONDecodeError, ValueError):
                        continue  # 跳过损坏行
        except OSError:
            pass

        return entries

    # ════════════════════════════════════════════════════════════
    # 指标收集
    # ════════════════════════════════════════════════════════════

    def record_latency(self, ms: float) -> None:
        """记录延迟（毫秒）"""
        self._latency.add(ms)

    def record_token_usage(self, tokens: int) -> None:
        """记录Token消耗"""
        self._token_usage.add(float(tokens))

    def record_tool_metrics(
        self,
        tool_name: str,
        success: bool,
        latency_ms: float,
        token_count: int = 0,
    ) -> None:
        """
        记录工具级指标

        收集：
        - 调用次数
        - 成功率
        - 延迟
        - Token消耗
        """
        self._tool_metrics[tool_name]["count"].add(1.0)
        self._tool_metrics[tool_name]["latency"].add(latency_ms)
        self._tool_metrics[tool_name]["error"].add(0.0 if success else 1.0)
        if token_count > 0:
            self._tool_metrics[tool_name]["tokens"].add(float(token_count))
            self.record_token_usage(token_count)

        self.record_latency(latency_ms)

    def get_metrics(self) -> MonitorMetrics:
        """
        获取当前监控指标快照

        Returns:
            MonitorMetrics 对象
        """
        tool_stats: Dict[str, Dict[str, Any]] = {}
        for tool_name, metrics in self._tool_metrics.items():
            total = metrics["count"].count()
            errors = int(metrics["error"].sum())
            tool_stats[tool_name] = {
                "total_calls": total,
                "errors": errors,
                "success_rate": 1.0 - (errors / total) if total > 0 else 1.0,
                "avg_latency_ms": metrics["latency"].avg(),
                "p99_latency_ms": metrics["latency"].pct(99),
                "avg_tokens": metrics["tokens"].avg() if "tokens" in metrics else 0,
            }

        return MonitorMetrics(
            total_requests=self._round_trip_count,
            avg_latency_ms=self._latency.avg(),
            p99_latency_ms=self._latency.pct(99),
            max_latency_ms=self._latency.max(),
            total_token_usage=int(self._token_usage.sum()),
            success_rate=self._calc_success_rate(),
            tool_stats=tool_stats,
        )

    def _calc_success_rate(self) -> float:
        """计算总体成功率"""
        total = 0
        errors = 0
        for metrics in self._tool_metrics.values():
            total += int(metrics["count"].count())
            errors += int(metrics["error"].sum())
        return 1.0 - (errors / total) if total > 0 else 1.0

    def persist_metrics(self) -> None:
        """持久化指标快照（崩溃安全）"""
        if not self._metric_dir:
            return

        metrics = self.get_metrics()
        snapshot_path = self._metric_dir / ".metrics_snapshot.json"
        AtomicWriter.write_json_atomic(snapshot_path, metrics.model_dump())

    # ════════════════════════════════════════════════════════════
    # 告警规则引擎
    # ════════════════════════════════════════════════════════════

    def add_alert_rule(self, rule: AlertRule) -> None:
        """注册告警规则"""
        self._alert_rules[rule.name] = rule

    def remove_alert_rule(self, name: str) -> None:
        """移除告警规则"""
        self._alert_rules.pop(name, None)

    def get_alert_rules(self) -> Dict[str, AlertRule]:
        """获取所有告警规则"""
        return dict(self._alert_rules)

    def check_alerts(self) -> List[Dict[str, Any]]:
        """
        检查所有告警规则

        Returns:
            触发的告警列表
        """
        triggered: List[Dict[str, Any]] = []
        metrics = self.get_metrics()

        for rule in self._alert_rules.values():
            if not rule.enabled:
                continue

            # 计算当前值
            current_value = self._evaluate_rule_condition(rule, metrics)
            if current_value is None:
                continue

            # 检查阈值
            if rule.condition == "gt" and current_value > rule.threshold:
                alert = self._fire_alert(rule, current_value)
                triggered.append(alert)
            elif rule.condition == "lt" and current_value < rule.threshold:
                alert = self._fire_alert(rule, current_value)
                triggered.append(alert)
            elif rule.condition == "gte" and current_value >= rule.threshold:
                alert = self._fire_alert(rule, current_value)
                triggered.append(alert)
            elif rule.condition == "lte" and current_value <= rule.threshold:
                alert = self._fire_alert(rule, current_value)
                triggered.append(alert)

        return triggered

    def _evaluate_rule_condition(
        self,
        rule: AlertRule,
        metrics: MonitorMetrics,
    ) -> Optional[float]:
        """评估规则条件，返回当前值"""
        if rule.metric == MetricType.LATENCY_P99:
            return metrics.p99_latency_ms
        elif rule.metric == MetricType.LATENCY_AVG:
            return metrics.avg_latency_ms
        elif rule.metric == MetricType.ERROR_RATE:
            return (1.0 - metrics.success_rate) * 100  # 百分比
        elif rule.metric == MetricType.TOKEN_USAGE:
            return float(metrics.total_token_usage)
        elif rule.metric == MetricType.REQUEST_COUNT:
            return float(metrics.total_requests)
        elif rule.metric == MetricType.SUCCESS_RATE:
            return metrics.success_rate * 100
        return None

    def _fire_alert(
        self,
        rule: AlertRule,
        current_value: float,
    ) -> Dict[str, Any]:
        """触发告警"""
        now = datetime.now(timezone.utc).isoformat()
        alert = {
            "rule_name": rule.name,
            "level": rule.level.value,
            "metric": rule.metric.value,
            "threshold": rule.threshold,
            "current_value": round(current_value, 2),
            "condition": rule.condition,
            "message": rule.message_template.format(
                name=rule.name,
                current=round(current_value, 2),
                threshold=rule.threshold,
            ),
            "triggered_at": now,
            "actions": rule.actions,
        }

        self._alert_history.append(alert)
        self.log_event("alert", rule.name, alert)

        return alert

    def get_alert_history(
        self,
        limit: int = 20,
        min_level: Optional[AlertLevel] = None,
    ) -> List[Dict[str, Any]]:
        """获取告警历史"""
        history = list(self._alert_history)
        if min_level:
            level_rank = {AlertLevel.DEBUG: 0, AlertLevel.INFO: 1,
                          AlertLevel.WARN: 2, AlertLevel.ERROR: 3,
                          AlertLevel.CRITICAL: 4}
            min_rank = level_rank.get(min_level, 0)
            history = [
                a for a in history
                if level_rank.get(AlertLevel(a.get("level", "info")), 0) >= min_rank
            ]
        return history[-limit:]

    # ════════════════════════════════════════════════════════════
    # 现场快照
    # ════════════════════════════════════════════════════════════

    def save_snapshot(
        self,
        name: str,
        data: Dict[str, Any],
    ) -> None:
        """
        保存现场快照（崩溃安全）

        用于故障时刻的状态保存。

        Args:
            name: 快照名称（如 "circuit_breaker_tool_x"）
            data: 快照数据
        """
        if not self._snapshot_dir or not self._sentinel:
            return

        snapshot_path = self._snapshot_dir / f"snapshot_{name}.json"
        self._sentinel.acquire("snapshot")
        try:
            snapshot = {
                "name": name,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "metrics_snapshot": self.get_metrics().model_dump(),
                "data": data,
            }
            AtomicWriter.write_json_atomic(snapshot_path, snapshot)
        finally:
            self._sentinel.release()

    def load_snapshot(self, name: str) -> Optional[Dict[str, Any]]:
        """加载现场快照"""
        if not self._snapshot_dir:
            return None
        snapshot_path = self._snapshot_dir / f"snapshot_{name}.json"
        return AtomicWriter.read_json_safe(snapshot_path)

    def list_snapshots(self) -> List[str]:
        """列出所有快照"""
        if not self._snapshot_dir:
            return []
        return sorted(
            p.stem.replace("snapshot_", "")
            for p in self._snapshot_dir.glob("snapshot_*.json")
        )

    # ════════════════════════════════════════════════════════════
    # 资源清理
    # ════════════════════════════════════════════════════════════

    def cleanup_old_logs(self, days: int = 30) -> int:
        """清理超过 N 天的日志"""
        if not self._log_dir:
            return 0
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        removed = 0
        for p in self._log_dir.glob("reliability_*.jsonl"):
            try:
                # 文件名包含日期 YYYYMMDD
                date_part = p.stem.replace("reliability_", "")
                file_date = datetime.strptime(date_part, "%Y%m%d").replace(
                    tzinfo=timezone.utc
                )
                if file_date < cutoff:
                    p.unlink()
                    removed += 1
            except (ValueError, OSError):
                pass
        return removed

    def reset(self) -> None:
        """重置所有运行时监控状态"""
        self._latency = RollingMetric()
        self._token_usage = RollingMetric()
        self._round_trip_count = 0
        self._tool_metrics.clear()
        self._alert_history.clear()
        self._log_buffer.clear()
