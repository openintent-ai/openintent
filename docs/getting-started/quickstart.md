# Quick Start

Get up and running with OpenIntent in minutes.

## Start a Server

First, start an OpenIntent server:

```bash
# Install with server support
pip install openintent[server]

# Start the server
openintent-server
```

The server runs on `http://localhost:8000` by default.

## Create Your First Intent

```python
from openintent import OpenIntentClient

# Connect to the server
client = OpenIntentClient(
    base_url="http://localhost:8000",
    agent_id="my-first-agent"
)

# Create an intent
intent = client.create_intent(
    title="Plan a trip to Paris",
    description="Research flights, hotels, and attractions"
)

print(f"Created intent: {intent.id}")
print(f"Status: {intent.status}")
```

## Update Intent State

```python
# Patch the state
updated = client.patch_state(
    intent.id,
    {
        "flights_researched": True,
        "hotels_found": 5,
        "budget_remaining": 2000
    }
)

print(f"New version: {updated.version}")
```

## Log Events

```python
from openintent.models import EventType

# Log progress
client.log_event(
    intent.id,
    EventType.STATE_PATCHED,
    payload={"step": "research", "progress": 0.5}
)
```

## Complete the Intent

```python
# Mark as completed
completed = client.complete_intent(intent.id)
print(f"Status: {completed.status}")  # "completed"
```

## Run the Demo

Try the interactive demo that showcases multi-agent coordination:

```bash
# Works without LLM keys (mock mode)
openintent demo

# With real LLM responses
OPENAI_API_KEY=sk-... openintent demo
```

## Next Steps

- [Configuration](configuration.md) - Advanced client configuration
- [Agent Abstractions](../guide/agents.md) - Build agents with decorators
- [LLM Adapters](../guide/adapters.md) - Add LLM observability
