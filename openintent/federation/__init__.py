"""
OpenIntent SDK - Federation module (RFC-0022 & RFC-0023).

Cross-server agent coordination with structured delegation,
governance propagation, and optional cryptographic verification.
"""

from .decorators import (
    Federation,
    on_budget_warning,
    on_federation_callback,
    on_federation_received,
)
from .models import (
    AgentVisibility,
    CallbackEventType,
    DelegationScope,
    DispatchResult,
    DispatchStatus,
    FederatedAgent,
    FederationAttestation,
    FederationCallback,
    FederationEnvelope,
    FederationManifest,
    FederationPolicy,
    FederationStatus,
    PeerInfo,
    PeerRelationship,
    ReceiveResult,
    TrustPolicy,
)
from .security import (
    MessageSignature,
    ServerIdentity,
    TrustEnforcer,
    UCANToken,
    resolve_did_web,
    sign_envelope,
    validate_ssrf,
    verify_envelope_signature,
)

__all__ = [
    "AgentVisibility",
    "CallbackEventType",
    "DelegationScope",
    "DispatchResult",
    "DispatchStatus",
    "FederatedAgent",
    "Federation",
    "FederationAttestation",
    "FederationCallback",
    "FederationEnvelope",
    "FederationManifest",
    "FederationPolicy",
    "FederationStatus",
    "MessageSignature",
    "PeerInfo",
    "PeerRelationship",
    "ReceiveResult",
    "ServerIdentity",
    "TrustEnforcer",
    "TrustPolicy",
    "UCANToken",
    "on_budget_warning",
    "on_federation_callback",
    "on_federation_received",
    "resolve_did_web",
    "sign_envelope",
    "validate_ssrf",
    "verify_envelope_signature",
]
