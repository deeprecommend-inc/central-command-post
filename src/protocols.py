"""
CCP v2 Protocol Interfaces

Domain-agnostic interfaces for cross-domain deployment.
Implementing these protocols enables:
- Military C2
- Plant/OT Control
- Financial Trading/Risk
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol, runtime_checkable
from enum import Enum

from .learn.experience_store import StateSnapshot, Action, Outcome


# =============================================================================
# Authorization & Safety
# =============================================================================

class AuthorizationStatus(Enum):
    """Authorization decision status"""
    APPROVED = "approved"
    DENIED = "denied"
    REQUIRES_HUMAN = "requires_human"
    THROTTLED = "throttled"


@dataclass
class Authorization:
    """Authorization decision with audit trail"""
    status: AuthorizationStatus
    reason: str
    risk_score: float = 0.0
    constraints: list[str] = field(default_factory=list)
    expires_at: datetime | None = None
    audit_id: str = ""


@dataclass
class Plan:
    """Sequence of actions to achieve a goal"""
    plan_id: str
    goal: str
    actions: list[Action]
    constraints: list[str] = field(default_factory=list)
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class SafetyPolicy(Protocol):
    """
    Protocol for domain-specific safety policies.

    Military: ROE, engagement rules, civilian protection
    Plant: Operating limits, safety interlocks
    Finance: Risk limits, compliance rules
    """

    def authorize(self, plan: Plan, state: StateSnapshot) -> Authorization:
        """Authorize a plan given current state"""
        ...

    def risk_score(self, plan: Plan, state: StateSnapshot) -> float:
        """Compute risk score for a plan (0.0 = safe, 1.0 = maximum risk)"""
        ...

    def kill_switch(self) -> bool:
        """Emergency stop - returns True if system should halt"""
        ...


# =============================================================================
# Domain Adapter
# =============================================================================

@runtime_checkable
class DomainAdapter(Protocol):
    """
    Protocol for domain-specific execution adapters.

    Military: Sensor integration, C2 systems
    Plant: SCADA, DCS, PLC interfaces
    Finance: Trading APIs, market data feeds
    """

    async def execute(self, action: Action) -> Outcome:
        """Execute an action and return outcome"""
        ...

    async def observe(self) -> StateSnapshot:
        """Get current state observation"""
        ...

    def capabilities(self) -> list[str]:
        """List available action types"""
        ...

    def constraints(self) -> list[str]:
        """List domain constraints"""
        ...


# =============================================================================
# Reward Model
# =============================================================================

@runtime_checkable
class RewardModel(Protocol):
    """
    Protocol for domain-specific reward computation.

    Military: Threat reduction, civilian safety, mission success
    Plant: Uptime, quality, energy efficiency
    Finance: Risk-adjusted return, drawdown
    """

    def compute(self, state: StateSnapshot, action: Action, outcome: Outcome) -> float:
        """Compute reward for (state, action, outcome) tuple"""
        ...


# =============================================================================
# Policy & Planning
# =============================================================================

@dataclass
class Decision:
    """Decision output from policy"""
    action: Action
    confidence: float
    reasoning: str = ""
    alternatives: list[Action] = field(default_factory=list)


@dataclass
class DecisionContext:
    """Context for decision making"""
    state: StateSnapshot
    goal: str | None = None
    constraints: list[str] = field(default_factory=list)
    history: list[tuple[Action, Outcome]] = field(default_factory=list)


@runtime_checkable
class Policy(Protocol):
    """
    Protocol for decision policies.

    Can be implemented as:
    - Rule-based (RulesEngine)
    - LLM-based
    - RL/Bandit-based
    - Hybrid
    """

    def decide(self, context: DecisionContext) -> Decision:
        """Make a decision given context"""
        ...

    def update(self, state: StateSnapshot, action: Action, outcome: Outcome, reward: float) -> None:
        """Update policy based on experience (for learning policies)"""
        ...


@runtime_checkable
class Planner(Protocol):
    """
    Protocol for action planning.

    Generates sequences of actions to achieve goals.
    """

    def plan(self, goal: str, state: StateSnapshot, constraints: list[str] | None = None) -> Plan:
        """Generate a plan to achieve goal from current state"""
        ...

    def replan(self, plan: Plan, state: StateSnapshot, failure_reason: str) -> Plan:
        """Replan after failure"""
        ...


# =============================================================================
# Evaluator
# =============================================================================

@dataclass
class EvaluationResult:
    """Result of policy/plan evaluation"""
    policy_id: str
    total_episodes: int
    success_rate: float
    avg_reward: float
    avg_duration_ms: float
    metrics: dict[str, float] = field(default_factory=dict)


@runtime_checkable
class Evaluator(Protocol):
    """Protocol for policy/plan evaluation"""

    def evaluate(
        self,
        policy: Policy,
        episodes: int,
        initial_state: StateSnapshot | None = None,
    ) -> EvaluationResult:
        """Evaluate a policy over multiple episodes"""
        ...

    def compare(
        self,
        policies: list[Policy],
        episodes: int,
    ) -> list[EvaluationResult]:
        """Compare multiple policies"""
        ...
