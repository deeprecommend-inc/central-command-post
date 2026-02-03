"""
Replay Engine - Simulation and policy evaluation for CCP v2

Enables:
- Replay past experiences with different policies
- A/B testing of strategies
- Offline policy improvement
- What-if analysis
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Awaitable
import asyncio
import json
from pathlib import Path

from .experience_store import (
    ExperienceStore,
    Experience,
    StateSnapshot,
    Action,
    Outcome,
    OutcomeStatus,
)
from ..protocols import Policy, Planner, EvaluationResult


@dataclass
class ReplayConfig:
    """Configuration for replay execution"""
    max_steps: int = 100
    timeout_seconds: float = 30.0
    record_traces: bool = True
    parallel_episodes: int = 1


@dataclass
class StepTrace:
    """Trace of a single replay step"""
    step: int
    state: StateSnapshot
    action: Action
    outcome: Outcome
    reward: float
    policy_decision: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "step": self.step,
            "state": self.state.to_dict(),
            "action": self.action.to_dict(),
            "outcome": self.outcome.to_dict(),
            "reward": self.reward,
            "policy_decision": self.policy_decision,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class EpisodeResult:
    """Result of a single replay episode"""
    episode_id: str
    policy_id: str
    total_steps: int
    total_reward: float
    success: bool
    duration_ms: float
    traces: list[StepTrace] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def avg_reward_per_step(self) -> float:
        return self.total_reward / self.total_steps if self.total_steps > 0 else 0.0

    def to_dict(self) -> dict:
        return {
            "episode_id": self.episode_id,
            "policy_id": self.policy_id,
            "total_steps": self.total_steps,
            "total_reward": self.total_reward,
            "success": self.success,
            "duration_ms": self.duration_ms,
            "avg_reward_per_step": self.avg_reward_per_step,
            "traces": [t.to_dict() for t in self.traces] if self.traces else [],
            "metadata": self.metadata,
        }


class SimulatedEnvironment:
    """
    Simulated environment for replay.
    Uses recorded experiences to simulate outcomes.
    """

    def __init__(self, experience_store: ExperienceStore):
        self._store = experience_store
        self._action_outcomes: dict[str, list[Outcome]] = {}
        self._build_outcome_model()

    def _build_outcome_model(self) -> None:
        """Build outcome probability model from experiences"""
        for exp in self._store:
            action_key = self._action_key(exp.action)
            if action_key not in self._action_outcomes:
                self._action_outcomes[action_key] = []
            self._action_outcomes[action_key].append(exp.outcome)

    def _action_key(self, action: Action) -> str:
        """Generate key for action lookup"""
        return f"{action.action_type}:{json.dumps(action.params, sort_keys=True)}"

    def simulate_outcome(self, state: StateSnapshot, action: Action) -> Outcome:
        """
        Simulate outcome for an action based on historical data.
        Falls back to probabilistic model if exact match not found.
        """
        action_key = self._action_key(action)

        if action_key in self._action_outcomes:
            # Use historical outcomes for this exact action
            outcomes = self._action_outcomes[action_key]
            # Weight by recency (newer outcomes more likely)
            import random
            weights = list(range(1, len(outcomes) + 1))
            return random.choices(outcomes, weights=weights, k=1)[0]

        # Fallback: simulate based on action type statistics
        action_type = action.action_type
        type_outcomes = [
            exp.outcome
            for exp in self._store.query_by_action(action_type)
        ]

        if type_outcomes:
            import random
            return random.choice(type_outcomes)

        # Default outcome if no historical data
        return Outcome(
            status=OutcomeStatus.SUCCESS,
            result={},
            duration_ms=100.0,
        )

    def get_success_rate(self, action_type: str) -> float:
        """Get historical success rate for action type"""
        experiences = self._store.query_by_action(action_type)
        if not experiences:
            return 0.5  # Default
        successes = sum(1 for e in experiences if e.is_success)
        return successes / len(experiences)


class ReplayEngine:
    """
    Engine for replaying experiences and evaluating policies.

    Usage:
        engine = ReplayEngine(experience_store)

        # Replay with a policy
        result = await engine.replay(policy, episodes=10)

        # Compare policies
        comparison = await engine.compare_policies([policy_a, policy_b])

        # Replay from file
        result = await engine.replay_from_file("logs/session.json", policy)
    """

    def __init__(
        self,
        experience_store: ExperienceStore,
        reward_calculator: Callable[[StateSnapshot, Action, Outcome], float] | None = None,
    ):
        self._store = experience_store
        self._env = SimulatedEnvironment(experience_store)
        self._reward_calc = reward_calculator or self._default_reward

    def _default_reward(self, state: StateSnapshot, action: Action, outcome: Outcome) -> float:
        """Default reward calculation"""
        reward_map = {
            OutcomeStatus.SUCCESS: 1.0,
            OutcomeStatus.PARTIAL: 0.5,
            OutcomeStatus.FAILURE: -1.0,
            OutcomeStatus.TIMEOUT: -0.5,
            OutcomeStatus.CANCELLED: 0.0,
        }
        return reward_map.get(outcome.status, 0.0)

    async def replay(
        self,
        policy: Policy,
        episodes: int = 10,
        config: ReplayConfig | None = None,
        initial_states: list[StateSnapshot] | None = None,
    ) -> EvaluationResult:
        """
        Replay experiences with a given policy.

        Args:
            policy: Policy to evaluate
            episodes: Number of episodes to run
            config: Replay configuration
            initial_states: Optional list of starting states

        Returns:
            EvaluationResult with aggregated metrics
        """
        config = config or ReplayConfig()
        results: list[EpisodeResult] = []

        # Get initial states from experiences if not provided
        if initial_states is None:
            recent = self._store.get_recent(episodes * 2)
            initial_states = [e.state for e in recent[:episodes]] if recent else []

        # Ensure we have enough initial states
        while len(initial_states) < episodes:
            if initial_states:
                initial_states.append(initial_states[0])
            else:
                initial_states.append(StateSnapshot(
                    timestamp=datetime.now(),
                    features={},
                ))

        # Run episodes
        for i in range(episodes):
            result = await self._run_episode(
                policy=policy,
                episode_id=f"ep-{i}",
                initial_state=initial_states[i],
                config=config,
            )
            results.append(result)

        # Aggregate results
        return self._aggregate_results(
            policy_id=getattr(policy, 'id', str(type(policy).__name__)),
            results=results,
        )

    async def _run_episode(
        self,
        policy: Policy,
        episode_id: str,
        initial_state: StateSnapshot,
        config: ReplayConfig,
    ) -> EpisodeResult:
        """Run a single replay episode"""
        start_time = datetime.now()
        traces: list[StepTrace] = []
        total_reward = 0.0
        current_state = initial_state
        success = True

        for step in range(config.max_steps):
            # Get policy decision
            from ..protocols import DecisionContext as PolicyContext
            context = PolicyContext(
                state=current_state,
                history=[(t.action, t.outcome) for t in traces[-5:]],  # Last 5 actions
            )

            try:
                decision = policy.decide(context)
                action = decision.action
            except Exception as e:
                # Policy failed
                success = False
                break

            # Simulate outcome
            outcome = self._env.simulate_outcome(current_state, action)
            reward = self._reward_calc(current_state, action, outcome)
            total_reward += reward

            # Record trace
            if config.record_traces:
                traces.append(StepTrace(
                    step=step,
                    state=current_state,
                    action=action,
                    outcome=outcome,
                    reward=reward,
                    policy_decision={
                        "confidence": decision.confidence,
                        "reasoning": decision.reasoning,
                    },
                ))

            # Update policy (for learning policies)
            if hasattr(policy, 'update'):
                policy.update(current_state, action, outcome, reward)

            # Check termination
            if outcome.status == OutcomeStatus.FAILURE:
                success = False
                break

            # Update state for next step (simplified state transition)
            current_state = StateSnapshot(
                timestamp=datetime.now(),
                features={
                    **current_state.features,
                    "last_action": action.action_type,
                    "last_outcome": outcome.status.value,
                },
                context=current_state.context,
            )

        end_time = datetime.now()
        duration_ms = (end_time - start_time).total_seconds() * 1000

        return EpisodeResult(
            episode_id=episode_id,
            policy_id=getattr(policy, 'id', str(type(policy).__name__)),
            total_steps=len(traces),
            total_reward=total_reward,
            success=success,
            duration_ms=duration_ms,
            traces=traces if config.record_traces else [],
        )

    def _aggregate_results(
        self,
        policy_id: str,
        results: list[EpisodeResult],
    ) -> EvaluationResult:
        """Aggregate episode results into evaluation result"""
        if not results:
            return EvaluationResult(
                policy_id=policy_id,
                total_episodes=0,
                success_rate=0.0,
                avg_reward=0.0,
                avg_duration_ms=0.0,
            )

        total_episodes = len(results)
        successes = sum(1 for r in results if r.success)
        total_reward = sum(r.total_reward for r in results)
        total_duration = sum(r.duration_ms for r in results)

        return EvaluationResult(
            policy_id=policy_id,
            total_episodes=total_episodes,
            success_rate=successes / total_episodes,
            avg_reward=total_reward / total_episodes,
            avg_duration_ms=total_duration / total_episodes,
            metrics={
                "total_reward": total_reward,
                "total_steps": sum(r.total_steps for r in results),
                "avg_steps_per_episode": sum(r.total_steps for r in results) / total_episodes,
            },
        )

    async def compare_policies(
        self,
        policies: list[Policy],
        episodes_per_policy: int = 10,
        config: ReplayConfig | None = None,
    ) -> list[EvaluationResult]:
        """
        Compare multiple policies on the same set of experiences.

        Returns list of EvaluationResults sorted by avg_reward (descending).
        """
        results: list[EvaluationResult] = []

        # Use same initial states for fair comparison
        recent = self._store.get_recent(episodes_per_policy * 2)
        initial_states = [e.state for e in recent[:episodes_per_policy]]

        for policy in policies:
            result = await self.replay(
                policy=policy,
                episodes=episodes_per_policy,
                config=config,
                initial_states=initial_states.copy(),
            )
            results.append(result)

        # Sort by avg_reward descending
        results.sort(key=lambda r: r.avg_reward, reverse=True)
        return results

    async def replay_from_file(
        self,
        file_path: str | Path,
        policy: Policy,
        config: ReplayConfig | None = None,
    ) -> EvaluationResult:
        """
        Replay experiences from a JSON file with a given policy.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Replay file not found: {path}")

        # Load experiences
        temp_store = ExperienceStore()
        temp_store.load_from_file(str(path))

        # Create engine with loaded experiences
        engine = ReplayEngine(temp_store, self._reward_calc)

        return await engine.replay(
            policy=policy,
            episodes=len(temp_store),
            config=config,
        )

    def get_action_statistics(self) -> dict[str, dict[str, float]]:
        """Get statistics for each action type"""
        stats: dict[str, dict[str, float]] = {}

        for exp in self._store:
            action_type = exp.action.action_type
            if action_type not in stats:
                stats[action_type] = {
                    "count": 0,
                    "successes": 0,
                    "total_reward": 0.0,
                    "total_duration_ms": 0.0,
                }

            stats[action_type]["count"] += 1
            if exp.is_success:
                stats[action_type]["successes"] += 1
            stats[action_type]["total_reward"] += exp.reward
            stats[action_type]["total_duration_ms"] += exp.outcome.duration_ms

        # Calculate averages
        for action_type, data in stats.items():
            count = data["count"]
            if count > 0:
                data["success_rate"] = data["successes"] / count
                data["avg_reward"] = data["total_reward"] / count
                data["avg_duration_ms"] = data["total_duration_ms"] / count

        return stats


# Convenience function for CLI usage
async def simulate(
    policy: Policy,
    replay_file: str,
    episodes: int = 10,
) -> EvaluationResult:
    """
    Simulate a policy using recorded experiences.

    Usage:
        python -c "
        from src.learn.replay_engine import simulate
        from my_policy import MyPolicy
        import asyncio
        result = asyncio.run(simulate(MyPolicy(), 'logs/session.json'))
        print(result)
        "
    """
    store = ExperienceStore()
    store.load_from_file(replay_file)

    engine = ReplayEngine(store)
    return await engine.replay(policy, episodes=episodes)
