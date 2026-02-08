# SSE Subscriptions & Real-Time Streaming

Subscribe to protocol events in real time via Server-Sent Events.

## Subscribe to Intent Events

```python
from openintent import OpenIntentClient

client = OpenIntentClient(
    base_url="http://localhost:8000",
    agent_id="watcher"
)

# SSE stream — blocks and yields events as they arrive
for event in client.subscribe(intent_id):
    print(f"[{event.timestamp}] {event.event_type}")
    print(f"  Actor: {event.actor}")
    print(f"  Payload: {event.payload}")

    if event.event_type == "status_changed":
        new_status = event.payload.get("new")
        if new_status == "completed":
            break
```

## Subscribe to Agent Events

Monitor all activity for a specific agent:

```python
for event in client.subscribe_agent("research-agent"):
    if event.event_type == "intent_assigned":
        print(f"New task: {event.payload.get('title')}")
    elif event.event_type == "lease_acquired":
        print(f"Lease acquired on {event.payload.get('intent_id')}")
```

## Subscribe to Portfolio Events

```python
for event in client.subscribe_portfolio(portfolio_id):
    intent_id = event.intent_id
    print(f"[{event.event_type}] Intent {intent_id}")

    if event.event_type == "all_intents_completed":
        print("Portfolio finished!")
        break
```

## Async Streaming

```python
from openintent import AsyncOpenIntentClient

async def watch_portfolio(portfolio_id):
    async with AsyncOpenIntentClient(
        base_url="http://localhost:8000",
        agent_id="async-watcher"
    ) as client:
        async for event in client.subscribe_portfolio(portfolio_id):
            print(f"Event: {event.event_type}")

            if event.event_type == "all_intents_completed":
                break
```

## Event Filtering

```python
from openintent.models import EventType

for event in client.subscribe(intent_id):
    match event.event_type:
        case EventType.STATE_PATCHED:
            handle_state_change(event)
        case EventType.LLM_REQUEST_COMPLETED:
            track_cost(event)
        case EventType.LEASE_EXPIRED:
            handle_lease_expiry(event)
        case EventType.ATTACHMENT_ADDED:
            process_attachment(event)
```

## LLM Streaming with Protocol Logging

Stream LLM responses while automatically logging to the intent event log:

```python
from openai import OpenAI
from openintent.adapters import OpenAIAdapter, AdapterConfig

config = AdapterConfig(
    on_stream_start=lambda: print("Generating..."),
    on_token=lambda t: print(t, end="", flush=True),
    on_stream_end=lambda u: print(f"\n[{u['total_tokens']} tokens]"),
    on_stream_error=lambda e: print(f"\nError: {e}")
)

adapter = OpenAIAdapter(OpenAI(), client, intent.id, config=config)

for chunk in adapter.chat_complete_stream(
    model="gpt-4",
    messages=[{"role": "user", "content": "Explain distributed systems"}]
):
    pass  # Hooks handle output

# Event log now contains the full LLM interaction with cost data
```

## Building a Dashboard

```python
import asyncio
from openintent import AsyncOpenIntentClient

async def dashboard(portfolio_ids):
    async with AsyncOpenIntentClient(
        base_url="http://localhost:8000",
        agent_id="dashboard"
    ) as client:
        tasks = [
            watch_portfolio(client, pid)
            for pid in portfolio_ids
        ]
        await asyncio.gather(*tasks)

async def watch_portfolio(client, portfolio_id):
    async for event in client.subscribe_portfolio(portfolio_id):
        print(f"[{portfolio_id[:8]}] {event.event_type}: {event.payload}")

asyncio.run(dashboard(["portfolio-1", "portfolio-2"]))
```
