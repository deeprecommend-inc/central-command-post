"""
PVA (Phone Verified Account) - SMS verification service integration.

External Layer: provides phone numbers and receives SMS codes via third-party
PVA APIs for account verification flow.

Supports multiple providers with automatic fallback and retry logic.
"""
import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import aiohttp
from loguru import logger


class PVAStatus(str, Enum):
    WAITING = "waiting"
    RECEIVED = "received"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    ERROR = "error"


class PVAService(str, Enum):
    """Supported PVA services"""
    FIVESIM = "5sim"
    SMS_ACTIVATE = "sms-activate"


@dataclass
class PhoneOrder:
    """Active phone number order"""
    order_id: str
    phone_number: str
    country: str
    service: str
    provider: PVAService
    status: PVAStatus
    sms_code: str = ""
    created_at: float = 0.0

    @property
    def age_seconds(self) -> float:
        return time.time() - self.created_at if self.created_at else 0.0


class PVAProvider(ABC):
    """Abstract PVA provider interface"""

    @abstractmethod
    async def get_number(self, service: str, country: str) -> Optional[PhoneOrder]:
        """Request a phone number for the given service and country"""
        ...

    @abstractmethod
    async def check_sms(self, order: PhoneOrder) -> PhoneOrder:
        """Check if SMS code has been received"""
        ...

    @abstractmethod
    async def cancel(self, order: PhoneOrder) -> bool:
        """Cancel an active order (for refund)"""
        ...

    @abstractmethod
    async def finish(self, order: PhoneOrder) -> bool:
        """Mark order as complete (after successful use)"""
        ...

    @abstractmethod
    async def get_balance(self) -> float:
        """Get account balance"""
        ...


class FiveSimProvider(PVAProvider):
    """
    5sim.net PVA provider.

    API docs: https://5sim.net/docs
    """

    BASE_URL = "https://5sim.net/v1"

    def __init__(self, api_key: str):
        self._api_key = api_key
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        }

    async def _request(self, method: str, path: str, **kwargs) -> dict:
        async with aiohttp.ClientSession(headers=self._headers) as session:
            async with session.request(method, f"{self.BASE_URL}{path}", **kwargs) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise Exception(f"5sim API error {resp.status}: {text}")
                return await resp.json()

    async def get_number(self, service: str, country: str) -> Optional[PhoneOrder]:
        """Buy a phone number from 5sim"""
        try:
            # 5sim endpoint: /user/buy/activation/{country}/{operator}/{product}
            data = await self._request(
                "GET",
                f"/user/buy/activation/{country}/any/{service}",
            )
            return PhoneOrder(
                order_id=str(data["id"]),
                phone_number=str(data["phone"]),
                country=country,
                service=service,
                provider=PVAService.FIVESIM,
                status=PVAStatus.WAITING,
                created_at=time.time(),
            )
        except Exception as e:
            logger.error(f"5sim get_number failed: {e}")
            return None

    async def check_sms(self, order: PhoneOrder) -> PhoneOrder:
        """Check for received SMS"""
        try:
            data = await self._request("GET", f"/user/check/{order.order_id}")
            status = data.get("status", "")

            if status == "RECEIVED" and data.get("sms"):
                sms_list = data["sms"]
                if sms_list:
                    order.sms_code = sms_list[0].get("code", "")
                    order.status = PVAStatus.RECEIVED
            elif status == "CANCELED":
                order.status = PVAStatus.CANCELLED
            elif status == "TIMEOUT":
                order.status = PVAStatus.TIMEOUT

            return order
        except Exception as e:
            logger.error(f"5sim check_sms failed: {e}")
            order.status = PVAStatus.ERROR
            return order

    async def cancel(self, order: PhoneOrder) -> bool:
        try:
            await self._request("GET", f"/user/cancel/{order.order_id}")
            order.status = PVAStatus.CANCELLED
            return True
        except Exception as e:
            logger.error(f"5sim cancel failed: {e}")
            return False

    async def finish(self, order: PhoneOrder) -> bool:
        try:
            await self._request("GET", f"/user/finish/{order.order_id}")
            return True
        except Exception as e:
            logger.error(f"5sim finish failed: {e}")
            return False

    async def get_balance(self) -> float:
        try:
            data = await self._request("GET", "/user/profile")
            return float(data.get("balance", 0))
        except Exception as e:
            logger.error(f"5sim balance failed: {e}")
            return 0.0


class SMSActivateProvider(PVAProvider):
    """
    sms-activate.org PVA provider.

    API docs: https://sms-activate.org/en/api2
    """

    BASE_URL = "https://api.sms-activate.org/stubs/handler_api.php"

    # Service codes for sms-activate
    SERVICE_CODES = {
        "google": "go",
        "twitter": "tw",
        "instagram": "ig",
        "tiktok": "lf",
        "youtube": "go",  # Same as Google
    }

    def __init__(self, api_key: str):
        self._api_key = api_key

    async def _request(self, params: dict) -> str:
        params["api_key"] = self._api_key
        async with aiohttp.ClientSession() as session:
            async with session.get(self.BASE_URL, params=params) as resp:
                text = await resp.text()
                if "ERROR" in text or "BAD" in text or "NO_" in text:
                    raise Exception(f"sms-activate error: {text}")
                return text

    async def get_number(self, service: str, country: str) -> Optional[PhoneOrder]:
        try:
            svc_code = self.SERVICE_CODES.get(service, service)
            # Country mapping: sms-activate uses numeric IDs
            # 0=Russia, 1=Ukraine, 6=Indonesia, 12=USA, 16=UK, etc.
            text = await self._request({
                "action": "getNumber",
                "service": svc_code,
                "country": country,
            })
            # Response: ACCESS_NUMBER:ID:NUMBER
            parts = text.split(":")
            if len(parts) >= 3 and parts[0] == "ACCESS_NUMBER":
                return PhoneOrder(
                    order_id=parts[1],
                    phone_number=parts[2],
                    country=country,
                    service=service,
                    provider=PVAService.SMS_ACTIVATE,
                    status=PVAStatus.WAITING,
                    created_at=time.time(),
                )
            return None
        except Exception as e:
            logger.error(f"sms-activate get_number failed: {e}")
            return None

    async def check_sms(self, order: PhoneOrder) -> PhoneOrder:
        try:
            text = await self._request({
                "action": "getStatus",
                "id": order.order_id,
            })
            if text.startswith("STATUS_OK:"):
                order.sms_code = text.split(":")[1]
                order.status = PVAStatus.RECEIVED
            elif text == "STATUS_CANCEL":
                order.status = PVAStatus.CANCELLED

            return order
        except Exception as e:
            logger.error(f"sms-activate check_sms failed: {e}")
            order.status = PVAStatus.ERROR
            return order

    async def cancel(self, order: PhoneOrder) -> bool:
        try:
            await self._request({
                "action": "setStatus",
                "id": order.order_id,
                "status": 8,  # Cancel
            })
            order.status = PVAStatus.CANCELLED
            return True
        except Exception as e:
            logger.error(f"sms-activate cancel failed: {e}")
            return False

    async def finish(self, order: PhoneOrder) -> bool:
        try:
            await self._request({
                "action": "setStatus",
                "id": order.order_id,
                "status": 6,  # Complete
            })
            return True
        except Exception as e:
            logger.error(f"sms-activate finish failed: {e}")
            return False

    async def get_balance(self) -> float:
        try:
            text = await self._request({"action": "getBalance"})
            # Response: ACCESS_BALANCE:123.45
            if ":" in text:
                return float(text.split(":")[1])
            return 0.0
        except Exception as e:
            logger.error(f"sms-activate balance failed: {e}")
            return 0.0


class PVAManager:
    """
    PVA orchestrator with retry, polling, and provider fallback.

    Usage:
        manager = PVAManager(providers=[
            FiveSimProvider(api_key="..."),
            SMSActivateProvider(api_key="..."),
        ])

        order = await manager.request_number("google", "us")
        if order:
            # Enter phone number into form...
            code = await manager.wait_for_code(order, timeout=120)
            if code:
                # Enter code into form...
                await manager.complete(order)
    """

    def __init__(
        self,
        providers: Optional[list[PVAProvider]] = None,
        poll_interval: float = 5.0,
        max_retries: int = 3,
    ):
        self._providers = providers or []
        self._poll_interval = poll_interval
        self._max_retries = max_retries

    def add_provider(self, provider: PVAProvider) -> None:
        self._providers.append(provider)

    async def request_number(
        self,
        service: str,
        country: str,
    ) -> Optional[PhoneOrder]:
        """
        Request a phone number, trying each provider with retries.

        Args:
            service: Target service (google, twitter, instagram, tiktok)
            country: Country code

        Returns:
            PhoneOrder if successful, None if all providers failed
        """
        for provider in self._providers:
            for attempt in range(self._max_retries):
                order = await provider.get_number(service, country)
                if order:
                    logger.info(
                        f"PVA number acquired: {order.phone_number} "
                        f"(provider={order.provider.value}, service={service})"
                    )
                    return order

                logger.warning(
                    f"PVA attempt {attempt + 1}/{self._max_retries} failed, "
                    f"retrying..."
                )
                await asyncio.sleep(2.0 * (attempt + 1))

        logger.error(f"All PVA providers failed for {service}/{country}")
        return None

    async def wait_for_code(
        self,
        order: PhoneOrder,
        timeout: float = 120.0,
    ) -> Optional[str]:
        """
        Poll for SMS code with timeout.

        Args:
            order: Active phone order
            timeout: Max wait time in seconds

        Returns:
            SMS code string if received, None on timeout
        """
        provider = self._get_provider(order)
        if not provider:
            return None

        start = time.time()
        logger.info(f"Waiting for SMS code: {order.phone_number} (timeout={timeout}s)")

        while (time.time() - start) < timeout:
            order = await provider.check_sms(order)

            if order.status == PVAStatus.RECEIVED and order.sms_code:
                logger.info(f"SMS code received: {order.sms_code}")
                return order.sms_code

            if order.status in (PVAStatus.CANCELLED, PVAStatus.ERROR):
                logger.error(f"SMS order failed: {order.status}")
                return None

            await asyncio.sleep(self._poll_interval)

        logger.warning(f"SMS timeout after {timeout}s for {order.phone_number}")
        # Cancel on timeout for refund
        await provider.cancel(order)
        return None

    async def complete(self, order: PhoneOrder) -> bool:
        """Mark order as complete after successful use"""
        provider = self._get_provider(order)
        if provider:
            return await provider.finish(order)
        return False

    async def cancel_order(self, order: PhoneOrder) -> bool:
        """Cancel order for refund"""
        provider = self._get_provider(order)
        if provider:
            return await provider.cancel(order)
        return False

    def _get_provider(self, order: PhoneOrder) -> Optional[PVAProvider]:
        """Find the provider that handles this order"""
        for p in self._providers:
            if isinstance(p, FiveSimProvider) and order.provider == PVAService.FIVESIM:
                return p
            if isinstance(p, SMSActivateProvider) and order.provider == PVAService.SMS_ACTIVATE:
                return p
        return self._providers[0] if self._providers else None
