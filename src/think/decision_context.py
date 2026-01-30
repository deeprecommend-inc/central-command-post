"""
Decision Context - Context for decision making
"""
from dataclasses import dataclass, field
from typing import Any, Optional
from ..sense import SystemState, Event


@dataclass
class TaskContext:
    """Context for a specific task"""
    task_id: str
    task_type: str  # "navigate", "scrape", "submit", etc.
    target_url: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    last_error: Optional[str] = None
    last_error_type: Optional[str] = None
    elapsed_time: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def can_retry(self) -> bool:
        """Check if task can be retried"""
        return self.retry_count < self.max_retries

    @property
    def is_first_attempt(self) -> bool:
        """Check if this is the first attempt"""
        return self.retry_count == 0


@dataclass
class DecisionContext:
    """
    Complete context for decision making.

    Aggregates system state, task context, and historical data
    to provide all information needed for strategic decisions.
    """
    system_state: SystemState
    task_context: Optional[TaskContext] = None
    recent_events: list[Event] = field(default_factory=list)
    knowledge: dict[str, Any] = field(default_factory=dict)

    @property
    def success_rate(self) -> float:
        """Current system success rate"""
        return self.system_state.success_rate

    @property
    def is_healthy(self) -> bool:
        """Check if system is in healthy state"""
        return self.success_rate > 0.7

    @property
    def has_recent_errors(self) -> bool:
        """Check if there are recent error events"""
        error_types = {"proxy.failure", "task.failed", "connection.error"}
        return any(e.event_type in error_types for e in self.recent_events[-5:])

    def get_error_frequency(self, window_events: int = 10) -> float:
        """Calculate error frequency in recent events"""
        if not self.recent_events:
            return 0.0
        recent = self.recent_events[-window_events:]
        error_types = {"proxy.failure", "task.failed", "connection.error"}
        errors = sum(1 for e in recent if e.event_type in error_types)
        return errors / len(recent)

    def get_knowledge(self, key: str, default: Any = None) -> Any:
        """Get value from knowledge store"""
        return self.knowledge.get(key, default)

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "system_state": self.system_state.to_dict(),
            "task_context": {
                "task_id": self.task_context.task_id,
                "task_type": self.task_context.task_type,
                "retry_count": self.task_context.retry_count,
                "can_retry": self.task_context.can_retry,
            } if self.task_context else None,
            "success_rate": self.success_rate,
            "is_healthy": self.is_healthy,
            "recent_event_count": len(self.recent_events),
        }
