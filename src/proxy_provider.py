"""
Proxy Provider - Multi-provider proxy abstraction

Supported providers:
  - brightdata: BrightData (residential/mobile/datacenter/ISP)
  - dataimpulse: DataImpulse ($1/GB residential, $2/GB mobile)
  - generic: Any HTTP/SOCKS5 proxy URL
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Protocol

from loguru import logger


class ProxyProvider(str, Enum):
    BRIGHTDATA = "brightdata"
    DATAIMPULSE = "dataimpulse"
    GEONODE = "geonode"
    GENERIC = "generic"


class ProxyType(str, Enum):
    DATACENTER = "datacenter"
    RESIDENTIAL = "residential"
    MOBILE = "mobile"
    ISP = "isp"


@dataclass
class ProxyConfig:
    """Provider-agnostic proxy configuration"""
    provider: ProxyProvider
    url: str
    country: Optional[str] = None
    session_id: Optional[str] = None
    proxy_type: ProxyType = ProxyType.RESIDENTIAL

    def get_url(self) -> str:
        return self.url


class ProxyProviderBackend(Protocol):
    """Protocol for proxy provider backends"""

    def create_proxy(
        self,
        country: Optional[str],
        session_id: Optional[str],
        proxy_type: ProxyType,
    ) -> ProxyConfig: ...

    def get_rotating_url(self) -> str: ...

    @property
    def provider_name(self) -> ProxyProvider: ...


# ---------------------------------------------------------------------------
# BrightData
# ---------------------------------------------------------------------------

BRIGHTDATA_COUNTRIES = ["us", "gb", "de", "fr", "jp", "au", "ca"]


class BrightDataBackend:
    """BrightData proxy backend"""

    def __init__(
        self,
        username: str,
        password: str,
        host: str = "brd.superproxy.io",
        port: int = 22225,
    ):
        self.username = username
        self.password = password
        self.host = host
        self.port = port

    @property
    def provider_name(self) -> ProxyProvider:
        return ProxyProvider.BRIGHTDATA

    def create_proxy(
        self,
        country: Optional[str] = None,
        session_id: Optional[str] = None,
        proxy_type: ProxyType = ProxyType.RESIDENTIAL,
    ) -> ProxyConfig:
        user = self.username
        if country:
            user = f"{user}-country-{country}"
        if session_id:
            user = f"{user}-session-{session_id}"
        url = f"http://{user}:{self.password}@{self.host}:{self.port}"
        return ProxyConfig(
            provider=ProxyProvider.BRIGHTDATA,
            url=url,
            country=country,
            session_id=session_id,
            proxy_type=proxy_type,
        )

    def get_rotating_url(self) -> str:
        return f"http://{self.username}:{self.password}@{self.host}:{self.port}"

    def get_server_url(self) -> str:
        """Proxy server URL without credentials (for Chrome --proxy-server)"""
        return f"http://{self.host}:{self.port}"

    def get_auth(self, country: Optional[str] = None, session_id: Optional[str] = None) -> tuple[str, str]:
        """Return (username, password) for proxy auth extension"""
        user = self.username
        if country:
            user = f"{user}-country-{country}"
        if session_id:
            user = f"{user}-session-{session_id}"
        return user, self.password


# ---------------------------------------------------------------------------
# DataImpulse
# ---------------------------------------------------------------------------

DATAIMPULSE_COUNTRIES = ["us", "gb", "de", "fr", "jp", "br", "in", "ca", "au"]


class DataImpulseBackend:
    """
    DataImpulse proxy backend - $1/GB residential, $2/GB mobile.

    Authentication: HTTP proxy with user:pass.
    Format: http://user:pass@gw.dataimpulse.com:823
    Country targeting: append -country-XX to username.
    Session: append -session-XXX for sticky sessions.
    """

    RESIDENTIAL_HOST = "gw.dataimpulse.com"
    RESIDENTIAL_PORT = 823
    MOBILE_HOST = "gw.dataimpulse.com"
    MOBILE_PORT = 824

    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password

    @property
    def provider_name(self) -> ProxyProvider:
        return ProxyProvider.DATAIMPULSE

    def _resolve_host_port(self, proxy_type: ProxyType) -> tuple[str, int]:
        if proxy_type == ProxyType.MOBILE:
            return self.MOBILE_HOST, self.MOBILE_PORT
        return self.RESIDENTIAL_HOST, self.RESIDENTIAL_PORT

    def create_proxy(
        self,
        country: Optional[str] = None,
        session_id: Optional[str] = None,
        proxy_type: ProxyType = ProxyType.RESIDENTIAL,
    ) -> ProxyConfig:
        host, port = self._resolve_host_port(proxy_type)
        user = self.username
        if country:
            user = f"{user}-country-{country}"
        if session_id:
            user = f"{user}-session-{session_id}"
        url = f"http://{user}:{self.password}@{host}:{port}"
        return ProxyConfig(
            provider=ProxyProvider.DATAIMPULSE,
            url=url,
            country=country,
            session_id=session_id,
            proxy_type=proxy_type,
        )

    def get_rotating_url(self) -> str:
        host, port = self._resolve_host_port(ProxyType.RESIDENTIAL)
        return f"http://{self.username}:{self.password}@{host}:{port}"

    def get_server_url(self, proxy_type: ProxyType = ProxyType.RESIDENTIAL) -> str:
        host, port = self._resolve_host_port(proxy_type)
        return f"http://{host}:{port}"

    def get_auth(self, country: Optional[str] = None, session_id: Optional[str] = None) -> tuple[str, str]:
        user = self.username
        if country:
            user = f"{user}-country-{country}"
        if session_id:
            user = f"{user}-session-{session_id}"
        return user, self.password


# ---------------------------------------------------------------------------
# GeoNode ($49/mo unlimited residential)
# ---------------------------------------------------------------------------

GEONODE_COUNTRIES = ["us", "gb", "de", "fr", "jp", "br", "in", "ca", "au", "kr"]


class GeoNodeBackend:
    """
    GeoNode proxy backend - $49/mo unlimited bandwidth (thread-limited).

    Authentication: HTTP proxy with user:pass.
    Format: http://user:pass@premium-residential.geonode.com:9001
    Country targeting: via separate port or X-GeoNode-Country header.
    """

    HOST = "premium-residential.geonode.com"
    PORT = 9001
    STICKY_PORT = 9002

    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password

    @property
    def provider_name(self) -> ProxyProvider:
        return ProxyProvider.GEONODE

    def create_proxy(
        self,
        country: Optional[str] = None,
        session_id: Optional[str] = None,
        proxy_type: ProxyType = ProxyType.RESIDENTIAL,
    ) -> ProxyConfig:
        port = self.STICKY_PORT if session_id else self.PORT
        user = self.username
        if country:
            user = f"{user}-country-{country}"
        if session_id:
            user = f"{user}-session-{session_id}"
        url = f"http://{user}:{self.password}@{self.HOST}:{port}"
        return ProxyConfig(
            provider=ProxyProvider.GEONODE,
            url=url,
            country=country,
            session_id=session_id,
            proxy_type=proxy_type,
        )

    def get_rotating_url(self) -> str:
        return f"http://{self.username}:{self.password}@{self.HOST}:{self.PORT}"

    def get_server_url(self) -> str:
        return f"http://{self.HOST}:{self.PORT}"

    def get_auth(self, country: Optional[str] = None, session_id: Optional[str] = None) -> tuple[str, str]:
        user = self.username
        if country:
            user = f"{user}-country-{country}"
        if session_id:
            user = f"{user}-session-{session_id}"
        return user, self.password


# ---------------------------------------------------------------------------
# Generic HTTP/SOCKS Proxy
# ---------------------------------------------------------------------------


class GenericProxyBackend:
    """
    Generic proxy backend for any HTTP/SOCKS5 proxy.
    Accepts a single proxy URL or a list for rotation.
    """

    def __init__(self, urls: list[str]):
        if not urls:
            raise ValueError("At least one proxy URL is required")
        self.urls = urls
        self._index = 0

    @property
    def provider_name(self) -> ProxyProvider:
        return ProxyProvider.GENERIC

    def create_proxy(
        self,
        country: Optional[str] = None,
        session_id: Optional[str] = None,
        proxy_type: ProxyType = ProxyType.RESIDENTIAL,
    ) -> ProxyConfig:
        url = self.urls[self._index % len(self.urls)]
        self._index += 1
        return ProxyConfig(
            provider=ProxyProvider.GENERIC,
            url=url,
            country=country,
            session_id=session_id,
            proxy_type=proxy_type,
        )

    def get_rotating_url(self) -> str:
        return self.urls[0]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def create_proxy_backend(
    provider: str,
    username: str = "",
    password: str = "",
    host: str = "",
    port: int = 0,
    proxy_urls: Optional[list[str]] = None,
) -> ProxyProviderBackend:
    """Create a proxy backend from provider name and credentials"""
    provider = provider.lower()

    if provider == "brightdata":
        return BrightDataBackend(
            username=username,
            password=password,
            host=host or "brd.superproxy.io",
            port=port or 22225,
        )
    elif provider == "dataimpulse":
        return DataImpulseBackend(
            username=username,
            password=password,
        )
    elif provider == "geonode":
        return GeoNodeBackend(
            username=username,
            password=password,
        )
    elif provider == "generic":
        urls = proxy_urls or []
        if not urls and host:
            scheme = "http"
            auth = f"{username}:{password}@" if username else ""
            p = f":{port}" if port else ""
            urls = [f"{scheme}://{auth}{host}{p}"]
        return GenericProxyBackend(urls=urls)
    else:
        raise ValueError(f"Unknown proxy provider: {provider}. Use: brightdata, dataimpulse, geonode, generic")
