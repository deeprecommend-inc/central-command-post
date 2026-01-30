"""
State Machine - Task state management
"""
import time
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Callable
from loguru import logger


class TaskState(Enum):
    """Task execution states"""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class StateTransition:
    """Record of a state transition"""
    from_state: TaskState
    to_state: TaskState
    timestamp: float = field(default_factory=time.time)
    reason: str = ""
    metadata: dict = field(default_factory=dict)


class StateMachine:
    """
    Manages task state transitions.

    Valid transitions:
        PENDING -> RUNNING
        RUNNING -> PAUSED, COMPLETED, FAILED, CANCELLED
        PAUSED -> RUNNING, CANCELLED
        COMPLETED (terminal)
        FAILED (terminal)
        CANCELLED (terminal)

    Example:
        sm = StateMachine("task_1")
        sm.transition_to(TaskState.RUNNING)
        sm.transition_to(TaskState.COMPLETED, reason="Success")
    """

    VALID_TRANSITIONS = {
        TaskState.PENDING: {TaskState.RUNNING, TaskState.CANCELLED},
        TaskState.RUNNING: {
            TaskState.PAUSED,
            TaskState.COMPLETED,
            TaskState.FAILED,
            TaskState.CANCELLED,
        },
        TaskState.PAUSED: {TaskState.RUNNING, TaskState.CANCELLED},
        TaskState.COMPLETED: set(),
        TaskState.FAILED: set(),
        TaskState.CANCELLED: set(),
    }

    def __init__(
        self,
        task_id: str,
        initial_state: TaskState = TaskState.PENDING,
        on_transition: Optional[Callable[[StateTransition], None]] = None,
    ):
        self.task_id = task_id
        self._state = initial_state
        self._history: list[StateTransition] = []
        self._on_transition = on_transition
        self._created_at = time.time()
        self._updated_at = self._created_at

    @property
    def state(self) -> TaskState:
        """Current state"""
        return self._state

    @property
    def is_terminal(self) -> bool:
        """Check if in terminal state"""
        return self._state in {
            TaskState.COMPLETED,
            TaskState.FAILED,
            TaskState.CANCELLED,
        }

    @property
    def is_active(self) -> bool:
        """Check if task is active (running or paused)"""
        return self._state in {TaskState.RUNNING, TaskState.PAUSED}

    @property
    def duration(self) -> float:
        """Time since creation"""
        return time.time() - self._created_at

    def can_transition_to(self, target: TaskState) -> bool:
        """Check if transition to target state is valid"""
        return target in self.VALID_TRANSITIONS.get(self._state, set())

    def transition_to(
        self,
        target: TaskState,
        reason: str = "",
        metadata: Optional[dict] = None,
    ) -> bool:
        """
        Transition to a new state.

        Args:
            target: Target state
            reason: Reason for transition
            metadata: Additional metadata

        Returns:
            True if transition was successful

        Raises:
            ValueError: If transition is not valid
        """
        if not self.can_transition_to(target):
            valid = self.VALID_TRANSITIONS.get(self._state, set())
            raise ValueError(
                f"Invalid transition: {self._state.value} -> {target.value}. "
                f"Valid targets: {[s.value for s in valid]}"
            )

        transition = StateTransition(
            from_state=self._state,
            to_state=target,
            reason=reason,
            metadata=metadata or {},
        )
        self._history.append(transition)
        self._state = target
        self._updated_at = time.time()

        logger.debug(
            f"Task {self.task_id}: {transition.from_state.value} -> "
            f"{transition.to_state.value} ({reason})"
        )

        if self._on_transition:
            try:
                self._on_transition(transition)
            except Exception as e:
                logger.error(f"Transition callback error: {e}")

        return True

    def get_history(self) -> list[StateTransition]:
        """Get state transition history"""
        return list(self._history)

    def get_time_in_state(self, state: TaskState) -> float:
        """Calculate total time spent in a state"""
        total = 0.0
        in_state_since = None

        for i, transition in enumerate(self._history):
            if transition.to_state == state:
                in_state_since = transition.timestamp
            elif in_state_since is not None:
                total += transition.timestamp - in_state_since
                in_state_since = None

        if in_state_since is not None and self._state == state:
            total += time.time() - in_state_since

        return total

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "task_id": self.task_id,
            "state": self._state.value,
            "is_terminal": self.is_terminal,
            "is_active": self.is_active,
            "duration": self.duration,
            "transition_count": len(self._history),
            "created_at": self._created_at,
            "updated_at": self._updated_at,
        }


class StateMachineRegistry:
    """
    Registry for managing multiple state machines.

    Example:
        registry = StateMachineRegistry()
        sm = registry.create("task_1")
        sm.transition_to(TaskState.RUNNING)

        active = registry.get_active()
    """

    def __init__(self):
        self._machines: dict[str, StateMachine] = {}

    def create(
        self,
        task_id: str,
        on_transition: Optional[Callable[[StateTransition], None]] = None,
    ) -> StateMachine:
        """Create and register a new state machine"""
        if task_id in self._machines:
            raise ValueError(f"Task {task_id} already exists")

        sm = StateMachine(task_id, on_transition=on_transition)
        self._machines[task_id] = sm
        return sm

    def get(self, task_id: str) -> Optional[StateMachine]:
        """Get state machine by task ID"""
        return self._machines.get(task_id)

    def remove(self, task_id: str) -> bool:
        """Remove a state machine"""
        if task_id in self._machines:
            del self._machines[task_id]
            return True
        return False

    def get_by_state(self, state: TaskState) -> list[StateMachine]:
        """Get all state machines in a specific state"""
        return [sm for sm in self._machines.values() if sm.state == state]

    def get_active(self) -> list[StateMachine]:
        """Get all active state machines"""
        return [sm for sm in self._machines.values() if sm.is_active]

    def get_all(self) -> list[StateMachine]:
        """Get all state machines"""
        return list(self._machines.values())

    def cleanup_terminal(self) -> int:
        """
        Remove all state machines in terminal states.

        Returns:
            Number of removed machines
        """
        terminal = [
            task_id for task_id, sm in self._machines.items()
            if sm.is_terminal
        ]
        for task_id in terminal:
            del self._machines[task_id]
        return len(terminal)

    def __len__(self) -> int:
        return len(self._machines)

    def __contains__(self, task_id: str) -> bool:
        return task_id in self._machines
