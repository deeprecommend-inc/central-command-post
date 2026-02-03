"""Tests for Agent State"""
import pytest
from datetime import datetime

from src.think import (
    AgentState,
    CCPPhase,
    TransitionReason,
    ThoughtStep,
    TransitionRecord,
    create_initial_state,
    state_to_summary,
)


class TestCCPPhase:
    def test_phases_defined(self):
        assert CCPPhase.SENSE.value == "sense"
        assert CCPPhase.THINK.value == "think"
        assert CCPPhase.COMMAND.value == "command"
        assert CCPPhase.CONTROL.value == "control"
        assert CCPPhase.LEARN.value == "learn"
        assert CCPPhase.AWAITING_APPROVAL.value == "awaiting_approval"
        assert CCPPhase.COMPLETED.value == "completed"
        assert CCPPhase.ABORTED.value == "aborted"


class TestThoughtStep:
    def test_create_thought_step(self):
        step = ThoughtStep(
            step_id="step_001",
            phase=CCPPhase.THINK,
            timestamp=datetime.now(),
            reasoning="Test reasoning",
            inputs={"key": "value"},
            outputs={"result": "success"},
            confidence=0.85,
            duration_ms=100.0,
        )

        assert step.step_id == "step_001"
        assert step.phase == CCPPhase.THINK
        assert step.confidence == 0.85

    def test_thought_step_to_dict(self):
        now = datetime.now()
        step = ThoughtStep(
            step_id="step_001",
            phase=CCPPhase.THINK,
            timestamp=now,
            reasoning="Test",
            inputs={},
            outputs={},
        )

        d = step.to_dict()
        assert d["step_id"] == "step_001"
        assert d["phase"] == "think"
        assert d["reasoning"] == "Test"


class TestTransitionRecord:
    def test_create_transition(self):
        record = TransitionRecord(
            from_phase=CCPPhase.SENSE,
            to_phase=CCPPhase.THINK,
            reason=TransitionReason.DATA_COLLECTED,
            timestamp=datetime.now(),
        )

        assert record.from_phase == CCPPhase.SENSE
        assert record.to_phase == CCPPhase.THINK

    def test_transition_to_dict(self):
        record = TransitionRecord(
            from_phase=CCPPhase.THINK,
            to_phase=CCPPhase.COMMAND,
            reason=TransitionReason.DECISION_MADE,
            timestamp=datetime.now(),
            metadata={"extra": "data"},
        )

        d = record.to_dict()
        assert d["from_phase"] == "think"
        assert d["to_phase"] == "command"
        assert d["metadata"]["extra"] == "data"


class TestCreateInitialState:
    def test_create_state(self):
        state = create_initial_state(
            task_id="task_001",
            task_type="navigate",
            target="https://example.com",
        )

        assert state["task_id"] == "task_001"
        assert state["task_type"] == "navigate"
        assert state["target"] == "https://example.com"
        assert state["current_phase"] == CCPPhase.SENSE
        assert state["retry_count"] == 0
        assert state["max_retries"] == 3

    def test_create_state_with_params(self):
        state = create_initial_state(
            task_id="task_002",
            task_type="scrape",
            target="https://example.com",
            params={"selector": ".content"},
            max_retries=5,
        )

        assert state["params"]["selector"] == ".content"
        assert state["max_retries"] == 5


class TestStateSummary:
    def test_state_to_summary(self):
        state = create_initial_state(
            task_id="task_001",
            task_type="navigate",
            target="https://example.com",
        )
        state["decision_action"] = "proceed"
        state["decision_confidence"] = 0.9

        summary = state_to_summary(state)

        assert summary["task_id"] == "task_001"
        assert summary["current_phase"] == "sense"
        assert summary["decision"]["action"] == "proceed"
        assert summary["decision"]["confidence"] == 0.9
