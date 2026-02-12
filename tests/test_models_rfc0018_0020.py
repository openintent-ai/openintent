"""
Tests for OpenIntent SDK models — RFC 0018-0020.

RFC-0018: Cryptographic Agent Identity
RFC-0019: Verifiable Event Logs
RFC-0020: Distributed Tracing
"""

import base64
import hashlib
from datetime import datetime
from typing import Any

from openintent.models import (
    AgentIdentity,
    ChainVerification,
    ConsistencyProof,
    EventProof,
    EventType,
    IdentityChallenge,
    IdentityVerification,
    IntentEvent,
    LogCheckpoint,
    MerkleProof,
    MerkleProofEntry,
    TimestampAnchor,
    TracingContext,
)

# ===========================================================================
# RFC-0020: Distributed Tracing — TracingContext
# ===========================================================================


class TestTracingContext:
    """Tests for TracingContext dataclass (RFC-0020)."""

    def test_create_basic(self):
        ctx = TracingContext(trace_id="abc123")
        assert ctx.trace_id == "abc123"
        assert ctx.parent_event_id is None

    def test_create_with_parent(self):
        ctx = TracingContext(trace_id="abc123", parent_event_id="evt-1")
        assert ctx.trace_id == "abc123"
        assert ctx.parent_event_id == "evt-1"

    def test_child_creates_new_context(self):
        ctx = TracingContext(trace_id="abc123", parent_event_id="evt-1")
        child = ctx.child("evt-2")
        assert child.trace_id == "abc123"
        assert child.parent_event_id == "evt-2"
        assert ctx.parent_event_id == "evt-1"

    def test_child_preserves_trace_id(self):
        ctx = TracingContext(trace_id="trace-XYZ")
        child = ctx.child("evt-42")
        grandchild = child.child("evt-99")
        assert grandchild.trace_id == "trace-XYZ"
        assert grandchild.parent_event_id == "evt-99"

    def test_to_dict_basic(self):
        ctx = TracingContext(trace_id="abc123")
        d = ctx.to_dict()
        assert d == {"trace_id": "abc123"}

    def test_to_dict_with_parent(self):
        ctx = TracingContext(trace_id="abc123", parent_event_id="evt-1")
        d = ctx.to_dict()
        assert d == {"trace_id": "abc123", "parent_event_id": "evt-1"}

    def test_from_dict_basic(self):
        ctx = TracingContext.from_dict({"trace_id": "abc123"})
        assert ctx is not None
        assert ctx.trace_id == "abc123"
        assert ctx.parent_event_id is None

    def test_from_dict_with_parent(self):
        ctx = TracingContext.from_dict(
            {"trace_id": "abc123", "parent_event_id": "evt-1"}
        )
        assert ctx is not None
        assert ctx.trace_id == "abc123"
        assert ctx.parent_event_id == "evt-1"

    def test_from_dict_missing_trace_id_returns_none(self):
        ctx = TracingContext.from_dict({})
        assert ctx is None

    def test_from_dict_empty_trace_id_returns_none(self):
        ctx = TracingContext.from_dict({"trace_id": ""})
        assert ctx is None

    def test_from_dict_none_trace_id_returns_none(self):
        ctx = TracingContext.from_dict({"trace_id": None})
        assert ctx is None

    def test_new_root_generates_unique_ids(self):
        ctx1 = TracingContext.new_root()
        ctx2 = TracingContext.new_root()
        assert ctx1.trace_id != ctx2.trace_id
        assert ctx1.parent_event_id is None
        assert ctx2.parent_event_id is None

    def test_new_root_generates_128_bit_id(self):
        ctx = TracingContext.new_root()
        assert len(ctx.trace_id) == 32

    def test_roundtrip_serialization(self):
        ctx = TracingContext(trace_id="roundtrip-test", parent_event_id="parent-evt")
        d = ctx.to_dict()
        restored = TracingContext.from_dict(d)
        assert restored is not None
        assert restored.trace_id == ctx.trace_id
        assert restored.parent_event_id == ctx.parent_event_id

    def test_child_chain_three_levels(self):
        root = TracingContext.new_root()
        level1 = root.child("evt-a")
        level2 = level1.child("evt-b")
        level3 = level2.child("evt-c")
        assert level3.trace_id == root.trace_id
        assert level3.parent_event_id == "evt-c"
        assert level2.parent_event_id == "evt-b"
        assert level1.parent_event_id == "evt-a"


# ===========================================================================
# RFC-0018: Cryptographic Agent Identity — EventProof
# ===========================================================================


class TestEventProof:
    """Tests for EventProof dataclass (RFC-0018)."""

    def test_default_type(self):
        proof = EventProof()
        assert proof.type == "Ed25519Signature2026"

    def test_create_full(self):
        proof = EventProof(
            type="Ed25519Signature2026",
            created="2026-02-12T10:00:00Z",
            verification_method="did:key:z6Mk...",
            signature="base64sig==",
        )
        assert proof.signature == "base64sig=="
        assert proof.verification_method == "did:key:z6Mk..."

    def test_to_dict_minimal(self):
        proof = EventProof()
        d = proof.to_dict()
        assert d == {"type": "Ed25519Signature2026"}

    def test_to_dict_full(self):
        proof = EventProof(
            type="Ed25519Signature2026",
            created="2026-02-12T10:00:00Z",
            verification_method="did:key:z6Mk...",
            signature="base64sig==",
        )
        d = proof.to_dict()
        assert d["type"] == "Ed25519Signature2026"
        assert d["created"] == "2026-02-12T10:00:00Z"
        assert d["verification_method"] == "did:key:z6Mk..."
        assert d["signature"] == "base64sig=="

    def test_from_dict_empty(self):
        proof = EventProof.from_dict({})
        assert proof.type == "Ed25519Signature2026"
        assert proof.created is None
        assert proof.signature is None

    def test_from_dict_full(self):
        proof = EventProof.from_dict(
            {
                "type": "Ed25519Signature2026",
                "created": "2026-02-12T10:00:00Z",
                "verification_method": "did:key:z6Mk...",
                "signature": "base64sig==",
            }
        )
        assert proof.type == "Ed25519Signature2026"
        assert proof.created == "2026-02-12T10:00:00Z"
        assert proof.signature == "base64sig=="

    def test_roundtrip(self):
        proof = EventProof(
            type="Ed25519Signature2026",
            created="2026-02-12T10:00:00Z",
            verification_method="did:key:z6Mk...",
            signature="base64sig==",
        )
        restored = EventProof.from_dict(proof.to_dict())
        assert restored.type == proof.type
        assert restored.created == proof.created
        assert restored.verification_method == proof.verification_method
        assert restored.signature == proof.signature


# ===========================================================================
# RFC-0018: Cryptographic Agent Identity — AgentIdentity
# ===========================================================================


class TestAgentIdentity:
    """Tests for AgentIdentity dataclass (RFC-0018)."""

    def test_create_minimal(self):
        identity = AgentIdentity(
            agent_id="agent-1",
            public_key="pubkey123",
            did="did:key:z6MkTest",
        )
        assert identity.agent_id == "agent-1"
        assert identity.public_key == "pubkey123"
        assert identity.did == "did:key:z6MkTest"
        assert identity.key_algorithm == "Ed25519"
        assert identity.registered_at is None
        assert identity.key_expires_at is None
        assert identity.previous_keys == []
        assert identity.metadata == {}

    def test_create_full(self):
        now = datetime(2026, 2, 12, 10, 0, 0)
        expires = datetime(2027, 2, 12, 10, 0, 0)
        identity = AgentIdentity(
            agent_id="agent-1",
            public_key="pubkey123",
            did="did:key:z6MkTest",
            key_algorithm="Ed25519",
            registered_at=now,
            key_expires_at=expires,
            previous_keys=["oldkey1", "oldkey2"],
            metadata={"role": "validator"},
        )
        assert identity.registered_at == now
        assert identity.key_expires_at == expires
        assert len(identity.previous_keys) == 2
        assert identity.metadata["role"] == "validator"

    def test_to_dict(self):
        now = datetime(2026, 2, 12, 10, 0, 0)
        identity = AgentIdentity(
            agent_id="agent-1",
            public_key="pubkey123",
            did="did:key:z6MkTest",
            registered_at=now,
        )
        d = identity.to_dict()
        assert d["agent_id"] == "agent-1"
        assert d["public_key"] == "pubkey123"
        assert d["did"] == "did:key:z6MkTest"
        assert d["key_algorithm"] == "Ed25519"
        assert d["registered_at"] == "2026-02-12T10:00:00"
        assert d["key_expires_at"] is None
        assert d["previous_keys"] == []

    def test_from_dict_minimal(self):
        identity = AgentIdentity.from_dict(
            {
                "agent_id": "agent-1",
                "public_key": "pubkey123",
                "did": "did:key:z6MkTest",
            }
        )
        assert identity.agent_id == "agent-1"
        assert identity.key_algorithm == "Ed25519"
        assert identity.registered_at is None

    def test_from_dict_full(self):
        identity = AgentIdentity.from_dict(
            {
                "agent_id": "agent-1",
                "public_key": "pubkey123",
                "did": "did:key:z6MkTest",
                "key_algorithm": "Ed25519",
                "registered_at": "2026-02-12T10:00:00",
                "key_expires_at": "2027-02-12T10:00:00",
                "previous_keys": ["oldkey1"],
                "metadata": {"role": "validator"},
            }
        )
        assert identity.registered_at == datetime(2026, 2, 12, 10, 0, 0)
        assert identity.key_expires_at == datetime(2027, 2, 12, 10, 0, 0)
        assert identity.previous_keys == ["oldkey1"]
        assert identity.metadata["role"] == "validator"

    def test_from_dict_empty(self):
        identity = AgentIdentity.from_dict({})
        assert identity.agent_id == ""
        assert identity.public_key == ""
        assert identity.did == ""

    def test_roundtrip(self):
        now = datetime(2026, 2, 12, 10, 0, 0)
        original = AgentIdentity(
            agent_id="agent-1",
            public_key="pubkey123",
            did="did:key:z6MkTest",
            registered_at=now,
            previous_keys=["old1"],
            metadata={"version": 2},
        )
        restored = AgentIdentity.from_dict(original.to_dict())
        assert restored.agent_id == original.agent_id
        assert restored.public_key == original.public_key
        assert restored.did == original.did
        assert restored.registered_at == original.registered_at
        assert restored.previous_keys == original.previous_keys
        assert restored.metadata == original.metadata


# ===========================================================================
# RFC-0018: Cryptographic Agent Identity — IdentityChallenge
# ===========================================================================


class TestIdentityChallenge:
    """Tests for IdentityChallenge dataclass (RFC-0018)."""

    def test_create_basic(self):
        challenge = IdentityChallenge(challenge="random-nonce-bytes")
        assert challenge.challenge == "random-nonce-bytes"
        assert challenge.challenge_expires_at is None

    def test_create_with_expiry(self):
        expires = datetime(2026, 2, 12, 10, 5, 0)
        challenge = IdentityChallenge(
            challenge="random-nonce", challenge_expires_at=expires
        )
        assert challenge.challenge_expires_at == expires

    def test_to_dict_basic(self):
        challenge = IdentityChallenge(challenge="nonce123")
        d = challenge.to_dict()
        assert d == {"challenge": "nonce123"}

    def test_to_dict_with_expiry(self):
        expires = datetime(2026, 2, 12, 10, 5, 0)
        challenge = IdentityChallenge(
            challenge="nonce123", challenge_expires_at=expires
        )
        d = challenge.to_dict()
        assert d["challenge"] == "nonce123"
        assert d["challenge_expires_at"] == "2026-02-12T10:05:00"

    def test_from_dict(self):
        challenge = IdentityChallenge.from_dict(
            {
                "challenge": "nonce123",
                "challenge_expires_at": "2026-02-12T10:05:00",
            }
        )
        assert challenge.challenge == "nonce123"
        assert challenge.challenge_expires_at == datetime(2026, 2, 12, 10, 5, 0)

    def test_from_dict_empty(self):
        challenge = IdentityChallenge.from_dict({})
        assert challenge.challenge == ""
        assert challenge.challenge_expires_at is None

    def test_roundtrip(self):
        expires = datetime(2026, 2, 12, 10, 5, 0)
        original = IdentityChallenge(
            challenge="nonce-xyz", challenge_expires_at=expires
        )
        restored = IdentityChallenge.from_dict(original.to_dict())
        assert restored.challenge == original.challenge
        assert restored.challenge_expires_at == original.challenge_expires_at


# ===========================================================================
# RFC-0018: Cryptographic Agent Identity — IdentityVerification
# ===========================================================================


class TestIdentityVerification:
    """Tests for IdentityVerification dataclass (RFC-0018)."""

    def test_create_valid(self):
        v = IdentityVerification(valid=True, agent_id="agent-1", did="did:key:z6Mk...")
        assert v.valid is True
        assert v.agent_id == "agent-1"
        assert v.did == "did:key:z6Mk..."

    def test_create_invalid(self):
        v = IdentityVerification(valid=False)
        assert v.valid is False
        assert v.agent_id == ""
        assert v.did == ""

    def test_to_dict(self):
        now = datetime(2026, 2, 12, 10, 0, 0)
        v = IdentityVerification(
            valid=True, agent_id="agent-1", did="did:key:z6Mk...", verified_at=now
        )
        d = v.to_dict()
        assert d["valid"] is True
        assert d["agent_id"] == "agent-1"
        assert d["did"] == "did:key:z6Mk..."
        assert d["verified_at"] == "2026-02-12T10:00:00"

    def test_from_dict(self):
        v = IdentityVerification.from_dict(
            {
                "valid": True,
                "agent_id": "agent-1",
                "did": "did:key:z6Mk...",
                "verified_at": "2026-02-12T10:00:00",
            }
        )
        assert v.valid is True
        assert v.verified_at == datetime(2026, 2, 12, 10, 0, 0)

    def test_from_dict_defaults(self):
        v = IdentityVerification.from_dict({})
        assert v.valid is False
        assert v.agent_id == ""
        assert v.did == ""
        assert v.verified_at is None

    def test_roundtrip(self):
        now = datetime(2026, 2, 12, 10, 0, 0)
        original = IdentityVerification(
            valid=True, agent_id="agent-1", did="did:key:z6Mk...", verified_at=now
        )
        restored = IdentityVerification.from_dict(original.to_dict())
        assert restored.valid == original.valid
        assert restored.agent_id == original.agent_id
        assert restored.did == original.did
        assert restored.verified_at == original.verified_at


# ===========================================================================
# RFC-0019: Verifiable Event Logs — TimestampAnchor
# ===========================================================================


class TestTimestampAnchor:
    """Tests for TimestampAnchor dataclass (RFC-0019)."""

    def test_create_defaults(self):
        anchor = TimestampAnchor()
        assert anchor.type == "external-timestamp"
        assert anchor.provider == ""
        assert anchor.reference == ""
        assert anchor.timestamp_proof == ""
        assert anchor.anchored_at is None

    def test_create_full(self):
        now = datetime(2026, 2, 12, 10, 0, 0)
        anchor = TimestampAnchor(
            type="external-timestamp",
            provider="opentimestamps",
            reference="ots://abc123",
            timestamp_proof="proof-data",
            anchored_at=now,
        )
        assert anchor.provider == "opentimestamps"
        assert anchor.anchored_at == now

    def test_to_dict(self):
        now = datetime(2026, 2, 12, 10, 0, 0)
        anchor = TimestampAnchor(
            provider="rfc3161",
            reference="tsa://ref",
            timestamp_proof="proof",
            anchored_at=now,
        )
        d = anchor.to_dict()
        assert d["type"] == "external-timestamp"
        assert d["provider"] == "rfc3161"
        assert d["anchored_at"] == "2026-02-12T10:00:00"

    def test_to_dict_no_anchored_at(self):
        anchor = TimestampAnchor(provider="test")
        d = anchor.to_dict()
        assert "anchored_at" not in d

    def test_from_dict(self):
        anchor = TimestampAnchor.from_dict(
            {
                "type": "external-timestamp",
                "provider": "opentimestamps",
                "reference": "ots://abc",
                "timestamp_proof": "proof-data",
                "anchored_at": "2026-02-12T10:00:00",
            }
        )
        assert anchor.provider == "opentimestamps"
        assert anchor.anchored_at == datetime(2026, 2, 12, 10, 0, 0)

    def test_from_dict_empty(self):
        anchor = TimestampAnchor.from_dict({})
        assert anchor.type == "external-timestamp"
        assert anchor.provider == ""
        assert anchor.anchored_at is None

    def test_roundtrip(self):
        now = datetime(2026, 2, 12, 10, 0, 0)
        original = TimestampAnchor(
            provider="opentimestamps",
            reference="ots://abc",
            timestamp_proof="proof",
            anchored_at=now,
        )
        restored = TimestampAnchor.from_dict(original.to_dict())
        assert restored.provider == original.provider
        assert restored.reference == original.reference
        assert restored.anchored_at == original.anchored_at


# ===========================================================================
# RFC-0019: Verifiable Event Logs — LogCheckpoint
# ===========================================================================


class TestLogCheckpoint:
    """Tests for LogCheckpoint dataclass (RFC-0019)."""

    def test_create_minimal(self):
        cp = LogCheckpoint(checkpoint_id="cp-1")
        assert cp.checkpoint_id == "cp-1"
        assert cp.scope == "intent"
        assert cp.merkle_root == ""
        assert cp.event_count == 0
        assert cp.anchor is None

    def test_create_full(self):
        now = datetime(2026, 2, 12, 10, 0, 0)
        anchor = TimestampAnchor(provider="test")
        cp = LogCheckpoint(
            checkpoint_id="cp-1",
            intent_id="intent-1",
            scope="intent",
            merkle_root="sha256:abc",
            event_count=50,
            first_sequence=1,
            last_sequence=50,
            created_at=now,
            signed_by="agent-1",
            signature="sig-data",
            anchor=anchor,
        )
        assert cp.event_count == 50
        assert cp.signed_by == "agent-1"
        assert cp.anchor is not None
        assert cp.anchor.provider == "test"

    def test_to_dict(self):
        now = datetime(2026, 2, 12, 10, 0, 0)
        cp = LogCheckpoint(
            checkpoint_id="cp-1",
            intent_id="intent-1",
            merkle_root="sha256:abc",
            event_count=10,
            first_sequence=1,
            last_sequence=10,
            created_at=now,
            signed_by="agent-1",
            signature="sig",
        )
        d = cp.to_dict()
        assert d["checkpoint_id"] == "cp-1"
        assert d["intent_id"] == "intent-1"
        assert d["merkle_root"] == "sha256:abc"
        assert d["event_count"] == 10
        assert d["created_at"] == "2026-02-12T10:00:00"
        assert d["signed_by"] == "agent-1"
        assert d["anchor"] is None

    def test_to_dict_with_anchor(self):
        anchor = TimestampAnchor(provider="ots")
        cp = LogCheckpoint(checkpoint_id="cp-1", anchor=anchor)
        d = cp.to_dict()
        assert d["anchor"] is not None
        assert d["anchor"]["provider"] == "ots"

    def test_from_dict_minimal(self):
        cp = LogCheckpoint.from_dict({"checkpoint_id": "cp-1"})
        assert cp.checkpoint_id == "cp-1"
        assert cp.scope == "intent"
        assert cp.anchor is None

    def test_from_dict_with_anchor(self):
        cp = LogCheckpoint.from_dict(
            {
                "checkpoint_id": "cp-1",
                "anchor": {
                    "type": "external-timestamp",
                    "provider": "opentimestamps",
                    "reference": "ref",
                    "timestamp_proof": "proof",
                },
            }
        )
        assert cp.anchor is not None
        assert cp.anchor.provider == "opentimestamps"

    def test_from_dict_full(self):
        cp = LogCheckpoint.from_dict(
            {
                "checkpoint_id": "cp-1",
                "intent_id": "intent-1",
                "scope": "global",
                "merkle_root": "sha256:abc",
                "event_count": 100,
                "first_sequence": 1,
                "last_sequence": 100,
                "created_at": "2026-02-12T10:00:00",
                "signed_by": "agent-1",
                "signature": "sig",
            }
        )
        assert cp.scope == "global"
        assert cp.event_count == 100
        assert cp.created_at == datetime(2026, 2, 12, 10, 0, 0)
        assert cp.signed_by == "agent-1"

    def test_roundtrip(self):
        now = datetime(2026, 2, 12, 10, 0, 0)
        anchor = TimestampAnchor(provider="ots", reference="ref")
        original = LogCheckpoint(
            checkpoint_id="cp-1",
            intent_id="intent-1",
            merkle_root="sha256:abc",
            event_count=50,
            first_sequence=1,
            last_sequence=50,
            created_at=now,
            signed_by="agent-1",
            signature="sig",
            anchor=anchor,
        )
        restored = LogCheckpoint.from_dict(original.to_dict())
        assert restored.checkpoint_id == original.checkpoint_id
        assert restored.merkle_root == original.merkle_root
        assert restored.event_count == original.event_count
        assert restored.anchor is not None
        assert restored.anchor.provider == "ots"


# ===========================================================================
# RFC-0019: Verifiable Event Logs — MerkleProofEntry
# ===========================================================================


class TestMerkleProofEntry:
    """Tests for MerkleProofEntry dataclass (RFC-0019)."""

    def test_create(self):
        entry = MerkleProofEntry(hash="sha256:abc", position="left")
        assert entry.hash == "sha256:abc"
        assert entry.position == "left"

    def test_to_dict(self):
        entry = MerkleProofEntry(hash="sha256:abc", position="right")
        d = entry.to_dict()
        assert d == {"hash": "sha256:abc", "position": "right"}

    def test_from_dict(self):
        entry = MerkleProofEntry.from_dict({"hash": "sha256:xyz", "position": "left"})
        assert entry.hash == "sha256:xyz"
        assert entry.position == "left"

    def test_from_dict_defaults(self):
        entry = MerkleProofEntry.from_dict({})
        assert entry.hash == ""
        assert entry.position == "left"


# ===========================================================================
# RFC-0019: Verifiable Event Logs — MerkleProof
# ===========================================================================


class TestMerkleProof:
    """Tests for MerkleProof dataclass (RFC-0019)."""

    def test_create_minimal(self):
        proof = MerkleProof(
            event_id="evt-1",
            event_hash="sha256:abc",
            checkpoint_id="cp-1",
            merkle_root="sha256:root",
        )
        assert proof.event_id == "evt-1"
        assert proof.proof_hashes == []
        assert proof.leaf_index == 0

    def test_create_with_proof_path(self):
        entries = [
            MerkleProofEntry(hash="sha256:sibling1", position="left"),
            MerkleProofEntry(hash="sha256:sibling2", position="right"),
        ]
        proof = MerkleProof(
            event_id="evt-1",
            event_hash="sha256:abc",
            checkpoint_id="cp-1",
            merkle_root="sha256:root",
            proof_hashes=entries,
            leaf_index=3,
        )
        assert len(proof.proof_hashes) == 2
        assert proof.leaf_index == 3

    def test_to_dict(self):
        entries = [MerkleProofEntry(hash="sha256:sib", position="left")]
        proof = MerkleProof(
            event_id="evt-1",
            event_hash="sha256:leaf",
            checkpoint_id="cp-1",
            merkle_root="sha256:root",
            proof_hashes=entries,
            leaf_index=0,
        )
        d = proof.to_dict()
        assert d["event_id"] == "evt-1"
        assert d["event_hash"] == "sha256:leaf"
        assert d["checkpoint_id"] == "cp-1"
        assert d["merkle_root"] == "sha256:root"
        assert len(d["proof_hashes"]) == 1
        assert d["proof_hashes"][0]["hash"] == "sha256:sib"
        assert d["leaf_index"] == 0

    def test_from_dict(self):
        proof = MerkleProof.from_dict(
            {
                "event_id": "evt-1",
                "event_hash": "sha256:leaf",
                "checkpoint_id": "cp-1",
                "merkle_root": "sha256:root",
                "proof_hashes": [
                    {"hash": "sha256:sib1", "position": "left"},
                    {"hash": "sha256:sib2", "position": "right"},
                ],
                "leaf_index": 2,
            }
        )
        assert proof.event_id == "evt-1"
        assert len(proof.proof_hashes) == 2
        assert proof.proof_hashes[0].position == "left"
        assert proof.leaf_index == 2

    def test_from_dict_empty(self):
        proof = MerkleProof.from_dict({})
        assert proof.event_id == ""
        assert proof.proof_hashes == []

    def test_verify_valid_proof(self):
        leaf_data = b"event-data"
        leaf_hash = hashlib.sha256(leaf_data).digest()
        sibling_data = b"sibling-data"
        sibling_hash = hashlib.sha256(sibling_data).digest()
        root_hash = hashlib.sha256(sibling_hash + leaf_hash).digest()

        leaf_b64 = base64.urlsafe_b64encode(leaf_hash).rstrip(b"=").decode()
        sibling_b64 = base64.urlsafe_b64encode(sibling_hash).rstrip(b"=").decode()
        root_b64 = base64.urlsafe_b64encode(root_hash).rstrip(b"=").decode()

        proof = MerkleProof(
            event_id="evt-1",
            event_hash=f"sha256:{leaf_b64}",
            checkpoint_id="cp-1",
            merkle_root=f"sha256:{root_b64}",
            proof_hashes=[
                MerkleProofEntry(hash=f"sha256:{sibling_b64}", position="left")
            ],
            leaf_index=1,
        )
        assert proof.verify() is True

    def test_verify_invalid_proof(self):
        proof = MerkleProof(
            event_id="evt-1",
            event_hash="sha256:invalid",
            checkpoint_id="cp-1",
            merkle_root="sha256:wrong",
            proof_hashes=[MerkleProofEntry(hash="sha256:sib", position="left")],
        )
        assert proof.verify() is False

    def test_verify_right_position(self):
        leaf_data = b"leaf"
        leaf_hash = hashlib.sha256(leaf_data).digest()
        sibling_data = b"sibling"
        sibling_hash = hashlib.sha256(sibling_data).digest()
        root_hash = hashlib.sha256(leaf_hash + sibling_hash).digest()

        leaf_b64 = base64.urlsafe_b64encode(leaf_hash).rstrip(b"=").decode()
        sibling_b64 = base64.urlsafe_b64encode(sibling_hash).rstrip(b"=").decode()
        root_b64 = base64.urlsafe_b64encode(root_hash).rstrip(b"=").decode()

        proof = MerkleProof(
            event_id="evt-1",
            event_hash=f"sha256:{leaf_b64}",
            checkpoint_id="cp-1",
            merkle_root=f"sha256:{root_b64}",
            proof_hashes=[
                MerkleProofEntry(hash=f"sha256:{sibling_b64}", position="right")
            ],
            leaf_index=0,
        )
        assert proof.verify() is True

    def test_roundtrip(self):
        entries = [
            MerkleProofEntry(hash="sha256:a", position="left"),
            MerkleProofEntry(hash="sha256:b", position="right"),
        ]
        original = MerkleProof(
            event_id="evt-1",
            event_hash="sha256:leaf",
            checkpoint_id="cp-1",
            merkle_root="sha256:root",
            proof_hashes=entries,
            leaf_index=3,
        )
        restored = MerkleProof.from_dict(original.to_dict())
        assert restored.event_id == original.event_id
        assert len(restored.proof_hashes) == 2
        assert restored.leaf_index == 3


# ===========================================================================
# RFC-0019: Verifiable Event Logs — ChainVerification
# ===========================================================================


class TestChainVerification:
    """Tests for ChainVerification dataclass (RFC-0019)."""

    def test_create_valid_chain(self):
        cv = ChainVerification(
            intent_id="intent-1",
            valid=True,
            event_count=100,
            first_sequence=1,
            last_sequence=100,
        )
        assert cv.valid is True
        assert cv.event_count == 100
        assert cv.breaks == []

    def test_create_broken_chain(self):
        cv = ChainVerification(
            intent_id="intent-1",
            valid=False,
            event_count=100,
            breaks=[{"sequence": 42, "expected_hash": "abc", "actual_hash": "xyz"}],
        )
        assert cv.valid is False
        assert len(cv.breaks) == 1
        assert cv.breaks[0]["sequence"] == 42

    def test_to_dict(self):
        cv = ChainVerification(
            intent_id="intent-1",
            valid=True,
            event_count=50,
            first_sequence=1,
            last_sequence=50,
        )
        d = cv.to_dict()
        assert d["intent_id"] == "intent-1"
        assert d["valid"] is True
        assert d["chain_valid"] is True
        assert d["event_count"] == 50
        assert d["breaks"] == []

    def test_from_dict_with_valid(self):
        cv = ChainVerification.from_dict(
            {
                "intent_id": "intent-1",
                "valid": True,
                "event_count": 50,
            }
        )
        assert cv.valid is True

    def test_from_dict_with_chain_valid_fallback(self):
        cv = ChainVerification.from_dict(
            {
                "intent_id": "intent-1",
                "chain_valid": True,
                "event_count": 50,
            }
        )
        assert cv.valid is True

    def test_from_dict_defaults(self):
        cv = ChainVerification.from_dict({})
        assert cv.intent_id == ""
        assert cv.valid is False
        assert cv.event_count == 0

    def test_roundtrip(self):
        original = ChainVerification(
            intent_id="intent-1",
            valid=False,
            event_count=100,
            first_sequence=1,
            last_sequence=100,
            breaks=[{"at": 55}],
        )
        restored = ChainVerification.from_dict(original.to_dict())
        assert restored.intent_id == original.intent_id
        assert restored.valid == original.valid
        assert restored.breaks == original.breaks


# ===========================================================================
# RFC-0019: Verifiable Event Logs — ConsistencyProof
# ===========================================================================


class TestConsistencyProof:
    """Tests for ConsistencyProof dataclass (RFC-0019)."""

    def test_create_consistent(self):
        cp = ConsistencyProof(
            from_checkpoint="cp-1",
            to_checkpoint="cp-2",
            consistent=True,
        )
        assert cp.consistent is True
        assert cp.boundary_event is None

    def test_create_inconsistent(self):
        cp = ConsistencyProof(
            from_checkpoint="cp-1",
            to_checkpoint="cp-2",
            consistent=False,
            boundary_event={"event_id": "evt-50", "issue": "hash mismatch"},
        )
        assert cp.consistent is False
        assert cp.boundary_event is not None
        assert cp.boundary_event["event_id"] == "evt-50"

    def test_to_dict(self):
        cp = ConsistencyProof(
            from_checkpoint="cp-1",
            to_checkpoint="cp-2",
            consistent=True,
        )
        d = cp.to_dict()
        assert d["from_checkpoint"] == "cp-1"
        assert d["to_checkpoint"] == "cp-2"
        assert d["consistent"] is True
        assert "boundary_event" not in d

    def test_to_dict_with_boundary(self):
        cp = ConsistencyProof(
            from_checkpoint="cp-1",
            to_checkpoint="cp-2",
            consistent=False,
            boundary_event={"event_id": "evt-50"},
        )
        d = cp.to_dict()
        assert d["boundary_event"]["event_id"] == "evt-50"

    def test_from_dict(self):
        cp = ConsistencyProof.from_dict(
            {
                "from_checkpoint": "cp-1",
                "to_checkpoint": "cp-2",
                "consistent": True,
            }
        )
        assert cp.from_checkpoint == "cp-1"
        assert cp.consistent is True

    def test_from_dict_defaults(self):
        cp = ConsistencyProof.from_dict({})
        assert cp.from_checkpoint == ""
        assert cp.to_checkpoint == ""
        assert cp.consistent is False
        assert cp.boundary_event is None

    def test_roundtrip(self):
        original = ConsistencyProof(
            from_checkpoint="cp-1",
            to_checkpoint="cp-2",
            consistent=False,
            boundary_event={"event_id": "evt-50"},
        )
        restored = ConsistencyProof.from_dict(original.to_dict())
        assert restored.from_checkpoint == original.from_checkpoint
        assert restored.to_checkpoint == original.to_checkpoint
        assert restored.consistent == original.consistent
        assert restored.boundary_event == original.boundary_event


# ===========================================================================
# RFC-0018/0019/0020: IntentEvent — Extended fields
# ===========================================================================


class TestIntentEventExtendedFields:
    """Tests for IntentEvent trace/proof/hash fields (RFC-0018, 0019, 0020)."""

    def _make_event(self, **kwargs: Any) -> IntentEvent:
        defaults = {
            "id": "evt-1",
            "intent_id": "intent-1",
            "event_type": EventType.STATE_PATCHED,
            "actor": "agent-1",
            "payload": {"key": "value"},
            "created_at": datetime(2026, 2, 12, 10, 0, 0),
        }
        defaults.update(kwargs)
        return IntentEvent(**defaults)

    def test_default_extended_fields_are_none(self):
        event = self._make_event()
        assert event.proof is None
        assert event.event_hash is None
        assert event.previous_event_hash is None
        assert event.sequence is None
        assert event.trace_id is None
        assert event.parent_event_id is None

    def test_rfc0018_proof_field(self):
        proof = EventProof(
            type="Ed25519Signature2026",
            created="2026-02-12T10:00:00Z",
            verification_method="did:key:z6MkTest",
            signature="sig-base64",
        )
        event = self._make_event(proof=proof)
        assert event.proof is not None
        assert event.proof.type == "Ed25519Signature2026"

    def test_rfc0019_hash_chain_fields(self):
        event = self._make_event(
            event_hash="sha256:abc",
            previous_event_hash="sha256:xyz",
            sequence=42,
        )
        assert event.event_hash == "sha256:abc"
        assert event.previous_event_hash == "sha256:xyz"
        assert event.sequence == 42

    def test_rfc0020_tracing_fields(self):
        event = self._make_event(
            trace_id="trace-abc123",
            parent_event_id="evt-parent",
        )
        assert event.trace_id == "trace-abc123"
        assert event.parent_event_id == "evt-parent"

    def test_to_dict_includes_proof(self):
        proof = EventProof(signature="sig")
        event = self._make_event(proof=proof)
        d = event.to_dict()
        assert "proof" in d
        assert d["proof"]["signature"] == "sig"

    def test_to_dict_excludes_none_proof(self):
        event = self._make_event()
        d = event.to_dict()
        assert "proof" not in d

    def test_to_dict_includes_hash_chain(self):
        event = self._make_event(
            event_hash="sha256:abc",
            previous_event_hash="sha256:xyz",
            sequence=5,
        )
        d = event.to_dict()
        assert d["event_hash"] == "sha256:abc"
        assert d["previous_event_hash"] == "sha256:xyz"
        assert d["sequence"] == 5

    def test_to_dict_excludes_none_hash_chain(self):
        event = self._make_event()
        d = event.to_dict()
        assert "event_hash" not in d
        assert "previous_event_hash" not in d
        assert "sequence" not in d

    def test_to_dict_includes_tracing(self):
        event = self._make_event(
            trace_id="trace-abc",
            parent_event_id="evt-parent",
        )
        d = event.to_dict()
        assert d["trace_id"] == "trace-abc"
        assert d["parent_event_id"] == "evt-parent"

    def test_to_dict_excludes_none_tracing(self):
        event = self._make_event()
        d = event.to_dict()
        assert "trace_id" not in d
        assert "parent_event_id" not in d

    def test_to_dict_all_extended_fields(self):
        proof = EventProof(signature="sig")
        event = self._make_event(
            proof=proof,
            event_hash="sha256:abc",
            previous_event_hash="sha256:xyz",
            sequence=10,
            trace_id="trace-id",
            parent_event_id="parent-id",
        )
        d = event.to_dict()
        assert d["proof"]["signature"] == "sig"
        assert d["event_hash"] == "sha256:abc"
        assert d["trace_id"] == "trace-id"
        assert d["parent_event_id"] == "parent-id"
        assert d["sequence"] == 10

    def test_from_dict_with_proof(self):
        event = IntentEvent.from_dict(
            {
                "id": "evt-1",
                "intent_id": "intent-1",
                "event_type": "state_patched",
                "payload": {},
                "created_at": "2026-02-12T10:00:00",
                "proof": {
                    "type": "Ed25519Signature2026",
                    "signature": "sig-data",
                },
            }
        )
        assert event.proof is not None
        assert event.proof.signature == "sig-data"

    def test_from_dict_with_hash_chain(self):
        event = IntentEvent.from_dict(
            {
                "id": "evt-1",
                "intent_id": "intent-1",
                "event_type": "state_patched",
                "payload": {},
                "created_at": "2026-02-12T10:00:00",
                "event_hash": "sha256:abc",
                "previous_event_hash": "sha256:xyz",
                "sequence": 42,
            }
        )
        assert event.event_hash == "sha256:abc"
        assert event.previous_event_hash == "sha256:xyz"
        assert event.sequence == 42

    def test_from_dict_with_tracing(self):
        event = IntentEvent.from_dict(
            {
                "id": "evt-1",
                "intent_id": "intent-1",
                "event_type": "state_patched",
                "payload": {},
                "created_at": "2026-02-12T10:00:00",
                "trace_id": "trace-abc123",
                "parent_event_id": "evt-parent",
            }
        )
        assert event.trace_id == "trace-abc123"
        assert event.parent_event_id == "evt-parent"

    def test_roundtrip_all_extended(self):
        proof = EventProof(
            type="Ed25519Signature2026",
            created="2026-02-12T10:00:00Z",
            verification_method="did:key:z6Mk",
            signature="sig",
        )
        event = self._make_event(
            proof=proof,
            event_hash="sha256:abc",
            previous_event_hash="sha256:xyz",
            sequence=10,
            trace_id="trace-id",
            parent_event_id="parent-id",
        )
        d = event.to_dict()
        restored = IntentEvent.from_dict(d)
        assert restored.proof is not None
        assert restored.proof.signature == "sig"
        assert restored.event_hash == "sha256:abc"
        assert restored.previous_event_hash == "sha256:xyz"
        assert restored.sequence == 10
        assert restored.trace_id == "trace-id"
        assert restored.parent_event_id == "parent-id"


# ===========================================================================
# RFC-0018: Workflow — IdentityConfig
# ===========================================================================


class TestIdentityConfig:
    """Tests for IdentityConfig workflow dataclass (RFC-0018)."""

    def test_defaults(self):
        from openintent.workflow import IdentityConfig

        config = IdentityConfig()
        assert config.enabled is False
        assert config.key_path is None
        assert config.auto_register is True
        assert config.auto_sign is True
        assert config.key_algorithm == "Ed25519"
        assert config.key_expires is None

    def test_from_dict_full(self):
        from openintent.workflow import IdentityConfig

        config = IdentityConfig.from_dict(
            {
                "enabled": True,
                "key_path": "/keys/agent.pem",
                "auto_register": False,
                "auto_sign": True,
                "key_algorithm": "Ed25519",
                "key_expires": "2027-01-01",
            }
        )
        assert config.enabled is True
        assert config.key_path == "/keys/agent.pem"
        assert config.auto_register is False
        assert config.key_expires == "2027-01-01"

    def test_from_dict_boolean_shorthand(self):
        from openintent.workflow import IdentityConfig

        config = IdentityConfig.from_dict(True)
        assert config.enabled is True
        assert config.auto_register is True

    def test_from_dict_boolean_shorthand_false(self):
        from openintent.workflow import IdentityConfig

        config = IdentityConfig.from_dict(False)
        assert config.enabled is False

    def test_from_dict_empty_defaults_to_enabled(self):
        from openintent.workflow import IdentityConfig

        config = IdentityConfig.from_dict({})
        assert config.enabled is True
        assert config.auto_register is True
