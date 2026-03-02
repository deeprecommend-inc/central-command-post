"""
User Agent Manager - Manages browser fingerprints and user agents with area-aware profiles

Supports GoLogin API for realistic browser fingerprints (UA, viewport, platform).
Falls back to fake_useragent when GoLogin is not configured or API fails.
"""
import random
from collections import OrderedDict
from dataclasses import dataclass
from typing import Optional

import requests as _requests
from fake_useragent import UserAgent
from loguru import logger


@dataclass
class BrowserProfile:
    """Browser profile with consistent fingerprint settings"""

    user_agent: str
    viewport_width: int
    viewport_height: int
    locale: str
    timezone: str
    platform: str

    def to_playwright_context(self) -> dict:
        """Convert to Playwright browser context options"""
        return {
            "user_agent": self.user_agent,
            "viewport": {"width": self.viewport_width, "height": self.viewport_height},
            "locale": self.locale,
            "timezone_id": self.timezone,
        }


# Area profiles: country code -> (locales, timezones)
AREA_PROFILES: dict[str, dict] = {
    # North America
    "us": {"locales": ["en-US"], "timezones": ["America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles"]},
    "ca": {"locales": ["en-CA", "fr-CA"], "timezones": ["America/Toronto", "America/Vancouver"]},
    "mx": {"locales": ["es-MX"], "timezones": ["America/Mexico_City", "America/Tijuana"]},
    # South America
    "br": {"locales": ["pt-BR"], "timezones": ["America/Sao_Paulo"]},
    "ar": {"locales": ["es-AR"], "timezones": ["America/Argentina/Buenos_Aires"]},
    "cl": {"locales": ["es-CL"], "timezones": ["America/Santiago"]},
    "co": {"locales": ["es-CO"], "timezones": ["America/Bogota"]},
    "pe": {"locales": ["es-PE"], "timezones": ["America/Lima"]},
    # Europe - Western
    "gb": {"locales": ["en-GB"], "timezones": ["Europe/London"]},
    "de": {"locales": ["de-DE"], "timezones": ["Europe/Berlin"]},
    "fr": {"locales": ["fr-FR"], "timezones": ["Europe/Paris"]},
    "es": {"locales": ["es-ES"], "timezones": ["Europe/Madrid"]},
    "it": {"locales": ["it-IT"], "timezones": ["Europe/Rome"]},
    "pt": {"locales": ["pt-PT"], "timezones": ["Europe/Lisbon"]},
    "nl": {"locales": ["nl-NL"], "timezones": ["Europe/Amsterdam"]},
    "be": {"locales": ["nl-BE", "fr-BE"], "timezones": ["Europe/Brussels"]},
    "ch": {"locales": ["de-CH", "fr-CH", "it-CH"], "timezones": ["Europe/Zurich"]},
    "at": {"locales": ["de-AT"], "timezones": ["Europe/Vienna"]},
    "ie": {"locales": ["en-IE"], "timezones": ["Europe/Dublin"]},
    # Europe - Northern
    "se": {"locales": ["sv-SE"], "timezones": ["Europe/Stockholm"]},
    "no": {"locales": ["nb-NO"], "timezones": ["Europe/Oslo"]},
    "dk": {"locales": ["da-DK"], "timezones": ["Europe/Copenhagen"]},
    "fi": {"locales": ["fi-FI"], "timezones": ["Europe/Helsinki"]},
    # Europe - Eastern
    "pl": {"locales": ["pl-PL"], "timezones": ["Europe/Warsaw"]},
    "cz": {"locales": ["cs-CZ"], "timezones": ["Europe/Prague"]},
    "ro": {"locales": ["ro-RO"], "timezones": ["Europe/Bucharest"]},
    "hu": {"locales": ["hu-HU"], "timezones": ["Europe/Budapest"]},
    "ua": {"locales": ["uk-UA"], "timezones": ["Europe/Kyiv"]},
    "bg": {"locales": ["bg-BG"], "timezones": ["Europe/Sofia"]},
    "hr": {"locales": ["hr-HR"], "timezones": ["Europe/Zagreb"]},
    "sk": {"locales": ["sk-SK"], "timezones": ["Europe/Bratislava"]},
    "rs": {"locales": ["sr-RS"], "timezones": ["Europe/Belgrade"]},
    "gr": {"locales": ["el-GR"], "timezones": ["Europe/Athens"]},
    # Europe - Other
    "ru": {"locales": ["ru-RU"], "timezones": ["Europe/Moscow", "Asia/Yekaterinburg", "Asia/Novosibirsk"]},
    "tr": {"locales": ["tr-TR"], "timezones": ["Europe/Istanbul"]},
    # Middle East
    "il": {"locales": ["he-IL"], "timezones": ["Asia/Jerusalem"]},
    "ae": {"locales": ["ar-AE", "en-AE"], "timezones": ["Asia/Dubai"]},
    "sa": {"locales": ["ar-SA"], "timezones": ["Asia/Riyadh"]},
    "qa": {"locales": ["ar-QA"], "timezones": ["Asia/Qatar"]},
    # Africa
    "za": {"locales": ["en-ZA"], "timezones": ["Africa/Johannesburg"]},
    "ng": {"locales": ["en-NG"], "timezones": ["Africa/Lagos"]},
    "eg": {"locales": ["ar-EG"], "timezones": ["Africa/Cairo"]},
    "ke": {"locales": ["en-KE", "sw-KE"], "timezones": ["Africa/Nairobi"]},
    "ma": {"locales": ["ar-MA", "fr-MA"], "timezones": ["Africa/Casablanca"]},
    "gh": {"locales": ["en-GH"], "timezones": ["Africa/Accra"]},
    # Asia - East
    "jp": {"locales": ["ja-JP"], "timezones": ["Asia/Tokyo"]},
    "kr": {"locales": ["ko-KR"], "timezones": ["Asia/Seoul"]},
    "cn": {"locales": ["zh-CN"], "timezones": ["Asia/Shanghai"]},
    "tw": {"locales": ["zh-TW"], "timezones": ["Asia/Taipei"]},
    "hk": {"locales": ["zh-HK", "en-HK"], "timezones": ["Asia/Hong_Kong"]},
    "mn": {"locales": ["mn-MN"], "timezones": ["Asia/Ulaanbaatar"]},
    # Asia - Southeast
    "sg": {"locales": ["en-SG", "zh-SG"], "timezones": ["Asia/Singapore"]},
    "th": {"locales": ["th-TH"], "timezones": ["Asia/Bangkok"]},
    "vn": {"locales": ["vi-VN"], "timezones": ["Asia/Ho_Chi_Minh"]},
    "id": {"locales": ["id-ID"], "timezones": ["Asia/Jakarta"]},
    "my": {"locales": ["ms-MY", "en-MY"], "timezones": ["Asia/Kuala_Lumpur"]},
    "ph": {"locales": ["en-PH", "fil-PH"], "timezones": ["Asia/Manila"]},
    # Asia - South
    "in": {"locales": ["en-IN", "hi-IN"], "timezones": ["Asia/Kolkata"]},
    "pk": {"locales": ["ur-PK", "en-PK"], "timezones": ["Asia/Karachi"]},
    "bd": {"locales": ["bn-BD"], "timezones": ["Asia/Dhaka"]},
    "lk": {"locales": ["si-LK", "ta-LK"], "timezones": ["Asia/Colombo"]},
    # Oceania
    "au": {"locales": ["en-AU"], "timezones": ["Australia/Sydney", "Australia/Melbourne", "Australia/Perth"]},
    "nz": {"locales": ["en-NZ"], "timezones": ["Pacific/Auckland"]},
}


class GoLoginClient:
    """Client for GoLogin fingerprint API. Returns realistic browser fingerprints."""

    BASE_URL = "https://api.gologin.com"

    def __init__(self, api_token: str):
        self._token = api_token
        self._headers = {"Authorization": f"Bearer {api_token}"}

    def get_random_fingerprint(self, os_type: str = "win") -> dict | None:
        """Fetch random fingerprint from GoLogin API. Returns None on failure."""
        try:
            resp = _requests.get(
                f"{self.BASE_URL}/browser/fingerprint",
                params={"os": os_type},
                headers=self._headers,
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning(f"GoLogin API failed: {e}")
            return None


class LRUCache:
    """Simple LRU cache implementation using OrderedDict"""

    def __init__(self, max_size: int = 100):
        self._cache: OrderedDict = OrderedDict()
        self._max_size = max_size

    def get(self, key: str) -> Optional[any]:
        """Get item and move to end (most recently used)"""
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        return None

    def set(self, key: str, value: any) -> None:
        """Set item, evicting oldest if at capacity"""
        if key in self._cache:
            self._cache.move_to_end(key)
        else:
            if len(self._cache) >= self._max_size:
                oldest = next(iter(self._cache))
                del self._cache[oldest]
                logger.debug(f"LRU evicted: {oldest}")
        self._cache[key] = value

    def delete(self, key: str) -> bool:
        """Delete item if exists"""
        if key in self._cache:
            del self._cache[key]
            return True
        return False

    def __contains__(self, key: str) -> bool:
        return key in self._cache

    def __len__(self) -> int:
        return len(self._cache)

    def clear(self) -> None:
        """Clear all cached items"""
        self._cache.clear()


class UserAgentManager:
    """Manages user agents and browser profiles with LRU caching"""

    MAX_CACHED_PROFILES = 100

    VIEWPORTS = [
        (1920, 1080),
        (1366, 768),
        (1536, 864),
        (1440, 900),
        (1280, 720),
        (2560, 1440),
    ]

    LOCALES = ["en-US", "en-GB", "de-DE", "fr-FR", "ja-JP", "es-ES"]

    TIMEZONES = [
        "America/New_York",
        "America/Los_Angeles",
        "Europe/London",
        "Europe/Berlin",
        "Asia/Tokyo",
        "Australia/Sydney",
    ]

    def __init__(self, max_cached_profiles: int = MAX_CACHED_PROFILES, gologin_token: str = ""):
        self._ua = UserAgent()
        self._profiles = LRUCache(max_size=max_cached_profiles)
        self._gologin: GoLoginClient | None = None
        if gologin_token:
            self._gologin = GoLoginClient(api_token=gologin_token)
            logger.info("GoLogin fingerprint API enabled")

    @staticmethod
    def _parse_resolution(resolution: str) -> tuple[int, int] | None:
        """Parse 'WIDTHxHEIGHT' string from GoLogin fingerprint."""
        try:
            w, h = resolution.split("x")
            return int(w), int(h)
        except (ValueError, AttributeError):
            return None

    @staticmethod
    def _platform_from_ua(ua_string: str) -> str:
        """Detect platform from user agent string."""
        if "Mac" in ua_string:
            return "MacIntel"
        if "Linux" in ua_string:
            return "Linux x86_64"
        return "Windows"

    def _fetch_gologin_fingerprint(self) -> dict | None:
        """Fetch fingerprint from GoLogin if available."""
        if not self._gologin:
            return None
        return self._gologin.get_random_fingerprint()

    def _build_profile_from_fingerprint(
        self,
        fp: dict,
        locale_override: str = "",
        timezone_override: str = "",
    ) -> BrowserProfile | None:
        """Build a BrowserProfile from GoLogin fingerprint data. Returns None if unusable."""
        nav = fp.get("navigator", {})
        ua_string = nav.get("userAgent", "")
        if not ua_string:
            return None

        resolution = nav.get("resolution", "")
        parsed = self._parse_resolution(resolution)
        if parsed:
            vw, vh = parsed
        else:
            vw, vh = random.choice(self.VIEWPORTS)

        platform = nav.get("platform", "") or self._platform_from_ua(ua_string)
        locale = locale_override or nav.get("language", "") or random.choice(self.LOCALES)
        timezone = timezone_override or random.choice(self.TIMEZONES)

        return BrowserProfile(
            user_agent=ua_string,
            viewport_width=vw,
            viewport_height=vh,
            locale=locale,
            timezone=timezone,
            platform=platform,
        )

    def get_random_profile(self, session_id: Optional[str] = None) -> BrowserProfile:
        """Generate a random but consistent browser profile"""
        # If session_id provided and profile exists, return cached
        if session_id:
            cached = self._profiles.get(session_id)
            if cached:
                return cached

        # Try GoLogin fingerprint first
        fp = self._fetch_gologin_fingerprint()
        if fp:
            profile = self._build_profile_from_fingerprint(fp)
            if profile:
                if session_id:
                    self._profiles.set(session_id, profile)
                    logger.debug(f"Created GoLogin profile for session {session_id}")
                return profile

        # Fallback: fake_useragent
        ua_string = self._ua.random
        viewport = random.choice(self.VIEWPORTS)
        locale = random.choice(self.LOCALES)
        timezone = random.choice(self.TIMEZONES)
        platform = self._platform_from_ua(ua_string)

        profile = BrowserProfile(
            user_agent=ua_string,
            viewport_width=viewport[0],
            viewport_height=viewport[1],
            locale=locale,
            timezone=timezone,
            platform=platform,
        )

        # Cache if session_id provided
        if session_id:
            self._profiles.set(session_id, profile)
            logger.debug(f"Created browser profile for session {session_id}")

        return profile

    def get_area_profile(
        self,
        area: str,
        timezone: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> BrowserProfile:
        """
        Generate a browser profile matched to a geographic area.

        Args:
            area: Country code (us, gb, de, fr, jp, au, ca, br, in, kr)
            timezone: Explicit timezone override (default: auto from area)
            session_id: Cache key for sticky profiles per worker
        """
        if session_id:
            cached = self._profiles.get(session_id)
            if cached:
                return cached

        area_lower = area.lower()
        area_data = AREA_PROFILES.get(area_lower)

        if area_data:
            locale = random.choice(area_data["locales"])
            tz = timezone or random.choice(area_data["timezones"])
        else:
            locale = random.choice(self.LOCALES)
            tz = timezone or random.choice(self.TIMEZONES)
            logger.warning(f"Unknown area '{area}', using random locale/timezone")

        # Try GoLogin fingerprint with area locale/timezone override
        fp = self._fetch_gologin_fingerprint()
        if fp:
            profile = self._build_profile_from_fingerprint(fp, locale_override=locale, timezone_override=tz)
            if profile:
                if session_id:
                    self._profiles.set(session_id, profile)
                    logger.debug(f"Created GoLogin area profile for session {session_id}: area={area}, tz={tz}")
                return profile

        # Fallback: fake_useragent
        ua_string = self._ua.random
        viewport = random.choice(self.VIEWPORTS)
        platform = self._platform_from_ua(ua_string)

        profile = BrowserProfile(
            user_agent=ua_string,
            viewport_width=viewport[0],
            viewport_height=viewport[1],
            locale=locale,
            timezone=tz,
            platform=platform,
        )

        if session_id:
            self._profiles.set(session_id, profile)
            logger.debug(f"Created area profile for session {session_id}: area={area}, tz={tz}")

        return profile

    def get_chrome_profile(self, session_id: Optional[str] = None) -> BrowserProfile:
        """Get a Chrome-specific profile"""
        if session_id:
            cached = self._profiles.get(session_id)
            if cached:
                return cached

        # Try GoLogin fingerprint (already Chrome-like)
        fp = self._fetch_gologin_fingerprint()
        if fp:
            profile = self._build_profile_from_fingerprint(fp)
            if profile:
                if session_id:
                    self._profiles.set(session_id, profile)
                return profile

        # Fallback: fake_useragent Chrome
        ua_string = self._ua.chrome
        viewport = random.choice(self.VIEWPORTS)
        locale = random.choice(self.LOCALES)
        timezone = random.choice(self.TIMEZONES)

        profile = BrowserProfile(
            user_agent=ua_string,
            viewport_width=viewport[0],
            viewport_height=viewport[1],
            locale=locale,
            timezone=timezone,
            platform="Windows",
        )

        if session_id:
            self._profiles.set(session_id, profile)

        return profile

    def clear_session(self, session_id: str) -> None:
        """Clear cached profile for session"""
        if self._profiles.delete(session_id):
            logger.debug(f"Cleared profile for session {session_id}")

    def clear_all(self) -> None:
        """Clear all cached profiles"""
        self._profiles.clear()
        logger.debug("Cleared all cached profiles")

    def get_cache_stats(self) -> dict:
        """Get cache statistics"""
        return {
            "cached_profiles": len(self._profiles),
            "max_profiles": self._profiles._max_size,
        }
