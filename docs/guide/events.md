# Event Logging

Every modification to an intent is recorded in an append-only event log, providing a complete audit trail.

## Event Types

```python
from openintent.models import EventType

# Core events
EventType.INTENT_CREATED      # Intent was created
EventType.STATE_PATCHED       # State was updated
EventType.STATUS_CHANGED      # Status transition
EventType.AGENT_ASSIGNED      # Agent assigned to intent
EventType.COMMENT             # Comment added

# LLM events
EventType.LLM_REQUEST_STARTED    # LLM call initiated
EventType.LLM_REQUEST_COMPLETED  # LLM call finished
EventType.LLM_REQUEST_FAILED     # LLM call failed

# Tool events
EventType.TOOL_CALL_STARTED      # Tool call initiated
EventType.TOOL_CALL_COMPLETED    # Tool call finished
EventType.TOOL_CALL_FAILED       # Tool call failed

# Streaming events
EventType.STREAM_STARTED      # Stream initiated
EventType.STREAM_CHUNK        # Stream chunk received
EventType.STREAM_COMPLETED    # Stream finished
```

## Logging Events

```python
from openintent.models import EventType

# Log a custom event
client.log_event(
    intent_id=intent.id,
    event_type=EventType.COMMENT,
    payload={"message": "Starting research phase"}
)

# Log with structured data
client.log_event(
    intent_id=intent.id,
    event_type=EventType.STATE_PATCHED,
    payload={
        "changes": {"progress": 0.5},
        "reason": "Completed initial analysis"
    }
)
```

## Querying Events

```python
from datetime import datetime, timedelta

# Get all events
events = client.get_events(intent.id)

# Filter by type
state_events = client.get_events(
    intent.id,
    event_type=EventType.STATE_PATCHED
)

# Filter by time
recent = client.get_events(
    intent.id,
    since=datetime.now() - timedelta(hours=1)
)

# Pagination
events = client.get_events(intent.id, limit=10)
```

## Event Structure

Each event contains:

```python
@dataclass
class IntentEvent:
    id: str                    # Unique event ID
    intent_id: str             # Parent intent
    event_type: EventType      # Type of event
    actor: str                 # Who created it (agent ID)
    payload: dict              # Event-specific data
    created_at: datetime       # When it occurred
```

## LLM Observability

Track LLM calls for cost and debugging:

```python
# Log LLM request start
client.log_llm_request_started(
    intent.id,
    payload={
        "model": "gpt-4",
        "messages": messages,
        "request_id": "req-123"
    }
)

# Log completion
client.log_llm_request_completed(
    intent.id,
    payload={
        "request_id": "req-123",
        "model": "gpt-4",
        "input_tokens": 150,
        "output_tokens": 50,
        "latency_ms": 1200
    }
)
```

!!! tip "Use LLM Adapters"
    The [LLM Adapters](adapters.md) handle this automatically for OpenAI, Anthropic, and other providers.

## Real-Time Subscriptions

Subscribe to events in real-time using SSE:

```python
# Subscribe to all events for an intent
for event in client.subscribe(intent.id):
    print(f"Event: {event.event_type}")
    print(f"Payload: {event.payload}")
```

See [Subscriptions](../api/client.md#subscriptions) for more details.

## Next Steps

- [Agent Abstractions](agents.md) - Handle events with decorators
- [LLM Adapters](adapters.md) - Automatic LLM observability
