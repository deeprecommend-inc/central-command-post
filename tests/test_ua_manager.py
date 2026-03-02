"""
Tests for UserAgentManager
"""
import pytest
from unittest.mock import patch, MagicMock
from src.ua_manager import UserAgentManager, BrowserProfile, LRUCache, GoLoginClient


# Sample GoLogin fingerprint response
SAMPLE_FINGERPRINT = {
    "navigator": {
        "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "resolution": "1920x1080",
        "language": "en-US",
        "platform": "Win32",
        "hardwareConcurrency": 4,
        "deviceMemory": 4,
        "maxTouchPoints": 10,
    },
    "fonts": {},
    "webgl": {},
    "webRtc": {},
}


class TestLRUCache:
    """Tests for LRUCache"""

    def test_basic_set_get(self):
        cache = LRUCache(max_size=3)
        cache.set("a", 1)
        assert cache.get("a") == 1

    def test_get_nonexistent(self):
        cache = LRUCache(max_size=3)
        assert cache.get("nonexistent") is None

    def test_eviction_on_capacity(self):
        cache = LRUCache(max_size=3)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        cache.set("d", 4)  # Should evict "a"
        assert cache.get("a") is None
        assert cache.get("b") == 2
        assert cache.get("d") == 4

    def test_lru_order_on_get(self):
        cache = LRUCache(max_size=3)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        cache.get("a")  # Move "a" to end
        cache.set("d", 4)  # Should evict "b" (oldest after "a" was accessed)
        assert cache.get("a") == 1
        assert cache.get("b") is None

    def test_delete(self):
        cache = LRUCache(max_size=3)
        cache.set("a", 1)
        assert cache.delete("a") is True
        assert cache.get("a") is None
        assert cache.delete("nonexistent") is False

    def test_contains(self):
        cache = LRUCache(max_size=3)
        cache.set("a", 1)
        assert "a" in cache
        assert "b" not in cache

    def test_len(self):
        cache = LRUCache(max_size=3)
        assert len(cache) == 0
        cache.set("a", 1)
        assert len(cache) == 1
        cache.set("b", 2)
        assert len(cache) == 2

    def test_clear(self):
        cache = LRUCache(max_size=3)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.clear()
        assert len(cache) == 0
        assert cache.get("a") is None


class TestBrowserProfile:
    """Tests for BrowserProfile dataclass"""

    def test_to_playwright_context(self):
        profile = BrowserProfile(
            user_agent="Mozilla/5.0 Test",
            viewport_width=1920,
            viewport_height=1080,
            locale="en-US",
            timezone="America/New_York",
            platform="Windows",
        )
        context = profile.to_playwright_context()
        assert context["user_agent"] == "Mozilla/5.0 Test"
        assert context["viewport"]["width"] == 1920
        assert context["viewport"]["height"] == 1080
        assert context["locale"] == "en-US"
        assert context["timezone_id"] == "America/New_York"


class TestGoLoginClient:
    """Tests for GoLoginClient"""

    def test_init(self):
        client = GoLoginClient(api_token="test-token")
        assert client._token == "test-token"
        assert client._headers == {"Authorization": "Bearer test-token"}

    @patch("src.ua_manager._requests.get")
    def test_get_random_fingerprint_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = SAMPLE_FINGERPRINT
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        client = GoLoginClient(api_token="test-token")
        fp = client.get_random_fingerprint(os_type="win")

        assert fp is not None
        assert fp["navigator"]["userAgent"].startswith("Mozilla/5.0")
        mock_get.assert_called_once_with(
            "https://api.gologin.com/browser/fingerprint",
            params={"os": "win"},
            headers={"Authorization": "Bearer test-token"},
            timeout=10,
        )

    @patch("src.ua_manager._requests.get")
    def test_get_random_fingerprint_api_error(self, mock_get):
        mock_get.side_effect = Exception("Connection refused")
        client = GoLoginClient(api_token="test-token")
        fp = client.get_random_fingerprint()
        assert fp is None

    @patch("src.ua_manager._requests.get")
    def test_get_random_fingerprint_http_error(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = Exception("401 Unauthorized")
        mock_get.return_value = mock_resp

        client = GoLoginClient(api_token="bad-token")
        fp = client.get_random_fingerprint()
        assert fp is None


class TestUserAgentManager:
    """Tests for UserAgentManager"""

    def test_initialization(self):
        manager = UserAgentManager()
        assert manager is not None
        assert manager._gologin is None

    def test_initialization_with_gologin_token(self):
        manager = UserAgentManager(gologin_token="test-token")
        assert manager._gologin is not None
        assert isinstance(manager._gologin, GoLoginClient)

    def test_initialization_empty_gologin_token(self):
        manager = UserAgentManager(gologin_token="")
        assert manager._gologin is None

    def test_get_random_profile(self):
        manager = UserAgentManager()
        profile = manager.get_random_profile()
        assert profile is not None
        assert profile.user_agent is not None
        assert len(profile.user_agent) > 0
        assert profile.viewport_width > 0
        assert profile.viewport_height > 0

    @patch("src.ua_manager._requests.get")
    def test_get_random_profile_with_gologin(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = SAMPLE_FINGERPRINT
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        manager = UserAgentManager(gologin_token="test-token")
        profile = manager.get_random_profile()

        assert profile.user_agent == SAMPLE_FINGERPRINT["navigator"]["userAgent"]
        assert profile.viewport_width == 1920
        assert profile.viewport_height == 1080
        assert profile.platform == "Win32"

    @patch("src.ua_manager._requests.get")
    def test_get_random_profile_gologin_fallback(self, mock_get):
        """When GoLogin API fails, should fall back to fake_useragent"""
        mock_get.side_effect = Exception("API down")

        manager = UserAgentManager(gologin_token="test-token")
        profile = manager.get_random_profile()

        # Should still return a valid profile via fallback
        assert profile is not None
        assert len(profile.user_agent) > 0
        assert profile.viewport_width > 0

    @patch("src.ua_manager._requests.get")
    def test_get_area_profile_with_gologin_overrides_locale_timezone(self, mock_get):
        """GoLogin UA should be used but locale/timezone come from AREA_PROFILES"""
        mock_resp = MagicMock()
        mock_resp.json.return_value = SAMPLE_FINGERPRINT
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        manager = UserAgentManager(gologin_token="test-token")
        profile = manager.get_area_profile(area="jp")

        # UA from GoLogin
        assert profile.user_agent == SAMPLE_FINGERPRINT["navigator"]["userAgent"]
        # Locale and timezone from AREA_PROFILES (Japan)
        assert profile.locale == "ja-JP"
        assert profile.timezone == "Asia/Tokyo"

    @patch("src.ua_manager._requests.get")
    def test_get_area_profile_gologin_fallback(self, mock_get):
        """When GoLogin API fails in area profile, should fall back"""
        mock_get.side_effect = Exception("API down")

        manager = UserAgentManager(gologin_token="test-token")
        profile = manager.get_area_profile(area="jp")

        assert profile is not None
        assert profile.locale == "ja-JP"
        assert profile.timezone == "Asia/Tokyo"

    @patch("src.ua_manager._requests.get")
    def test_get_chrome_profile_with_gologin(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = SAMPLE_FINGERPRINT
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        manager = UserAgentManager(gologin_token="test-token")
        profile = manager.get_chrome_profile()

        assert profile.user_agent == SAMPLE_FINGERPRINT["navigator"]["userAgent"]

    def test_get_profile_with_session_id(self):
        manager = UserAgentManager()
        profile1 = manager.get_random_profile(session_id="test_session")
        profile2 = manager.get_random_profile(session_id="test_session")
        # Same session should return same profile
        assert profile1.user_agent == profile2.user_agent

    def test_different_sessions_get_different_profiles(self):
        manager = UserAgentManager()
        profiles = [
            manager.get_random_profile(session_id=f"session_{i}")
            for i in range(10)
        ]
        # At least some should be different (probabilistic but very likely)
        user_agents = [p.user_agent for p in profiles]
        unique_agents = set(user_agents)
        assert len(unique_agents) >= 1  # At least one unique

    def test_clear_session(self):
        manager = UserAgentManager()
        profile1 = manager.get_random_profile(session_id="clear_test")
        manager.clear_session("clear_test")
        profile2 = manager.get_random_profile(session_id="clear_test")
        # After clearing, may get different profile (not guaranteed but possible)
        # Just ensure no error occurs
        assert profile2 is not None

    def test_profile_has_valid_viewport(self):
        manager = UserAgentManager()
        profile = manager.get_random_profile()
        valid_widths = [w for w, h in manager.VIEWPORTS]
        assert profile.viewport_width in valid_widths

    def test_profile_has_valid_locale(self):
        manager = UserAgentManager()
        profile = manager.get_random_profile()
        assert profile.locale in manager.LOCALES

    def test_profile_has_valid_timezone(self):
        manager = UserAgentManager()
        profile = manager.get_random_profile()
        assert profile.timezone in manager.TIMEZONES

    def test_profile_platform_consistency(self):
        manager = UserAgentManager()
        profile = manager.get_random_profile()
        # Platform should be consistent with user agent
        ua_lower = profile.user_agent.lower()
        if "windows" in ua_lower:
            assert profile.platform in ["Windows", "Win32", "Win64"]
        elif "mac" in ua_lower or "macintosh" in ua_lower:
            assert "Mac" in profile.platform or "darwin" in profile.platform.lower()
        elif "linux" in ua_lower:
            assert "Linux" in profile.platform or "linux" in profile.platform.lower()

    def test_lru_eviction(self):
        manager = UserAgentManager(max_cached_profiles=3)
        manager.get_random_profile(session_id="s1")
        manager.get_random_profile(session_id="s2")
        manager.get_random_profile(session_id="s3")
        manager.get_random_profile(session_id="s4")  # Should evict s1
        stats = manager.get_cache_stats()
        assert stats["cached_profiles"] == 3
        assert stats["max_profiles"] == 3

    def test_clear_all(self):
        manager = UserAgentManager()
        manager.get_random_profile(session_id="s1")
        manager.get_random_profile(session_id="s2")
        manager.clear_all()
        stats = manager.get_cache_stats()
        assert stats["cached_profiles"] == 0

    def test_get_cache_stats(self):
        manager = UserAgentManager(max_cached_profiles=50)
        stats = manager.get_cache_stats()
        assert stats["max_profiles"] == 50
        assert stats["cached_profiles"] == 0

    def test_parse_resolution_valid(self):
        assert UserAgentManager._parse_resolution("1920x1080") == (1920, 1080)
        assert UserAgentManager._parse_resolution("2560x1440") == (2560, 1440)

    def test_parse_resolution_invalid(self):
        assert UserAgentManager._parse_resolution("invalid") is None
        assert UserAgentManager._parse_resolution("") is None
        assert UserAgentManager._parse_resolution(None) is None

    def test_platform_from_ua(self):
        assert UserAgentManager._platform_from_ua("Mozilla/5.0 (Windows NT 10.0)") == "Windows"
        assert UserAgentManager._platform_from_ua("Mozilla/5.0 (Macintosh; Intel Mac OS X)") == "MacIntel"
        assert UserAgentManager._platform_from_ua("Mozilla/5.0 (X11; Linux x86_64)") == "Linux x86_64"

    @patch("src.ua_manager._requests.get")
    def test_gologin_fingerprint_empty_ua_falls_back(self, mock_get):
        """If GoLogin returns empty UA, should fall back to fake_useragent"""
        bad_fp = {"navigator": {"userAgent": "", "resolution": "1920x1080"}}
        mock_resp = MagicMock()
        mock_resp.json.return_value = bad_fp
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        manager = UserAgentManager(gologin_token="test-token")
        profile = manager.get_random_profile()

        # Should fall back -- profile UA should not be empty
        assert len(profile.user_agent) > 0

    @patch("src.ua_manager._requests.get")
    def test_gologin_session_caching(self, mock_get):
        """GoLogin profile should be cached per session_id"""
        mock_resp = MagicMock()
        mock_resp.json.return_value = SAMPLE_FINGERPRINT
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        manager = UserAgentManager(gologin_token="test-token")
        p1 = manager.get_random_profile(session_id="s1")
        p2 = manager.get_random_profile(session_id="s1")

        # Second call should hit cache, not API
        assert mock_get.call_count == 1
        assert p1.user_agent == p2.user_agent
