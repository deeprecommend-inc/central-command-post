"""Tests for RulesEngine"""
import pytest
from src.think import RulesEngine, Rule, DecisionContext, TaskContext
from src.sense import SystemState


class TestRule:
    """Tests for Rule dataclass"""

    def test_rule_creation(self):
        rule = Rule(
            name="test_rule",
            condition=lambda ctx: True,
            action="proceed",
            priority=10,
        )
        assert rule.name == "test_rule"
        assert rule.priority == 10

    def test_rule_evaluate_true(self):
        rule = Rule(
            name="always_true",
            condition=lambda ctx: True,
            action="test_action",
            params={"key": "value"},
        )
        context = DecisionContext(system_state=SystemState())
        decision = rule.evaluate(context)

        assert decision is not None
        assert decision.action == "test_action"
        assert decision.params["key"] == "value"

    def test_rule_evaluate_false(self):
        rule = Rule(
            name="always_false",
            condition=lambda ctx: False,
            action="test_action",
        )
        context = DecisionContext(system_state=SystemState())
        decision = rule.evaluate(context)
        assert decision is None

    def test_rule_evaluate_error_returns_none(self):
        rule = Rule(
            name="error_rule",
            condition=lambda ctx: 1 / 0,
            action="test",
        )
        context = DecisionContext(system_state=SystemState())
        decision = rule.evaluate(context)
        assert decision is None


class TestRulesEngine:
    """Tests for RulesEngine"""

    def test_initialization(self):
        engine = RulesEngine()
        assert len(engine) == 0

    def test_add_rule(self):
        engine = RulesEngine()
        rule = Rule(name="r1", condition=lambda ctx: True, action="a1")
        engine.add_rule(rule)
        assert len(engine) == 1

    def test_rules_sorted_by_priority(self):
        engine = RulesEngine()
        engine.add_rule(Rule(name="low", condition=lambda x: True, action="low", priority=1))
        engine.add_rule(Rule(name="high", condition=lambda x: True, action="high", priority=100))
        engine.add_rule(Rule(name="mid", condition=lambda x: True, action="mid", priority=50))

        rules = engine.get_rules()
        assert rules[0].name == "high"
        assert rules[1].name == "mid"
        assert rules[2].name == "low"

    def test_remove_rule(self):
        engine = RulesEngine()
        engine.add_rule(Rule(name="r1", condition=lambda x: True, action="a1"))
        result = engine.remove_rule("r1")
        assert result is True
        assert len(engine) == 0

    def test_remove_rule_not_found(self):
        engine = RulesEngine()
        result = engine.remove_rule("nonexistent")
        assert result is False

    def test_evaluate_returns_all_matches(self):
        engine = RulesEngine()
        engine.add_rule(Rule(name="r1", condition=lambda x: True, action="a1", priority=1))
        engine.add_rule(Rule(name="r2", condition=lambda x: True, action="a2", priority=2))
        engine.add_rule(Rule(name="r3", condition=lambda x: False, action="a3", priority=3))

        context = DecisionContext(system_state=SystemState())
        decisions = engine.evaluate(context)

        assert len(decisions) == 2
        assert decisions[0].action == "a2"
        assert decisions[1].action == "a1"

    def test_evaluate_first(self):
        engine = RulesEngine()
        engine.add_rule(Rule(name="r1", condition=lambda x: True, action="first", priority=100))
        engine.add_rule(Rule(name="r2", condition=lambda x: True, action="second", priority=50))

        context = DecisionContext(system_state=SystemState())
        decision = engine.evaluate_first(context)

        assert decision.action == "first"

    def test_evaluate_first_none(self):
        engine = RulesEngine()
        engine.add_rule(Rule(name="r1", condition=lambda x: False, action="a1"))

        context = DecisionContext(system_state=SystemState())
        decision = engine.evaluate_first(context)
        assert decision is None

    def test_clear(self):
        engine = RulesEngine()
        engine.add_rule(Rule(name="r1", condition=lambda x: True, action="a1"))
        engine.clear()
        assert len(engine) == 0

    def test_create_default(self):
        engine = RulesEngine.create_default()
        assert len(engine) > 0
        rules = engine.get_rules()
        rule_names = [r.name for r in rules]
        assert "abort_on_validation" in rule_names
        assert "proceed_default" in rule_names

    def test_default_engine_validation_abort(self):
        engine = RulesEngine.create_default()
        context = DecisionContext(
            system_state=SystemState(),
            task_context=TaskContext(
                task_id="t1",
                task_type="nav",
                last_error_type="validation",
            ),
        )
        decision = engine.evaluate_first(context)
        assert decision.action == "abort"

    def test_default_engine_timeout_retry(self):
        engine = RulesEngine.create_default()
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
        decision = engine.evaluate_first(context)
        assert decision.action == "retry"
