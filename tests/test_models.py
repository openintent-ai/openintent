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
    LLMRequestPayload,
    StreamState,
    StreamStatus,
    ToolCallPayload,
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

    def test_stream_status_values(self):
        assert StreamStatus.ACTIVE.value == "active"
        assert StreamStatus.COMPLETED.value == "completed"
        assert StreamStatus.CANCELLED.value == "cancelled"
        assert StreamStatus.FAILED.value == "failed"

    def test_new_event_type_values(self):
        assert EventType.TOOL_CALL_STARTED.value == "tool_call_started"
        assert EventType.TOOL_CALL_COMPLETED.value == "tool_call_completed"
        assert EventType.TOOL_CALL_FAILED.value == "tool_call_failed"
        assert EventType.LLM_REQUEST_STARTED.value == "llm_request_started"
        assert EventType.LLM_REQUEST_COMPLETED.value == "llm_request_completed"
        assert EventType.LLM_REQUEST_FAILED.value == "llm_request_failed"
        assert EventType.STREAM_STARTED.value == "stream_started"
        assert EventType.STREAM_CHUNK.value == "stream_chunk"
        assert EventType.STREAM_COMPLETED.value == "stream_completed"
        assert EventType.STREAM_CANCELLED.value == "stream_cancelled"


class TestToolCallPayload:
    """Tests for ToolCallPayload model."""

    def test_create_minimal(self):
        payload = ToolCallPayload(
            tool_name="web_search",
            tool_id="call_123",
            arguments={"query": "test"},
        )
        assert payload.tool_name == "web_search"
        assert payload.tool_id == "call_123"
        assert payload.arguments == {"query": "test"}
        assert payload.provider is None

    def test_create_full(self):
        payload = ToolCallPayload(
            tool_name="web_search",
            tool_id="call_123",
            arguments={"query": "test"},
            provider="openai",
            model="gpt-4",
            parent_request_id="req_456",
            result={"data": "result"},
            duration_ms=150,
            token_count=50,
        )
        assert payload.provider == "openai"
        assert payload.model == "gpt-4"
        assert payload.result == {"data": "result"}
        assert payload.duration_ms == 150

    def test_to_dict_minimal(self):
        payload = ToolCallPayload(
            tool_name="calculator",
            tool_id="call_789",
            arguments={"a": 1, "b": 2},
        )
        d = payload.to_dict()
        assert d["tool_name"] == "calculator"
        assert d["tool_id"] == "call_789"
        assert d["arguments"] == {"a": 1, "b": 2}
        assert "provider" not in d
        assert "error" not in d

    def test_to_dict_with_error(self):
        payload = ToolCallPayload(
            tool_name="api_call",
            tool_id="call_error",
            arguments={},
            error="Connection timeout",
            duration_ms=5000,
        )
        d = payload.to_dict()
        assert d["error"] == "Connection timeout"
        assert d["duration_ms"] == 5000

    def test_from_dict(self):
        data = {
            "tool_name": "search",
            "tool_id": "call_abc",
            "arguments": {"q": "hello"},
            "provider": "anthropic",
            "model": "claude-3",
            "result": "found",
        }
        payload = ToolCallPayload.from_dict(data)
        assert payload.tool_name == "search"
        assert payload.provider == "anthropic"
        assert payload.result == "found"


class TestLLMRequestPayload:
    """Tests for LLMRequestPayload model."""

    def test_create_minimal(self):
        payload = LLMRequestPayload(
            request_id="req_123",
            provider="openai",
            model="gpt-4",
            messages_count=3,
        )
        assert payload.request_id == "req_123"
        assert payload.provider == "openai"
        assert payload.stream is False
        assert payload.tools_available == []

    def test_create_streaming_request(self):
        payload = LLMRequestPayload(
            request_id="req_stream",
            provider="anthropic",
            model="claude-3-opus",
            messages_count=5,
            stream=True,
            temperature=0.7,
            max_tokens=4000,
            tools_available=["web_search", "calculator"],
        )
        assert payload.stream is True
        assert payload.temperature == 0.7
        assert len(payload.tools_available) == 2

    def test_create_completed_request(self):
        payload = LLMRequestPayload(
            request_id="req_done",
            provider="openai",
            model="gpt-4",
            messages_count=2,
            response_content="Hello, world!",
            finish_reason="stop",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            duration_ms=1200,
        )
        assert payload.response_content == "Hello, world!"
        assert payload.total_tokens == 150

    def test_to_dict_minimal(self):
        payload = LLMRequestPayload(
            request_id="req_min",
            provider="openai",
            model="gpt-3.5-turbo",
            messages_count=1,
        )
        d = payload.to_dict()
        assert d["request_id"] == "req_min"
        assert d["stream"] is False
        assert "response_content" not in d
        assert "error" not in d

    def test_to_dict_with_tool_calls(self):
        payload = LLMRequestPayload(
            request_id="req_tools",
            provider="openai",
            model="gpt-4",
            messages_count=2,
            tool_calls=[
                {"id": "call_1", "function": {"name": "search"}},
                {"id": "call_2", "function": {"name": "calculate"}},
            ],
        )
        d = payload.to_dict()
        assert len(d["tool_calls"]) == 2

    def test_from_dict(self):
        data = {
            "request_id": "req_parsed",
            "provider": "anthropic",
            "model": "claude-3-sonnet",
            "messages_count": 4,
            "stream": True,
            "total_tokens": 500,
        }
        payload = LLMRequestPayload.from_dict(data)
        assert payload.request_id == "req_parsed"
        assert payload.stream is True
        assert payload.total_tokens == 500


class TestStreamState:
    """Tests for StreamState model."""

    def test_create_active_stream(self):
        now = datetime.now()
        state = StreamState(
            stream_id="stream_123",
            intent_id="intent_abc",
            agent_id="agent_1",
            status=StreamStatus.ACTIVE,
            provider="openai",
            model="gpt-4",
            started_at=now,
        )
        assert state.stream_id == "stream_123"
        assert state.status == StreamStatus.ACTIVE
        assert state.chunks_received == 0

    def test_create_completed_stream(self):
        now = datetime.now()
        state = StreamState(
            stream_id="stream_done",
            intent_id="intent_xyz",
            agent_id="agent_2",
            status=StreamStatus.COMPLETED,
            provider="anthropic",
            model="claude-3",
            chunks_received=100,
            tokens_streamed=1500,
            started_at=now,
            completed_at=now,
        )
        assert state.chunks_received == 100
        assert state.tokens_streamed == 1500

    def test_create_cancelled_stream(self):
        now = datetime.now()
        state = StreamState(
            stream_id="stream_cancel",
            intent_id="intent_cancel",
            agent_id="agent_3",
            status=StreamStatus.CANCELLED,
            provider="openai",
            model="gpt-4",
            chunks_received=50,
            tokens_streamed=750,
            cancelled_at=now,
            cancel_reason="User interrupted",
        )
        assert state.status == StreamStatus.CANCELLED
        assert state.cancel_reason == "User interrupted"

    def test_to_dict(self):
        now = datetime.now()
        state = StreamState(
            stream_id="stream_dict",
            intent_id="intent_dict",
            agent_id="agent_dict",
            status=StreamStatus.ACTIVE,
            provider="openai",
            model="gpt-4",
            chunks_received=10,
            tokens_streamed=100,
            started_at=now,
        )
        d = state.to_dict()
        assert d["stream_id"] == "stream_dict"
        assert d["status"] == "active"
        assert d["chunks_received"] == 10
        assert d["started_at"] == now.isoformat()
        assert "cancelled_at" not in d

    def test_from_dict(self):
        now = datetime.now()
        data = {
            "stream_id": "stream_parsed",
            "intent_id": "intent_parsed",
            "agent_id": "agent_parsed",
            "status": "completed",
            "provider": "anthropic",
            "model": "claude-3",
            "chunks_received": 200,
            "tokens_streamed": 3000,
            "started_at": now.isoformat(),
            "completed_at": now.isoformat(),
        }
        state = StreamState.from_dict(data)
        assert state.stream_id == "stream_parsed"
        assert state.status == StreamStatus.COMPLETED
        assert state.tokens_streamed == 3000
