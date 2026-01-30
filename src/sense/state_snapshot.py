"""
State Snapshot - System state capture
"""
import time
from dataclasses import dataclass, field
from typing import Any, Optional
from datetime import timedelta
from loguru import logger


@dataclass
class SystemState:
    """Snapshot of system state at a point in time"""
    timestamp: float = field(default_factory=time.time)
    proxy_stats: dict[str, Any] = field(default_factory=dict)
    worker_stats: dict[str, Any] = field(default_factory=dict)
    metrics_summary: dict[str, Any] = field(default_factory=dict)
    recent_events: list[dict] = field(default_factory=list)
    active_tasks: int = 0
    error_count: int = 0
    success_count: int = 0

    @property
    def success_rate(self) -> float:
        """Calculate success rate"""
        total = self.success_count + self.error_count
        if total == 0:
            return 1.0
        return self.success_count / total

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "timestamp": self.timestamp,
            "proxy_stats": self.proxy_stats,
            "worker_stats": self.worker_stats,
            "metrics_summary": self.metrics_summary,
            "recent_events": self.recent_events,
            "active_tasks": self.active_tasks,
            "error_count": self.error_count,
            "success_count": self.success_count,
            "success_rate": self.success_rate,
        }


class StateSnapshot:
    """
    Captures and tracks system state over time.

    Example:
        snapshot = StateSnapshot()
        snapshot.update_proxy_stats(proxy_manager.get_stats())
        snapshot.record_success()
        state = snapshot.get_current_state()
    """

    def __init__(
        self,
        event_bus=None,
        metrics_collector=None,
        max_history: int = 100,
    ):
        self._event_bus = event_bus
        self._metrics = metrics_collector
        self._max_history = max_history
        self._history: list[SystemState] = []
        self._current = SystemState()

    def update_proxy_stats(self, stats: dict[str, Any]) -> None:
        """Update proxy statistics"""
        self._current.proxy_stats = stats

    def update_worker_stats(self, stats: dict[str, Any]) -> None:
        """Update worker statistics"""
        self._current.worker_stats = stats

    def set_active_tasks(self, count: int) -> None:
        """Set number of active tasks"""
        self._current.active_tasks = count

    def record_success(self) -> None:
        """Record a successful operation"""
        self._current.success_count += 1

    def record_error(self) -> None:
        """Record an error"""
        self._current.error_count += 1

    def get_current_state(self) -> SystemState:
        """
        Get current system state with all available data.

        Returns:
            SystemState snapshot
        """
        self._current.timestamp = time.time()

        if self._event_bus:
            events = self._event_bus.get_history(limit=10)
            self._current.recent_events = [
                {
                    "type": e.event_type,
                    "source": e.source,
                    "timestamp": e.timestamp,
                }
                for e in events
            ]

        if self._metrics:
            self._current.metrics_summary = self._metrics.get_stats()

        return self._current

    def save_snapshot(self) -> SystemState:
        """
        Save current state to history.

        Returns:
            Saved state
        """
        state = self.get_current_state()
        snapshot = SystemState(
            timestamp=state.timestamp,
            proxy_stats=dict(state.proxy_stats),
            worker_stats=dict(state.worker_stats),
            metrics_summary=dict(state.metrics_summary),
            recent_events=list(state.recent_events),
            active_tasks=state.active_tasks,
            error_count=state.error_count,
            success_count=state.success_count,
        )
        self._history.append(snapshot)

        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        logger.debug(f"Saved state snapshot at {snapshot.timestamp}")
        return snapshot

    def get_history(
        self,
        window: Optional[timedelta] = None,
        limit: int = 10,
    ) -> list[SystemState]:
        """
        Get state history.

        Args:
            window: Optional time window filter
            limit: Maximum snapshots to return
        """
        states = self._history

        if window:
            cutoff = time.time() - window.total_seconds()
            states = [s for s in states if s.timestamp >= cutoff]

        return states[-limit:]

    def get_trend(self, metric: str, window: timedelta) -> Optional[dict]:
        """
        Calculate trend for a metric over time.

        Args:
            metric: Metric name ("success_rate", "error_count", etc.)
            window: Time window

        Returns:
            Trend data with direction and magnitude
        """
        states = self.get_history(window=window)
        if len(states) < 2:
            return None

        values = []
        for state in states:
            if metric == "success_rate":
                values.append(state.success_rate)
            elif metric == "error_count":
                values.append(state.error_count)
            elif metric == "success_count":
                values.append(state.success_count)
            elif metric == "active_tasks":
                values.append(state.active_tasks)
            else:
                return None

        first_half = values[:len(values)//2]
        second_half = values[len(values)//2:]

        avg_first = sum(first_half) / len(first_half) if first_half else 0
        avg_second = sum(second_half) / len(second_half) if second_half else 0

        if avg_first == 0:
            change = 0 if avg_second == 0 else float("inf")
        else:
            change = (avg_second - avg_first) / avg_first

        return {
            "metric": metric,
            "direction": "up" if change > 0.05 else "down" if change < -0.05 else "stable",
            "change_percent": change * 100,
            "first_avg": avg_first,
            "second_avg": avg_second,
            "samples": len(values),
        }

    def reset(self) -> None:
        """Reset current state counters"""
        self._current = SystemState()

    def clear_history(self) -> None:
        """Clear state history"""
        self._history = []
