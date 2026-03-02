"""
Proxy Provider - SmartProxy ISP (Decodo) backend

Sticky endpoint: isp.decodo.com:10001
Auth: user-{username}-country-{cc}-session-{id}-sessionduration-{min}
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from loguru import logger


class ProxyProvider(str, Enum):
    SMARTPROXY = "smartproxy"


@dataclass
class ProxyConfig:
    """Proxy configuration"""
    provider: ProxyProvider
    url: str
    country: str | None = None
    session_id: str | None = None

    def get_url(self) -> str:
        return self.url


class SmartProxyISPBackend:
    """
    SmartProxy ISP (Decodo) proxy backend.

    Sticky sessions via unique session IDs per worker.
    Each worker gets a unique IP that persists for the session duration.
    """

    HOST = "isp.decodo.com"
    STICKY_PORT = 10001
    ROTATING_PORT = 10000

    def __init__(
        self,
        username: str,
        password: str,
        host: str = "",
        port: int = 0,
    ):
        self.username = username
        self.password = password
        self.host = host or self.HOST
        self.port = port or self.STICKY_PORT

    @property
    def provider_name(self) -> ProxyProvider:
        return ProxyProvider.SMARTPROXY

    def create_proxy(
        self,
        country: Optional[str] = None,
        session_id: Optional[str] = None,
        session_duration: int = 30,
    ) -> ProxyConfig:
        user = self._build_username(country, session_id, session_duration)
        url = f"http://{user}:{self.password}@{self.host}:{self.port}"
        return ProxyConfig(
            provider=ProxyProvider.SMARTPROXY,
            url=url,
            country=country,
            session_id=session_id,
        )

    def get_server_url(self) -> str:
        """Proxy server URL without credentials (for Chrome --proxy-server)"""
        return f"http://{self.host}:{self.port}"

    def get_auth(
        self,
        country: Optional[str] = None,
        session_id: Optional[str] = None,
        session_duration: int = 30,
    ) -> tuple[str, str]:
        """Return (username, password) for proxy auth extension"""
        user = self._build_username(country, session_id, session_duration)
        return user, self.password

    def get_rotating_url(self) -> str:
        """Get rotating proxy URL (port 10000)"""
        return f"http://{self.username}:{self.password}@{self.host}:{self.ROTATING_PORT}"

    def _build_username(
        self,
        country: Optional[str] = None,
        session_id: Optional[str] = None,
        session_duration: int = 30,
    ) -> str:
        """Build SmartProxy auth username string"""
        user = f"user-{self.username}"
        if country:
            user = f"{user}-country-{country}"
        if session_id:
            user = f"{user}-session-{session_id}"
        user = f"{user}-sessionduration-{session_duration}"
        return user
