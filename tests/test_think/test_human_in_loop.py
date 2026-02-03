"""Tests for Human-in-the-Loop"""
import pytest
import asyncio
from datetime import datetime

from src.think import (
    HumanApprovalManager,
    ApprovalConfig,
    ApprovalRequest,
    ApprovalStatus,
    Decision,
    create_initial_state,
    update_state_for_approval,
    update_state_after_approval,
    CCPPhase,
)


class TestApprovalConfig:
    def test_default_config(self):
        config = ApprovalConfig()
        assert config.confidence_threshold == 0.7
        assert config.auto_approve_above == 0.9
        assert config.default_timeout == 300.0

    def test_custom_config(self):
        config = ApprovalConfig(
            confidence_threshold=0.8,
            enable_escalation=False,
        )
        assert config.confidence_threshold == 0.8
        assert config.enable_escalation is False


class TestHumanApprovalManager:
    def test_create_manager(self):
        manager = HumanApprovalManager()
        assert manager.config.confidence_threshold == 0.7

    def test_needs_approval_low_confidence(self):
        manager = HumanApprovalManager()
        decision = Decision(action="proceed", confidence=0.5)
        assert manager.needs_approval(decision) is True

    def test_no_approval_high_confidence(self):
        manager = HumanApprovalManager()
        decision = Decision(action="proceed", confidence=0.95)
        assert manager.needs_approval(decision) is False

    def test_needs_approval_high_risk_action(self):
        manager = HumanApprovalManager()
        decision = Decision(action="abort", confidence=0.9)
        assert manager.needs_approval(decision) is True

    def test_create_request(self):
        manager = HumanApprovalManager()
        decision = Decision(action="proceed", confidence=0.5)
        state = create_initial_state(
            task_id="test",
            task_type="navigate",
            target="https://example.com",
        )

        request = manager.create_request("test", decision, state)

        assert request.task_id == "test"
        assert request.status == ApprovalStatus.PENDING
        assert request.decision.confidence == 0.5

    def test_approve_request(self):
        manager = HumanApprovalManager()
        decision = Decision(action="proceed", confidence=0.5)
        state = create_initial_state(
            task_id="test",
            task_type="navigate",
            target="https://example.com",
        )

        request = manager.create_request("test", decision, state)
        result = manager.approve(request.request_id, "user", "Looks good")

        assert result is True
        resolved = manager.get_request(request.request_id)
        assert resolved.status == ApprovalStatus.APPROVED
        assert resolved.resolved_by == "user"

    def test_reject_request(self):
        manager = HumanApprovalManager()
        decision = Decision(action="proceed", confidence=0.5)
        state = create_initial_state(
            task_id="test",
            task_type="navigate",
            target="https://example.com",
        )

        request = manager.create_request("test", decision, state)
        result = manager.reject(request.request_id, "user", "Not safe")

        assert result is True
        resolved = manager.get_request(request.request_id)
        assert resolved.status == ApprovalStatus.REJECTED

    def test_get_pending_requests(self):
        manager = HumanApprovalManager()
        decision = Decision(action="proceed", confidence=0.5)
        state = create_initial_state(
            task_id="test",
            task_type="navigate",
            target="https://example.com",
        )

        manager.create_request("test1", decision, state)
        manager.create_request("test2", decision, state)

        pending = manager.get_pending_requests()
        assert len(pending) == 2

    def test_get_stats(self):
        manager = HumanApprovalManager()
        decision = Decision(action="proceed", confidence=0.5)
        state = create_initial_state(
            task_id="test",
            task_type="navigate",
            target="https://example.com",
        )

        req1 = manager.create_request("test1", decision, state)
        req2 = manager.create_request("test2", decision, state)

        manager.approve(req1.request_id)
        manager.reject(req2.request_id)

        stats = manager.get_stats()
        assert stats["resolved_count"] == 2
        assert stats["approved_count"] == 1
        assert stats["rejected_count"] == 1


class TestStateUpdates:
    def test_update_state_for_approval(self):
        state = create_initial_state(
            task_id="test",
            task_type="navigate",
            target="https://example.com",
        )
        decision = Decision(action="proceed", confidence=0.5)
        request = ApprovalRequest(
            request_id="req_001",
            task_id="test",
            decision=decision,
            state_summary={},
            created_at=datetime.now(),
        )

        updated = update_state_for_approval(state, decision, request)

        assert updated["requires_approval"] is True
        assert updated["approval_status"] == "pending"
        assert updated["current_phase"] == CCPPhase.AWAITING_APPROVAL

    def test_update_state_after_approved(self):
        state = create_initial_state(
            task_id="test",
            task_type="navigate",
            target="https://example.com",
        )
        state["current_phase"] = CCPPhase.AWAITING_APPROVAL

        updated = update_state_after_approval(state, ApprovalStatus.APPROVED, "OK")

        assert updated["approval_status"] == "approved"
        assert updated["current_phase"] == CCPPhase.COMMAND

    def test_update_state_after_rejected(self):
        state = create_initial_state(
            task_id="test",
            task_type="navigate",
            target="https://example.com",
        )
        state["current_phase"] = CCPPhase.AWAITING_APPROVAL

        updated = update_state_after_approval(state, ApprovalStatus.REJECTED, "Not safe")

        assert updated["approval_status"] == "rejected"
        assert updated["current_phase"] == CCPPhase.ABORTED
        assert "rejected" in updated["final_error"].lower()
