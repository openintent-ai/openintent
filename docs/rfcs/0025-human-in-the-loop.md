# RFC-0025: Human-in-the-Loop Intent Suspension

**Status:** Accepted  
**Version:** v0.16.0  
**Date:** 2026-03-23  
**Authors:** OpenIntent Working Group

---

## Abstract

This RFC defines the protocol for suspending an intent mid-execution to obtain operator input before proceeding. It introduces the `suspended_awaiting_input` lifecycle state, four new event types, a REST endpoint for operator responses, engagement-decision logic for when to invoke the human loop, and fallback policies for handling timeouts.

---

## 1. Motivation

Autonomous agents operating in high-stakes environments (finance, healthcare, legal, operations) encounter situations where acting without a human sanity-check is unacceptable. RFC-0025 provides a first-class protocol primitive — intent suspension — that:

- Integrates cleanly with the existing intent lifecycle (RFC-0001).
- Preserves audit trails via the event log (RFC-0019).
- Supports structured engagement-decision logic to minimise unnecessary interruptions.
- Defines deterministic fallback behaviour when operators are unresponsive.

---

## 2. New Lifecycle State

```
draft → active ⇄ suspended_awaiting_input → active → completed
                                          ↘ abandoned (via fallback)
```

| Transition | Trigger |
|---|---|
| `active → suspended_awaiting_input` | Agent calls `request_input()` |
| `suspended_awaiting_input → active` | Operator responds via `POST /intents/{id}/suspend/respond` |
| `suspended_awaiting_input → abandoned` | `fallback_policy: "fail"` and timeout expires |

**Reaper / lease-expiry workers MUST skip intents in `suspended_awaiting_input`** status — these intents are intentionally blocked pending human input.

**Lease renewal MUST succeed** for intents in `suspended_awaiting_input` so the holding agent retains ownership across the suspension period.

---

## 3. New Event Types

| Event | When emitted |
|---|---|
| `intent.suspended` | When `request_input()` transitions the intent |
| `intent.resumed` | When an operator response is accepted |
| `intent.suspension_expired` | When a suspension timeout fires before a response |
| `engagement.decision` | When `should_request_input()` returns a decision |

All events are stored in the intent event log and are visible via `GET /intents/{id}/events`.

---

## 4. Response Types and Choices

Every suspension declares the kind of input it expects from the operator via `response_type` and an optional list of `choices`. This gives operators clear, actionable options and lets the server validate responses before they reach the agent.

### 4.1 ResponseType

| Value | Description | Choices required | Server-validated |
|---|---|---|---|
| `choice` | Operator selects one of the defined choices | Yes | Yes — value must match a choice |
| `confirm` | Binary yes/no confirmation | Optional (defaults to yes/no) | Yes — value must be `"yes"` or `"no"` |
| `text` | Free-form text input | No | No |
| `form` | Structured key/value fields (keys defined in context) | No | No |

### 4.2 SuspensionChoice

Each choice presented to the operator is a `SuspensionChoice`:

| Field | Type | Required | Description |
|---|---|---|---|
| `value` | string | ✓ | Machine-readable value returned to the agent when selected |
| `label` | string | ✓ | Human-readable label displayed to the operator |
| `description` | string | — | Longer explanation to help the operator decide |
| `style` | string | — | Visual hint for the channel UI: `"primary"`, `"danger"`, `"default"` |
| `metadata` | object | — | Arbitrary extra data attached to this choice |

When `response_type` is `choice`, the agent MUST supply at least one `SuspensionChoice`. When `response_type` is `confirm` and no explicit choices are supplied, the server assumes `[{value: "yes", label: "Yes"}, {value: "no", label: "No"}]`.

---

## 5. SuspensionRecord

A `SuspensionRecord` is created by the agent and persisted in `intent.state._suspension`.

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string (UUID) | ✓ | Unique suspension identifier |
| `question` | string | ✓ | Human-readable question/prompt |
| `response_type` | enum | ✓ | Expected response type (see §4.1) — default `"choice"` |
| `choices` | SuspensionChoice[] | — | Available options for the operator (see §4.2) |
| `context` | object | — | Structured context for the operator |
| `channel_hint` | string | — | Preferred delivery channel (`"slack"`, `"email"`) |
| `suspended_at` | ISO-8601 | — | When the suspension started |
| `timeout_seconds` | integer | — | Expiry window (omit for no timeout) |
| `expires_at` | ISO-8601 | — | Computed from `suspended_at + timeout_seconds` |
| `fallback_value` | any | — | Value for `complete_with_fallback` policy |
| `fallback_policy` | enum | ✓ | See §6 |
| `confidence_at_suspension` | float [0,1] | — | Agent confidence at suspension time |
| `decision_record` | object | — | EngagementDecision that triggered suspension |
| `response` | any | — | Operator's response (set on resume) |
| `responded_at` | ISO-8601 | — | When the operator responded |
| `resolution` | enum | — | `"responded"`, `"expired"`, `"cancelled"` |

---

## 6. Fallback Policies

| Policy | On timeout |
|---|---|
| `fail` | Raise `InputTimeoutError`; intent remains suspended or transitions to abandoned |
| `complete_with_fallback` | Return `fallback_value` and continue execution |
| `use_default_and_continue` | Return `fallback_value` and continue execution (alias for compatibility) |

---

## 7. EngagementSignals and EngagementDecision

Before calling `request_input()`, agents SHOULD call `should_request_input()` to obtain an engagement decision.

### 7.1 EngagementSignals

| Field | Type | Default | Description |
|---|---|---|---|
| `confidence` | float [0,1] | 1.0 | Agent confidence in autonomous answer |
| `risk` | float [0,1] | 0.0 | Estimated risk of acting autonomously |
| `reversibility` | float [0,1] | 1.0 | How reversible the action is |
| `context` | object | `{}` | Additional key/value context |

### 7.2 Decision Modes

| Mode | Condition | `should_ask` |
|---|---|---|
| `autonomous` | confidence ≥ 0.85, risk ≤ 0.20, reversibility ≥ 0.50 | `false` |
| `request_input` | moderate uncertainty | `true` |
| `require_input` | confidence < 0.50 or risk > 0.50 | `true` |
| `defer` | risk ≥ 0.80 or reversibility ≤ 0.10 | `false` |

---

## 8. REST Endpoint: `POST /intents/{id}/suspend/respond`

**Authentication:** X-API-Key header required.

### Request body

```json
{
  "suspension_id": "susp-uuid",
  "value": "<operator response>",
  "responded_by": "alice@example.com",
  "metadata": {}
}
```

### Success response (200)

```json
{
  "intent_id": "intent-uuid",
  "suspension_id": "susp-uuid",
  "resolution": "responded",
  "value": "approve",
  "choice_label": "Approve refund",
  "choice_description": "Issue full refund to original payment method",
  "responded_by": "alice@example.com",
  "responded_at": "2026-03-23T10:01:00"
}
```

When the selected value matches a `SuspensionChoice`, the response includes `choice_label` and `choice_description` for downstream audit/display.

### Validation behaviour

The server validates the `value` field against the suspension's `response_type` and `choices`:

| `response_type` | Validation |
|---|---|
| `choice` | `value` MUST match one of the defined `SuspensionChoice.value` entries |
| `confirm` | `value` MUST be `"yes"` or `"no"` (checked even if no explicit choices are defined) |
| `text` | No validation — any non-empty string is accepted |
| `form` | No validation — value is passed through as-is |

### Error responses

| Status | Condition |
|---|---|
| 401 | Missing or invalid API key |
| 404 | Intent not found |
| 409 | Intent is not in `suspended_awaiting_input` status, or `suspension_id` does not match the active suspension |
| 422 | `suspension_id` is missing/empty, or `value` is invalid for the declared `response_type` |

On a 422 for invalid choice, the response body includes `valid_choices` listing the accepted values.

---

## 9. Agent SDK

### 9.1 `request_input()`

```python
from openintent import SuspensionChoice

value = await self.request_input(
    intent_id,
    question="Should we refund order #12345?",
    response_type="choice",
    choices=[
        SuspensionChoice(value="approve", label="Approve refund",
                         description="Issue full refund to original payment method",
                         style="primary"),
        SuspensionChoice(value="deny", label="Deny refund",
                         description="Reject and close the case",
                         style="danger"),
        SuspensionChoice(value="escalate", label="Escalate",
                         description="Route to a senior operator"),
    ],
    context={"order_id": "12345", "amount": 499.99},
    channel_hint="slack",
    timeout_seconds=3600,
    fallback_policy="complete_with_fallback",
    fallback_value="deny",
    confidence=0.55,
)
```

Returns the operator's response value. Raises `InputTimeoutError` (fallback_policy="fail") or `InputCancelledError`.

For `confirm` type, choices default to yes/no if omitted:

```python
value = await self.request_input(
    intent_id,
    question="Deploy to production?",
    response_type="confirm",
    timeout_seconds=600,
    fallback_policy="fail",
)
# value will be "yes" or "no"
```

### 9.2 `should_request_input()`

```python
decision = await self.should_request_input(
    intent_id,
    confidence=0.55,
    risk=0.60,
    reversibility=0.80,
)
if decision.should_ask:
    value = await self.request_input(intent_id, question="Proceed?",
                                     response_type="confirm")
```

### 9.3 Lifecycle Decorators

```python
@on_input_requested    # fired after suspension is written
@on_input_received     # fired when operator response arrives
@on_suspension_expired # fired when timeout expires
@on_engagement_decision # fired after should_request_input() returns
```

---

## 10. InputResponse

| Field | Type | Description |
|---|---|---|
| `suspension_id` | string | ID of the SuspensionRecord |
| `value` | any | Operator's answer |
| `choice_label` | string | Label of the selected choice (if applicable) |
| `choice_description` | string | Description of the selected choice (if applicable) |
| `responded_by` | string | Operator identifier |
| `responded_at` | ISO-8601 | When the operator responded |
| `metadata` | object | Optional channel metadata |

---

## 11. Security Considerations

- The `POST /suspend/respond` endpoint MUST be authenticated. Implementors SHOULD apply role-based access control to restrict which API keys can respond.
- `suspension_id` SHOULD be treated as a secret capability token when transmitted via external channels (Slack, email).
- Suspension payloads MUST NOT include secrets or PII in the `context` field unless the delivery channel is encrypted end-to-end.

---

## 12. Backwards Compatibility

- Adds a new `suspended_awaiting_input` status string — existing clients that enumerate statuses must be updated to handle this value.
- The `response_type` field defaults to `"choice"` — suspensions created without it behave identically to pre-0.16.0 behaviour.
- All new event types, endpoint, decorators, and structured choice fields are additive.
- Servers that do not implement this suspension protocol will return 404 for `POST /suspend/respond`; agents SHOULD handle this gracefully.
