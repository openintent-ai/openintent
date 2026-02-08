# Agent Abstractions

The `openintent.agents` module provides high-level, decorator-first abstractions for building agents with minimal boilerplate. The design philosophy is Pythonic and elegant: decorators and class parameters express protocol semantics so the framework handles the heavy lifting.

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
from openintent import Agent, on_assignment, on_complete, on_state_change

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

### v0.8.0: Agent with Memory and Tools

The `@Agent` decorator accepts configuration that the framework manages automatically:

```python
from openintent import Agent, on_assignment, on_task

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

### v0.8.0: Lifecycle Decorators

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
@Agent("planner", capabilities=["planning"])
class PlannerAgent:
    
    @on_assignment
    async def plan(self, intent):
        await self.tasks.create(
            intent.id,
            title="Research phase",
            assigned_to="researcher"
        )
        await self.tasks.create(
            intent.id,
            title="Analysis phase",
            assigned_to="analyst"
        )
        return {"status": "plan_created"}
```

### Graceful Shutdown (RFC-0016)

```python
from openintent import Agent, on_drain

@Agent("worker", auto_heartbeat=True)
class GracefulWorker:
    
    @on_drain
    async def shutdown(self):
        """Framework sends drain signal; finish in-progress work."""
        await self.memory.store("checkpoint", self._progress)
        print("Draining... saving state and finishing up")
```

## @Coordinator (Multi-Agent)

For orchestrating multiple agents with portfolios, governance, and decision auditing. The `@Coordinator` decorator mirrors `@Agent` with added orchestration capabilities:

```python
from openintent import Coordinator, on_all_complete, on_conflict, on_escalation, on_quorum

@Coordinator("pipeline",
    agents=["researcher", "analyst", "writer"],
    strategy="sequential",
    guardrails=["budget < 1000", "max_retries: 3"],
)
class ResearchPipeline:
    
    @on_all_complete
    async def finalize(self, portfolio):
        """Called when all intents in the portfolio complete."""
        return self._merge_results(portfolio)

    async def run_pipeline(self, goal: str):
        portfolio = await self.delegate(
            goal,
            agents=self.agents,
            strategy="sequential"
        )
        return portfolio

pipeline = ResearchPipeline()
result = await pipeline.run_pipeline("Market Analysis")
```

### v0.8.0: Coordinator Lifecycle Decorators

Coordinator-specific lifecycle decorators for governance, conflict resolution, and consensus:

```python
@Coordinator("governed",
    agents=["agent-a", "agent-b"],
    strategy="parallel",
    guardrails=["require_approval"],
)
class GovernedCoordinator:
    
    @on_conflict
    async def handle_conflict(self, intent, conflict):
        """Called on version conflicts — resolve optimistically."""
        await self.record_decision(
            decision_type="conflict_resolution",
            summary=f"Resolved conflict on {intent.id}",
            rationale="Latest write wins"
        )

    @on_escalation
    async def handle_escalation(self, intent, source_agent):
        """Called when an agent escalates to the coordinator."""
        await self.delegate(intent.title, agents=["senior-agent"])

    @on_quorum(threshold=0.6)
    async def on_vote_reached(self, intent, votes):
        """Called when 60% of agents agree on a decision."""
        await self.record_decision(
            decision_type="quorum",
            summary="Consensus reached",
            rationale=f"{len(votes)} votes in favor"
        )

    # Access the full decision audit log
    # audit = coordinator.decisions
```

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
- [Examples](../examples/multi-agent.md) - Full working examples
