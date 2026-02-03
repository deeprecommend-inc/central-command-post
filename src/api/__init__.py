"""
CCP API Layer - FastAPI-based REST/WebSocket API

v2 Features:
- LangGraph workflow execution
- Human-in-the-Loop approval workflow
- Thought Log Chain of Thought storage
"""
from .server import create_app, get_ccp, app
from .models import (
    # Core models
    TaskRequest,
    TaskResponse,
    TaskStatus,
    StatsResponse,
    HealthResponse,
    ExperienceResponse,
    # v2: Workflow
    WorkflowRequest,
    WorkflowResponse,
    WorkflowPhase,
    ThoughtStepResponse,
    # v2: Approvals
    ApprovalRequestResponse,
    ApprovalListResponse,
    ApprovalDecisionRequest,
    ApprovalStatsResponse,
    ApprovalStatusEnum,
    # v2: Thoughts
    ThoughtChainResponse,
    ThoughtChainListResponse,
    ThoughtLogStatsResponse,
)

__all__ = [
    # Server
    "create_app",
    "get_ccp",
    "app",
    # Core models
    "TaskRequest",
    "TaskResponse",
    "TaskStatus",
    "StatsResponse",
    "HealthResponse",
    "ExperienceResponse",
    # v2: Workflow
    "WorkflowRequest",
    "WorkflowResponse",
    "WorkflowPhase",
    "ThoughtStepResponse",
    # v2: Approvals
    "ApprovalRequestResponse",
    "ApprovalListResponse",
    "ApprovalDecisionRequest",
    "ApprovalStatsResponse",
    "ApprovalStatusEnum",
    # v2: Thoughts
    "ThoughtChainResponse",
    "ThoughtChainListResponse",
    "ThoughtLogStatsResponse",
]
