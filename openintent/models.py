"""
OpenIntent SDK - Data models based on the OpenIntent Protocol specification.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class IntentStatus(str, Enum):
    """Status of an intent in its lifecycle."""

    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"


class EventType(str, Enum):
    """Types of events that can occur on an intent."""

    CREATED = "created"
    STATE_UPDATED = "state_updated"
    STATUS_CHANGED = "status_changed"
    AGENT_ASSIGNED = "agent_assigned"
    AGENT_UNASSIGNED = "agent_unassigned"
    CONSTRAINT_ADDED = "constraint_added"
    CONSTRAINT_REMOVED = "constraint_removed"
    LEASE_ACQUIRED = "lease_acquired"
    LEASE_RELEASED = "lease_released"
    ARBITRATION_REQUESTED = "arbitration_requested"
    DECISION_RECORDED = "decision_recorded"
    COMMENT = "comment"


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
    """

    id: str
    title: str
    description: str
    version: int
    status: IntentStatus
    state: IntentState
    constraints: list[str] = field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "version": self.version,
            "status": self.status.value,
            "state": self.state.to_dict(),
            "constraints": self.constraints,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Intent":
        return cls(
            id=data["id"],
            title=data["title"],
            description=data["description"],
            version=data["version"],
            status=IntentStatus(data["status"]),
            state=IntentState.from_dict(data.get("state", {})),
            constraints=data.get("constraints", []),
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


@dataclass
class IntentEvent:
    """
    Immutable event in the intent's audit log.
    """

    id: str
    intent_id: str
    event_type: EventType
    agent_id: str
    payload: dict[str, Any]
    created_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "intent_id": self.intent_id,
            "event_type": self.event_type.value,
            "agent_id": self.agent_id,
            "payload": self.payload,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IntentEvent":
        return cls(
            id=data["id"],
            intent_id=data["intent_id"],
            event_type=EventType(data["event_type"]),
            agent_id=data["agent_id"],
            payload=data.get("payload", {}),
            created_at=datetime.fromisoformat(data["created_at"]),
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
