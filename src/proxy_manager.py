"""
Proxy Manager - SmartProxy ISP rotation with health checking
"""
import asyncio
import random
import time
from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING
from loguru import logger

try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False

if TYPE_CHECKING:
    from .sense import EventBus, MetricsCollector

from .proxy_provider import (
    ProxyProvider,
    ProxyConfig,
    SmartProxyISPBackend,
)


@dataclass
class ProxyStats:
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_response_time: float = 0.0
    last_used: float = field(default_factory=time.time)
    last_health_check: float = 0.0
    is_healthy: bool = True
    consecutive_failures: int = 0

    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 1.0
        return self.successful_requests / self.total_requests

    @property
    def avg_response_time(self) -> float:
        if self.successful_requests == 0:
            return float('inf')
        return self.total_response_time / self.successful_requests

    @property
    def health_score(self) -> float:
        """Calculate health score (0.0 - 1.0) based on success rate and response time"""
        if not self.is_healthy:
            return 0.0
        if self.total_requests == 0:
            return 1.0

        # Weight: 70% success rate, 30% response time score
        success_score = self.success_rate * 0.7

        # Response time score (faster = better, cap at 10s)
        avg_time = self.avg_response_time
        if avg_time == float('inf'):
            time_score = 0.0
        else:
            time_score = max(0, (10.0 - min(avg_time, 10.0)) / 10.0) * 0.3

        return success_score + time_score


class ProxyManager:
    """Manages SmartProxy ISP rotation with health checking"""

    HEALTH_CHECK_URL = "https://httpbin.org/ip"
    HEALTH_CHECK_TIMEOUT = 10.0
    HEALTH_CHECK_INTERVAL = 300.0  # 5 minutes
    MAX_CONSECUTIVE_FAILURES = 3
    UNHEALTHY_COOLDOWN = 60.0  # 1 minute cooldown for unhealthy proxies

    def __init__(
        self,
        backend: Optional[SmartProxyISPBackend] = None,
        area: str = "us",
        event_bus: Optional["EventBus"] = None,
        metrics_collector: Optional["MetricsCollector"] = None,
    ):
        if not backend:
            raise ValueError("SmartProxyISPBackend required")

        self._backend = backend
        self.area = area
        self._session_counter = 0
        self._stats: dict[str, ProxyStats] = {}
        self._event_bus = event_bus
        self._metrics = metrics_collector

        logger.info(f"ProxyManager initialized: provider=smartproxy, area={area}")

    @property
    def backend(self) -> SmartProxyISPBackend:
        return self._backend

    @property
    def provider_name(self) -> str:
        return self._backend.provider_name.value

    def _get_or_create_stats(self, key: str) -> ProxyStats:
        """Get or create stats for a proxy configuration"""
        if key not in self._stats:
            self._stats[key] = ProxyStats()
        return self._stats[key]

    def get_proxy(
        self,
        worker_id: Optional[int] = None,
        country: Optional[str] = None,
        new_session: bool = True,
    ) -> ProxyConfig:
        """Get a proxy configuration with unique session ID per worker"""
        session_id = None
        if new_session:
            if worker_id is not None:
                session_id = f"w{worker_id}_{random.randint(1000, 9999)}"
            else:
                self._session_counter += 1
                session_id = f"sess{self._session_counter}_{random.randint(1000, 9999)}"

        use_country = country or self.area

        proxy = self._backend.create_proxy(
            country=use_country,
            session_id=session_id,
        )

        stats_key = f"smartproxy_{use_country}"
        stats = self._get_or_create_stats(stats_key)
        stats.last_used = time.time()

        logger.debug(
            f"Created proxy config: provider=smartproxy, "
            f"country={proxy.country}, session={proxy.session_id}"
        )
        return proxy

    def get_rotating_proxy_url(self) -> str:
        """Get a simple rotating proxy URL"""
        return self._backend.get_rotating_url()

    def record_success(self, session_id: str, response_time: float = 0.0, country: Optional[str] = None) -> None:
        """Record successful request with response time"""
        if session_id not in self._stats:
            self._stats[session_id] = ProxyStats()

        stats = self._stats[session_id]
        stats.total_requests += 1
        stats.successful_requests += 1
        stats.total_response_time += response_time
        stats.consecutive_failures = 0
        stats.is_healthy = True

        if country:
            country_key = f"smartproxy_{country}"
            country_stats = self._get_or_create_stats(country_key)
            country_stats.total_requests += 1
            country_stats.successful_requests += 1
            country_stats.total_response_time += response_time
            country_stats.consecutive_failures = 0
            country_stats.is_healthy = True

        if self._metrics:
            self._metrics.record("proxy.request.success", 1.0, {"country": country or "unknown"})
            self._metrics.record("proxy.response_time", response_time, {"country": country or "unknown"})

        if self._event_bus:
            from .sense import Event
            event = Event(
                event_type="proxy.success",
                source="proxy_manager",
                data={
                    "session_id": session_id,
                    "country": country,
                    "response_time": response_time,
                },
            )
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._event_bus.publish(event))
            except RuntimeError:
                pass

    def record_failure(self, session_id: str, country: Optional[str] = None, error: Optional[str] = None) -> None:
        """Record failed request"""
        if session_id not in self._stats:
            self._stats[session_id] = ProxyStats()

        stats = self._stats[session_id]
        stats.total_requests += 1
        stats.failed_requests += 1
        stats.consecutive_failures += 1

        if stats.consecutive_failures >= self.MAX_CONSECUTIVE_FAILURES:
            stats.is_healthy = False
            logger.warning(f"Proxy {session_id} marked unhealthy after {stats.consecutive_failures} failures")

        if country:
            country_key = f"smartproxy_{country}"
            country_stats = self._get_or_create_stats(country_key)
            country_stats.total_requests += 1
            country_stats.failed_requests += 1
            country_stats.consecutive_failures += 1

            if country_stats.consecutive_failures >= self.MAX_CONSECUTIVE_FAILURES:
                country_stats.is_healthy = False
                logger.warning(f"Country {country} marked unhealthy")

        if self._metrics:
            self._metrics.record("proxy.request.failure", 1.0, {"country": country or "unknown"})

        if self._event_bus:
            from .sense import Event
            event = Event(
                event_type="proxy.failure",
                source="proxy_manager",
                data={
                    "session_id": session_id,
                    "country": country,
                    "error": error,
                    "consecutive_failures": stats.consecutive_failures,
                },
            )
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._event_bus.publish(event))
            except RuntimeError:
                pass

    async def health_check(self, proxy_config: Optional[ProxyConfig] = None) -> bool:
        """Perform health check on a proxy configuration"""
        if not HAS_AIOHTTP:
            logger.warning("aiohttp not available, skipping health check")
            return True

        if proxy_config is None:
            proxy_config = self.get_proxy(new_session=True)

        proxy_url = proxy_config.get_url()
        stats_key = f"smartproxy_{proxy_config.country or 'unknown'}"
        stats = self._get_or_create_stats(stats_key)

        start_time = time.time()
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.HEALTH_CHECK_URL,
                    proxy=proxy_url,
                    timeout=aiohttp.ClientTimeout(total=self.HEALTH_CHECK_TIMEOUT),
                ) as response:
                    response_time = time.time() - start_time

                    if response.status == 200:
                        stats.last_health_check = time.time()
                        stats.is_healthy = True
                        stats.consecutive_failures = 0
                        logger.info(
                            f"Health check passed: {proxy_config.country} "
                            f"({response_time:.2f}s)"
                        )
                        return True
                    else:
                        logger.warning(
                            f"Health check failed: {proxy_config.country} "
                            f"status={response.status}"
                        )
                        stats.consecutive_failures += 1
                        if stats.consecutive_failures >= self.MAX_CONSECUTIVE_FAILURES:
                            stats.is_healthy = False
                        return False

        except asyncio.TimeoutError:
            logger.warning(f"Health check timeout: {proxy_config.country}")
            stats.consecutive_failures += 1
            if stats.consecutive_failures >= self.MAX_CONSECUTIVE_FAILURES:
                stats.is_healthy = False
            return False
        except Exception as e:
            logger.error(f"Health check error: {proxy_config.country} - {e}")
            stats.consecutive_failures += 1
            if stats.consecutive_failures >= self.MAX_CONSECUTIVE_FAILURES:
                stats.is_healthy = False
            return False

    async def health_check_all(self) -> dict[str, bool]:
        """Perform health check on area proxy"""
        results = {}
        proxy_config = self._backend.create_proxy(country=self.area)
        results[self.area] = await self.health_check(proxy_config)

        healthy_count = sum(1 for v in results.values() if v)
        logger.info(f"Health check complete: {healthy_count}/{len(results)} healthy")
        return results

    def get_stats(self) -> dict[str, ProxyStats]:
        """Get all proxy stats"""
        return self._stats.copy()

    def get_health_summary(self) -> dict:
        """Get summary of proxy health status"""
        stats_key = f"smartproxy_{self.area}"
        stats = self._get_or_create_stats(stats_key)

        summary = {
            "provider": "smartproxy",
            "area": self.area,
            "healthy": 1 if stats.is_healthy else 0,
            "unhealthy": 0 if stats.is_healthy else 1,
            "stats": {
                "healthy": stats.is_healthy,
                "success_rate": f"{stats.success_rate:.1%}",
                "avg_response_time": f"{stats.avg_response_time:.2f}s" if stats.avg_response_time != float('inf') else "N/A",
                "health_score": f"{stats.health_score:.2f}",
            },
        }

        return summary
