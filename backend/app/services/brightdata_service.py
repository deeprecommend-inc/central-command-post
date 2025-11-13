"""
BrightData API連携サービス
レジデンシャルプロキシ・データセンタープロキシ管理
"""

import httpx
from typing import Dict, Any, Optional
from ..core.config import settings


class BrightDataService:
    """BrightData Proxy Service"""

    def __init__(self):
        self.username = getattr(settings, 'BRIGHTDATA_USERNAME', '')
        self.password = getattr(settings, 'BRIGHTDATA_PASSWORD', '')
        self.zone = getattr(settings, 'BRIGHTDATA_ZONE', 'residential')
        self.proxy_host = 'brd.superproxy.io'
        self.proxy_port = 22225

    def get_residential_proxy(
        self,
        country: Optional[str] = None,
        city: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> str:
        """
        レジデンシャルプロキシを取得

        Args:
            country: 国コード (例: "us", "jp", "uk")
            city: 都市名 (例: "newyork", "tokyo")
            session_id: セッションID (同じIPを維持)

        Returns:
            プロキシURL (例: "http://user-zone-residential-country-us:pass@brd.superproxy.io:22225")
        """

        # ユーザー名にパラメータを追加
        username = f"{self.username}-zone-{self.zone}"

        if country:
            username += f"-country-{country.lower()}"

        if city:
            username += f"-city-{city.lower()}"

        if session_id:
            username += f"-session-{session_id}"

        return f"http://{username}:{self.password}@{self.proxy_host}:{self.proxy_port}"

    def get_datacenter_proxy(
        self,
        session_id: Optional[str] = None
    ) -> str:
        """
        データセンタープロキシを取得

        Args:
            session_id: セッションID

        Returns:
            プロキシURL
        """

        username = f"{self.username}-zone-datacenter"

        if session_id:
            username += f"-session-{session_id}"

        return f"http://{username}:{self.password}@{self.proxy_host}:{self.proxy_port}"

    def get_mobile_proxy(
        self,
        country: Optional[str] = None,
        carrier: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> str:
        """
        モバイルプロキシを取得

        Args:
            country: 国コード
            carrier: キャリア名 (例: "verizon", "tmobile", "att")
            session_id: セッションID

        Returns:
            プロキシURL
        """

        username = f"{self.username}-zone-mobile"

        if country:
            username += f"-country-{country.lower()}"

        if carrier:
            username += f"-carrier-{carrier.lower()}"

        if session_id:
            username += f"-session-{session_id}"

        return f"http://{username}:{self.password}@{self.proxy_host}:{self.proxy_port}"

    def get_isp_proxy(
        self,
        country: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> str:
        """
        ISPプロキシを取得 (レジデンシャルとデータセンターの中間)

        Args:
            country: 国コード
            session_id: セッションID

        Returns:
            プロキシURL
        """

        username = f"{self.username}-zone-isp"

        if country:
            username += f"-country-{country.lower()}"

        if session_id:
            username += f"-session-{session_id}"

        return f"http://{username}:{self.password}@{self.proxy_host}:{self.proxy_port}"

    async def test_proxy(self, proxy_url: str) -> Dict[str, Any]:
        """
        プロキシをテスト

        Returns:
            {"success": True, "ip": "xxx.xxx.xxx.xxx", "country": "US", "city": "New York"}
        """

        try:
            async with httpx.AsyncClient(proxies={"http://": proxy_url, "https://": proxy_url}, timeout=10) as client:
                # IPチェック
                response = await client.get("http://lumtest.com/myip.json")

                if response.status_code == 200:
                    data = response.json()
                    return {
                        "success": True,
                        "ip": data.get("ip"),
                        "country": data.get("country"),
                        "city": data.get("city"),
                        "asn": data.get("asn"),
                        "isp": data.get("org")
                    }

                return {"success": False, "error": f"HTTP {response.status_code}"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_proxy_for_persona(self, persona: Dict[str, Any], session_id: str) -> str:
        """
        ペルソナに基づいてプロキシを取得

        Args:
            persona: ペルソナ情報
            session_id: セッションID（アカウントごとに固定IP）

        Returns:
            プロキシURL
        """

        country = persona.get("location_country", "us")
        city = persona.get("location_city")

        # デバイスタイプに応じてプロキシタイプを選択
        device = persona.get("preferred_device", "desktop")

        if device == "mobile":
            return self.get_mobile_proxy(country=country, session_id=session_id)
        else:
            return self.get_residential_proxy(country=country, city=city, session_id=session_id)

    async def get_ip_info(self, ip: str) -> Dict[str, Any]:
        """
        IPアドレスの情報を取得

        Returns:
            {"country": "US", "city": "New York", "isp": "Comcast", "is_proxy": False}
        """

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(f"http://ip-api.com/json/{ip}")

                if response.status_code == 200:
                    data = response.json()
                    return {
                        "country": data.get("countryCode"),
                        "country_name": data.get("country"),
                        "city": data.get("city"),
                        "region": data.get("regionName"),
                        "isp": data.get("isp"),
                        "org": data.get("org"),
                        "as": data.get("as"),
                        "lat": data.get("lat"),
                        "lon": data.get("lon"),
                        "timezone": data.get("timezone"),
                        "is_proxy": data.get("proxy", False),
                        "is_hosting": data.get("hosting", False)
                    }

                return {"error": f"HTTP {response.status_code}"}

        except Exception as e:
            return {"error": str(e)}


# シングルトンインスタンス
brightdata_service = BrightDataService()
