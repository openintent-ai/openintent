# RFC-0020: Distributed Tracing

**Status:** Draft
**Created:** 2026-02-12
**Depends on:** RFC-0001 (Intent Objects), RFC-0018 (Cryptographic Agent Identity)

## Abstract

This RFC defines a lightweight, W3C-inspired distributed tracing mechanism for OpenIntent event logs. It adds two optional fields — `trace_id` and `parent_event_id` — to the Event Object (RFC-0001), enabling end-to-end visibility across recursive agent → tool → agent call chains. A `TracingContext` object propagates correlation state through the SDK, ensuring every event emitted during a traced execution is linked to its root cause and immediate parent.

## Motivation

### 1. No cross-agent visibility

When Agent A calls a tool that invokes Agent B, the resulting events appear as unrelated entries in the event log. There is no field linking Agent B's work back to the tool invocation that triggered it. Debugging requires manual timestamp correlation — which breaks at scale.

### 2. No recursive depth tracking

Agent A → Tool X → Agent B → Tool Y → Agent C produces five separate event sequences with no structural relationship. An operator looking at Agent C's events has no way to discover that the root cause was Agent A's original assignment.

### 3. Observability is table stakes

Modern distributed systems expect trace propagation as a baseline capability. Without `trace_id` correlation, OpenIntent event logs cannot integrate with observability platforms (Jaeger, Zipkin, OpenTelemetry) or provide the call-graph visualizations that operators need for debugging multi-agent workflows.

### 4. Cost attribution across chains

RFC-0009 (Cost Tracking) records costs per intent, but when an agent delegates work through tools to other agents, there is no way to attribute the total cost of a traced execution back to its originating intent. Trace IDs enable roll-up cost queries across the full call chain.

## Design Principles

1. **Optional and backward-compatible.** The new fields are optional on `IntentEvent`. Existing events without tracing fields remain valid. Servers that do not implement RFC-0020 ignore the fields.

2. **Propagation is automatic in the SDK.** The Python SDK propagates `TracingContext` through `_emit_tool_event`, tool handlers, and agent invocations without requiring user code changes.

3. **W3C-aligned identifiers.** `trace_id` uses 32-character lowercase hex (128-bit), matching the W3C Trace Context `trace-id` format. This enables direct export to OpenTelemetry-compatible systems.

4. **Self-contained.** No external tracing infrastructure is required. Trace data lives in the protocol's own event log and can be queried using standard event log APIs.

## Specification

### Event Object Extensions

Two optional fields are added to the Event Object (RFC-0001):

| Field | Type | Required | Description |
|---|---|---|---|
| `trace_id` | string (hex, 32 chars) | No | Correlation identifier shared by all events in a single traced execution. Generated at the root of a call chain and propagated to all descendant events. Format: 32 lowercase hexadecimal characters (128-bit). |
| `parent_event_id` | string | No | The `id` of the event that directly caused this event. For a tool invocation event triggered by an agent's assignment handler, the `parent_event_id` points to the assignment event. For an agent invoked by a tool, the `parent_event_id` points to the tool invocation event. |

### TracingContext Object

The SDK introduces a `TracingContext` dataclass for propagating tracing state:

```python
@dataclass
class TracingContext:
    trace_id: str           # 32-char hex, shared across the full call chain
    parent_event_id: str    # ID of the event that caused the current execution
```

**Generation rules:**
- A new `trace_id` is generated (via `uuid4().hex`) at the root of a call chain — typically when an agent receives an assignment and no existing `TracingContext` is present.
- `parent_event_id` is updated at each hop: when a tool invocation event is emitted, that event's ID becomes the `parent_event_id` for any downstream agent invocations.

### Propagation Rules

#### Agent Assignment → Tool Invocation

When an agent processes an assignment and invokes a tool:

1. If no `TracingContext` exists, create one with a fresh `trace_id` and the assignment event's ID as `parent_event_id`.
2. The `tool_invocation` event includes `trace_id` and `parent_event_id` in its payload.
3. The emitted event's own `id` becomes available for downstream propagation.

#### Tool Handler → Agent Invocation

When a tool handler invokes another agent:

1. The tool handler receives the current `TracingContext` (via the `tracing` keyword argument or the agent's `_tracing_context` attribute).
2. The downstream agent inherits the `TracingContext`, with `parent_event_id` updated to the tool invocation event's ID.
3. All events emitted by the downstream agent include the inherited `trace_id`.

#### Cross-Intent Tracing

When a tool invocation creates a new intent and assigns it to another agent:

1. The `trace_id` is included in the new intent's creation event payload as `trace_id`.
2. The `parent_event_id` references the tool invocation event from the originating intent.
3. This links events across intent boundaries while preserving per-intent event ordering.

### Event Log Payload Extensions

The `tool_invocation` event payload gains two fields:

```json
{
  "tool_name": "research",
  "arguments": {"query": "climate data"},
  "result": {"summary": "..."},
  "duration_ms": 142.5,
  "agent_id": "agent-a",
  "trace_id": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
  "parent_event_id": "evt-assignment-001"
}
```

### Query Support

Servers implementing RFC-0020 SHOULD support filtering events by `trace_id`:

```
GET /api/v1/events?trace_id={trace_id}
```

This returns all events across all intents that share the given `trace_id`, reconstructing the full call graph.

### TracingContext in YAML Workflows

YAML workflow definitions (RFC-0011) automatically receive tracing. Each workflow execution generates a root `trace_id`, and all agent assignments within the workflow inherit it. No additional YAML configuration is needed.

## SDK Implementation

### Python SDK

The `TracingContext` is stored on the agent instance as `_tracing_context` and propagated through:

1. `LLMEngine._emit_tool_event()` — includes `trace_id` and `parent_event_id` in the event payload.
2. `LLMEngine._execute_tool()` — passes `TracingContext` to local tool handlers via the `tracing` keyword argument (if the handler accepts it).
3. `log_event()` — both sync and async clients accept an optional `trace_id` and `parent_event_id` that are included in the event POST body.
4. Agent assignment handlers — when processing an assignment, the agent checks for `trace_id` in the assignment event's payload and creates or inherits a `TracingContext`.

### Extracting Call Graphs

Given a `trace_id`, a client can reconstruct the full call graph:

```python
events = client.get_events_by_trace(trace_id="a1b2c3d4...")
# Returns all events across all intents with this trace_id

# Build parent-child tree
tree = {}
for event in events:
    parent = event.payload.get("parent_event_id")
    tree.setdefault(parent, []).append(event)
```

## Interaction with Other RFCs

| RFC | Interaction |
|---|---|
| **RFC-0001** (Intent Objects) | Extends the Event Object with two optional fields. |
| **RFC-0009** (Cost Tracking) | Enables cost roll-up across a traced call chain by grouping cost events with the same `trace_id`. |
| **RFC-0012** (Task Decomposition) | Plan execution inherits `trace_id` from the coordinator, linking all task events to the original plan. |
| **RFC-0013** (Coordinator Governance) | Coordinator decision events include `trace_id` for end-to-end governance audit. |
| **RFC-0018** (Cryptographic Identity) | Signed events in a trace chain provide cryptographic proof of the call graph's authenticity. |
| **RFC-0019** (Verifiable Event Logs) | Traced events participate in hash chains normally. The `trace_id` and `parent_event_id` are included in the hash, binding the call graph to the verifiable log. |

## Security Considerations

- `trace_id` values are random 128-bit hex strings with no semantic content. They do not leak information about the agents, intents, or operations involved.
- Trace data is subject to the same access control as other event data (RFC-0011). An agent can only see traced events for intents it has access to.
- Malicious agents cannot forge `parent_event_id` references when RFC-0018 signing is enabled — the server validates that the referenced parent event exists and the signing agent had access to it.

## Backward Compatibility

- All new fields are optional. Existing events without `trace_id` or `parent_event_id` remain valid.
- Servers that do not implement RFC-0020 ignore the new fields in event payloads.
- The SDK generates `TracingContext` automatically but never requires it — agents without tracing continue to work exactly as before.
- The `log_event()` API signature change is backward-compatible (new parameters have default values of `None`).
