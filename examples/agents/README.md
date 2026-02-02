# OpenIntent Agent Examples

This directory contains examples using the high-level agent abstractions.

## Quick Start

```bash
# Install with server support
pip install -e ".[server]"

# Start the OpenIntent server
openintent-server

# In another terminal, run an agent
python examples/agents/research_agent.py
```

## Examples

### 1. Research Agent (`research_agent.py`)

Demonstrates the `@Agent` decorator for creating agents with minimal boilerplate:

```python
from openintent import Agent, on_assignment

@Agent("research-bot")
class ResearchAgent:
    @on_assignment
    async def work(self, intent):
        return {"result": "done"}  # Auto-patches state

ResearchAgent.run()
```

### 2. Coordinator (`coordinator.py`)

Shows how to orchestrate multiple agents using portfolios with dependencies:

```python
from openintent import Coordinator, PortfolioSpec, IntentSpec

class MyCoordinator(Coordinator):
    async def plan(self, topic):
        return PortfolioSpec(
            name=topic,
            intents=[
                IntentSpec("Research", assign="researcher"),
                IntentSpec("Write", assign="writer", depends_on=["Research"]),
            ]
        )

# Execute and wait for all to complete
result = await coordinator.execute(spec)
```

### 3. Worker (`worker.py`)

The absolute minimum for a single-purpose agent:

```python
from openintent import Worker

async def process(intent):
    return {"result": "processed"}

Worker("my-worker", process).run()
```

## Event Handlers

Available decorator-based event handlers:

| Decorator | When Called |
|-----------|------------|
| `@on_assignment` | When assigned to an intent |
| `@on_complete` | When an intent completes |
| `@on_lease_available(scope)` | When a scope lease becomes available |
| `@on_state_change(keys)` | When intent state changes |
| `@on_event(type)` | When a specific event type occurs |
| `@on_all_complete` | When all portfolio intents complete |

## Configuration

Use environment variables:

```bash
export OPENINTENT_URL="http://localhost:8000"
export OPENINTENT_API_KEY="your-api-key"
```

Or pass directly:

```python
ResearchAgent.run(base_url="http://...", api_key="...")
```

## Comparison: Before and After

**Before (low-level SDK):**

```python
client = OpenIntentClient(base_url="...", api_key="...", agent_id="bot")
for event in client.subscribe_agent("bot"):
    if event.type == "AGENT_ASSIGNED":
        intent = client.get_intent(event.intent_id)
        # do work
        client.update_state(intent.id, intent.version, {"result": "done"})
        client.set_status(intent.id, IntentStatus.COMPLETED, intent.version + 1)
```

**After (high-level SDK):**

```python
@Agent("bot")
class Bot:
    @on_assignment
    async def work(self, intent):
        return {"result": "done"}  # Auto-patched, auto-completed

Bot.run()
```
