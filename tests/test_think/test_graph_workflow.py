"""Tests for Graph Workflow"""
import pytest
import asyncio
from datetime import datetime

from src.think import (
    CCPGraphWorkflow,
    LLMConfig,
    ApprovalConfig,
    create_initial_state,
    CCPPhase,
)
from src.sense import SystemState


class TestCCPGraphWorkflow:
    def test_create_workflow(self):
        workflow = CCPGraphWorkflow()
        assert workflow.llm_maker is not None
        assert workflow.approval_manager is not None
        assert workflow.thought_logger is not None

    def test_create_with_config(self):
        workflow = CCPGraphWorkflow(
            llm_config=LLMConfig(provider="anthropic"),
            approval_config=ApprovalConfig(confidence_threshold=0.8),
        )
        assert workflow.llm_maker.config.provider == "anthropic"
        assert workflow.approval_manager.config.confidence_threshold == 0.8

    def test_configure_llm(self):
        workflow = CCPGraphWorkflow()
        workflow.configure_llm(LLMConfig(model="gpt-4o-mini"))
        assert workflow.llm_maker.config.model == "gpt-4o-mini"

    def test_set_executors(self):
        workflow = CCPGraphWorkflow()

        async def sense_exec(state):
            return {"system_state": SystemState()}

        async def command_exec(state):
            return {"success": True, "data": {}}

        workflow.set_sense_executor(sense_exec)
        workflow.set_command_executor(command_exec)

        assert workflow._sense_executor is not None
        assert workflow._command_executor is not None


class TestRoutingFunctions:
    def test_route_from_sense(self):
        workflow = CCPGraphWorkflow()
        state = create_initial_state(
            task_id="test",
            task_type="navigate",
            target="https://example.com",
        )

        route = workflow._route_from_sense(state)
        assert route == "think"

    def test_route_from_sense_abort_on_errors(self):
        workflow = CCPGraphWorkflow()
        state = create_initial_state(
            task_id="test",
            task_type="navigate",
            target="https://example.com",
        )
        state["error_history"] = ["e1", "e2", "e3", "e4", "e5", "e6"]

        route = workflow._route_from_sense(state)
        assert route == "aborted"

    def test_route_from_think_proceed(self):
        workflow = CCPGraphWorkflow()
        state = create_initial_state(
            task_id="test",
            task_type="navigate",
            target="https://example.com",
        )
        state["decision_action"] = "proceed"
        state["requires_approval"] = False

        route = workflow._route_from_think(state)
        assert route == "command"

    def test_route_from_think_abort(self):
        workflow = CCPGraphWorkflow()
        state = create_initial_state(
            task_id="test",
            task_type="navigate",
            target="https://example.com",
        )
        state["decision_action"] = "abort"

        route = workflow._route_from_think(state)
        assert route == "aborted"

    def test_route_from_think_approval(self):
        workflow = CCPGraphWorkflow()
        state = create_initial_state(
            task_id="test",
            task_type="navigate",
            target="https://example.com",
        )
        state["requires_approval"] = True

        route = workflow._route_from_think(state)
        assert route == "awaiting_approval"

    def test_route_from_approval_approved(self):
        workflow = CCPGraphWorkflow()
        state = create_initial_state(
            task_id="test",
            task_type="navigate",
            target="https://example.com",
        )
        state["approval_status"] = "approved"

        route = workflow._route_from_approval(state)
        assert route == "command"

    def test_route_from_approval_rejected(self):
        workflow = CCPGraphWorkflow()
        state = create_initial_state(
            task_id="test",
            task_type="navigate",
            target="https://example.com",
        )
        state["approval_status"] = "rejected"

        route = workflow._route_from_approval(state)
        assert route == "aborted"

    def test_route_from_control_success(self):
        workflow = CCPGraphWorkflow()
        state = create_initial_state(
            task_id="test",
            task_type="navigate",
            target="https://example.com",
        )
        state["command_success"] = True

        route = workflow._route_from_control(state)
        assert route == "learn"

    def test_route_from_control_retry(self):
        workflow = CCPGraphWorkflow()
        state = create_initial_state(
            task_id="test",
            task_type="navigate",
            target="https://example.com",
            max_retries=3,
        )
        state["command_success"] = False
        state["retry_count"] = 1

        route = workflow._route_from_control(state)
        assert route == "sense"

    def test_route_from_control_max_retries(self):
        workflow = CCPGraphWorkflow()
        state = create_initial_state(
            task_id="test",
            task_type="navigate",
            target="https://example.com",
            max_retries=3,
        )
        state["command_success"] = False
        state["retry_count"] = 3

        route = workflow._route_from_control(state)
        assert route == "aborted"

    def test_route_from_learn(self):
        workflow = CCPGraphWorkflow()
        state = create_initial_state(
            task_id="test",
            task_type="navigate",
            target="https://example.com",
        )

        route = workflow._route_from_learn(state)
        assert route == "completed"


@pytest.mark.asyncio
class TestWorkflowExecution:
    async def test_run_fallback_success(self):
        workflow = CCPGraphWorkflow()

        # Set up executors
        async def sense_exec(state):
            return {"system_state": SystemState()}

        async def command_exec(state):
            return {"success": True, "data": {"title": "Test"}}

        async def control_exec(state):
            return {"state": "completed", "feedback": []}

        async def learn_exec(state):
            return {"patterns": [], "knowledge_updates": []}

        workflow.set_sense_executor(sense_exec)
        workflow.set_command_executor(command_exec)
        workflow.set_control_executor(control_exec)
        workflow.set_learn_executor(learn_exec)

        result = await workflow.run(
            task_id="test_001",
            task_type="navigate",
            target="https://example.com",
        )

        assert result["final_success"] is True
        assert result["current_phase"] == CCPPhase.COMPLETED

    async def test_run_fallback_failure(self):
        workflow = CCPGraphWorkflow()

        async def sense_exec(state):
            return {"system_state": SystemState()}

        async def command_exec(state):
            return {"success": False, "error": "Connection failed"}

        async def control_exec(state):
            return {"state": "failed", "feedback": []}

        workflow.set_sense_executor(sense_exec)
        workflow.set_command_executor(command_exec)
        workflow.set_control_executor(control_exec)

        result = await workflow.run(
            task_id="test_002",
            task_type="navigate",
            target="https://example.com",
            max_retries=1,
        )

        # After max retries, should abort
        assert result["final_success"] is False

    async def test_thought_chain_populated(self):
        workflow = CCPGraphWorkflow()

        async def sense_exec(state):
            return {"system_state": SystemState()}

        async def command_exec(state):
            return {"success": True, "data": {}}

        async def control_exec(state):
            return {"state": "completed", "feedback": []}

        async def learn_exec(state):
            return {"patterns": [], "knowledge_updates": []}

        workflow.set_sense_executor(sense_exec)
        workflow.set_command_executor(command_exec)
        workflow.set_control_executor(control_exec)
        workflow.set_learn_executor(learn_exec)

        result = await workflow.run(
            task_id="test_003",
            task_type="navigate",
            target="https://example.com",
        )

        # Should have thought steps from each phase
        thought_chain = result.get("thought_chain", [])
        assert len(thought_chain) >= 4  # sense, think, command, control, learn


class TestWorkflowStats:
    def test_get_stats(self):
        workflow = CCPGraphWorkflow()
        stats = workflow.get_stats()

        assert "thought_logger" in stats
        assert "approval_manager" in stats
