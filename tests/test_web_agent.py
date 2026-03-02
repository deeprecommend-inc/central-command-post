"""
Tests for WebAgent
"""
import pytest
from pydantic import ValidationError
from src.web_agent import WebAgent, AgentConfig


class TestAgentConfig:
    """Tests for AgentConfig with validation"""

    def test_default_config(self):
        config = AgentConfig()
        assert config.smartproxy_username == ""
        assert config.area == "us"
        assert config.parallel_sessions == 5
        assert config.headless is True
        assert config.max_retries == 3

    def test_custom_config(self):
        config = AgentConfig(
            smartproxy_username="user",
            smartproxy_password="pass",
            area="jp",
            parallel_sessions=3,
        )
        assert config.smartproxy_username == "user"
        assert config.area == "jp"
        assert config.parallel_sessions == 3

    def test_invalid_port_too_high(self):
        with pytest.raises(ValidationError):
            AgentConfig(smartproxy_port=70000)

    def test_invalid_parallel_sessions_zero(self):
        with pytest.raises(ValidationError):
            AgentConfig(parallel_sessions=0)

    def test_invalid_parallel_sessions_too_high(self):
        with pytest.raises(ValidationError):
            AgentConfig(parallel_sessions=100)

    def test_invalid_max_retries_negative(self):
        with pytest.raises(ValidationError):
            AgentConfig(max_retries=-1)

    def test_extra_fields_rejected(self):
        with pytest.raises(ValidationError):
            AgentConfig(unknown_field="value")

    def test_no_proxy_flag(self):
        config = AgentConfig(no_proxy=True)
        assert config.no_proxy is True


class TestWebAgent:
    """Tests for WebAgent"""

    def test_initialization_no_proxy(self):
        agent = WebAgent()
        assert agent.proxy_manager is None
        assert agent.ua_manager is not None
        assert agent.is_closed is False

    def test_initialization_with_proxy(self):
        config = AgentConfig(
            smartproxy_username="user",
            smartproxy_password="pass",
        )
        agent = WebAgent(config)
        assert agent.proxy_manager is not None

    def test_initialization_no_proxy_flag(self):
        config = AgentConfig(
            smartproxy_username="user",
            smartproxy_password="pass",
            no_proxy=True,
        )
        agent = WebAgent(config)
        assert agent.proxy_manager is None

    def test_is_closed_property(self):
        agent = WebAgent()
        assert agent.is_closed is False

    def test_get_proxy_stats_no_proxy(self):
        agent = WebAgent()
        stats = agent.get_proxy_stats()
        assert stats == {}

    def test_get_proxy_health_no_proxy(self):
        agent = WebAgent()
        health = agent.get_proxy_health()
        assert health == {}


class TestWebAgentAsync:
    """Async tests for WebAgent"""

    @pytest.mark.asyncio
    async def test_cleanup(self):
        agent = WebAgent()
        await agent.cleanup()
        assert agent.is_closed is True

    @pytest.mark.asyncio
    async def test_double_cleanup(self):
        agent = WebAgent()
        await agent.cleanup()
        await agent.cleanup()  # Should not raise
        assert agent.is_closed is True

    @pytest.mark.asyncio
    async def test_context_manager(self):
        async with WebAgent() as agent:
            assert agent.is_closed is False
        assert agent.is_closed is True

    @pytest.mark.asyncio
    async def test_check_closed_raises(self):
        agent = WebAgent()
        await agent.cleanup()
        with pytest.raises(RuntimeError, match="closed"):
            agent._check_closed()

    @pytest.mark.asyncio
    async def test_navigate_after_close_raises(self):
        agent = WebAgent()
        await agent.cleanup()
        with pytest.raises(RuntimeError, match="closed"):
            await agent.navigate("https://example.com")

    @pytest.mark.asyncio
    async def test_parallel_navigate_after_close_raises(self):
        agent = WebAgent()
        await agent.cleanup()
        with pytest.raises(RuntimeError, match="closed"):
            await agent.parallel_navigate(["https://example.com"])

    @pytest.mark.asyncio
    async def test_health_check_no_proxy(self):
        agent = WebAgent()
        result = await agent.health_check()
        assert result == {}
