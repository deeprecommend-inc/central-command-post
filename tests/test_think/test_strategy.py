"""Tests for Strategy classes"""
import pytest
from src.think import (
    Decision, Strategy, RetryStrategy, ProxySelectionStrategy,
    DecisionContext, TaskContext,
)
from src.sense import SystemState


class TestDecision:
    """Tests for Decision dataclass"""

    def test_decision_creation(self):
        decision = Decision(
            action="retry",
            params={"delay": 1.0},
            confidence=0.8,
            reasoning="Retryable error",
        )
        assert decision.action == "retry"
        assert decision.params["delay"] == 1.0
        assert decision.confidence == 0.8

    def test_decision_invalid_confidence(self):
        with pytest.raises(ValueError):
            Decision(action="test", confidence=1.5)

    def test_decision_to_dict(self):
        decision = Decision(action="proceed", confidence=0.9)
        d = decision.to_dict()
        assert d["action"] == "proceed"
        assert d["confidence"] == 0.9


class TestRetryStrategy:
    """Tests for RetryStrategy"""

    def test_initialization(self):
        strategy = RetryStrategy(max_retries=5)
        assert strategy.max_retries == 5

    def test_no_error_proceeds(self):
        strategy = RetryStrategy()
        context = DecisionContext(
            system_state=SystemState(),
            task_context=TaskContext(task_id="t1", task_type="nav"),
        )
        decision = strategy.evaluate(context)
        assert decision.action == "proceed"

    def test_non_retryable_error_aborts(self):
        strategy = RetryStrategy()
        context = DecisionContext(
            system_state=SystemState(),
            task_context=TaskContext(
                task_id="t1",
                task_type="nav",
                last_error_type="validation",
            ),
        )
        decision = strategy.evaluate(context)
        assert decision.action == "abort"

    def test_retryable_error_retries(self):
        strategy = RetryStrategy()
        context = DecisionContext(
            system_state=SystemState(),
            task_context=TaskContext(
                task_id="t1",
                task_type="nav",
                last_error_type="timeout",
                retry_count=0,
                max_retries=3,
            ),
        )
        decision = strategy.evaluate(context)
        assert decision.action == "retry"
        assert "delay" in decision.params

    def test_max_retries_exceeded(self):
        strategy = RetryStrategy(max_retries=3)
        context = DecisionContext(
            system_state=SystemState(),
            task_context=TaskContext(
                task_id="t1",
                task_type="nav",
                last_error_type="timeout",
                retry_count=3,
                max_retries=3,
            ),
        )
        decision = strategy.evaluate(context)
        assert decision.action == "abort"

    def test_proxy_error_switches_proxy(self):
        strategy = RetryStrategy()
        context = DecisionContext(
            system_state=SystemState(),
            task_context=TaskContext(
                task_id="t1",
                task_type="nav",
                last_error_type="proxy",
                retry_count=0,
                max_retries=3,
            ),
        )
        decision = strategy.evaluate(context)
        assert decision.action == "retry"
        assert decision.params.get("switch_proxy") is True

    def test_backoff_calculation(self):
        strategy = RetryStrategy(backoff_base=1.0, backoff_max=30.0)
        assert strategy._calculate_backoff(0) == 1.0
        assert strategy._calculate_backoff(1) == 2.0
        assert strategy._calculate_backoff(2) == 4.0
        assert strategy._calculate_backoff(10) == 30.0


class TestProxySelectionStrategy:
    """Tests for ProxySelectionStrategy"""

    def test_no_stats_uses_default(self):
        strategy = ProxySelectionStrategy()
        context = DecisionContext(
            system_state=SystemState(proxy_stats={}),
        )
        decision = strategy.evaluate(context)
        assert decision.action == "use_default_proxy"

    def test_selects_healthy_proxy(self):
        strategy = ProxySelectionStrategy()
        context = DecisionContext(
            system_state=SystemState(
                proxy_stats={
                    "us": {"health_score": 0.9},
                    "jp": {"health_score": 0.7},
                }
            ),
        )
        decision = strategy.evaluate(context)
        assert decision.action == "select_proxy"
        assert decision.params["country"] == "us"

    def test_no_healthy_proxies_resets(self):
        strategy = ProxySelectionStrategy(health_threshold=0.8)
        context = DecisionContext(
            system_state=SystemState(
                proxy_stats={
                    "us": {"health_score": 0.3},
                    "jp": {"health_score": 0.2},
                }
            ),
        )
        decision = strategy.evaluate(context)
        assert decision.action == "reset_proxies"
