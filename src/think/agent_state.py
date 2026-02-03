"""
Agent State - LangGraph state definitions for CCP workflow
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, TypedDict, Annotated, Optional
from operator import add

from ..sense import SystemState


class CCPPhase(str, Enum):
    """CCP cycle phases"""
    SENSE = "sense"
    THINK = "think"
    COMMAND = "command"
    CONTROL = "control"
    LEARN = "learn"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    ABORTED = "aborted"


class TransitionReason(str, Enum):
    """Reasons for state transitions"""
    INITIAL = "initial"
    DATA_COLLECTED = "data_collected"
    DECISION_MADE = "decision_made"
    LOW_CONFIDENCE = "low_confidence"
    APPROVED = "approved"
    REJECTED = "rejected"
    COMMAND_ISSUED = "command_issued"
    EXECUTION_COMPLETED = "execution_completed"
    LEARNING_RECORDED = "learning_recorded"
    ERROR_DETECTED = "error_detected"
    MAX_RETRIES_EXCEEDED = "max_retries_exceeded"


@dataclass
class ThoughtStep:
    """A single step in the chain of thought"""
    step_id: str
    phase: CCPPhase
    timestamp: datetime
    reasoning: str
    inputs: dict[str, Any]
    outputs: dict[str, Any]
    confidence: float = 1.0
    duration_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "step_id": self.step_id,
            "phase": self.phase.value,
            "timestamp": self.timestamp.isoformat(),
            "reasoning": self.reasoning,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "confidence": self.confidence,
            "duration_ms": self.duration_ms,
        }


@dataclass
class TransitionRecord:
    """Record of a state transition"""
    from_phase: CCPPhase
    to_phase: CCPPhase
    reason: TransitionReason
    timestamp: datetime
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "from_phase": self.from_phase.value,
            "to_phase": self.to_phase.value,
            "reason": self.reason.value,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


class AgentState(TypedDict, total=False):
    """
    LangGraph state for CCP agent workflow.

    This state is passed through the graph and updated at each node.
    Uses TypedDict for LangGraph compatibility.
    """
    # Core identifiers
    task_id: str
    cycle_id: str

    # Current phase
    current_phase: CCPPhase
    previous_phase: Optional[CCPPhase]

    # Task information
    task_type: str
    target: str
    params: dict[str, Any]

    # Sense layer outputs
    system_state: Optional[SystemState]
    recent_events: list[dict]
    metrics_summary: dict[str, Any]

    # Think layer outputs
    decision_action: str
    decision_params: dict[str, Any]
    decision_confidence: float
    decision_reasoning: str

    # Human-in-the-loop
    requires_approval: bool
    approval_status: Optional[str]  # "pending", "approved", "rejected"
    approval_reason: Optional[str]

    # Command layer outputs
    command_result: Optional[dict]
    command_success: bool
    command_error: Optional[str]

    # Control layer outputs
    execution_state: str
    feedback: list[dict]

    # Learn layer outputs
    patterns_detected: list[dict]
    knowledge_updates: list[dict]

    # Execution tracking
    retry_count: int
    max_retries: int
    error_history: list[str]

    # Chain of thought
    thought_chain: Annotated[list[ThoughtStep], add]
    transitions: Annotated[list[TransitionRecord], add]

    # Timing
    start_time: datetime
    end_time: Optional[datetime]
    total_duration_ms: float

    # Final result
    final_success: bool
    final_error: Optional[str]


def create_initial_state(
    task_id: str,
    task_type: str,
    target: str,
    params: Optional[dict] = None,
    max_retries: int = 3,
) -> AgentState:
    """
    Create initial agent state for a new CCP cycle.

    Args:
        task_id: Unique task identifier
        task_type: Type of task (navigate, scrape, etc.)
        target: Target URL or identifier
        params: Additional task parameters
        max_retries: Maximum retry attempts

    Returns:
        Initialized AgentState
    """
    now = datetime.now()
    cycle_id = f"cycle_{task_id}_{int(now.timestamp())}"

    return AgentState(
        task_id=task_id,
        cycle_id=cycle_id,
        current_phase=CCPPhase.SENSE,
        previous_phase=None,
        task_type=task_type,
        target=target,
        params=params or {},
        system_state=None,
        recent_events=[],
        metrics_summary={},
        decision_action="",
        decision_params={},
        decision_confidence=0.0,
        decision_reasoning="",
        requires_approval=False,
        approval_status=None,
        approval_reason=None,
        command_result=None,
        command_success=False,
        command_error=None,
        execution_state="pending",
        feedback=[],
        patterns_detected=[],
        knowledge_updates=[],
        retry_count=0,
        max_retries=max_retries,
        error_history=[],
        thought_chain=[],
        transitions=[],
        start_time=now,
        end_time=None,
        total_duration_ms=0.0,
        final_success=False,
        final_error=None,
    )


def state_to_summary(state: AgentState) -> dict:
    """
    Convert state to a summary dict for logging/display.

    Args:
        state: Current agent state

    Returns:
        Summary dictionary
    """
    return {
        "task_id": state.get("task_id"),
        "cycle_id": state.get("cycle_id"),
        "current_phase": state.get("current_phase", CCPPhase.SENSE).value,
        "task_type": state.get("task_type"),
        "target": state.get("target"),
        "decision": {
            "action": state.get("decision_action"),
            "confidence": state.get("decision_confidence"),
            "reasoning": state.get("decision_reasoning"),
        },
        "requires_approval": state.get("requires_approval", False),
        "approval_status": state.get("approval_status"),
        "retry_count": state.get("retry_count", 0),
        "thought_steps": len(state.get("thought_chain", [])),
        "transitions": len(state.get("transitions", [])),
        "final_success": state.get("final_success"),
    }
