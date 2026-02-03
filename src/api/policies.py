"""
API Policies - Policy implementations for replay simulation
"""
from __future__ import annotations

from ..learn import ReplayEngine, StateSnapshot, Action, Outcome, OutcomeStatus
from ..protocols import Policy, DecisionContext, Decision


class DefaultPolicy:
    """Default policy that chooses best historical action"""
    id = "default"

    def __init__(self, engine: ReplayEngine):
        self._stats = engine.get_action_statistics()
        self._best_action = self._find_best_action()

    def _find_best_action(self) -> str:
        if not self._stats:
            return "navigate"
        best = max(self._stats.items(), key=lambda x: x[1].get("success_rate", 0))
        return best[0]

    def decide(self, context: DecisionContext) -> Decision:
        return Decision(
            action=Action(action_type=self._best_action, params={}),
            confidence=0.9,
            reasoning=f"Best historical action: {self._best_action}",
        )

    def update(self, state, action, outcome, reward):
        pass


class RandomPolicy:
    """Random policy for baseline comparison"""
    id = "random"

    def __init__(self, action_types: list[str]):
        self._action_types = action_types or ["navigate"]

    def decide(self, context: DecisionContext) -> Decision:
        import random
        action_type = random.choice(self._action_types)
        return Decision(
            action=Action(action_type=action_type, params={}),
            confidence=0.5,
            reasoning="Random selection",
        )

    def update(self, state, action, outcome, reward):
        pass


class GreedyPolicy:
    """Greedy policy that avoids recently failed actions"""
    id = "greedy"

    def __init__(self, action_types: list[str]):
        self._action_types = action_types or ["navigate"]
        self._scores: dict[str, float] = {a: 1.0 for a in self._action_types}

    def decide(self, context: DecisionContext) -> Decision:
        # Choose action with highest score
        best_action = max(self._action_types, key=lambda a: self._scores.get(a, 0))
        return Decision(
            action=Action(action_type=best_action, params={}),
            confidence=self._scores.get(best_action, 0.5),
            reasoning=f"Greedy selection: {best_action}",
        )

    def update(self, state, action, outcome, reward):
        action_type = action.action_type
        if action_type in self._scores:
            # Exponential moving average
            alpha = 0.3
            self._scores[action_type] = (1 - alpha) * self._scores[action_type] + alpha * reward


class EpsilonGreedyPolicy:
    """Epsilon-greedy policy for exploration/exploitation balance"""
    id = "epsilon-greedy"

    def __init__(self, action_types: list[str], epsilon: float = 0.1):
        self._action_types = action_types or ["navigate"]
        self._epsilon = epsilon
        self._scores: dict[str, float] = {a: 1.0 for a in self._action_types}

    def decide(self, context: DecisionContext) -> Decision:
        import random

        if random.random() < self._epsilon:
            # Explore
            action_type = random.choice(self._action_types)
            reasoning = "Exploration"
        else:
            # Exploit
            action_type = max(self._action_types, key=lambda a: self._scores.get(a, 0))
            reasoning = "Exploitation"

        return Decision(
            action=Action(action_type=action_type, params={}),
            confidence=self._scores.get(action_type, 0.5),
            reasoning=reasoning,
        )

    def update(self, state, action, outcome, reward):
        action_type = action.action_type
        if action_type in self._scores:
            alpha = 0.3
            self._scores[action_type] = (1 - alpha) * self._scores[action_type] + alpha * reward


def create_policy(policy_name: str, engine: ReplayEngine) -> Policy:
    """Factory function to create policies by name"""
    stats = engine.get_action_statistics()
    action_types = list(stats.keys()) or ["navigate"]

    policies = {
        "default": lambda: DefaultPolicy(engine),
        "random": lambda: RandomPolicy(action_types),
        "greedy": lambda: GreedyPolicy(action_types),
        "epsilon-greedy": lambda: EpsilonGreedyPolicy(action_types),
    }

    factory = policies.get(policy_name.lower())
    if factory is None:
        raise ValueError(f"Unknown policy: {policy_name}. Available: {list(policies.keys())}")

    return factory()
