---
title: Cross-Server Federation
---

# Cross-Server Federation

Federation lets agents on one OpenIntent server dispatch work to agents on another. Instead of building monolithic multi-agent systems, you split capabilities across servers and let them coordinate through signed envelopes, scoped delegation, and trust policies. Two RFCs define the protocol: **RFC-0022** (federation mechanics) and **RFC-0023** (federation security).

---

## Quick Start

Two servers: `analytics.example.com` runs a data-processing agent, `research.example.com` runs a research agent that needs data processed remotely.

### 1. YAML Workflow with Federation

```yaml
openintent: "1.0"
info:
  name: "Federated Research Pipeline"

federation:
  peers:
    - url: https://analytics.example.com
      relationship: downstream
      trust_policy: allowlist
  visibility: public
  trust_policy: allowlist

workflow:
  collect:
    assign: researcher
  analyze:
    assign: federation://analytics.example.com/data-processor
    depends_on: [collect]
    delegation_scope:
      permissions: [state.patch, events.log]
      max_delegation_depth: 1
```

### 2. Python — Configure Federation

```python
from openintent.federation import Federation
from openintent.federation.security import ServerIdentity

@Federation(
    server_url="https://research.example.com",
    identity="did:web:research.example.com",
    trust_policy="allowlist",
    peers=["https://analytics.example.com"],
    visibility_default="public",
)
class MyFederatedServer:
    pass
```

### 3. Dispatch an Intent

```python
from openintent import Client

client = Client("https://research.example.com")

result = client.federation_dispatch(
    intent_id="intent-001",
    target_server="https://analytics.example.com",
    agent_id="data-processor",
    delegation_scope={
        "permissions": ["state.patch", "events.log"],
        "max_delegation_depth": 1,
    },
    callback_url="https://research.example.com/api/v1/federation/callback",
)

print(result["dispatch_id"])   # UUID tracking the dispatch
print(result["status"])        # "accepted"
```

!!! tip "Zero ceremony"
    The `@Federation` decorator handles identity generation, trust enforcement, and endpoint registration. Your agents don't need to know they're federated — the framework routes dispatched intents transparently.

---

## Agent Visibility

Every agent registered on a federated server has a visibility level that controls whether remote servers can discover it:

| Visibility | Discovery behavior |
|------------|-------------------|
| `public` | Listed in `GET /api/v1/federation/agents` for all callers. |
| `unlisted` | Only listed for known peers (servers in the peer list). |
| `private` | Never listed. Can still receive dispatched work if addressed directly. |

Set visibility per agent:

```python
from openintent.agents import Agent, on_assignment

@Agent("data-processor", federation_visibility="public")
class DataProcessor:
    @on_assignment
    async def handle(self, intent):
        return {"processed": True}
```

Or set a server-wide default:

```python
@Federation(
    server_url="https://analytics.example.com",
    visibility_default="unlisted",
    trust_policy="allowlist",
    peers=["https://research.example.com"],
)
class AnalyticsServer:
    pass
```

---

## Peer Relationships

Peers are remote servers your server trusts to send or receive federated work. Each peer has a **relationship** that describes the direction of trust:

| Relationship | Description |
|-------------|-------------|
| `peer` | Bidirectional — both servers can dispatch to each other. |
| `upstream` | The remote server sends work to you. |
| `downstream` | You send work to the remote server. |

Configure peers in YAML:

```yaml
federation:
  peers:
    - url: https://analytics.example.com
      relationship: downstream
      trust_policy: allowlist
    - url: https://ingest.example.com
      relationship: upstream
      trust_policy: allowlist
```

Or programmatically:

```python
from openintent.federation.models import PeerInfo, PeerRelationship, TrustPolicy

peer = PeerInfo(
    server_url="https://analytics.example.com",
    relationship=PeerRelationship.DOWNSTREAM,
    trust_policy=TrustPolicy.ALLOWLIST,
)
```

---

## Delegation Scope

When you dispatch an intent to a remote server, you control what the remote agent is allowed to do via a **DelegationScope**. This prevents a remote server from escalating its own permissions.

```python
from openintent.federation.models import DelegationScope

scope = DelegationScope(
    permissions=["state.patch", "events.log"],
    denied_operations=["intent.delete"],
    max_delegation_depth=1,
    expires_at="2026-12-31T23:59:59Z",
)
```

**Key fields:**

| Field | Description |
|-------|-------------|
| `permissions` | Operations the remote agent is allowed to perform. |
| `denied_operations` | Explicit deny list — overrides permissions. |
| `max_delegation_depth` | How many hops the remote server can re-delegate (0 = no re-delegation). |
| `expires_at` | ISO 8601 timestamp after which the scope is invalid. |

### Scope Attenuation

When a remote server re-delegates to a third server, the scope is **attenuated**: permissions are intersected, denied operations are merged, and delegation depth decreases.

```python
parent_scope = DelegationScope(
    permissions=["state.patch", "events.log", "intent.read"],
    max_delegation_depth=2,
)

child_scope = DelegationScope(
    permissions=["state.patch", "events.log"],
    denied_operations=["intent.delete"],
    max_delegation_depth=1,
)

attenuated = parent_scope.attenuate(child_scope)
# attenuated.permissions = ["events.log", "state.patch"]
# attenuated.denied_operations = ["intent.delete"]
# attenuated.max_delegation_depth = 1
```

!!! warning "Attenuation is monotonic"
    A child scope can never have more permissions than its parent. The `attenuate()` method enforces this by intersecting permission sets and taking the minimum delegation depth.

---

## Governance Propagation

Federation policies let the originating server enforce governance, budget, and observability rules on the remote server:

```python
from openintent.federation.models import FederationPolicy

policy = FederationPolicy(
    governance={
        "require_human_approval": True,
        "max_autonomous_steps": 5,
    },
    budget={
        "max_llm_tokens": 10000,
        "cost_ceiling_usd": 1.50,
    },
    observability={
        "require_trace_propagation": True,
        "log_level": "info",
    },
)
```

When two policies meet (e.g., the dispatcher's policy and the receiver's local policy), they compose using **strictest-wins**:

```python
local_policy = FederationPolicy(
    governance={"require_human_approval": False, "max_autonomous_steps": 10},
    budget={"max_llm_tokens": 50000},
)

composed = local_policy.compose_strictest(policy)
# composed.governance["require_human_approval"] = True   (stricter)
# composed.governance["max_autonomous_steps"] = 5        (lower)
# composed.budget["max_llm_tokens"] = 10000              (lower)
```

---

## Federation Envelopes

Every dispatched intent is wrapped in a **FederationEnvelope** — a self-contained message that carries the intent data, delegation scope, policy, and cryptographic signature.

```python
from openintent.federation.models import FederationEnvelope

envelope = FederationEnvelope(
    dispatch_id="d-123",
    source_server="https://research.example.com",
    target_server="https://analytics.example.com",
    intent_id="intent-001",
    intent_title="Process Q1 Data",
    intent_description="Run analytics on Q1 sales dataset",
    intent_state={"dataset": "q1-sales"},
    delegation_scope=scope,
    federation_policy=policy,
    trace_context={"trace_id": "abc123", "span_id": "def456"},
    callback_url="https://research.example.com/api/v1/federation/callback",
)

envelope_dict = envelope.to_dict()
```

The envelope is signed before dispatch and verified on receipt. See [Envelope Signing](#envelope-signing) below.

---

## Attestations

When a remote server completes work, it returns a **FederationAttestation** — a signed record of what happened, including governance compliance and resource usage.

```python
from openintent.federation.models import FederationAttestation

attestation = FederationAttestation(
    dispatch_id="d-123",
    governance_compliant=True,
    usage={
        "llm_tokens": 4200,
        "cost_usd": 0.35,
        "duration_seconds": 12.5,
    },
    trace_references=["trace-abc123"],
    timestamp="2026-02-01T10:30:00Z",
)
```

Attestations are delivered via callbacks and can be cryptographically signed for tamper-evidence.

---

## Callbacks

The dispatching server can specify a `callback_url` to receive real-time updates about federated work:

```python
from openintent.federation.models import FederationCallback, CallbackEventType

callback = FederationCallback(
    dispatch_id="d-123",
    event_type=CallbackEventType.STATE_DELTA,
    state_delta={"progress": 0.75, "phase": "analysis"},
    trace_id="abc123",
    idempotency_key="cb-d-123-003",
    timestamp="2026-02-01T10:30:00Z",
)
```

**Callback event types:**

| Event Type | Description |
|-----------|-------------|
| `state_delta` | Partial state update from the remote agent. |
| `status_changed` | The remote intent changed status (e.g., assigned, completed). |
| `attestation` | Governance attestation delivered. |
| `budget_warning` | Remote execution approaching budget limits. |
| `completed` | Remote work finished successfully. |
| `failed` | Remote work failed. |

Handle callbacks in your agent with lifecycle hooks:

```python
from openintent.federation import on_federation_callback, on_budget_warning

@Agent("coordinator")
class CoordinatorAgent:
    @on_federation_callback
    async def handle_callback(self, callback):
        if callback.event_type == "completed":
            print(f"Remote work done: {callback.state_delta}")

    @on_budget_warning
    async def handle_budget(self, callback):
        print(f"Budget warning for dispatch {callback.dispatch_id}")
```

---

## Discovery

Every federated server exposes a discovery manifest at a well-known URL:

```
GET /.well-known/openintent-federation.json
```

Response:

```json
{
  "server_did": "did:web:analytics.example.com",
  "server_url": "https://analytics.example.com",
  "protocol_version": "0.1",
  "trust_policy": "allowlist",
  "visibility_default": "public",
  "supported_rfcs": ["RFC-0022", "RFC-0023"],
  "peers": ["https://research.example.com"],
  "public_key": "base64-encoded-ed25519-public-key",
  "endpoints": {
    "status": "/api/v1/federation/status",
    "agents": "/api/v1/federation/agents",
    "dispatch": "/api/v1/federation/dispatch",
    "receive": "/api/v1/federation/receive"
  }
}
```

The manifest includes the server's DID, public key, trust policy, and available endpoints. Remote servers use this to validate identity and negotiate trust before dispatching work.

A DID document is also available at `/.well-known/did.json` for W3C DID resolution.

---

## Envelope Signing

Envelopes are signed using the server's Ed25519 private key (or HMAC-SHA256 fallback) before dispatch:

```python
from openintent.federation.security import ServerIdentity, sign_envelope

identity = ServerIdentity.generate("https://research.example.com")

envelope_dict = envelope.to_dict()
signature = sign_envelope(identity, envelope_dict)
envelope_dict["signature"] = signature
```

The receiving server verifies the signature using the sender's public key (obtained from the discovery manifest or DID document):

```python
from openintent.federation.security import verify_envelope_signature

is_valid = verify_envelope_signature(
    public_key_b64=sender_public_key,
    envelope_dict=received_envelope,
    signature_b64=received_envelope["signature"],
)
```

Signing uses canonical JSON serialization: keys sorted alphabetically, minimal separators, `signature` field excluded from the signing input.

---

## Trust Policies

Trust policies control which remote servers are allowed to dispatch work to your server:

| Policy | Behavior |
|--------|----------|
| `open` | Accept dispatches from any server. |
| `allowlist` | Only accept from servers in the peer list. **Recommended default.** |
| `trustless` | Reject all incoming dispatches. |

```python
from openintent.federation.security import TrustEnforcer
from openintent.federation.models import TrustPolicy

enforcer = TrustEnforcer(
    policy=TrustPolicy.ALLOWLIST,
    allowed_peers=["https://research.example.com", "did:web:research.example.com"],
)

enforcer.is_trusted("https://research.example.com")     # True
enforcer.is_trusted("https://unknown.example.com")      # False

enforcer.add_peer("https://new-partner.example.com")
enforcer.is_trusted("https://new-partner.example.com")  # True
```

Trust enforcement supports both server URLs and DID identifiers. The `TrustEnforcer` checks both when evaluating incoming dispatches.

---

## UCAN Tokens

For fine-grained delegation across server boundaries, federation uses **UCAN (User Controlled Authorization Networks)** tokens. UCANs encode delegation scope, expiry, and a proof chain that links back to the original authorizer.

```python
from openintent.federation.security import UCANToken, ServerIdentity
from openintent.federation.models import DelegationScope

identity = ServerIdentity.generate("https://research.example.com")

token = UCANToken(
    issuer="did:web:research.example.com",
    audience="did:web:analytics.example.com",
    scope=DelegationScope(
        permissions=["state.patch", "events.log"],
        max_delegation_depth=2,
    ),
)

encoded = token.encode(identity)   # JWT-like string: header.payload.signature
decoded = UCANToken.decode(encoded)

print(decoded.is_active())    # True (within time window)
print(decoded.is_expired())   # False
```

### Token Attenuation

A server that received a UCAN can attenuate it and pass a weaker token to a third server:

```python
child_scope = DelegationScope(
    permissions=["state.patch"],
    max_delegation_depth=1,
)

child_token = token.attenuate(
    audience="did:web:third-server.example.com",
    child_scope=child_scope,
    identity=analytics_identity,
)

# child_token.proof_chain contains the parent token
# child_token.scope.permissions is intersected with parent
```

!!! warning "Delegation depth"
    If `max_delegation_depth` reaches 0, further attenuation raises `ValueError`. This prevents unbounded delegation chains.

---

## SSRF Protection

All outbound federation URLs (target servers, callback URLs) are validated against SSRF attacks before any HTTP request is made:

```python
from openintent.federation.security import validate_ssrf

validate_ssrf("https://analytics.example.com")   # True — public URL
validate_ssrf("http://localhost:8080")            # False — blocked
validate_ssrf("http://169.254.169.254")           # False — metadata endpoint
validate_ssrf("http://10.0.0.5/internal")         # False — private network
```

**Blocked patterns:**

- `localhost`, `127.0.0.1`, `0.0.0.0`, `::1`
- AWS/GCP metadata endpoints (`169.254.169.254`, `metadata.google.internal`)
- Private network ranges (`10.*`, `172.*`, `192.168.*`)
- Internal domains (`*.internal`, `*.local`)

The server rejects dispatch and callback requests that fail SSRF validation with a `400 Bad Request` response.

---

## HTTP Message Signatures

For request-level authentication (beyond envelope signing), federation supports HTTP Message Signatures per RFC 9421:

```python
from openintent.federation.security import MessageSignature, ServerIdentity

identity = ServerIdentity.generate("https://research.example.com")

sig = MessageSignature.create(
    identity=identity,
    method="POST",
    target_uri="https://analytics.example.com/api/v1/federation/receive",
    content_type="application/json",
    body=b'{"dispatch_id": "d-123"}',
)

headers = {
    "Signature-Input": sig.to_header(),
    "Signature": sig.signature_header(),
}
```

This signs the HTTP method, target URI, content type, and content digest — ensuring the request hasn't been tampered with in transit.

---

## Federation Lifecycle Hooks

Agents can react to federation events with dedicated lifecycle decorators:

```python
from openintent.agents import Agent, on_assignment
from openintent.federation import (
    on_federation_received,
    on_federation_callback,
    on_budget_warning,
)

@Agent("coordinator")
class FederatedCoordinator:
    @on_assignment
    async def handle(self, intent):
        return {"status": "processing"}

    @on_federation_received
    async def on_received(self, envelope):
        """Called when this server receives a federated dispatch."""
        print(f"Received dispatch {envelope.dispatch_id} from {envelope.source_server}")

    @on_federation_callback
    async def on_callback(self, callback):
        """Called when a remote server sends a callback for our dispatch."""
        print(f"Callback: {callback.event_type} for {callback.dispatch_id}")

    @on_budget_warning
    async def on_budget(self, callback):
        """Called when remote execution approaches budget limits."""
        print(f"Budget warning: {callback.state_delta}")
```

---

## Best Practices

**Use `allowlist` trust policy in production.** The `open` policy is convenient for development but should never be used in production. Explicitly list trusted peers.

**Set delegation depth to 1 unless you need multi-hop.** Each additional hop adds latency, reduces permissions through attenuation, and increases the attack surface.

**Always set `callback_url` for long-running dispatches.** Without callbacks, you have no visibility into remote execution progress. Use idempotency keys on callbacks to handle retries.

**Enable trace context propagation.** Pass `trace_context` in dispatch requests so distributed traces span server boundaries. This integrates with [distributed tracing](distributed-tracing.md).

**Validate SSRF before making any outbound request.** The SDK does this automatically for dispatch and callback URLs, but if you build custom federation logic, always call `validate_ssrf()` first.

**Sign all envelopes.** Even with `allowlist` trust, envelope signing prevents tampering in transit. The overhead is negligible — Ed25519 signatures take microseconds.

---

## Next Steps

<div class="oi-features" style="margin-top: 1em;">
  <div class="oi-feature">
    <div class="oi-feature__title">Federation Examples</div>
    <p class="oi-feature__desc">Runnable examples for dispatch, receive, signing, and multi-hop delegation.</p>
    <a href="../../examples/federation/" class="oi-feature__link">See examples</a>
  </div>
  <div class="oi-feature">
    <div class="oi-feature__title">Federation API Reference</div>
    <p class="oi-feature__desc">Complete API docs for all federation classes, decorators, and endpoints.</p>
    <a href="../../api/federation/" class="oi-feature__link">API reference</a>
  </div>
  <div class="oi-feature">
    <div class="oi-feature__title">RFC-0022</div>
    <p class="oi-feature__desc">Full specification for cross-server federation protocol.</p>
    <a href="../../rfcs/0022-federation/" class="oi-feature__link">Read the RFC</a>
  </div>
  <div class="oi-feature">
    <div class="oi-feature__title">RFC-0023</div>
    <p class="oi-feature__desc">Federation security: identity, signing, UCAN tokens, and trust policies.</p>
    <a href="../../rfcs/0023-federation-security/" class="oi-feature__link">Read the RFC</a>
  </div>
</div>
