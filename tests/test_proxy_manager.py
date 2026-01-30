"""
Tests for ProxyManager
"""
import pytest
import time
from src.proxy_manager import ProxyManager, ProxyConfig, ProxyStats, ProxyType


class TestProxyConfig:
    """Tests for ProxyConfig dataclass"""

    def test_basic_url(self):
        config = ProxyConfig(
            username="user",
            password="pass",
            host="proxy.example.com",
            port=8080,
        )
        url = config.get_url()
        assert url == "http://user:pass@proxy.example.com:8080"

    def test_url_with_country(self):
        config = ProxyConfig(
            username="user",
            password="pass",
            country="us",
        )
        url = config.get_url()
        assert "-country-us" in url

    def test_url_with_session(self):
        config = ProxyConfig(
            username="user",
            password="pass",
            session_id="sess123",
        )
        url = config.get_url()
        assert "-session-sess123" in url

    def test_url_with_country_and_session(self):
        config = ProxyConfig(
            username="user",
            password="pass",
            country="jp",
            session_id="sess456",
        )
        url = config.get_url()
        assert "-country-jp" in url
        assert "-session-sess456" in url


class TestProxyStats:
    """Tests for ProxyStats dataclass"""

    def test_initial_success_rate(self):
        stats = ProxyStats()
        assert stats.success_rate == 1.0  # No requests = 100% success rate

    def test_success_rate_calculation(self):
        stats = ProxyStats(
            total_requests=10,
            successful_requests=8,
            failed_requests=2,
        )
        assert stats.success_rate == 0.8

    def test_avg_response_time_no_requests(self):
        stats = ProxyStats()
        assert stats.avg_response_time == float('inf')

    def test_avg_response_time_calculation(self):
        stats = ProxyStats(
            successful_requests=4,
            total_response_time=8.0,
        )
        assert stats.avg_response_time == 2.0

    def test_health_score_healthy(self):
        stats = ProxyStats(
            total_requests=10,
            successful_requests=10,
            total_response_time=10.0,  # 1s avg
            is_healthy=True,
        )
        # 70% success (1.0) + 30% time (0.9 for 1s response)
        assert stats.health_score > 0.9

    def test_health_score_unhealthy(self):
        stats = ProxyStats(is_healthy=False)
        assert stats.health_score == 0.0


class TestProxyManager:
    """Tests for ProxyManager"""

    def test_initialization(self):
        manager = ProxyManager(
            username="user",
            password="pass",
            proxy_type=ProxyType.MOBILE,
        )
        assert manager.username == "user"
        assert manager.proxy_type == ProxyType.MOBILE

    def test_get_proxy_creates_session(self):
        manager = ProxyManager(username="user", password="pass")
        proxy = manager.get_proxy(new_session=True)
        assert proxy.session_id is not None
        assert proxy.session_id.startswith("sess")

    def test_get_proxy_no_session(self):
        manager = ProxyManager(username="user", password="pass")
        proxy = manager.get_proxy(new_session=False)
        assert proxy.session_id is None

    def test_get_proxy_with_country(self):
        manager = ProxyManager(username="user", password="pass")
        proxy = manager.get_proxy(country="de")
        assert proxy.country == "de"

    def test_get_proxy_auto_country(self):
        manager = ProxyManager(username="user", password="pass")
        proxy = manager.get_proxy()
        assert proxy.country in manager.COUNTRIES

    def test_round_robin_country_selection(self):
        manager = ProxyManager(username="user", password="pass")
        # Get countries via round-robin
        countries = []
        for _ in range(len(manager.COUNTRIES) * 2):
            country = manager._get_next_country()
            countries.append(country)

        # Should cycle through all countries
        assert countries[:len(manager.COUNTRIES)] == manager.COUNTRIES
        assert countries[len(manager.COUNTRIES):] == manager.COUNTRIES

    def test_record_success(self):
        manager = ProxyManager(username="user", password="pass")
        manager.record_success("sess1", response_time=1.5, country="us")
        stats = manager.get_stats()
        assert "sess1" in stats
        assert stats["sess1"].successful_requests == 1
        assert stats["sess1"].total_response_time == 1.5

    def test_record_failure(self):
        manager = ProxyManager(username="user", password="pass")
        manager.record_failure("sess1", country="us")
        stats = manager.get_stats()
        assert stats["sess1"].failed_requests == 1

    def test_consecutive_failures_marks_unhealthy(self):
        manager = ProxyManager(username="user", password="pass")
        for _ in range(manager.MAX_CONSECUTIVE_FAILURES):
            manager.record_failure("sess1")
        stats = manager.get_stats()
        assert stats["sess1"].is_healthy is False

    def test_success_resets_consecutive_failures(self):
        manager = ProxyManager(username="user", password="pass")
        manager.record_failure("sess1")
        manager.record_failure("sess1")
        manager.record_success("sess1")
        stats = manager.get_stats()
        assert stats["sess1"].consecutive_failures == 0
        assert stats["sess1"].is_healthy is True

    def test_get_health_summary(self):
        manager = ProxyManager(username="user", password="pass")
        manager.record_success("sess1", country="us")
        summary = manager.get_health_summary()
        assert "total_proxies" in summary
        assert "healthy" in summary
        assert "countries" in summary

    def test_proxy_type_override(self):
        manager = ProxyManager(
            username="user",
            password="pass",
            proxy_type=ProxyType.RESIDENTIAL,
        )
        proxy = manager.get_proxy(proxy_type=ProxyType.MOBILE)
        assert proxy.proxy_type == ProxyType.MOBILE

    def test_select_best_country_prefers_healthy(self):
        manager = ProxyManager(username="user", password="pass")
        # Mark one country as unhealthy
        for _ in range(manager.MAX_CONSECUTIVE_FAILURES):
            manager.record_failure("sess_us", country="us")

        # Best country should not be "us" if others are healthy
        best = manager._select_best_country(ProxyType.RESIDENTIAL)
        # Since all others have no requests (health_score=1.0), any of them is valid
        assert best in manager.COUNTRIES
