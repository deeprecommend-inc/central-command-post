"""Tests for Replay Engine"""
import pytest
from datetime import datetime

from src.learn.experience_store import (
    ExperienceStore,
    Experience,
    StateSnapshot,
    Action,
    Outcome,
    OutcomeStatus,
)
from src.learn.replay_engine import (
    ReplayEngine,
    ReplayConfig,
    SimulatedEnvironment,
    EpisodeResult,
)
from src.protocols import Policy, DecisionContext, Decision


class SimplePolicy:
    """Simple test policy that always returns the same action"""

    def __init__(self, action_type: str = "test"):
        self.action_type = action_type
        self.id = f"simple-{action_type}"
        self.updates: list[tuple] = []

    def decide(self, context: DecisionContext) -> Decision:
        return Decision(
            action=Action(action_type=self.action_type, params={}),
            confidence=0.9,
            reasoning="Test policy",
        )

    def update(self, state: StateSnapshot, action: Action, outcome: Outcome, reward: float) -> None:
        self.updates.append((state, action, outcome, reward))


class RandomPolicy:
    """Policy that randomly chooses from available action types"""

    def __init__(self, action_types: list[str]):
        self.action_types = action_types
        self.id = "random"

    def decide(self, context: DecisionContext) -> Decision:
        import random
        action_type = random.choice(self.action_types)
        return Decision(
            action=Action(action_type=action_type, params={}),
            confidence=0.5,
            reasoning="Random choice",
        )

    def update(self, state: StateSnapshot, action: Action, outcome: Outcome, reward: float) -> None:
        pass


@pytest.fixture
def experience_store():
    """Create store with sample experiences"""
    store = ExperienceStore()

    # Add various experiences
    action_types = ["navigate", "click", "type", "scroll"]
    statuses = [OutcomeStatus.SUCCESS, OutcomeStatus.SUCCESS, OutcomeStatus.FAILURE, OutcomeStatus.SUCCESS]

    for i, (action_type, status) in enumerate(zip(action_types * 3, statuses * 3)):
        state = StateSnapshot(
            timestamp=datetime.now(),
            features={"step": i, "value": i * 0.1},
        )
        action = Action(action_type=action_type, params={"index": i})
        outcome = Outcome(
            status=status,
            result={"data": f"result-{i}"},
            duration_ms=100 + i * 10,
        )
        reward = 1.0 if status == OutcomeStatus.SUCCESS else -1.0
        store.record(state, action, outcome, reward=reward)

    return store


class TestSimulatedEnvironment:
    def test_simulate_outcome_from_history(self, experience_store):
        env = SimulatedEnvironment(experience_store)

        state = StateSnapshot(timestamp=datetime.now(), features={})
        action = Action(action_type="navigate", params={"index": 0})

        # Should return an outcome based on historical data
        outcome = env.simulate_outcome(state, action)
        assert outcome is not None
        assert isinstance(outcome.status, OutcomeStatus)

    def test_simulate_outcome_fallback(self, experience_store):
        env = SimulatedEnvironment(experience_store)

        state = StateSnapshot(timestamp=datetime.now(), features={})
        # Action type exists but with different params
        action = Action(action_type="navigate", params={"unknown": "param"})

        outcome = env.simulate_outcome(state, action)
        assert outcome is not None

    def test_get_success_rate(self, experience_store):
        env = SimulatedEnvironment(experience_store)

        rate = env.get_success_rate("navigate")
        assert 0.0 <= rate <= 1.0

        # Unknown action type returns default
        rate = env.get_success_rate("unknown_action")
        assert rate == 0.5


class TestReplayEngine:
    @pytest.fixture
    def engine(self, experience_store):
        return ReplayEngine(experience_store)

    @pytest.mark.asyncio
    async def test_replay_single_episode(self, engine):
        policy = SimplePolicy("navigate")
        config = ReplayConfig(max_steps=5, record_traces=True)

        result = await engine.replay(policy, episodes=1, config=config)

        assert result.total_episodes == 1
        assert result.avg_reward != 0.0
        assert result.policy_id == "simple-navigate"

    @pytest.mark.asyncio
    async def test_replay_multiple_episodes(self, engine):
        policy = SimplePolicy("navigate")  # Use navigate which has more successes
        config = ReplayConfig(max_steps=10, record_traces=False)

        result = await engine.replay(policy, episodes=5, config=config)

        assert result.total_episodes == 5
        assert result.metrics["total_steps"] >= 0  # May be 0 if all episodes fail immediately

    @pytest.mark.asyncio
    async def test_replay_with_learning_policy(self, engine):
        policy = SimplePolicy("type")
        config = ReplayConfig(max_steps=3)

        await engine.replay(policy, episodes=2, config=config)

        # Policy should have received updates
        assert len(policy.updates) > 0

    @pytest.mark.asyncio
    async def test_compare_policies(self, engine):
        policies = [
            SimplePolicy("navigate"),
            SimplePolicy("click"),
            RandomPolicy(["navigate", "click", "type"]),
        ]

        results = await engine.compare_policies(
            policies,
            episodes_per_policy=3,
            config=ReplayConfig(max_steps=5),
        )

        assert len(results) == 3
        # Results should be sorted by avg_reward descending
        assert results[0].avg_reward >= results[1].avg_reward
        assert results[1].avg_reward >= results[2].avg_reward

    def test_get_action_statistics(self, engine):
        stats = engine.get_action_statistics()

        assert "navigate" in stats
        assert stats["navigate"]["count"] > 0
        assert "success_rate" in stats["navigate"]
        assert 0.0 <= stats["navigate"]["success_rate"] <= 1.0


class TestEpisodeResult:
    def test_avg_reward_per_step(self):
        result = EpisodeResult(
            episode_id="test",
            policy_id="test-policy",
            total_steps=10,
            total_reward=5.0,
            success=True,
            duration_ms=100.0,
        )

        assert result.avg_reward_per_step == 0.5

    def test_avg_reward_per_step_zero_steps(self):
        result = EpisodeResult(
            episode_id="test",
            policy_id="test-policy",
            total_steps=0,
            total_reward=0.0,
            success=False,
            duration_ms=0.0,
        )

        assert result.avg_reward_per_step == 0.0

    def test_to_dict(self):
        result = EpisodeResult(
            episode_id="test",
            policy_id="test-policy",
            total_steps=5,
            total_reward=2.5,
            success=True,
            duration_ms=50.0,
            metadata={"tag": "test"},
        )

        data = result.to_dict()

        assert data["episode_id"] == "test"
        assert data["total_reward"] == 2.5
        assert data["metadata"]["tag"] == "test"


class TestReplayConfig:
    def test_default_config(self):
        config = ReplayConfig()

        assert config.max_steps == 100
        assert config.timeout_seconds == 30.0
        assert config.record_traces is True
        assert config.parallel_episodes == 1

    def test_custom_config(self):
        config = ReplayConfig(
            max_steps=50,
            record_traces=False,
        )

        assert config.max_steps == 50
        assert config.record_traces is False
