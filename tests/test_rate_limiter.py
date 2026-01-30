"""
Tests for RateLimiter
"""
import pytest
import asyncio
import time
from src.rate_limiter import TokenBucketRateLimiter, DomainRateLimiter


class TestTokenBucketRateLimiter:
    """Tests for TokenBucketRateLimiter"""

    def test_initialization(self):
        limiter = TokenBucketRateLimiter(requests_per_second=2.0, burst_size=5)
        assert limiter.requests_per_second == 2.0
        assert limiter.burst_size == 5
        assert limiter.enabled is True

    def test_disabled_limiter(self):
        limiter = TokenBucketRateLimiter(enabled=False)
        assert limiter.enabled is False

    @pytest.mark.asyncio
    async def test_acquire_no_wait(self):
        limiter = TokenBucketRateLimiter(requests_per_second=10.0, burst_size=5)
        wait_time = await limiter.acquire()
        assert wait_time == 0.0

    @pytest.mark.asyncio
    async def test_acquire_disabled(self):
        limiter = TokenBucketRateLimiter(enabled=False)
        wait_time = await limiter.acquire()
        assert wait_time == 0.0

    @pytest.mark.asyncio
    async def test_burst_allows_multiple(self):
        limiter = TokenBucketRateLimiter(requests_per_second=1.0, burst_size=5)
        # Should allow 5 requests quickly
        for _ in range(5):
            wait_time = await limiter.acquire()
            assert wait_time == 0.0

    @pytest.mark.asyncio
    async def test_context_manager(self):
        limiter = TokenBucketRateLimiter(requests_per_second=10.0)
        async with limiter:
            pass  # Should not raise

    def test_get_stats(self):
        limiter = TokenBucketRateLimiter(requests_per_second=2.0, burst_size=3)
        stats = limiter.get_stats()
        assert stats["enabled"] is True
        assert stats["requests_per_second"] == 2.0
        assert stats["burst_size"] == 3
        assert stats["total_requests"] == 0

    @pytest.mark.asyncio
    async def test_stats_update(self):
        limiter = TokenBucketRateLimiter(requests_per_second=10.0, burst_size=5)
        await limiter.acquire()
        await limiter.acquire()
        stats = limiter.get_stats()
        assert stats["total_requests"] == 2

    def test_reset(self):
        limiter = TokenBucketRateLimiter(burst_size=5)
        limiter._tokens = 0
        limiter._total_requests = 10
        limiter.reset()
        assert limiter._tokens == 5.0
        assert limiter._total_requests == 0


class TestDomainRateLimiter:
    """Tests for DomainRateLimiter"""

    def test_initialization(self):
        limiter = DomainRateLimiter(default_rps=2.0, default_burst=10)
        assert limiter.default_rps == 2.0
        assert limiter.default_burst == 10

    def test_set_domain_limit(self):
        limiter = DomainRateLimiter()
        limiter.set_domain_limit("api.example.com", 5.0, 10)
        # Verify config is stored
        assert "api.example.com" in limiter._domain_configs
        assert limiter._domain_configs["api.example.com"] == (5.0, 10)

    def test_get_domain_from_url(self):
        limiter = DomainRateLimiter()
        assert limiter._get_domain("https://example.com/path") == "example.com"
        assert limiter._get_domain("https://api.example.com:8080/path") == "api.example.com:8080"
        assert limiter._get_domain("http://localhost/test") == "localhost"

    def test_for_url(self):
        limiter = DomainRateLimiter(default_rps=1.0)
        limiter.set_domain_limit("api.example.com", 5.0)

        # Get limiter for configured domain
        api_limiter = limiter.for_url("https://api.example.com/data")
        assert api_limiter.requests_per_second == 5.0

        # Get limiter for unconfigured domain (uses default)
        other_limiter = limiter.for_url("https://other.com/")
        assert other_limiter.requests_per_second == 1.0

    def test_for_domain(self):
        limiter = DomainRateLimiter(default_rps=2.0)
        domain_limiter = limiter.for_domain("test.com")
        assert domain_limiter.requests_per_second == 2.0

    def test_get_stats(self):
        limiter = DomainRateLimiter(default_rps=1.0)
        limiter.for_url("https://a.com/")
        limiter.for_url("https://b.com/")
        stats = limiter.get_stats()
        assert stats["enabled"] is True
        assert "a.com" in stats["domains"]
        assert "b.com" in stats["domains"]

    def test_reset_all(self):
        limiter = DomainRateLimiter()
        l1 = limiter.for_domain("a.com")
        l2 = limiter.for_domain("b.com")
        l1._tokens = 0
        l2._tokens = 0
        limiter.reset_all()
        assert l1._tokens == limiter.default_burst
        assert l2._tokens == limiter.default_burst
