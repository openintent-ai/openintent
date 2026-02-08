---
title: Agent Lifecycle & Health
---

# Agent Lifecycle & Health

Agent Lifecycle manages registration, health monitoring, graceful shutdown, and agent pools. It provides the infrastructure for reliable multi-agent systems where agents can fail, restart, and scale independently. Defined in [RFC-0016](../rfcs/0016-agent-lifecycle-health.md).

## Agent Registration

Agents register with the server to declare their identity, capabilities, and capacity:

```python
# Register an agent
registration = client.agents.register(
    agent_id="research-agent-01",
    role_id="researcher",         # Shared role identity
    capabilities=["nlp", "web_search", "analysis"],
    capacity=5,                   # Can handle 5 concurrent intents
    metadata={"version": "2.1", "region": "us-east"}
)

print(f"Registered: {registration.agent_id}")
print(f"Status: {registration.status}")
```

### Instance vs Role Identity

| Concept | Description |
|---------|-------------|
| `agent_id` | Unique instance identity (e.g., `researcher-01`) |
| `role_id` | Shared role identity (e.g., `researcher`) |

Multiple agent instances can share the same `role_id`, forming an **agent pool**. When work is assigned to a role, any available instance with that role can pick it up.

## Heartbeats

Agents send periodic heartbeats to signal they are healthy:

```python
# Manual heartbeat
client.agents.heartbeat(agent_id="research-agent-01")
```

### Automatic Heartbeats

The `@Agent` decorator supports automatic heartbeats:

```python
from openintent.agents import Agent, on_assignment

@Agent("research-agent",
    auto_heartbeat=True,   # Sends heartbeats automatically
    capabilities=["nlp", "web_search"]
)
class ResearchAgent:

    @on_assignment
    async def handle(self, intent):
        # Heartbeats are sent in the background
        return {"result": await do_research(intent)}
```

## Status Lifecycle

```
active → unhealthy → dead
  ↓          ↓
draining   draining
  ↓
deregistered
```

| Status | Description |
|--------|-------------|
| `active` | Agent is healthy and accepting work |
| `unhealthy` | Missed heartbeats, may recover |
| `dead` | Too many missed heartbeats, leases expired |
| `draining` | Graceful shutdown in progress, finishing current work |
| `deregistered` | Agent has been removed from the registry |

### Jitter-Tolerant Thresholds

The protocol uses jitter-tolerant thresholds to prevent false positives from network hiccups:

- **Unhealthy threshold:** 2 missed heartbeats
- **Dead threshold:** 5 missed heartbeats
- **Heartbeat interval:** configurable (default 30s)

## Graceful Drain

When shutting down, agents drain gracefully — finishing current work without accepting new assignments:

```python
# Initiate graceful drain
client.agents.drain(
    agent_id="research-agent-01",
    timeout_seconds=300  # 5 minutes to finish current work
)
```

### Drain in Agents

```python
import signal

@Agent("graceful-worker", auto_heartbeat=True)
class GracefulWorker:

    @on_assignment
    async def handle(self, intent):
        return {"result": await process(intent)}

    @on_drain
    async def shutting_down(self):
        """Called when drain is initiated."""
        print("Finishing current work, not accepting new assignments...")
```

## Agent Pools

Multiple instances with the same `role_id` form a pool:

```python
# Register multiple instances of the same role
for i in range(3):
    client.agents.register(
        agent_id=f"researcher-{i:02d}",
        role_id="researcher",
        capabilities=["nlp", "search"],
        capacity=3
    )

# Assign work to the role — any available instance picks it up
intent = client.create_intent(
    title="Research competitors",
    assign="researcher"  # Role, not instance
)
```

## Querying Agent Status

```python
# Get agent status
status = client.agents.get_status(agent_id="research-agent-01")
print(f"Status: {status.status}")
print(f"Last heartbeat: {status.last_heartbeat}")
print(f"Active leases: {status.active_lease_count}")

# List all agents with a specific role
agents = client.agents.list(role_id="researcher")
for a in agents:
    print(f"{a.agent_id}: {a.status} ({a.active_lease_count} active)")
```

## Death Triggers

When an agent transitions to `dead`, the protocol automatically:

1. **Expires all active leases** (RFC-0003) — scopes become available for other agents
2. **Triggers lifecycle events** — other agents are notified
3. **Preserves working memory** (RFC-0015) — new instances can resume

## Agents in YAML Workflows

```yaml
agents:
  researcher:
    description: "Research agent"
    capabilities: [nlp, web_search]
    capacity: 5
    heartbeat_interval: 30
    pool_size: 3

  writer:
    description: "Content writer"
    capabilities: [writing, editing]
    default_permission: write
    approval_required: false
```

!!! info "Registration is optional"
    Standalone agents (e.g., those using direct tool grants via RFC-0014) can operate without registration. Registration is required for agent pools and health monitoring.

## Next Steps

- [Agent Memory](memory.md) — Memory continuity across agent restarts
- [Leasing & Concurrency](leasing.md) — Lease expiry on agent death
- [Agent Abstractions](agents.md) — `@on_drain` and lifecycle decorators
