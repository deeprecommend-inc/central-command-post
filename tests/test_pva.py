"""Tests for PVA - SMS verification service"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.pva import (
    PVAManager,
    PVAProvider,
    PVAStatus,
    PhoneOrder,
    PVAService,
    FiveSimProvider,
    SMSActivateProvider,
)


class MockProvider(PVAProvider):
    """Mock PVA provider for testing"""

    def __init__(self, should_fail=False):
        self.should_fail = should_fail
        self._numbers_given = 0
        self._finished = []
        self._cancelled = []

    async def get_number(self, service, country):
        if self.should_fail:
            return None
        self._numbers_given += 1
        return PhoneOrder(
            order_id=f"mock_{self._numbers_given}",
            phone_number=f"+1555000{self._numbers_given:04d}",
            country=country,
            service=service,
            provider=PVAService.FIVESIM,
            status=PVAStatus.WAITING,
        )

    async def check_sms(self, order):
        # Simulate receiving code on second check
        order.sms_code = "123456"
        order.status = PVAStatus.RECEIVED
        return order

    async def cancel(self, order):
        self._cancelled.append(order.order_id)
        order.status = PVAStatus.CANCELLED
        return True

    async def finish(self, order):
        self._finished.append(order.order_id)
        return True

    async def get_balance(self):
        return 100.0


@pytest.fixture
def mock_provider():
    return MockProvider()


@pytest.fixture
def failing_provider():
    return MockProvider(should_fail=True)


@pytest.fixture
def manager(mock_provider):
    return PVAManager(providers=[mock_provider], poll_interval=0.1)


@pytest.mark.asyncio
async def test_request_number(manager, mock_provider):
    order = await manager.request_number("google", "us")
    assert order is not None
    assert order.phone_number.startswith("+1555")
    assert order.status == PVAStatus.WAITING
    assert mock_provider._numbers_given == 1


@pytest.mark.asyncio
async def test_request_number_all_fail(failing_provider):
    manager = PVAManager(providers=[failing_provider], max_retries=2)
    order = await manager.request_number("google", "us")
    assert order is None


@pytest.mark.asyncio
async def test_wait_for_code(manager):
    order = await manager.request_number("google", "us")
    code = await manager.wait_for_code(order, timeout=5.0)
    assert code == "123456"


@pytest.mark.asyncio
async def test_complete_order(manager, mock_provider):
    order = await manager.request_number("google", "us")
    result = await manager.complete(order)
    assert result is True
    assert order.order_id in mock_provider._finished


@pytest.mark.asyncio
async def test_cancel_order(manager, mock_provider):
    order = await manager.request_number("google", "us")
    result = await manager.cancel_order(order)
    assert result is True
    assert order.order_id in mock_provider._cancelled


@pytest.mark.asyncio
async def test_fallback_providers():
    """Test that manager falls back to second provider when first fails"""
    failing = MockProvider(should_fail=True)
    working = MockProvider(should_fail=False)
    manager = PVAManager(providers=[failing, working], max_retries=1)

    order = await manager.request_number("google", "us")
    assert order is not None
    assert working._numbers_given == 1


def test_phone_order_age():
    import time
    order = PhoneOrder(
        order_id="1",
        phone_number="+1",
        country="us",
        service="google",
        provider=PVAService.FIVESIM,
        status=PVAStatus.WAITING,
        created_at=time.time() - 60,
    )
    assert order.age_seconds >= 59


def test_phone_order_no_created_at():
    order = PhoneOrder(
        order_id="1",
        phone_number="+1",
        country="us",
        service="google",
        provider=PVAService.FIVESIM,
        status=PVAStatus.WAITING,
    )
    assert order.age_seconds == 0.0


def test_pva_status_enum():
    assert PVAStatus.WAITING == "waiting"
    assert PVAStatus.RECEIVED == "received"
    assert PVAStatus.CANCELLED == "cancelled"


def test_sms_activate_service_codes():
    assert SMSActivateProvider.SERVICE_CODES["google"] == "go"
    assert SMSActivateProvider.SERVICE_CODES["twitter"] == "tw"
    assert SMSActivateProvider.SERVICE_CODES["instagram"] == "ig"
    assert SMSActivateProvider.SERVICE_CODES["tiktok"] == "lf"


@pytest.mark.asyncio
async def test_manager_no_providers():
    manager = PVAManager(providers=[])
    order = await manager.request_number("google", "us")
    assert order is None
