"""
Tests for OpenIntent SDK models.
"""

from datetime import datetime

from openintent.models import (
    EventType,
    Intent,
    IntentEvent,
    IntentLease,
    IntentState,
    IntentStatus,
    LeaseStatus,
)


class TestIntentState:
    """Tests for IntentState model."""

    def test_create_empty_state(self):
        state = IntentState()
        assert state.data == {}

    def test_create_state_with_data(self):
        state = IntentState(data={"key": "value"})
        assert state.get("key") == "value"

    def test_get_with_default(self):
        state = IntentState()
        assert state.get("missing", "default") == "default"

    def test_set_value(self):
        state = IntentState()
        state.set("key", "value")
        assert state.get("key") == "value"

    def test_to_dict(self):
        state = IntentState(data={"a": 1, "b": 2})
        d = state.to_dict()
        assert d == {"a": 1, "b": 2}
        d["c"] = 3
        assert "c" not in state.data

    def test_from_dict(self):
        state = IntentState.from_dict({"x": "y"})
        assert state.get("x") == "y"


class TestIntent:
    """Tests for Intent model."""

    def test_create_intent(self):
        intent = Intent(
            id="test-id",
            title="Test Intent",
            description="A test intent",
            version=1,
            status=IntentStatus.ACTIVE,
            state=IntentState(),
        )
        assert intent.id == "test-id"
        assert intent.title == "Test Intent"
        assert intent.version == 1
        assert intent.status == IntentStatus.ACTIVE

    def test_intent_to_dict(self):
        intent = Intent(
            id="test-id",
            title="Test",
            description="Desc",
            version=1,
            status=IntentStatus.ACTIVE,
            state=IntentState(data={"progress": 0.5}),
            constraints=["constraint1"],
        )
        d = intent.to_dict()
        assert d["id"] == "test-id"
        assert d["status"] == "active"
        assert d["state"] == {"progress": 0.5}
        assert d["constraints"] == ["constraint1"]

    def test_intent_from_dict(self):
        data = {
            "id": "test-id",
            "title": "Test",
            "description": "Desc",
            "version": 2,
            "status": "completed",
            "state": {"done": True},
            "constraints": [],
        }
        intent = Intent.from_dict(data)
        assert intent.id == "test-id"
        assert intent.version == 2
        assert intent.status == IntentStatus.COMPLETED
        assert intent.state.get("done") is True


class TestIntentEvent:
    """Tests for IntentEvent model."""

    def test_create_event(self):
        now = datetime.now()
        event = IntentEvent(
            id="event-1",
            intent_id="intent-1",
            event_type=EventType.CREATED,
            agent_id="agent-1",
            payload={"key": "value"},
            created_at=now,
        )
        assert event.id == "event-1"
        assert event.event_type == EventType.CREATED
        assert event.payload["key"] == "value"

    def test_event_to_dict(self):
        now = datetime.now()
        event = IntentEvent(
            id="event-1",
            intent_id="intent-1",
            event_type=EventType.STATE_UPDATED,
            agent_id="agent-1",
            payload={},
            created_at=now,
        )
        d = event.to_dict()
        assert d["event_type"] == "state_updated"
        assert d["created_at"] == now.isoformat()


class TestIntentLease:
    """Tests for IntentLease model."""

    def test_lease_is_active(self):
        future = datetime(2099, 1, 1)
        lease = IntentLease(
            id="lease-1",
            intent_id="intent-1",
            agent_id="agent-1",
            scope="research",
            status=LeaseStatus.ACTIVE,
            expires_at=future,
            created_at=datetime.now(),
        )
        assert lease.is_active is True

    def test_lease_expired_status(self):
        future = datetime(2099, 1, 1)
        lease = IntentLease(
            id="lease-1",
            intent_id="intent-1",
            agent_id="agent-1",
            scope="research",
            status=LeaseStatus.EXPIRED,
            expires_at=future,
            created_at=datetime.now(),
        )
        assert lease.is_active is False

    def test_lease_to_dict(self):
        now = datetime.now()
        future = datetime(2099, 1, 1)
        lease = IntentLease(
            id="lease-1",
            intent_id="intent-1",
            agent_id="agent-1",
            scope="research",
            status=LeaseStatus.ACTIVE,
            expires_at=future,
            created_at=now,
        )
        d = lease.to_dict()
        assert d["scope"] == "research"
        assert d["status"] == "active"


class TestEnums:
    """Tests for enum values."""

    def test_intent_status_values(self):
        assert IntentStatus.ACTIVE.value == "active"
        assert IntentStatus.COMPLETED.value == "completed"
        assert IntentStatus.CANCELLED.value == "cancelled"
        assert IntentStatus.BLOCKED.value == "blocked"

    def test_event_type_values(self):
        assert EventType.CREATED.value == "created"
        assert EventType.STATE_UPDATED.value == "state_updated"
        assert EventType.LEASE_ACQUIRED.value == "lease_acquired"

    def test_lease_status_values(self):
        assert LeaseStatus.ACTIVE.value == "active"
        assert LeaseStatus.RELEASED.value == "released"
        assert LeaseStatus.EXPIRED.value == "expired"
