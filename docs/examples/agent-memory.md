# Agent Memory & Persistent State

Three-tier memory model for agent continuity — working memory (task-scoped), episodic memory (agent-scoped), and semantic memory (shared).

## Declarative Memory with @Agent

```python
from openintent.agents import Agent, on_assignment, Memory

@Memory
class AgentMemory:
    type = "episodic"
    max_entries = 1000
    eviction = "lru"
    ttl_seconds = 86400

@Agent("remembering-agent", memory="episodic", auto_heartbeat=True)
class RememberingAgent:

    @on_assignment
    async def handle(self, intent):
        # Store in episodic memory (survives across tasks)
        await self.memory.store(
            key=f"task_{intent.id}",
            value={"topic": intent.title, "outcome": "success"},
            tags=["completed", "research"]
        )

        # Query past experiences
        past = await self.memory.query(
            tags=["research"],
            limit=5
        )

        # Pin important memories (exempt from eviction)
        await self.memory.pin(key="critical_finding_1")

        return {
            "past_experience_count": len(past),
            "status": "done"
        }
```

## Three Memory Tiers (Imperative)

```python
from openintent import OpenIntentClient

client = OpenIntentClient(
    base_url="http://localhost:8000",
    agent_id="memory-agent"
)

# --- Working Memory (task-scoped, auto-archived on completion) ---
client.memory.store(
    key="current_findings",
    value={"data": [1, 2, 3]},
    scope="working",
    intent_id=intent.id
)

# --- Episodic Memory (agent-scoped, LRU eviction) ---
client.memory.store(
    key="learned_pattern",
    value={"pattern": "users prefer concise responses"},
    scope="episodic",
    tags=["learning", "user-behavior"]
)

# --- Semantic Memory (shared across agents, namespace-scoped) ---
client.memory.store(
    key="company_policy",
    value={"refund_window_days": 30},
    scope="semantic",
    namespace="customer-support",
    tags=["policy"]
)
```

## Querying Memory

```python
# Tag-based queries
results = client.memory.query(
    scope="episodic",
    tags=["research"],
    limit=10
)

for entry in results:
    print(f"  [{entry.key}] {entry.value} (tags: {entry.tags})")

# Get specific entry
entry = client.memory.get(key="learned_pattern", scope="episodic")

# Delete with optimistic concurrency
client.memory.delete(
    key="outdated_info",
    scope="episodic",
    expected_version=entry.version
)
```

## Memory Continuity on Agent Restart

When an agent crashes and restarts, working memory enables seamless resumption:

```python
from openintent.agents import Agent, on_assignment

@Agent("resilient-agent", memory="episodic", auto_heartbeat=True)
class ResilientAgent:

    @on_assignment
    async def handle(self, intent):
        # Check if we were interrupted
        checkpoint = await self.memory.get(
            key=f"checkpoint_{intent.id}",
            scope="working"
        )

        if checkpoint:
            # Resume from checkpoint
            step = checkpoint.value.get("step", 0)
            print(f"Resuming from step {step}")
        else:
            step = 0

        for i in range(step, 10):
            await self.do_step(i)
            # Save checkpoint after each step
            await self.memory.store(
                key=f"checkpoint_{intent.id}",
                value={"step": i + 1},
                scope="working",
                intent_id=intent.id
            )

        return {"status": "complete", "steps": 10}
```

## YAML Workflow with Memory

```yaml
openintent: "1.0"
info:
  name: "Learning Pipeline"

memory:
  default_scope: episodic
  max_entries: 500
  eviction: lru
  ttl_seconds: 604800  # 7 days

workflow:
  observe:
    title: "Observe User Patterns"
    assign: observer
    memory:
      scope: episodic
      tags: [observation, user-behavior]

  learn:
    title: "Extract Insights"
    assign: learner
    depends_on: [observe]
    memory:
      scope: semantic
      namespace: insights

  apply:
    title: "Apply Insights"
    assign: applier
    depends_on: [learn]
    memory:
      scope: working
```

```python
from openintent.workflow import load_workflow

wf = load_workflow("learning_pipeline.yaml")
wf.run()
```
