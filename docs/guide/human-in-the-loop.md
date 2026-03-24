# Human-in-the-Loop (HITL) — RFC-0025

OpenIntent v0.16.0 introduces first-class support for suspending an intent mid-execution and waiting for operator input before proceeding. This guide covers everything from quick-start usage to advanced fallback policies and engagement-decision logic.

---

## Why HITL?

Autonomous agents are fast and consistent, but sometimes an action requires a human sanity-check before proceeding:

- Refunding a large payment
- Sending a legally sensitive communication
- Deleting irreversible data
- Approving a budget overrun

RFC-0025 provides a single, protocol-level primitive — **intent suspension** — that handles all of these cases, with built-in audit trails, fallback policies, and lifecycle hooks.

---

## Quick Start

```python
from openintent import Agent, on_assignment, on_input_requested

@Agent("approvals-agent")
class ApprovalsAgent:

    @on_assignment
    async def handle(self, intent):
        # Ask the operator before proceeding
        decision = await self.request_input(
            intent.id,
            question="Should we issue a refund for order #12345?",
            context={
                "order_id": "12345",
                "amount": 499.99,
                "currency": "USD",
                "customer": "alice@example.com",
            },
            channel_hint="slack",
            timeout_seconds=3600,            # 1 hour
            fallback_policy="complete_with_fallback",
            fallback_value="deny",           # deny if no response
            confidence=0.55,
        )

        if decision == "approve":
            await self.issue_refund(intent)
        else:
            await self.notify_customer_denied(intent)

    @on_input_requested
    async def notify_operator(self, intent, suspension):
        # Route the question to your notification channel
        await send_slack_message(
            channel="#approvals",
            text=suspension.question,
            context=suspension.context,
            suspension_id=suspension.id,
            intent_id=intent.id,
        )

ApprovalsAgent.run()
```

---

## Lifecycle Overview

```
active
  │
  │  agent calls request_input()
  ▼
suspended_awaiting_input
  │
  │  operator POSTs to /intents/{id}/suspend/respond
  ▼
active  (agent continues with the response value)
```

If the suspension times out, the **fallback policy** is applied (see [Fallback Policies](#fallback-policies)).

---

## `request_input()` Reference

```python
value = await self.request_input(
    intent_id,           # str  — the intent to suspend
    question,            # str  — prompt for the operator
    context={},          # dict — structured context
    channel_hint=None,   # str  — e.g. "slack", "email"
    timeout_seconds=None,# int  — None = no timeout
    fallback_policy="fail",   # str — see below
    fallback_value=None, # any — used by complete_with_fallback
    confidence=None,     # float [0,1] — your confidence at suspension time
)
```

### What happens internally

1. A `SuspensionRecord` is created and stored in `intent.state._suspension`.
2. The intent transitions to `suspended_awaiting_input`.
3. An `intent.suspended` event is emitted.
4. `@on_input_requested` hooks are fired so you can notify operators.
5. The agent polls `intent.state._suspension.resolution` every 2 seconds.
6. When an operator responds, the intent transitions back to `active` and the response value is returned.

---

## Fallback Policies

| Policy | What happens on timeout |
|---|---|
| `"fail"` (default) | `InputTimeoutError` is raised |
| `"complete_with_fallback"` | `fallback_value` is returned; agent continues |
| `"use_default_and_continue"` | Same as `complete_with_fallback` |

```python
from openintent.exceptions import InputTimeoutError

try:
    answer = await self.request_input(
        intent_id,
        question="Approve?",
        timeout_seconds=300,
        fallback_policy="fail",
    )
except InputTimeoutError as e:
    await self.log(intent_id, f"Suspension {e.suspension_id} expired")
    await self.abandon(intent_id, reason="No operator response")
```

---

## Engagement Decisions

Before calling `request_input()`, use `should_request_input()` to decide whether human input is actually needed:

```python
from openintent.models import EngagementSignals

signals = EngagementSignals(
    confidence=0.55,   # agent confidence in autonomous answer
    risk=0.70,         # risk of acting without input
    reversibility=0.80,# how reversible the action is
)

decision = await self.should_request_input(intent_id, signals=signals)

print(decision.mode)      # "require_input"
print(decision.should_ask)# True
print(decision.rationale) # Human-readable explanation

if decision.should_ask:
    value = await self.request_input(intent_id, question="Proceed?")
else:
    value = await self.autonomous_action(intent_id)
```

### Decision Modes

| Mode | When | `should_ask` |
|---|---|---|
| `autonomous` | High confidence, low risk, reversible | `False` |
| `request_input` | Moderate uncertainty | `True` |
| `require_input` | Low confidence or high risk | `True` |
| `defer` | Risk or irreversibility too high | `False` |

### Keyword shorthand

```python
decision = await self.should_request_input(
    intent_id,
    confidence=0.9,
    risk=0.05,
    reversibility=0.95,
)
```

---

## HITL Lifecycle Decorators

### `@on_input_requested`

Called after the suspension is persisted, before polling begins. Use this to notify operators via your preferred channel.

```python
@on_input_requested
async def notify(self, intent, suspension):
    # suspension is a SuspensionRecord
    await slack.post(
        channel=suspension.channel_hint or "#general",
        text=f"*Human input required*\n{suspension.question}",
    )
```

### `@on_input_received`

Called when an operator response arrives, before `request_input()` returns. Use this for logging or routing.

```python
@on_input_received
async def log_response(self, intent, response):
    # response is an InputResponse
    await self.log(intent.id, f"Operator {response.responded_by}: {response.value}")
```

### `@on_suspension_expired`

Called when a suspension times out, before the fallback policy is applied.

```python
@on_suspension_expired
async def handle_timeout(self, intent, suspension):
    await alert_on_call(f"Suspension {suspension.id} expired on intent {intent.id}")
```

### `@on_engagement_decision`

Called after `should_request_input()` computes a decision. Use this to audit or override decisions.

```python
@on_engagement_decision
async def audit(self, intent, decision):
    await self.log(intent.id, f"Engagement: {decision.mode} ({decision.rationale})")
```

---

## Operator Responds via REST

Operators (or your UI/bot) submit responses via:

```http
POST /api/v1/intents/{intent_id}/suspend/respond
X-API-Key: <operator-key>
Content-Type: application/json

{
  "suspension_id": "susp-uuid",
  "value": "approve",
  "responded_by": "alice@example.com"
}
```

**Response (200):**

```json
{
  "intent_id": "intent-uuid",
  "suspension_id": "susp-uuid",
  "resolution": "responded",
  "value": "approve",
  "responded_by": "alice@example.com",
  "responded_at": "2026-03-23T10:01:00"
}
```

The intent immediately transitions back to `active` and the polling agent unblocks.

---

## Exception Reference

| Exception | When raised |
|---|---|
| `InputTimeoutError` | `fallback_policy="fail"` and timeout expires |
| `InputCancelledError` | Suspension is cancelled (resolution="cancelled") |

Both inherit from `OpenIntentError`.

```python
from openintent.exceptions import InputCancelledError, InputTimeoutError
```

---

## Full Example: Refund Agent with Engagement Logic

```python
from openintent import Agent, on_assignment, on_input_requested, on_suspension_expired
from openintent.exceptions import InputTimeoutError
from openintent.models import EngagementSignals


@Agent("refund-agent")
class RefundAgent:

    @on_assignment
    async def handle(self, intent):
        order_id = intent.ctx.data.get("order_id")
        amount = intent.ctx.data.get("amount", 0)

        # Compute engagement signals
        confidence = 0.9 if amount < 100 else 0.4
        risk = 0.8 if amount > 1000 else 0.3

        signals = EngagementSignals(confidence=confidence, risk=risk, reversibility=0.5)
        decision = await self.should_request_input(intent.id, signals=signals)

        if decision.should_ask:
            try:
                answer = await self.request_input(
                    intent.id,
                    question=f"Approve refund of ${amount} for order {order_id}?",
                    context={"order_id": order_id, "amount": amount},
                    channel_hint="slack",
                    timeout_seconds=7200,
                    fallback_policy="complete_with_fallback",
                    fallback_value="deny",
                    confidence=confidence,
                )
            except InputTimeoutError:
                answer = "deny"
        else:
            answer = "approve" if confidence >= 0.85 else "deny"

        return {"order_id": order_id, "refund_decision": answer}

    @on_input_requested
    async def notify_slack(self, intent, suspension):
        await post_slack(
            f"Refund approval needed: {suspension.question}",
            context=suspension.context,
        )

    @on_suspension_expired
    async def alert_on_timeout(self, intent, suspension):
        await post_slack(f"Refund approval timed out for suspension {suspension.id}")
```

---

## Testing HITL Agents

Use the `POST /suspend/respond` endpoint in your integration tests:

```python
import httpx

async def test_refund_agent(client, intent_id):
    # Trigger the agent assignment
    ...

    # Simulate operator response
    resp = httpx.post(
        f"http://localhost:8000/api/v1/intents/{intent_id}/suspend/respond",
        headers={"X-API-Key": "test-key"},
        json={
            "suspension_id": suspension_id,
            "value": "approve",
            "responded_by": "test-operator",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["resolution"] == "responded"
```

---

## See Also

- [RFC-0025: Human-in-the-Loop Intent Suspension](../rfcs/0025-human-in-the-loop.md)
- [RFC-0001: Intent Objects](../rfcs/0001-intent-objects.md) — lifecycle states
- [RFC-0013: Coordinator Governance](../rfcs/0013-coordinator-governance.md) — escalation
- [RFC-0019: Verifiable Event Logs](../rfcs/0019-verifiable-event-logs.md) — audit trail
