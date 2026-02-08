# RFC-0006: Real-time Subscriptions v1.0

**Status:** Proposed  
**Created:** 2026-02-01  
**Authors:** OpenIntent Contributors  
**Requires:** [RFC-0001 (Intents)](./0001-intent-objects.md)

---

## Abstract

This RFC defines real-time subscription mechanisms for receiving notifications when intents change, events occur, or portfolios update.

## Motivation

Polling for updates is inefficient. Real-time subscriptions enable:

- **Instant reactions:** Agents respond immediately to state changes
- **Reduced latency:** No polling delays between updates
- **Lower overhead:** No wasted API calls checking for changes
- **Webhook integration:** Push notifications to external systems

## Subscription Model

```json
{
  "id": "uuid",
  "intent_id": "uuid | null",
  "portfolio_id": "uuid | null",
  "subscriber_id": "agent-id",
  "event_types": ["state_patched", "status_changed", "intent_created"],
  "webhook_url": "https://agent.example.com/webhook",
  "active": true,
  "expires_at": "ISO 8601 | null"
}
```

### Subscription Scopes

Subscriptions can target different scopes:

- **Intent-level:** Subscribe to events on a specific intent by setting `intent_id`
- **Portfolio-level:** Subscribe to all events within a portfolio by setting `portfolio_id`
- **Global:** Subscribe to all events of certain types (both fields null)

### Event Types

Subscribable event types include:

| Event Type | Description |
|-----------|-------------|
| `intent_created` | New intent created |
| `state_patched` | Intent state was updated |
| `status_changed` | Intent status transition |
| `agent_assigned` | Agent assigned to intent |
| `lease_acquired` | Agent acquired a lease |
| `lease_released` | Agent released a lease |
| `arbitration_requested` | Arbitration was requested |
| `decision_recorded` | Decision was recorded |

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/v1/subscriptions` | Create subscription |
| `GET` | `/v1/subscriptions` | List subscriptions (filter by intent/portfolio) |
| `DELETE` | `/v1/subscriptions/{id}` | Remove subscription |

### WebSocket (Future)

```
WS /v1/ws/subscribe — Real-time event stream
```

## Webhook Delivery

When a subscribed event occurs, the server sends an HTTP POST to the `webhook_url`:

```json
{
  "subscription_id": "uuid",
  "event": {
    "id": "uuid",
    "intent_id": "uuid",
    "event_type": "status_changed",
    "actor": "agent-research",
    "payload": { "from": "active", "to": "completed" },
    "created_at": "2026-02-01T12:00:00Z"
  }
}
```

Delivery follows at-least-once semantics with exponential backoff retry.

## Example: Webhook Subscription

```bash
# Subscribe to intent changes
curl -X POST http://localhost:8000/api/v1/subscriptions \
  -H "X-API-Key: dev-user-key" \
  -d '{
    "intent_id": "intent-uuid",
    "subscriber_id": "my-agent",
    "event_types": ["state_patched", "status_changed"],
    "webhook_url": "https://my-agent.example.com/webhook"
  }'
```

## Python SDK Usage

```python
from openintent import OpenIntentClient

client = OpenIntentClient(base_url="http://localhost:8000", api_key="key")

# Subscribe to intent events
sub = client.subscribe(
    intent_id="intent-uuid",
    event_types=["status_changed", "state_patched"]
)

# Stream events (async)
async for event in client.stream(intent_id="intent-uuid"):
    print(f"Event: {event.event_type}")
    print(f"Payload: {event.payload}")
```
