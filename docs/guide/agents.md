# Agent Abstractions

The `openintent.agents` module provides high-level, decorator-first abstractions for building agents with minimal boilerplate. Decorators and class parameters express protocol semantics so the framework handles the heavy lifting.

## Three Levels of Abstraction

| Level | Class | Use Case |
|-------|-------|----------|
| Simple | `Worker` | Single-purpose agents with one handler |
| Standard | `@Agent` | Full-featured agents with event routing, memory, tools |
| Complex | `@Coordinator` | Multi-agent orchestration with governance |

## Worker (Simplest)

For single-purpose agents:

```python
from openintent import Worker

async def process(intent):
    return {"result": do_work(intent.title)}

worker = Worker("processor", process)
worker.run()
```

## @Agent Decorator (Recommended)

Zero-boilerplate agent classes with auto-subscription, state auto-patching, and protocol-managed lifecycle:

```python
from openintent.agents import Agent, on_assignment, on_complete, on_state_change

@Agent("research-agent")
class ResearchAgent:

    @on_assignment
    async def handle_new_intent(self, intent):
        """Called when assigned to a new intent."""
        return {"status": "researching"}  # Auto-patches state

    @on_state_change(keys=["data"])
    async def on_data_ready(self, intent, old_state, new_state):
        """Called when 'data' key changes in state."""
        analysis = analyze(new_state["data"])
        return {"analysis": analysis}

    @on_complete
    async def handle_completion(self, intent):
        """Called when intent is completed."""
        print(f"Intent {intent.id} completed!")

if __name__ == "__main__":
    ResearchAgent.run()
```

### Agent with Memory and Tools

The `@Agent` decorator accepts configuration that the framework manages automatically:

```python
from openintent.agents import Agent, on_assignment, on_task

@Agent("analyst",
    memory="episodic",           # RFC-0015: auto-configured memory tier
    tools=["web_search", "sql"], # RFC-0014: scoped tool access
    capabilities=["nlp", "sql"], # RFC-0016: registered capabilities
    auto_heartbeat=True,         # RFC-0016: automatic health pings
)
class AnalystAgent:

    @on_assignment
    async def research(self, intent):
        past = await self.memory.recall(tags=["research"])

        findings = await do_research(intent.description, context=past)

        await self.memory.store(
            key=f"research-{intent.id}",
            value=findings,
            tags=["research", intent.title]
        )

        return {"findings": findings, "status": "analyzed"}

    @on_task(status="completed")
    async def on_subtask_done(self, intent, task):
        """Called when a subtask completes."""
        return {"last_completed_task": task.title}
```

### Lifecycle Decorators

| Decorator | Trigger |
|-----------|---------|
| `@on_assignment` | Agent assigned to intent |
| `@on_complete` | Intent completed |
| `@on_state_change(keys)` | State keys changed |
| `@on_event(event_type)` | Specific event type |
| `@on_lease_available(scope)` | Lease becomes available |
| `@on_access_requested` | Access request received (RFC-0011) |
| `@on_task(status)` | Task lifecycle event (RFC-0012) |
| `@on_trigger(name)` | Trigger fires (RFC-0017) |
| `@on_drain` | Graceful shutdown signal (RFC-0016) |
| `@on_all_complete` | All portfolio intents complete |

### Memory Access (RFC-0015)

Agents configured with `memory=` get a natural `self.memory` proxy:

```python
@Agent("note-taker", memory="episodic")
class NoteTaker:

    @on_assignment
    async def work(self, intent):
        await self.memory.store("key", {"data": "value"}, tags=["notes"])

        results = await self.memory.recall(tags=["notes"])

        await self.memory.pin("key")  # Prevent LRU eviction
```

### Task Decomposition (RFC-0012)

Create and manage subtasks from within agent handlers:

```python
@Agent("planner", memory="working")
class PlannerAgent:

    @on_assignment
    async def plan(self, intent):
        await self.tasks.create(
            title="Research phase",
            parent_intent_id=intent.id,
            assign_to="researcher"
        )
        await self.tasks.create(
            title="Analysis phase",
            parent_intent_id=intent.id,
            depends_on=["research-phase"],
            assign_to="analyst"
        )
        return {"status": "planning", "tasks_created": 2}
```

### Tool Access (RFC-0014)

Agents configured with `tools=` get scoped tool access via `self.tools`:

```python
@Agent("data-agent", tools=["web_search", "sql_query"])
class DataAgent:

    @on_assignment
    async def work(self, intent):
        results = await self.tools.invoke("web_search", query=intent.description)
        return {"search_results": results}
```

## Protocol Decorators

First-class declarative configuration for protocol features. Import from `openintent.agents`:

### @Plan (RFC-0012)

Declare task decomposition strategy:

```python
from openintent.agents import Agent, Plan, on_assignment

@Plan(strategy="sequential", checkpoints=True)
@Agent("pipeline-agent")
class PipelineAgent:

    @on_assignment
    async def handle(self, intent):
        return {"status": "processing"}
```

### @Vault (RFC-0014)

Declare credential vault requirements:

```python
from openintent.agents import Agent, Vault, on_assignment

@Vault(name="api-keys", rotation_policy="30d")
@Agent("secure-agent")
class SecureAgent:

    @on_assignment
    async def handle(self, intent):
        return {"status": "authenticated"}
```

### @Memory (RFC-0015)

Declare memory tier configuration:

```python
from openintent.agents import Agent, Memory, on_assignment

@Memory(tier="episodic", capacity=1000, eviction="lru")
@Agent("learning-agent")
class LearningAgent:

    @on_assignment
    async def handle(self, intent):
        past = await self.memory.recall(tags=["similar"])
        return {"context_used": len(past)}
```

### @Trigger (RFC-0017)

Declare reactive scheduling:

```python
from openintent.agents import Agent, Trigger, on_trigger

@Trigger(type="schedule", cron="0 9 * * *")
@Agent("morning-agent")
class MorningAgent:

    @on_trigger(name="daily-check")
    async def daily_report(self, intent):
        return {"report": "generated"}
```

## @Coordinator Decorator

Multi-agent orchestration with governance features:

```python
from openintent.agents import (
    Coordinator, on_conflict, on_escalation, on_quorum
)

@Coordinator("team-lead",
    agents=["agent-a", "agent-b"],
    strategy="parallel",
    guardrails=["require_approval"],
)
class TeamCoordinator:

    @on_conflict
    async def handle_conflict(self, intent, conflict):
        """Called on version conflicts."""
        await self.record_decision(
            decision_type="conflict_resolution",
            summary=f"Resolved conflict on {intent.id}",
            rationale="Latest write wins"
        )

    @on_escalation
    async def handle_escalation(self, intent, source_agent):
        """Called when an agent escalates."""
        await self.delegate(intent.title, agents=["senior-agent"])

    @on_quorum(threshold=0.6)
    async def on_vote_reached(self, intent, votes):
        """Called when 60% of agents agree."""
        await self.record_decision(
            decision_type="quorum",
            summary="Consensus reached",
            rationale=f"{len(votes)} votes in favor"
        )

    # Access the full decision audit log
    # audit = coordinator.decisions
```

### Coordinator Lifecycle Decorators

| Decorator | Trigger |
|-----------|---------|
| `@on_conflict` | Version conflict detected |
| `@on_escalation` | Agent escalation received |
| `@on_quorum(threshold)` | Voting threshold met |

### Coordinator Methods

| Method | Description |
|--------|-------------|
| `self.delegate(title, agents)` | Delegate work to agents |
| `self.record_decision(...)` | Record governance decision |
| `self.decisions` | Access decision audit log |

## Running Agents

```python
# Run agent (blocks until stopped)
ResearchAgent.run()

# Run with asyncio
import asyncio
asyncio.run(agent.run_async())
```

## Next Steps

- [LLM Adapters](adapters.md) - Add LLM observability
- [Built-in Server](server.md) - Run your own OpenIntent server
- [Examples](../examples/multi-agent.md) - Full working examples
