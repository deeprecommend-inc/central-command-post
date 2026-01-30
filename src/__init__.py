"""
CCP - Central Command Platform

[Sense] -> [Think] -> [Command] -> [Control] -> [Learn]
"""
# Command Layer (existing)
from .web_agent import WebAgent, AgentConfig
from .proxy_manager import ProxyManager, ProxyType
from .ua_manager import UserAgentManager
from .browser_worker import BrowserWorker, WorkerResult, ErrorType
from .parallel_controller import ParallelController, TaskResult
from .browser_use_agent import BrowserUseAgent
from .logging_config import configure_logging
from .rate_limiter import TokenBucketRateLimiter, DomainRateLimiter
from .session_manager import SessionManager, SessionData

# Sense Layer
from .sense import (
    Event, EventBus,
    MetricsCollector, Metric, AggregatedMetric,
    StateSnapshot, SystemState,
)

# Think Layer
from .think import (
    DecisionContext, TaskContext,
    Strategy, Decision, RetryStrategy, ProxySelectionStrategy,
    RulesEngine, Rule,
)

# Control Layer
from .control import (
    TaskState, StateMachine, StateTransition,
    Executor, ExecutionResult, Task,
    FeedbackLoop, Feedback,
)

# Learn Layer
from .learn import (
    KnowledgeStore, KnowledgeEntry,
    PatternDetector, Pattern, Anomaly,
    PerformanceAnalyzer, PerformanceReport,
)

# CCP Orchestrator
from .ccp import (
    CCPOrchestrator,
    SenseLayer, ThinkLayer, ControlLayer, LearnLayer,
    CycleResult,
)

__all__ = [
    # Command Layer
    "WebAgent",
    "AgentConfig",
    "ProxyManager",
    "ProxyType",
    "UserAgentManager",
    "BrowserWorker",
    "WorkerResult",
    "ErrorType",
    "ParallelController",
    "TaskResult",
    "BrowserUseAgent",
    "configure_logging",
    "TokenBucketRateLimiter",
    "DomainRateLimiter",
    "SessionManager",
    "SessionData",
    # Sense Layer
    "Event",
    "EventBus",
    "MetricsCollector",
    "Metric",
    "AggregatedMetric",
    "StateSnapshot",
    "SystemState",
    # Think Layer
    "DecisionContext",
    "TaskContext",
    "Strategy",
    "Decision",
    "RetryStrategy",
    "ProxySelectionStrategy",
    "RulesEngine",
    "Rule",
    # Control Layer
    "TaskState",
    "StateMachine",
    "StateTransition",
    "Executor",
    "ExecutionResult",
    "Task",
    "FeedbackLoop",
    "Feedback",
    # Learn Layer
    "KnowledgeStore",
    "KnowledgeEntry",
    "PatternDetector",
    "Pattern",
    "Anomaly",
    "PerformanceAnalyzer",
    "PerformanceReport",
    # CCP
    "CCPOrchestrator",
    "SenseLayer",
    "ThinkLayer",
    "ControlLayer",
    "LearnLayer",
    "CycleResult",
]
