"""
AdsPower Local API Client - Fingerprint browser integration

AdsPower provides an antidetect browser with:
  - Free: 2 profiles + API access
  - $9/mo: 10 profiles + API access
  - Selenium / Puppeteer / Playwright support via CDP

The Local API runs at http://local.adspower.com:50325 by default.
Each profile launches a browser with unique fingerprint settings.
Playwright connects to the launched browser via CDP WebSocket URL.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Optional

from loguru import logger

try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


@dataclass
class AdsPowerProfile:
    """Profile info returned by AdsPower API"""
    profile_id: str
    name: str = ""
    ws_url: str = ""
    debug_port: int = 0


@dataclass
class AdsPowerConfig:
    """Configuration for AdsPower Local API"""
    api_base: str = "http://local.adspower.com:50325"
    # If empty, profiles are managed manually in AdsPower GUI.
    # If set, auto-selects profiles by serial_number or group.
    default_group_id: str = ""


class AdsPowerClient:
    """
    Client for AdsPower Local API.

    Usage:
        client = AdsPowerClient()
        ws_url = await client.start_profile("profile_id_123")
        # Connect Playwright via: browser = await playwright.chromium.connect_over_cdp(ws_url)
        # ... do work ...
        await client.stop_profile("profile_id_123")
    """

    def __init__(self, config: Optional[AdsPowerConfig] = None):
        self.config = config or AdsPowerConfig()
        self._active_profiles: dict[str, str] = {}  # profile_id -> ws_url

    def _url(self, path: str) -> str:
        return f"{self.config.api_base}{path}"

    # ------------------------------------------------------------------
    # Synchronous API (for startup / simple use)
    # ------------------------------------------------------------------

    def check_status(self) -> bool:
        """Check if AdsPower is running"""
        if not HAS_REQUESTS:
            logger.warning("requests not available, cannot check AdsPower status")
            return False
        try:
            resp = requests.get(self._url("/status"), timeout=5)
            data = resp.json()
            return data.get("code") == 0
        except Exception as e:
            logger.debug(f"AdsPower not available: {e}")
            return False

    def start_profile_sync(self, profile_id: str) -> Optional[str]:
        """Start a browser profile and return CDP WebSocket URL (sync)"""
        if not HAS_REQUESTS:
            return None
        try:
            resp = requests.get(
                self._url("/api/v1/browser/start"),
                params={"serial_number": profile_id},
                timeout=30,
            )
            data = resp.json()
            if data.get("code") != 0:
                logger.error(f"AdsPower start failed: {data.get('msg')}")
                return None

            ws_data = data.get("data", {}).get("ws", {})
            ws_url = ws_data.get("puppeteer", "") or ws_data.get("selenium", "")
            if ws_url:
                self._active_profiles[profile_id] = ws_url
                logger.info(f"AdsPower profile {profile_id} started")
                return ws_url

            logger.error("AdsPower: no WebSocket URL in response")
            return None
        except Exception as e:
            logger.error(f"AdsPower start error: {e}")
            return None

    def stop_profile_sync(self, profile_id: str) -> bool:
        """Stop a browser profile (sync)"""
        if not HAS_REQUESTS:
            return False
        try:
            resp = requests.get(
                self._url("/api/v1/browser/stop"),
                params={"serial_number": profile_id},
                timeout=10,
            )
            data = resp.json()
            self._active_profiles.pop(profile_id, None)
            return data.get("code") == 0
        except Exception as e:
            logger.error(f"AdsPower stop error: {e}")
            return False

    def list_profiles_sync(self, page: int = 1, page_size: int = 100) -> list[AdsPowerProfile]:
        """List browser profiles (sync)"""
        if not HAS_REQUESTS:
            return []
        try:
            resp = requests.get(
                self._url("/api/v1/user/list"),
                params={"page": page, "page_size": page_size},
                timeout=10,
            )
            data = resp.json()
            if data.get("code") != 0:
                return []

            profiles = []
            for item in data.get("data", {}).get("list", []):
                profiles.append(AdsPowerProfile(
                    profile_id=item.get("serial_number", ""),
                    name=item.get("name", ""),
                ))
            return profiles
        except Exception as e:
            logger.error(f"AdsPower list error: {e}")
            return []

    # ------------------------------------------------------------------
    # Async API
    # ------------------------------------------------------------------

    async def start_profile(self, profile_id: str) -> Optional[str]:
        """Start a browser profile and return CDP WebSocket URL (async)"""
        if not HAS_AIOHTTP:
            return self.start_profile_sync(profile_id)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self._url("/api/v1/browser/start"),
                    params={"serial_number": profile_id},
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    data = await resp.json()

            if data.get("code") != 0:
                logger.error(f"AdsPower start failed: {data.get('msg')}")
                return None

            ws_data = data.get("data", {}).get("ws", {})
            ws_url = ws_data.get("puppeteer", "") or ws_data.get("selenium", "")
            if ws_url:
                self._active_profiles[profile_id] = ws_url
                logger.info(f"AdsPower profile {profile_id} started")
                return ws_url

            logger.error("AdsPower: no WebSocket URL in response")
            return None
        except Exception as e:
            logger.error(f"AdsPower start error: {e}")
            return None

    async def stop_profile(self, profile_id: str) -> bool:
        """Stop a browser profile (async)"""
        if not HAS_AIOHTTP:
            return self.stop_profile_sync(profile_id)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self._url("/api/v1/browser/stop"),
                    params={"serial_number": profile_id},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    data = await resp.json()

            self._active_profiles.pop(profile_id, None)
            return data.get("code") == 0
        except Exception as e:
            logger.error(f"AdsPower stop error: {e}")
            return False

    async def stop_all(self) -> None:
        """Stop all active profiles"""
        for profile_id in list(self._active_profiles):
            await self.stop_profile(profile_id)

    async def list_profiles(self, page: int = 1, page_size: int = 100) -> list[AdsPowerProfile]:
        """List browser profiles (async)"""
        if not HAS_AIOHTTP:
            return self.list_profiles_sync(page, page_size)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self._url("/api/v1/user/list"),
                    params={"page": page, "page_size": page_size},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    data = await resp.json()

            if data.get("code") != 0:
                return []

            profiles = []
            for item in data.get("data", {}).get("list", []):
                profiles.append(AdsPowerProfile(
                    profile_id=item.get("serial_number", ""),
                    name=item.get("name", ""),
                ))
            return profiles
        except Exception as e:
            logger.error(f"AdsPower list error: {e}")
            return []
