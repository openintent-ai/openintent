---
title: Subscriptions & Streaming
---

# Subscriptions & Streaming

Subscriptions provide real-time event delivery using Server-Sent Events (SSE). Agents and clients can subscribe to intents, agents, or portfolios to receive updates as they happen. Defined in [RFC-0006](../rfcs/0006-subscriptions.md).

## Subscribing to an Intent

```python
# Subscribe to all events for an intent
for event in client.subscribe(intent.id):
    print(f"[{event.event_type}] {event.payload}")
```

### Filtered Subscriptions

```python
from openintent.models import EventType

# Subscribe to specific event types only
for event in client.subscribe(
    intent.id,
    event_types=[EventType.STATE_PATCHED, EventType.STATUS_CHANGED]
):
    print(f"State or status changed: {event.payload}")
```

## Subscribing to an Agent

Watch all events across every intent an agent is working on:

```python
for event in client.subscribe_agent(agent_id="research-agent"):
    print(f"Intent {event.intent_id}: {event.event_type}")
```

## Subscribing to a Portfolio

Watch aggregate events across a portfolio of intents:

```python
for event in client.subscribe_portfolio(portfolio_id):
    print(f"Portfolio event: {event.event_type} on {event.intent_id}")
```

## Async Subscriptions

```python
import asyncio
from openintent import AsyncOpenIntentClient

async def watch():
    client = AsyncOpenIntentClient(
        base_url="http://localhost:8000",
        api_key="dev-user-key",
        agent_id="watcher"
    )

    async for event in client.subscribe(intent_id):
        print(f"[{event.event_type}] {event.payload}")

        if event.event_type == "status_changed" and \
           event.payload.get("new_status") == "completed":
            break

asyncio.run(watch())
```

## SSE Event Format

Events are delivered as standard SSE with JSON payloads:

```
event: state_patched
data: {"intent_id": "intent_01", "changes": {"progress": 0.5}, "version": 3}

event: status_changed
data: {"intent_id": "intent_01", "old_status": "active", "new_status": "completed"}
```

## Using Subscriptions in Agents

The `@Agent` decorator handles subscriptions automatically. When you call `agent.run()`, the agent subscribes to relevant intents and routes events to your decorated handlers:

```python
from openintent.agents import Agent, on_state_change, on_event
from openintent.models import EventType

@Agent("monitor")
class MonitorAgent:

    @on_state_change(keys=["progress"])
    async def on_progress(self, intent, old_state, new_state):
        pct = new_state.get("progress", 0) * 100
        print(f"Progress: {pct:.0f}%")

    @on_event(EventType.COMMENT)
    async def on_comment(self, intent, event):
        print(f"Comment: {event.payload['message']}")
```

!!! info "Automatic reconnection"
    The SDK handles SSE reconnection automatically. If the connection drops, it resumes from the last received event ID.

## Server-Side Endpoint

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/intents/{id}/subscribe` | Subscribe to intent events |
| `GET` | `/api/v1/agents/{id}/subscribe` | Subscribe to agent events |
| `GET` | `/api/v1/portfolios/{id}/subscribe` | Subscribe to portfolio events |

## Next Steps

- [Events](events.md) — Event types and logging
- [Agent Abstractions](agents.md) — Automatic subscription handling
- [Portfolios](portfolios.md) — Portfolio-level subscriptions
