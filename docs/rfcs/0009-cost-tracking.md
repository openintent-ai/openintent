# RFC-0009: Cost & Resource Tracking v1.0

**Status:** Proposed  
**Created:** 2026-02-01  
**Authors:** OpenIntent Contributors  
**Requires:** [RFC-0001 (Intents)](./0001-intent-objects.md)

---

## Abstract

This RFC defines mechanisms for tracking costs and resource usage per intent and agent, enabling budgeting, optimization, and accountability in multi-agent systems.

## Motivation

Multi-agent workflows consume resources that need tracking:

- **Token usage:** LLM API calls consume tokens with associated costs
- **API costs:** External service calls may have per-request pricing
- **Compute time:** Processing time for resource-intensive tasks
- **Budget enforcement:** Prevent runaway costs in autonomous agents

## Cost Record Model

```json
{
  "id": "uuid",
  "intent_id": "uuid",
  "agent_id": "agent-research",
  "cost_type": "tokens | api_call | compute | custom",
  "amount": 1500,
  "unit": "tokens | cents | seconds | custom",
  "provider": "openai | anthropic | google | null",
  "metadata": {
    "model": "gpt-4",
    "prompt_tokens": 1200,
    "completion_tokens": 300
  },
  "recorded_at": "ISO 8601"
}
```

### Cost Types

| Type | Description | Typical Unit |
|------|------------|-------------|
| `tokens` | LLM token consumption | tokens |
| `api_call` | External API invocation | cents |
| `compute` | Processing time | seconds |
| `custom` | User-defined resource | custom |

## Budget Enforcement

Intents can define budget constraints:

```json
{
  "constraints": {
    "budget": {
      "max_total_cents": 10000,
      "max_per_agent_cents": 2000,
      "max_per_call_cents": 500,
      "alert_threshold_percent": 80
    }
  }
}
```

When spending approaches the threshold, the server emits a `budget_alert` event. When the budget is exceeded, the server can block further operations or require human approval.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/v1/intents/{id}/costs` | Record cost |
| `GET` | `/v1/intents/{id}/costs` | Get costs with summary |

### Response Format

```json
{
  "costs": [],
  "summary": {
    "total": 5000,
    "by_type": { "tokens": 4500, "api_call": 500 },
    "by_agent": { "agent-research": 3000, "agent-synth": 2000 }
  }
}
```

## Example: Tracking LLM Costs

```bash
# Record token usage after an LLM call
curl -X POST http://localhost:8000/api/v1/intents/{id}/costs \
  -H "X-API-Key: agent-research-key" \
  -d '{
    "agent_id": "agent-research",
    "cost_type": "tokens",
    "amount": 1500,
    "unit": "tokens",
    "provider": "openai",
    "metadata": {
      "model": "gpt-4",
      "prompt_tokens": 1200,
      "completion_tokens": 300
    }
  }'
```

## Cross-RFC Interactions

| RFC | Interaction |
|-----|------------|
| RFC-0004 (Portfolios) | Aggregate cost tracking across portfolio intents |
| RFC-0008 (LLM Integration) | Automatic cost recording for LLM calls |
| RFC-0013 (Coordinators) | Coordinator guardrails can enforce budget limits |
