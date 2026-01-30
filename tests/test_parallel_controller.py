"""
Tests for ParallelController
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from src.parallel_controller import ParallelController, TaskResult
from src.browser_worker import WorkerResult, ErrorType
from src.proxy_manager import ProxyManager, ProxyType


class TestTaskResult:
    """Tests for TaskResult dataclass"""

    def test_success_result(self):
        result = TaskResult(
            worker_id="worker_1",
            success=True,
            data={"key": "value"},
            retries=0,
            duration=1.5,
        )
        assert result.success is True
        assert result.retries == 0

    def test_failure_result(self):
        result = TaskResult(
            worker_id="worker_1",
            success=False,
            error="some error",
            error_type=ErrorType.TIMEOUT,
            retries=2,
        )
        assert result.success is False
        assert result.error_type == ErrorType.TIMEOUT


class TestParallelController:
    """Tests for ParallelController"""

    def test_initialization(self):
        controller = ParallelController(max_workers=3)
        assert controller.max_workers == 3
        assert controller.max_retries == 3

    def test_initialization_with_proxy_manager(self):
        proxy_manager = ProxyManager(username="user", password="pass")
        controller = ParallelController(proxy_manager=proxy_manager)
        assert controller.proxy_manager is proxy_manager

    def test_calculate_delay(self):
        controller = ParallelController()
        assert controller._calculate_delay(0) == 1.0  # BASE_DELAY
        assert controller._calculate_delay(1) == 2.0
        assert controller._calculate_delay(2) == 4.0
        assert controller._calculate_delay(3) == 8.0
        assert controller._calculate_delay(10) == 30.0  # MAX_DELAY

    def test_is_retryable_success(self):
        controller = ParallelController()
        result = WorkerResult(success=True)
        assert controller._is_retryable(result) is False

    def test_is_retryable_timeout(self):
        controller = ParallelController()
        result = WorkerResult(
            success=False,
            error="timeout",
            error_type=ErrorType.TIMEOUT
        )
        assert controller._is_retryable(result) is True

    def test_is_retryable_connection(self):
        controller = ParallelController()
        result = WorkerResult(
            success=False,
            error="connection refused",
            error_type=ErrorType.CONNECTION
        )
        assert controller._is_retryable(result) is True

    def test_is_retryable_proxy(self):
        controller = ParallelController()
        result = WorkerResult(
            success=False,
            error="proxy error",
            error_type=ErrorType.PROXY
        )
        assert controller._is_retryable(result) is True

    def test_is_retryable_validation_false(self):
        controller = ParallelController()
        result = WorkerResult(
            success=False,
            error="validation error",
            error_type=ErrorType.VALIDATION
        )
        assert controller._is_retryable(result) is False

    def test_is_proxy_error_legacy(self):
        controller = ParallelController()
        assert controller._is_proxy_error_legacy("proxy connection failed") is True
        assert controller._is_proxy_error_legacy("ECONNREFUSED") is True
        assert controller._is_proxy_error_legacy("502 bad gateway") is True
        assert controller._is_proxy_error_legacy("element not found") is False

    def test_get_stats(self):
        controller = ParallelController(max_workers=5, max_retries=2)
        stats = controller.get_stats()
        assert stats["max_workers"] == 5
        assert stats["max_retries"] == 2
        assert stats["active_workers"] == 0


class TestParallelControllerAsync:
    """Async tests for ParallelController"""

    @pytest.mark.asyncio
    async def test_cleanup_all_empty(self):
        controller = ParallelController()
        await controller.cleanup_all()  # Should not raise

    @pytest.mark.asyncio
    async def test_run_parallel_empty_tasks(self):
        controller = ParallelController()
        results = await controller.run_parallel([])
        assert results == []

    @pytest.mark.asyncio
    async def test_cleanup_worker_not_exists(self):
        controller = ParallelController()
        # Should not raise for non-existent worker
        await controller._cleanup_worker("non_existent")
