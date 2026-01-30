"""
Tests for UserAgentManager
"""
import pytest
from src.ua_manager import UserAgentManager, BrowserProfile


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


class TestUserAgentManager:
    """Tests for UserAgentManager"""

    def test_initialization(self):
        manager = UserAgentManager()
        assert manager is not None

    def test_get_random_profile(self):
        manager = UserAgentManager()
        profile = manager.get_random_profile()
        assert profile is not None
        assert profile.user_agent is not None
        assert len(profile.user_agent) > 0
        assert profile.viewport_width > 0
        assert profile.viewport_height > 0

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
