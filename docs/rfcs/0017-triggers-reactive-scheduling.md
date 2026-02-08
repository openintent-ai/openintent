# RFC-0017: Triggers & Reactive Scheduling

- **Status:** Proposed
- **Created:** 2026-02-08
- **Authors:** OpenIntent Contributors
- **Depends on:** RFC-0001, RFC-0006, RFC-0011, RFC-0012, RFC-0013, RFC-0016

## Abstract

This RFC defines triggers — standing declarations that create intents when a condition is met. Triggers are the protocol's starting gun: they close the gap between "something happened" and "work begins." Three trigger types are specified — schedule (time-based), event (protocol-reactive), and webhook (external) — each producing intents through the same creation path. Triggers are global first-class objects with cascading namespace governance. Deduplication semantics, trigger-to-intent lineage, and YAML workflow integration are formally specified.

## Motivation

The protocol currently defines how work is coordinated (intents, leasing, graphs, governance) and who does it (agents, capabilities, lifecycle). What it does not define is **what causes work to begin.** Today, intents are created by external API calls — a human, a script, or another system sends a POST to `/api/v1/intents`. This works, but it leaves the "why did this intent appear?" question outside the protocol's audit boundary.

This creates several coordination gaps:

1. **No autonomous initiation.** An agent cannot express "start a compliance review every Monday." The protocol has no concept of recurring or conditional work creation. Scheduling lives outside the system, invisible to governance and audit.

2. **No reactive chaining.** When an intent resolves, there is no protocol-level mechanism to say "now create this follow-up." Intent graphs (RFC-0012) define decomposition within a plan, but cross-workflow reactions — "when billing completes, trigger a receipt email" — require external glue code.

3. **No external event bridge.** When an external system fires a webhook (a payment, a deployment, a document upload), there is no standardized way to translate that event into protocol-level work. Each implementation invents its own adapter.

4. **No trigger audit trail.** Even when external schedulers or event systems create intents, the causal link between "what triggered this" and "the intent that was created" is not captured. Governance (RFC-0013) cannot answer "why does this intent exist?"

5. **Incomplete runloop.** With RFC-0016 (agent lifecycle), agents can register, heartbeat, and drain. With RFC-0003 (leasing), they can claim work. But without triggers, the runloop has no entry point. The protocol describes a machine with no ignition.

## Specification

### 1. Trigger Record

A trigger is a first-class protocol object. It declares a condition and an intent template. When the condition is met, the server creates an intent from the template.

```json
{
  "trigger_id": "trg_daily_compliance",
  "name": "Daily Compliance Review",
  "type": "schedule",
  "enabled": true,
  "condition": {
    "cron": "0 9 * * MON-FRI"
  },
  "intent_template": {
    "type": "compliance.review",
    "title": "Daily compliance review",
    "priority": "medium",
    "context": {
      "scope": "all-departments"
    }
  },
  "deduplication": "skip",
  "namespace": null,
  "created_at": "2026-02-08T10:00:00Z",
  "updated_at": "2026-02-08T10:00:00Z",
  "last_fired_at": null,
  "fire_count": 0,
  "version": 1
}
```

#### 1.1 Fields

| Field | Type | Description |
|---|---|---|
| `trigger_id` | string | Unique identifier. Server-assigned, prefixed `trg_`. |
| `name` | string | Human-readable label. |
| `type` | enum | One of: `schedule`, `event`, `webhook`. |
| `enabled` | boolean | Whether the trigger is active. Disabled triggers are retained but do not fire. |
| `condition` | object | Type-specific condition. See Sections 2, 3, 4. |
| `intent_template` | object | Template for the intent to create. See Section 5. |
| `deduplication` | enum | How to handle firing when a matching intent is already active. One of: `allow`, `skip`, `queue`. Default: `allow`. |
| `namespace` | string or null | If set, the trigger only creates intents within this namespace. If null, the trigger is global. |
| `created_at` | datetime | When the trigger was created. |
| `updated_at` | datetime | Last modification time. |
| `last_fired_at` | datetime or null | When the trigger last created an intent. Null if never fired. |
| `fire_count` | integer | Total number of times this trigger has fired. |
| `version` | integer | Optimistic concurrency version. Incremented on every update. |

### 2. Schedule Triggers

Schedule triggers fire at time-based intervals. The condition specifies when.

#### 2.1 Condition Schema

```json
{
  "cron": "0 9 * * MON-FRI",
  "timezone": "UTC",
  "starts_at": "2026-02-08T00:00:00Z",
  "ends_at": null
}
```

| Field | Type | Description |
|---|---|---|
| `cron` | string | Standard 5-field cron expression. Required. |
| `timezone` | string | IANA timezone for cron evaluation. Default: `UTC`. |
| `starts_at` | datetime or null | Earliest time the trigger can fire. Null means immediately. |
| `ends_at` | datetime or null | Latest time the trigger can fire. Null means indefinitely. |

#### 2.2 Semantics

- The server evaluates cron expressions and fires the trigger at the next matching time.
- If the server is unavailable at the scheduled time, it fires on the next evaluation cycle. Missed firings are not retroactively created unless the implementation explicitly supports backfill.
- `starts_at` and `ends_at` define a time window. Outside this window, the trigger behaves as if disabled.

#### 2.3 One-Time Schedules

For one-time execution, use a cron expression that matches once, or set `starts_at` and `ends_at` to the same value. Implementations may also support a shorthand:

```json
{
  "at": "2026-03-01T14:00:00Z"
}
```

When `at` is present, `cron` is ignored. The trigger fires once at the specified time and is automatically disabled after firing.

### 3. Event Triggers

Event triggers fire in response to protocol-observable events — state transitions, agent lifecycle changes, or subscription notifications.

#### 3.1 Condition Schema

```json
{
  "event": "intent.state_changed",
  "filter": {
    "to_state": "resolved",
    "intent_type": "billing.*"
  }
}
```

| Field | Type | Description |
|---|---|---|
| `event` | string | The protocol event type to listen for. Required. |
| `filter` | object | Key-value pairs that the event payload must match. Supports exact match and glob patterns (e.g., `billing.*`). Optional — if omitted, the trigger fires on every occurrence of the event type. |

#### 3.2 Standard Event Types

The protocol defines the following event types that event triggers can listen for:

| Event Type | Fires When | Payload Keys |
|---|---|---|
| `intent.created` | A new intent is created | `intent_id`, `type`, `priority`, `namespace` |
| `intent.state_changed` | An intent transitions state | `intent_id`, `from_state`, `to_state`, `type` |
| `intent.resolved` | An intent reaches `resolved` | `intent_id`, `type`, `resolution` |
| `intent.failed` | An intent reaches `failed` | `intent_id`, `type`, `error` |
| `intent.stalled` | An intent exceeds its expected duration | `intent_id`, `type`, `stalled_since` |
| `agent.registered` | An agent registers (RFC-0016) | `agent_id`, `role_id`, `capabilities` |
| `agent.status_changed` | An agent's status changes | `agent_id`, `from_status`, `to_status` |
| `agent.dead` | An agent is declared dead | `agent_id`, `role_id`, `last_heartbeat` |
| `lease.expired` | A lease expires without renewal | `lease_id`, `intent_id`, `agent_id` |
| `lease.claimed` | An agent claims a lease | `lease_id`, `intent_id`, `agent_id` |
| `trigger.fired` | Another trigger fires | `trigger_id`, `created_intent_id` |

Implementations may extend this list with custom event types prefixed by `x-`.

#### 3.3 Cascading Event Triggers

Event triggers can reference other triggers' firings (`trigger.fired`), enabling trigger chains. To prevent infinite loops, the server must enforce a maximum cascade depth (default: 10). When the depth is exceeded, the trigger is suppressed and a `trigger.cascade_limit` event is emitted.

Each intent created by a trigger carries a `trigger_depth` field in its metadata. The first trigger in a chain sets `trigger_depth: 1`. Each subsequent trigger increments it by 1.

### 4. Webhook Triggers

Webhook triggers fire when an external HTTP request is received at a trigger-specific endpoint.

#### 4.1 Condition Schema

```json
{
  "path": "/hooks/stripe-payment",
  "method": "POST",
  "secret": "whsec_...",
  "transform": {
    "amount": "{{ body.data.object.amount }}",
    "customer_id": "{{ body.data.object.customer }}"
  }
}
```

| Field | Type | Description |
|---|---|---|
| `path` | string | URL path suffix for the webhook endpoint. The full URL is implementation-defined (e.g., `https://api.example.com/webhooks/hooks/stripe-payment`). Required. |
| `method` | string | HTTP method to accept. Default: `POST`. |
| `secret` | string or null | Shared secret for webhook signature verification. Verification method is implementation-defined. Optional. |
| `transform` | object | Template expressions that extract fields from the incoming request and inject them into the intent's context. Uses `{{ body.field }}`, `{{ headers.field }}`, `{{ query.field }}` syntax. Optional. |

#### 4.2 Semantics

- The server exposes webhook endpoints based on registered webhook triggers.
- When a request arrives, the server matches it to a trigger by path and method.
- If `secret` is set, the server verifies the request signature. Verification failure returns HTTP 401 and does not fire the trigger.
- If `transform` is set, the server extracts values from the request and injects them into the intent template's context.
- The server returns HTTP 202 Accepted with the created intent's ID in the response body.
- If deduplication prevents intent creation, the server returns HTTP 200 OK with a `deduplicated: true` field.

#### 4.3 Webhook Security

Webhook endpoints are unauthenticated by default (they are designed for external callers). Security is provided through:

1. **Signature verification** via the `secret` field (implementation-specific — e.g., HMAC-SHA256).
2. **Path obscurity** — implementations may generate random path suffixes.
3. **Rate limiting** — implementations should enforce per-trigger rate limits.
4. **IP allowlists** — implementations may restrict source IPs.

The protocol does not mandate a specific verification mechanism. It requires that the `secret` field is never exposed in API responses (write-only).

### 5. Intent Template

The intent template defines the shape of the intent created when a trigger fires.

```json
{
  "type": "compliance.review",
  "title": "Weekly compliance review",
  "priority": "medium",
  "assignee": null,
  "context": {
    "scope": "all-departments",
    "source_trigger": "{{ trigger.trigger_id }}",
    "fired_at": "{{ trigger.fired_at }}"
  },
  "graph_id": null,
  "tags": ["automated", "compliance"]
}
```

#### 5.1 Template Expressions

Template expressions use `{{ }}` syntax to inject dynamic values. Available variables:

| Variable | Description |
|---|---|
| `trigger.trigger_id` | The trigger's ID. |
| `trigger.name` | The trigger's name. |
| `trigger.type` | The trigger type (`schedule`, `event`, `webhook`). |
| `trigger.fired_at` | ISO 8601 timestamp of when the trigger fired. |
| `trigger.fire_count` | How many times the trigger has fired (including this time). |
| `event.*` | For event triggers: the full event payload. |
| `body.*` | For webhook triggers: the request body. |
| `headers.*` | For webhook triggers: request headers. |
| `query.*` | For webhook triggers: query string parameters. |

#### 5.2 Lineage

Every intent created by a trigger includes lineage metadata:

```json
{
  "created_by": "trigger",
  "trigger_id": "trg_daily_compliance",
  "trigger_type": "schedule",
  "trigger_depth": 1,
  "trigger_chain": ["trg_daily_compliance"]
}
```

- `created_by` distinguishes trigger-created intents from manually-created ones.
- `trigger_chain` records the sequence of triggers in a cascade (for chained event triggers).
- This lineage is immutable and append-only.

### 6. Deduplication

When a trigger fires, there may already be an active intent that matches the template. The `deduplication` field controls behavior:

| Mode | Behavior |
|---|---|
| `allow` | Always create a new intent. No deduplication check. This is the default. |
| `skip` | If an active (non-resolved, non-failed) intent with the same `type` exists within the same namespace, do not create a new one. Record a `trigger.skipped` event. |
| `queue` | If an active intent exists, defer creation. When the existing intent resolves or fails, fire the trigger again. Maximum queue depth: 1 (only one pending fire is retained). |

#### 6.1 Deduplication Scope

Deduplication checks are scoped to the trigger's namespace. If the trigger is global (`namespace: null`), deduplication checks all active intents of the matching type across all namespaces. If the trigger has a namespace, deduplication checks only within that namespace.

### 7. Cascading Namespace Governance

Triggers are global first-class objects. Namespaces govern how triggers apply within their boundary.

#### 7.1 Global vs. Namespace Triggers

- **Global triggers** (`namespace: null`): Fire and create intents in the default namespace, or in a namespace specified by the intent template. Subject to namespace governance rules.
- **Namespace triggers** (`namespace: "billing"`): Fire and create intents only within the specified namespace. The namespace owns the trigger.

#### 7.2 Namespace Trigger Policy

A namespace can declare a trigger policy that governs which triggers are allowed to create intents within it:

```json
{
  "namespace": "eu-operations",
  "trigger_policy": {
    "allow_global_triggers": true,
    "allowed_trigger_types": ["schedule", "event"],
    "blocked_triggers": ["trg_us_only_report"],
    "context_injection": {
      "region": "EU",
      "gdpr_required": true
    }
  }
}
```

| Field | Type | Description |
|---|---|---|
| `allow_global_triggers` | boolean | Whether global triggers can create intents in this namespace. Default: `true`. |
| `allowed_trigger_types` | array or null | Whitelist of trigger types (`schedule`, `event`, `webhook`). Null means all types allowed. |
| `blocked_triggers` | array | Specific trigger IDs that are blocked from this namespace. |
| `context_injection` | object | Additional context fields injected into intents created by triggers within this namespace. Merged with the intent template's context (namespace values take precedence on conflict). |

#### 7.3 Cascade Resolution

When a global trigger fires:

1. The server evaluates the intent template's target namespace (explicit or default).
2. The server checks the target namespace's trigger policy.
3. If the policy blocks the trigger (by type, by ID, or by `allow_global_triggers: false`), the trigger is suppressed for that namespace. A `trigger.namespace_blocked` event is emitted.
4. If the policy allows the trigger, context injection is applied and the intent is created.

This ensures global triggers cascade down by default, but namespaces retain local authority.

### 8. API

#### 8.1 Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/triggers` | Create a trigger. |
| `GET` | `/api/v1/triggers` | List all triggers. Supports `?type=`, `?enabled=`, `?namespace=` filters. |
| `GET` | `/api/v1/triggers/:trigger_id` | Get a trigger by ID. |
| `PATCH` | `/api/v1/triggers/:trigger_id` | Update a trigger. Supports `If-Match` for optimistic concurrency. |
| `DELETE` | `/api/v1/triggers/:trigger_id` | Delete a trigger. Active intents created by this trigger are not affected. |
| `POST` | `/api/v1/triggers/:trigger_id/fire` | Manually fire a trigger (for testing and debugging). |
| `GET` | `/api/v1/triggers/:trigger_id/history` | Get the trigger's fire history (list of created intent IDs with timestamps). |

#### 8.2 Create Trigger

```http
POST /api/v1/triggers
Content-Type: application/json

{
  "name": "Daily Compliance Review",
  "type": "schedule",
  "condition": {
    "cron": "0 9 * * MON-FRI",
    "timezone": "America/New_York"
  },
  "intent_template": {
    "type": "compliance.review",
    "title": "Daily compliance review",
    "priority": "medium"
  },
  "deduplication": "skip",
  "namespace": null
}
```

Response: `201 Created` with the full trigger record.

#### 8.3 Manual Fire

```http
POST /api/v1/triggers/trg_daily_compliance/fire
```

Response: `201 Created` with the created intent. This bypasses the trigger's condition but respects deduplication rules and namespace governance.

#### 8.4 Webhook Receive

```http
POST /webhooks/hooks/stripe-payment
Content-Type: application/json

{ "type": "payment_intent.succeeded", "data": { "object": { "amount": 5000 } } }
```

Response: `202 Accepted` with `{ "intent_id": "intent_...", "trigger_id": "trg_..." }`.

### 9. Trigger Lifecycle

#### 9.1 States

Triggers have a simple lifecycle:

| State | Description |
|---|---|
| `enabled` | Active and will fire when its condition is met. |
| `disabled` | Retained but will not fire. Can be re-enabled. |
| `deleted` | Permanently removed. Fire history is retained for audit. |

#### 9.2 Pause and Resume

Triggers can be paused (disabled) and resumed (enabled) via `PATCH`:

```http
PATCH /api/v1/triggers/trg_daily_compliance
Content-Type: application/json
If-Match: "1"

{ "enabled": false }
```

This is useful for maintenance windows, incident response, or temporary suspension without losing configuration.

### 10. Integration with Other RFCs

| RFC | Integration |
|---|---|
| RFC-0001 (Intents) | Triggers create intents through the standard creation path. All intent semantics (state machine, events, versioning) apply. |
| RFC-0006 (Subscriptions) | Subscription notifications can be event sources for event triggers. A subscription matching `billing.*` can trigger follow-up work. |
| RFC-0011 (Access Control) | Namespace trigger policies extend RFC-0011's permission model. Trigger creation requires appropriate namespace permissions. |
| RFC-0012 (Task Decomposition) | A trigger can create a top-level intent that initiates a plan. The trigger fires once; the plan handles decomposition. |
| RFC-0013 (Coordinator Governance) | Coordinators can define guardrails on trigger creation (e.g., "no webhook triggers in production namespace"). Trigger fire events are subject to governance audit. |
| RFC-0016 (Agent Lifecycle) | Agent lifecycle events (`agent.registered`, `agent.dead`) are event sources for event triggers. Example: "when an agent dies, create a failover intent." |

### 11. YAML Workflow Integration

Triggers are declared in the `triggers:` block of a workflow YAML file:

```yaml
version: "1.0"
name: compliance-pipeline
namespace: compliance

triggers:
  daily-review:
    type: schedule
    cron: "0 9 * * MON-FRI"
    timezone: "America/New_York"
    deduplication: skip
    creates:
      type: compliance.review
      title: "Daily compliance review"
      priority: medium
      context:
        scope: all-departments

  escalate-stalled:
    type: event
    when:
      event: intent.stalled
      filter:
        priority: critical
    creates:
      type: escalation.review
      title: "Stalled critical intent escalation"
      context:
        source_intent: "{{ event.intent_id }}"

  payment-received:
    type: webhook
    path: /hooks/payment
    secret: "${PAYMENT_WEBHOOK_SECRET}"
    transform:
      amount: "{{ body.data.object.amount }}"
      customer: "{{ body.data.object.customer }}"
    creates:
      type: billing.process-payment
      title: "Process incoming payment"

agents:
  billing-processor:
    capabilities: [billing, invoicing]
    # ...

steps:
  # ...
```

#### 11.1 YAML Semantics

- Trigger names in YAML are local identifiers (e.g., `daily-review`). The server generates the `trigger_id`.
- The `creates` block maps to the `intent_template` field.
- Environment variable substitution (`${VAR}`) is supported for secrets.
- If the workflow declares a `namespace`, all triggers inherit it unless they explicitly override with a `namespace` field.

### 12. SDK Integration

The SDK exposes triggers through a `client.triggers` namespace:

```python
from openintent import Client

client = Client("https://api.example.com", api_key="...")

trigger = client.triggers.create(
    name="Daily Compliance Review",
    type="schedule",
    condition={"cron": "0 9 * * MON-FRI"},
    intent_template={
        "type": "compliance.review",
        "title": "Daily compliance review",
        "priority": "medium",
    },
    deduplication="skip",
)

triggers = client.triggers.list(type="schedule", enabled=True)

client.triggers.fire(trigger.trigger_id)

client.triggers.update(trigger.trigger_id, enabled=False, version=trigger.version)

history = client.triggers.history(trigger.trigger_id)

client.triggers.delete(trigger.trigger_id)
```

## Security Considerations

1. **Webhook secrets** are write-only — the API never returns them in responses. They are stored encrypted at rest.
2. **Trigger creation** is a privileged operation. In production, it should require specific API key permissions or coordinator approval (RFC-0013).
3. **Cascade limits** prevent denial-of-service through recursive trigger chains. The default depth of 10 should be sufficient for legitimate use cases.
4. **Rate limiting** on webhook endpoints prevents external abuse. Implementations should enforce per-trigger and global rate limits.
5. **Template injection** is limited to the `{{ }}` expression syntax. Arbitrary code execution is not supported. Implementations must sanitize template expressions.

## Rationale

**Why "intent factory" and not a workflow engine?**

The protocol already has intents, leasing, agents, and governance. Triggers reuse all of this by simply creating intents. The alternative — building a trigger execution engine with its own state machine, retries, and routing — would duplicate existing protocol machinery and push the protocol toward becoming an orchestration platform rather than a coordination protocol.

**Why three types and not an extensible event system?**

Schedule, event, and webhook cover the three fundamental categories of "what causes work": time, internal state changes, and external signals. An extensible type system would invite implementation-specific triggers that break interoperability. Custom event types (prefixed `x-`) provide extensibility within the event trigger type.

**Why global-first with namespace governance?**

Global triggers reflect the reality that many triggers span organizational boundaries (e.g., "when any agent dies, alert the ops team"). Namespace governance ensures that teams retain control over their domain. This cascading model is consistent with RFC-0011's permission inheritance.

**Why deduplication as a first-class concept?**

The most common trigger footgun is "the trigger fires faster than the intent resolves." Without explicit deduplication semantics, implementations will invent inconsistent solutions. Making it a protocol-level field with three clear modes eliminates ambiguity.

## Dependencies

- **RFC-0001 (Intent Model):** Triggers create intents through the standard intent creation path.
- **RFC-0006 (Subscriptions):** Subscription notifications are event sources for event triggers.
- **RFC-0011 (Access Control):** Namespace trigger policies extend the access control model.
- **RFC-0012 (Task Decomposition):** Triggers can initiate plans by creating top-level intents.
- **RFC-0013 (Coordinator Governance):** Trigger creation and firing are subject to governance guardrails.
- **RFC-0016 (Agent Lifecycle):** Agent lifecycle events are event sources for event triggers.
