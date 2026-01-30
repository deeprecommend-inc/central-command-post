"""Tests for CCP Orchestrator"""
import pytest
from src.ccp import (
    CCPOrchestrator, CycleResult,
    SenseLayer, ThinkLayer, ControlLayer, LearnLayer,
)
from src.sense import SystemState
from src.think import Decision
from src.control import TaskState


class TestSenseLayer:
    """Tests for SenseLayer"""

    def test_initialization(self):
        sense = SenseLayer()
        assert sense.event_bus is not None
        assert sense.metrics is not None
        assert sense.snapshot is not None

    def test_get_state(self):
        sense = SenseLayer()
        state = sense.get_state()
        assert isinstance(state, SystemState)

    def test_record_metric(self):
        sense = SenseLayer()
        sense.record_metric("test", 1.0)
        latest = sense.metrics.get_latest("test", 1)
        assert len(latest) == 1

    @pytest.mark.asyncio
    async def test_publish_event(self):
        sense = SenseLayer()
        received = []

        async def handler(event):
            received.append(event)

        sense.event_bus.subscribe("test", handler)
        from src.sense import Event
        await sense.publish_event(Event("test", "test"))

        assert len(received) == 1


class TestThinkLayer:
    """Tests for ThinkLayer"""

    def test_initialization(self):
        think = ThinkLayer()
        assert think.rules_engine is not None
        assert think.retry_strategy is not None

    def test_decide_default(self):
        think = ThinkLayer()
        state = SystemState()
        decision = think.decide(state)
        assert isinstance(decision, Decision)

    def test_decide_with_task_context(self):
        think = ThinkLayer()
        state = SystemState()
        from src.think import TaskContext
        task = TaskContext(task_id="t1", task_type="nav", last_error_type="timeout")
        decision = think.decide(state, task)
        assert decision.action in ["retry", "abort", "proceed"]


class TestControlLayer:
    """Tests for ControlLayer"""

    def test_initialization(self):
        control = ControlLayer()
        assert control.executor is not None
        assert control.feedback_loop is not None


class TestLearnLayer:
    """Tests for LearnLayer"""

    def test_initialization(self):
        learn = LearnLayer()
        assert learn.knowledge is not None
        assert learn.patterns is not None
        assert learn.analyzer is not None

    def test_record_and_query(self):
        learn = LearnLayer()
        learn.record("test.key", "test_value", confidence=0.9)

        entry = learn.query("test.key")
        assert entry is not None
        assert entry.value == "test_value"


class TestCCPOrchestrator:
    """Tests for CCPOrchestrator"""

    def test_initialization(self):
        ccp = CCPOrchestrator()
        assert ccp.sense is not None
        assert ccp.think is not None
        assert ccp.control is not None
        assert ccp.learn is not None
        assert not ccp.is_closed

    def test_get_stats(self):
        ccp = CCPOrchestrator()
        stats = ccp.get_stats()
        assert "cycle_count" in stats
        assert stats["cycle_count"] == 0

    @pytest.mark.asyncio
    async def test_cleanup(self):
        ccp = CCPOrchestrator()
        await ccp.cleanup()
        assert ccp.is_closed


class TestCycleResult:
    """Tests for CycleResult dataclass"""

    def test_creation(self):
        from src.control import ExecutionResult
        result = CycleResult(
            task_id="t1",
            success=True,
            state=SystemState(),
            decision=Decision(action="proceed"),
            execution_result=ExecutionResult(task_id="t1", success=True),
            feedback=[],
        )
        assert result.task_id == "t1"
        assert result.success is True

    def test_to_dict(self):
        from src.control import ExecutionResult
        result = CycleResult(
            task_id="t1",
            success=True,
            state=SystemState(),
            decision=Decision(action="proceed"),
            execution_result=ExecutionResult(task_id="t1", success=True),
            feedback=[],
            cycle_number=1,
        )
        d = result.to_dict()
        assert d["task_id"] == "t1"
        assert d["cycle_number"] == 1
