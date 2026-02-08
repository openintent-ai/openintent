"""
Tests for RFC-0011 Access Control models, enums, and agent decorators.
"""

from datetime import datetime

from openintent.agents import (
    Agent,
    AgentConfig,
    on_access_requested,
)
from openintent.models import (
    AccessPolicy,
    AccessRequest,
    AccessRequestStatus,
    ACLEntry,
    EventType,
    Intent,
    IntentACL,
    IntentContext,
    IntentState,
    IntentStatus,
    PeerInfo,
    Permission,
)


class TestPermissionEnum:
    """Tests for Permission enum values."""

    def test_read_value(self):
        assert Permission.READ.value == "read"

    def test_write_value(self):
        assert Permission.WRITE.value == "write"

    def test_admin_value(self):
        assert Permission.ADMIN.value == "admin"

    def test_from_string(self):
        assert Permission("read") == Permission.READ
        assert Permission("write") == Permission.WRITE
        assert Permission("admin") == Permission.ADMIN


class TestAccessPolicyEnum:
    """Tests for AccessPolicy enum values."""

    def test_open_value(self):
        assert AccessPolicy.OPEN.value == "open"

    def test_closed_value(self):
        assert AccessPolicy.CLOSED.value == "closed"

    def test_from_string(self):
        assert AccessPolicy("open") == AccessPolicy.OPEN
        assert AccessPolicy("closed") == AccessPolicy.CLOSED


class TestAccessRequestStatusEnum:
    """Tests for AccessRequestStatus enum values."""

    def test_pending_value(self):
        assert AccessRequestStatus.PENDING.value == "pending"

    def test_approved_value(self):
        assert AccessRequestStatus.APPROVED.value == "approved"

    def test_denied_value(self):
        assert AccessRequestStatus.DENIED.value == "denied"

    def test_from_string(self):
        assert AccessRequestStatus("pending") == AccessRequestStatus.PENDING
        assert AccessRequestStatus("approved") == AccessRequestStatus.APPROVED
        assert AccessRequestStatus("denied") == AccessRequestStatus.DENIED


class TestAccessControlEventTypes:
    """Tests for RFC-0011 access control event types."""

    def test_access_granted(self):
        assert EventType.ACCESS_GRANTED.value == "access_granted"

    def test_access_revoked(self):
        assert EventType.ACCESS_REVOKED.value == "access_revoked"

    def test_access_expired(self):
        assert EventType.ACCESS_EXPIRED.value == "access_expired"

    def test_access_requested(self):
        assert EventType.ACCESS_REQUESTED.value == "access_requested"

    def test_access_request_approved(self):
        assert EventType.ACCESS_REQUEST_APPROVED.value == "access_request_approved"

    def test_access_request_denied(self):
        assert EventType.ACCESS_REQUEST_DENIED.value == "access_request_denied"


class TestACLEntry:
    """Tests for ACLEntry dataclass."""

    def test_create_minimal(self):
        entry = ACLEntry(
            id="acl-1",
            principal_id="agent-1",
            principal_type="agent",
            permission=Permission.READ,
            granted_by="admin-1",
        )
        assert entry.id == "acl-1"
        assert entry.principal_id == "agent-1"
        assert entry.principal_type == "agent"
        assert entry.permission == Permission.READ
        assert entry.granted_by == "admin-1"
        assert entry.granted_at is None
        assert entry.expires_at is None
        assert entry.reason is None

    def test_create_full(self):
        now = datetime.now()
        future = datetime(2099, 1, 1)
        entry = ACLEntry(
            id="acl-2",
            principal_id="agent-2",
            principal_type="human",
            permission=Permission.ADMIN,
            granted_by="system",
            granted_at=now,
            expires_at=future,
            reason="Project lead",
        )
        assert entry.principal_type == "human"
        assert entry.permission == Permission.ADMIN
        assert entry.granted_at == now
        assert entry.expires_at == future
        assert entry.reason == "Project lead"

    def test_to_dict(self):
        now = datetime(2025, 6, 15, 12, 0, 0)
        entry = ACLEntry(
            id="acl-1",
            principal_id="agent-1",
            principal_type="agent",
            permission=Permission.WRITE,
            granted_by="admin-1",
            granted_at=now,
            reason="Needs write access",
        )
        d = entry.to_dict()
        assert d["id"] == "acl-1"
        assert d["principal_id"] == "agent-1"
        assert d["principal_type"] == "agent"
        assert d["permission"] == "write"
        assert d["granted_by"] == "admin-1"
        assert d["granted_at"] == now.isoformat()
        assert d["expires_at"] is None
        assert d["reason"] == "Needs write access"

    def test_from_dict(self):
        data = {
            "id": "acl-3",
            "principal_id": "bot-x",
            "principal_type": "agent",
            "permission": "admin",
            "granted_by": "owner",
            "granted_at": "2025-06-15T12:00:00",
            "reason": "Full access",
        }
        entry = ACLEntry.from_dict(data)
        assert entry.id == "acl-3"
        assert entry.principal_id == "bot-x"
        assert entry.permission == Permission.ADMIN
        assert entry.granted_by == "owner"
        assert entry.granted_at == datetime(2025, 6, 15, 12, 0, 0)
        assert entry.reason == "Full access"

    def test_round_trip(self):
        now = datetime(2025, 1, 1, 0, 0, 0)
        original = ACLEntry(
            id="acl-rt",
            principal_id="agent-rt",
            principal_type="agent",
            permission=Permission.READ,
            granted_by="system",
            granted_at=now,
        )
        restored = ACLEntry.from_dict(original.to_dict())
        assert restored.id == original.id
        assert restored.principal_id == original.principal_id
        assert restored.permission == original.permission
        assert restored.granted_at == original.granted_at


class TestIntentACL:
    """Tests for IntentACL dataclass."""

    def test_create_empty(self):
        acl = IntentACL(
            intent_id="intent-1",
            default_policy=AccessPolicy.OPEN,
        )
        assert acl.intent_id == "intent-1"
        assert acl.default_policy == AccessPolicy.OPEN
        assert acl.entries == []

    def test_create_with_entries(self):
        entry = ACLEntry(
            id="e1",
            principal_id="agent-1",
            principal_type="agent",
            permission=Permission.READ,
            granted_by="admin",
        )
        acl = IntentACL(
            intent_id="intent-2",
            default_policy=AccessPolicy.CLOSED,
            entries=[entry],
        )
        assert len(acl.entries) == 1
        assert acl.entries[0].principal_id == "agent-1"
        assert acl.default_policy == AccessPolicy.CLOSED

    def test_to_dict(self):
        entry = ACLEntry(
            id="e1",
            principal_id="agent-1",
            principal_type="agent",
            permission=Permission.WRITE,
            granted_by="admin",
        )
        acl = IntentACL(
            intent_id="intent-1",
            default_policy=AccessPolicy.OPEN,
            entries=[entry],
        )
        d = acl.to_dict()
        assert d["intent_id"] == "intent-1"
        assert d["default_policy"] == "open"
        assert len(d["entries"]) == 1
        assert d["entries"][0]["permission"] == "write"

    def test_from_dict(self):
        data = {
            "intent_id": "intent-x",
            "default_policy": "closed",
            "entries": [
                {
                    "id": "e1",
                    "principal_id": "bot-1",
                    "principal_type": "agent",
                    "permission": "read",
                    "granted_by": "owner",
                }
            ],
        }
        acl = IntentACL.from_dict(data)
        assert acl.intent_id == "intent-x"
        assert acl.default_policy == AccessPolicy.CLOSED
        assert len(acl.entries) == 1
        assert acl.entries[0].permission == Permission.READ

    def test_round_trip(self):
        entry = ACLEntry(
            id="e1",
            principal_id="agent-1",
            principal_type="agent",
            permission=Permission.ADMIN,
            granted_by="system",
        )
        original = IntentACL(
            intent_id="intent-rt",
            default_policy=AccessPolicy.CLOSED,
            entries=[entry],
        )
        restored = IntentACL.from_dict(original.to_dict())
        assert restored.intent_id == original.intent_id
        assert restored.default_policy == original.default_policy
        assert len(restored.entries) == 1
        assert restored.entries[0].permission == Permission.ADMIN


class TestAccessRequest:
    """Tests for AccessRequest dataclass."""

    def test_create_minimal(self):
        req = AccessRequest(
            id="req-1",
            intent_id="intent-1",
            principal_id="agent-1",
            principal_type="agent",
            requested_permission=Permission.READ,
            reason="Need to read state",
        )
        assert req.id == "req-1"
        assert req.status == AccessRequestStatus.PENDING
        assert req.capabilities == []
        assert req.decided_by is None

    def test_create_full(self):
        now = datetime.now()
        req = AccessRequest(
            id="req-2",
            intent_id="intent-2",
            principal_id="agent-2",
            principal_type="agent",
            requested_permission=Permission.WRITE,
            reason="Need write access",
            status=AccessRequestStatus.APPROVED,
            capabilities=["ocr", "nlp"],
            decided_by="admin-1",
            decided_at=now,
            decision_reason="Has required capabilities",
            created_at=now,
        )
        assert req.status == AccessRequestStatus.APPROVED
        assert req.capabilities == ["ocr", "nlp"]
        assert req.decided_by == "admin-1"
        assert req.decision_reason == "Has required capabilities"

    def test_to_dict(self):
        req = AccessRequest(
            id="req-1",
            intent_id="intent-1",
            principal_id="agent-1",
            principal_type="agent",
            requested_permission=Permission.WRITE,
            reason="Need access",
            capabilities=["search"],
        )
        d = req.to_dict()
        assert d["id"] == "req-1"
        assert d["requested_permission"] == "write"
        assert d["status"] == "pending"
        assert d["capabilities"] == ["search"]
        assert d["decided_by"] is None

    def test_from_dict(self):
        data = {
            "id": "req-3",
            "intent_id": "intent-3",
            "principal_id": "bot-z",
            "principal_type": "agent",
            "requested_permission": "admin",
            "reason": "Full access needed",
            "status": "denied",
            "capabilities": ["code_review"],
            "decided_by": "owner",
            "decision_reason": "Insufficient trust",
        }
        req = AccessRequest.from_dict(data)
        assert req.id == "req-3"
        assert req.requested_permission == Permission.ADMIN
        assert req.status == AccessRequestStatus.DENIED
        assert req.capabilities == ["code_review"]
        assert req.decided_by == "owner"

    def test_round_trip(self):
        now = datetime(2025, 3, 1, 10, 0, 0)
        original = AccessRequest(
            id="req-rt",
            intent_id="intent-rt",
            principal_id="agent-rt",
            principal_type="agent",
            requested_permission=Permission.READ,
            reason="Testing",
            status=AccessRequestStatus.APPROVED,
            capabilities=["a", "b"],
            decided_by="admin",
            decided_at=now,
            created_at=now,
        )
        restored = AccessRequest.from_dict(original.to_dict())
        assert restored.id == original.id
        assert restored.requested_permission == original.requested_permission
        assert restored.status == original.status
        assert restored.capabilities == original.capabilities
        assert restored.decided_at == original.decided_at


class TestPeerInfo:
    """Tests for PeerInfo dataclass."""

    def test_create_minimal(self):
        peer = PeerInfo(
            principal_id="agent-1",
            principal_type="agent",
        )
        assert peer.principal_id == "agent-1"
        assert peer.principal_type == "agent"
        assert peer.permission is None

    def test_create_with_permission(self):
        peer = PeerInfo(
            principal_id="agent-2",
            principal_type="human",
            permission=Permission.WRITE,
        )
        assert peer.permission == Permission.WRITE

    def test_to_dict_without_permission(self):
        peer = PeerInfo(principal_id="agent-1", principal_type="agent")
        d = peer.to_dict()
        assert d == {"principal_id": "agent-1", "principal_type": "agent"}
        assert "permission" not in d

    def test_to_dict_with_permission(self):
        peer = PeerInfo(
            principal_id="agent-1",
            principal_type="agent",
            permission=Permission.READ,
        )
        d = peer.to_dict()
        assert d["permission"] == "read"

    def test_from_dict(self):
        data = {
            "principal_id": "bot-1",
            "principal_type": "agent",
            "permission": "write",
        }
        peer = PeerInfo.from_dict(data)
        assert peer.principal_id == "bot-1"
        assert peer.permission == Permission.WRITE

    def test_from_dict_no_permission(self):
        data = {
            "principal_id": "bot-2",
            "principal_type": "agent",
        }
        peer = PeerInfo.from_dict(data)
        assert peer.permission is None

    def test_round_trip(self):
        original = PeerInfo(
            principal_id="agent-rt",
            principal_type="human",
            permission=Permission.ADMIN,
        )
        restored = PeerInfo.from_dict(original.to_dict())
        assert restored.principal_id == original.principal_id
        assert restored.principal_type == original.principal_type
        assert restored.permission == original.permission


class TestIntentContext:
    """Tests for IntentContext dataclass."""

    def test_create_empty(self):
        ctx = IntentContext()
        assert ctx.parent is None
        assert ctx.dependencies == {}
        assert ctx.events == []
        assert ctx.acl is None
        assert ctx.my_permission is None
        assert ctx.attachments == []
        assert ctx.peers == []
        assert ctx.delegated_by is None

    def test_create_with_permission(self):
        ctx = IntentContext(my_permission=Permission.WRITE)
        assert ctx.my_permission == Permission.WRITE

    def test_create_with_acl(self):
        acl = IntentACL(
            intent_id="intent-1",
            default_policy=AccessPolicy.CLOSED,
        )
        ctx = IntentContext(acl=acl)
        assert ctx.acl is not None
        assert ctx.acl.default_policy == AccessPolicy.CLOSED

    def test_create_with_peers(self):
        peers = [
            PeerInfo("agent-1", "agent", Permission.READ),
            PeerInfo("agent-2", "agent", Permission.WRITE),
        ]
        ctx = IntentContext(peers=peers)
        assert len(ctx.peers) == 2
        assert ctx.peers[0].principal_id == "agent-1"
        assert ctx.peers[1].permission == Permission.WRITE

    def test_create_with_delegated_by(self):
        ctx = IntentContext(delegated_by="coordinator-1")
        assert ctx.delegated_by == "coordinator-1"

    def test_create_with_all_fields(self):
        parent = Intent(
            id="parent-1",
            title="Parent",
            description="Parent intent",
            version=1,
            status=IntentStatus.ACTIVE,
            state=IntentState(),
        )
        acl = IntentACL(
            intent_id="intent-1",
            default_policy=AccessPolicy.OPEN,
        )
        ctx = IntentContext(
            parent=parent,
            dependencies={"dep-1": {"status": "completed"}},
            acl=acl,
            my_permission=Permission.ADMIN,
            peers=[PeerInfo("agent-1", "agent")],
            delegated_by="owner",
        )
        assert ctx.parent.id == "parent-1"
        assert ctx.dependencies == {"dep-1": {"status": "completed"}}
        assert ctx.my_permission == Permission.ADMIN
        assert ctx.delegated_by == "owner"

    def test_to_dict_empty(self):
        ctx = IntentContext()
        d = ctx.to_dict()
        assert d["dependencies"] == {}
        assert d["events"] == []
        assert d["peers"] == []
        assert d["attachments"] == []
        assert "parent" not in d
        assert "acl" not in d
        assert "my_permission" not in d
        assert "delegated_by" not in d

    def test_to_dict_with_permission(self):
        ctx = IntentContext(my_permission=Permission.READ)
        d = ctx.to_dict()
        assert d["my_permission"] == "read"

    def test_to_dict_with_peers(self):
        ctx = IntentContext(
            peers=[PeerInfo("a1", "agent", Permission.WRITE)],
        )
        d = ctx.to_dict()
        assert len(d["peers"]) == 1
        assert d["peers"][0]["principal_id"] == "a1"

    def test_from_dict_empty(self):
        ctx = IntentContext.from_dict({})
        assert ctx.parent is None
        assert ctx.dependencies == {}
        assert ctx.events == []
        assert ctx.peers == []

    def test_from_dict_with_acl(self):
        data = {
            "acl": {
                "intent_id": "i1",
                "default_policy": "closed",
                "entries": [],
            },
            "my_permission": "write",
        }
        ctx = IntentContext.from_dict(data)
        assert ctx.acl is not None
        assert ctx.acl.default_policy == AccessPolicy.CLOSED
        assert ctx.my_permission == Permission.WRITE

    def test_from_dict_with_peers(self):
        data = {
            "peers": [
                {"principal_id": "bot-1", "principal_type": "agent", "permission": "read"},
                {"principal_id": "bot-2", "principal_type": "agent"},
            ],
        }
        ctx = IntentContext.from_dict(data)
        assert len(ctx.peers) == 2
        assert ctx.peers[0].permission == Permission.READ
        assert ctx.peers[1].permission is None

    def test_round_trip(self):
        acl = IntentACL(
            intent_id="i1",
            default_policy=AccessPolicy.CLOSED,
            entries=[
                ACLEntry(
                    id="e1",
                    principal_id="a1",
                    principal_type="agent",
                    permission=Permission.READ,
                    granted_by="admin",
                )
            ],
        )
        original = IntentContext(
            dependencies={"d1": {"done": True}},
            acl=acl,
            my_permission=Permission.WRITE,
            peers=[PeerInfo("a1", "agent", Permission.READ)],
            delegated_by="coordinator",
        )
        restored = IntentContext.from_dict(original.to_dict())
        assert restored.dependencies == original.dependencies
        assert restored.acl.default_policy == AccessPolicy.CLOSED
        assert len(restored.acl.entries) == 1
        assert restored.my_permission == Permission.WRITE
        assert len(restored.peers) == 1
        assert restored.delegated_by == "coordinator"


class TestOnAccessRequestedDecorator:
    """Tests for the @on_access_requested decorator."""

    def test_marks_handler(self):
        @on_access_requested
        def handler(intent, request):
            pass

        assert hasattr(handler, "_openintent_handler")
        assert handler._openintent_handler == "access_requested"

    def test_marks_async_handler(self):
        @on_access_requested
        async def handler(intent, request):
            return "approve"

        assert handler._openintent_handler == "access_requested"


class TestAgentConfigAccessControl:
    """Tests for AgentConfig access control fields."""

    def test_default_capabilities(self):
        config = AgentConfig()
        assert config.capabilities == []

    def test_default_auto_request_access(self):
        config = AgentConfig()
        assert config.auto_request_access is False

    def test_custom_capabilities(self):
        config = AgentConfig(capabilities=["ocr", "nlp", "search"])
        assert config.capabilities == ["ocr", "nlp", "search"]

    def test_auto_request_access_enabled(self):
        config = AgentConfig(auto_request_access=True)
        assert config.auto_request_access is True

    def test_capabilities_with_other_fields(self):
        config = AgentConfig(
            base_url="https://example.com",
            api_key="key-123",
            capabilities=["code_review"],
            auto_request_access=True,
        )
        assert config.base_url == "https://example.com"
        assert config.capabilities == ["code_review"]
        assert config.auto_request_access is True


class TestAgentDecoratorWithCapabilities:
    """Tests for the @Agent decorator with capabilities parameter."""

    def test_agent_with_capabilities(self):
        @Agent("cap-bot", capabilities=["ocr", "nlp"])
        class CapAgent:
            pass

        assert hasattr(CapAgent, "run")

    def test_agent_with_access_handler(self):
        @Agent("access-bot")
        class AccessAgent:
            @on_access_requested
            async def policy(self, intent, request):
                return "approve"

        instance = AccessAgent()
        assert hasattr(instance, "_handlers")
        assert "access_requested" in instance._handlers
        assert len(instance._handlers["access_requested"]) == 1
