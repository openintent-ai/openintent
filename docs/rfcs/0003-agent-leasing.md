# RFC-0003: Arbitration, Governance & Agent Leasing v1.0

**Status:** Proposed  
**Created:** 2026-02-01  
**Authors:** OpenIntent Contributors  
**Requires:** [RFC-0001 (Intents)](./0001-intent-objects.md)

---

## Abstract

This RFC defines governance extensions for the OpenIntent protocol, including agent leasing for ownership and collision prevention, arbitration requests, decision records, and delegation contracts.

## Motivation

As multiple agents work on the same intent, coordination challenges emerge:

- **Collision:** Two agents modifying the same scope simultaneously
- **Responsibility:** Unclear ownership of work items
- **Escalation:** No path when agents disagree or are uncertain
- **Provenance:** Decisions need audit trails

## Agent Leasing

Leasing assigns temporary ownership of an intent scope to a specific agent. This prevents collisions and introduces clear responsibility.

### Lease Object

```json
{
  "id": "uuid",
  "intent_id": "uuid",
  "agent_id": "string",
  "scope": "string (e.g., 'hotel_search', 'flight_booking')",
  "status": "active | released | expired | revoked",
  "expires_at": "ISO 8601",
  "acquired_at": "ISO 8601",
  "released_at": "ISO 8601 | null"
}
```

### Lease Semantics

- A scope can only have one active lease at a time
- Leases have mandatory expiration to prevent deadlocks
- Agents can release leases early when work is complete
- Expired leases automatically transition to `expired` status
- Governance/admin actions can revoke leases (status becomes `revoked`)
- State patches to a leased scope require holding the lease

## Governance Objects

### ArbitrationRequest

Request human or higher-authority intervention when an agent is uncertain or in conflict.

```json
{
  "id": "uuid",
  "intent_id": "uuid",
  "requestor": "string",
  "reason": "string",
  "options": [{ "label": "...", "rationale": "..." }],
  "status": "pending | resolved",
  "resolution": "string | null"
}
```

### DecisionRecord

Immutable record of a consequential decision with evidence and rationale.

```json
{
  "id": "uuid",
  "intent_id": "uuid",
  "decision": "string",
  "rationale": "string",
  "decided_by": "string",
  "evidence": [{ "source": "...", "summary": "..." }],
  "created_at": "ISO 8601"
}
```

### DelegationContract

Formal delegation of authority from one agent/human to another with constraints.

```json
{
  "id": "uuid",
  "delegator": "string",
  "delegate": "string",
  "scope": { "intents": ["uuid"], "actions": ["..."] },
  "constraints": { "max_cost": 1000, "requires_approval": false },
  "expires_at": "ISO 8601"
}
```

## Endpoints

### Leasing

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/v1/intents/{id}/leases` | Acquire a lease for a scope |
| `GET` | `/v1/intents/{id}/leases` | List active leases |
| `DELETE` | `/v1/intents/{id}/leases/{leaseId}` | Release a lease |

### Governance

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/v1/intents/{id}/arbitrate` | Request arbitration |
| `GET` | `/v1/intents/{id}/decisions` | List decision records |
| `POST` | `/v1/intents/{id}/decisions` | Record a decision |

## Example: Lease-Protected Work

```bash
# Acquire a lease for hotel_search scope (5 minute duration)
curl -X POST http://localhost:8000/api/v1/intents/{id}/leases \
  -H "Content-Type: application/json" \
  -H "X-API-Key: agent-research-key" \
  -d '{"agent_id": "agent-research", "scope": "hotel_search", "duration_seconds": 300}'

# Now only this agent can modify the hotel_search scope
curl -X POST http://localhost:8000/api/v1/intents/{id}/state \
  -H "X-API-Key: agent-research-key" \
  -H "If-Match: 1" \
  -d '{"patches": [{"op": "set", "path": "/hotel_search/results", "value": [...]}]}'

# Release the lease when done
curl -X DELETE http://localhost:8000/api/v1/intents/{id}/leases/{leaseId} \
  -H "X-API-Key: agent-research-key"
```
