"""
Warmup Engine - Cookie farming and Trust Score building via autonomous browsing.

Action Layer: uses OpenClaw (browser-use) LLM agent to browse tracker-heavy sites
(Google Analytics, Meta Pixel) with non-linear navigation patterns.

The warmup builds a realistic browsing history (cookies, localStorage)
before account creation to avoid immediate flagging.
"""
import asyncio
import random
import time
from dataclasses import dataclass, field
from typing import Optional

from loguru import logger

from .human_score import HumanScoreTracker
from .human_timing import random_delay, dwell_time
from .session_manager import SessionManager


# Sites with Google Analytics / Meta Pixel / other major trackers
WARMUP_SITES = [
    # News
    "https://www.bbc.com",
    "https://edition.cnn.com",
    "https://www.reuters.com",
    "https://www.theguardian.com",
    "https://apnews.com",
    # Tech
    "https://www.wired.com",
    "https://arstechnica.com",
    "https://techcrunch.com",
    "https://www.theverge.com",
    # Shopping / EC
    "https://www.amazon.com",
    "https://www.ebay.com",
    "https://www.etsy.com",
    # Reference
    "https://en.wikipedia.org/wiki/Main_Page",
    "https://stackoverflow.com",
    # Entertainment
    "https://www.imdb.com",
    "https://www.rottentomatoes.com",
    # Weather / Utility
    "https://weather.com",
    "https://www.timeanddate.com",
    # Google properties (builds Google cookies directly)
    "https://www.google.com/maps",
    "https://news.google.com",
    "https://translate.google.com",
    "https://www.youtube.com",
]

# LLM prompt for autonomous warmup browsing
WARMUP_PROMPT_TEMPLATE = """
You are casually browsing the internet as a normal person.
Visit {url} and behave naturally:

1. Wait for the page to load, then scroll down slowly to read content.
2. Find an interesting link or article on the page and click it.
3. Read the new page for a few seconds, scroll around.
4. If there are more links, follow one more.
5. After visiting 2-3 pages from this site, stop.

Important:
- Do NOT create any accounts or log in.
- Do NOT fill in any forms.
- Just browse, read, and click like a normal curious person.
- Take your time between actions.
"""


@dataclass
class WarmupConfig:
    """Configuration for warmup sessions"""
    # How many sites to visit per session
    sites_per_session: int = 5
    # How many pages to browse per site (via LLM navigation)
    pages_per_site: int = 3
    # Minimum delay between site visits (seconds)
    inter_site_delay_min: float = 30.0
    inter_site_delay_max: float = 120.0
    # Session duration limit (minutes)
    max_session_minutes: float = 60.0
    # LLM model for autonomous browsing
    model: str = "dolphin3"
    # Custom sites to include
    extra_sites: list[str] = field(default_factory=list)


@dataclass
class WarmupResult:
    """Result of a warmup session"""
    session_id: str
    sites_visited: list[str]
    pages_browsed: int
    duration_seconds: float
    human_score: dict
    cookies_count: int
    success: bool
    error: str = ""


class WarmupEngine:
    """
    Autonomous browsing engine for cookie farming and trust score building.

    Uses BrowserUseAgent (OpenClaw) to let an LLM navigate websites naturally,
    accumulating cookies and browsing history that make the profile look human.

    Usage:
        engine = WarmupEngine(session_id="account_1")
        result = await engine.run_session()
    """

    def __init__(
        self,
        session_id: str,
        config: Optional[WarmupConfig] = None,
        browser_config: Optional[dict] = None,
    ):
        self.session_id = session_id
        self.config = config or WarmupConfig()
        self.browser_config = browser_config or {}
        self.session_manager = SessionManager(storage_dir="./sessions")
        self._tracker = HumanScoreTracker()

    def _select_sites(self) -> list[str]:
        """Select random sites for this warmup session"""
        pool = WARMUP_SITES.copy()
        if self.config.extra_sites:
            pool.extend(self.config.extra_sites)
        random.shuffle(pool)
        return pool[: self.config.sites_per_session]

    async def run_session(self) -> WarmupResult:
        """
        Run a single warmup session: visit multiple sites with LLM-driven browsing.

        Returns WarmupResult with session stats.
        """
        sites = self._select_sites()
        start_time = time.time()
        visited = []
        total_pages = 0

        logger.info(
            f"Warmup session {self.session_id}: {len(sites)} sites planned"
        )

        for i, site in enumerate(sites):
            # Check session time limit
            elapsed_min = (time.time() - start_time) / 60.0
            if elapsed_min >= self.config.max_session_minutes:
                logger.info(f"Warmup session time limit reached: {elapsed_min:.1f}min")
                break

            logger.info(f"Warmup [{i+1}/{len(sites)}]: {site}")

            try:
                pages = await self._browse_site(site)
                visited.append(site)
                total_pages += pages
                self._tracker.record_action("navigate", timestamp=time.time())
            except Exception as e:
                logger.warning(f"Warmup site failed: {site} - {e}")
                self._tracker.record_outcome("failure")
                continue

            # Inter-site delay (human-like pause between different sites)
            if i < len(sites) - 1:
                delay = random.uniform(
                    self.config.inter_site_delay_min,
                    self.config.inter_site_delay_max,
                )
                logger.debug(f"Inter-site delay: {delay:.1f}s")
                await asyncio.sleep(delay)

        duration = time.time() - start_time
        score_report = self._tracker.compute()

        result = WarmupResult(
            session_id=self.session_id,
            sites_visited=visited,
            pages_browsed=total_pages,
            duration_seconds=duration,
            human_score=score_report.summary(),
            cookies_count=0,
            success=len(visited) > 0,
        )

        logger.info(
            f"Warmup session complete: {len(visited)} sites, "
            f"{total_pages} pages, {duration:.0f}s, "
            f"score={score_report.total_score}/{score_report.max_score}"
        )

        return result

    async def _browse_site(self, url: str) -> int:
        """
        Browse a single site using BrowserUseAgent with LLM navigation.

        Returns number of pages browsed.
        """
        from .browser_use_agent import BrowserUseConfig, BrowserUseAgent

        prompt = WARMUP_PROMPT_TEMPLATE.format(url=url)

        # Build agent config from browser_config + defaults
        agent_config = BrowserUseConfig(
            smartproxy_username=self.browser_config.get("smartproxy_username", ""),
            smartproxy_password=self.browser_config.get("smartproxy_password", ""),
            smartproxy_host=self.browser_config.get("smartproxy_host", "isp.decodo.com"),
            smartproxy_port=self.browser_config.get("smartproxy_port", 10001),
            area=self.browser_config.get("area", "us"),
            timezone=self.browser_config.get("timezone", ""),
            no_proxy=self.browser_config.get("no_proxy", False),
            llm_provider=self.browser_config.get("llm_provider", "local"),
            llm_api_key=self.browser_config.get("llm_api_key", ""),
            llm_base_url=self.browser_config.get("llm_base_url", "http://localhost:11434/v1"),
            model=self.config.model,
            headless=self.browser_config.get("headless", True),
            use_vision=self.browser_config.get("use_vision", True),
            session_dir=f"./sessions/{self.session_id}",
            llm_timeout=self.browser_config.get("llm_timeout", 300),
            step_timeout=self.browser_config.get("step_timeout", 600),
            gologin_api_token=self.browser_config.get("gologin_api_token", ""),
        )

        agent = BrowserUseAgent(agent_config)

        try:
            result = await agent.run(prompt)
            pages = result.get("steps", self.config.pages_per_site)

            # Record page visits with realistic dwell times
            for _ in range(min(pages, self.config.pages_per_site)):
                dwell = dwell_time(5.0)
                self._tracker.record_page_visit(
                    url=url,
                    dwell_sec=dwell,
                    completed=random.random() < 0.6,
                    bounced=False,
                    clicked=True,
                )
                self._tracker.record_action("scroll", timestamp=time.time())
                self._tracker.record_action("click", timestamp=time.time())

            self._tracker.record_outcome("success")
            return min(pages, self.config.pages_per_site)

        except Exception as e:
            logger.error(f"Browse site failed: {url} - {e}")
            self._tracker.record_page_visit(
                url=url, dwell_sec=2.0, completed=False, bounced=True,
            )
            raise

    async def run_daily_warmup(self, days: int = 3) -> list[WarmupResult]:
        """
        Run warmup sessions spread across multiple days.

        In practice, call run_session() once per day via scheduler.
        This method simulates the full warmup cycle for testing.
        """
        results = []
        for day in range(days):
            logger.info(f"Warmup day {day + 1}/{days} for {self.session_id}")
            result = await self.run_session()
            results.append(result)

            if day < days - 1:
                # In production, this would be a cron/scheduler gap
                # For testing, just a short pause
                logger.info("Waiting for next warmup session...")
                await asyncio.sleep(1.0)

        return results
