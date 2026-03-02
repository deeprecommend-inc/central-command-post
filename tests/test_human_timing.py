"""
Tests for human_timing module
"""
import asyncio
import math
import pytest
from src.human_timing import random_delay, action_throttle, dwell_time, human_sleep


class TestRandomDelay:
    def test_within_bounds(self):
        for _ in range(100):
            d = random_delay(0.5, 3.0)
            assert 0.5 <= d <= 3.0

    def test_custom_bounds(self):
        for _ in range(50):
            d = random_delay(1.0, 10.0)
            assert 1.0 <= d <= 10.0

    def test_cv_above_threshold(self):
        """CV should be >= 0.20 (H_T1 threshold) over many samples"""
        samples = [random_delay(0.5, 5.0) for _ in range(200)]
        mean = sum(samples) / len(samples)
        variance = sum((x - mean) ** 2 for x in samples) / len(samples)
        cv = math.sqrt(variance) / mean if mean > 0 else 0
        assert cv >= 0.20, f"CV={cv:.4f} < 0.20"

    def test_min_equals_max(self):
        d = random_delay(2.0, 2.0)
        assert d == 2.0


class TestActionThrottle:
    def test_low_rate_no_delay(self):
        # 5 actions in 60s = 5/min, well under 18/min
        delay = action_throttle(5, 60.0)
        assert delay == 0.0

    def test_high_rate_returns_delay(self):
        # 30 actions in 30s = 60/min, way over 18/min
        delay = action_throttle(30, 30.0)
        assert delay > 0.0

    def test_zero_actions(self):
        assert action_throttle(0, 10.0) == 0.0

    def test_zero_elapsed(self):
        assert action_throttle(5, 0.0) == 0.0

    def test_negative_values(self):
        assert action_throttle(-1, 10.0) == 0.0
        assert action_throttle(5, -1.0) == 0.0

    def test_exactly_at_limit(self):
        # 18 actions in 60s = 18/min, exactly at limit
        delay = action_throttle(18, 60.0)
        assert delay == 0.0

    def test_slightly_over_limit(self):
        # 19 actions in 60s = 19/min, just over 18/min
        delay = action_throttle(19, 60.0)
        assert delay > 0.0


class TestDwellTime:
    def test_minimum_value(self):
        for _ in range(100):
            d = dwell_time(3.0)
            assert d >= 1.0

    def test_reasonable_mean(self):
        samples = [dwell_time(3.0) for _ in range(200)]
        mean = sum(samples) / len(samples)
        # Gamma(2, 1.5) has mean=3.0, so we expect around 3.0
        assert 1.5 <= mean <= 6.0, f"Mean dwell={mean:.2f} outside expected range"

    def test_custom_base(self):
        samples = [dwell_time(10.0) for _ in range(100)]
        mean = sum(samples) / len(samples)
        assert mean > 3.0  # Should be noticeably higher than default


class TestHumanSleep:
    @pytest.mark.asyncio
    async def test_returns_delay(self):
        delay = await human_sleep(0.01, 0.05)
        assert 0.01 <= delay <= 0.05

    @pytest.mark.asyncio
    async def test_actually_sleeps(self):
        import time
        start = time.time()
        await human_sleep(0.05, 0.1)
        elapsed = time.time() - start
        assert elapsed >= 0.04  # Allow small timing tolerance
