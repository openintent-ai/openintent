---
title: Agent Memory
---

# Agent Memory

Agent Memory provides persistent state that survives across tasks, sessions, and agent restarts. The three-tier model — working, episodic, and semantic — gives agents short-term task context, long-term recall, and shared knowledge. Defined in [RFC-0015](../rfcs/0015-agent-memory-persistent-state.md).

## Memory Tiers

| Tier | Scope | Lifetime | Use Case |
|------|-------|----------|----------|
| `working` | Task-scoped | Archived when task completes | Scratch state, intermediate results |
| `episodic` | Agent-scoped | LRU eviction, pinnable | Past experiences, learned patterns |
| `semantic` | Shared namespace | Namespace-level permissions | Shared knowledge base, reference data |

## Storing Memories

```python
# Store a memory entry
client.memory.store(
    agent_id="researcher",
    key="competitor-analysis-2026",
    value={
        "competitors": ["Acme", "Globex", "Initech"],
        "market_share": {"Acme": 0.35, "Globex": 0.28, "Initech": 0.15}
    },
    tier="episodic",
    tags=["research", "competitors", "2026"]
)
```

### Memory Entry Structure

Each entry is a structured key-value pair:

| Field | Description |
|-------|-------------|
| `key` | Unique identifier within the agent's namespace |
| `value` | JSON-serializable data |
| `tier` | `working`, `episodic`, or `semantic` |
| `tags` | List of strings for filtering and retrieval |
| `ttl` | Optional time-to-live in seconds |
| `version` | Optimistic concurrency version |

## Recalling Memories

```python
# Recall by tags
memories = client.memory.recall(
    agent_id="researcher",
    tags=["research", "competitors"]
)

for m in memories:
    print(f"{m.key}: {m.value}")

# Get a specific entry
entry = client.memory.get(
    agent_id="researcher",
    key="competitor-analysis-2026"
)
```

## Using Memory in Agents

The `@Agent` decorator provides a `self.memory` proxy:

```python
from openintent.agents import Agent, on_assignment

@Agent("learning-agent",
    memory="episodic",            # Default tier for this agent
    memory_namespace="research"   # Namespace for shared access
)
class LearningAgent:

    @on_assignment
    async def handle(self, intent):
        # Recall past findings
        past = await self.memory.recall(tags=["research"])

        # Do work informed by past experience
        findings = await research(intent.description, context=past)

        # Store for future recall
        await self.memory.store(
            key=f"research-{intent.id}",
            value=findings,
            tags=["research", intent.title]
        )

        return {"findings": findings}
```

## Declarative Memory Configuration

Use the `@Memory` decorator for configuration classes:

```python
from openintent.agents import Memory

@Memory(
    namespace="research",
    tier="episodic",
    ttl=86400 * 30,     # 30-day TTL
    max_entries=1000     # LRU eviction after 1000 entries
)
class ResearchMemory:
    findings = {"tags": ["research"], "pinned": True}
    sources = {"tags": ["sources"]}
```

## Pinning Entries

Pinned entries are exempt from LRU eviction:

```python
# Pin an important memory
await client.memory.pin(
    agent_id="researcher",
    key="critical-insight-2026"
)

# Pinned entries survive LRU eviction
```

## Working Memory

Working memory is task-scoped and auto-archived when the task completes:

```python
@Agent("stateful-worker", memory="working")
class StatefulWorker:

    @on_assignment
    async def handle(self, intent):
        # Store intermediate results in working memory
        await self.memory.store(
            key="step-1-result",
            value={"partial": "data"},
            tier="working"
        )

        # Later steps can read working memory
        step1 = await self.memory.get(key="step-1-result")

        # Working memory is archived when task completes
        return {"final_result": process(step1.value)}
```

## Semantic Memory (Shared)

Semantic memory is shared across agents within a namespace:

```python
# Agent A stores shared knowledge
client.memory.store(
    agent_id="agent-a",
    key="product-specs",
    value={"version": "3.0", "features": [...]},
    tier="semantic",
    namespace="product-team"
)

# Agent B can read it (if namespace permissions allow)
specs = client.memory.get(
    agent_id="agent-b",
    key="product-specs",
    namespace="product-team"
)
```

## Memory in YAML Workflows

```yaml
memory:
  namespace: project-alpha
  tier: episodic
  ttl: 2592000          # 30 days
  max_entries: 5000

workflow:
  research:
    assign: researcher
    memory:
      tier: working     # Override for this phase
      handoff: true     # Pass working memory to next phase

  synthesis:
    assign: synthesizer
    depends_on: [research]
    memory:
      tier: episodic
```

!!! tip "Agent resumability"
    When an agent restarts or is replaced, working memory enables the new instance to pick up where the previous one left off. See [Agent Lifecycle](lifecycle.md) for details.

## Next Steps

- [Agent Lifecycle](lifecycle.md) — Agent restarts and memory continuity
- [Agent Abstractions](agents.md) — `@Memory` decorator reference
- [Credential Vaults & Tools](vaults.md) — Secure storage for credentials
