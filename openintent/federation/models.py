"""
OpenIntent SDK - Federation data models (RFC-0022 & RFC-0023).

Defines the canonical data structures for cross-server agent coordination:
envelopes, policies, attestations, delegation scopes, and discovery manifests.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class AgentVisibility(str, Enum):
    PUBLIC = "public"
    UNLISTED = "unlisted"
    PRIVATE = "private"


class PeerRelationship(str, Enum):
    PEER = "peer"
    UPSTREAM = "upstream"
    DOWNSTREAM = "downstream"


class TrustPolicy(str, Enum):
    OPEN = "open"
    ALLOWLIST = "allowlist"
    TRUSTLESS = "trustless"


class CallbackEventType(str, Enum):
    STATE_DELTA = "state_delta"
    STATUS_CHANGED = "status_changed"
    ATTESTATION = "attestation"
    BUDGET_WARNING = "budget_warning"
    COMPLETED = "completed"
    FAILED = "failed"


class DispatchStatus(str, Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    PENDING = "pending"


@dataclass
class DelegationScope:
    permissions: list[str] = field(
        default_factory=lambda: ["state.patch", "events.log"]
    )
    denied_operations: list[str] = field(default_factory=list)
    max_delegation_depth: int = 1
    expires_at: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "permissions": self.permissions,
            "denied_operations": self.denied_operations,
            "max_delegation_depth": self.max_delegation_depth,
        }
        if self.expires_at:
            result["expires_at"] = self.expires_at
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DelegationScope":
        return cls(
            permissions=data.get("permissions", ["state.patch", "events.log"]),
            denied_operations=data.get("denied_operations", []),
            max_delegation_depth=data.get("max_delegation_depth", 1),
            expires_at=data.get("expires_at"),
        )

    def attenuate(self, child_scope: "DelegationScope") -> "DelegationScope":
        allowed = set(self.permissions) & set(child_scope.permissions)
        denied = list(set(self.denied_operations) | set(child_scope.denied_operations))
        return DelegationScope(
            permissions=sorted(allowed),
            denied_operations=sorted(denied),
            max_delegation_depth=min(
                self.max_delegation_depth - 1,
                child_scope.max_delegation_depth,
            ),
            expires_at=self.expires_at,
        )


@dataclass
class FederationPolicy:
    governance: dict[str, Any] = field(default_factory=dict)
    budget: dict[str, Any] = field(default_factory=dict)
    observability: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "governance": self.governance,
            "budget": self.budget,
            "observability": self.observability,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FederationPolicy":
        return cls(
            governance=data.get("governance", {}),
            budget=data.get("budget", {}),
            observability=data.get("observability", {}),
        )

    def compose_strictest(self, other: "FederationPolicy") -> "FederationPolicy":
        governance = {**self.governance}
        for k, v in other.governance.items():
            if k in governance:
                if isinstance(v, bool) and isinstance(governance[k], bool):
                    governance[k] = governance[k] or v
                elif isinstance(v, (int, float)) and isinstance(
                    governance[k], (int, float)
                ):
                    governance[k] = min(governance[k], v)
                else:
                    governance[k] = v
            else:
                governance[k] = v

        budget = {**self.budget}
        for k, v in other.budget.items():
            if k in budget and isinstance(v, (int, float)):
                budget[k] = min(budget[k], v)
            else:
                budget[k] = v

        observability = {**self.observability, **other.observability}

        return FederationPolicy(
            governance=governance,
            budget=budget,
            observability=observability,
        )


@dataclass
class FederationAttestation:
    dispatch_id: str
    governance_compliant: bool = True
    usage: dict[str, Any] = field(default_factory=dict)
    trace_references: list[str] = field(default_factory=list)
    timestamp: Optional[str] = None
    signature: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "dispatch_id": self.dispatch_id,
            "governance_compliant": self.governance_compliant,
            "usage": self.usage,
            "trace_references": self.trace_references,
        }
        if self.timestamp:
            result["timestamp"] = self.timestamp
        if self.signature:
            result["signature"] = self.signature
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FederationAttestation":
        return cls(
            dispatch_id=data.get("dispatch_id", ""),
            governance_compliant=data.get("governance_compliant", True),
            usage=data.get("usage", {}),
            trace_references=data.get("trace_references", []),
            timestamp=data.get("timestamp"),
            signature=data.get("signature"),
        )


@dataclass
class FederationEnvelope:
    dispatch_id: str
    source_server: str
    target_server: str
    intent_id: str
    intent_title: str
    intent_description: str = ""
    intent_state: dict[str, Any] = field(default_factory=dict)
    intent_constraints: dict[str, Any] = field(default_factory=dict)
    agent_id: Optional[str] = None
    delegation_scope: Optional[DelegationScope] = None
    federation_policy: Optional[FederationPolicy] = None
    trace_context: Optional[dict[str, str]] = None
    callback_url: Optional[str] = None
    idempotency_key: Optional[str] = None
    created_at: Optional[str] = None
    signature: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "dispatch_id": self.dispatch_id,
            "source_server": self.source_server,
            "target_server": self.target_server,
            "intent_id": self.intent_id,
            "intent_title": self.intent_title,
            "intent_description": self.intent_description,
            "intent_state": self.intent_state,
            "intent_constraints": self.intent_constraints,
        }
        if self.agent_id:
            result["agent_id"] = self.agent_id
        if self.delegation_scope:
            result["delegation_scope"] = self.delegation_scope.to_dict()
        if self.federation_policy:
            result["federation_policy"] = self.federation_policy.to_dict()
        if self.trace_context:
            result["trace_context"] = self.trace_context
        if self.callback_url:
            result["callback_url"] = self.callback_url
        if self.idempotency_key:
            result["idempotency_key"] = self.idempotency_key
        if self.created_at:
            result["created_at"] = self.created_at
        if self.signature:
            result["signature"] = self.signature
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FederationEnvelope":
        delegation_scope = None
        if data.get("delegation_scope"):
            delegation_scope = DelegationScope.from_dict(data["delegation_scope"])
        federation_policy = None
        if data.get("federation_policy"):
            federation_policy = FederationPolicy.from_dict(data["federation_policy"])
        return cls(
            dispatch_id=data.get("dispatch_id", ""),
            source_server=data.get("source_server", ""),
            target_server=data.get("target_server", ""),
            intent_id=data.get("intent_id", ""),
            intent_title=data.get("intent_title", ""),
            intent_description=data.get("intent_description", ""),
            intent_state=data.get("intent_state", {}),
            intent_constraints=data.get("intent_constraints", {}),
            agent_id=data.get("agent_id"),
            delegation_scope=delegation_scope,
            federation_policy=federation_policy,
            trace_context=data.get("trace_context"),
            callback_url=data.get("callback_url"),
            idempotency_key=data.get("idempotency_key"),
            created_at=data.get("created_at"),
            signature=data.get("signature"),
        )


@dataclass
class FederationCallback:
    dispatch_id: str
    event_type: CallbackEventType
    state_delta: dict[str, Any] = field(default_factory=dict)
    attestation: Optional[FederationAttestation] = None
    trace_id: Optional[str] = None
    idempotency_key: Optional[str] = None
    timestamp: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "dispatch_id": self.dispatch_id,
            "event_type": self.event_type.value,
            "state_delta": self.state_delta,
        }
        if self.attestation:
            result["attestation"] = self.attestation.to_dict()
        if self.trace_id:
            result["trace_id"] = self.trace_id
        if self.idempotency_key:
            result["idempotency_key"] = self.idempotency_key
        if self.timestamp:
            result["timestamp"] = self.timestamp
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FederationCallback":
        attestation = None
        if data.get("attestation"):
            attestation = FederationAttestation.from_dict(data["attestation"])
        return cls(
            dispatch_id=data.get("dispatch_id", ""),
            event_type=CallbackEventType(data.get("event_type", "state_delta")),
            state_delta=data.get("state_delta", {}),
            attestation=attestation,
            trace_id=data.get("trace_id"),
            idempotency_key=data.get("idempotency_key"),
            timestamp=data.get("timestamp"),
        )


@dataclass
class PeerInfo:
    server_url: str
    server_did: Optional[str] = None
    relationship: PeerRelationship = PeerRelationship.PEER
    trust_policy: TrustPolicy = TrustPolicy.ALLOWLIST
    public_key: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "server_url": self.server_url,
            "relationship": self.relationship.value,
            "trust_policy": self.trust_policy.value,
        }
        if self.server_did:
            result["server_did"] = self.server_did
        if self.public_key:
            result["public_key"] = self.public_key
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PeerInfo":
        return cls(
            server_url=data.get("server_url", ""),
            server_did=data.get("server_did"),
            relationship=PeerRelationship(data.get("relationship", "peer")),
            trust_policy=TrustPolicy(data.get("trust_policy", "allowlist")),
            public_key=data.get("public_key"),
        )


@dataclass
class FederationManifest:
    server_did: str
    server_url: str
    protocol_version: str = "0.1"
    trust_policy: TrustPolicy = TrustPolicy.ALLOWLIST
    visibility_default: AgentVisibility = AgentVisibility.PUBLIC
    supported_rfcs: list[str] = field(default_factory=lambda: ["RFC-0022", "RFC-0023"])
    peers: list[str] = field(default_factory=list)
    public_key: Optional[str] = None
    endpoints: dict[str, str] = field(
        default_factory=lambda: {
            "status": "/api/v1/federation/status",
            "agents": "/api/v1/federation/agents",
            "dispatch": "/api/v1/federation/dispatch",
            "receive": "/api/v1/federation/receive",
        }
    )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "server_did": self.server_did,
            "server_url": self.server_url,
            "protocol_version": self.protocol_version,
            "trust_policy": self.trust_policy.value,
            "visibility_default": self.visibility_default.value,
            "supported_rfcs": self.supported_rfcs,
            "peers": self.peers,
            "endpoints": self.endpoints,
        }
        if self.public_key:
            result["public_key"] = self.public_key
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FederationManifest":
        return cls(
            server_did=data.get("server_did", ""),
            server_url=data.get("server_url", ""),
            protocol_version=data.get("protocol_version", "0.1"),
            trust_policy=TrustPolicy(data.get("trust_policy", "allowlist")),
            visibility_default=AgentVisibility(
                data.get("visibility_default", "public")
            ),
            supported_rfcs=data.get("supported_rfcs", ["RFC-0022", "RFC-0023"]),
            peers=data.get("peers", []),
            public_key=data.get("public_key"),
            endpoints=data.get("endpoints", {}),
        )


@dataclass
class FederationStatus:
    enabled: bool = True
    server_did: Optional[str] = None
    trust_policy: TrustPolicy = TrustPolicy.ALLOWLIST
    peer_count: int = 0
    active_dispatches: int = 0
    total_dispatches: int = 0
    total_received: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "server_did": self.server_did,
            "trust_policy": self.trust_policy.value,
            "peer_count": self.peer_count,
            "active_dispatches": self.active_dispatches,
            "total_dispatches": self.total_dispatches,
            "total_received": self.total_received,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FederationStatus":
        return cls(
            enabled=data.get("enabled", True),
            server_did=data.get("server_did"),
            trust_policy=TrustPolicy(data.get("trust_policy", "allowlist")),
            peer_count=data.get("peer_count", 0),
            active_dispatches=data.get("active_dispatches", 0),
            total_dispatches=data.get("total_dispatches", 0),
            total_received=data.get("total_received", 0),
        )


@dataclass
class DispatchResult:
    dispatch_id: str
    status: DispatchStatus
    target_server: str
    message: str = ""
    remote_intent_id: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "dispatch_id": self.dispatch_id,
            "status": self.status.value,
            "target_server": self.target_server,
            "message": self.message,
        }
        if self.remote_intent_id:
            result["remote_intent_id"] = self.remote_intent_id
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DispatchResult":
        return cls(
            dispatch_id=data.get("dispatch_id", ""),
            status=DispatchStatus(data.get("status", "pending")),
            target_server=data.get("target_server", ""),
            message=data.get("message", ""),
            remote_intent_id=data.get("remote_intent_id"),
        )


@dataclass
class ReceiveResult:
    dispatch_id: str
    accepted: bool
    local_intent_id: Optional[str] = None
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "dispatch_id": self.dispatch_id,
            "accepted": self.accepted,
            "message": self.message,
        }
        if self.local_intent_id:
            result["local_intent_id"] = self.local_intent_id
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReceiveResult":
        return cls(
            dispatch_id=data.get("dispatch_id", ""),
            accepted=data.get("accepted", False),
            local_intent_id=data.get("local_intent_id"),
            message=data.get("message", ""),
        )


@dataclass
class FederatedAgent:
    agent_id: str
    server_url: str
    capabilities: list[str] = field(default_factory=list)
    visibility: AgentVisibility = AgentVisibility.PUBLIC
    server_did: Optional[str] = None
    status: str = "active"

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "server_url": self.server_url,
            "capabilities": self.capabilities,
            "visibility": self.visibility.value,
            "server_did": self.server_did,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FederatedAgent":
        return cls(
            agent_id=data.get("agent_id", ""),
            server_url=data.get("server_url", ""),
            capabilities=data.get("capabilities", []),
            visibility=AgentVisibility(data.get("visibility", "public")),
            server_did=data.get("server_did"),
            status=data.get("status", "active"),
        )
