"""Tests for StateSnapshot"""
import pytest
from datetime import timedelta
from src.sense import StateSnapshot, SystemState


class TestSystemState:
    """Tests for SystemState dataclass"""

    def test_default_values(self):
        state = SystemState()
        assert state.active_tasks == 0
        assert state.error_count == 0
        assert state.success_count == 0

    def test_success_rate_calculation(self):
        state = SystemState(success_count=8, error_count=2)
        assert state.success_rate == 0.8

    def test_success_rate_no_requests(self):
        state = SystemState()
        assert state.success_rate == 1.0

    def test_to_dict(self):
        state = SystemState(active_tasks=5)
        d = state.to_dict()
        assert d["active_tasks"] == 5
        assert "success_rate" in d


class TestStateSnapshot:
    """Tests for StateSnapshot"""

    def test_initialization(self):
        snapshot = StateSnapshot()
        state = snapshot.get_current_state()
        assert isinstance(state, SystemState)

    def test_update_proxy_stats(self):
        snapshot = StateSnapshot()
        snapshot.update_proxy_stats({"us": {"health": 0.9}})
        state = snapshot.get_current_state()
        assert state.proxy_stats == {"us": {"health": 0.9}}

    def test_update_worker_stats(self):
        snapshot = StateSnapshot()
        snapshot.update_worker_stats({"active": 3})
        state = snapshot.get_current_state()
        assert state.worker_stats == {"active": 3}

    def test_set_active_tasks(self):
        snapshot = StateSnapshot()
        snapshot.set_active_tasks(10)
        state = snapshot.get_current_state()
        assert state.active_tasks == 10

    def test_record_success(self):
        snapshot = StateSnapshot()
        snapshot.record_success()
        snapshot.record_success()
        state = snapshot.get_current_state()
        assert state.success_count == 2

    def test_record_error(self):
        snapshot = StateSnapshot()
        snapshot.record_error()
        state = snapshot.get_current_state()
        assert state.error_count == 1

    def test_save_snapshot(self):
        snapshot = StateSnapshot()
        snapshot.record_success()
        saved = snapshot.save_snapshot()
        assert saved.success_count == 1

        history = snapshot.get_history()
        assert len(history) == 1

    def test_get_history_limit(self):
        snapshot = StateSnapshot()
        for _ in range(5):
            snapshot.save_snapshot()

        history = snapshot.get_history(limit=3)
        assert len(history) == 3

    def test_get_trend_not_enough_data(self):
        snapshot = StateSnapshot()
        trend = snapshot.get_trend("success_rate", timedelta(hours=1))
        assert trend is None

    def test_get_trend_stable(self):
        snapshot = StateSnapshot()
        for _ in range(5):
            snapshot.record_success()
            snapshot.save_snapshot()

        trend = snapshot.get_trend("success_rate", timedelta(hours=1))
        assert trend is not None
        assert trend["direction"] == "stable"

    def test_reset(self):
        snapshot = StateSnapshot()
        snapshot.record_success()
        snapshot.record_error()
        snapshot.reset()

        state = snapshot.get_current_state()
        assert state.success_count == 0
        assert state.error_count == 0

    def test_clear_history(self):
        snapshot = StateSnapshot()
        snapshot.save_snapshot()
        snapshot.save_snapshot()
        snapshot.clear_history()

        history = snapshot.get_history()
        assert len(history) == 0

    def test_max_history(self):
        snapshot = StateSnapshot(max_history=3)
        for _ in range(5):
            snapshot.save_snapshot()

        history = snapshot.get_history()
        assert len(history) == 3
