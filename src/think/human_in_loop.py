"""
Human-in-the-Loop - Approval workflow for low-confidence decisions
"""
import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional, Awaitable
from loguru import logger

from .agent_state import AgentState, CCPPhase
from .strategy import Decision


class ApprovalStatus(str, Enum):
    """Status of an approval request"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    TIMEOUT = "timeout"
    ESCALATED = "escalated"


@dataclass
class ApprovalRequest:
    """Request for human approval"""
    request_id: str
    task_id: str
    decision: Decision
    state_summary: dict[str, Any]
    created_at: datetime
    timeout_seconds: float = 300.0  # 5 minutes default
    priority: int = 0  # Higher = more urgent
    context: str = ""
    status: ApprovalStatus = ApprovalStatus.PENDING
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    resolution_reason: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "request_id": self.request_id,
            "task_id": self.task_id,
            "decision": self.decision.to_dict(),
            "state_summary": self.state_summary,
            "created_at": self.created_at.isoformat(),
            "timeout_seconds": self.timeout_seconds,
            "priority": self.priority,
            "context": self.context,
            "status": self.status.value,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "resolved_by": self.resolved_by,
            "resolution_reason": self.resolution_reason,
        }


@dataclass
class ApprovalConfig:
    """Configuration for approval workflow"""
    confidence_threshold: float = 0.7
    auto_approve_above: float = 0.9
    default_timeout: float = 300.0
    max_pending_requests: int = 100
    enable_escalation: bool = True
    escalation_timeout: float = 600.0  # 10 minutes


ApprovalHandler = Callable[[ApprovalRequest], Awaitable[ApprovalStatus]]


class HumanApprovalManager:
    """
    Manages human-in-the-loop approval workflow.

    When decision confidence is below threshold, pauses execution
    and waits for human approval before proceeding.

    Example:
        manager = HumanApprovalManager()

        # Register approval handler (e.g., webhook, UI callback)
        manager.register_handler(my_approval_handler)

        # Check if decision needs approval
        if manager.needs_approval(decision):
            request = manager.create_request(task_id, decision, state)
            status = await manager.wait_for_approval(request)
    """

    def __init__(self, config: Optional[ApprovalConfig] = None):
        self.config = config or ApprovalConfig()
        self._pending_requests: dict[str, ApprovalRequest] = {}
        self._resolved_requests: list[ApprovalRequest] = []
        self._handlers: list[ApprovalHandler] = []
        self._approval_events: dict[str, asyncio.Event] = {}

    def register_handler(self, handler: ApprovalHandler) -> None:
        """
        Register an approval handler.

        Handler is called when new approval request is created.
        Can be used to send notifications, update UI, etc.
        """
        self._handlers.append(handler)

    def needs_approval(self, decision: Decision) -> bool:
        """
        Check if decision requires human approval.

        Args:
            decision: The decision to check

        Returns:
            True if approval is required
        """
        # Auto-approve high confidence decisions
        if decision.confidence >= self.config.auto_approve_above:
            return False

        # Require approval for low confidence
        if decision.confidence < self.config.confidence_threshold:
            return True

        # Special actions always need approval
        high_risk_actions = {"abort", "pause_operations", "reset_proxies"}
        if decision.action in high_risk_actions:
            return True

        return False

    def create_request(
        self,
        task_id: str,
        decision: Decision,
        state: AgentState,
        context: str = "",
        priority: int = 0,
    ) -> ApprovalRequest:
        """
        Create a new approval request.

        Args:
            task_id: Task identifier
            decision: Decision requiring approval
            state: Current agent state
            context: Additional context for reviewer
            priority: Request priority (higher = more urgent)

        Returns:
            ApprovalRequest
        """
        if len(self._pending_requests) >= self.config.max_pending_requests:
            # Remove oldest pending request
            oldest_id = next(iter(self._pending_requests))
            self._timeout_request(oldest_id)

        now = datetime.now()
        request_id = f"approval_{task_id}_{int(now.timestamp())}"

        # Build state summary for review
        state_summary = {
            "task_type": state.get("task_type"),
            "target": state.get("target"),
            "current_phase": state.get("current_phase", CCPPhase.SENSE).value,
            "retry_count": state.get("retry_count", 0),
            "max_retries": state.get("max_retries", 3),
            "error_history": state.get("error_history", [])[-3:],
        }

        system_state = state.get("system_state")
        if system_state:
            state_summary["success_rate"] = system_state.success_rate
            state_summary["error_count"] = system_state.error_count

        request = ApprovalRequest(
            request_id=request_id,
            task_id=task_id,
            decision=decision,
            state_summary=state_summary,
            created_at=now,
            timeout_seconds=self.config.default_timeout,
            priority=priority,
            context=context,
        )

        self._pending_requests[request_id] = request
        self._approval_events[request_id] = asyncio.Event()

        logger.info(
            f"Created approval request {request_id}: "
            f"action={decision.action}, confidence={decision.confidence:.2f}"
        )

        return request

    async def wait_for_approval(
        self,
        request: ApprovalRequest,
        timeout: Optional[float] = None,
    ) -> ApprovalStatus:
        """
        Wait for approval decision.

        Args:
            request: The approval request
            timeout: Optional custom timeout

        Returns:
            Final ApprovalStatus
        """
        timeout = timeout or request.timeout_seconds
        event = self._approval_events.get(request.request_id)

        if not event:
            logger.error(f"No event for request {request.request_id}")
            return ApprovalStatus.REJECTED

        # Notify handlers
        for handler in self._handlers:
            try:
                await handler(request)
            except Exception as e:
                logger.error(f"Approval handler error: {e}")

        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
            return request.status
        except asyncio.TimeoutError:
            logger.warning(f"Approval request {request.request_id} timed out")
            self._timeout_request(request.request_id)

            # Check for escalation
            if self.config.enable_escalation:
                return await self._escalate_request(request)

            return ApprovalStatus.TIMEOUT

    def approve(
        self,
        request_id: str,
        approved_by: str = "system",
        reason: str = "",
    ) -> bool:
        """
        Approve a pending request.

        Args:
            request_id: Request to approve
            approved_by: Identifier of approver
            reason: Optional reason for approval

        Returns:
            True if request was found and approved
        """
        request = self._pending_requests.get(request_id)
        if not request:
            logger.warning(f"Request {request_id} not found for approval")
            return False

        request.status = ApprovalStatus.APPROVED
        request.resolved_at = datetime.now()
        request.resolved_by = approved_by
        request.resolution_reason = reason

        self._resolve_request(request_id)
        logger.info(f"Approved request {request_id} by {approved_by}")
        return True

    def reject(
        self,
        request_id: str,
        rejected_by: str = "system",
        reason: str = "",
    ) -> bool:
        """
        Reject a pending request.

        Args:
            request_id: Request to reject
            rejected_by: Identifier of rejector
            reason: Optional reason for rejection

        Returns:
            True if request was found and rejected
        """
        request = self._pending_requests.get(request_id)
        if not request:
            logger.warning(f"Request {request_id} not found for rejection")
            return False

        request.status = ApprovalStatus.REJECTED
        request.resolved_at = datetime.now()
        request.resolved_by = rejected_by
        request.resolution_reason = reason

        self._resolve_request(request_id)
        logger.info(f"Rejected request {request_id} by {rejected_by}: {reason}")
        return True

    def _resolve_request(self, request_id: str) -> None:
        """Move request from pending to resolved"""
        request = self._pending_requests.pop(request_id, None)
        if request:
            self._resolved_requests.append(request)

            # Signal waiting coroutine
            event = self._approval_events.pop(request_id, None)
            if event:
                event.set()

    def _timeout_request(self, request_id: str) -> None:
        """Mark request as timed out"""
        request = self._pending_requests.get(request_id)
        if request:
            request.status = ApprovalStatus.TIMEOUT
            request.resolved_at = datetime.now()
            self._resolve_request(request_id)

    async def _escalate_request(self, request: ApprovalRequest) -> ApprovalStatus:
        """Escalate timed-out request"""
        request.status = ApprovalStatus.ESCALATED
        request.priority += 10  # Increase priority

        logger.warning(
            f"Escalating request {request.request_id}, "
            f"new priority: {request.priority}"
        )

        # Re-add to pending with extended timeout
        self._pending_requests[request.request_id] = request
        self._approval_events[request.request_id] = asyncio.Event()

        # Wait with escalation timeout
        try:
            event = self._approval_events[request.request_id]
            await asyncio.wait_for(
                event.wait(),
                timeout=self.config.escalation_timeout
            )
            return request.status
        except asyncio.TimeoutError:
            # Final timeout - auto-reject
            request.status = ApprovalStatus.TIMEOUT
            request.resolution_reason = "Escalation timeout exceeded"
            self._resolve_request(request.request_id)
            return ApprovalStatus.TIMEOUT

    def get_pending_requests(self) -> list[ApprovalRequest]:
        """Get all pending approval requests"""
        return list(self._pending_requests.values())

    def get_request(self, request_id: str) -> Optional[ApprovalRequest]:
        """Get a specific request by ID"""
        return self._pending_requests.get(request_id) or next(
            (r for r in self._resolved_requests if r.request_id == request_id),
            None
        )

    def get_stats(self) -> dict:
        """Get approval statistics"""
        resolved = self._resolved_requests
        approved = sum(1 for r in resolved if r.status == ApprovalStatus.APPROVED)
        rejected = sum(1 for r in resolved if r.status == ApprovalStatus.REJECTED)
        timed_out = sum(1 for r in resolved if r.status == ApprovalStatus.TIMEOUT)

        return {
            "pending_count": len(self._pending_requests),
            "resolved_count": len(resolved),
            "approved_count": approved,
            "rejected_count": rejected,
            "timeout_count": timed_out,
            "approval_rate": approved / len(resolved) if resolved else 0.0,
        }

    def clear_resolved(self) -> int:
        """Clear resolved requests history"""
        count = len(self._resolved_requests)
        self._resolved_requests.clear()
        return count


def update_state_for_approval(
    state: AgentState,
    decision: Decision,
    request: ApprovalRequest,
) -> AgentState:
    """
    Update agent state to await approval.

    Args:
        state: Current agent state
        decision: Decision requiring approval
        request: Approval request

    Returns:
        Updated state
    """
    state["requires_approval"] = True
    state["approval_status"] = "pending"
    state["current_phase"] = CCPPhase.AWAITING_APPROVAL
    state["decision_action"] = decision.action
    state["decision_params"] = decision.params
    state["decision_confidence"] = decision.confidence
    state["decision_reasoning"] = decision.reasoning

    return state


def update_state_after_approval(
    state: AgentState,
    status: ApprovalStatus,
    reason: str = "",
) -> AgentState:
    """
    Update agent state after approval decision.

    Args:
        state: Current agent state
        status: Approval status
        reason: Approval/rejection reason

    Returns:
        Updated state
    """
    state["approval_status"] = status.value
    state["approval_reason"] = reason

    if status == ApprovalStatus.APPROVED:
        state["current_phase"] = CCPPhase.COMMAND
    elif status in (ApprovalStatus.REJECTED, ApprovalStatus.TIMEOUT):
        state["current_phase"] = CCPPhase.ABORTED
        state["final_error"] = f"Approval {status.value}: {reason}"

    return state
