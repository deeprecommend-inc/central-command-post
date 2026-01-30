"""
Rate Limiter - Token bucket rate limiting for request throttling
"""
import asyncio
import time
from dataclasses import dataclass, field
from typing import Optional
from loguru import logger


@dataclass
class RateLimiterConfig:
    """Configuration for rate limiter"""
    requests_per_second: float = 1.0  # Max requests per second
    burst_size: int = 5  # Max burst size (tokens)
    enabled: bool = True


class TokenBucketRateLimiter:
    """
    Token bucket rate limiter for controlling request rate.

    Example:
        limiter = TokenBucketRateLimiter(requests_per_second=2.0, burst_size=5)
        async with limiter:
            await make_request()
    """

    def __init__(
        self,
        requests_per_second: float = 1.0,
        burst_size: int = 5,
        enabled: bool = True,
    ):
        self.requests_per_second = requests_per_second
        self.burst_size = burst_size
        self.enabled = enabled

        self._tokens = float(burst_size)
        self._last_update = time.monotonic()
        self._lock = asyncio.Lock()

        # Stats
        self._total_requests = 0
        self._total_wait_time = 0.0

    async def acquire(self) -> float:
        """
        Acquire a token, waiting if necessary.
        Returns the time waited in seconds.
        """
        if not self.enabled:
            self._total_requests += 1
            return 0.0

        async with self._lock:
            wait_time = 0.0

            # Refill tokens based on elapsed time
            now = time.monotonic()
            elapsed = now - self._last_update
            self._tokens = min(
                self.burst_size,
                self._tokens + elapsed * self.requests_per_second
            )
            self._last_update = now

            # Wait if no tokens available
            if self._tokens < 1:
                wait_time = (1 - self._tokens) / self.requests_per_second
                logger.debug(f"Rate limited: waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time)

                # Refill after wait
                self._tokens = min(
                    self.burst_size,
                    self._tokens + wait_time * self.requests_per_second
                )

            # Consume one token
            self._tokens -= 1

            self._total_requests += 1
            self._total_wait_time += wait_time

            return wait_time

    async def __aenter__(self):
        """Context manager entry - acquire token"""
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        return None

    def get_stats(self) -> dict:
        """Get rate limiter statistics"""
        return {
            "enabled": self.enabled,
            "requests_per_second": self.requests_per_second,
            "burst_size": self.burst_size,
            "current_tokens": self._tokens,
            "total_requests": self._total_requests,
            "total_wait_time": f"{self._total_wait_time:.2f}s",
            "avg_wait_time": f"{self._total_wait_time / max(1, self._total_requests):.3f}s",
        }

    def reset(self) -> None:
        """Reset the rate limiter"""
        self._tokens = float(self.burst_size)
        self._last_update = time.monotonic()
        self._total_requests = 0
        self._total_wait_time = 0.0


class DomainRateLimiter:
    """
    Per-domain rate limiting to respect different site's rate limits.

    Example:
        limiter = DomainRateLimiter(default_rps=1.0)
        limiter.set_domain_limit("api.example.com", 5.0)

        async with limiter.for_url("https://api.example.com/data"):
            await fetch_data()
    """

    def __init__(
        self,
        default_rps: float = 1.0,
        default_burst: int = 5,
        enabled: bool = True,
    ):
        self.default_rps = default_rps
        self.default_burst = default_burst
        self.enabled = enabled
        self._limiters: dict[str, TokenBucketRateLimiter] = {}
        self._domain_configs: dict[str, tuple[float, int]] = {}

    def set_domain_limit(
        self,
        domain: str,
        requests_per_second: float,
        burst_size: Optional[int] = None,
    ) -> None:
        """Set rate limit for specific domain"""
        self._domain_configs[domain] = (
            requests_per_second,
            burst_size or self.default_burst,
        )
        # Update existing limiter if present
        if domain in self._limiters:
            limiter = self._limiters[domain]
            limiter.requests_per_second = requests_per_second
            if burst_size:
                limiter.burst_size = burst_size

    def _get_domain(self, url: str) -> str:
        """Extract domain from URL"""
        from urllib.parse import urlparse
        try:
            parsed = urlparse(url)
            return parsed.netloc or url
        except Exception:
            return url

    def _get_limiter(self, domain: str) -> TokenBucketRateLimiter:
        """Get or create rate limiter for domain"""
        if domain not in self._limiters:
            rps, burst = self._domain_configs.get(
                domain,
                (self.default_rps, self.default_burst)
            )
            self._limiters[domain] = TokenBucketRateLimiter(
                requests_per_second=rps,
                burst_size=burst,
                enabled=self.enabled,
            )
        return self._limiters[domain]

    def for_url(self, url: str) -> TokenBucketRateLimiter:
        """Get rate limiter for URL"""
        domain = self._get_domain(url)
        return self._get_limiter(domain)

    def for_domain(self, domain: str) -> TokenBucketRateLimiter:
        """Get rate limiter for domain"""
        return self._get_limiter(domain)

    def get_stats(self) -> dict:
        """Get stats for all domains"""
        return {
            "enabled": self.enabled,
            "default_rps": self.default_rps,
            "default_burst": self.default_burst,
            "domains": {
                domain: limiter.get_stats()
                for domain, limiter in self._limiters.items()
            },
        }

    def reset_all(self) -> None:
        """Reset all rate limiters"""
        for limiter in self._limiters.values():
            limiter.reset()
