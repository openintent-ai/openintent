# RFC-0010: Retry & Failure Policies v1.0

**Status:** Proposed  
**Created:** 2026-02-01  
**Authors:** OpenIntent Contributors  
**Requires:** [RFC-0001 (Intents)](./0001-intent-objects.md), [RFC-0003 (Leasing)](./0003-agent-leasing.md)

---

## Abstract

This RFC defines retry policies and failure handling for intents, enabling resilient agent coordination with configurable backoff strategies and fallback agents.

## Motivation

Agent workflows fail for various reasons:

- **Transient errors:** Network issues, rate limits, temporary outages
- **Resource exhaustion:** Token limits, timeouts, memory constraints
- **External dependencies:** Third-party API failures, data unavailability
- **Agent errors:** Bugs, invalid outputs, unexpected states

Retry policies define how to recover from these failures automatically.

## Retry Policy Model

```json
{
  "id": "uuid",
  "intent_id": "uuid",
  "strategy": "none | fixed | exponential | linear",
  "max_retries": 3,
  "base_delay_ms": 1000,
  "max_delay_ms": 60000,
  "fallback_agent_id": "agent-backup | null",
  "failure_threshold": 3
}
```

### Strategies

| Strategy | Description | Delay Pattern |
|----------|------------|---------------|
| `none` | No automatic retries | N/A |
| `fixed` | Constant delay between retries | 1s, 1s, 1s |
| `exponential` | Delay doubles each attempt (recommended) | 1s, 2s, 4s, 8s |
| `linear` | Delay increases linearly | 1s, 2s, 3s, 4s |

## Failure Record Model

```json
{
  "id": "uuid",
  "intent_id": "uuid",
  "agent_id": "agent-research",
  "attempt_number": 2,
  "error_code": "RATE_LIMIT",
  "error_message": "Rate limit exceeded, retry after 60s",
  "retry_scheduled_at": "ISO 8601 | null",
  "resolved_at": "ISO 8601 | null",
  "metadata": { "http_status": 429 }
}
```

### Error Codes

| Code | Description | Typically Retryable |
|------|------------|-------------------|
| `RATE_LIMIT` | Provider rate limit exceeded | Yes |
| `TIMEOUT` | Operation timed out | Yes |
| `NETWORK_ERROR` | Network connectivity failure | Yes |
| `INVALID_OUTPUT` | Agent produced invalid output | Maybe |
| `BUDGET_EXCEEDED` | Cost limit reached | No (requires human) |
| `PERMISSION_DENIED` | Access control violation | No |

## Fallback Agents

When retries are exhausted, the system can automatically assign a fallback agent:

1. Current agent's lease is released
2. Fallback agent is assigned via leasing (RFC-0003)
3. Previous agent's state and failure history are available to the fallback
4. A `fallback_triggered` event is recorded

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `PUT` | `/v1/intents/{id}/retry-policy` | Set retry policy |
| `GET` | `/v1/intents/{id}/retry-policy` | Get retry policy |
| `POST` | `/v1/intents/{id}/failures` | Record failure |
| `GET` | `/v1/intents/{id}/failures` | Get failure history |

## Example: Configuring Exponential Backoff

```bash
# Set retry policy with exponential backoff
curl -X PUT http://localhost:8000/api/v1/intents/{id}/retry-policy \
  -H "X-API-Key: dev-user-key" \
  -d '{
    "strategy": "exponential",
    "max_retries": 5,
    "base_delay_ms": 1000,
    "max_delay_ms": 60000,
    "fallback_agent_id": "agent-backup"
  }'

# Record a failure
curl -X POST http://localhost:8000/api/v1/intents/{id}/failures \
  -H "X-API-Key: agent-research-key" \
  -d '{
    "agent_id": "agent-research",
    "attempt_number": 1,
    "error_code": "TIMEOUT",
    "error_message": "Request timed out after 30s",
    "retry_scheduled_at": "2026-02-15T10:05:00Z"
  }'
```

## Cross-RFC Interactions

| RFC | Interaction |
|-----|------------|
| RFC-0003 (Leasing) | Lease released on fallback; new lease acquired by fallback agent |
| RFC-0009 (Costs) | Failed attempts still record costs |
| RFC-0012 (Tasks) | Task-level retry policies override intent-level policies |
