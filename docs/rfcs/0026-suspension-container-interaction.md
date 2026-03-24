# RFC-0026: Suspension Propagation & Retry v1.0

**Status:** Accepted  
**Version:** v0.17.0  
**Date:** 2026-03-24  
**Authors:** OpenIntent Working Group  
**Extends:** [RFC-0025 (Human-in-the-Loop)](./0025-human-in-the-loop.md)

---

## Abstract

RFC-0025 introduced `suspended_awaiting_input` as an intent-level lifecycle state but left three gaps: (1) how suspension interacts with container structures (intent graphs, portfolios, plans, workflows); (2) a single-shot timeout model with no re-notification or escalation ladder; and (3) no platform- or agent-level default for suspension policy. RFC-0026 closes all three gaps in a single coherent extension so the protocol has complete, end-to-end coverage of human engagement.

---

## 1. Motivation

### Gap 1 — Container semantics

RFC-0025 defines suspension at the intent level but does not specify how containers observe it:

- **RFC-0002 (Intent Graphs):** `aggregate_status.by_status` has no entry for `suspended_awaiting_input`. The completion gate does not explicitly say whether a suspended dependency satisfies it. No `active → blocked` trigger is defined for upstream suspension.
- **RFC-0007 (Portfolios):** The aggregate status algorithm does not enumerate suspension. The GET response has no suspension-aware fields.
- **RFC-0012 (Plans & Tasks):** The task `blocked` state was designed before RFC-0025 and has no defined relationship to `suspended_awaiting_input`. When a phase-agent calls `request_input()`, the plan task does not transition to `blocked`. The coordinator sees the task as still running.
- **RFC-0024 (Workflows):** `validate_claim_inputs()` has no rejection reason for upstream suspension. The workflow progress object has no `suspended_phases` field.

### Gap 2 — Human retry / re-notification

RFC-0025 timeout model is single-shot: one window, then fallback policy fires. A missed Slack notification should not immediately trigger `complete_with_fallback="deny"`. Systems need grace — notify once, re-notify, escalate, then fail.

### Gap 3 — Platform and agent-level defaults

Every `request_input()` call must specify its own policy from scratch. There is no platform-level constant and no agent-level default.

---

## 2. Container Rules (Five, Non-Negotiable)

### Rule 1 — Suspension is always intent-local

Only the suspended intent changes to `suspended_awaiting_input`. Container structures (parent intents, portfolios, plans, workflows) observe it; they never absorb it into their own state. A portfolio does not become suspended because a member is suspended.

### Rule 2 — Suspended intent is "not completed"; dependents stay blocked

`suspended_awaiting_input` does **NOT** satisfy the RFC-0002 completion gate. A dependent intent that is `active` and whose upstream suspends MUST transition to `blocked` (new `active → blocked` trigger). Auto-unblock fires when the dependency *resumes and subsequently completes*, not on resume alone.

### Rule 3 — RFC-0012 tasks mirror intent suspension bidirectionally

When an intent transitions to `suspended_awaiting_input`, its corresponding plan task MUST transition to `blocked` with:

```json
{
  "blocked_reason": "intent_suspended",
  "suspended_intent_id": "<intent_id>"
}
```

On `intent.resumed`, the task transitions back to `running`. RFC-0012 checkpoints that require human approval SHOULD be implemented via RFC-0025 `request_input()` — this is the canonical pattern going forward.

### Rule 4 — Container aggregates gain suspension-aware fields

**RFC-0002 parent intents:**

```json
{
  "aggregate_status": {
    "total": 6,
    "by_status": {
      "completed": 3,
      "active": 2,
      "blocked": 0,
      "suspended_awaiting_input": 1
    }
  }
}
```

**RFC-0007 portfolios:**

Portfolio GET response adds two fields:

```json
{
  "has_suspended_members": true,
  "suspended_member_count": 1
}
```

Aggregate status algorithm (revised):

| Condition | Aggregate status |
|---|---|
| All members `completed` | `completed` |
| Any member `failed` or `abandoned` | `failed` |
| Otherwise (including any suspended) | `in_progress` |

**RFC-0012 plans:**

Plan progress object gains:

```json
{
  "suspended_tasks": [
    {
      "task_id": "task_01XYZ",
      "intent_id": "intent_01ABC",
      "suspended_since": "2026-03-24T10:00:00Z",
      "expires_at": "2026-03-24T13:00:00Z"
    }
  ]
}
```

**RFC-0024 workflows:**

Workflow progress object gains:

```json
{
  "suspended_phases": [
    {
      "phase_name": "compliance_review",
      "intent_id": "intent_01ABC",
      "suspended_since": "2026-03-24T10:00:00Z",
      "expires_at": "2026-03-24T13:00:00Z"
    }
  ]
}
```

### Rule 5 — Portfolio deadline takes precedence over suspension timeout

If `governance.deadline` fires while a member intent is `suspended_awaiting_input`, the server MUST abandon the intent with `abandonment_reason: "portfolio_deadline_exceeded"`, bypassing `fallback_policy`. `intent.suspension_expired` is still emitted with `reason: "portfolio_deadline"` for audit.

---

## 3. Coordinator Suspension Policy (RFC-0013 Extension)

Coordinator leases gain an optional `suspension_policy` field:

| Value | Behaviour |
|---|---|
| `isolate` | Default. No action beyond aggregate status update. |
| `block_dependents` | Coordinator explicitly pauses RFC-0024-wired downstream phases. |
| `escalate` | Emits `coordinator.escalation_required` or self-suspends. |

---

## 4. Human Retry / Re-notification Policy

### 4.1 The `HumanRetryPolicy` Object

```json
{
  "max_attempts": 3,
  "interval_seconds": 3600,
  "strategy": "fixed",
  "escalation_ladder": [
    { "attempt": 2, "channel_hint": "email", "notify_to": null },
    { "attempt": 3, "channel_hint": "pagerduty", "notify_to": "supervisor@example.com" }
  ],
  "final_fallback_policy": "fail"
}
```

| Field | Type | Default | Description |
|---|---|---|---|
| `max_attempts` | integer | 1 | Total notification attempts (including initial) |
| `interval_seconds` | integer | — | Seconds between re-notification attempts (≤ `timeout_seconds`) |
| `strategy` | `"fixed"` | `"fixed"` | Re-notification cadence strategy |
| `escalation_ladder` | array | `[]` | Per-attempt channel/recipient overrides |
| `final_fallback_policy` | enum | (inherited) | Policy to apply after all attempts exhausted |

### 4.2 How It Works

1. **Attempt 1** fires immediately when `request_input()` is called. `timeout_seconds` becomes the *per-attempt* window.
2. If the operator does not respond within `interval_seconds` (≤ `timeout_seconds`), a re-notification fires and the attempt counter increments.
3. Each `escalation_ladder` entry triggers at its `attempt` number, overriding `channel_hint` and optionally routing to a different `notify_to` identity.
4. After `max_attempts` notifications with no response, `final_fallback_policy` is applied.
5. **Total suspension window** = `interval_seconds × max_attempts`. `expires_at` on `SuspensionRecord` reflects this total deadline.
6. `suspension_id` is **unchanged** across all attempts — the operator can respond to the original request at any point.

### 4.3 Backwards Compatibility

The existing `fallback_policy` field on `SuspensionRecord` is kept as an alias:

- `fallback_policy` with no `retry_policy` is equivalent to `HumanRetryPolicy(max_attempts=1)`.
- When a `retry_policy` is present, `final_fallback_policy` inside it takes precedence over the top-level `fallback_policy`.

### 4.4 New Events

| Event | When emitted |
|---|---|
| `intent.suspension_renotified` | Before each re-notification attempt (attempt ≥ 2) |
| `intent.suspension_escalated` | When an `escalation_ladder` entry triggers |

**`intent.suspension_renotified` payload:**

```json
{
  "suspension_id": "susp-uuid",
  "attempt": 2,
  "max_attempts": 3,
  "channel_hint": "email",
  "notify_to": null,
  "next_attempt_at": "2026-03-24T11:00:00Z"
}
```

**`intent.suspension_escalated` payload:**

```json
{
  "suspension_id": "susp-uuid",
  "attempt": 3,
  "escalated_to": "supervisor@example.com",
  "channel_hint": "pagerduty"
}
```

Existing `intent.suspension_expired` fires after all attempts exhausted, then `final_fallback_policy` executes.

### 4.5 `@on_input_requested` Re-fired on Each Attempt

The existing `@on_input_requested` decorator is called again with `attempt` number in the suspension context on each re-notification. Agents can customize messages:

```python
@on_input_requested
async def notify_operator(self, intent, suspension):
    attempt = suspension.context.get("_attempt", 1)
    if attempt == 1:
        msg = f"Input needed: {suspension.question}"
    elif attempt < suspension.context.get("_max_attempts", 1):
        msg = f"Reminder ({attempt}): {suspension.question}"
    else:
        msg = f"URGENT — final reminder: {suspension.question}"
    await send_notification(msg, channel=suspension.channel_hint)
```

---

## 5. Three-Level Configuration Cascade

```
server config          → BaseAgent default         → request_input() call
─────────────────────    ────────────────────────    ──────────────────────
default_human_retry_     default_human_retry_         retry_policy=
  policy: {               policy: {                    HumanRetryPolicy(
  max_attempts: 3,          max_attempts: 2,             max_attempts: 1,
  interval_seconds: 3600    interval_seconds: 1800       interval_seconds: 300
}                         }                           )
```

Resolution: per-suspension overrides agent default overrides platform default. Any field not specified at a lower level inherits from the level above.

**Platform constant location:** Server config file (`openintent.yaml`) under `suspension.default_retry_policy`. Exposed via `GET /v1/server/config` (read-only, for client introspection).

**Agent-level default:** `BaseAgent.default_human_retry_policy` — a `HumanRetryPolicy` instance set in the agent definition or `__init__`. If `None`, platform default applies.

---

## 6. RFC-0024 Patch: `validate_claim_inputs()` Rejection Reason

When an agent attempts to claim a task whose declared inputs reference an upstream phase that is currently `suspended_awaiting_input`, `validate_claim_inputs()` MUST reject with:

```python
raise UpstreamIntentSuspendedError(
    task_id=task_id,
    phase_name=phase_name,
    suspended_intent_id="<upstream_intent_id>",
    expected_resume_at="<ISO-8601 or None>",
)
```

This is a new exception type (`upstream_intent_suspended`) that the executor surfaces as a claim rejection reason. The downstream task stays in `pending` / `ready` state and retries the claim check after the upstream resumes.

---

## 7. Relationship to RFC-0010 (Retry Policies)

RFC-0010 defines retry when the *agent* fails (picks a new agent attempt). RFC-0026 defines retry when the *human* fails to respond (resends notification, escalates channel). They are parallel constructs at different layers:

| Dimension | RFC-0010 | RFC-0026 |
|---|---|---|
| What failed? | Agent execution | Human responsiveness |
| What retries? | Agent assignment | Human notification |
| State during retry | Intent may be reassigned | Intent stays `suspended_awaiting_input` |
| Infrastructure | Scheduled retry job | Scheduled re-notification job |

The server SHOULD use the same scheduled-job infrastructure for both.

---

## 8. Python SDK — `HumanRetryPolicy`

```python
from openintent import HumanRetryPolicy

policy = HumanRetryPolicy(
    max_attempts=3,
    interval_seconds=3600,
    escalation_ladder=[
        {"attempt": 2, "channel_hint": "email"},
        {"attempt": 3, "channel_hint": "pagerduty", "notify_to": "supervisor@example.com"},
    ],
    final_fallback_policy="fail",
)

value = await self.request_input(
    intent_id,
    question="Should we proceed with the refund?",
    response_type="choice",
    choices=[...],
    timeout_seconds=3600,
    retry_policy=policy,
)
```

`BaseAgent` gains `default_human_retry_policy`:

```python
@Agent("my-agent")
class MyAgent:
    default_human_retry_policy = HumanRetryPolicy(
        max_attempts=2,
        interval_seconds=1800,
        final_fallback_policy="complete_with_fallback",
    )
```

---

## 9. End-to-End Motivating Example

**Scenario:** Multi-phase compliance workflow. Phase 2 (`compliance_review`) requires human sign-off before Phase 3 (`generate_report`) can run.

```
Phase 1: fetch_data        → completes OK
Phase 2: compliance_review → agent calls request_input()
Phase 3: generate_report   → depends_on: compliance_review
```

**Timeline:**

| Time | Event |
|---|---|
| T+0 | Phase 2 agent calls `request_input()` with `retry_policy(max_attempts=3, interval_seconds=3600)` |
| T+0 | Intent 2 → `suspended_awaiting_input` |
| T+0 | Task 2 → `blocked` (`blocked_reason: "intent_suspended"`) |
| T+0 | Intent 3 → `blocked` (upstream suspended, does not satisfy completion gate) |
| T+0 | `intent.suspended` emitted; `@on_input_requested` fires (attempt=1) → Slack message sent |
| T+0 | Portfolio: `has_suspended_members: true`, `suspended_member_count: 1` |
| T+3600 | No response. `intent.suspension_renotified` emitted (attempt=2) |
| T+3600 | `@on_input_requested` fires again (attempt=2, channel_hint="email") → email sent |
| T+3600 | `intent.suspension_escalated` emitted (attempt=2) |
| T+5400 | Operator responds via `POST /intents/{id}/suspend/respond` |
| T+5400 | Intent 2 → `active` → `completed` |
| T+5400 | Task 2 → `running` → `completed` |
| T+5400 | Intent 3 → `active` (dependency now completed) |
| T+5400 | Task 3 claims Phase 3 inputs from Phase 2 outputs — validate_claim_inputs() succeeds |
| T+5500 | Phase 3 completes. Workflow done. |

**What did NOT happen:** Phase 3 did not try to claim while Phase 2 was suspended. The coordinator saw the suspension in the aggregate. The portfolio deadline was not exceeded.

---

## 10. Cross-RFC Patch Summary

### RFC-0002 patches

- Status enum: add `suspended_awaiting_input` to `by_status` in `aggregate_status`.
- Completion gate: explicitly states `suspended_awaiting_input` does NOT satisfy the gate.
- New `active → blocked` trigger: upstream dependency transitions to `suspended_awaiting_input`.
- Cross-RFC table: add RFC-0026.

### RFC-0007 patches

- Aggregate status algorithm: enumerated explicitly (completed/failed/in_progress).
- GET response: add `has_suspended_members: bool`, `suspended_member_count: int`.
- New events: `portfolio.member_suspended`, `portfolio.member_resumed`.
- Cross-RFC table: add RFC-0026.

### RFC-0012 patches

- Bidirectional task/intent relationship: task `blocked` ↔ intent `suspended_awaiting_input`.
- `blocked_reason: "intent_suspended"` and `suspended_intent_id` on blocked task.
- Plan progress: add `suspended_tasks` array.
- Checkpoints: explicitly documented as RFC-0025 `request_input()` triggers (canonical pattern).
- Cross-RFC table: add RFC-0026.

### RFC-0024 patches

- `validate_claim_inputs()`: add `upstream_intent_suspended` rejection reason (`UpstreamIntentSuspendedError`).
- Workflow progress: add `suspended_phases` array.
- Cross-RFC table: add RFC-0026.

### RFC-0025 patches

- `SuspensionRecord`: add `retry_policy` field (optional `HumanRetryPolicy`).
- `timeout_seconds` semantics: clarified as per-attempt window when `retry_policy` is set.
- `fallback_policy`: documented as alias for `HumanRetryPolicy(max_attempts=1, final_fallback_policy=...)`.
- Cross-RFC table: add RFC-0026, RFC-0010.
- Backwards compatibility: note `fallback_policy` unchanged; `retry_policy` is additive.

### RFC-0010 patches

- Cross-RFC table: add RFC-0026 with note on parallel retry constructs.

---

## 11. Security Considerations

- Re-notification payloads to external channels (Slack, PagerDuty) MUST NOT include secrets or PII in `question` or `context` fields.
- `escalation_ladder.notify_to` identity values should be validated against an allowlist before delivery.
- Multiple re-notification attempts increase the attack surface for replay; `suspension_id` SHOULD remain the same (see §4.2 item 6) and the server MUST reject duplicate responses after the first.

---

## 12. Backwards Compatibility

- `retry_policy` on `SuspensionRecord` is optional. Existing `fallback_policy` field continues to work unchanged with single-attempt semantics.
- `UpstreamIntentSuspendedError` is a new exception class; callers that only catch `UnresolvableInputError` will see uncaught exceptions if they don't update. Callers should catch `WorkflowError` for robust handling.
- New events (`intent.suspension_renotified`, `intent.suspension_escalated`) are additive; existing subscriptions propagate them through the same infrastructure.
- `has_suspended_members` / `suspended_member_count` are additive fields on portfolio GET responses; existing clients that ignore unknown fields are unaffected.
- `suspended_tasks` / `suspended_phases` are additive fields on progress objects.
