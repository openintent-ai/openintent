# RFC-0002: Intent Graphs v1.0

**Status:** Proposed  
**Created:** 2026-02-01  
**Authors:** OpenIntent Contributors  
**Requires:** [RFC-0001 (Intents)](./0001-intent-objects.md)

---

## Abstract

This RFC extends the OpenIntent protocol with support for hierarchical intent relationships and dependency graphs. It introduces `parent_intent_id` for parent-child nesting and `depends_on` for expressing execution dependencies between intents. Together, these enable complex goal decomposition with proper coordination semantics.

## Motivation

Complex goals naturally decompose into sub-goals with dependencies. Consider incident response:

```
"Resolve Production Outage" (parent)
├── "Diagnose Root Cause"
├── "Customer Communication" (parallel, no dependencies)
├── "Implement Hotfix" (depends_on: Diagnose)
├── "Deploy Fix" (depends_on: Diagnose, Implement)
├── "Verify Resolution" (depends_on: Deploy)
└── "Post-Mortem" (depends_on: ALL above)
```

This structure requires:

- **Hierarchical nesting:** Sub-intents belong to a parent intent
- **Parallel execution:** Independent tasks can run concurrently
- **Dependency gates:** Some tasks must wait for others to complete
- **Aggregate completion:** Parent completes when all children complete

## Data Model Extensions

Intent objects are extended with two new fields:

```json
{
  "id": "uuid",
  "title": "string",
  "description": "string | null",
  "status": "draft | active | blocked | completed | abandoned",
  "state": { },
  "version": "integer",

  "parent_intent_id": "uuid | null",
  "depends_on": ["uuid", "uuid"]
}
```

**parent_intent_id**
:   Optional reference to a parent intent. Creates a hierarchical tree structure. Child intents inherit context from their parent and contribute to parent's aggregate status.

**depends_on**
:   Array of intent IDs that must complete before this intent can transition to `completed`. Creates a directed acyclic graph (DAG) of execution dependencies.

## DAG Semantics

Intent graphs MUST form valid directed acyclic graphs (DAGs):

- **Acyclic:** No circular dependencies allowed. Server MUST reject cycles with `400 Bad Request`
- **Dependency validation:** All IDs in `depends_on` MUST reference existing intents
- **Parent validation:** `parent_intent_id` MUST reference an existing intent or be null
- **Self-reference prohibited:** An intent cannot depend on or parent itself

## Status Transition Rules

Dependencies affect status transitions:

- **Blocked by dependencies:** An intent with incomplete dependencies is automatically `blocked`
- **Auto-unblock:** When all dependencies complete, intent transitions from `blocked` to `active`
- **Completion gate:** Cannot transition to `completed` until all dependencies are `completed`
- **Parent completion:** Parent intent cannot complete until all children complete
- **Cascade abandonment:** Abandoning a parent MAY cascade to children (configurable)

```
draft → active (if no unmet dependencies, else → blocked)
blocked → active (when dependencies resolve)
active → completed (if all dependencies + children completed)
active → blocked (if dependency becomes incomplete)
any → abandoned
```

## Aggregate Status

Parent intents track aggregate status of their children:

```json
{
  "aggregate_status": {
    "total": 6,
    "by_status": {
      "completed": 3,
      "active": 2,
      "blocked": 1
    },
    "completion_percentage": 50,
    "blocking_intents": ["intent-uuid-1"],
    "ready_intents": ["intent-uuid-2", "intent-uuid-3"]
  }
}
```

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/v1/intents/{id}/children` | Create a child intent under parent |
| `GET` | `/v1/intents/{id}/children` | List immediate children of an intent |
| `GET` | `/v1/intents/{id}/descendants` | List all descendants (recursive) |
| `GET` | `/v1/intents/{id}/ancestors` | List all ancestors up to root |
| `GET` | `/v1/intents/{id}/dependencies` | List dependency intents |
| `GET` | `/v1/intents/{id}/dependents` | List intents depending on this one |
| `GET` | `/v1/intents/{id}/graph` | Get full intent graph from this node |
| `POST` | `/v1/intents/{id}/dependencies` | Add dependencies to an intent |
| `DELETE` | `/v1/intents/{id}/dependencies/{dep_id}` | Remove a dependency |

## Python SDK Usage

```python
from openintent import OpenIntentClient

client = OpenIntentClient(
    base_url="http://localhost:8000",
    api_key="key",
    agent_id="coordinator"
)

# Create parent intent (incident response)
parent = client.create_intent(
    title="Resolve Production Outage",
    description="Critical: API returning 500 errors"
)

# Create child intents with dependencies
diagnose = client.create_child_intent(
    parent_id=parent.id,
    title="Diagnose Root Cause"
)

communicate = client.create_child_intent(
    parent_id=parent.id,
    title="Customer Communication"
)

hotfix = client.create_child_intent(
    parent_id=parent.id,
    title="Implement Hotfix",
    depends_on=[diagnose.id]  # Must diagnose first
)

deploy = client.create_child_intent(
    parent_id=parent.id,
    title="Deploy Fix",
    depends_on=[diagnose.id, hotfix.id]  # Multi-dependency gate
)

# Query the graph
children = client.get_children(parent.id)
deps = client.get_dependencies(deploy.id)  # Returns [diagnose, hotfix]
ready = client.get_ready_intents(parent.id)  # Unblocked intents
```

## Why Intent Graphs Matter

- **Complex goal decomposition:** Break large goals into manageable, trackable sub-goals
- **Coordination semantics:** Dependencies prevent race conditions and ensure correct ordering
- **Progress visibility:** Aggregate status shows overall completion percentage
- **Multi-agent orchestration:** Different agents can work on different branches in parallel
- **Audit trail:** Parent-child relationships provide clear provenance for all work
