"""
Scrapling Agent - Stealth browser fetching via Scrapling's StealthyFetcher.

Provides anti-bot stealth (TLS fingerprint spoofing, CDP runtime patches,
JS injection, Cloudflare bypass) that raw Chrome launch lacks.

Dual mode with BrowserUseAgent:
  - BrowserUseAgent: AI-driven multi-step browser tasks
  - ScraplingAgent: Stealth single-page fetching with human-like timing
"""
import asyncio
import os
import random
import re
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from loguru import logger

from .human_timing import random_delay, action_throttle, dwell_time
from .human_score import HumanScoreTracker
from .proxy_manager import ProxyManager
from .proxy_provider import SmartProxyISPBackend
from .ua_manager import UserAgentManager


@dataclass
class ScraplingConfig:
    """Configuration for ScraplingAgent"""

    # SmartProxy ISP credentials
    smartproxy_username: str = ""
    smartproxy_password: str = ""
    smartproxy_host: str = "isp.decodo.com"
    smartproxy_port: int = 10001

    # Area/timezone
    area: str = "us"
    timezone: str = ""

    # No proxy mode
    no_proxy: bool = False

    # Browser settings
    headless: bool = True

    # Scrapling-specific
    solve_cloudflare: bool = False
    hide_canvas: bool = True
    network_idle: bool = True

    # GoLogin fingerprint API token
    gologin_api_token: str = ""


def _build_scrapling_proxy(
    backend: SmartProxyISPBackend,
    country: str,
    session_id: str,
) -> dict:
    """
    Convert SmartProxyISPBackend credentials to Scrapling's proxy format.

    Scrapling expects: {"server": "host:port", "username": "...", "password": "..."}
    """
    username, password = backend.get_auth(
        country=country, session_id=session_id,
    )
    return {
        "server": f"{backend.host}:{backend.port}",
        "username": username,
        "password": password,
    }


class ScraplingAgent:
    """
    Stealth web fetcher using Scrapling's StealthyFetcher.

    Provides anti-bot stealth capabilities with human-like timing injection.
    Output shape matches BrowserUseAgent: {success, result, task, human_score}
    """

    def __init__(self, config: ScraplingConfig):
        self.config = config

        # Initialize proxy manager
        self.proxy_manager: Optional[ProxyManager] = None
        if not config.no_proxy and config.smartproxy_username and config.smartproxy_password:
            backend = SmartProxyISPBackend(
                username=config.smartproxy_username,
                password=config.smartproxy_password,
                host=config.smartproxy_host,
                port=config.smartproxy_port,
            )
            self.proxy_manager = ProxyManager(
                backend=backend,
                area=config.area,
            )
            logger.info(f"ScraplingAgent proxy enabled: area={config.area}")
        else:
            logger.info("ScraplingAgent: direct connection")

        # Initialize UA manager
        self.ua_manager = UserAgentManager(gologin_token=config.gologin_api_token)
        self._session_counter = 0

    def _get_session_params(self) -> dict:
        """Build kwargs for StealthyFetcher session."""
        self._session_counter += 1
        session_id = f"scrapling_{self._session_counter}"

        # UA profile
        profile = self.ua_manager.get_area_profile(
            area=self.config.area,
            timezone=self.config.timezone or None,
            session_id=session_id,
        )

        kwargs: dict[str, Any] = {
            "headless": self.config.headless,
            "useragent": profile.user_agent,
            "locale": profile.locale,
            "timezone_id": profile.timezone,
            "hide_canvas": self.config.hide_canvas,
            "block_webrtc": True,
        }

        # Proxy
        if self.proxy_manager:
            proxy_config = self.proxy_manager.get_proxy(new_session=True)
            backend = self.proxy_manager.backend
            kwargs["proxy"] = _build_scrapling_proxy(
                backend, proxy_config.country or self.config.area, proxy_config.session_id or session_id,
            )
            logger.info(
                f"Scrapling proxy: country={proxy_config.country}, session={proxy_config.session_id}"
            )

        logger.info(f"Scrapling UA: {profile.user_agent[:60]}...")
        return kwargs

    @staticmethod
    def _extract_url(text: str) -> str:
        """Extract a URL from text. Handles full URLs and bare domains."""
        # Match explicit URLs (http/https)
        m = re.search(r'https?://[^\s,\'"<>]+', text)
        if m:
            return m.group(0).rstrip(".,;:!?)")

        # Match bare domains (e.g. "example.com", "httpbin.org/ip")
        m = re.search(r'(?:^|\s)((?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}(?:/[^\s,\'"<>]*)?)', text)
        if m:
            return "https://" + m.group(1).rstrip(".,;:!?)")

        return ""

    def _parse_task(self, task: str | dict) -> dict:
        """Parse task parameter into structured form."""
        if isinstance(task, str):
            url = self._extract_url(task)
            return {"url": url, "page_action": None, "solve_cloudflare": self.config.solve_cloudflare}
        return {
            "url": task.get("url", ""),
            "page_action": task.get("page_action"),
            "solve_cloudflare": task.get("solve_cloudflare", self.config.solve_cloudflare),
        }

    async def run(self, task: str | dict) -> dict[str, Any]:
        """
        Fetch a URL with stealth and human-like timing.

        Args:
            task: URL string or dict {url, page_action, solve_cloudflare}

        Returns:
            {success, result, task, human_score}
        """
        parsed = self._parse_task(task)
        url = parsed["url"]
        if not url:
            return {"success": False, "error": "No URL provided", "task": str(task), "human_score": {}}

        logger.info(f"Scrapling fetch: {url}")
        tracker = HumanScoreTracker()

        # Record fingerprint
        import hashlib
        session_kwargs = self._get_session_params()
        ua = session_kwargs.get("useragent", "")
        fp_hash = hashlib.sha256(ua.encode()).hexdigest()[:16] if ua else ""
        tracker.record_ip(
            ip=f"{self.config.smartproxy_host}:{self.config.smartproxy_port}" if self.proxy_manager else "direct",
            country=self.config.area,
            fingerprint_hash=fp_hash,
        )

        try:
            from scrapling import StealthyFetcher
        except ImportError:
            return {
                "success": False,
                "error": "scrapling not installed. Run: pip install 'scrapling[fetchers]' && scrapling install",
                "task": str(task),
                "human_score": {},
            }

        try:
            # Pre-navigation human delay
            pre_delay = random_delay(1.0, 3.0)
            tracker.record_action("wait", timestamp=time.time())
            await asyncio.sleep(pre_delay)

            # Build fetch kwargs from session params
            fetch_kwargs: dict[str, Any] = {}
            if session_kwargs.get("headless") is not None:
                fetch_kwargs["headless"] = session_kwargs["headless"]
            if session_kwargs.get("proxy"):
                fetch_kwargs["proxy"] = session_kwargs["proxy"]
            if session_kwargs.get("useragent"):
                fetch_kwargs["useragent"] = session_kwargs["useragent"]
            if session_kwargs.get("locale"):
                fetch_kwargs["locale"] = session_kwargs["locale"]
            if session_kwargs.get("timezone_id"):
                fetch_kwargs["timezone_id"] = session_kwargs["timezone_id"]
            fetch_kwargs["hide_canvas"] = session_kwargs.get("hide_canvas", True)
            fetch_kwargs["block_webrtc"] = session_kwargs.get("block_webrtc", True)
            if parsed["solve_cloudflare"]:
                fetch_kwargs["solve_cloudflare"] = True

            fetch_start = time.time()
            tracker.record_action("navigate", timestamp=fetch_start)

            # StealthyFetcher.fetch() is a class method (synchronous)
            loop = asyncio.get_running_loop()
            page = await loop.run_in_executor(
                None,
                lambda: StealthyFetcher.fetch(url, **fetch_kwargs),
            )

            fetch_end = time.time()
            tracker.record_action("page_load", timestamp=fetch_end)

            # Page dwell (human-like reading time)
            dwell = dwell_time(3.0)
            await asyncio.sleep(dwell)
            tracker.record_action("read", timestamp=time.time())

            # Throttle check
            elapsed = time.time() - fetch_start
            throttle_delay = action_throttle(4, elapsed)
            if throttle_delay > 0:
                await asyncio.sleep(throttle_delay)

            # Extract result
            title_els = page.css("title")
            title = title_els[0].text if title_els else ""
            result_data = {
                "url": url,
                "status": getattr(page, "status", None),
                "title": title,
                "text_length": len(page.get_all_text()) if hasattr(page, "get_all_text") else 0,
            }

            # Record page visit
            tracker.record_page_visit(
                url=url, dwell_sec=dwell, completed=True, bounced=False, clicked=False,
            )
            tracker.record_outcome("success")

            # Post-action delay
            post_delay = random_delay(0.5, 2.0)
            tracker.record_action("idle", timestamp=time.time())
            await asyncio.sleep(post_delay)

            score_report = tracker.compute()
            logger.info(f"Scrapling done: {url} | Human score: {score_report.total_score}/{score_report.max_score}")

            return {
                "success": True,
                "result": result_data,
                "task": str(task),
                "human_score": score_report.summary(),
            }

        except Exception as e:
            logger.error(f"Scrapling fetch failed: {e}")
            tracker.record_outcome("failure")
            score_report = tracker.compute()
            return {
                "success": False,
                "error": str(e),
                "task": str(task),
                "human_score": score_report.summary(),
            }

    async def run_parallel(
        self, tasks: list[str | dict], max_concurrent: int = 5
    ) -> list[dict]:
        """Run multiple stealth fetches in parallel."""
        logger.info(f"Scrapling parallel: {len(tasks)} tasks (max {max_concurrent})")
        semaphore = asyncio.Semaphore(max_concurrent)

        async def _run(task: str | dict, index: int) -> dict:
            async with semaphore:
                result = await self.run(task)
                result["index"] = index
                return result

        results = await asyncio.gather(
            *[_run(t, i) for i, t in enumerate(tasks)],
            return_exceptions=True,
        )

        final = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                final.append({"success": False, "error": str(r), "task": str(tasks[i]), "index": i})
            else:
                final.append(r)

        success_count = sum(1 for r in final if r.get("success"))
        logger.info(f"Scrapling completed: {success_count}/{len(tasks)} successful")
        return final
