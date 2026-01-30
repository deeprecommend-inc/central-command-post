"""Tests for Executor"""
import pytest
import asyncio
from src.control import Executor, ExecutionResult, Task, TaskState


class TestTask:
    """Tests for Task dataclass"""

    def test_task_creation(self):
        task = Task(
            task_id="t1",
            task_type="navigate",
            target="https://example.com",
        )
        assert task.task_id == "t1"
        assert task.task_type == "navigate"
        assert task.max_retries == 3
        assert task.timeout == 30.0

    def test_task_to_dict(self):
        task = Task(task_id="t1", task_type="nav", target="url")
        d = task.to_dict()
        assert d["task_id"] == "t1"


class TestExecutionResult:
    """Tests for ExecutionResult dataclass"""

    def test_result_creation(self):
        result = ExecutionResult(
            task_id="t1",
            success=True,
            data={"title": "Test"},
        )
        assert result.success is True
        assert result.data == {"title": "Test"}

    def test_result_to_dict(self):
        result = ExecutionResult(task_id="t1", success=False, error="Failed")
        d = result.to_dict()
        assert d["success"] is False
        assert d["error"] == "Failed"


class TestExecutor:
    """Tests for Executor"""

    def test_initialization(self):
        executor = Executor()
        assert executor.get_active_tasks() == []

    @pytest.mark.asyncio
    async def test_execute_success(self):
        executor = Executor()
        task = Task(task_id="t1", task_type="test", target="target")

        async def success_executor(t: Task) -> ExecutionResult:
            return ExecutionResult(task_id=t.task_id, success=True, data="ok")

        result = await executor.execute(task, success_executor)
        assert result.success is True
        assert result.state == TaskState.COMPLETED

    @pytest.mark.asyncio
    async def test_execute_failure(self):
        executor = Executor()
        task = Task(task_id="t1", task_type="test", target="target")

        async def fail_executor(t: Task) -> ExecutionResult:
            return ExecutionResult(task_id=t.task_id, success=False, error="oops")

        result = await executor.execute(task, fail_executor)
        assert result.success is False
        assert result.state == TaskState.FAILED

    @pytest.mark.asyncio
    async def test_execute_timeout(self):
        executor = Executor()
        task = Task(task_id="t1", task_type="test", target="target", timeout=0.1)

        async def slow_executor(t: Task) -> ExecutionResult:
            await asyncio.sleep(10)
            return ExecutionResult(task_id=t.task_id, success=True)

        result = await executor.execute(task, slow_executor)
        assert result.success is False
        assert result.error_type == "timeout"

    @pytest.mark.asyncio
    async def test_execute_exception(self):
        executor = Executor()
        task = Task(task_id="t1", task_type="test", target="target")

        async def error_executor(t: Task) -> ExecutionResult:
            raise ValueError("Boom!")

        result = await executor.execute(task, error_executor)
        assert result.success is False
        assert "Boom!" in result.error

    def test_get_state_not_found(self):
        executor = Executor()
        state = executor.get_state("nonexistent")
        assert state is None

    def test_get_result_not_found(self):
        executor = Executor()
        result = executor.get_result("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_result_after_execute(self):
        executor = Executor()
        task = Task(task_id="t1", task_type="test", target="target")

        async def executor_fn(t: Task) -> ExecutionResult:
            return ExecutionResult(task_id=t.task_id, success=True)

        await executor.execute(task, executor_fn)
        result = executor.get_result("t1")
        assert result is not None
        assert result.success is True

    def test_get_stats(self):
        executor = Executor()
        stats = executor.get_stats()
        assert "total_tasks" in stats
        assert "active_tasks" in stats

    @pytest.mark.asyncio
    async def test_cancel_running_task(self):
        executor = Executor()
        task = Task(task_id="t1", task_type="test", target="target", timeout=10)
        cancelled = False

        async def long_executor(t: Task) -> ExecutionResult:
            await asyncio.sleep(5)
            return ExecutionResult(task_id=t.task_id, success=True)

        async def cancel_task():
            await asyncio.sleep(0.1)
            return await executor.cancel("t1")

        results = await asyncio.gather(
            executor.execute(task, long_executor),
            cancel_task(),
        )

        assert results[1] is True
        assert results[0].state == TaskState.CANCELLED
