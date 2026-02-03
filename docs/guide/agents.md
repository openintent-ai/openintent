# Agent Abstractions

The `openintent.agents` module provides high-level abstractions for building agents with minimal boilerplate.

## Three Levels of Abstraction

| Level | Class | Use Case |
|-------|-------|----------|
| Simple | `Worker` | Single-purpose agents with one handler |
| Standard | `@Agent` | Full-featured agents with event routing |
| Complex | `Coordinator` | Multi-agent orchestration |

## Worker (Simplest)

For single-purpose agents:

```python
from openintent.agents import Worker

def handle_task(intent, client):
    # Do work
    return {"result": "done"}

worker = Worker(
    agent_id="simple-worker",
    base_url="http://localhost:8000",
    handler=handle_task
)
worker.run()
```

## @Agent Decorator (Recommended)

Zero-boilerplate agent classes:

```python
from openintent.agents import Agent, on_assignment, on_complete

@Agent("research-agent")
class ResearchAgent:
    
    @on_assignment
    async def handle_new_intent(self, intent):
        """Called when assigned to a new intent."""
        # Your logic here
        return {"status": "researching"}
    
    @on_complete
    async def handle_completion(self, intent):
        """Called when intent is completed."""
        print(f"Intent {intent.id} completed!")
```

### Event Decorators

| Decorator | Trigger |
|-----------|---------|
| `@on_assignment` | Agent assigned to intent |
| `@on_complete` | Intent completed |
| `@on_state_change(keys)` | State keys changed |
| `@on_event(event_type)` | Specific event type |
| `@on_lease_available(scope)` | Lease becomes available |

### State Change Handlers

React to specific state changes:

```python
@Agent("monitor-agent")
class MonitorAgent:
    
    @on_state_change(["error_count"])
    async def handle_errors(self, intent, old_state, new_state):
        if new_state.get("error_count", 0) > 5:
            # Alert on high error count
            return {"status": "alerting"}
```

### Auto-Patching

Return values automatically update intent state:

```python
@Agent("auto-patch-agent")
class AutoPatchAgent:
    
    @on_assignment
    async def work(self, intent):
        # Returning a dict patches the state
        return {
            "processed": True,
            "items": 42
        }
        # Automatically calls: client.patch_state(intent.id, {...})
```

## Coordinator (Multi-Agent)

For orchestrating multiple agents with dependencies:

```python
from openintent.agents import Coordinator, IntentSpec, PortfolioSpec

# Define workflow
workflow = PortfolioSpec(
    name="Research Pipeline",
    intents=[
        IntentSpec(
            title="Gather data",
            assign="data-agent"
        ),
        IntentSpec(
            title="Analyze results",
            assign="analysis-agent",
            depends_on=["Gather data"]
        ),
        IntentSpec(
            title="Generate report",
            assign="report-agent",
            depends_on=["Analyze results"]
        )
    ]
)

coordinator = Coordinator(
    agent_id="coordinator",
    base_url="http://localhost:8000"
)

# Execute workflow
coordinator.run_portfolio(workflow)
```

### Portfolio Events

```python
from openintent.agents import on_all_complete

@Coordinator("my-coordinator")
class MyCoordinator:
    
    @on_all_complete
    async def handle_portfolio_done(self, portfolio):
        """Called when all intents in portfolio complete."""
        print("Workflow complete!")
```

## Running Agents

```python
# Run agent (blocks)
agent = ResearchAgent()
agent.run()

# Run with asyncio
import asyncio
asyncio.run(agent.run_async())
```

## Configuration

```python
from openintent.agents import AgentConfig

config = AgentConfig(
    base_url="http://localhost:8000",
    poll_interval=1.0,  # Seconds between polls
    auto_complete=True  # Auto-complete after handlers
)

@Agent("my-agent", config=config)
class MyAgent:
    ...
```

## Next Steps

- [LLM Adapters](adapters.md) - Add LLM observability
- [Examples](../examples/multi-agent.md) - Full working examples
