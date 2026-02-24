"""
Proxy Manager - Multi-provider proxy rotation with health checking

Supported providers:
  - brightdata: BrightData ($4-5/GB residential)
  - dataimpulse: DataImpulse ($1/GB residential, $2/GB mobile)
  - generic: Any HTTP/SOCKS5 proxy URL
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
    ProxyType,
    ProxyConfig,
    ProxyProviderBackend,
    BrightDataBackend,
    DataImpulseBackend,
    GeoNodeBackend,
    GenericProxyBackend,
    create_proxy_backend,
    BRIGHTDATA_COUNTRIES,
    DATAIMPULSE_COUNTRIES,
    GEONODE_COUNTRIES,
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
    """Manages multi-provider proxy rotation with health checking and smart rotation"""

    HEALTH_CHECK_URL = "https://httpbin.org/ip"
    HEALTH_CHECK_TIMEOUT = 10.0
    HEALTH_CHECK_INTERVAL = 300.0  # 5 minutes
    MAX_CONSECUTIVE_FAILURES = 3
    UNHEALTHY_COOLDOWN = 60.0  # 1 minute cooldown for unhealthy proxies

    def __init__(
        self,
        backend: Optional[ProxyProviderBackend] = None,
        # Legacy BrightData-compatible constructor args
        username: str = "",
        password: str = "",
        host: str = "brd.superproxy.io",
        port: int = 22225,
        proxy_type: ProxyType = ProxyType.RESIDENTIAL,
        provider: str = "brightdata",
        proxy_urls: Optional[list[str]] = None,
        event_bus: Optional["EventBus"] = None,
        metrics_collector: Optional["MetricsCollector"] = None,
    ):
        # If backend is provided, use it directly
        if backend:
            self._backend = backend
        elif username and password:
            self._backend = create_proxy_backend(
                provider=provider,
                username=username,
                password=password,
                host=host,
                port=port,
                proxy_urls=proxy_urls,
            )
        elif proxy_urls:
            self._backend = GenericProxyBackend(urls=proxy_urls)
        else:
            raise ValueError("Either backend, credentials, or proxy_urls required")

        self.proxy_type = proxy_type
        self._session_counter = 0
        self._country_index = 0
        self._stats: dict[str, ProxyStats] = {}
        self._event_bus = event_bus
        self._metrics = metrics_collector

        # Backward compat: expose credentials for BrightData/DataImpulse
        self.username = username
        self.password = password
        self.host = host
        self.port = port

        provider_name = self._backend.provider_name.value
        self.COUNTRIES = self._resolve_countries()
        logger.info(f"ProxyManager initialized: provider={provider_name}, type={proxy_type.value}")

    def _resolve_countries(self) -> list[str]:
        """Get country list based on provider"""
        if isinstance(self._backend, BrightDataBackend):
            return BRIGHTDATA_COUNTRIES
        elif isinstance(self._backend, DataImpulseBackend):
            return DATAIMPULSE_COUNTRIES
        elif isinstance(self._backend, GeoNodeBackend):
            return GEONODE_COUNTRIES
        return ["us"]  # generic fallback

    @property
    def backend(self) -> ProxyProviderBackend:
        return self._backend

    @property
    def provider_name(self) -> str:
        return self._backend.provider_name.value

    def _get_next_country(self) -> str:
        """Get next country in round-robin fashion for better distribution"""
        country = self.COUNTRIES[self._country_index]
        self._country_index = (self._country_index + 1) % len(self.COUNTRIES)
        return country

    def _get_stats_key(self, country: str, proxy_type: ProxyType) -> str:
        """Generate stats key for a proxy configuration"""
        return f"{proxy_type.value}_{country}"

    def _get_or_create_stats(self, key: str) -> ProxyStats:
        """Get or create stats for a proxy configuration"""
        if key not in self._stats:
            self._stats[key] = ProxyStats()
        return self._stats[key]

    def get_proxy(
        self,
        country: Optional[str] = None,
        new_session: bool = True,
        proxy_type: Optional[ProxyType] = None,
    ) -> ProxyConfig:
        """Get a proxy configuration with smart country selection"""
        session_id = None
        if new_session:
            self._session_counter += 1
            session_id = f"sess{self._session_counter}_{random.randint(1000, 9999)}"

        use_type = proxy_type or self.proxy_type

        # Smart country selection based on health
        if country is None:
            country = self._select_best_country(use_type)

        proxy = self._backend.create_proxy(
            country=country,
            session_id=session_id,
            proxy_type=use_type,
        )

        # Update last used time
        stats_key = self._get_stats_key(country, use_type)
        stats = self._get_or_create_stats(stats_key)
        stats.last_used = time.time()

        logger.debug(
            f"Created proxy config: provider={self.provider_name}, "
            f"type={use_type.value}, country={proxy.country}, session={proxy.session_id}"
        )
        return proxy

    def _select_best_country(self, proxy_type: ProxyType) -> str:
        """Select best country based on health scores"""
        best_country = None
        best_score = -1.0
        current_time = time.time()

        for country in self.COUNTRIES:
            stats_key = self._get_stats_key(country, proxy_type)
            stats = self._get_or_create_stats(stats_key)

            # Skip unhealthy proxies in cooldown
            if not stats.is_healthy:
                if current_time - stats.last_used < self.UNHEALTHY_COOLDOWN:
                    continue
                # Reset health after cooldown
                stats.is_healthy = True
                stats.consecutive_failures = 0

            score = stats.health_score
            if score > best_score:
                best_score = score
                best_country = country

        # Fallback to round-robin if all unhealthy
        if best_country is None:
            best_country = self._get_next_country()
            logger.warning(f"All proxies unhealthy, falling back to: {best_country}")

        return best_country

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

        # Also update country-level stats if provided
        if country:
            country_key = self._get_stats_key(country, self.proxy_type)
            country_stats = self._get_or_create_stats(country_key)
            country_stats.total_requests += 1
            country_stats.successful_requests += 1
            country_stats.total_response_time += response_time
            country_stats.consecutive_failures = 0
            country_stats.is_healthy = True

        # Record metrics
        if self._metrics:
            self._metrics.record("proxy.request.success", 1.0, {"country": country or "unknown"})
            self._metrics.record("proxy.response_time", response_time, {"country": country or "unknown"})

        # Publish event (async-safe)
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

        # Also update country-level stats if provided
        if country:
            country_key = self._get_stats_key(country, self.proxy_type)
            country_stats = self._get_or_create_stats(country_key)
            country_stats.total_requests += 1
            country_stats.failed_requests += 1
            country_stats.consecutive_failures += 1

            if country_stats.consecutive_failures >= self.MAX_CONSECUTIVE_FAILURES:
                country_stats.is_healthy = False
                logger.warning(f"Country {country} marked unhealthy")

        # Record metrics
        if self._metrics:
            self._metrics.record("proxy.request.failure", 1.0, {"country": country or "unknown"})

        # Publish event (async-safe)
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
        """
        Perform health check on a proxy configuration.
        Returns True if proxy is healthy, False otherwise.
        """
        if not HAS_AIOHTTP:
            logger.warning("aiohttp not available, skipping health check")
            return True

        if proxy_config is None:
            proxy_config = self.get_proxy(new_session=True)

        proxy_url = proxy_config.get_url()
        stats_key = self._get_stats_key(proxy_config.country or "unknown", proxy_config.proxy_type)
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
        """Perform health check on all country proxies"""
        results = {}
        tasks = []

        for country in self.COUNTRIES:
            proxy_config = self._backend.create_proxy(
                country=country,
                proxy_type=self.proxy_type,
            )
            tasks.append((country, self.health_check(proxy_config)))

        for country, task in tasks:
            try:
                results[country] = await task
            except Exception as e:
                logger.error(f"Health check failed for {country}: {e}")
                results[country] = False

        healthy_count = sum(1 for v in results.values() if v)
        logger.info(f"Health check complete: {healthy_count}/{len(results)} healthy")
        return results

    def get_stats(self) -> dict[str, ProxyStats]:
        """Get all proxy stats"""
        return self._stats.copy()

    def get_health_summary(self) -> dict:
        """Get summary of proxy health status"""
        summary = {
            "provider": self.provider_name,
            "total_proxies": len(self.COUNTRIES),
            "healthy": 0,
            "unhealthy": 0,
            "countries": {},
        }

        for country in self.COUNTRIES:
            stats_key = self._get_stats_key(country, self.proxy_type)
            stats = self._get_or_create_stats(stats_key)
            summary["countries"][country] = {
                "healthy": stats.is_healthy,
                "success_rate": f"{stats.success_rate:.1%}",
                "avg_response_time": f"{stats.avg_response_time:.2f}s" if stats.avg_response_time != float('inf') else "N/A",
                "health_score": f"{stats.health_score:.2f}",
            }
            if stats.is_healthy:
                summary["healthy"] += 1
            else:
                summary["unhealthy"] += 1

        return summary
