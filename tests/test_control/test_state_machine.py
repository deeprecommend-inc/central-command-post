"""Tests for StateMachine"""
import pytest
from src.control import TaskState, StateMachine, StateTransition


class TestTaskState:
    """Tests for TaskState enum"""

    def test_all_states(self):
        states = [
            TaskState.PENDING,
            TaskState.RUNNING,
            TaskState.PAUSED,
            TaskState.COMPLETED,
            TaskState.FAILED,
            TaskState.CANCELLED,
        ]
        assert len(states) == 6


class TestStateMachine:
    """Tests for StateMachine"""

    def test_initialization(self):
        sm = StateMachine("task_1")
        assert sm.task_id == "task_1"
        assert sm.state == TaskState.PENDING
        assert not sm.is_terminal
        assert not sm.is_active

    def test_transition_pending_to_running(self):
        sm = StateMachine("task_1")
        result = sm.transition_to(TaskState.RUNNING)
        assert result is True
        assert sm.state == TaskState.RUNNING
        assert sm.is_active

    def test_transition_running_to_completed(self):
        sm = StateMachine("task_1")
        sm.transition_to(TaskState.RUNNING)
        sm.transition_to(TaskState.COMPLETED)
        assert sm.state == TaskState.COMPLETED
        assert sm.is_terminal

    def test_invalid_transition_raises(self):
        sm = StateMachine("task_1")
        with pytest.raises(ValueError):
            sm.transition_to(TaskState.COMPLETED)

    def test_can_transition_to(self):
        sm = StateMachine("task_1")
        assert sm.can_transition_to(TaskState.RUNNING)
        assert not sm.can_transition_to(TaskState.COMPLETED)

    def test_transition_history(self):
        sm = StateMachine("task_1")
        sm.transition_to(TaskState.RUNNING, "Started")
        sm.transition_to(TaskState.COMPLETED, "Done")

        history = sm.get_history()
        assert len(history) == 2
        assert history[0].from_state == TaskState.PENDING
        assert history[0].to_state == TaskState.RUNNING
        assert history[0].reason == "Started"

    def test_terminal_states(self):
        for terminal_state in [TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED]:
            sm = StateMachine("task_1")
            sm.transition_to(TaskState.RUNNING)
            sm.transition_to(terminal_state)
            assert sm.is_terminal
            assert len(sm.VALID_TRANSITIONS[terminal_state]) == 0

    def test_duration(self):
        sm = StateMachine("task_1")
        assert sm.duration >= 0

    def test_to_dict(self):
        sm = StateMachine("task_1")
        d = sm.to_dict()
        assert d["task_id"] == "task_1"
        assert d["state"] == "pending"
        assert d["is_terminal"] is False

    def test_on_transition_callback(self):
        transitions = []

        def callback(t: StateTransition):
            transitions.append(t)

        sm = StateMachine("task_1", on_transition=callback)
        sm.transition_to(TaskState.RUNNING)

        assert len(transitions) == 1
        assert transitions[0].to_state == TaskState.RUNNING

    def test_pause_and_resume(self):
        sm = StateMachine("task_1")
        sm.transition_to(TaskState.RUNNING)
        sm.transition_to(TaskState.PAUSED)
        assert sm.state == TaskState.PAUSED
        assert sm.is_active

        sm.transition_to(TaskState.RUNNING)
        assert sm.state == TaskState.RUNNING

    def test_paused_can_be_cancelled(self):
        sm = StateMachine("task_1")
        sm.transition_to(TaskState.RUNNING)
        sm.transition_to(TaskState.PAUSED)
        sm.transition_to(TaskState.CANCELLED)
        assert sm.state == TaskState.CANCELLED
        assert sm.is_terminal
