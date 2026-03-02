"""
Tests for ScraplingAgent
"""
import pytest
from unittest.mock import MagicMock, patch
from src.scrapling_agent import ScraplingConfig, ScraplingAgent, _build_scrapling_proxy
from src.proxy_provider import SmartProxyISPBackend


class TestScraplingConfig:
    def test_defaults(self):
        config = ScraplingConfig()
        assert config.area == "us"
        assert config.headless is True
        assert config.solve_cloudflare is False
        assert config.hide_canvas is True
        assert config.network_idle is True
        assert config.no_proxy is False
        assert config.smartproxy_host == "isp.decodo.com"
        assert config.smartproxy_port == 10001

    def test_custom_values(self):
        config = ScraplingConfig(
            area="jp",
            solve_cloudflare=True,
            headless=False,
            no_proxy=True,
        )
        assert config.area == "jp"
        assert config.solve_cloudflare is True
        assert config.headless is False
        assert config.no_proxy is True


class TestBuildScraplingProxy:
    def test_output_format(self):
        backend = SmartProxyISPBackend(
            username="testuser",
            password="testpass",
            host="proxy.example.com",
            port=12345,
        )
        result = _build_scrapling_proxy(backend, "us", "sess1")
        assert "server" in result
        assert "username" in result
        assert "password" in result
        assert result["server"] == "proxy.example.com:12345"
        assert result["password"] == "testpass"

    def test_credential_mapping(self):
        backend = SmartProxyISPBackend(
            username="myuser",
            password="mypass",
        )
        result = _build_scrapling_proxy(backend, "jp", "session_42")
        assert "myuser" in result["username"]
        assert "jp" in result["username"]
        assert "session_42" in result["username"]
        assert result["password"] == "mypass"


class TestScraplingAgentInit:
    def test_init_no_proxy(self):
        config = ScraplingConfig(no_proxy=True)
        agent = ScraplingAgent(config)
        assert agent.proxy_manager is None
        assert agent.ua_manager is not None

    def test_init_with_proxy(self):
        config = ScraplingConfig(
            smartproxy_username="user",
            smartproxy_password="pass",
        )
        agent = ScraplingAgent(config)
        assert agent.proxy_manager is not None

    def test_init_no_proxy_flag_overrides_credentials(self):
        config = ScraplingConfig(
            smartproxy_username="user",
            smartproxy_password="pass",
            no_proxy=True,
        )
        agent = ScraplingAgent(config)
        assert agent.proxy_manager is None


class TestScraplingAgentSessionKwargs:
    def test_session_kwargs_headless(self):
        config = ScraplingConfig(no_proxy=True, headless=True)
        agent = ScraplingAgent(config)
        kwargs = agent._get_session_params()
        assert kwargs["headless"] is True

    def test_session_kwargs_headless_false(self):
        config = ScraplingConfig(no_proxy=True, headless=False)
        agent = ScraplingAgent(config)
        kwargs = agent._get_session_params()
        assert kwargs["headless"] is False

    def test_session_kwargs_ua(self):
        config = ScraplingConfig(no_proxy=True)
        agent = ScraplingAgent(config)
        kwargs = agent._get_session_params()
        assert "useragent" in kwargs
        assert len(kwargs["useragent"]) > 0

    def test_session_kwargs_locale(self):
        config = ScraplingConfig(no_proxy=True, area="jp")
        agent = ScraplingAgent(config)
        kwargs = agent._get_session_params()
        assert "locale" in kwargs
        assert "ja" in kwargs["locale"].lower() or "jp" in kwargs["locale"].lower()

    def test_session_kwargs_hide_canvas(self):
        config = ScraplingConfig(no_proxy=True, hide_canvas=True)
        agent = ScraplingAgent(config)
        kwargs = agent._get_session_params()
        assert kwargs["hide_canvas"] is True

    def test_session_kwargs_block_webrtc(self):
        config = ScraplingConfig(no_proxy=True)
        agent = ScraplingAgent(config)
        kwargs = agent._get_session_params()
        assert kwargs["block_webrtc"] is True


class TestScraplingAgentRun:
    @pytest.mark.asyncio
    async def test_run_no_url(self):
        config = ScraplingConfig(no_proxy=True)
        agent = ScraplingAgent(config)
        result = await agent.run("")
        assert result["success"] is False
        assert "No URL" in result["error"]

    @pytest.mark.asyncio
    async def test_run_dict_task_no_url(self):
        config = ScraplingConfig(no_proxy=True)
        agent = ScraplingAgent(config)
        result = await agent.run({"page_action": "click"})
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_run_scrapling_not_installed(self):
        config = ScraplingConfig(no_proxy=True)
        agent = ScraplingAgent(config)
        with patch.dict("sys.modules", {"scrapling": None}):
            with patch("src.scrapling_agent.ScraplingAgent._get_session_params", return_value={
                "headless": True, "useragent": "test", "locale": "en-US",
                "timezone_id": "UTC", "hide_canvas": True, "block_webrtc": True,
            }):
                # Force ImportError by patching the import
                import builtins
                real_import = builtins.__import__
                def mock_import(name, *args, **kwargs):
                    if name == "scrapling":
                        raise ImportError("No module named 'scrapling'")
                    return real_import(name, *args, **kwargs)
                with patch("builtins.__import__", side_effect=mock_import):
                    result = await agent.run("https://example.com")
                    assert result["success"] is False
                    assert "scrapling not installed" in result["error"]

    def test_parse_task_string(self):
        config = ScraplingConfig(no_proxy=True)
        agent = ScraplingAgent(config)
        parsed = agent._parse_task("https://example.com")
        assert parsed["url"] == "https://example.com"
        assert parsed["page_action"] is None

    def test_parse_task_dict(self):
        config = ScraplingConfig(no_proxy=True, solve_cloudflare=True)
        agent = ScraplingAgent(config)
        parsed = agent._parse_task({"url": "https://example.com", "page_action": "click"})
        assert parsed["url"] == "https://example.com"
        assert parsed["page_action"] == "click"
        assert parsed["solve_cloudflare"] is True
