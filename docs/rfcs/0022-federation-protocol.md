# RFC-0022: Federation Protocol

**Status:** Proposed  
**Created:** 2026-02-25  
**Authors:** OpenIntent Contributors  
**Requires:** RFC-0001 (Intents), RFC-0003 (Leasing), RFC-0011 (Access Control), RFC-0016 (Agent Lifecycle), RFC-0021 (Messaging)

---

## Abstract

This RFC defines the federation contract for cross-server agent coordination. It covers how independent OpenIntent servers discover each other, dispatch intents to remote agents, receive results, and maintain governance coherence across organizational boundaries.

## Motivation

A single OpenIntent server handles intra-organization coordination well, but production agent systems frequently need to span multiple organizations, cloud regions, or trust boundaries. Without a standard federation mechanism, each deployment invents its own inter-server protocol, leading to incompatible implementations and security gaps.

Federation addresses three concrete needs:

1. **Cross-org agent access.** Organization A has a specialized research agent; Organization B needs to use it for a task. There is no standard way to discover, invoke, or pay for that agent's work.

2. **Geographic distribution.** A global deployment runs servers in three regions. Intents created in one region may need agents running in another. The protocol must route intents to the right server without manual configuration per intent.

3. **Trust boundaries.** An upstream server dispatches work to a downstream server. The downstream server must enforce its own governance policies while respecting the upstream's constraints. Neither server should blindly trust the other.

## Specification

### Federation Envelope

All cross-server communication uses a `FederationEnvelope`:

```json
{
  "envelope_id": "fed_abc123",
  "source_server": "https://server-a.example.com",
  "target_server": "https://server-b.example.com",
  "intent_snapshot": { },
  "delegation_scope": {
    "permissions": ["read", "write"],
    "denied_operations": [],
    "max_delegation_depth": 2,
    "budget_limit": 100.0
  },
  "callback_url": "https://server-a.example.com/api/v1/federation/callback",
  "trace_context": {
    "trace_id": "abc123",
    "parent_event_id": "evt_456"
  },
  "timestamp": "2026-02-25T00:00:00Z",
  "signature": null
}
```

### Agent Visibility

Agents declare their federation visibility:

| Visibility | Behavior |
|---|---|
| `public` | Listed in federation discovery, available to any peer |
| `unlisted` | Not listed in discovery, available if agent ID is known |
| `private` | Not available to federated requests (default) |

### Peer Relationships

Servers relate to each other as:

| Relationship | Direction | Use Case |
|---|---|---|
| `peer` | Bidirectional | Equal partners, mutual dispatch |
| `upstream` | Inbound only | Receives work from this server |
| `downstream` | Outbound only | Sends work to this server |

### Delegation Scope

Each envelope carries a `DelegationScope` that narrows per hop:

- **Permissions:** Intersection with parent scope (can only remove, never add)
- **Denied operations:** Union with parent scope (accumulates restrictions)
- **Max delegation depth:** Decremented per hop, dispatch rejected at zero
- **Budget limit:** Minimum of parent and local limit

```python
child_scope = parent_scope.attenuate(
    permissions=["read"],
    denied_operations=["delete"],
    max_delegation_depth=1,
    budget_limit=50.0
)
```

### Governance Propagation

When two servers' governance policies overlap, the strictest rule wins:

- **Booleans:** `require_human_approval = A or B` (if either requires it, the composed policy requires it)
- **Numerics:** `max_cost = min(A, B)` (the lower limit applies)
- **Observability:** Merged (union of required fields)

```python
composed = FederationPolicy.compose_strictest(local_policy, remote_policy)
```

### Federation Callbacks

After processing a dispatched intent, the receiving server sends a callback:

```json
{
  "envelope_id": "fed_abc123",
  "event_type": "completed",
  "intent_id": "intent_789",
  "result": { },
  "attestation": { }
}
```

Callbacks use at-least-once delivery with idempotency keys.

### Discovery

Servers publish federation capabilities at:

```
GET /.well-known/openintent-federation.json
```

Response:

```json
{
  "server_id": "server-a",
  "server_url": "https://server-a.example.com",
  "protocol_version": "0.14.0",
  "capabilities": ["dispatch", "receive", "callbacks"],
  "public_agents": ["researcher", "summarizer"],
  "trust_policy": "allowlist",
  "did": "did:web:server-a.example.com"
}
```

### REST Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/federation/status` | Server federation status |
| `GET` | `/api/v1/federation/agents` | List federated agents |
| `POST` | `/api/v1/federation/dispatch` | Dispatch intent to remote server |
| `POST` | `/api/v1/federation/receive` | Receive dispatched intent |

### Federation-Aware Leasing

Federated intents follow standard leasing (RFC-0003) on the receiving server. The originating server retains intent authority — the receiving server operates on a copy.

## Security Considerations

Federation security is defined separately in RFC-0023. Without RFC-0023, federation operates in trusted mode (suitable for intra-org deployments). RFC-0023 is required for cross-org or public federation.

## SDK Implementation

See the [Federation Guide](../guide/federation.md) for Python SDK usage and the [Federation API Reference](../api/federation.md) for complete class documentation.
