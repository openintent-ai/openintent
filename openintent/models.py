"""
OpenIntent SDK - Data models based on the OpenIntent Protocol specification.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class IntentStatus(str, Enum):
    """Status of an intent in its lifecycle."""

    DRAFT = "draft"
    ACTIVE = "active"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class EventType(str, Enum):
    """Types of events that can occur on an intent."""

    # Intent lifecycle events
    INTENT_CREATED = "intent_created"
    STATE_PATCHED = "state_patched"
    STATUS_CHANGED = "status_changed"

    # Agent events
    AGENT_ASSIGNED = "agent_assigned"
    AGENT_UNASSIGNED = "agent_unassigned"

    # Constraint events
    CONSTRAINT_ADDED = "constraint_added"
    CONSTRAINT_REMOVED = "constraint_removed"

    # Dependency events (RFC-0002 Intent Graphs)
    DEPENDENCY_ADDED = "dependency_added"
    DEPENDENCY_REMOVED = "dependency_removed"

    # Lease events (RFC-0003)
    LEASE_ACQUIRED = "lease_acquired"
    LEASE_RELEASED = "lease_released"

    # Governance events (RFC-0004)
    ARBITRATION_REQUESTED = "arbitration_requested"
    DECISION_RECORDED = "decision_recorded"

    # Attachment events (RFC-0005)
    ATTACHMENT_ADDED = "attachment_added"

    # Portfolio events (RFC-0007)
    PORTFOLIO_CREATED = "portfolio_created"
    ADDED_TO_PORTFOLIO = "added_to_portfolio"
    REMOVED_FROM_PORTFOLIO = "removed_from_portfolio"

    # Failure events (RFC-0010)
    FAILURE_RECORDED = "failure_recorded"

    # General events
    COMMENT = "comment"

    # LLM observability events
    TOOL_CALL_STARTED = "tool_call_started"
    TOOL_CALL_COMPLETED = "tool_call_completed"
    TOOL_CALL_FAILED = "tool_call_failed"
    LLM_REQUEST_STARTED = "llm_request_started"
    LLM_REQUEST_COMPLETED = "llm_request_completed"
    LLM_REQUEST_FAILED = "llm_request_failed"
    STREAM_STARTED = "stream_started"
    STREAM_CHUNK = "stream_chunk"
    STREAM_COMPLETED = "stream_completed"
    STREAM_CANCELLED = "stream_cancelled"

    # Access control events (RFC-0011)
    ACCESS_GRANTED = "access_granted"
    ACCESS_REVOKED = "access_revoked"
    ACCESS_EXPIRED = "access_expired"
    ACCESS_REQUESTED = "access_requested"
    ACCESS_REQUEST_APPROVED = "access_request_approved"
    ACCESS_REQUEST_DENIED = "access_request_denied"

    # Task events (RFC-0012)
    TASK_CREATED = "task.created"
    TASK_READY = "task.ready"
    TASK_CLAIMED = "task.claimed"
    TASK_STARTED = "task.started"
    TASK_PROGRESS = "task.progress"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    TASK_RETRYING = "task.retrying"
    TASK_BLOCKED = "task.blocked"
    TASK_UNBLOCKED = "task.unblocked"
    TASK_DELEGATED = "task.delegated"
    TASK_ESCALATED = "task.escalated"
    TASK_CANCELLED = "task.cancelled"
    TASK_SKIPPED = "task.skipped"

    # Plan events (RFC-0012)
    PLAN_CREATED = "plan.created"
    PLAN_ACTIVATED = "plan.activated"
    PLAN_PAUSED = "plan.paused"
    PLAN_RESUMED = "plan.resumed"
    PLAN_COMPLETED = "plan.completed"
    PLAN_FAILED = "plan.failed"
    PLAN_CHECKPOINT_REACHED = "plan.checkpoint_reached"
    PLAN_CHECKPOINT_APPROVED = "plan.checkpoint_approved"
    PLAN_CHECKPOINT_REJECTED = "plan.checkpoint_rejected"

    # Coordinator events (RFC-0013)
    COORDINATOR_DECISION = "coordinator.decision"
    COORDINATOR_HEARTBEAT = "coordinator.heartbeat"
    COORDINATOR_PAUSED = "coordinator.paused"
    COORDINATOR_RESUMED = "coordinator.resumed"
    COORDINATOR_REPLACED = "coordinator.replaced"
    COORDINATOR_UNRESPONSIVE = "coordinator.unresponsive"
    COORDINATOR_FAILED_OVER = "coordinator.failed_over"
    COORDINATOR_HANDOFF = "coordinator.handoff"
    COORDINATOR_PLAN_OVERRIDDEN = "coordinator.plan_overridden"
    COORDINATOR_GUARDRAILS_UPDATED = "coordinator.guardrails_updated"
    COORDINATOR_STALLED = "coordinator.stalled"
    COORDINATOR_ESCALATION_RESOLVED = "coordinator.escalation_resolved"

    # Tool and grant events (RFC-0014)
    TOOL_INVOKED = "tool.invoked"
    TOOL_DENIED = "tool.denied"
    GRANT_CREATED = "grant.created"
    GRANT_DELEGATED = "grant.delegated"
    GRANT_REVOKED = "grant.revoked"
    GRANT_EXPIRED = "grant.expired"
    GRANT_SUSPENDED = "grant.suspended"
    GRANT_RESUMED = "grant.resumed"
    CREDENTIAL_CREATED = "credential.created"
    CREDENTIAL_ROTATED = "credential.rotated"
    CREDENTIAL_EXPIRED = "credential.expired"
    CREDENTIAL_REVOKED = "credential.revoked"

    # Memory events (RFC-0015)
    MEMORY_CREATED = "memory.created"
    MEMORY_UPDATED = "memory.updated"
    MEMORY_DELETED = "memory.deleted"
    MEMORY_ARCHIVED = "memory.archived"
    MEMORY_EVICTED = "memory.evicted"
    MEMORY_EXPIRED = "memory.expired"

    # Agent lifecycle events (RFC-0016)
    AGENT_LIFECYCLE = "agent.lifecycle"
    AGENT_REGISTERED = "agent.registered"
    AGENT_STATUS_CHANGED = "agent.status_changed"
    AGENT_DEAD = "agent.dead"

    # Trigger events (RFC-0017)
    TRIGGER_FIRED = "trigger.fired"
    TRIGGER_SKIPPED = "trigger.skipped"
    TRIGGER_CASCADE_LIMIT = "trigger.cascade_limit"
    TRIGGER_NAMESPACE_BLOCKED = "trigger.namespace_blocked"

    # Identity events (RFC-0018)
    IDENTITY_REGISTERED = "agent.identity.registered"
    IDENTITY_ROTATED = "agent.identity.rotated"
    IDENTITY_REVOKED = "agent.identity.revoked"
    IDENTITY_CHALLENGE_ISSUED = "agent.identity.challenge_issued"
    IDENTITY_VERIFIED = "agent.identity.verified"

    # Verifiable log events (RFC-0019)
    LOG_CHECKPOINT_CREATED = "log.checkpoint.created"
    LOG_CHECKPOINT_ANCHORED = "log.checkpoint.anchored"

    # Legacy aliases for backward compatibility
    CREATED = "intent_created"
    STATE_UPDATED = "state_patched"


class StreamStatus(str, Enum):
    """Status of a streaming operation."""

    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class LeaseStatus(str, Enum):
    """Status of a scope lease."""

    ACTIVE = "active"
    RELEASED = "released"
    EXPIRED = "expired"
    REVOKED = "revoked"


class PortfolioStatus(str, Enum):
    """Status of a portfolio."""

    ACTIVE = "active"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class MembershipRole(str, Enum):
    """Role of an intent within a portfolio."""

    PRIMARY = "primary"
    MEMBER = "member"
    DEPENDENCY = "dependency"


class RetryStrategy(str, Enum):
    """Retry strategy for failure handling."""

    NONE = "none"
    FIXED = "fixed"
    EXPONENTIAL = "exponential"
    LINEAR = "linear"


class CostType(str, Enum):
    """Type of cost/resource being tracked."""

    TOKENS = "tokens"
    API_CALL = "api_call"
    COMPUTE = "compute"
    CUSTOM = "custom"


class Permission(str, Enum):
    """Permission level for intent access control (RFC-0011)."""

    READ = "read"
    WRITE = "write"
    ADMIN = "admin"


class AccessPolicy(str, Enum):
    """Default access policy when no ACL entry matches (RFC-0011)."""

    OPEN = "open"
    CLOSED = "closed"


class AccessRequestStatus(str, Enum):
    """Status of an access request (RFC-0011)."""

    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"


# ---------------------------------------------------------------------------
# RFC-0012: Task Decomposition & Planning
# ---------------------------------------------------------------------------


class TaskStatus(str, Enum):
    """Status of a task in its lifecycle (RFC-0012)."""

    PENDING = "pending"
    READY = "ready"
    CLAIMED = "claimed"
    RUNNING = "running"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


class PlanState(str, Enum):
    """State of a plan (RFC-0012)."""

    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CheckpointTimeoutAction(str, Enum):
    """Action when a checkpoint times out (RFC-0012)."""

    ESCALATE = "escalate"
    AUTO_APPROVE = "auto_approve"
    FAIL = "fail"


class PlanFailureAction(str, Enum):
    """Action when a plan encounters a failure (RFC-0012)."""

    PAUSE_AND_ESCALATE = "pause_and_escalate"
    NOTIFY = "notify"
    FAIL = "fail"
    RETRY = "retry"


# ---------------------------------------------------------------------------
# RFC-0013: Coordinator Governance & Meta-Coordination
# ---------------------------------------------------------------------------


class CoordinatorType(str, Enum):
    """Type of coordinator (RFC-0013)."""

    LLM = "llm"
    HUMAN = "human"
    COMPOSITE = "composite"
    SYSTEM = "system"


class CoordinatorStatus(str, Enum):
    """Lifecycle state of a coordinator (RFC-0013)."""

    REGISTERING = "registering"
    ACTIVE = "active"
    PAUSED = "paused"
    UNRESPONSIVE = "unresponsive"
    FAILED_OVER = "failed_over"
    COMPLETING = "completing"
    COMPLETED = "completed"


class CoordinatorScope(str, Enum):
    """Scope of a coordinator lease (RFC-0013)."""

    INTENT = "intent"
    PORTFOLIO = "portfolio"


class CompositeMode(str, Enum):
    """Mode for composite coordinators (RFC-0013)."""

    PROPOSE_APPROVE = "propose-approve"
    ACT_NOTIFY = "act-notify"
    ACT_AUDIT = "act-audit"


class DecisionType(str, Enum):
    """Type of coordinator decision (RFC-0013)."""

    PLAN_CREATED = "plan_created"
    PLAN_MODIFIED = "plan_modified"
    TASK_ASSIGNED = "task_assigned"
    TASK_DELEGATED = "task_delegated"
    ESCALATION_INITIATED = "escalation_initiated"
    ESCALATION_RESOLVED = "escalation_resolved"
    CHECKPOINT_EVALUATED = "checkpoint_evaluated"
    FAILURE_HANDLED = "failure_handled"
    GUARDRAIL_APPROACHED = "guardrail_approached"
    COORDINATOR_HANDOFF = "coordinator_handoff"


class GuardrailExceedAction(str, Enum):
    """Action when a guardrail is exceeded (RFC-0013)."""

    PAUSE = "pause"
    ESCALATE = "escalate"
    PAUSE_AND_ESCALATE = "pause_and_escalate"
    FAIL = "fail"


# ---------------------------------------------------------------------------
# RFC-0014: Credential Vaults & Tool Scoping
# ---------------------------------------------------------------------------


class AuthType(str, Enum):
    """Authentication type for a credential (RFC-0014)."""

    API_KEY = "api_key"
    OAUTH2_TOKEN = "oauth2_token"
    OAUTH2_CLIENT_CREDENTIALS = "oauth2_client_credentials"
    BEARER_TOKEN = "bearer_token"
    BASIC_AUTH = "basic_auth"
    CONNECTION_STRING = "connection_string"
    CUSTOM = "custom"


class CredentialStatus(str, Enum):
    """Status of a credential (RFC-0014)."""

    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"


class GrantStatus(str, Enum):
    """Status of a tool grant (RFC-0014)."""

    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    SUSPENDED = "suspended"


class GrantSource(str, Enum):
    """Source of a tool grant (RFC-0014)."""

    DIRECT = "direct"
    DELEGATED = "delegated"


class InvocationStatus(str, Enum):
    """Status of a tool invocation (RFC-0014)."""

    SUCCESS = "success"
    DENIED = "denied"
    ERROR = "error"


# ---------------------------------------------------------------------------
# RFC-0015: Agent Memory & Persistent State
# ---------------------------------------------------------------------------


class MemoryType(str, Enum):
    """Memory tier for a memory entry (RFC-0015)."""

    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"


class MemoryPriority(str, Enum):
    """Priority level for episodic memory entries (RFC-0015)."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class EvictionPolicy(str, Enum):
    """Eviction policy for episodic memory (RFC-0015)."""

    LRU = "lru"


class MemorySensitivity(str, Enum):
    """Sensitivity classification for memory entries (RFC-0015)."""

    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


# ---------------------------------------------------------------------------
# RFC-0016: Agent Lifecycle & Health
# ---------------------------------------------------------------------------


class AgentStatus(str, Enum):
    """Lifecycle status of an agent (RFC-0016)."""

    REGISTERING = "registering"
    ACTIVE = "active"
    DRAINING = "draining"
    UNHEALTHY = "unhealthy"
    DEAD = "dead"
    DEREGISTERED = "deregistered"


# ---------------------------------------------------------------------------
# RFC-0017: Triggers & Reactive Scheduling
# ---------------------------------------------------------------------------


class TriggerType(str, Enum):
    """Type of trigger (RFC-0017)."""

    SCHEDULE = "schedule"
    EVENT = "event"
    WEBHOOK = "webhook"


class DeduplicationMode(str, Enum):
    """Deduplication behavior when a trigger fires (RFC-0017)."""

    ALLOW = "allow"
    SKIP = "skip"
    QUEUE = "queue"


class TriggerState(str, Enum):
    """Lifecycle state of a trigger (RFC-0017)."""

    ENABLED = "enabled"
    DISABLED = "disabled"
    DELETED = "deleted"


@dataclass
class IntentState:
    """
    Represents the current state of an intent.
    State is a flexible key-value store for tracking progress.
    """

    data: dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value

    def to_dict(self) -> dict[str, Any]:
        return self.data.copy()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IntentState":
        return cls(data=data)


@dataclass
class Intent:
    """
    Core intent object representing a goal to be coordinated.

    RFC-0002 Intent Graphs: Supports hierarchical parent-child relationships
    via parent_intent_id and dependency graphs via depends_on.
    """

    id: str
    title: str
    description: str
    version: int
    status: IntentStatus
    state: IntentState
    constraints: dict[str, Any] = field(default_factory=dict)
    parent_intent_id: Optional[str] = None
    depends_on: list[str] = field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: Optional[str] = None
    confidence: int = 0

    @property
    def has_parent(self) -> bool:
        """Check if this intent has a parent (is a child intent)."""
        return self.parent_intent_id is not None

    @property
    def has_dependencies(self) -> bool:
        """Check if this intent depends on other intents."""
        return len(self.depends_on) > 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "version": self.version,
            "status": self.status.value,
            "state": self.state.to_dict(),
            "constraints": self.constraints,
            "parent_intent_id": self.parent_intent_id,
            "depends_on": self.depends_on,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "created_by": self.created_by,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Intent":
        # Handle constraints as dict (spec) or list (legacy)
        constraints = data.get("constraints", {})
        if isinstance(constraints, list):
            # Preserve legacy list constraints in a "rules" key
            constraints = {"rules": constraints} if constraints else {}
        return cls(
            id=data["id"],
            title=data["title"],
            description=data.get("description", ""),
            version=data.get("version", 1),
            status=IntentStatus(data.get("status", "active")),
            state=IntentState.from_dict(data.get("state", {})),
            constraints=constraints,
            parent_intent_id=data.get("parent_intent_id") or data.get("parentIntentId"),
            depends_on=data.get("depends_on") or data.get("dependsOn") or [],
            created_at=(
                datetime.fromisoformat(data["created_at"])
                if data.get("created_at")
                else None
            ),
            updated_at=(
                datetime.fromisoformat(data["updated_at"])
                if data.get("updated_at")
                else None
            ),
            created_by=data.get("created_by"),
            confidence=data.get("confidence", 0),
        )


@dataclass
class TracingContext:
    """Propagated tracing state for distributed call chain visibility (RFC-0020).

    Carries a correlation identifier and parent event reference through
    agent -> tool -> agent call chains, enabling end-to-end observability.
    """

    trace_id: str
    parent_event_id: Optional[str] = None

    def child(self, new_parent_event_id: str) -> "TracingContext":
        """Create a child context with the same trace_id but a new parent."""
        return TracingContext(
            trace_id=self.trace_id, parent_event_id=new_parent_event_id
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"trace_id": self.trace_id}
        if self.parent_event_id:
            result["parent_event_id"] = self.parent_event_id
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Optional["TracingContext"]:
        """Deserialize a TracingContext from a dict. Returns None if trace_id is missing."""
        trace_id = data.get("trace_id")
        if not trace_id:
            return None
        return cls(
            trace_id=trace_id,
            parent_event_id=data.get("parent_event_id"),
        )

    @classmethod
    def new_root(cls) -> "TracingContext":
        """Generate a fresh tracing context with a new 128-bit trace ID."""
        import uuid

        return cls(trace_id=uuid.uuid4().hex)


@dataclass
class EventProof:
    """Cryptographic proof attached to a signed event (RFC-0018)."""

    type: str = "Ed25519Signature2026"
    created: Optional[str] = None
    verification_method: Optional[str] = None
    signature: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"type": self.type}
        if self.created:
            result["created"] = self.created
        if self.verification_method:
            result["verification_method"] = self.verification_method
        if self.signature:
            result["signature"] = self.signature
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EventProof":
        return cls(
            type=data.get("type", "Ed25519Signature2026"),
            created=data.get("created"),
            verification_method=data.get("verification_method"),
            signature=data.get("signature"),
        )


@dataclass
class IntentEvent:
    """
    Immutable event in the intent's audit log.

    RFC-0018: Optional `proof` field for signed events.
    RFC-0019: Optional `event_hash`, `previous_event_hash`, `sequence` for verifiable logs.
    RFC-0020: Optional `trace_id`, `parent_event_id` for distributed tracing.
    """

    id: str
    intent_id: str
    event_type: EventType
    actor: Optional[str]
    payload: dict[str, Any]
    created_at: datetime
    proof: Optional[EventProof] = None
    event_hash: Optional[str] = None
    previous_event_hash: Optional[str] = None
    sequence: Optional[int] = None
    trace_id: Optional[str] = None
    parent_event_id: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "id": self.id,
            "intent_id": self.intent_id,
            "event_type": self.event_type.value,
            "payload": self.payload,
            "created_at": self.created_at.isoformat(),
        }
        if self.actor:
            result["actor"] = self.actor
        if self.proof:
            result["proof"] = self.proof.to_dict()
        if self.event_hash:
            result["event_hash"] = self.event_hash
        if self.previous_event_hash:
            result["previous_event_hash"] = self.previous_event_hash
        if self.sequence is not None:
            result["sequence"] = self.sequence
        if self.trace_id:
            result["trace_id"] = self.trace_id
        if self.parent_event_id:
            result["parent_event_id"] = self.parent_event_id
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IntentEvent":
        proof = None
        if data.get("proof"):
            proof = EventProof.from_dict(data["proof"])
        return cls(
            id=data.get("id", ""),
            intent_id=data.get("intent_id", ""),
            event_type=EventType(data.get("event_type", "state_patched")),
            actor=data.get("actor"),
            payload=data.get("payload", {}),
            created_at=(
                datetime.fromisoformat(data["created_at"])
                if "created_at" in data
                else datetime.now()
            ),
            proof=proof,
            event_hash=data.get("event_hash"),
            previous_event_hash=data.get("previous_event_hash"),
            sequence=data.get("sequence"),
            trace_id=data.get("trace_id"),
            parent_event_id=data.get("parent_event_id"),
        )


@dataclass
class IntentLease:
    """
    Lease granting exclusive access to a scope within an intent.
    """

    id: str
    intent_id: str
    agent_id: str
    scope: str
    status: LeaseStatus
    expires_at: datetime
    created_at: datetime

    @property
    def is_active(self) -> bool:
        return self.status == LeaseStatus.ACTIVE and datetime.now() < self.expires_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "intent_id": self.intent_id,
            "agent_id": self.agent_id,
            "scope": self.scope,
            "status": self.status.value,
            "expires_at": self.expires_at.isoformat(),
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IntentLease":
        return cls(
            id=data["id"],
            intent_id=data["intent_id"],
            agent_id=data["agent_id"],
            scope=data["scope"],
            status=LeaseStatus(data["status"]),
            expires_at=datetime.fromisoformat(data["expires_at"]),
            created_at=datetime.fromisoformat(data["created_at"]),
        )


@dataclass
class ArbitrationRequest:
    """
    Request for human arbitration on a conflict or decision.
    """

    id: str
    intent_id: str
    requester_id: str
    reason: str
    context: dict[str, Any]
    status: str
    created_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "intent_id": self.intent_id,
            "requester_id": self.requester_id,
            "reason": self.reason,
            "context": self.context,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ArbitrationRequest":
        return cls(
            id=data["id"],
            intent_id=data["intent_id"],
            requester_id=data["requester_id"],
            reason=data["reason"],
            context=data.get("context", {}),
            status=data["status"],
            created_at=datetime.fromisoformat(data["created_at"]),
        )


@dataclass
class Decision:
    """
    Governance decision recorded for an intent.
    """

    id: str
    intent_id: str
    decision_maker_id: str
    decision_type: str
    outcome: str
    reasoning: str
    created_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "intent_id": self.intent_id,
            "decision_maker_id": self.decision_maker_id,
            "decision_type": self.decision_type,
            "outcome": self.outcome,
            "reasoning": self.reasoning,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Decision":
        return cls(
            id=data["id"],
            intent_id=data["intent_id"],
            decision_maker_id=data["decision_maker_id"],
            decision_type=data["decision_type"],
            outcome=data["outcome"],
            reasoning=data["reasoning"],
            created_at=datetime.fromisoformat(data["created_at"]),
        )


@dataclass
class AggregateStatus:
    """
    Computed aggregate status for a portfolio.
    """

    total: int
    by_status: dict[str, int]
    completion_percentage: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "by_status": self.by_status,
            "completion_percentage": self.completion_percentage,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AggregateStatus":
        return cls(
            total=data.get("total", 0),
            by_status=data.get("by_status", data.get("byStatus", {})),
            completion_percentage=data.get(
                "completion_percentage", data.get("completionPercentage", 0)
            ),
        )


@dataclass
class PortfolioMembership:
    """
    Membership of an intent within a portfolio.
    """

    id: str
    portfolio_id: str
    intent_id: str
    role: MembershipRole
    priority: int
    added_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "portfolio_id": self.portfolio_id,
            "intent_id": self.intent_id,
            "role": self.role.value,
            "priority": self.priority,
            "added_at": self.added_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PortfolioMembership":
        return cls(
            id=data["id"],
            portfolio_id=data.get("portfolio_id", data.get("portfolioId", "")),
            intent_id=data.get("intent_id", data.get("intentId", "")),
            role=MembershipRole(data.get("role", "member")),
            priority=data.get("priority", 0),
            added_at=datetime.fromisoformat(
                data.get("added_at", data.get("addedAt", datetime.now().isoformat()))
            ),
        )


@dataclass
class IntentPortfolio:
    """
    Collection of related intents with aggregate tracking and shared governance.
    """

    id: str
    name: str
    description: Optional[str]
    created_by: str
    status: PortfolioStatus
    metadata: dict[str, Any]
    governance_policy: dict[str, Any]
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    intents: list[Intent] = field(default_factory=list)
    aggregate_status: Optional[AggregateStatus] = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "created_by": self.created_by,
            "status": self.status.value,
            "metadata": self.metadata,
            "governance_policy": self.governance_policy,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if self.intents:
            result["intents"] = [i.to_dict() for i in self.intents]
        if self.aggregate_status:
            result["aggregate_status"] = self.aggregate_status.to_dict()
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IntentPortfolio":
        intents = []
        if "intents" in data:
            intents = [Intent.from_dict(i) for i in data["intents"]]

        aggregate = None
        agg_data = data.get("aggregate_status") or data.get("aggregateStatus")
        if agg_data:
            aggregate = AggregateStatus.from_dict(agg_data)

        return cls(
            id=data["id"],
            name=data["name"],
            description=data.get("description"),
            created_by=data.get("created_by", data.get("createdBy", "")),
            status=PortfolioStatus(data.get("status", "active")),
            metadata=data.get("metadata", {}),
            governance_policy=data.get(
                "governance_policy", data.get("governancePolicy", {})
            ),
            created_at=(
                datetime.fromisoformat(data["createdAt"])
                if data.get("createdAt")
                else None
            ),
            updated_at=(
                datetime.fromisoformat(data["updatedAt"])
                if data.get("updatedAt")
                else None
            ),
            intents=intents,
            aggregate_status=aggregate,
        )


@dataclass
class IntentAttachment:
    """
    File attachment on an intent for multi-modal content.
    """

    id: str
    intent_id: str
    filename: str
    mime_type: str
    size: int
    storage_url: str
    metadata: dict[str, Any]
    uploaded_by: str
    created_at: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "intent_id": self.intent_id,
            "filename": self.filename,
            "mime_type": self.mime_type,
            "size": self.size,
            "storage_url": self.storage_url,
            "metadata": self.metadata,
            "uploaded_by": self.uploaded_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IntentAttachment":
        return cls(
            id=data["id"],
            intent_id=data.get("intent_id", data.get("intentId", "")),
            filename=data["filename"],
            mime_type=data.get("mime_type", data.get("mimeType", "")),
            size=data["size"],
            storage_url=data.get("storage_url", data.get("storageUrl", "")),
            metadata=data.get("metadata", {}),
            uploaded_by=data.get("uploaded_by", data.get("uploadedBy", "")),
            created_at=(
                datetime.fromisoformat(data["createdAt"])
                if data.get("createdAt")
                else None
            ),
        )


@dataclass
class IntentCost:
    """
    Cost record tracking resource usage for an intent.
    """

    id: str
    intent_id: str
    agent_id: str
    cost_type: str
    amount: int
    unit: str
    provider: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    recorded_at: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "intent_id": self.intent_id,
            "agent_id": self.agent_id,
            "cost_type": self.cost_type,
            "amount": self.amount,
            "unit": self.unit,
            "provider": self.provider,
            "metadata": self.metadata,
            "recorded_at": self.recorded_at.isoformat() if self.recorded_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IntentCost":
        return cls(
            id=data["id"],
            intent_id=data.get("intent_id", data.get("intentId", "")),
            agent_id=data.get("agent_id", data.get("agentId", "")),
            cost_type=data.get("cost_type", data.get("costType", "")),
            amount=data["amount"],
            unit=data["unit"],
            provider=data.get("provider"),
            metadata=data.get("metadata", {}),
            recorded_at=(
                datetime.fromisoformat(data["recordedAt"])
                if data.get("recordedAt")
                else None
            ),
        )


@dataclass
class CostSummary:
    """
    Aggregate cost summary for an intent.
    """

    total: int
    by_type: dict[str, int]
    by_agent: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "by_type": self.by_type,
            "by_agent": self.by_agent,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CostSummary":
        return cls(
            total=data.get("total", 0),
            by_type=data.get("by_type", data.get("byType", {})),
            by_agent=data.get("by_agent", data.get("byAgent", {})),
        )


@dataclass
class RetryPolicy:
    """
    Retry policy configuration for an intent.
    """

    id: str
    intent_id: str
    strategy: RetryStrategy
    max_retries: int
    base_delay_ms: int
    max_delay_ms: int
    fallback_agent_id: Optional[str] = None
    failure_threshold: int = 3
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "intent_id": self.intent_id,
            "strategy": self.strategy.value,
            "max_retries": self.max_retries,
            "base_delay_ms": self.base_delay_ms,
            "max_delay_ms": self.max_delay_ms,
            "fallback_agent_id": self.fallback_agent_id,
            "failure_threshold": self.failure_threshold,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RetryPolicy":
        return cls(
            id=data["id"],
            intent_id=data.get("intent_id", data.get("intentId", "")),
            strategy=RetryStrategy(data.get("strategy", "exponential")),
            max_retries=data.get("max_retries", data.get("maxRetries", 3)),
            base_delay_ms=data.get("base_delay_ms", data.get("baseDelayMs", 1000)),
            max_delay_ms=data.get("max_delay_ms", data.get("maxDelayMs", 60000)),
            fallback_agent_id=data.get(
                "fallback_agent_id", data.get("fallbackAgentId")
            ),
            failure_threshold=data.get(
                "failure_threshold", data.get("failureThreshold", 3)
            ),
            created_at=(
                datetime.fromisoformat(data["createdAt"])
                if data.get("createdAt")
                else None
            ),
            updated_at=(
                datetime.fromisoformat(data["updatedAt"])
                if data.get("updatedAt")
                else None
            ),
        )


@dataclass
class IntentFailure:
    """
    Record of a failure that occurred while processing an intent.
    """

    id: str
    intent_id: str
    agent_id: str
    attempt_number: int
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    retry_scheduled_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "intent_id": self.intent_id,
            "agent_id": self.agent_id,
            "attempt_number": self.attempt_number,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "retry_scheduled_at": (
                self.retry_scheduled_at.isoformat() if self.retry_scheduled_at else None
            ),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IntentFailure":
        return cls(
            id=data["id"],
            intent_id=data.get("intent_id", data.get("intentId", "")),
            agent_id=data.get("agent_id", data.get("agentId", "")),
            attempt_number=data.get("attempt_number", data.get("attemptNumber", 0)),
            error_code=data.get("error_code", data.get("errorCode")),
            error_message=data.get("error_message", data.get("errorMessage")),
            retry_scheduled_at=(
                datetime.fromisoformat(data["retryScheduledAt"])
                if data.get("retryScheduledAt")
                else None
            ),
            resolved_at=(
                datetime.fromisoformat(data["resolvedAt"])
                if data.get("resolvedAt")
                else None
            ),
            metadata=data.get("metadata", {}),
            created_at=(
                datetime.fromisoformat(data["createdAt"])
                if data.get("createdAt")
                else None
            ),
        )


@dataclass
class IntentSubscription:
    """
    Subscription for real-time notifications on intent or portfolio changes.
    """

    id: str
    subscriber_id: str
    intent_id: Optional[str] = None
    portfolio_id: Optional[str] = None
    event_types: list[str] = field(default_factory=list)
    webhook_url: Optional[str] = None
    active: bool = True
    expires_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "intent_id": self.intent_id,
            "portfolio_id": self.portfolio_id,
            "subscriber_id": self.subscriber_id,
            "event_types": self.event_types,
            "webhook_url": self.webhook_url,
            "active": self.active,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IntentSubscription":
        return cls(
            id=data["id"],
            intent_id=data.get("intent_id", data.get("intentId")),
            portfolio_id=data.get("portfolio_id", data.get("portfolioId")),
            subscriber_id=data.get("subscriber_id", data.get("subscriberId", "")),
            event_types=data.get("event_types", data.get("eventTypes", [])),
            webhook_url=data.get("webhook_url", data.get("webhookUrl")),
            active=bool(data.get("active", 1)),
            expires_at=(
                datetime.fromisoformat(data["expiresAt"])
                if data.get("expiresAt")
                else None
            ),
            created_at=(
                datetime.fromisoformat(data["createdAt"])
                if data.get("createdAt")
                else None
            ),
        )


@dataclass
class ToolCallPayload:
    """
    Structured payload for tool call events.
    Captures LLM-initiated tool/function calls with full context.
    """

    tool_name: str
    tool_id: str
    arguments: dict[str, Any]
    provider: Optional[str] = None
    model: Optional[str] = None
    parent_request_id: Optional[str] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    duration_ms: Optional[int] = None
    token_count: Optional[int] = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "tool_name": self.tool_name,
            "tool_id": self.tool_id,
            "arguments": self.arguments,
        }
        if self.provider:
            result["provider"] = self.provider
        if self.model:
            result["model"] = self.model
        if self.parent_request_id:
            result["parent_request_id"] = self.parent_request_id
        if self.result is not None:
            result["result"] = self.result
        if self.error:
            result["error"] = self.error
        if self.duration_ms is not None:
            result["duration_ms"] = self.duration_ms
        if self.token_count is not None:
            result["token_count"] = self.token_count
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ToolCallPayload":
        return cls(
            tool_name=data["tool_name"],
            tool_id=data["tool_id"],
            arguments=data.get("arguments", {}),
            provider=data.get("provider"),
            model=data.get("model"),
            parent_request_id=data.get("parent_request_id"),
            result=data.get("result"),
            error=data.get("error"),
            duration_ms=data.get("duration_ms"),
            token_count=data.get("token_count"),
        )


@dataclass
class LLMRequestPayload:
    """
    Structured payload for LLM request events.
    Captures the full context of an LLM API call.
    """

    request_id: str
    provider: str
    model: str
    messages_count: int
    tools_available: list[str] = field(default_factory=list)
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    stream: bool = False
    response_content: Optional[str] = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    finish_reason: Optional[str] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    duration_ms: Optional[int] = None
    error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "request_id": self.request_id,
            "provider": self.provider,
            "model": self.model,
            "messages_count": self.messages_count,
            "stream": self.stream,
        }
        if self.tools_available:
            result["tools_available"] = self.tools_available
        if self.temperature is not None:
            result["temperature"] = self.temperature
        if self.max_tokens is not None:
            result["max_tokens"] = self.max_tokens
        if self.response_content:
            result["response_content"] = self.response_content
        if self.tool_calls:
            result["tool_calls"] = self.tool_calls
        if self.finish_reason:
            result["finish_reason"] = self.finish_reason
        if self.prompt_tokens is not None:
            result["prompt_tokens"] = self.prompt_tokens
        if self.completion_tokens is not None:
            result["completion_tokens"] = self.completion_tokens
        if self.total_tokens is not None:
            result["total_tokens"] = self.total_tokens
        if self.duration_ms is not None:
            result["duration_ms"] = self.duration_ms
        if self.error:
            result["error"] = self.error
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LLMRequestPayload":
        return cls(
            request_id=data["request_id"],
            provider=data["provider"],
            model=data["model"],
            messages_count=data.get("messages_count", 0),
            tools_available=data.get("tools_available", []),
            temperature=data.get("temperature"),
            max_tokens=data.get("max_tokens"),
            stream=data.get("stream", False),
            response_content=data.get("response_content"),
            tool_calls=data.get("tool_calls", []),
            finish_reason=data.get("finish_reason"),
            prompt_tokens=data.get("prompt_tokens"),
            completion_tokens=data.get("completion_tokens"),
            total_tokens=data.get("total_tokens"),
            duration_ms=data.get("duration_ms"),
            error=data.get("error"),
        )


@dataclass
class StreamState:
    """
    Tracks the state of a streaming operation.
    Used for real-time coordination and cancellation.
    """

    stream_id: str
    intent_id: str
    agent_id: str
    status: StreamStatus
    provider: str
    model: str
    chunks_received: int = 0
    tokens_streamed: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    cancel_reason: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "stream_id": self.stream_id,
            "intent_id": self.intent_id,
            "agent_id": self.agent_id,
            "status": self.status.value,
            "provider": self.provider,
            "model": self.model,
            "chunks_received": self.chunks_received,
            "tokens_streamed": self.tokens_streamed,
        }
        if self.started_at:
            result["started_at"] = self.started_at.isoformat()
        if self.completed_at:
            result["completed_at"] = self.completed_at.isoformat()
        if self.cancelled_at:
            result["cancelled_at"] = self.cancelled_at.isoformat()
        if self.cancel_reason:
            result["cancel_reason"] = self.cancel_reason
        if self.error:
            result["error"] = self.error
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StreamState":
        return cls(
            stream_id=data["stream_id"],
            intent_id=data["intent_id"],
            agent_id=data["agent_id"],
            status=StreamStatus(data["status"]),
            provider=data["provider"],
            model=data["model"],
            chunks_received=data.get("chunks_received", 0),
            tokens_streamed=data.get("tokens_streamed", 0),
            started_at=(
                datetime.fromisoformat(data["started_at"])
                if data.get("started_at")
                else None
            ),
            completed_at=(
                datetime.fromisoformat(data["completed_at"])
                if data.get("completed_at")
                else None
            ),
            cancelled_at=(
                datetime.fromisoformat(data["cancelled_at"])
                if data.get("cancelled_at")
                else None
            ),
            cancel_reason=data.get("cancel_reason"),
            error=data.get("error"),
        )


@dataclass
class ACLEntry:
    """Single entry in an intent's access control list (RFC-0011)."""

    id: str
    principal_id: str
    principal_type: str
    permission: Permission
    granted_by: str
    granted_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    reason: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "principal_id": self.principal_id,
            "principal_type": self.principal_type,
            "permission": self.permission.value,
            "granted_by": self.granted_by,
            "granted_at": self.granted_at.isoformat() if self.granted_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ACLEntry":
        return cls(
            id=data.get("id", ""),
            principal_id=data["principal_id"],
            principal_type=data.get("principal_type", "agent"),
            permission=Permission(data.get("permission", "read")),
            granted_by=data.get("granted_by", ""),
            granted_at=(
                datetime.fromisoformat(data["granted_at"])
                if data.get("granted_at")
                else None
            ),
            expires_at=(
                datetime.fromisoformat(data["expires_at"])
                if data.get("expires_at")
                else None
            ),
            reason=data.get("reason"),
        )


@dataclass
class IntentACL:
    """Access control list for an intent (RFC-0011)."""

    intent_id: str
    default_policy: AccessPolicy
    entries: list[ACLEntry] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent_id": self.intent_id,
            "default_policy": self.default_policy.value,
            "entries": [e.to_dict() for e in self.entries],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IntentACL":
        return cls(
            intent_id=data.get("intent_id", ""),
            default_policy=AccessPolicy(data.get("default_policy", "open")),
            entries=[ACLEntry.from_dict(e) for e in data.get("entries", [])],
        )


@dataclass
class AccessRequest:
    """Request for access to an intent (RFC-0011)."""

    id: str
    intent_id: str
    principal_id: str
    principal_type: str
    requested_permission: Permission
    reason: str
    status: AccessRequestStatus = AccessRequestStatus.PENDING
    capabilities: list[str] = field(default_factory=list)
    decided_by: Optional[str] = None
    decided_at: Optional[datetime] = None
    decision_reason: Optional[str] = None
    created_at: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "intent_id": self.intent_id,
            "principal_id": self.principal_id,
            "principal_type": self.principal_type,
            "requested_permission": self.requested_permission.value,
            "reason": self.reason,
            "status": self.status.value,
            "capabilities": self.capabilities,
            "decided_by": self.decided_by,
            "decided_at": self.decided_at.isoformat() if self.decided_at else None,
            "decision_reason": self.decision_reason,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AccessRequest":
        return cls(
            id=data.get("id", ""),
            intent_id=data.get("intent_id", ""),
            principal_id=data["principal_id"],
            principal_type=data.get("principal_type", "agent"),
            requested_permission=Permission(data.get("requested_permission", "read")),
            reason=data.get("reason", ""),
            status=AccessRequestStatus(data.get("status", "pending")),
            capabilities=data.get("capabilities", []),
            decided_by=data.get("decided_by"),
            decided_at=(
                datetime.fromisoformat(data["decided_at"])
                if data.get("decided_at")
                else None
            ),
            decision_reason=data.get("decision_reason"),
            created_at=(
                datetime.fromisoformat(data["created_at"])
                if data.get("created_at")
                else None
            ),
        )


@dataclass
class PeerInfo:
    """Information about a peer agent working on the same intent (RFC-0011)."""

    principal_id: str
    principal_type: str
    permission: Optional[Permission] = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "principal_id": self.principal_id,
            "principal_type": self.principal_type,
        }
        if self.permission is not None:
            result["permission"] = self.permission.value
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PeerInfo":
        return cls(
            principal_id=data["principal_id"],
            principal_type=data.get("principal_type", "agent"),
            permission=(
                Permission(data["permission"]) if data.get("permission") else None
            ),
        )


@dataclass
class IntentContext:
    """
    Auto-populated context for an intent, available as intent.ctx (RFC-0011).

    What you see depends on your permission level. The SDK automatically
    filters context based on the agent's access.
    """

    parent: Optional[Intent] = None
    dependencies: dict[str, dict[str, Any]] = field(default_factory=dict)
    events: list[IntentEvent] = field(default_factory=list)
    acl: Optional[IntentACL] = None
    my_permission: Optional[Permission] = None
    attachments: list[IntentAttachment] = field(default_factory=list)
    peers: list[PeerInfo] = field(default_factory=list)
    delegated_by: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "dependencies": self.dependencies,
            "events": [e.to_dict() for e in self.events],
            "peers": [p.to_dict() for p in self.peers],
            "attachments": [a.to_dict() for a in self.attachments],
        }
        if self.parent:
            result["parent"] = self.parent.to_dict()
        if self.acl:
            result["acl"] = self.acl.to_dict()
        if self.my_permission:
            result["my_permission"] = self.my_permission.value
        if self.delegated_by:
            result["delegated_by"] = self.delegated_by
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IntentContext":
        parent = Intent.from_dict(data["parent"]) if data.get("parent") else None
        acl = IntentACL.from_dict(data["acl"]) if data.get("acl") else None
        events = [IntentEvent.from_dict(e) for e in data.get("events", [])]
        attachments = [
            IntentAttachment.from_dict(a) for a in data.get("attachments", [])
        ]
        peers = [PeerInfo.from_dict(p) for p in data.get("peers", [])]
        perm = Permission(data["my_permission"]) if data.get("my_permission") else None
        return cls(
            parent=parent,
            dependencies=data.get("dependencies", {}),
            events=events,
            acl=acl,
            my_permission=perm,
            attachments=attachments,
            peers=peers,
            delegated_by=data.get("delegated_by"),
        )


# ===========================================================================
# RFC-0012: Task Decomposition & Planning — Dataclasses
# ===========================================================================


@dataclass
class Checkpoint:
    """A named gate in a plan where execution pauses for review (RFC-0012)."""

    id: str
    name: str
    after_task: str
    requires_approval: bool = True
    approvers: list[str] = field(default_factory=list)
    timeout_hours: Optional[int] = None
    on_timeout: CheckpointTimeoutAction = CheckpointTimeoutAction.ESCALATE
    status: str = "pending"
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "after_task": self.after_task,
            "requires_approval": self.requires_approval,
            "approvers": self.approvers,
            "on_timeout": self.on_timeout.value,
            "status": self.status,
        }
        if self.timeout_hours is not None:
            result["timeout_hours"] = self.timeout_hours
        if self.approved_by:
            result["approved_by"] = self.approved_by
        if self.approved_at:
            result["approved_at"] = self.approved_at.isoformat()
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Checkpoint":
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            after_task=data.get("after_task", data.get("after", "")),
            requires_approval=data.get("requires_approval", True),
            approvers=data.get("approvers", []),
            timeout_hours=data.get("timeout_hours"),
            on_timeout=CheckpointTimeoutAction(data.get("on_timeout", "escalate")),
            status=data.get("status", "pending"),
            approved_by=data.get("approved_by"),
            approved_at=(
                datetime.fromisoformat(data["approved_at"])
                if data.get("approved_at")
                else None
            ),
        )


@dataclass
class PlanCondition:
    """Conditional branching logic within a plan (RFC-0012)."""

    id: str
    task_id: str
    when: str
    otherwise: str = "skip"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "task_id": self.task_id,
            "when": self.when,
            "otherwise": self.otherwise,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PlanCondition":
        return cls(
            id=data.get("id", ""),
            task_id=data.get("task_id", ""),
            when=data.get("when", ""),
            otherwise=data.get("otherwise", "skip"),
        )


@dataclass
class MemoryPolicy:
    """Working memory policy for a task (RFC-0015 integration with RFC-0012)."""

    archive_on_completion: bool = True
    inherit_from_parent: bool = False
    max_entries: Optional[int] = None
    max_total_size_kb: Optional[int] = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "archive_on_completion": self.archive_on_completion,
            "inherit_from_parent": self.inherit_from_parent,
        }
        if self.max_entries is not None:
            result["max_entries"] = self.max_entries
        if self.max_total_size_kb is not None:
            result["max_total_size_kb"] = self.max_total_size_kb
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemoryPolicy":
        return cls(
            archive_on_completion=data.get("archive_on_completion", True),
            inherit_from_parent=data.get("inherit_from_parent", False),
            max_entries=data.get("max_entries"),
            max_total_size_kb=data.get("max_total_size_kb"),
        )


@dataclass
class ToolRequirement:
    """External service access required by a task (RFC-0014 integration with RFC-0012)."""

    service: str
    scopes: list[str] = field(default_factory=list)
    required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "service": self.service,
            "scopes": self.scopes,
            "required": self.required,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ToolRequirement":
        return cls(
            service=data["service"],
            scopes=data.get("scopes", []),
            required=data.get("required", True),
        )


@dataclass
class Task:
    """A concrete, bounded unit of work derived from an intent (RFC-0012)."""

    id: str
    intent_id: str
    name: str
    version: int = 1
    status: TaskStatus = TaskStatus.PENDING
    plan_id: Optional[str] = None
    description: Optional[str] = None
    priority: str = "normal"
    input: dict[str, Any] = field(default_factory=dict)
    output: Optional[dict[str, Any]] = None
    artifacts: list[str] = field(default_factory=list)
    assigned_agent: Optional[str] = None
    lease_id: Optional[str] = None
    capabilities_required: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    blocks: list[str] = field(default_factory=list)
    parent_task_id: Optional[str] = None
    retry_policy: Optional[str] = None
    timeout_seconds: Optional[int] = None
    attempt: int = 1
    max_attempts: int = 3
    permissions: str = "inherit"
    memory_policy: Optional[MemoryPolicy] = None
    requires_tools: list[ToolRequirement] = field(default_factory=list)
    blocked_reason: Optional[str] = None
    error: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "id": self.id,
            "intent_id": self.intent_id,
            "name": self.name,
            "version": self.version,
            "status": self.status.value,
            "priority": self.priority,
            "input": self.input,
            "artifacts": self.artifacts,
            "capabilities_required": self.capabilities_required,
            "depends_on": self.depends_on,
            "blocks": self.blocks,
            "attempt": self.attempt,
            "max_attempts": self.max_attempts,
            "permissions": self.permissions,
            "metadata": self.metadata,
        }
        if self.plan_id:
            result["plan_id"] = self.plan_id
        if self.description:
            result["description"] = self.description
        if self.output is not None:
            result["output"] = self.output
        if self.assigned_agent:
            result["assigned_agent"] = self.assigned_agent
        if self.lease_id:
            result["lease_id"] = self.lease_id
        if self.parent_task_id:
            result["parent_task_id"] = self.parent_task_id
        if self.retry_policy:
            result["retry_policy"] = self.retry_policy
        if self.timeout_seconds is not None:
            result["timeout_seconds"] = self.timeout_seconds
        if self.memory_policy:
            result["memory_policy"] = self.memory_policy.to_dict()
        if self.requires_tools:
            result["requires_tools"] = [t.to_dict() for t in self.requires_tools]
        if self.blocked_reason:
            result["blocked_reason"] = self.blocked_reason
        if self.error:
            result["error"] = self.error
        if self.created_at:
            result["created_at"] = self.created_at.isoformat()
        if self.started_at:
            result["started_at"] = self.started_at.isoformat()
        if self.completed_at:
            result["completed_at"] = self.completed_at.isoformat()
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Task":
        memory_policy = None
        if data.get("memory_policy"):
            memory_policy = MemoryPolicy.from_dict(data["memory_policy"])
        requires_tools = [
            ToolRequirement.from_dict(t) for t in data.get("requires_tools", [])
        ]
        return cls(
            id=data["id"],
            intent_id=data.get("intent_id", ""),
            name=data.get("name", ""),
            version=data.get("version", 1),
            status=TaskStatus(data.get("status", "pending")),
            plan_id=data.get("plan_id"),
            description=data.get("description"),
            priority=data.get("priority", "normal"),
            input=data.get("input", {}),
            output=data.get("output"),
            artifacts=data.get("artifacts", []),
            assigned_agent=data.get("assigned_agent"),
            lease_id=data.get("lease_id"),
            capabilities_required=data.get("capabilities_required", []),
            depends_on=data.get("depends_on", []),
            blocks=data.get("blocks", []),
            parent_task_id=data.get("parent_task_id"),
            retry_policy=data.get("retry_policy"),
            timeout_seconds=data.get("timeout_seconds"),
            attempt=data.get("attempt", 1),
            max_attempts=data.get("max_attempts", 3),
            permissions=data.get("permissions", "inherit"),
            memory_policy=memory_policy,
            requires_tools=requires_tools,
            blocked_reason=data.get("blocked_reason"),
            error=data.get("error"),
            metadata=data.get("metadata", {}),
            created_at=(
                datetime.fromisoformat(data["created_at"])
                if data.get("created_at")
                else None
            ),
            started_at=(
                datetime.fromisoformat(data["started_at"])
                if data.get("started_at")
                else None
            ),
            completed_at=(
                datetime.fromisoformat(data["completed_at"])
                if data.get("completed_at")
                else None
            ),
        )


@dataclass
class Plan:
    """Execution strategy for achieving an intent (RFC-0012)."""

    id: str
    intent_id: str
    version: int = 1
    state: PlanState = PlanState.DRAFT
    tasks: list[str] = field(default_factory=list)
    checkpoints: list[Checkpoint] = field(default_factory=list)
    conditions: list[PlanCondition] = field(default_factory=list)
    on_failure: PlanFailureAction = PlanFailureAction.PAUSE_AND_ESCALATE
    on_complete: str = "notify"
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "id": self.id,
            "intent_id": self.intent_id,
            "version": self.version,
            "state": self.state.value,
            "tasks": self.tasks,
            "checkpoints": [c.to_dict() for c in self.checkpoints],
            "conditions": [c.to_dict() for c in self.conditions],
            "on_failure": self.on_failure.value,
            "on_complete": self.on_complete,
            "metadata": self.metadata,
        }
        if self.created_at:
            result["created_at"] = self.created_at.isoformat()
        if self.updated_at:
            result["updated_at"] = self.updated_at.isoformat()
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Plan":
        return cls(
            id=data["id"],
            intent_id=data.get("intent_id", ""),
            version=data.get("version", 1),
            state=PlanState(data.get("state", "draft")),
            tasks=data.get("tasks", []),
            checkpoints=[Checkpoint.from_dict(c) for c in data.get("checkpoints", [])],
            conditions=[PlanCondition.from_dict(c) for c in data.get("conditions", [])],
            on_failure=PlanFailureAction(data.get("on_failure", "pause_and_escalate")),
            on_complete=data.get("on_complete", "notify"),
            metadata=data.get("metadata", {}),
            created_at=(
                datetime.fromisoformat(data["created_at"])
                if data.get("created_at")
                else None
            ),
            updated_at=(
                datetime.fromisoformat(data["updated_at"])
                if data.get("updated_at")
                else None
            ),
        )


# ===========================================================================
# RFC-0013: Coordinator Governance & Meta-Coordination — Dataclasses
# ===========================================================================


@dataclass
class Guardrails:
    """Declarative constraints bounding coordinator behavior (RFC-0013)."""

    max_budget_usd: Optional[float] = None
    warn_at_percentage: int = 80
    on_exceed: GuardrailExceedAction = GuardrailExceedAction.PAUSE_AND_ESCALATE
    max_tasks_per_plan: int = 20
    max_delegation_depth: int = 3
    max_concurrent_tasks: int = 10
    max_plan_versions: int = 5
    allowed_capabilities: Optional[list[str]] = None
    max_plan_duration_hours: Optional[int] = None
    max_task_wait_hours: Optional[int] = None
    checkpoint_timeout_hours: int = 24
    require_progress_every_minutes: Optional[int] = None
    requires_plan_review: bool = False
    requires_replan_review: bool = False
    auto_escalate_after_failures: int = 3
    require_human_for_capabilities: list[str] = field(default_factory=list)
    max_working_memory_per_task: Optional[int] = None
    max_episodic_memory_per_agent: Optional[int] = None
    allowed_semantic_namespaces: Optional[list[str]] = None
    denied_semantic_namespaces: Optional[list[str]] = None
    memory_archive_required: bool = True

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "warn_at_percentage": self.warn_at_percentage,
            "on_exceed": self.on_exceed.value,
            "max_tasks_per_plan": self.max_tasks_per_plan,
            "max_delegation_depth": self.max_delegation_depth,
            "max_concurrent_tasks": self.max_concurrent_tasks,
            "max_plan_versions": self.max_plan_versions,
            "checkpoint_timeout_hours": self.checkpoint_timeout_hours,
            "requires_plan_review": self.requires_plan_review,
            "requires_replan_review": self.requires_replan_review,
            "auto_escalate_after_failures": self.auto_escalate_after_failures,
            "require_human_for_capabilities": self.require_human_for_capabilities,
            "memory_archive_required": self.memory_archive_required,
        }
        if self.max_budget_usd is not None:
            result["max_budget_usd"] = self.max_budget_usd
        if self.allowed_capabilities is not None:
            result["allowed_capabilities"] = self.allowed_capabilities
        if self.max_plan_duration_hours is not None:
            result["max_plan_duration_hours"] = self.max_plan_duration_hours
        if self.max_task_wait_hours is not None:
            result["max_task_wait_hours"] = self.max_task_wait_hours
        if self.require_progress_every_minutes is not None:
            result["require_progress_every_minutes"] = (
                self.require_progress_every_minutes
            )
        if self.max_working_memory_per_task is not None:
            result["max_working_memory_per_task"] = self.max_working_memory_per_task
        if self.max_episodic_memory_per_agent is not None:
            result["max_episodic_memory_per_agent"] = self.max_episodic_memory_per_agent
        if self.allowed_semantic_namespaces is not None:
            result["allowed_semantic_namespaces"] = self.allowed_semantic_namespaces
        if self.denied_semantic_namespaces is not None:
            result["denied_semantic_namespaces"] = self.denied_semantic_namespaces
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Guardrails":
        return cls(
            max_budget_usd=data.get("max_budget_usd"),
            warn_at_percentage=data.get("warn_at_percentage", 80),
            on_exceed=GuardrailExceedAction(
                data.get("on_exceed", "pause_and_escalate")
            ),
            max_tasks_per_plan=data.get("max_tasks_per_plan", 20),
            max_delegation_depth=data.get("max_delegation_depth", 3),
            max_concurrent_tasks=data.get("max_concurrent_tasks", 10),
            max_plan_versions=data.get("max_plan_versions", 5),
            allowed_capabilities=data.get("allowed_capabilities"),
            max_plan_duration_hours=data.get("max_plan_duration_hours"),
            max_task_wait_hours=data.get("max_task_wait_hours"),
            checkpoint_timeout_hours=data.get("checkpoint_timeout_hours", 24),
            require_progress_every_minutes=data.get("require_progress_every_minutes"),
            requires_plan_review=data.get("requires_plan_review", False),
            requires_replan_review=data.get("requires_replan_review", False),
            auto_escalate_after_failures=data.get("auto_escalate_after_failures", 3),
            require_human_for_capabilities=data.get(
                "require_human_for_capabilities", []
            ),
            max_working_memory_per_task=data.get("max_working_memory_per_task"),
            max_episodic_memory_per_agent=data.get("max_episodic_memory_per_agent"),
            allowed_semantic_namespaces=data.get("allowed_semantic_namespaces"),
            denied_semantic_namespaces=data.get("denied_semantic_namespaces"),
            memory_archive_required=data.get("memory_archive_required", True),
        )


@dataclass
class CoordinatorLease:
    """Lease granting coordinator authority over an intent or portfolio (RFC-0013)."""

    id: str
    intent_id: Optional[str] = None
    portfolio_id: Optional[str] = None
    agent_id: str = ""
    role: str = "coordinator"
    supervisor_id: Optional[str] = None
    coordinator_type: CoordinatorType = CoordinatorType.LLM
    scope: CoordinatorScope = CoordinatorScope.INTENT
    status: CoordinatorStatus = CoordinatorStatus.ACTIVE
    guardrails: Optional[Guardrails] = None
    heartbeat_interval_seconds: int = 60
    last_heartbeat: Optional[datetime] = None
    granted_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    version: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "id": self.id,
            "agent_id": self.agent_id,
            "role": self.role,
            "coordinator_type": self.coordinator_type.value,
            "scope": self.scope.value,
            "status": self.status.value,
            "heartbeat_interval_seconds": self.heartbeat_interval_seconds,
            "version": self.version,
            "metadata": self.metadata,
        }
        if self.intent_id:
            result["intent_id"] = self.intent_id
        if self.portfolio_id:
            result["portfolio_id"] = self.portfolio_id
        if self.supervisor_id:
            result["supervisor_id"] = self.supervisor_id
        if self.guardrails:
            result["guardrails"] = self.guardrails.to_dict()
        if self.last_heartbeat:
            result["last_heartbeat"] = self.last_heartbeat.isoformat()
        if self.granted_at:
            result["granted_at"] = self.granted_at.isoformat()
        if self.expires_at:
            result["expires_at"] = self.expires_at.isoformat()
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CoordinatorLease":
        guardrails = None
        if data.get("guardrails"):
            guardrails = Guardrails.from_dict(data["guardrails"])
        return cls(
            id=data["id"],
            intent_id=data.get("intent_id"),
            portfolio_id=data.get("portfolio_id"),
            agent_id=data.get("agent_id", ""),
            role=data.get("role", "coordinator"),
            supervisor_id=data.get("supervisor_id"),
            coordinator_type=CoordinatorType(
                data.get("coordinator_type", data.get("type", "llm"))
            ),
            scope=CoordinatorScope(data.get("scope", "intent")),
            status=CoordinatorStatus(data.get("status", "active")),
            guardrails=guardrails,
            heartbeat_interval_seconds=data.get("heartbeat_interval_seconds", 60),
            last_heartbeat=(
                datetime.fromisoformat(data["last_heartbeat"])
                if data.get("last_heartbeat")
                else None
            ),
            granted_at=(
                datetime.fromisoformat(data["granted_at"])
                if data.get("granted_at")
                else None
            ),
            expires_at=(
                datetime.fromisoformat(data["expires_at"])
                if data.get("expires_at")
                else None
            ),
            version=data.get("version", 1),
            metadata=data.get("metadata", {}),
        )


@dataclass
class DecisionRecord:
    """Auditable record of a coordination decision (RFC-0013)."""

    id: str
    coordinator_id: str
    intent_id: str
    decision_type: DecisionType
    summary: str
    rationale: str
    alternatives_considered: list[dict[str, Any]] = field(default_factory=list)
    confidence: Optional[float] = None
    timestamp: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "id": self.id,
            "type": "coordinator.decision",
            "coordinator_id": self.coordinator_id,
            "intent_id": self.intent_id,
            "decision_type": self.decision_type.value,
            "summary": self.summary,
            "rationale": self.rationale,
            "alternatives_considered": self.alternatives_considered,
        }
        if self.confidence is not None:
            result["confidence"] = self.confidence
        if self.timestamp:
            result["timestamp"] = self.timestamp.isoformat()
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DecisionRecord":
        return cls(
            id=data.get("id", ""),
            coordinator_id=data.get("coordinator_id", ""),
            intent_id=data.get("intent_id", ""),
            decision_type=DecisionType(data.get("decision_type", "plan_created")),
            summary=data.get("summary", ""),
            rationale=data.get("rationale", ""),
            alternatives_considered=data.get("alternatives_considered", []),
            confidence=data.get("confidence"),
            timestamp=(
                datetime.fromisoformat(data["timestamp"])
                if data.get("timestamp")
                else None
            ),
        )


# ===========================================================================
# RFC-0014: Credential Vaults & Tool Scoping — Dataclasses
# ===========================================================================


@dataclass
class CredentialVault:
    """User-owned encrypted store for external service credentials (RFC-0014)."""

    id: str
    owner_id: str
    name: str
    credentials: list[str] = field(default_factory=list)
    created_at: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "id": self.id,
            "owner_id": self.owner_id,
            "name": self.name,
            "credentials": self.credentials,
        }
        if self.created_at:
            result["created_at"] = self.created_at.isoformat()
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CredentialVault":
        return cls(
            id=data["id"],
            owner_id=data.get("owner_id", ""),
            name=data.get("name", ""),
            credentials=data.get("credentials", []),
            created_at=(
                datetime.fromisoformat(data["created_at"])
                if data.get("created_at")
                else None
            ),
        )


@dataclass
class Credential:
    """Encrypted record of authentication material for an external service (RFC-0014)."""

    id: str
    vault_id: str
    service: str
    label: str
    auth_type: AuthType
    scopes_available: list[str] = field(default_factory=list)
    status: CredentialStatus = CredentialStatus.ACTIVE
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: Optional[datetime] = None
    rotated_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "id": self.id,
            "vault_id": self.vault_id,
            "service": self.service,
            "label": self.label,
            "auth_type": self.auth_type.value,
            "scopes_available": self.scopes_available,
            "status": self.status.value,
            "metadata": self.metadata,
        }
        if self.created_at:
            result["created_at"] = self.created_at.isoformat()
        if self.rotated_at:
            result["rotated_at"] = self.rotated_at.isoformat()
        if self.expires_at:
            result["expires_at"] = self.expires_at.isoformat()
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Credential":
        return cls(
            id=data["id"],
            vault_id=data.get("vault_id", ""),
            service=data.get("service", ""),
            label=data.get("label", ""),
            auth_type=AuthType(data.get("auth_type", "api_key")),
            scopes_available=data.get("scopes_available", []),
            status=CredentialStatus(data.get("status", "active")),
            metadata=data.get("metadata", {}),
            created_at=(
                datetime.fromisoformat(data["created_at"])
                if data.get("created_at")
                else None
            ),
            rotated_at=(
                datetime.fromisoformat(data["rotated_at"])
                if data.get("rotated_at")
                else None
            ),
            expires_at=(
                datetime.fromisoformat(data["expires_at"])
                if data.get("expires_at")
                else None
            ),
        )


@dataclass
class GrantConstraints:
    """Operational constraints on a tool grant (RFC-0014)."""

    max_invocations_per_hour: Optional[int] = None
    max_cost_per_invocation: Optional[float] = None
    allowed_parameters: Optional[dict[str, Any]] = None
    denied_parameters: Optional[dict[str, Any]] = None
    ip_allowlist: Optional[list[str]] = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        if self.max_invocations_per_hour is not None:
            result["max_invocations_per_hour"] = self.max_invocations_per_hour
        if self.max_cost_per_invocation is not None:
            result["max_cost_per_invocation"] = self.max_cost_per_invocation
        if self.allowed_parameters is not None:
            result["allowed_parameters"] = self.allowed_parameters
        if self.denied_parameters is not None:
            result["denied_parameters"] = self.denied_parameters
        if self.ip_allowlist is not None:
            result["ip_allowlist"] = self.ip_allowlist
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GrantConstraints":
        return cls(
            max_invocations_per_hour=data.get("max_invocations_per_hour"),
            max_cost_per_invocation=data.get("max_cost_per_invocation"),
            allowed_parameters=data.get("allowed_parameters"),
            denied_parameters=data.get("denied_parameters"),
            ip_allowlist=data.get("ip_allowlist"),
        )


@dataclass
class ToolGrant:
    """Permission linking an agent to external service tools (RFC-0014)."""

    id: str
    credential_id: str
    agent_id: str
    granted_by: str
    scopes: list[str] = field(default_factory=list)
    constraints: Optional[GrantConstraints] = None
    source: GrantSource = GrantSource.DIRECT
    delegatable: bool = False
    delegation_depth: int = 0
    delegated_from: Optional[str] = None
    context: dict[str, Any] = field(default_factory=dict)
    status: GrantStatus = GrantStatus.ACTIVE
    expires_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "id": self.id,
            "credential_id": self.credential_id,
            "agent_id": self.agent_id,
            "granted_by": self.granted_by,
            "scopes": self.scopes,
            "source": self.source.value,
            "delegatable": self.delegatable,
            "delegation_depth": self.delegation_depth,
            "context": self.context,
            "status": self.status.value,
        }
        if self.constraints:
            result["constraints"] = self.constraints.to_dict()
        if self.delegated_from:
            result["delegated_from"] = self.delegated_from
        if self.expires_at:
            result["expires_at"] = self.expires_at.isoformat()
        if self.created_at:
            result["created_at"] = self.created_at.isoformat()
        if self.revoked_at:
            result["revoked_at"] = self.revoked_at.isoformat()
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ToolGrant":
        constraints = None
        if data.get("constraints"):
            constraints = GrantConstraints.from_dict(data["constraints"])
        return cls(
            id=data["id"],
            credential_id=data.get("credential_id", ""),
            agent_id=data.get("agent_id", ""),
            granted_by=data.get("granted_by", ""),
            scopes=data.get("scopes", []),
            constraints=constraints,
            source=GrantSource(data.get("source", "direct")),
            delegatable=data.get("delegatable", False),
            delegation_depth=data.get("delegation_depth", 0),
            delegated_from=data.get("delegated_from"),
            context=data.get("context", {}),
            status=GrantStatus(data.get("status", "active")),
            expires_at=(
                datetime.fromisoformat(data["expires_at"])
                if data.get("expires_at")
                else None
            ),
            created_at=(
                datetime.fromisoformat(data["created_at"])
                if data.get("created_at")
                else None
            ),
            revoked_at=(
                datetime.fromisoformat(data["revoked_at"])
                if data.get("revoked_at")
                else None
            ),
        )


@dataclass
class ToolInvocation:
    """Record of a tool proxy invocation (RFC-0014)."""

    invocation_id: str
    grant_id: str
    service: str
    tool: str
    agent_id: str
    parameters: dict[str, Any] = field(default_factory=dict)
    status: InvocationStatus = InvocationStatus.SUCCESS
    result: Optional[dict[str, Any]] = None
    error: Optional[dict[str, Any]] = None
    cost: Optional[dict[str, Any]] = None
    duration_ms: Optional[int] = None
    idempotency_key: Optional[str] = None
    context: dict[str, Any] = field(default_factory=dict)
    timestamp: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        result_dict: dict[str, Any] = {
            "invocation_id": self.invocation_id,
            "grant_id": self.grant_id,
            "service": self.service,
            "tool": self.tool,
            "agent_id": self.agent_id,
            "status": self.status.value,
            "context": self.context,
        }
        if self.result is not None:
            result_dict["result"] = self.result
        if self.error is not None:
            result_dict["error"] = self.error
        if self.cost is not None:
            result_dict["cost"] = self.cost
        if self.duration_ms is not None:
            result_dict["duration_ms"] = self.duration_ms
        if self.idempotency_key:
            result_dict["idempotency_key"] = self.idempotency_key
        if self.timestamp:
            result_dict["timestamp"] = self.timestamp.isoformat()
        return result_dict

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ToolInvocation":
        return cls(
            invocation_id=data.get("invocation_id", ""),
            grant_id=data.get("grant_id", ""),
            service=data.get("service", ""),
            tool=data.get("tool", ""),
            agent_id=data.get("agent_id", ""),
            parameters=data.get("parameters", {}),
            status=InvocationStatus(data.get("status", "success")),
            result=data.get("result"),
            error=data.get("error"),
            cost=data.get("cost"),
            duration_ms=data.get("duration_ms"),
            idempotency_key=data.get("idempotency_key"),
            context=data.get("context", {}),
            timestamp=(
                datetime.fromisoformat(data["timestamp"])
                if data.get("timestamp")
                else None
            ),
        )


# ===========================================================================
# RFC-0015: Agent Memory & Persistent State — Dataclasses
# ===========================================================================


@dataclass
class MemoryScope:
    """Binds a memory entry to a task or intent context (RFC-0015)."""

    task_id: Optional[str] = None
    intent_id: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        if self.task_id:
            result["task_id"] = self.task_id
        if self.intent_id:
            result["intent_id"] = self.intent_id
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemoryScope":
        return cls(
            task_id=data.get("task_id"),
            intent_id=data.get("intent_id"),
        )


@dataclass
class MemoryEntry:
    """Fundamental unit of agent state (RFC-0015)."""

    id: str
    agent_id: str
    namespace: str
    key: str
    value: dict[str, Any]
    memory_type: MemoryType
    version: int = 1
    scope: Optional[MemoryScope] = None
    tags: list[str] = field(default_factory=list)
    ttl: Optional[str] = None
    pinned: bool = False
    priority: MemoryPriority = MemoryPriority.NORMAL
    sensitivity: Optional[MemorySensitivity] = None
    curated_by: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "id": self.id,
            "agent_id": self.agent_id,
            "namespace": self.namespace,
            "key": self.key,
            "value": self.value,
            "memory_type": self.memory_type.value,
            "version": self.version,
            "tags": self.tags,
            "pinned": self.pinned,
            "priority": self.priority.value,
        }
        if self.scope:
            result["scope"] = self.scope.to_dict()
        if self.ttl:
            result["ttl"] = self.ttl
        if self.sensitivity:
            result["sensitivity"] = self.sensitivity.value
        if self.curated_by:
            result["curated_by"] = self.curated_by
        if self.created_at:
            result["created_at"] = self.created_at.isoformat()
        if self.updated_at:
            result["updated_at"] = self.updated_at.isoformat()
        if self.expires_at:
            result["expires_at"] = self.expires_at.isoformat()
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemoryEntry":
        scope = None
        if data.get("scope"):
            scope = MemoryScope.from_dict(data["scope"])
        return cls(
            id=data.get("id", ""),
            agent_id=data.get("agent_id", ""),
            namespace=data.get("namespace", ""),
            key=data.get("key", ""),
            value=data.get("value", {}),
            memory_type=MemoryType(data.get("memory_type", "working")),
            version=data.get("version", 1),
            scope=scope,
            tags=data.get("tags", []),
            ttl=data.get("ttl"),
            pinned=data.get("pinned", False),
            priority=MemoryPriority(data.get("priority", "normal")),
            sensitivity=(
                MemorySensitivity(data["sensitivity"])
                if data.get("sensitivity")
                else None
            ),
            curated_by=data.get("curated_by"),
            created_at=(
                datetime.fromisoformat(data["created_at"])
                if data.get("created_at")
                else None
            ),
            updated_at=(
                datetime.fromisoformat(data["updated_at"])
                if data.get("updated_at")
                else None
            ),
            expires_at=(
                datetime.fromisoformat(data["expires_at"])
                if data.get("expires_at")
                else None
            ),
        )


@dataclass
class NamespacePermissions:
    """Access control for a semantic memory namespace (RFC-0015)."""

    namespace: str
    default: str = "read"
    allow: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "namespace": self.namespace,
            "permissions": {
                "default": self.default,
                "allow": self.allow,
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NamespacePermissions":
        perms = data.get("permissions", {})
        return cls(
            namespace=data.get("namespace", ""),
            default=perms.get("default", "read"),
            allow=perms.get("allow", []),
        )


# ===========================================================================
# RFC-0016: Agent Lifecycle & Health — Dataclasses
# ===========================================================================


@dataclass
class HeartbeatConfig:
    """Heartbeat timing configuration for an agent (RFC-0016)."""

    interval_seconds: int = 30
    unhealthy_after_seconds: int = 90
    dead_after_seconds: int = 300

    def to_dict(self) -> dict[str, Any]:
        return {
            "interval_seconds": self.interval_seconds,
            "unhealthy_after_seconds": self.unhealthy_after_seconds,
            "dead_after_seconds": self.dead_after_seconds,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HeartbeatConfig":
        return cls(
            interval_seconds=data.get("interval_seconds", 30),
            unhealthy_after_seconds=data.get("unhealthy_after_seconds", 90),
            dead_after_seconds=data.get("dead_after_seconds", 300),
        )


@dataclass
class AgentCapacity:
    """Capacity declaration for an agent (RFC-0016)."""

    max_concurrent_tasks: int = 5
    current_load: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_concurrent_tasks": self.max_concurrent_tasks,
            "current_load": self.current_load,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentCapacity":
        return cls(
            max_concurrent_tasks=data.get("max_concurrent_tasks", 5),
            current_load=data.get("current_load", 0),
        )


@dataclass
class AgentRecord:
    """Protocol-level representation of a participating agent (RFC-0016, RFC-0018)."""

    agent_id: str
    status: AgentStatus = AgentStatus.ACTIVE
    role_id: Optional[str] = None
    name: Optional[str] = None
    capabilities: list[str] = field(default_factory=list)
    capacity: Optional[AgentCapacity] = None
    endpoint: Optional[str] = None
    heartbeat_config: Optional[HeartbeatConfig] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    registered_at: Optional[datetime] = None
    last_heartbeat_at: Optional[datetime] = None
    drain_timeout_seconds: Optional[int] = None
    version: int = 1
    public_key: Optional[str] = None
    did: Optional[str] = None
    key_algorithm: Optional[str] = None
    key_registered_at: Optional[datetime] = None
    key_expires_at: Optional[datetime] = None
    previous_keys: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "agent_id": self.agent_id,
            "status": self.status.value,
            "capabilities": self.capabilities,
            "metadata": self.metadata,
            "version": self.version,
        }
        if self.role_id:
            result["role_id"] = self.role_id
        if self.name:
            result["name"] = self.name
        if self.capacity:
            result["capacity"] = self.capacity.to_dict()
        if self.endpoint:
            result["endpoint"] = self.endpoint
        if self.heartbeat_config:
            result["heartbeat_config"] = self.heartbeat_config.to_dict()
        if self.registered_at:
            result["registered_at"] = self.registered_at.isoformat()
        if self.last_heartbeat_at:
            result["last_heartbeat_at"] = self.last_heartbeat_at.isoformat()
        if self.drain_timeout_seconds is not None:
            result["drain_timeout_seconds"] = self.drain_timeout_seconds
        if self.public_key:
            result["public_key"] = self.public_key
        if self.did:
            result["did"] = self.did
        if self.key_algorithm:
            result["key_algorithm"] = self.key_algorithm
        if self.key_registered_at:
            result["key_registered_at"] = self.key_registered_at.isoformat()
        if self.key_expires_at:
            result["key_expires_at"] = self.key_expires_at.isoformat()
        if self.previous_keys:
            result["previous_keys"] = self.previous_keys
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentRecord":
        capacity = None
        if data.get("capacity"):
            capacity = AgentCapacity.from_dict(data["capacity"])
        heartbeat_config = None
        if data.get("heartbeat_config"):
            heartbeat_config = HeartbeatConfig.from_dict(data["heartbeat_config"])
        return cls(
            agent_id=data.get("agent_id", ""),
            status=AgentStatus(data.get("status", "active")),
            role_id=data.get("role_id"),
            name=data.get("name"),
            capabilities=data.get("capabilities", []),
            capacity=capacity,
            endpoint=data.get("endpoint"),
            heartbeat_config=heartbeat_config,
            metadata=data.get("metadata", {}),
            registered_at=(
                datetime.fromisoformat(data["registered_at"])
                if data.get("registered_at")
                else None
            ),
            last_heartbeat_at=(
                datetime.fromisoformat(data["last_heartbeat_at"])
                if data.get("last_heartbeat_at")
                else None
            ),
            drain_timeout_seconds=data.get("drain_timeout_seconds"),
            version=data.get("version", 1),
            public_key=data.get("public_key"),
            did=data.get("did"),
            key_algorithm=data.get("key_algorithm"),
            key_registered_at=(
                datetime.fromisoformat(data["key_registered_at"])
                if data.get("key_registered_at")
                else None
            ),
            key_expires_at=(
                datetime.fromisoformat(data["key_expires_at"])
                if data.get("key_expires_at")
                else None
            ),
            previous_keys=data.get("previous_keys", []),
        )


@dataclass
class Heartbeat:
    """Agent heartbeat payload (RFC-0016)."""

    agent_id: str
    status: str = "active"
    current_load: int = 0
    tasks_in_progress: list[str] = field(default_factory=list)
    client_timestamp: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "agent_id": self.agent_id,
            "status": self.status,
            "current_load": self.current_load,
            "tasks_in_progress": self.tasks_in_progress,
        }
        if self.client_timestamp:
            result["client_timestamp"] = self.client_timestamp.isoformat()
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Heartbeat":
        return cls(
            agent_id=data.get("agent_id", ""),
            status=data.get("status", "active"),
            current_load=data.get("current_load", 0),
            tasks_in_progress=data.get("tasks_in_progress", []),
            client_timestamp=(
                datetime.fromisoformat(data["client_timestamp"])
                if data.get("client_timestamp")
                else None
            ),
        )


# ===========================================================================
# RFC-0017: Triggers & Reactive Scheduling — Dataclasses
# ===========================================================================


@dataclass
class IntentTemplate:
    """Template for the intent created when a trigger fires (RFC-0017)."""

    type: str
    title: str
    priority: str = "medium"
    assignee: Optional[str] = None
    context: dict[str, Any] = field(default_factory=dict)
    graph_id: Optional[str] = None
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "type": self.type,
            "title": self.title,
            "priority": self.priority,
            "context": self.context,
            "tags": self.tags,
        }
        if self.assignee:
            result["assignee"] = self.assignee
        if self.graph_id:
            result["graph_id"] = self.graph_id
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IntentTemplate":
        return cls(
            type=data.get("type", ""),
            title=data.get("title", ""),
            priority=data.get("priority", "medium"),
            assignee=data.get("assignee"),
            context=data.get("context", {}),
            graph_id=data.get("graph_id"),
            tags=data.get("tags", []),
        )


@dataclass
class TriggerCondition:
    """Type-specific condition for a trigger (RFC-0017)."""

    cron: Optional[str] = None
    timezone: str = "UTC"
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    at: Optional[datetime] = None
    event: Optional[str] = None
    filter: Optional[dict[str, Any]] = None
    path: Optional[str] = None
    method: str = "POST"
    secret: Optional[str] = None
    transform: Optional[dict[str, str]] = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        if self.cron:
            result["cron"] = self.cron
            result["timezone"] = self.timezone
        if self.starts_at:
            result["starts_at"] = self.starts_at.isoformat()
        if self.ends_at:
            result["ends_at"] = self.ends_at.isoformat()
        if self.at:
            result["at"] = self.at.isoformat()
        if self.event:
            result["event"] = self.event
        if self.filter is not None:
            result["filter"] = self.filter
        if self.path:
            result["path"] = self.path
            result["method"] = self.method
        if self.transform is not None:
            result["transform"] = self.transform
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TriggerCondition":
        return cls(
            cron=data.get("cron"),
            timezone=data.get("timezone", "UTC"),
            starts_at=(
                datetime.fromisoformat(data["starts_at"])
                if data.get("starts_at")
                else None
            ),
            ends_at=(
                datetime.fromisoformat(data["ends_at"]) if data.get("ends_at") else None
            ),
            at=(datetime.fromisoformat(data["at"]) if data.get("at") else None),
            event=data.get("event"),
            filter=data.get("filter"),
            path=data.get("path"),
            method=data.get("method", "POST"),
            secret=data.get("secret"),
            transform=data.get("transform"),
        )


@dataclass
class TriggerLineage:
    """Lineage metadata for a trigger-created intent (RFC-0017)."""

    created_by: str = "trigger"
    trigger_id: str = ""
    trigger_type: str = ""
    trigger_depth: int = 1
    trigger_chain: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "created_by": self.created_by,
            "trigger_id": self.trigger_id,
            "trigger_type": self.trigger_type,
            "trigger_depth": self.trigger_depth,
            "trigger_chain": self.trigger_chain,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TriggerLineage":
        return cls(
            created_by=data.get("created_by", "trigger"),
            trigger_id=data.get("trigger_id", ""),
            trigger_type=data.get("trigger_type", ""),
            trigger_depth=data.get("trigger_depth", 1),
            trigger_chain=data.get("trigger_chain", []),
        )


@dataclass
class Trigger:
    """Standing declaration that creates intents when a condition is met (RFC-0017)."""

    trigger_id: str
    name: str
    type: TriggerType
    enabled: bool = True
    condition: Optional[TriggerCondition] = None
    intent_template: Optional[IntentTemplate] = None
    deduplication: DeduplicationMode = DeduplicationMode.ALLOW
    namespace: Optional[str] = None
    fire_count: int = 0
    version: int = 1
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_fired_at: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "trigger_id": self.trigger_id,
            "name": self.name,
            "type": self.type.value,
            "enabled": self.enabled,
            "deduplication": self.deduplication.value,
            "fire_count": self.fire_count,
            "version": self.version,
        }
        if self.condition:
            result["condition"] = self.condition.to_dict()
        if self.intent_template:
            result["intent_template"] = self.intent_template.to_dict()
        if self.namespace:
            result["namespace"] = self.namespace
        if self.created_at:
            result["created_at"] = self.created_at.isoformat()
        if self.updated_at:
            result["updated_at"] = self.updated_at.isoformat()
        if self.last_fired_at:
            result["last_fired_at"] = self.last_fired_at.isoformat()
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Trigger":
        condition = None
        if data.get("condition"):
            condition = TriggerCondition.from_dict(data["condition"])
        intent_template = None
        if data.get("intent_template"):
            intent_template = IntentTemplate.from_dict(data["intent_template"])
        return cls(
            trigger_id=data.get("trigger_id", ""),
            name=data.get("name", ""),
            type=TriggerType(data.get("type", "schedule")),
            enabled=data.get("enabled", True),
            condition=condition,
            intent_template=intent_template,
            deduplication=DeduplicationMode(data.get("deduplication", "allow")),
            namespace=data.get("namespace"),
            fire_count=data.get("fire_count", 0),
            version=data.get("version", 1),
            created_at=(
                datetime.fromisoformat(data["created_at"])
                if data.get("created_at")
                else None
            ),
            updated_at=(
                datetime.fromisoformat(data["updated_at"])
                if data.get("updated_at")
                else None
            ),
            last_fired_at=(
                datetime.fromisoformat(data["last_fired_at"])
                if data.get("last_fired_at")
                else None
            ),
        )


@dataclass
class TriggerPolicy:
    """Namespace governance for triggers (RFC-0017)."""

    namespace: str
    allow_global_triggers: bool = True
    allowed_trigger_types: Optional[list[str]] = None
    blocked_triggers: list[str] = field(default_factory=list)
    context_injection: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "namespace": self.namespace,
            "allow_global_triggers": self.allow_global_triggers,
            "blocked_triggers": self.blocked_triggers,
            "context_injection": self.context_injection,
        }
        if self.allowed_trigger_types is not None:
            result["allowed_trigger_types"] = self.allowed_trigger_types
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TriggerPolicy":
        return cls(
            namespace=data.get("namespace", ""),
            allow_global_triggers=data.get("allow_global_triggers", True),
            allowed_trigger_types=data.get("allowed_trigger_types"),
            blocked_triggers=data.get("blocked_triggers", []),
            context_injection=data.get("context_injection", {}),
        )


# ===========================================================================
# RFC-0018: Cryptographic Agent Identity — Dataclasses
# ===========================================================================


@dataclass
class AgentIdentity:
    """Cryptographic identity record for an agent (RFC-0018)."""

    agent_id: str
    public_key: str
    did: str
    key_algorithm: str = "Ed25519"
    registered_at: Optional[datetime] = None
    key_expires_at: Optional[datetime] = None
    previous_keys: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "agent_id": self.agent_id,
            "public_key": self.public_key,
            "did": self.did,
            "key_algorithm": self.key_algorithm,
            "previous_keys": self.previous_keys,
            "metadata": self.metadata,
        }
        if self.registered_at:
            result["registered_at"] = self.registered_at.isoformat()
        if self.key_expires_at:
            result["key_expires_at"] = self.key_expires_at.isoformat()
        else:
            result["key_expires_at"] = None
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentIdentity":
        return cls(
            agent_id=data.get("agent_id", ""),
            public_key=data.get("public_key", ""),
            did=data.get("did", ""),
            key_algorithm=data.get("key_algorithm", "Ed25519"),
            registered_at=(
                datetime.fromisoformat(data["registered_at"])
                if data.get("registered_at")
                else None
            ),
            key_expires_at=(
                datetime.fromisoformat(data["key_expires_at"])
                if data.get("key_expires_at")
                else None
            ),
            previous_keys=data.get("previous_keys", []),
            metadata=data.get("metadata", {}),
        )


@dataclass
class IdentityChallenge:
    """Challenge issued during key registration (RFC-0018)."""

    challenge: str
    challenge_expires_at: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"challenge": self.challenge}
        if self.challenge_expires_at:
            result["challenge_expires_at"] = self.challenge_expires_at.isoformat()
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IdentityChallenge":
        return cls(
            challenge=data.get("challenge", ""),
            challenge_expires_at=(
                datetime.fromisoformat(data["challenge_expires_at"])
                if data.get("challenge_expires_at")
                else None
            ),
        )


@dataclass
class IdentityVerification:
    """Result of verifying a signed payload (RFC-0018)."""

    valid: bool
    agent_id: str = ""
    did: str = ""
    verified_at: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "valid": self.valid,
            "agent_id": self.agent_id,
            "did": self.did,
        }
        if self.verified_at:
            result["verified_at"] = self.verified_at.isoformat()
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IdentityVerification":
        return cls(
            valid=data.get("valid", False),
            agent_id=data.get("agent_id", ""),
            did=data.get("did", ""),
            verified_at=(
                datetime.fromisoformat(data["verified_at"])
                if data.get("verified_at")
                else None
            ),
        )


# ===========================================================================
# RFC-0019: Verifiable Event Logs — Dataclasses
# ===========================================================================


@dataclass
class TimestampAnchor:
    """External timestamp anchor for a log checkpoint (RFC-0019)."""

    type: str = "external-timestamp"
    provider: str = ""
    reference: str = ""
    timestamp_proof: str = ""
    anchored_at: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "type": self.type,
            "provider": self.provider,
            "reference": self.reference,
            "timestamp_proof": self.timestamp_proof,
        }
        if self.anchored_at:
            result["anchored_at"] = self.anchored_at.isoformat()
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TimestampAnchor":
        return cls(
            type=data.get("type", "external-timestamp"),
            provider=data.get("provider", ""),
            reference=data.get("reference", ""),
            timestamp_proof=data.get("timestamp_proof", ""),
            anchored_at=(
                datetime.fromisoformat(data["anchored_at"])
                if data.get("anchored_at")
                else None
            ),
        )


@dataclass
class LogCheckpoint:
    """Signed checkpoint over a batch of event hashes (RFC-0019)."""

    checkpoint_id: str
    intent_id: Optional[str] = None
    scope: str = "intent"
    merkle_root: str = ""
    event_count: int = 0
    first_sequence: int = 0
    last_sequence: int = 0
    created_at: Optional[datetime] = None
    signed_by: Optional[str] = None
    signature: Optional[str] = None
    anchor: Optional[TimestampAnchor] = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "checkpoint_id": self.checkpoint_id,
            "intent_id": self.intent_id,
            "scope": self.scope,
            "merkle_root": self.merkle_root,
            "event_count": self.event_count,
            "first_sequence": self.first_sequence,
            "last_sequence": self.last_sequence,
        }
        if self.created_at:
            result["created_at"] = self.created_at.isoformat()
        if self.signed_by:
            result["signed_by"] = self.signed_by
        if self.signature:
            result["signature"] = self.signature
        if self.anchor:
            result["anchor"] = self.anchor.to_dict()
        else:
            result["anchor"] = None
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LogCheckpoint":
        anchor = None
        if data.get("anchor"):
            anchor = TimestampAnchor.from_dict(data["anchor"])
        return cls(
            checkpoint_id=data.get("checkpoint_id", ""),
            intent_id=data.get("intent_id"),
            scope=data.get("scope", "intent"),
            merkle_root=data.get("merkle_root", ""),
            event_count=data.get("event_count", 0),
            first_sequence=data.get("first_sequence", 0),
            last_sequence=data.get("last_sequence", 0),
            created_at=(
                datetime.fromisoformat(data["created_at"])
                if data.get("created_at")
                else None
            ),
            signed_by=data.get("signed_by"),
            signature=data.get("signature"),
            anchor=anchor,
        )


@dataclass
class MerkleProofEntry:
    """Single entry in a Merkle proof path (RFC-0019)."""

    hash: str
    position: str

    def to_dict(self) -> dict[str, Any]:
        return {"hash": self.hash, "position": self.position}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MerkleProofEntry":
        return cls(hash=data.get("hash", ""), position=data.get("position", "left"))


@dataclass
class MerkleProof:
    """Proof that an event is included in a checkpoint's Merkle tree (RFC-0019)."""

    event_id: str
    event_hash: str
    checkpoint_id: str
    merkle_root: str
    proof_hashes: list[MerkleProofEntry] = field(default_factory=list)
    leaf_index: int = 0

    def verify(self) -> bool:
        """Recompute root from proof hashes and compare to merkle_root."""
        import base64
        import hashlib

        raw = self.event_hash
        if raw.startswith("sha256:"):
            raw = raw[7:]
        try:
            current = base64.urlsafe_b64decode(raw + "==")
        except Exception:
            return False
        for entry in self.proof_hashes:
            sibling_raw = entry.hash
            if sibling_raw.startswith("sha256:"):
                sibling_raw = sibling_raw[7:]
            try:
                sibling = base64.urlsafe_b64decode(sibling_raw + "==")
            except Exception:
                return False
            if entry.position == "left":
                current = hashlib.sha256(sibling + current).digest()
            else:
                current = hashlib.sha256(current + sibling).digest()
        computed_root = (
            "sha256:" + base64.urlsafe_b64encode(current).rstrip(b"=").decode()
        )
        return computed_root == self.merkle_root

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_hash": self.event_hash,
            "checkpoint_id": self.checkpoint_id,
            "merkle_root": self.merkle_root,
            "proof_hashes": [e.to_dict() for e in self.proof_hashes],
            "leaf_index": self.leaf_index,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MerkleProof":
        return cls(
            event_id=data.get("event_id", ""),
            event_hash=data.get("event_hash", ""),
            checkpoint_id=data.get("checkpoint_id", ""),
            merkle_root=data.get("merkle_root", ""),
            proof_hashes=[
                MerkleProofEntry.from_dict(e) for e in data.get("proof_hashes", [])
            ],
            leaf_index=data.get("leaf_index", 0),
        )


@dataclass
class ChainVerification:
    """Result of verifying an intent's event hash chain (RFC-0019)."""

    intent_id: str
    valid: bool
    event_count: int = 0
    first_sequence: int = 0
    last_sequence: int = 0
    breaks: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent_id": self.intent_id,
            "valid": self.valid,
            "event_count": self.event_count,
            "first_sequence": self.first_sequence,
            "last_sequence": self.last_sequence,
            "chain_valid": self.valid,
            "breaks": self.breaks,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ChainVerification":
        return cls(
            intent_id=data.get("intent_id", ""),
            valid=data.get("valid", data.get("chain_valid", False)),
            event_count=data.get("event_count", 0),
            first_sequence=data.get("first_sequence", 0),
            last_sequence=data.get("last_sequence", 0),
            breaks=data.get("breaks", []),
        )


@dataclass
class ConsistencyProof:
    """Result of verifying consistency between two checkpoints (RFC-0019)."""

    from_checkpoint: str
    to_checkpoint: str
    consistent: bool
    boundary_event: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "from_checkpoint": self.from_checkpoint,
            "to_checkpoint": self.to_checkpoint,
            "consistent": self.consistent,
        }
        if self.boundary_event:
            result["boundary_event"] = self.boundary_event
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConsistencyProof":
        return cls(
            from_checkpoint=data.get("from_checkpoint", ""),
            to_checkpoint=data.get("to_checkpoint", ""),
            consistent=data.get("consistent", False),
            boundary_event=data.get("boundary_event"),
        )
