# RFC-0001: OpenIntent Coordination Protocol (OICP) v1.0

**Status:** Proposed  
**Created:** 2026-02-01  
**Authors:** OpenIntent Contributors

---

## Abstract

This RFC specifies the OpenIntent Coordination Protocol (OICP), a standard for coordinating work across humans and autonomous agents using structured intent objects, append-only event logs, and optimistic concurrency control.

## Motivation

As AI agents become more capable, coordinating their work with each other and with humans becomes critical. Existing approaches rely on unstructured chat, which lacks:

- A shared source of truth for goals and progress
- Clear semantics for state updates
- Audit trails for accountability
- Concurrency control for parallel work

## Terminology

**Intent**
:   A structured object representing a goal, its constraints, current state, and lifecycle status.

**Event**
:   An immutable record of something that happened to an intent.

**Agent**
:   A participant (human or automated) that can read and modify intents.

**State Patch**
:   A structured update operation (append, set, remove) on intent state.

## Data Model

### Intent Object

```json
{
  "id": "uuid",
  "title": "string",
  "description": "string | null",
  "created_by": "string",
  "status": "draft | active | blocked | completed | abandoned",
  "constraints": { },
  "state": { },
  "confidence": "0-100",
  "version": "integer",
  "created_at": "ISO 8601",
  "updated_at": "ISO 8601"
}
```

### Event Object

```json
{
  "id": "uuid",
  "intent_id": "uuid",
  "event_type": "string",
  "actor": "string",
  "payload": { },
  "created_at": "ISO 8601"
}
```

### State Patch

```json
{
  "op": "append | set | remove",
  "path": "string (JSON pointer)",
  "value": "any"
}
```

## Lifecycle

Intents follow a defined state machine:

```
draft → active | abandoned
active → blocked | completed | abandoned
blocked → active | abandoned
```

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/v1/intents` | Create a new intent |
| `GET` | `/v1/intents/{id}` | Retrieve an intent by ID |
| `POST` | `/v1/intents/{id}/state` | Apply state patches |
| `POST` | `/v1/intents/{id}/events` | Emit an event |
| `GET` | `/v1/intents/{id}/events` | List events (paginated) |
| `POST` | `/v1/intents/{id}/agents` | Assign an agent |
| `POST` | `/v1/intents/{id}/status` | Transition status |

## Concurrency

Optimistic concurrency using `If-Match` headers:

- All mutating requests MUST include `If-Match: <version>`
- If version mismatch, server responds `409 Conflict`
- Successful updates increment version and return new value in `ETag`

## Why Agents Care

- **Shared truth:** No re-explaining context. Read from intent.
- **Resumability:** Pick up where another agent left off.
- **Structured updates:** Clear patch semantics.
- **Auditability:** All work is recorded in event log.

## Non-Goals

This protocol does not specify how agents should reason, what models they should use, or how they should decompose work. It provides coordination infrastructure, not agent architecture.
