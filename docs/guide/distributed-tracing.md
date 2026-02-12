---
title: Distributed Tracing
---

# Distributed Tracing

RFC-0020 adds end-to-end distributed tracing to multi-agent workflows. Every event can carry a `trace_id` (shared across the entire workflow) and a `parent_event_id` (linking back to the event that caused it). Together they form a call tree that shows exactly how a user request flowed through agents and tools.

## Key Concepts

- **Trace** — A complete execution graph for a single workflow, identified by a 128-bit hex ID (W3C-aligned).
- **Span** — A single unit of work within a trace, represented by an IntentEvent with `trace_id` and `parent_event_id`.
- **TracingContext** — A dataclass that carries correlation state automatically through the SDK.
- **Root Span** — The first event in a trace, with `parent_event_id` set to `None`.

## TracingContext

The SDK provides `TracingContext` for propagating trace state:

```python
from openintent import TracingContext

# Start a new trace
ctx = TracingContext.new_root()
print(ctx.trace_id)  # 128-bit hex, e.g. "4bf92f3577b34da6a3ce929d0e0e4736"

# After emitting an event, create a child context
child_ctx = ctx.child(event_id="evt_001")
print(child_ctx.parent_event_id)  # "evt_001"

# Serialize / deserialize
data = ctx.to_dict()
restored = TracingContext.from_dict(data)  # Returns None if trace_id missing
```

## Automatic Propagation

Tracing propagates automatically through three mechanisms — no user code changes required:

### 1. Tool Event Emission

When an agent executes a tool, `_emit_tool_event` reads the agent's `_tracing_context` and includes `trace_id` and `parent_event_id` in the event. After emission, the context updates via `child()`.

### 2. Tool Handler Injection

`_execute_tool` inspects each local tool handler's signature. If it accepts a `tracing` keyword argument, the current `TracingContext` is injected automatically:

```python
from openintent import TracingContext

# This handler receives tracing context automatically
async def delegate_research(query: str, tracing: TracingContext = None):
    sub_agent = ResearchAgent(tracing_context=tracing)
    return await sub_agent.run(query)

# Normal tools work exactly as before — no changes needed
def simple_calculator(expression: str):
    return {"result": eval(expression)}
```

### 3. Client-Level Tracing

Both sync and async clients accept optional `trace_id` and `parent_event_id` on `log_event()`:

```python
client.log_event(
    intent_id="intent-123",
    event_type="analysis_complete",
    payload={"result": "done"},
    trace_id="4bf92f3577b34da6a3ce929d0e0e4736",
    parent_event_id="evt_001",
)
```

## Call Chain Example

A typical multi-agent workflow produces a trace tree like this:

```text
Trace: 4bf92f3577b34da6a3ce929d0e0e4736

User Request
└── Coordinator Agent
    ├── tool_invocation: web_search          (evt_001, parent: null)
    ├── tool_invocation: delegate_research   (evt_002, parent: evt_001)
    │   └── Research Agent
    │       ├── tool_invocation: fetch_data  (evt_003, parent: evt_002)
    │       └── tool_invocation: summarize   (evt_004, parent: evt_003)
    └── tool_invocation: format_response     (evt_005, parent: evt_004)
```

Every event shares the same `trace_id`. The `parent_event_id` chain reveals causality.

## Querying Traces

```python
from openintent import OpenIntentClient

client = OpenIntentClient(base_url="...", api_key="...")

# Get all events in a trace
events = client.list_events(trace_id="4bf92f3577b34da6a3ce929d0e0e4736")

# Build the call tree
roots = [e for e in events if e.parent_event_id is None]
children = {e.id: [c for c in events if c.parent_event_id == e.id] for e in events}

# Find trace depth
def depth(event_id):
    kids = children.get(event_id, [])
    return 1 + max((depth(k.id) for k in kids), default=0)

print(f"Trace depth: {depth(roots[0].id)}, total events: {len(events)}")
```

## Decorator Approach

Agents created with `@Agent` automatically participate in tracing when a `TracingContext` is set on the agent:

```python
from openintent import Agent, on_assignment, TracingContext

@Agent("traced-agent")
class TracedAgent:
    @on_assignment
    async def handle(self, intent):
        # Tracing context is automatically propagated to tool calls
        result = await self.think("Analyze this data")
        return result
```

## Event Extension

IntentEvent (RFC-0001) gains two optional fields:

| Field | Type | Description |
|-------|------|-------------|
| `trace_id` | `string \| null` | 128-bit hex identifier. All events in the same workflow share this value. |
| `parent_event_id` | `string \| null` | The event ID that caused this event. `null` for root spans. |

Both fields are optional for backward compatibility — events without them behave exactly as before.
