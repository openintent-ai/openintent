# Streaming Example

This example shows how to use real-time event subscriptions.

## Subscribing to Intent Events

```python
from openintent import OpenIntentClient

client = OpenIntentClient(
    base_url="http://localhost:8000",
    agent_id="watcher"
)

# Subscribe to events for a specific intent
for event in client.subscribe(intent_id):
    print(f"Event: {event.event_type}")
    print(f"Actor: {event.actor}")
    print(f"Payload: {event.payload}")
    print("---")
```

## Subscribing to Agent Events

Monitor all events for a specific agent:

```python
for event in client.subscribe_agent("research-agent"):
    print(f"Agent event: {event.event_type}")
```

## Subscribing to Portfolio Events

Monitor all intents in a portfolio:

```python
for event in client.subscribe_portfolio(portfolio_id):
    print(f"Portfolio event: {event.event_type}")
    print(f"Intent: {event.intent_id}")
```

## Async Streaming

```python
from openintent import AsyncOpenIntentClient

async def watch_intent(intent_id):
    async with AsyncOpenIntentClient(
        base_url="http://localhost:8000",
        agent_id="async-watcher"
    ) as client:
        async for event in client.subscribe(intent_id):
            print(f"Event: {event.event_type}")
            
            if event.event_type == "status_changed":
                if event.payload.get("new") == "completed":
                    break
```

## LLM Streaming with Observability

Stream LLM responses while logging to OpenIntent:

```python
from openai import OpenAI
from openintent.adapters import OpenAIAdapter

adapter = OpenAIAdapter(OpenAI(), client, intent_id)

# Stream with automatic logging
for chunk in adapter.chat_complete_stream(
    model="gpt-4",
    messages=[{"role": "user", "content": "Tell me a story"}]
):
    content = chunk.choices[0].delta.content
    if content:
        print(content, end="", flush=True)

print()  # Final newline
```

## Event Filtering

```python
from openintent.models import EventType

# Only process specific event types
for event in client.subscribe(intent_id):
    if event.event_type == EventType.STATE_PATCHED:
        handle_state_change(event)
    elif event.event_type == EventType.LLM_REQUEST_COMPLETED:
        track_llm_usage(event)
```
