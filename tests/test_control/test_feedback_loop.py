"""Tests for FeedbackLoop"""
import pytest
from src.control import FeedbackLoop, Feedback, ExecutionResult


class TestFeedback:
    """Tests for Feedback dataclass"""

    def test_feedback_creation(self):
        fb = Feedback(
            task_id="t1",
            success=True,
            metric_type="response_time",
            value=0.5,
        )
        assert fb.task_id == "t1"
        assert fb.success is True
        assert fb.value == 0.5

    def test_feedback_to_dict(self):
        fb = Feedback(task_id="t1", success=True, metric_type="test", value=1.0)
        d = fb.to_dict()
        assert d["task_id"] == "t1"
        assert d["metric_type"] == "test"


class TestFeedbackLoop:
    """Tests for FeedbackLoop"""

    def test_initialization(self):
        loop = FeedbackLoop()
        summary = loop.get_summary()
        assert summary["status"] == "no_data"

    @pytest.mark.asyncio
    async def test_on_result_success(self):
        loop = FeedbackLoop()
        result = ExecutionResult(task_id="t1", success=True, duration=0.5)

        feedback = await loop.on_result(result)
        assert len(feedback) >= 2

        success_fb = [f for f in feedback if f.metric_type == "success"]
        assert len(success_fb) == 1
        assert success_fb[0].value == 1.0

    @pytest.mark.asyncio
    async def test_on_result_failure(self):
        loop = FeedbackLoop()
        result = ExecutionResult(task_id="t1", success=False, duration=0.5)

        feedback = await loop.on_result(result)
        success_fb = [f for f in feedback if f.metric_type == "success"]
        assert success_fb[0].value == 0.0

    @pytest.mark.asyncio
    async def test_on_result_with_retries(self):
        loop = FeedbackLoop()
        result = ExecutionResult(task_id="t1", success=True, retries=2, duration=0.5)

        feedback = await loop.on_result(result)
        retry_fb = [f for f in feedback if f.metric_type == "retries"]
        assert len(retry_fb) == 1
        assert retry_fb[0].value == 2.0

    def test_get_adjustments_empty(self):
        loop = FeedbackLoop()
        adjustments = loop.get_adjustments()
        assert adjustments == []

    @pytest.mark.asyncio
    async def test_get_adjustments_low_success(self):
        loop = FeedbackLoop()

        for i in range(20):
            result = ExecutionResult(task_id=f"t{i}", success=(i % 5 == 0), duration=0.5)
            await loop.on_result(result)

        adjustments = loop.get_adjustments()
        parallel_adj = [a for a in adjustments if a.parameter == "parallel_sessions"]
        assert len(parallel_adj) > 0

    def test_update_params(self):
        loop = FeedbackLoop()
        loop.update_params({"parallel_sessions": 10})

        summary = loop.get_summary()
        assert summary["current_params"]["parallel_sessions"] == 10

    def test_on_adjustment_handler(self):
        loop = FeedbackLoop()
        adjustments_received = []

        loop.on_adjustment(lambda adj: adjustments_received.append(adj))

        assert len(loop._adjustment_handlers) == 1

    def test_clear_history(self):
        loop = FeedbackLoop()
        loop._feedback_history.append(
            Feedback(task_id="t1", success=True, metric_type="test", value=1.0)
        )
        loop.clear_history()
        assert len(loop._feedback_history) == 0

    def test_get_summary_with_data(self):
        loop = FeedbackLoop()
        loop._feedback_history.append(
            Feedback(task_id="t1", success=True, metric_type="success", value=1.0)
        )
        loop._feedback_history.append(
            Feedback(task_id="t2", success=False, metric_type="success", value=0.0)
        )

        summary = loop.get_summary()
        assert summary["samples"] == 2
        assert summary["success_rate"] == 0.5
