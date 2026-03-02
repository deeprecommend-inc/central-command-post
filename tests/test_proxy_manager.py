"""
Tests for ProxyManager and SmartProxyISPBackend
"""
import pytest
import time
from src.proxy_manager import ProxyManager, ProxyStats
from src.proxy_provider import (
    ProxyConfig, ProxyProvider, SmartProxyISPBackend,
)


class TestProxyConfig:
    """Tests for ProxyConfig dataclass"""

    def test_basic_url(self):
        config = ProxyConfig(
            provider=ProxyProvider.SMARTPROXY,
            url="http://user-test:pass@isp.decodo.com:10001",
        )
        assert config.get_url() == "http://user-test:pass@isp.decodo.com:10001"

    def test_url_with_country(self):
        backend = SmartProxyISPBackend(username="test", password="pass")
        config = backend.create_proxy(country="us")
        assert "-country-us" in config.get_url()

    def test_url_with_session(self):
        backend = SmartProxyISPBackend(username="test", password="pass")
        config = backend.create_proxy(session_id="sess123")
        assert "-session-sess123" in config.get_url()

    def test_url_with_country_and_session(self):
        backend = SmartProxyISPBackend(username="test", password="pass")
        config = backend.create_proxy(country="jp", session_id="sess456")
        url = config.get_url()
        assert "-country-jp" in url
        assert "-session-sess456" in url

    def test_url_contains_session_duration(self):
        backend = SmartProxyISPBackend(username="test", password="pass")
        config = backend.create_proxy(session_duration=60)
        assert "-sessionduration-60" in config.get_url()


class TestSmartProxyISPBackend:
    """Tests for SmartProxyISPBackend"""

    def test_provider_name(self):
        backend = SmartProxyISPBackend(username="user", password="pass")
        assert backend.provider_name == ProxyProvider.SMARTPROXY

    def test_default_host_port(self):
        backend = SmartProxyISPBackend(username="user", password="pass")
        assert backend.host == "isp.decodo.com"
        assert backend.port == 10001

    def test_custom_host_port(self):
        backend = SmartProxyISPBackend(username="user", password="pass", host="custom.proxy.com", port=9999)
        assert backend.host == "custom.proxy.com"
        assert backend.port == 9999

    def test_create_proxy(self):
        backend = SmartProxyISPBackend(username="user", password="pass")
        config = backend.create_proxy(country="us")
        assert "isp.decodo.com:10001" in config.get_url()
        assert config.provider == ProxyProvider.SMARTPROXY

    def test_get_server_url(self):
        backend = SmartProxyISPBackend(username="user", password="pass")
        assert backend.get_server_url() == "http://isp.decodo.com:10001"

    def test_get_auth(self):
        backend = SmartProxyISPBackend(username="user", password="pass")
        username, password = backend.get_auth(country="jp", session_id="w1")
        assert username == "user-user-country-jp-session-w1-sessionduration-30"
        assert password == "pass"

    def test_get_rotating_url(self):
        backend = SmartProxyISPBackend(username="user", password="pass")
        url = backend.get_rotating_url()
        assert "isp.decodo.com:10000" in url

    def test_username_format_full(self):
        backend = SmartProxyISPBackend(username="myuser", password="mypass")
        username, _ = backend.get_auth(country="de", session_id="w5", session_duration=60)
        assert username == "user-myuser-country-de-session-w5-sessionduration-60"

    def test_username_format_no_country(self):
        backend = SmartProxyISPBackend(username="myuser", password="mypass")
        username, _ = backend.get_auth(session_id="w1")
        assert username == "user-myuser-session-w1-sessionduration-30"
        assert "-country-" not in username

    def test_username_format_no_session(self):
        backend = SmartProxyISPBackend(username="myuser", password="mypass")
        username, _ = backend.get_auth(country="us")
        assert username == "user-myuser-country-us-sessionduration-30"
        assert "-session-" not in username


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

    def _make_manager(self, area="us"):
        backend = SmartProxyISPBackend(username="user", password="pass")
        return ProxyManager(backend=backend, area=area)

    def test_initialization(self):
        manager = self._make_manager()
        assert manager.provider_name == "smartproxy"
        assert manager.area == "us"

    def test_requires_backend(self):
        with pytest.raises(ValueError, match="SmartProxyISPBackend required"):
            ProxyManager(backend=None)

    def test_get_proxy_creates_session(self):
        manager = self._make_manager()
        proxy = manager.get_proxy(new_session=True)
        assert proxy.session_id is not None

    def test_get_proxy_no_session(self):
        manager = self._make_manager()
        proxy = manager.get_proxy(new_session=False)
        assert proxy.session_id is None

    def test_get_proxy_uses_area(self):
        manager = self._make_manager(area="jp")
        proxy = manager.get_proxy()
        assert proxy.country == "jp"

    def test_get_proxy_country_override(self):
        manager = self._make_manager(area="us")
        proxy = manager.get_proxy(country="de")
        assert proxy.country == "de"

    def test_get_proxy_worker_id(self):
        manager = self._make_manager()
        proxy = manager.get_proxy(worker_id=3)
        assert proxy.session_id is not None
        assert proxy.session_id.startswith("w3_")

    def test_record_success(self):
        manager = self._make_manager()
        manager.record_success("sess1", response_time=1.5, country="us")
        stats = manager.get_stats()
        assert "sess1" in stats
        assert stats["sess1"].successful_requests == 1
        assert stats["sess1"].total_response_time == 1.5

    def test_record_failure(self):
        manager = self._make_manager()
        manager.record_failure("sess1", country="us")
        stats = manager.get_stats()
        assert stats["sess1"].failed_requests == 1

    def test_consecutive_failures_marks_unhealthy(self):
        manager = self._make_manager()
        for _ in range(manager.MAX_CONSECUTIVE_FAILURES):
            manager.record_failure("sess1")
        stats = manager.get_stats()
        assert stats["sess1"].is_healthy is False

    def test_success_resets_consecutive_failures(self):
        manager = self._make_manager()
        manager.record_failure("sess1")
        manager.record_failure("sess1")
        manager.record_success("sess1")
        stats = manager.get_stats()
        assert stats["sess1"].consecutive_failures == 0
        assert stats["sess1"].is_healthy is True

    def test_get_health_summary(self):
        manager = self._make_manager()
        manager.record_success("sess1", country="us")
        summary = manager.get_health_summary()
        assert summary["provider"] == "smartproxy"
        assert summary["area"] == "us"
        assert "stats" in summary
