"""Tests for Experience Store"""
import pytest
import json
import tempfile
from datetime import datetime

from src.learn.experience_store import (
    ExperienceStore,
    Experience,
    StateSnapshot,
    Action,
    Outcome,
    OutcomeStatus,
    DefaultRewardModel,
)


class TestStateSnapshot:
    def test_create_snapshot(self):
        snap = StateSnapshot(
            timestamp=datetime.now(),
            features={"cpu": 0.5, "memory": 0.7},
            context={"task_id": "t1"},
        )
        assert snap.features["cpu"] == 0.5
        assert snap.context["task_id"] == "t1"

    def test_serialization(self):
        snap = StateSnapshot(
            timestamp=datetime(2025, 1, 1, 12, 0, 0),
            features={"value": 42},
        )
        data = snap.to_dict()
        restored = StateSnapshot.from_dict(data)
        assert restored.features["value"] == 42
        assert restored.timestamp == snap.timestamp


class TestAction:
    def test_create_action(self):
        action = Action(
            action_type="navigate",
            params={"url": "https://example.com"},
            source="policy",
        )
        assert action.action_type == "navigate"
        assert action.params["url"] == "https://example.com"

    def test_serialization(self):
        action = Action(action_type="click", params={"selector": "#btn"})
        data = action.to_dict()
        restored = Action.from_dict(data)
        assert restored.action_type == "click"
        assert restored.params["selector"] == "#btn"


class TestOutcome:
    def test_create_outcome(self):
        outcome = Outcome(
            status=OutcomeStatus.SUCCESS,
            result={"title": "Example"},
            duration_ms=150.5,
        )
        assert outcome.status == OutcomeStatus.SUCCESS
        assert outcome.result["title"] == "Example"

    def test_serialization(self):
        outcome = Outcome(
            status=OutcomeStatus.FAILURE,
            error="Connection timeout",
            duration_ms=30000,
        )
        data = outcome.to_dict()
        restored = Outcome.from_dict(data)
        assert restored.status == OutcomeStatus.FAILURE
        assert restored.error == "Connection timeout"


class TestExperience:
    def test_create_experience(self):
        state = StateSnapshot(timestamp=datetime.now(), features={"x": 1})
        action = Action(action_type="test", params={})
        outcome = Outcome(status=OutcomeStatus.SUCCESS, result={})

        exp = Experience(
            id="exp-1",
            state=state,
            action=action,
            outcome=outcome,
            reward=1.0,
        )
        assert exp.id == "exp-1"
        assert exp.is_success is True
        assert exp.reward == 1.0

    def test_auto_generate_id(self):
        state = StateSnapshot(timestamp=datetime.now(), features={})
        action = Action(action_type="test", params={})
        outcome = Outcome(status=OutcomeStatus.SUCCESS, result={})

        exp = Experience(id="", state=state, action=action, outcome=outcome, reward=0.0)
        assert exp.id != ""
        assert len(exp.id) > 0

    def test_serialization(self):
        state = StateSnapshot(timestamp=datetime.now(), features={"key": "value"})
        action = Action(action_type="action1", params={"p": 1})
        outcome = Outcome(status=OutcomeStatus.PARTIAL, result={"r": 2})

        exp = Experience(
            id="test-id",
            state=state,
            action=action,
            outcome=outcome,
            reward=0.5,
            metadata={"tag": "test"},
        )

        data = exp.to_dict()
        restored = Experience.from_dict(data)

        assert restored.id == "test-id"
        assert restored.state.features["key"] == "value"
        assert restored.action.action_type == "action1"
        assert restored.outcome.status == OutcomeStatus.PARTIAL
        assert restored.reward == 0.5
        assert restored.metadata["tag"] == "test"


class TestDefaultRewardModel:
    def test_success_reward(self):
        model = DefaultRewardModel()
        state = StateSnapshot(timestamp=datetime.now(), features={})
        action = Action(action_type="test", params={})
        outcome = Outcome(status=OutcomeStatus.SUCCESS, result={}, duration_ms=500)

        reward = model.compute(state, action, outcome)
        assert reward == 1.1  # 1.0 + 0.1 fast bonus

    def test_failure_reward(self):
        model = DefaultRewardModel()
        state = StateSnapshot(timestamp=datetime.now(), features={})
        action = Action(action_type="test", params={})
        outcome = Outcome(status=OutcomeStatus.FAILURE, result={})

        reward = model.compute(state, action, outcome)
        assert reward == -1.0


class TestExperienceStore:
    @pytest.fixture
    def store(self):
        return ExperienceStore(max_size=100)

    @pytest.fixture
    def sample_experience(self):
        state = StateSnapshot(timestamp=datetime.now(), features={"cpu": 0.5})
        action = Action(action_type="navigate", params={"url": "https://test.com"})
        outcome = Outcome(status=OutcomeStatus.SUCCESS, result={"title": "Test"})
        return Experience(id="sample-1", state=state, action=action, outcome=outcome, reward=1.0)

    def test_store_and_get(self, store, sample_experience):
        exp_id = store.store(sample_experience)
        assert exp_id == "sample-1"

        retrieved = store.get(exp_id)
        assert retrieved is not None
        assert retrieved.id == "sample-1"

    def test_record(self, store):
        state = StateSnapshot(timestamp=datetime.now(), features={})
        action = Action(action_type="click", params={})
        outcome = Outcome(status=OutcomeStatus.SUCCESS, result={}, duration_ms=100)

        exp = store.record(state, action, outcome)
        assert exp.reward == 1.1  # Auto-computed reward
        assert len(store) == 1

    def test_get_recent(self, store):
        for i in range(10):
            state = StateSnapshot(timestamp=datetime.now(), features={"i": i})
            action = Action(action_type="test", params={})
            outcome = Outcome(status=OutcomeStatus.SUCCESS, result={})
            store.record(state, action, outcome)

        recent = store.get_recent(5)
        assert len(recent) == 5

    def test_query_by_action(self, store):
        for action_type in ["navigate", "click", "navigate", "type"]:
            state = StateSnapshot(timestamp=datetime.now(), features={})
            action = Action(action_type=action_type, params={})
            outcome = Outcome(status=OutcomeStatus.SUCCESS, result={})
            store.record(state, action, outcome)

        navigate_exps = store.query_by_action("navigate")
        assert len(navigate_exps) == 2

    def test_query_by_status(self, store):
        for status in [OutcomeStatus.SUCCESS, OutcomeStatus.FAILURE, OutcomeStatus.SUCCESS]:
            state = StateSnapshot(timestamp=datetime.now(), features={})
            action = Action(action_type="test", params={})
            outcome = Outcome(status=status, result={})
            store.record(state, action, outcome)

        successes = store.query_successful()
        failures = store.query_failed()

        assert len(successes) == 2
        assert len(failures) == 1

    def test_max_size_eviction(self):
        store = ExperienceStore(max_size=3)

        for i in range(5):
            state = StateSnapshot(timestamp=datetime.now(), features={"i": i})
            action = Action(action_type="test", params={})
            outcome = Outcome(status=OutcomeStatus.SUCCESS, result={})
            store.record(state, action, outcome)

        assert len(store) == 3
        # Oldest should be evicted
        recent = store.get_recent(10)
        features = [e.state.features["i"] for e in recent]
        assert 0 not in features
        assert 1 not in features

    def test_statistics(self, store):
        # Add mixed experiences
        for status in [OutcomeStatus.SUCCESS, OutcomeStatus.SUCCESS, OutcomeStatus.FAILURE]:
            state = StateSnapshot(timestamp=datetime.now(), features={})
            action = Action(action_type="test", params={})
            outcome = Outcome(status=status, result={})
            store.record(state, action, outcome)

        stats = store.get_statistics()
        assert stats["total"] == 3
        assert stats["success_rate"] == pytest.approx(2 / 3)

    def test_export_import_json(self, store, sample_experience):
        store.store(sample_experience)

        json_str = store.export_json()
        data = json.loads(json_str)
        assert data["version"] == "1.0"
        assert len(data["experiences"]) == 1

        new_store = ExperienceStore()
        count = new_store.import_json(json_str)
        assert count == 1
        assert len(new_store) == 1

    def test_save_load_file(self, store, sample_experience):
        store.store(sample_experience)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            path = f.name

        store.save_to_file(path)

        new_store = ExperienceStore()
        count = new_store.load_from_file(path)
        assert count == 1

    def test_clear(self, store, sample_experience):
        store.store(sample_experience)
        assert len(store) == 1

        store.clear()
        assert len(store) == 0

    def test_iteration(self, store):
        for i in range(3):
            state = StateSnapshot(timestamp=datetime.now(), features={"i": i})
            action = Action(action_type="test", params={})
            outcome = Outcome(status=OutcomeStatus.SUCCESS, result={})
            store.record(state, action, outcome)

        experiences = list(store)
        assert len(experiences) == 3
