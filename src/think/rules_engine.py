"""
Rules Engine - Rule-based decision making
"""
from dataclasses import dataclass, field
from typing import Callable, Optional, Any
from loguru import logger

from .decision_context import DecisionContext
from .strategy import Decision


@dataclass
class Rule:
    """
    A single decision rule.

    Example:
        rule = Rule(
            name="high_error_rate",
            condition=lambda ctx: ctx.get_error_frequency() > 0.5,
            action="reduce_load",
            params={"factor": 0.5},
            priority=10,
        )
    """
    name: str
    condition: Callable[[DecisionContext], bool]
    action: str
    params: dict[str, Any] = field(default_factory=dict)
    priority: int = 0
    confidence: float = 1.0
    description: str = ""

    def evaluate(self, context: DecisionContext) -> Optional[Decision]:
        """
        Evaluate rule against context.

        Returns:
            Decision if condition is met, None otherwise
        """
        try:
            if self.condition(context):
                return Decision(
                    action=self.action,
                    params=self.params,
                    confidence=self.confidence,
                    reasoning=self.description or f"Rule '{self.name}' triggered",
                    priority=self.priority,
                )
        except Exception as e:
            logger.error(f"Error evaluating rule '{self.name}': {e}")
        return None


class RulesEngine:
    """
    Rule-based decision engine.

    Evaluates rules in priority order and returns matching decisions.

    Example:
        engine = RulesEngine()

        engine.add_rule(Rule(
            name="abort_on_validation_error",
            condition=lambda ctx: ctx.task_context and
                ctx.task_context.last_error_type == "validation",
            action="abort",
            priority=100,
        ))

        engine.add_rule(Rule(
            name="retry_on_timeout",
            condition=lambda ctx: ctx.task_context and
                ctx.task_context.last_error_type == "timeout" and
                ctx.task_context.can_retry,
            action="retry",
            params={"delay": 2.0},
            priority=50,
        ))

        decisions = engine.evaluate(context)
    """

    def __init__(self):
        self._rules: list[Rule] = []

    def add_rule(self, rule: Rule) -> None:
        """Add a rule to the engine"""
        self._rules.append(rule)
        self._rules.sort(key=lambda r: r.priority, reverse=True)
        logger.debug(f"Added rule: {rule.name} (priority={rule.priority})")

    def remove_rule(self, name: str) -> bool:
        """
        Remove a rule by name.

        Returns:
            True if rule was found and removed
        """
        for i, rule in enumerate(self._rules):
            if rule.name == name:
                del self._rules[i]
                logger.debug(f"Removed rule: {name}")
                return True
        return False

    def evaluate(self, context: DecisionContext) -> list[Decision]:
        """
        Evaluate all rules against context.

        Args:
            context: Decision context

        Returns:
            List of decisions from triggered rules, sorted by priority
        """
        decisions = []
        for rule in self._rules:
            decision = rule.evaluate(context)
            if decision:
                decisions.append(decision)
                logger.debug(f"Rule '{rule.name}' triggered: {decision.action}")

        return decisions

    def evaluate_first(self, context: DecisionContext) -> Optional[Decision]:
        """
        Evaluate rules and return the first (highest priority) match.

        Args:
            context: Decision context

        Returns:
            First matching decision or None
        """
        for rule in self._rules:
            decision = rule.evaluate(context)
            if decision:
                return decision
        return None

    def get_rules(self) -> list[Rule]:
        """Get all rules"""
        return list(self._rules)

    def clear(self) -> None:
        """Clear all rules"""
        self._rules.clear()

    def __len__(self) -> int:
        return len(self._rules)

    @classmethod
    def create_default(cls) -> "RulesEngine":
        """
        Create engine with default rules.

        Returns:
            RulesEngine with common rules pre-configured
        """
        engine = cls()

        engine.add_rule(Rule(
            name="abort_on_validation",
            condition=lambda ctx: (
                ctx.task_context and
                ctx.task_context.last_error_type == "validation"
            ),
            action="abort",
            priority=100,
            confidence=1.0,
            description="Abort on validation errors (non-retryable)",
        ))

        engine.add_rule(Rule(
            name="abort_on_browser_closed",
            condition=lambda ctx: (
                ctx.task_context and
                ctx.task_context.last_error_type == "browser_closed"
            ),
            action="abort",
            priority=100,
            confidence=1.0,
            description="Abort when browser is closed",
        ))

        engine.add_rule(Rule(
            name="abort_on_max_retries",
            condition=lambda ctx: (
                ctx.task_context and
                not ctx.task_context.can_retry
            ),
            action="abort",
            params={"reason": "max_retries_exceeded"},
            priority=90,
            confidence=0.95,
            description="Abort when max retries exceeded",
        ))

        engine.add_rule(Rule(
            name="retry_on_proxy_error",
            condition=lambda ctx: (
                ctx.task_context and
                ctx.task_context.last_error_type == "proxy" and
                ctx.task_context.can_retry
            ),
            action="retry",
            params={"switch_proxy": True, "delay": 1.0},
            priority=80,
            confidence=0.85,
            description="Retry with new proxy on proxy errors",
        ))

        engine.add_rule(Rule(
            name="retry_on_timeout",
            condition=lambda ctx: (
                ctx.task_context and
                ctx.task_context.last_error_type == "timeout" and
                ctx.task_context.can_retry
            ),
            action="retry",
            params={"delay": 2.0},
            priority=70,
            confidence=0.8,
            description="Retry on timeout errors",
        ))

        engine.add_rule(Rule(
            name="retry_on_connection",
            condition=lambda ctx: (
                ctx.task_context and
                ctx.task_context.last_error_type == "connection" and
                ctx.task_context.can_retry
            ),
            action="retry",
            params={"delay": 1.5},
            priority=70,
            confidence=0.8,
            description="Retry on connection errors",
        ))

        engine.add_rule(Rule(
            name="pause_on_critical",
            condition=lambda ctx: ctx.success_rate < 0.3,
            action="pause",
            params={"duration": 30},
            priority=50,
            confidence=0.9,
            description="Pause operations when success rate is critical",
        ))

        engine.add_rule(Rule(
            name="proceed_default",
            condition=lambda ctx: True,
            action="proceed",
            priority=0,
            confidence=0.5,
            description="Default: proceed with operation",
        ))

        return engine
