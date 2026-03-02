"""
Human Timing Utilities - Generate human-like delays for browser automation.

Pure functions producing natural timing distributions that satisfy HumanScoreTracker thresholds:
  - H_T1 (Event Interval CV >= 0.20): Log-normal distribution gives CV ~0.53
  - H_G1 (Action Speed <= 20/min): action_throttle rate-limits to ~18/min
  - H_E1 (Dwell Skewness): Gamma distribution for natural page dwell
"""
import asyncio
import math
import random


def random_delay(min_s: float = 0.5, max_s: float = 3.0) -> float:
    """
    Generate a human-like delay using log-normal distribution.

    The log-normal distribution naturally produces right-skewed timing
    with high coefficient of variation (~0.53), satisfying H_T1 >= 0.20.

    Returns:
        Delay in seconds, clamped to [min_s, max_s].
    """
    # Log-normal with mu=0, sigma=0.5 gives CV ~0.53
    mu = 0.0
    sigma = 0.5
    midpoint = (min_s + max_s) / 2
    raw = random.lognormvariate(mu, sigma) * midpoint
    return max(min_s, min(raw, max_s))


def action_throttle(action_count: int, elapsed_s: float) -> float:
    """
    Rate limiter targeting ~18 actions per minute (H_G1 <= 20).

    Returns additional delay needed to stay under the target rate.
    Returns 0.0 if already within limits.
    """
    target_rate = 18.0  # actions per minute
    if action_count <= 0 or elapsed_s <= 0:
        return 0.0
    current_rate = (action_count / elapsed_s) * 60.0
    if current_rate <= target_rate:
        return 0.0
    # Time needed for the rate to drop to target
    needed_elapsed = (action_count / target_rate) * 60.0
    return max(0.0, needed_elapsed - elapsed_s)


def dwell_time(base_s: float = 3.0) -> float:
    """
    Generate natural page dwell time using Gamma distribution.

    Gamma(shape=2, scale=base_s/2) produces right-skewed dwell times
    with a minimum floor, suitable for H_E1 dwell skewness metric.

    Returns:
        Dwell time in seconds, minimum 1.0s.
    """
    shape = 2.0
    scale = base_s / shape
    return max(1.0, random.gammavariate(shape, scale))


async def human_sleep(min_s: float = 0.5, max_s: float = 3.0) -> float:
    """
    Async convenience wrapper: sleep for a human-like duration.

    Returns the actual delay used.
    """
    delay = random_delay(min_s, max_s)
    await asyncio.sleep(delay)
    return delay
