# Working with Intents

Intents are the core data structure in OpenIntent - they represent goals with state, status, and an audit trail.

## Intent Lifecycle

```
draft → active → completed
              ↘ abandoned
         ↓
      blocked
```

### Statuses

| Status | Description |
|--------|-------------|
| `draft` | Intent created but not yet active |
| `active` | Intent is being worked on |
| `blocked` | Waiting on dependencies or human input |
| `completed` | Goal achieved successfully |
| `abandoned` | Intent was cancelled |

## Creating Intents

```python
from openintent import OpenIntentClient

client = OpenIntentClient(base_url="http://localhost:8000", agent_id="my-agent")

# Basic intent
intent = client.create_intent(
    title="Research competitors",
    description="Analyze top 5 competitors in the market"
)

# Intent with initial state
intent = client.create_intent(
    title="Process data",
    initial_state={"rows_processed": 0, "errors": []}
)

# Intent with constraints
intent = client.create_intent(
    title="Book flight",
    constraints={"max_budget": 500, "airline": "any"}
)
```

## Managing State

State is a JSON object that agents can read and update:

```python
# Patch state (merge with existing)
updated = client.patch_state(
    intent.id,
    {"progress": 0.5, "items_found": 10}
)

# Replace entire state
updated = client.update_state(
    intent.id,
    {"status": "complete", "result": "..."}
)
```

### Optimistic Concurrency

OpenIntent uses version numbers to prevent conflicting updates:

```python
# Get current intent
intent = client.get_intent(intent_id)
print(f"Version: {intent.version}")  # 1

# Update state
updated = client.patch_state(intent.id, {"step": 2})
print(f"Version: {updated.version}")  # 2

# Stale update will fail with ConflictError
```

## Intent Graphs (RFC-0002)

Create hierarchical structures with parent-child relationships:

```python
# Create parent intent
parent = client.create_intent(title="Complete project")

# Create child intents
research = client.create_intent(
    title="Research phase",
    parent_intent_id=parent.id
)

analysis = client.create_intent(
    title="Analysis phase",
    parent_intent_id=parent.id,
    depends_on=[research.id]  # Waits for research
)
```

### Dependencies

Dependencies ensure intents execute in order:

```python
# This intent is blocked until research completes
synthesis = client.create_intent(
    title="Synthesize findings",
    depends_on=[research.id, analysis.id]
)

# Check status
print(synthesis.status)  # "blocked"
```

## Completing Intents

```python
# Mark as completed
completed = client.complete_intent(intent.id)

# Mark as abandoned
abandoned = client.abandon_intent(intent.id)
```

## Next Steps

- [Events](events.md) - Log and query events
- [Agent Abstractions](agents.md) - Build agents with decorators
