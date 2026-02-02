"""
OpenIntent SDK - Python client for the OpenIntent Coordination Protocol.

A lightweight SDK for coordinating intent across humans and AI agents.
"""

from .agents import (
    Agent,
    AgentConfig,
    BaseAgent,
    Coordinator,
    IntentSpec,
    PortfolioSpec,
    Worker,
    on_all_complete,
    on_assignment,
    on_complete,
    on_event,
    on_lease_available,
    on_state_change,
)
from .client import AsyncOpenIntentClient, OpenIntentClient
from .exceptions import (
    ConflictError,
    LeaseConflictError,
    NotFoundError,
    OpenIntentError,
    ValidationError,
)
from .models import (
    AggregateStatus,
    ArbitrationRequest,
    CostSummary,
    CostType,
    Decision,
    EventType,
    Intent,
    IntentAttachment,
    IntentCost,
    IntentEvent,
    IntentFailure,
    IntentLease,
    IntentPortfolio,
    IntentState,
    IntentStatus,
    IntentSubscription,
    LeaseStatus,
    LLMRequestPayload,
    MembershipRole,
    PortfolioMembership,
    PortfolioStatus,
    RetryPolicy,
    RetryStrategy,
    StreamState,
    StreamStatus,
    ToolCallPayload,
)
from .streaming import (
    EventQueue,
    SSEEvent,
    SSEEventType,
    SSEStream,
    SSESubscription,
)
from .validation import (
    InputValidationError,
    validate_agent_id,
    validate_cost_record,
    validate_intent_create,
    validate_lease_acquire,
    validate_non_negative,
    validate_positive_int,
    validate_required,
    validate_scope,
    validate_string_length,
    validate_subscription,
    validate_url,
    validate_uuid,
)
from .workflow import (
    GovernanceConfig,
    PhaseConfig,
    WorkflowError,
    WorkflowNotFoundError,
    WorkflowSpec,
    WorkflowValidationError,
    validate_workflow,
)


def get_server():
    """Lazy import for server components (requires server extras)."""
    try:
        from .server import OpenIntentServer, ServerConfig, create_app

        return OpenIntentServer, ServerConfig, create_app
    except ImportError:
        raise ImportError(
            "Server components require the 'server' extras. "
            "Install with: pip install openintent[server]"
        )


__version__ = "0.4.0"
__all__ = [
    "OpenIntentClient",
    "AsyncOpenIntentClient",
    "Intent",
    "IntentState",
    "IntentStatus",
    "IntentEvent",
    "EventType",
    "IntentLease",
    "LeaseStatus",
    "ArbitrationRequest",
    "Decision",
    "IntentPortfolio",
    "PortfolioStatus",
    "PortfolioMembership",
    "MembershipRole",
    "AggregateStatus",
    "IntentAttachment",
    "IntentCost",
    "CostSummary",
    "CostType",
    "RetryPolicy",
    "RetryStrategy",
    "IntentFailure",
    "IntentSubscription",
    "ToolCallPayload",
    "LLMRequestPayload",
    "StreamState",
    "StreamStatus",
    "OpenIntentError",
    "ConflictError",
    "NotFoundError",
    "LeaseConflictError",
    "ValidationError",
    "InputValidationError",
    "validate_required",
    "validate_string_length",
    "validate_positive_int",
    "validate_non_negative",
    "validate_uuid",
    "validate_url",
    "validate_scope",
    "validate_agent_id",
    "validate_intent_create",
    "validate_lease_acquire",
    "validate_cost_record",
    "validate_subscription",
    "SSEEvent",
    "SSEEventType",
    "SSEStream",
    "SSESubscription",
    "EventQueue",
    "Agent",
    "BaseAgent",
    "Coordinator",
    "Worker",
    "AgentConfig",
    "IntentSpec",
    "PortfolioSpec",
    "on_assignment",
    "on_complete",
    "on_lease_available",
    "on_state_change",
    "on_event",
    "on_all_complete",
    "WorkflowSpec",
    "WorkflowError",
    "WorkflowValidationError",
    "WorkflowNotFoundError",
    "PhaseConfig",
    "GovernanceConfig",
    "validate_workflow",
    "get_server",
]
