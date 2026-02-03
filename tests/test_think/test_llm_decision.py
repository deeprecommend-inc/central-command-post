"""Tests for LLM Decision Maker"""
import pytest
from datetime import datetime

from src.think import (
    LLMDecisionMaker,
    LLMConfig,
    TransitionDecider,
    Decision,
    create_initial_state,
    CCPPhase,
)


class TestLLMConfig:
    def test_default_config(self):
        config = LLMConfig()
        assert config.provider == "openai"
        assert config.model == "gpt-4o"
        assert config.temperature == 0.3
        assert config.confidence_threshold == 0.7

    def test_custom_config(self):
        config = LLMConfig(
            provider="anthropic",
            model="claude-sonnet-4-20250514",
            temperature=0.5,
            confidence_threshold=0.8,
        )
        assert config.provider == "anthropic"
        assert config.confidence_threshold == 0.8


class TestLLMDecisionMaker:
    def test_create_maker(self):
        maker = LLMDecisionMaker()
        assert maker.config.provider == "openai"

    def test_requires_approval_low_confidence(self):
        maker = LLMDecisionMaker(LLMConfig(confidence_threshold=0.7))
        decision = Decision(action="proceed", confidence=0.5)
        assert maker.requires_approval(decision) is True

    def test_no_approval_high_confidence(self):
        maker = LLMDecisionMaker(LLMConfig(confidence_threshold=0.7))
        decision = Decision(action="proceed", confidence=0.9)
        assert maker.requires_approval(decision) is False

    def test_fallback_decision_max_retries(self):
        maker = LLMDecisionMaker()
        state = create_initial_state(
            task_id="test",
            task_type="navigate",
            target="https://example.com",
            max_retries=3,
        )
        state["retry_count"] = 3

        decision, outputs = maker._fallback_decision(state, None)

        assert decision.action == "abort"
        assert outputs["fallback"] is True

    def test_fallback_decision_proxy_error(self):
        maker = LLMDecisionMaker()
        state = create_initial_state(
            task_id="test",
            task_type="navigate",
            target="https://example.com",
        )
        state["error_history"] = ["proxy connection failed"]

        decision, outputs = maker._fallback_decision(state, None)

        assert decision.action == "switch_proxy"

    def test_fallback_decision_default(self):
        maker = LLMDecisionMaker()
        state = create_initial_state(
            task_id="test",
            task_type="navigate",
            target="https://example.com",
        )

        decision, outputs = maker._fallback_decision(state, None)

        assert decision.action == "proceed"


class TestTransitionDecider:
    def test_decide_from_sense(self):
        decider = TransitionDecider()
        state = create_initial_state(
            task_id="test",
            task_type="navigate",
            target="https://example.com",
        )
        state["current_phase"] = CCPPhase.SENSE

        next_phase = decider.decide_next_phase(state)
        assert next_phase == CCPPhase.THINK

    def test_decide_from_think_no_approval(self):
        decider = TransitionDecider()
        state = create_initial_state(
            task_id="test",
            task_type="navigate",
            target="https://example.com",
        )
        state["current_phase"] = CCPPhase.THINK
        state["requires_approval"] = False

        next_phase = decider.decide_next_phase(state)
        assert next_phase == CCPPhase.COMMAND

    def test_decide_from_think_needs_approval(self):
        decider = TransitionDecider()
        state = create_initial_state(
            task_id="test",
            task_type="navigate",
            target="https://example.com",
        )
        state["current_phase"] = CCPPhase.THINK
        state["requires_approval"] = True
        state["approval_status"] = None

        next_phase = decider.decide_next_phase(state)
        assert next_phase == CCPPhase.AWAITING_APPROVAL

    def test_decide_abort(self):
        decider = TransitionDecider()
        state = create_initial_state(
            task_id="test",
            task_type="navigate",
            target="https://example.com",
        )
        state["decision_action"] = "abort"

        next_phase = decider.decide_next_phase(state)
        assert next_phase == CCPPhase.ABORTED

    def test_decide_from_control_success(self):
        decider = TransitionDecider()
        state = create_initial_state(
            task_id="test",
            task_type="navigate",
            target="https://example.com",
        )
        state["current_phase"] = CCPPhase.CONTROL
        state["command_success"] = True

        next_phase = decider.decide_next_phase(state)
        assert next_phase == CCPPhase.LEARN

    def test_decide_from_control_retry(self):
        decider = TransitionDecider()
        state = create_initial_state(
            task_id="test",
            task_type="navigate",
            target="https://example.com",
            max_retries=3,
        )
        state["current_phase"] = CCPPhase.CONTROL
        state["command_success"] = False
        state["retry_count"] = 1

        next_phase = decider.decide_next_phase(state)
        assert next_phase == CCPPhase.SENSE

    def test_routing_key(self):
        decider = TransitionDecider()
        state = create_initial_state(
            task_id="test",
            task_type="navigate",
            target="https://example.com",
        )
        state["current_phase"] = CCPPhase.LEARN

        key = decider.get_routing_key(state)
        assert key == "completed"
