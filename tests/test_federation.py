"""
Comprehensive tests for the OpenIntent Federation module (RFC-0022 & RFC-0023).

Covers: models serialization, security (sign/verify, UCAN, SSRF, trust),
server endpoints, client methods, decorators, and integration flows.
"""

import uuid

import pytest

from openintent.federation.decorators import (
    Federation,
    on_budget_warning,
    on_federation_callback,
    on_federation_received,
)
from openintent.federation.models import (
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
from openintent.federation.security import (
    MessageSignature,
    ServerIdentity,
    TrustEnforcer,
    UCANToken,
    _canonical_bytes,
    resolve_did_web,
    sign_envelope,
    validate_ssrf,
)
from openintent.models import EventType


class TestAgentVisibility:
    def test_values(self):
        assert AgentVisibility.PUBLIC == "public"
        assert AgentVisibility.UNLISTED == "unlisted"
        assert AgentVisibility.PRIVATE == "private"

    def test_from_string(self):
        assert AgentVisibility("public") == AgentVisibility.PUBLIC
        assert AgentVisibility("unlisted") == AgentVisibility.UNLISTED


class TestPeerRelationship:
    def test_values(self):
        assert PeerRelationship.PEER == "peer"
        assert PeerRelationship.UPSTREAM == "upstream"
        assert PeerRelationship.DOWNSTREAM == "downstream"


class TestTrustPolicy:
    def test_values(self):
        assert TrustPolicy.OPEN == "open"
        assert TrustPolicy.ALLOWLIST == "allowlist"
        assert TrustPolicy.TRUSTLESS == "trustless"


class TestDelegationScope:
    def test_defaults(self):
        scope = DelegationScope()
        assert "state.patch" in scope.permissions
        assert "events.log" in scope.permissions
        assert scope.denied_operations == []
        assert scope.max_delegation_depth == 1

    def test_roundtrip(self):
        scope = DelegationScope(
            permissions=["state.patch", "tools.invoke"],
            denied_operations=["intent.delete"],
            max_delegation_depth=3,
            expires_at="2026-12-31T23:59:59Z",
        )
        d = scope.to_dict()
        restored = DelegationScope.from_dict(d)
        assert restored.permissions == scope.permissions
        assert restored.denied_operations == scope.denied_operations
        assert restored.max_delegation_depth == 3
        assert restored.expires_at == "2026-12-31T23:59:59Z"

    def test_attenuate(self):
        parent = DelegationScope(
            permissions=["state.patch", "tools.invoke", "events.log"],
            max_delegation_depth=3,
        )
        child = DelegationScope(
            permissions=["state.patch", "events.log"],
            denied_operations=["tools.invoke"],
            max_delegation_depth=5,
        )
        result = parent.attenuate(child)
        assert "state.patch" in result.permissions
        assert "events.log" in result.permissions
        assert "tools.invoke" not in result.permissions
        assert "tools.invoke" in result.denied_operations
        assert result.max_delegation_depth == 2

    def test_attenuate_depth_narrows(self):
        parent = DelegationScope(max_delegation_depth=1)
        child = DelegationScope(max_delegation_depth=10)
        result = parent.attenuate(child)
        assert result.max_delegation_depth == 0


class TestFederationPolicy:
    def test_defaults(self):
        policy = FederationPolicy()
        assert policy.governance == {}
        assert policy.budget == {}
        assert policy.observability == {}

    def test_roundtrip(self):
        policy = FederationPolicy(
            governance={"max_delegation_depth": 2, "require_approval": True},
            budget={"max_llm_tokens": 50000, "cost_ceiling_usd": 10.0},
            observability={"report_frequency": "on_state_change"},
        )
        d = policy.to_dict()
        restored = FederationPolicy.from_dict(d)
        assert restored.governance["max_delegation_depth"] == 2
        assert restored.budget["cost_ceiling_usd"] == 10.0
        assert restored.observability["report_frequency"] == "on_state_change"

    def test_compose_strictest_numeric(self):
        p1 = FederationPolicy(
            governance={"max_delegation_depth": 3},
            budget={"max_llm_tokens": 100000},
        )
        p2 = FederationPolicy(
            governance={"max_delegation_depth": 1},
            budget={"max_llm_tokens": 50000},
        )
        result = p1.compose_strictest(p2)
        assert result.governance["max_delegation_depth"] == 1
        assert result.budget["max_llm_tokens"] == 50000

    def test_compose_strictest_boolean(self):
        p1 = FederationPolicy(governance={"require_approval": False})
        p2 = FederationPolicy(governance={"require_approval": True})
        result = p1.compose_strictest(p2)
        assert result.governance["require_approval"] is True

    def test_compose_strictest_new_keys(self):
        p1 = FederationPolicy(governance={"key_a": "value_a"})
        p2 = FederationPolicy(governance={"key_b": "value_b"})
        result = p1.compose_strictest(p2)
        assert result.governance["key_a"] == "value_a"
        assert result.governance["key_b"] == "value_b"


class TestFederationAttestation:
    def test_roundtrip(self):
        att = FederationAttestation(
            dispatch_id="dispatch-123",
            governance_compliant=True,
            usage={"llm_tokens": 5000, "tool_calls": 3},
            trace_references=["trace-abc", "trace-def"],
            timestamp="2026-01-01T00:00:00Z",
            signature="sig123",
        )
        d = att.to_dict()
        restored = FederationAttestation.from_dict(d)
        assert restored.dispatch_id == "dispatch-123"
        assert restored.governance_compliant is True
        assert restored.usage["llm_tokens"] == 5000
        assert len(restored.trace_references) == 2

    def test_defaults(self):
        att = FederationAttestation(dispatch_id="d1")
        assert att.governance_compliant is True
        assert att.usage == {}
        assert att.signature is None


class TestFederationEnvelope:
    def test_minimal_roundtrip(self):
        env = FederationEnvelope(
            dispatch_id="d-1",
            source_server="https://server-a.com",
            target_server="https://server-b.com",
            intent_id="intent-1",
            intent_title="Test Intent",
        )
        d = env.to_dict()
        assert d["dispatch_id"] == "d-1"
        assert d["source_server"] == "https://server-a.com"
        assert "delegation_scope" not in d
        restored = FederationEnvelope.from_dict(d)
        assert restored.intent_id == "intent-1"
        assert restored.delegation_scope is None

    def test_full_roundtrip(self):
        env = FederationEnvelope(
            dispatch_id="d-2",
            source_server="https://a.com",
            target_server="https://b.com",
            intent_id="i-2",
            intent_title="Full Test",
            intent_description="A complete test",
            intent_state={"key": "value"},
            intent_constraints={"max_cost": 100},
            agent_id="agent-1",
            delegation_scope=DelegationScope(permissions=["state.patch"]),
            federation_policy=FederationPolicy(budget={"max_llm_tokens": 1000}),
            trace_context={"trace_id": "t-1", "span_id": "s-1"},
            callback_url="https://a.com/callback",
            idempotency_key="idem-1",
            created_at="2026-01-01T00:00:00Z",
            signature="sig-abc",
        )
        d = env.to_dict()
        restored = FederationEnvelope.from_dict(d)
        assert restored.agent_id == "agent-1"
        assert restored.delegation_scope.permissions == ["state.patch"]
        assert restored.federation_policy.budget["max_llm_tokens"] == 1000
        assert restored.trace_context["trace_id"] == "t-1"
        assert restored.callback_url == "https://a.com/callback"
        assert restored.signature == "sig-abc"


class TestFederationCallback:
    def test_roundtrip(self):
        cb = FederationCallback(
            dispatch_id="d-1",
            event_type=CallbackEventType.STATE_DELTA,
            state_delta={"progress": 0.5},
            attestation=FederationAttestation(dispatch_id="d-1"),
            trace_id="t-1",
            idempotency_key="cb-idem-1",
            timestamp="2026-01-01T00:00:00Z",
        )
        d = cb.to_dict()
        restored = FederationCallback.from_dict(d)
        assert restored.event_type == CallbackEventType.STATE_DELTA
        assert restored.state_delta["progress"] == 0.5
        assert restored.attestation.dispatch_id == "d-1"
        assert restored.trace_id == "t-1"


class TestPeerInfo:
    def test_roundtrip(self):
        peer = PeerInfo(
            server_url="https://peer.example.com",
            server_did="did:web:peer.example.com",
            relationship=PeerRelationship.UPSTREAM,
            trust_policy=TrustPolicy.ALLOWLIST,
            public_key="pk-abc",
        )
        d = peer.to_dict()
        restored = PeerInfo.from_dict(d)
        assert restored.server_url == "https://peer.example.com"
        assert restored.relationship == PeerRelationship.UPSTREAM


class TestFederationManifest:
    def test_roundtrip(self):
        manifest = FederationManifest(
            server_did="did:web:my-server.com",
            server_url="https://my-server.com",
            trust_policy=TrustPolicy.OPEN,
            visibility_default=AgentVisibility.UNLISTED,
            peers=["did:web:peer.com"],
            public_key="pk-xyz",
        )
        d = manifest.to_dict()
        restored = FederationManifest.from_dict(d)
        assert restored.server_did == "did:web:my-server.com"
        assert restored.trust_policy == TrustPolicy.OPEN
        assert restored.visibility_default == AgentVisibility.UNLISTED
        assert "RFC-0022" in restored.supported_rfcs


class TestFederationStatus:
    def test_roundtrip(self):
        status = FederationStatus(
            enabled=True,
            server_did="did:web:srv.com",
            trust_policy=TrustPolicy.TRUSTLESS,
            peer_count=5,
            active_dispatches=2,
            total_dispatches=10,
            total_received=8,
        )
        d = status.to_dict()
        restored = FederationStatus.from_dict(d)
        assert restored.enabled is True
        assert restored.peer_count == 5
        assert restored.trust_policy == TrustPolicy.TRUSTLESS


class TestDispatchResult:
    def test_roundtrip(self):
        result = DispatchResult(
            dispatch_id="d-1",
            status=DispatchStatus.ACCEPTED,
            target_server="https://target.com",
            message="Dispatch initiated",
            remote_intent_id="remote-i-1",
        )
        d = result.to_dict()
        restored = DispatchResult.from_dict(d)
        assert restored.status == DispatchStatus.ACCEPTED
        assert restored.remote_intent_id == "remote-i-1"


class TestReceiveResult:
    def test_roundtrip(self):
        result = ReceiveResult(
            dispatch_id="d-1",
            accepted=True,
            local_intent_id="local-i-1",
            message="Accepted",
        )
        d = result.to_dict()
        restored = ReceiveResult.from_dict(d)
        assert restored.accepted is True
        assert restored.local_intent_id == "local-i-1"


class TestFederatedAgent:
    def test_roundtrip(self):
        agent = FederatedAgent(
            agent_id="researcher-01",
            server_url="https://server.com",
            capabilities=["research", "analysis"],
            visibility=AgentVisibility.PUBLIC,
            server_did="did:web:server.com",
        )
        d = agent.to_dict()
        restored = FederatedAgent.from_dict(d)
        assert restored.agent_id == "researcher-01"
        assert "research" in restored.capabilities
        assert restored.visibility == AgentVisibility.PUBLIC


class TestFederationEventTypes:
    def test_event_types_exist(self):
        assert EventType.FEDERATION_DISPATCHED == "federation.dispatched"
        assert EventType.FEDERATION_RECEIVED == "federation.received"
        assert EventType.FEDERATION_CALLBACK == "federation.callback"
        assert EventType.FEDERATION_BUDGET_WARNING == "federation.budget_warning"
        assert EventType.FEDERATION_COMPLETED == "federation.completed"
        assert EventType.FEDERATION_FAILED == "federation.failed"


class TestServerIdentity:
    def test_generate(self):
        identity = ServerIdentity.generate("https://my-server.com")
        assert identity.did == "did:web:my-server.com"
        assert identity.private_key_bytes is not None
        assert identity.public_key_bytes is not None
        assert len(identity.public_key_b64) > 0

    def test_did_from_url(self):
        identity = ServerIdentity(server_url="https://agents.acme.com")
        assert identity.did == "did:web:agents.acme.com"

    def test_did_document(self):
        identity = ServerIdentity.generate("https://example.com")
        doc = identity.did_document()
        assert doc["id"] == "did:web:example.com"
        assert len(doc["verificationMethod"]) == 1
        assert doc["verificationMethod"][0]["type"] == "Ed25519VerificationKey2020"

    def test_sign_and_verify(self):
        identity = ServerIdentity.generate("https://test.com")
        message = b"test message"
        signature = identity.sign(message)
        assert identity.verify(message, signature)

    def test_verify_wrong_message(self):
        identity = ServerIdentity.generate("https://test.com")
        signature = identity.sign(b"correct message")
        assert not identity.verify(b"wrong message", signature)

    def test_verify_invalid_signature(self):
        identity = ServerIdentity.generate("https://test.com")
        assert not identity.verify(b"test", "invalid_base64!!!")

    def test_sign_no_key_raises(self):
        identity = ServerIdentity(server_url="https://test.com")
        with pytest.raises(ValueError, match="No private key"):
            identity.sign(b"test")


class TestSignEnvelope:
    def test_sign_and_verify(self):
        identity = ServerIdentity.generate("https://signing-server.com")
        envelope = {
            "dispatch_id": "d-1",
            "source_server": "https://signing-server.com",
            "target_server": "https://target.com",
            "intent_id": "i-1",
        }
        signature = sign_envelope(identity, envelope)
        assert len(signature) > 0

        assert identity.verify(
            _canonical_bytes(envelope),
            signature,
        )

    def test_signature_excludes_signature_field(self):
        identity = ServerIdentity.generate("https://test.com")
        envelope = {"a": 1, "b": 2}
        sig1 = sign_envelope(identity, envelope)
        envelope_with_sig = {**envelope, "signature": "old-sig"}
        sig2 = sign_envelope(identity, envelope_with_sig)
        assert sig1 == sig2


class TestCanonicalBytes:
    def test_deterministic(self):
        d1 = {"b": 2, "a": 1}
        d2 = {"a": 1, "b": 2}
        assert _canonical_bytes(d1) == _canonical_bytes(d2)

    def test_excludes_signature(self):
        d1 = {"a": 1}
        d2 = {"a": 1, "signature": "sig"}
        assert _canonical_bytes(d1) == _canonical_bytes(d2)


class TestMessageSignature:
    def test_create(self):
        identity = ServerIdentity.generate("https://test.com")
        sig = MessageSignature.create(
            identity=identity,
            method="POST",
            target_uri="https://target.com/api/v1/federation/receive",
            body=b'{"dispatch_id": "d-1"}',
        )
        assert sig.key_id == "did:web:test.com"
        assert sig.algorithm == "ed25519"
        assert len(sig.signature) > 0

    def test_to_header(self):
        sig = MessageSignature(key_id="did:web:test.com")
        header = sig.to_header()
        assert "did:web:test.com" in header
        assert "ed25519" in header


class TestTrustEnforcer:
    def test_open_trusts_everything(self):
        enforcer = TrustEnforcer(policy=TrustPolicy.OPEN)
        assert enforcer.is_trusted("https://unknown.com")
        assert enforcer.is_trusted("https://anything.com", "did:web:anything.com")

    def test_allowlist_allows_listed(self):
        enforcer = TrustEnforcer(
            policy=TrustPolicy.ALLOWLIST,
            allowed_peers=["https://peer-a.com", "did:web:peer-b.com"],
        )
        assert enforcer.is_trusted("https://peer-a.com")
        assert enforcer.is_trusted("https://other.com", "did:web:peer-b.com")
        assert not enforcer.is_trusted("https://unknown.com")

    def test_allowlist_add_remove(self):
        enforcer = TrustEnforcer(policy=TrustPolicy.ALLOWLIST)
        assert not enforcer.is_trusted("https://new-peer.com")
        enforcer.add_peer("https://new-peer.com")
        assert enforcer.is_trusted("https://new-peer.com")
        enforcer.remove_peer("https://new-peer.com")
        assert not enforcer.is_trusted("https://new-peer.com")

    def test_trustless_rejects_all(self):
        enforcer = TrustEnforcer(policy=TrustPolicy.TRUSTLESS)
        assert not enforcer.is_trusted("https://any.com")
        assert not enforcer.is_trusted("https://any.com", "did:web:any.com")


class TestUCANToken:
    def test_create_and_encode(self):
        identity = ServerIdentity.generate("https://issuer.com")
        token = UCANToken(
            issuer="did:web:issuer.com",
            audience="did:web:audience.com",
            scope=DelegationScope(permissions=["state.patch"]),
        )
        encoded = token.encode(identity)
        assert len(encoded.split(".")) == 3

    def test_decode(self):
        identity = ServerIdentity.generate("https://issuer.com")
        original = UCANToken(
            issuer="did:web:issuer.com",
            audience="did:web:audience.com",
            scope=DelegationScope(
                permissions=["state.patch", "events.log"],
                max_delegation_depth=2,
            ),
        )
        encoded = original.encode(identity)
        decoded = UCANToken.decode(encoded)
        assert decoded.issuer == "did:web:issuer.com"
        assert decoded.audience == "did:web:audience.com"
        assert "state.patch" in decoded.scope.permissions

    def test_decode_invalid_format(self):
        with pytest.raises(ValueError, match="Invalid UCAN"):
            UCANToken.decode("not.a-valid-token")

    def test_is_active(self):
        import time

        token = UCANToken(
            issuer="a",
            audience="b",
            scope=DelegationScope(),
            not_before=int(time.time()) - 10,
            expires_at=int(time.time()) + 3600,
        )
        assert token.is_active()
        assert not token.is_expired()

    def test_is_expired(self):
        token = UCANToken(
            issuer="a",
            audience="b",
            scope=DelegationScope(),
            not_before=1000,
            expires_at=1001,
        )
        assert token.is_expired()
        assert not token.is_active()

    def test_attenuate(self):
        identity = ServerIdentity.generate("https://a.com")
        parent = UCANToken(
            issuer="did:web:a.com",
            audience="did:web:b.com",
            scope=DelegationScope(
                permissions=["state.patch", "tools.invoke", "events.log"],
                max_delegation_depth=3,
            ),
        )
        child_scope = DelegationScope(
            permissions=["state.patch"],
            max_delegation_depth=2,
        )
        child = parent.attenuate("did:web:c.com", child_scope, identity)
        assert child.issuer == "did:web:b.com"
        assert child.audience == "did:web:c.com"
        assert "state.patch" in child.scope.permissions
        assert "tools.invoke" not in child.scope.permissions
        assert child.scope.max_delegation_depth == 2
        assert len(child.proof_chain) == 1

    def test_attenuate_depth_exceeded(self):
        identity = ServerIdentity.generate("https://a.com")
        parent = UCANToken(
            issuer="did:web:a.com",
            audience="did:web:b.com",
            scope=DelegationScope(max_delegation_depth=0),
        )
        child_scope = DelegationScope(max_delegation_depth=1)
        with pytest.raises(ValueError, match="Delegation depth exceeded"):
            parent.attenuate("did:web:c.com", child_scope, identity)


class TestResolveDIDWeb:
    def test_basic(self):
        url = resolve_did_web("did:web:example.com")
        assert url == "https://example.com/.well-known/did.json"

    def test_with_path(self):
        url = resolve_did_web("did:web:example.com:users:alice")
        assert url == "https://example.com/users/alice/.well-known/did.json"

    def test_invalid_prefix(self):
        with pytest.raises(ValueError, match="Not a did:web"):
            resolve_did_web("did:key:z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK")


class TestValidateSSRF:
    def test_valid_url(self):
        assert validate_ssrf("https://api.example.com/callback")
        assert validate_ssrf("https://federation.partner.org/receive")

    def test_localhost_blocked(self):
        assert not validate_ssrf("http://localhost:8080/callback")
        assert not validate_ssrf("http://127.0.0.1/callback")
        assert not validate_ssrf("http://0.0.0.0/callback")

    def test_private_networks_blocked(self):
        assert not validate_ssrf("http://10.0.0.1/callback")
        assert not validate_ssrf("http://192.168.1.1/callback")
        assert not validate_ssrf("http://172.16.0.1/callback")

    def test_metadata_blocked(self):
        assert not validate_ssrf("http://169.254.169.254/latest/meta-data")
        assert not validate_ssrf("http://metadata.google.internal/computeMetadata")

    def test_internal_domains_blocked(self):
        assert not validate_ssrf("http://service.internal/callback")
        assert not validate_ssrf("http://host.local/callback")

    def test_invalid_scheme(self):
        assert not validate_ssrf("ftp://example.com/file")
        assert not validate_ssrf("file:///etc/passwd")

    def test_no_hostname(self):
        assert not validate_ssrf("http:///path")


class TestDecoratorLifecycleHooks:
    def test_on_federation_received(self):
        @on_federation_received
        async def handler(self, intent, context):
            pass

        assert handler._openintent_handler == "federation_received"

    def test_on_federation_callback(self):
        @on_federation_callback
        async def handler(self, dispatch_id, attestation):
            pass

        assert handler._openintent_handler == "federation_callback"

    def test_on_budget_warning(self):
        @on_budget_warning
        async def handler(self, dispatch_id, usage):
            pass

        assert handler._openintent_handler == "budget_warning"


class TestFederationDecorator:
    def test_decorator_configures_class(self):
        @Federation(
            identity="did:web:test.example.com",
            visibility_default="public",
            trust_policy="allowlist",
            peers=["did:web:peer.com"],
            server_url="https://test.example.com",
        )
        class TestFederation:
            pass

        assert TestFederation._federation_configured is True
        assert TestFederation._federation_trust_policy_name == "allowlist"
        assert TestFederation._federation_visibility_default_name == "public"
        assert "did:web:peer.com" in TestFederation._federation_peer_list

    def test_decorator_sets_identity_on_init(self):
        @Federation(
            identity="did:web:init-test.com",
            server_url="https://init-test.com",
        )
        class TestFed:
            pass

        instance = TestFed()
        assert instance._federation_identity.did == "did:web:init-test.com"
        assert instance._federation_trust_policy == TrustPolicy.ALLOWLIST
        assert instance._federation_visibility_default == AgentVisibility.PUBLIC


class TestAgentFederationVisibility:
    def test_agent_stores_federation_visibility(self):
        from openintent.agents import Agent, on_assignment

        @Agent(
            agent_id="test-fed-agent",
            federation_visibility="public",
        )
        class TestAgent:
            @on_assignment
            async def handle(self, intent):
                return {}

        instance = TestAgent.__new__(TestAgent)
        instance.__init__()
        assert instance._federation_visibility == "public"

    def test_agent_default_none(self):
        from openintent.agents import Agent, on_assignment

        @Agent(agent_id="test-no-fed")
        class TestAgent:
            @on_assignment
            async def handle(self, intent):
                return {}

        instance = TestAgent.__new__(TestAgent)
        instance.__init__()
        assert instance._federation_visibility is None


class TestCoordinatorFederationPolicy:
    def test_coordinator_stores_federation_policy(self):
        from openintent.agents import Coordinator

        @Coordinator(
            coordinator_id="test-fed-coord",
            federation_visibility="unlisted",
            federation_policy={"budget": {"max_llm_tokens": 50000}},
        )
        class TestCoord:
            pass

        instance = TestCoord.__new__(TestCoord)
        instance.__init__()
        assert instance._federation_visibility == "unlisted"
        assert instance._federation_policy["budget"]["max_llm_tokens"] == 50000


class TestServerEndpoints:
    @pytest.fixture
    def client(self):
        from openintent.server.app import create_app
        from openintent.server.config import ServerConfig
        from openintent.server.federation import (
            configure_federation,
            get_federation_state,
        )

        config = ServerConfig(database_url="sqlite:///./test_federation.db")
        app = create_app(config)

        from fastapi.testclient import TestClient

        with TestClient(app) as tc:
            configure_federation(
                server_url="https://test-server.com",
                server_did="did:web:test-server.com",
                trust_policy=TrustPolicy.OPEN,
                peers=["https://trusted-peer.com"],
            )

            state = get_federation_state()
            state.register_agent(
                "researcher-01",
                capabilities=["research", "analysis"],
                visibility=AgentVisibility.PUBLIC,
            )
            state.register_agent(
                "internal-bot",
                capabilities=["internal"],
                visibility=AgentVisibility.PRIVATE,
            )

            yield tc

    def test_federation_discovery(self, client):
        response = client.get("/.well-known/openintent-federation.json")
        assert response.status_code == 200
        data = response.json()
        assert data["server_did"] == "did:web:test-server.com"
        assert data["trust_policy"] == "open"
        assert "dispatch" in data["endpoints"]

    def test_did_document(self, client):
        response = client.get("/.well-known/did.json")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "did:web:test-server.com"
        assert len(data["verificationMethod"]) == 1

    def test_federation_status(self, client):
        response = client.get(
            "/api/v1/federation/status",
            headers={"X-API-Key": "dev-user-key"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is True
        assert data["server_did"] == "did:web:test-server.com"
        assert data["trust_policy"] == "open"

    def test_federation_agents_public(self, client):
        response = client.get(
            "/api/v1/federation/agents",
            headers={"X-API-Key": "dev-user-key"},
        )
        assert response.status_code == 200
        agents = response.json()["agents"]
        agent_ids = [a["agent_id"] for a in agents]
        assert "researcher-01" in agent_ids
        assert "internal-bot" not in agent_ids

    def test_federation_dispatch(self, client):
        response = client.post(
            "/api/v1/federation/dispatch",
            json={
                "intent_id": "intent-123",
                "target_server": "https://remote-server.com",
                "agent_id": "remote-agent",
                "delegation_scope": {
                    "permissions": ["state.patch"],
                    "max_delegation_depth": 1,
                },
            },
            headers={"X-API-Key": "dev-user-key"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "accepted"
        assert len(data["dispatch_id"]) > 0

    def test_federation_dispatch_ssrf_blocked(self, client):
        response = client.post(
            "/api/v1/federation/dispatch",
            json={
                "intent_id": "intent-123",
                "target_server": "http://localhost:8080",
            },
            headers={"X-API-Key": "dev-user-key"},
        )
        assert response.status_code == 400
        assert "SSRF" in response.json()["detail"]

    def test_federation_dispatch_callback_ssrf_blocked(self, client):
        response = client.post(
            "/api/v1/federation/dispatch",
            json={
                "intent_id": "intent-123",
                "target_server": "https://valid-server.com",
                "callback_url": "http://169.254.169.254/metadata",
            },
            headers={"X-API-Key": "dev-user-key"},
        )
        assert response.status_code == 400
        assert "SSRF" in response.json()["detail"]

    def test_federation_receive(self, client):
        response = client.post(
            "/api/v1/federation/receive",
            json={
                "dispatch_id": str(uuid.uuid4()),
                "source_server": "https://trusted-peer.com",
                "intent_id": "remote-intent-1",
                "intent_title": "Remote Task",
                "intent_description": "Do something remotely",
                "intent_state": {"key": "value"},
                "agent_id": "researcher-01",
            },
            headers={"X-API-Key": "dev-user-key"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["accepted"] is True
        assert data["local_intent_id"] is not None

    def test_federation_receive_idempotency(self, client):
        dispatch_id = str(uuid.uuid4())
        idempotency_key = "idem-test-1"

        response1 = client.post(
            "/api/v1/federation/receive",
            json={
                "dispatch_id": dispatch_id,
                "source_server": "https://trusted-peer.com",
                "intent_id": "i-1",
                "intent_title": "Test",
                "idempotency_key": idempotency_key,
            },
            headers={"X-API-Key": "dev-user-key"},
        )
        assert response1.status_code == 200

        response2 = client.post(
            "/api/v1/federation/receive",
            json={
                "dispatch_id": dispatch_id,
                "source_server": "https://trusted-peer.com",
                "intent_id": "i-1",
                "intent_title": "Test",
                "idempotency_key": idempotency_key,
            },
            headers={"X-API-Key": "dev-user-key"},
        )
        assert response2.status_code == 200
        assert "idempotent" in response2.json()["message"].lower()

    def test_federation_receive_budget_rejection(self, client):
        response = client.post(
            "/api/v1/federation/receive",
            json={
                "dispatch_id": str(uuid.uuid4()),
                "source_server": "https://trusted-peer.com",
                "intent_id": "i-tight-budget",
                "intent_title": "Tight Budget Task",
                "federation_policy": {
                    "budget": {"max_llm_tokens": 0},
                    "governance": {},
                    "observability": {},
                },
            },
            headers={"X-API-Key": "dev-user-key"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["accepted"] is False


class TestServerEndpointsTrustEnforcement:
    @pytest.fixture
    def client(self):
        from openintent.server.app import create_app
        from openintent.server.config import ServerConfig
        from openintent.server.federation import configure_federation

        config = ServerConfig(database_url="sqlite:///./test_federation_trust.db")
        app = create_app(config)

        from fastapi.testclient import TestClient

        with TestClient(app) as tc:
            configure_federation(
                server_url="https://strict-server.com",
                trust_policy=TrustPolicy.ALLOWLIST,
                peers=["https://allowed-peer.com"],
            )

            yield tc

    def test_receive_from_untrusted_rejected(self, client):
        response = client.post(
            "/api/v1/federation/receive",
            json={
                "dispatch_id": str(uuid.uuid4()),
                "source_server": "https://untrusted-server.com",
                "intent_id": "i-1",
                "intent_title": "Test",
            },
            headers={"X-API-Key": "dev-user-key"},
        )
        assert response.status_code == 403
        assert "not trusted" in response.json()["detail"]

    def test_receive_from_trusted_accepted(self, client):
        response = client.post(
            "/api/v1/federation/receive",
            json={
                "dispatch_id": str(uuid.uuid4()),
                "source_server": "https://allowed-peer.com",
                "intent_id": "i-1",
                "intent_title": "Test",
            },
            headers={"X-API-Key": "dev-user-key"},
        )
        assert response.status_code == 200
        assert response.json()["accepted"] is True


class TestFederationDisabledEndpoints:
    @pytest.fixture
    def client(self):
        from openintent.server.app import create_app
        from openintent.server.config import ServerConfig
        from openintent.server.federation import get_federation_state

        config = ServerConfig(database_url="sqlite:///./test_federation_disabled.db")
        app = create_app(config)

        from fastapi.testclient import TestClient

        with TestClient(app) as tc:
            state = get_federation_state()
            state.enabled = False
            state.identity = None
            state.manifest = None

            yield tc

    def test_discovery_404_when_disabled(self, client):
        response = client.get("/.well-known/openintent-federation.json")
        assert response.status_code == 404

    def test_status_shows_disabled(self, client):
        response = client.get(
            "/api/v1/federation/status",
            headers={"X-API-Key": "dev-user-key"},
        )
        assert response.status_code == 200
        assert response.json()["enabled"] is False

    def test_dispatch_fails_when_disabled(self, client):
        response = client.post(
            "/api/v1/federation/dispatch",
            json={
                "intent_id": "i-1",
                "target_server": "https://target.com",
            },
            headers={"X-API-Key": "dev-user-key"},
        )
        assert response.status_code == 400
