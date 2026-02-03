#!/usr/bin/env python3
"""
CCP v2 Simulation CLI

Replay experiences with different policies and compare results.

Usage:
    python simulate.py replay <experience_file> [--episodes N]
    python simulate.py compare <experience_file> [--episodes N]
    python simulate.py stats <experience_file>
"""
import asyncio
import sys
import json
from pathlib import Path

from src.learn import (
    ExperienceStore,
    ReplayEngine,
    ReplayConfig,
    StateSnapshot,
    Action,
    Outcome,
    OutcomeStatus,
)
from src.protocols import Policy, DecisionContext, Decision


# =============================================================================
# Sample Policies for Testing
# =============================================================================

class AlwaysSucceedPolicy:
    """Policy that always chooses actions with highest success rate"""
    id = "always-succeed"

    def __init__(self, engine: ReplayEngine):
        self._stats = engine.get_action_statistics()
        self._best_action = self._find_best_action()

    def _find_best_action(self) -> str:
        if not self._stats:
            return "default"
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
    """Policy that randomly chooses from available actions"""
    id = "random"

    def __init__(self, action_types: list[str]):
        self._action_types = action_types or ["default"]

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


class HistoryAwarePolicy:
    """Policy that avoids actions that recently failed"""
    id = "history-aware"

    def __init__(self, action_types: list[str]):
        self._action_types = action_types or ["default"]
        self._recent_failures: dict[str, int] = {}

    def decide(self, context: DecisionContext) -> Decision:
        # Check recent history for failures
        if context.history:
            for action, outcome in context.history[-3:]:
                if outcome.status == OutcomeStatus.FAILURE:
                    self._recent_failures[action.action_type] = \
                        self._recent_failures.get(action.action_type, 0) + 1

        # Choose action with fewest recent failures
        import random
        weights = []
        for action_type in self._action_types:
            failures = self._recent_failures.get(action_type, 0)
            weights.append(max(1, 10 - failures))

        action_type = random.choices(self._action_types, weights=weights, k=1)[0]

        return Decision(
            action=Action(action_type=action_type, params={}),
            confidence=0.7,
            reasoning=f"Avoiding recently failed actions",
        )

    def update(self, state, action, outcome, reward):
        if outcome.status == OutcomeStatus.FAILURE:
            self._recent_failures[action.action_type] = \
                self._recent_failures.get(action.action_type, 0) + 1


# =============================================================================
# CLI Commands
# =============================================================================

async def cmd_replay(file_path: str, episodes: int = 10):
    """Replay experiences with sample policies"""
    print(f"Loading experiences from: {file_path}")
    store = ExperienceStore()

    try:
        count = store.load_from_file(file_path)
        print(f"Loaded {count} experiences")
    except FileNotFoundError:
        print(f"File not found: {file_path}")
        sys.exit(1)

    if len(store) == 0:
        print("No experiences to replay")
        sys.exit(1)

    engine = ReplayEngine(store)

    # Get action types from experiences
    stats = engine.get_action_statistics()
    action_types = list(stats.keys()) or ["default"]

    print(f"Action types found: {action_types}")
    print(f"Running {episodes} episodes...")
    print()

    # Test with AlwaysSucceed policy
    policy = AlwaysSucceedPolicy(engine)
    result = await engine.replay(policy, episodes=episodes)

    print(f"Policy: {result.policy_id}")
    print(f"  Episodes: {result.total_episodes}")
    print(f"  Success Rate: {result.success_rate:.1%}")
    print(f"  Avg Reward: {result.avg_reward:.3f}")
    print(f"  Avg Duration: {result.avg_duration_ms:.1f}ms")
    print()


async def cmd_compare(file_path: str, episodes: int = 10):
    """Compare multiple policies"""
    print(f"Loading experiences from: {file_path}")
    store = ExperienceStore()

    try:
        count = store.load_from_file(file_path)
        print(f"Loaded {count} experiences")
    except FileNotFoundError:
        print(f"File not found: {file_path}")
        sys.exit(1)

    if len(store) == 0:
        print("No experiences to replay")
        sys.exit(1)

    engine = ReplayEngine(store)

    # Get action types
    stats = engine.get_action_statistics()
    action_types = list(stats.keys()) or ["default"]

    # Create policies to compare
    policies = [
        AlwaysSucceedPolicy(engine),
        RandomPolicy(action_types),
        HistoryAwarePolicy(action_types),
    ]

    print(f"Comparing {len(policies)} policies with {episodes} episodes each...")
    print()

    results = await engine.compare_policies(
        policies,
        episodes_per_policy=episodes,
        config=ReplayConfig(max_steps=20),
    )

    print("Results (sorted by avg reward):")
    print("-" * 60)
    print(f"{'Policy':<20} {'Success%':>10} {'Avg Reward':>12} {'Episodes':>10}")
    print("-" * 60)

    for result in results:
        print(f"{result.policy_id:<20} {result.success_rate:>9.1%} {result.avg_reward:>12.3f} {result.total_episodes:>10}")

    print("-" * 60)
    print(f"\nBest policy: {results[0].policy_id}")


def cmd_stats(file_path: str):
    """Show statistics for experience file"""
    print(f"Loading experiences from: {file_path}")
    store = ExperienceStore()

    try:
        count = store.load_from_file(file_path)
        print(f"Loaded {count} experiences")
    except FileNotFoundError:
        print(f"File not found: {file_path}")
        sys.exit(1)

    stats = store.get_statistics()
    print()
    print("Experience Store Statistics:")
    print("-" * 40)
    print(f"Total experiences: {stats['total']}")
    print(f"Success rate: {stats['success_rate']:.1%}")
    print(f"Average reward: {stats['avg_reward']:.3f}")
    print()

    if stats.get("by_action"):
        print("By Action Type:")
        for action, count in stats["by_action"].items():
            print(f"  {action}: {count}")
        print()

    if stats.get("by_status"):
        print("By Status:")
        for status, count in stats["by_status"].items():
            print(f"  {status}: {count}")


def print_usage():
    print("""
CCP v2 Simulation CLI

Usage:
    python simulate.py <command> <experience_file> [options]

Commands:
    replay   - Replay experiences with a sample policy
    compare  - Compare multiple policies
    stats    - Show experience file statistics

Options:
    --episodes N    Number of episodes to run (default: 10)

Examples:
    python simulate.py stats logs/session.json
    python simulate.py replay logs/session.json --episodes 20
    python simulate.py compare logs/session.json --episodes 10

Note:
    Create experience files by running CCP with experience recording enabled,
    or use ExperienceStore.save_to_file() programmatically.
""")


def main():
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(0)

    command = sys.argv[1].lower()
    args = sys.argv[2:]

    # Parse arguments
    file_path = None
    episodes = 10

    i = 0
    while i < len(args):
        if args[i] == "--episodes" and i + 1 < len(args):
            episodes = int(args[i + 1])
            i += 2
        elif not args[i].startswith("--"):
            file_path = args[i]
            i += 1
        else:
            i += 1

    if command in ["replay", "compare", "stats"] and not file_path:
        print(f"Error: {command} requires an experience file path")
        sys.exit(1)

    if command == "replay":
        asyncio.run(cmd_replay(file_path, episodes))
    elif command == "compare":
        asyncio.run(cmd_compare(file_path, episodes))
    elif command == "stats":
        cmd_stats(file_path)
    elif command in ["-h", "--help", "help"]:
        print_usage()
    else:
        print(f"Unknown command: {command}")
        print_usage()
        sys.exit(1)


if __name__ == "__main__":
    main()
