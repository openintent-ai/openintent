---
title: Cost Tracking & Retry Policies
---

# Cost Tracking & Retry Policies

OpenIntent provides built-in cost tracking for budgeting multi-agent workflows and configurable retry policies for handling transient failures. Defined in [RFC-0009](../rfcs/0009-cost-tracking.md) and [RFC-0010](../rfcs/0010-retry-policies.md).

---

## Cost Tracking

### Recording Costs

Every billable action — LLM calls, API requests, tool invocations — can be recorded against an intent:

```python
# Record a cost event
client.record_cost(
    intent_id=intent.id,
    amount_cents=15,
    currency="USD",
    category="llm",
    metadata={
        "model": "gpt-4",
        "input_tokens": 500,
        "output_tokens": 200,
        "provider": "openai"
    }
)
```

### Cost Categories

| Category | Description |
|----------|-------------|
| `llm` | Language model API calls |
| `tool` | External tool invocations |
| `compute` | Processing and compute time |
| `storage` | Data storage and retrieval |
| `api` | Third-party API calls |
| `custom` | User-defined categories |

### Querying Costs

```python
# Get total costs for an intent
costs = client.get_costs(intent.id)

print(f"Total: ${costs.total_cents / 100:.2f}")
print(f"By category:")
for category, amount in costs.by_category.items():
    print(f"  {category}: ${amount / 100:.2f}")
```

### Budget Enforcement

Set budgets at the intent or portfolio level:

```python
# Intent-level budget
intent = client.create_intent(
    title="Research competitors",
    constraints={"max_budget_cents": 1000}  # $10 budget
)

# Portfolio-level budget
portfolio = client.create_portfolio(
    name="Q1 Analysis",
    governance={"budget_limit_cents": 50000}  # $500 budget
)
```

### Automatic LLM Cost Tracking

[LLM Adapters](adapters.md) record costs automatically:

```python
from openintent.adapters import OpenAIAdapter

adapter = OpenAIAdapter(openai_client, oi_client, intent.id)

# Costs are tracked automatically for every call
response = adapter.chat_complete(
    model="gpt-4",
    messages=[{"role": "user", "content": "Analyze this data"}]
)
# → Cost event recorded: model, tokens, provider
```

### Cost Tracking in YAML Workflows

```yaml
workflow:
  research:
    title: "Research Phase"
    assign: researcher
    cost_tracking:
      enabled: true
      budget_usd: 5.00
      alert_threshold_pct: 80

governance:
  max_cost_usd: 50.00
```

---

## Retry Policies

### Configuring Retries

Retry policies define how the protocol handles transient failures:

```python
# Set a retry policy for an intent
client.set_retry_policy(
    intent_id=intent.id,
    max_attempts=3,
    backoff="exponential",
    initial_delay_seconds=1,
    max_delay_seconds=60
)
```

### Backoff Strategies

| Strategy | Behavior |
|----------|----------|
| `none` | No delay between retries |
| `fixed` | Same delay every time |
| `linear` | Delay increases linearly (1s, 2s, 3s, ...) |
| `exponential` | Delay doubles each attempt (1s, 2s, 4s, 8s, ...) |

### Recording Failures

When an agent encounters a transient error, record the failure so the protocol can schedule a retry:

```python
from openintent.agents import Agent, on_assignment
from openintent.exceptions import TransientError

@Agent("resilient-worker")
class ResilientWorker:

    @on_assignment
    async def handle(self, intent):
        try:
            result = await call_external_api(intent.state)
            return {"result": result}
        except TransientError as e:
            # Record the failure — protocol handles retry scheduling
            await self.client.record_failure(
                intent_id=intent.id,
                attempt_number=intent.state.get("attempt", 1),
                error_code="API_TIMEOUT",
                error_message=str(e),
                retry_scheduled_at=None  # Let the policy decide
            )
```

### Querying Failure History

```python
# Get failure history
failures = client.get_failures(intent.id)

for f in failures:
    print(f"Attempt {f.attempt_number}: {f.error_code} — {f.error_message}")
    if f.retry_scheduled_at:
        print(f"  Retry at: {f.retry_scheduled_at}")
```

### Retry Policies in YAML Workflows

```yaml
workflow:
  fetch_data:
    title: "Fetch External Data"
    assign: data-fetcher
    retry:
      max_attempts: 5
      backoff: exponential
      initial_delay_seconds: 2
      max_delay_seconds: 120
```

!!! warning "Idempotency"
    When using retry policies, ensure your agent handlers are idempotent — safe to call multiple times with the same input without side effects.

## Next Steps

- [LLM Adapters](adapters.md) — Automatic cost tracking for LLM calls
- [Governance & Arbitration](governance.md) — Budget enforcement and escalation
- [YAML Workflows](workflows.md) — Declarative retry and cost configuration
