"""
Experience Store - Universal learning foundation for CCP v2

Stores experiences as (State, Action, Outcome, Reward) tuples.
Domain-agnostic design enables cross-domain learning and replay.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol, TypeVar, Generic
from enum import Enum
import json
import uuid
from collections import deque


class OutcomeStatus(Enum):
    """Outcome status classification"""
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class StateSnapshot:
    """
    Immutable state observation at a point in time.
    Domain-specific fields go in 'features' dict.
    """
    timestamp: datetime
    features: dict[str, Any]
    context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "features": self.features,
            "context": self.context,
        }

    @classmethod
    def from_dict(cls, data: dict) -> StateSnapshot:
        return cls(
            timestamp=datetime.fromisoformat(data["timestamp"]),
            features=data["features"],
            context=data.get("context", {}),
        )


@dataclass(frozen=True)
class Action:
    """
    Immutable action taken by the system.
    """
    action_type: str
    params: dict[str, Any] = field(default_factory=dict)
    source: str = "system"  # system, human, policy
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "action_type": self.action_type,
            "params": self.params,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> Action:
        return cls(
            action_type=data["action_type"],
            params=data.get("params", {}),
            source=data.get("source", "system"),
            timestamp=datetime.fromisoformat(data["timestamp"]),
        )


@dataclass(frozen=True)
class Outcome:
    """
    Immutable outcome of an action.
    """
    status: OutcomeStatus
    result: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    duration_ms: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> Outcome:
        return cls(
            status=OutcomeStatus(data["status"]),
            result=data.get("result", {}),
            error=data.get("error"),
            duration_ms=data.get("duration_ms", 0.0),
            timestamp=datetime.fromisoformat(data["timestamp"]),
        )


@dataclass
class Experience:
    """
    Complete experience tuple (S, A, O, R).
    The fundamental unit of learning in CCP v2.
    """
    id: str
    state: StateSnapshot
    action: Action
    outcome: Outcome
    reward: float
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "state": self.state.to_dict(),
            "action": self.action.to_dict(),
            "outcome": self.outcome.to_dict(),
            "reward": self.reward,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Experience:
        return cls(
            id=data["id"],
            state=StateSnapshot.from_dict(data["state"]),
            action=Action.from_dict(data["action"]),
            outcome=Outcome.from_dict(data["outcome"]),
            reward=data["reward"],
            metadata=data.get("metadata", {}),
        )

    @property
    def is_success(self) -> bool:
        return self.outcome.status == OutcomeStatus.SUCCESS


class RewardModel(Protocol):
    """Protocol for domain-specific reward computation"""
    def compute(self, state: StateSnapshot, action: Action, outcome: Outcome) -> float:
        """Compute reward for a given (state, action, outcome) tuple"""
        ...


class DefaultRewardModel:
    """Default reward model based on outcome status"""

    def compute(self, state: StateSnapshot, action: Action, outcome: Outcome) -> float:
        reward_map = {
            OutcomeStatus.SUCCESS: 1.0,
            OutcomeStatus.PARTIAL: 0.5,
            OutcomeStatus.FAILURE: -1.0,
            OutcomeStatus.TIMEOUT: -0.5,
            OutcomeStatus.CANCELLED: 0.0,
        }
        base_reward = reward_map.get(outcome.status, 0.0)

        # Bonus for fast execution
        if outcome.duration_ms > 0 and outcome.duration_ms < 1000:
            base_reward += 0.1

        return base_reward


class ExperienceStore:
    """
    In-memory experience store with persistence support.

    Features:
    - Store/retrieve experiences by ID
    - Query by state features, action type, outcome status
    - Export/import for replay
    - Rolling window support for online learning
    """

    def __init__(
        self,
        max_size: int = 10000,
        reward_model: RewardModel | None = None,
    ):
        self._experiences: dict[str, Experience] = {}
        self._timeline: deque[str] = deque(maxlen=max_size)
        self._max_size = max_size
        self._reward_model = reward_model or DefaultRewardModel()

        # Indices for fast lookup
        self._by_action_type: dict[str, list[str]] = {}
        self._by_status: dict[OutcomeStatus, list[str]] = {}

    def store(self, experience: Experience) -> str:
        """Store an experience and return its ID"""
        # Evict oldest if at capacity
        if len(self._timeline) >= self._max_size:
            oldest_id = self._timeline[0]
            self._remove_from_indices(oldest_id)
            del self._experiences[oldest_id]

        self._experiences[experience.id] = experience
        self._timeline.append(experience.id)
        self._add_to_indices(experience)

        return experience.id

    def record(
        self,
        state: StateSnapshot,
        action: Action,
        outcome: Outcome,
        reward: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Experience:
        """
        Record a new experience.
        If reward is None, compute using reward model.
        """
        if reward is None:
            reward = self._reward_model.compute(state, action, outcome)

        experience = Experience(
            id=str(uuid.uuid4()),
            state=state,
            action=action,
            outcome=outcome,
            reward=reward,
            metadata=metadata or {},
        )
        self.store(experience)
        return experience

    def get(self, experience_id: str) -> Experience | None:
        """Get experience by ID"""
        return self._experiences.get(experience_id)

    def get_recent(self, n: int = 100) -> list[Experience]:
        """Get n most recent experiences"""
        ids = list(self._timeline)[-n:]
        return [self._experiences[id] for id in ids if id in self._experiences]

    def query_by_action(self, action_type: str) -> list[Experience]:
        """Get all experiences with given action type"""
        ids = self._by_action_type.get(action_type, [])
        return [self._experiences[id] for id in ids if id in self._experiences]

    def query_by_status(self, status: OutcomeStatus) -> list[Experience]:
        """Get all experiences with given outcome status"""
        ids = self._by_status.get(status, [])
        return [self._experiences[id] for id in ids if id in self._experiences]

    def query_successful(self) -> list[Experience]:
        """Get all successful experiences"""
        return self.query_by_status(OutcomeStatus.SUCCESS)

    def query_failed(self) -> list[Experience]:
        """Get all failed experiences"""
        return self.query_by_status(OutcomeStatus.FAILURE)

    def get_statistics(self) -> dict[str, Any]:
        """Get store statistics"""
        total = len(self._experiences)
        if total == 0:
            return {"total": 0, "success_rate": 0.0, "avg_reward": 0.0}

        successes = len(self.query_successful())
        rewards = [e.reward for e in self._experiences.values()]

        return {
            "total": total,
            "success_rate": successes / total,
            "avg_reward": sum(rewards) / len(rewards),
            "by_action": {k: len(v) for k, v in self._by_action_type.items()},
            "by_status": {k.value: len(v) for k, v in self._by_status.items()},
        }

    def export_json(self) -> str:
        """Export all experiences as JSON"""
        data = {
            "version": "1.0",
            "experiences": [e.to_dict() for e in self._experiences.values()],
        }
        return json.dumps(data, indent=2)

    def import_json(self, json_str: str) -> int:
        """Import experiences from JSON, return count imported"""
        data = json.loads(json_str)
        count = 0
        for exp_data in data.get("experiences", []):
            experience = Experience.from_dict(exp_data)
            self.store(experience)
            count += 1
        return count

    def save_to_file(self, path: str) -> None:
        """Save experiences to file"""
        with open(path, "w") as f:
            f.write(self.export_json())

    def load_from_file(self, path: str) -> int:
        """Load experiences from file"""
        with open(path, "r") as f:
            return self.import_json(f.read())

    def clear(self) -> None:
        """Clear all experiences"""
        self._experiences.clear()
        self._timeline.clear()
        self._by_action_type.clear()
        self._by_status.clear()

    def _add_to_indices(self, experience: Experience) -> None:
        """Add experience to lookup indices"""
        action_type = experience.action.action_type
        if action_type not in self._by_action_type:
            self._by_action_type[action_type] = []
        self._by_action_type[action_type].append(experience.id)

        status = experience.outcome.status
        if status not in self._by_status:
            self._by_status[status] = []
        self._by_status[status].append(experience.id)

    def _remove_from_indices(self, experience_id: str) -> None:
        """Remove experience from lookup indices"""
        experience = self._experiences.get(experience_id)
        if not experience:
            return

        action_type = experience.action.action_type
        if action_type in self._by_action_type:
            self._by_action_type[action_type] = [
                id for id in self._by_action_type[action_type] if id != experience_id
            ]

        status = experience.outcome.status
        if status in self._by_status:
            self._by_status[status] = [
                id for id in self._by_status[status] if id != experience_id
            ]

    def __len__(self) -> int:
        return len(self._experiences)

    def __iter__(self):
        return iter(self._experiences.values())
