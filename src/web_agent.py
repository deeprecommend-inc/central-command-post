"""
Web Agent - Main interface for web automation with proxy and UA rotation
"""
import asyncio
from typing import Optional, Any, TYPE_CHECKING
from loguru import logger
from pydantic import BaseModel, Field, ConfigDict

from .proxy_manager import ProxyManager
from .proxy_provider import SmartProxyISPBackend
from .ua_manager import UserAgentManager
from .browser_worker import BrowserWorker, WorkerResult
from .parallel_controller import ParallelController, TaskResult

if TYPE_CHECKING:
    from .sense import EventBus, MetricsCollector


class AgentConfig(BaseModel):
    """Configuration for WebAgent with validation"""

    # SmartProxy ISP credentials
    smartproxy_username: str = ""
    smartproxy_password: str = ""
    smartproxy_host: str = "isp.decodo.com"
    smartproxy_port: int = Field(default=10001, ge=1, le=65535)

    # Area/timezone
    area: str = "us"
    no_proxy: bool = False

    # GoLogin fingerprint API token
    gologin_api_token: str = ""

    parallel_sessions: int = Field(default=5, ge=1, le=50)
    headless: bool = True
    max_retries: int = Field(default=3, ge=0, le=10)

    model_config = ConfigDict(extra="forbid")


class WebAgent:
    """
    Web automation agent with proxy rotation and user agent management.

    Supports async context manager for automatic cleanup:

        async with WebAgent(config) as agent:
            result = await agent.navigate("https://example.com")

    Or manual cleanup:

        agent = WebAgent(config)
        try:
            result = await agent.navigate("https://example.com")
        finally:
            await agent.cleanup()
    """

    def __init__(
        self,
        config: Optional[AgentConfig] = None,
        event_bus: Optional["EventBus"] = None,
        metrics_collector: Optional["MetricsCollector"] = None,
    ):
        self.config = config or AgentConfig()
        self._closed = False
        self._event_bus = event_bus
        self._metrics = metrics_collector

        # Initialize proxy manager if credentials provided
        self.proxy_manager = None
        if (
            not self.config.no_proxy
            and self.config.smartproxy_username
            and self.config.smartproxy_password
        ):
            backend = SmartProxyISPBackend(
                username=self.config.smartproxy_username,
                password=self.config.smartproxy_password,
                host=self.config.smartproxy_host,
                port=self.config.smartproxy_port,
            )
            self.proxy_manager = ProxyManager(
                backend=backend,
                area=self.config.area,
                event_bus=event_bus,
                metrics_collector=metrics_collector,
            )
            logger.info(f"Proxy enabled: provider=smartproxy, area={self.config.area}")
        else:
            logger.info("Proxy disabled: direct connection")

        self.ua_manager = UserAgentManager(gologin_token=self.config.gologin_api_token)
        self.controller = ParallelController(
            proxy_manager=self.proxy_manager,
            ua_manager=self.ua_manager,
            max_workers=self.config.parallel_sessions,
            headless=self.config.headless,
            max_retries=self.config.max_retries,
            area=self.config.area,
            event_bus=event_bus,
            metrics_collector=metrics_collector,
        )

    async def __aenter__(self) -> "WebAgent":
        """Async context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit with cleanup"""
        await self.cleanup()
        return None

    async def navigate(self, url: str) -> TaskResult:
        """Navigate to URL with single worker"""
        self._check_closed()

        async def task(worker: BrowserWorker) -> WorkerResult:
            result = await worker.navigate(url)
            if result.success:
                content = await worker.get_content()
                if content.success:
                    result.data = {**result.data, **content.data}
            return result

        return await self.controller.run_task("single", task)

    async def parallel_navigate(self, urls: list[str]) -> list[TaskResult]:
        """Navigate to multiple URLs in parallel"""
        self._check_closed()

        def make_task(url: str):
            async def task(worker: BrowserWorker) -> WorkerResult:
                result = await worker.navigate(url)
                if result.success:
                    content = await worker.get_content()
                    if content.success:
                        result.data = {**result.data, **content.data}
                return result

            return task

        tasks = [(f"nav_{i}", make_task(url)) for i, url in enumerate(urls)]
        return await self.controller.run_parallel(tasks)

    async def run_custom_task(
        self,
        task_id: str,
        task_fn,
    ) -> TaskResult:
        """Run custom task with worker"""
        self._check_closed()
        return await self.controller.run_task(task_id, task_fn)

    async def run_custom_tasks_parallel(
        self,
        tasks: list[tuple[str, Any]],
    ) -> list[TaskResult]:
        """Run multiple custom tasks in parallel"""
        self._check_closed()
        return await self.controller.run_parallel(tasks)

    async def cleanup(self) -> None:
        """Clean up all resources"""
        if not self._closed:
            await self.controller.cleanup_all()
            self.ua_manager.clear_all()
            self._closed = True
            logger.info("WebAgent cleanup complete")

    def _check_closed(self) -> None:
        """Check if agent is closed"""
        if self._closed:
            raise RuntimeError("WebAgent is closed")

    @property
    def is_closed(self) -> bool:
        """Check if agent has been closed"""
        return self._closed

    def get_proxy_stats(self) -> dict:
        """Get proxy usage statistics"""
        if self.proxy_manager:
            return {
                k: {"success_rate": v.success_rate, "total": v.total_requests}
                for k, v in self.proxy_manager.get_stats().items()
            }
        return {}

    def get_proxy_health(self) -> dict:
        """Get proxy health summary"""
        if self.proxy_manager:
            return self.proxy_manager.get_health_summary()
        return {}

    async def health_check(self) -> dict:
        """Run health check on all proxies"""
        if self.proxy_manager:
            return await self.proxy_manager.health_check_all()
        return {}
