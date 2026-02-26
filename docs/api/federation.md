# Federation API Reference

Cross-server agent coordination (RFC-0022) with cryptographic security (RFC-0023).

!!! tip "Quick setup"
    Use `@Federation` on your server class and `federation_visibility=` on `@Agent` to get started. See the [Federation Guide](../guide/federation.md) for a walkthrough.

## Federation Decorator

### Federation

`@Federation(server=, identity=, key_path=, visibility_default=, trust_policy=, peers=, server_url=)` — class decorator that configures a server for cross-server federation.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `server` | `object` | `None` | Server instance with `.config` and `.app` attributes; used to auto-derive `server_url` and register federation routes |
| `identity` | `str` | `None` | Override the generated `did:web` identifier |
| `key_path` | `str` | `None` | Path to an Ed25519 private key file; generates a new key pair if omitted |
| `visibility_default` | `str` | `"public"` | Default agent visibility: `"public"`, `"unlisted"`, or `"private"` |
| `trust_policy` | `str` | `"allowlist"` | Trust policy: `"open"`, `"allowlist"`, or `"trustless"` |
| `peers` | `list[str]` | `None` | List of trusted peer server URLs |
| `server_url` | `str` | `None` | Explicit server URL (used when `server` is not provided) |

The decorator sets the following attributes on the decorated class:

| Attribute | Type | Description |
|-----------|------|-------------|
| `_federation_configured` | `bool` | Always `True` after decoration |
| `_federation_trust_policy_name` | `str` | The trust policy string |
| `_federation_visibility_default_name` | `str` | The visibility default string |
| `_federation_peer_list` | `list[str]` | Configured peer URLs |

Instance attributes set in `__init__`:

| Attribute | Type | Description |
|-----------|------|-------------|
| `self._federation_identity` | `ServerIdentity` | The server's cryptographic identity |
| `self._federation_trust_policy` | `TrustPolicy` | Parsed trust policy enum |
| `self._federation_visibility_default` | `AgentVisibility` | Parsed visibility enum |
| `self._federation_peers` | `list[str]` | Peer URL list |
| `self._federation_server_url` | `str` | Resolved server URL |

```python
from openintent.federation import Federation

@Federation(
    server_url="https://api.example.com",
    trust_policy="allowlist",
    peers=["https://partner.example.com"],
    visibility_default="public",
)
class MyFederationHub:
    pass
```

## Lifecycle Decorators

### on_federation_received

`@on_federation_received` — marks a method as the handler for incoming federated intents.

```python
from openintent.federation import on_federation_received

class MyAgent:
    @on_federation_received
    async def handle_received(self, envelope):
        print(f"Received dispatch {envelope.dispatch_id} from {envelope.source_server}")
```

Sets `func._openintent_handler = "federation_received"`.

### on_federation_callback

`@on_federation_callback` — marks a method as the handler for federation callback events (state deltas, completions, failures).

```python
from openintent.federation import on_federation_callback

class MyAgent:
    @on_federation_callback
    async def handle_callback(self, callback):
        print(f"Callback for dispatch {callback.dispatch_id}: {callback.event_type}")
```

Sets `func._openintent_handler = "federation_callback"`.

### on_budget_warning

`@on_budget_warning` — marks a method as the handler for budget threshold warnings during federated work.

```python
from openintent.federation import on_budget_warning

class MyAgent:
    @on_budget_warning
    async def handle_budget(self, warning):
        print(f"Budget warning: {warning}")
```

Sets `func._openintent_handler = "budget_warning"`.

## Security Classes (RFC-0023)

### ServerIdentity

`ServerIdentity(server_url, did=, private_key_bytes=, public_key_bytes=)` — represents a server's cryptographic identity using `did:web` and Ed25519 keys.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `server_url` | `str` | required | The server's public URL |
| `did` | `str` | `""` | DID identifier; auto-generated as `did:web:{domain}` if empty |
| `private_key_bytes` | `bytes \| None` | `None` | Ed25519 private key (raw 32 bytes) |
| `public_key_bytes` | `bytes \| None` | `None` | Ed25519 public key (raw 32 bytes) |

#### Class Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `ServerIdentity.generate(server_url)` | `ServerIdentity` | Generate a new Ed25519 key pair (falls back to HMAC-SHA256 without `cryptography`) |
| `ServerIdentity.from_key_file(server_url, key_path)` | `ServerIdentity` | Load identity from a private key file |

#### Instance Methods & Properties

| Method / Property | Returns | Description |
|-------------------|---------|-------------|
| `save_key(key_path)` | `None` | Write the private key bytes to a file |
| `public_key_b64` | `str` | Base64-encoded public key |
| `did_document()` | `dict` | W3C DID Document with `Ed25519VerificationKey2020` |
| `sign(message)` | `str` | Sign bytes and return base64-encoded signature |
| `verify(message, signature_b64)` | `bool` | Verify a base64-encoded signature against this identity |

```python
from openintent.federation import ServerIdentity

identity = ServerIdentity.generate("https://api.example.com")
print(identity.did)           # "did:web:api.example.com"
print(identity.public_key_b64)  # base64 public key

sig = identity.sign(b"hello")
assert identity.verify(b"hello", sig)
```

### TrustEnforcer

`TrustEnforcer(policy, allowed_peers=)` — enforces trust policies for incoming federation requests.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `policy` | `TrustPolicy` | required | The trust policy to enforce |
| `allowed_peers` | `list[str] \| None` | `None` | List of trusted server URLs or DIDs |

#### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `is_trusted(source_server, source_did=)` | `bool` | Check if a source server is trusted under the current policy |
| `add_peer(peer)` | `None` | Add a server URL or DID to the allow list |
| `remove_peer(peer)` | `None` | Remove a server URL or DID from the allow list |

Trust policy behavior:

| Policy | Behavior |
|--------|----------|
| `open` | All servers are trusted |
| `allowlist` | Only servers in `allowed_peers` (by URL or DID) are trusted |
| `trustless` | No servers are trusted |

```python
from openintent.federation import TrustEnforcer, TrustPolicy

enforcer = TrustEnforcer(
    policy=TrustPolicy.ALLOWLIST,
    allowed_peers=["https://partner.example.com"],
)

assert enforcer.is_trusted("https://partner.example.com")
assert not enforcer.is_trusted("https://unknown.example.com")

enforcer.add_peer("https://new-partner.example.com")
assert enforcer.is_trusted("https://new-partner.example.com")
```

### UCANToken

`UCANToken(issuer, audience, scope, not_before=, expires_at=, nonce=, proof_chain=)` — UCAN delegation token for capability-based authorization.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `issuer` | `str` | required | DID of the token issuer |
| `audience` | `str` | required | DID of the token audience (recipient) |
| `scope` | `DelegationScope` | required | Permissions granted by this token |
| `not_before` | `int` | `0` | Unix timestamp; auto-set to `time.time()` if `0` |
| `expires_at` | `int` | `0` | Unix timestamp; auto-set to `not_before + 3600` if `0` |
| `nonce` | `str` | `""` | Random nonce; auto-generated if empty |
| `proof_chain` | `list[str]` | `[]` | Chain of parent UCAN tokens proving delegation authority |

#### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `to_dict()` | `dict` | Serialize to UCAN payload dict (keys: `iss`, `aud`, `scope`, `nbf`, `exp`, `nonce`, `prf`) |
| `UCANToken.from_dict(data)` | `UCANToken` | Deserialize from dict |
| `encode(identity)` | `str` | Encode as a signed JWT-like `header.payload.signature` string |
| `UCANToken.decode(token)` | `UCANToken` | Decode a UCAN token string (does not verify signature) |
| `is_expired()` | `bool` | Check if the token has expired |
| `is_active()` | `bool` | Check if the current time is within `[not_before, expires_at]` |
| `attenuate(audience, child_scope, identity)` | `UCANToken` | Create a child token with attenuated (reduced) permissions |

```python
from openintent.federation import UCANToken, DelegationScope, ServerIdentity

identity = ServerIdentity.generate("https://api.example.com")
scope = DelegationScope(permissions=["state.patch", "events.log"])

token = UCANToken(
    issuer=identity.did,
    audience="did:web:partner.example.com",
    scope=scope,
)

encoded = token.encode(identity)
decoded = UCANToken.decode(encoded)
assert decoded.issuer == identity.did
assert decoded.is_active()
```

### MessageSignature

`MessageSignature(key_id, algorithm=, created=, headers=, signature=)` — HTTP Message Signature per RFC 9421.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `key_id` | `str` | required | DID of the signing server |
| `algorithm` | `str` | `"ed25519"` | Signature algorithm |
| `created` | `int` | `0` | Unix timestamp; auto-set to `time.time()` if `0` |
| `headers` | `list[str]` | `["@method", "@target-uri", "content-type", "content-digest"]` | Signed HTTP components |
| `signature` | `str` | `""` | Base64-encoded signature value |

#### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `MessageSignature.create(identity, method, target_uri, content_type=, body=)` | `MessageSignature` | Create a signature for an HTTP request |
| `to_header()` | `str` | Format as `Signature-Input` header value |
| `signature_header()` | `str` | Format as `Signature` header value |

```python
from openintent.federation import MessageSignature, ServerIdentity
import json

identity = ServerIdentity.generate("https://api.example.com")
body = json.dumps({"intent_id": "i-123"}).encode()

sig = MessageSignature.create(
    identity=identity,
    method="POST",
    target_uri="https://partner.example.com/api/v1/federation/dispatch",
    body=body,
)

print(sig.to_header())        # Signature-Input header
print(sig.signature_header())  # Signature header
```

## Envelope Functions

### sign_envelope

`sign_envelope(identity, envelope_dict) -> str` — sign a federation envelope dict and return a base64 signature.

| Parameter | Type | Description |
|-----------|------|-------------|
| `identity` | `ServerIdentity` | The signing server's identity |
| `envelope_dict` | `dict` | The envelope data (the `"signature"` key is excluded from signing) |

Returns the base64-encoded signature string.

### verify_envelope_signature

`verify_envelope_signature(public_key_b64, envelope_dict, signature_b64) -> bool` — verify a federation envelope signature.

| Parameter | Type | Description |
|-----------|------|-------------|
| `public_key_b64` | `str` | Base64-encoded public key of the signer |
| `envelope_dict` | `dict` | The envelope data to verify |
| `signature_b64` | `str` | The base64-encoded signature |

Returns `True` if the signature is valid.

```python
from openintent.federation import sign_envelope, verify_envelope_signature, ServerIdentity

identity = ServerIdentity.generate("https://api.example.com")

envelope = {
    "dispatch_id": "d-123",
    "source_server": "https://api.example.com",
    "target_server": "https://partner.example.com",
    "intent_id": "i-456",
    "intent_title": "Research task",
}

sig = sign_envelope(identity, envelope)
assert verify_envelope_signature(identity.public_key_b64, envelope, sig)
```

## Utility Functions

### resolve_did_web

`resolve_did_web(did) -> str` — resolve a `did:web` identifier to the URL of its DID Document.

| Parameter | Type | Description |
|-----------|------|-------------|
| `did` | `str` | A `did:web:` identifier |

Returns the HTTPS URL for `/.well-known/did.json`.

```python
from openintent.federation import resolve_did_web

url = resolve_did_web("did:web:api.example.com")
# "https://api.example.com/.well-known/did.json"
```

### validate_ssrf

`validate_ssrf(url) -> bool` — validate a URL against SSRF protection rules.

| Parameter | Type | Description |
|-----------|------|-------------|
| `url` | `str` | The URL to validate |

Returns `True` if the URL is safe. Blocks:

- Non-HTTP(S) schemes
- `localhost`, `127.0.0.1`, `0.0.0.0`, `::1`
- Private IP ranges (`10.*`, `172.*`, `192.168.*`)
- Cloud metadata endpoints (`169.254.169.254`, `metadata.google.internal`)
- `.internal` and `.local` domains

```python
from openintent.federation import validate_ssrf

assert validate_ssrf("https://partner.example.com")
assert not validate_ssrf("http://localhost:8000")
assert not validate_ssrf("http://169.254.169.254/metadata")
```

## Model Classes

### Enums

#### AgentVisibility

Controls whether an agent is discoverable by federated peers.

| Value | Description |
|-------|-------------|
| `PUBLIC` | Visible to all peers |
| `UNLISTED` | Visible only to known peers |
| `PRIVATE` | Not visible to any peer |

#### PeerRelationship

Describes the relationship between two federated servers.

| Value | Description |
|-------|-------------|
| `PEER` | Equal bidirectional relationship |
| `UPSTREAM` | The peer is an authority / delegator |
| `DOWNSTREAM` | The peer is a delegate / worker |

#### TrustPolicy

Determines how incoming federation requests are validated.

| Value | Description |
|-------|-------------|
| `OPEN` | Accept from any server |
| `ALLOWLIST` | Accept only from explicitly listed peers |
| `TRUSTLESS` | Reject all federation requests |

#### CallbackEventType

Types of events sent via federation callbacks.

| Value | Description |
|-------|-------------|
| `STATE_DELTA` | Partial state update |
| `STATUS_CHANGED` | Intent status changed |
| `ATTESTATION` | Governance attestation |
| `BUDGET_WARNING` | Budget threshold reached |
| `COMPLETED` | Work completed |
| `FAILED` | Work failed |

#### DispatchStatus

Status of a dispatched federation request.

| Value | Description |
|-------|-------------|
| `ACCEPTED` | Dispatch accepted by target |
| `REJECTED` | Dispatch rejected by target |
| `PENDING` | Dispatch in progress |

### DelegationScope

`DelegationScope(permissions=, denied_operations=, max_delegation_depth=, expires_at=)` — defines what operations a remote server is allowed to perform.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `permissions` | `list[str]` | `["state.patch", "events.log"]` | Allowed operations |
| `denied_operations` | `list[str]` | `[]` | Explicitly denied operations |
| `max_delegation_depth` | `int` | `1` | How many times this scope can be re-delegated |
| `expires_at` | `str \| None` | `None` | ISO 8601 expiration timestamp |

#### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `to_dict()` | `dict` | Serialize to dict |
| `DelegationScope.from_dict(data)` | `DelegationScope` | Deserialize from dict |
| `attenuate(child_scope)` | `DelegationScope` | Create a reduced scope (intersection of permissions, union of denials, decremented depth) |

```python
from openintent.federation import DelegationScope

parent = DelegationScope(
    permissions=["state.patch", "events.log", "cost.report"],
    max_delegation_depth=2,
)

child = DelegationScope(
    permissions=["state.patch", "events.log"],
    max_delegation_depth=1,
)

attenuated = parent.attenuate(child)
assert "cost.report" not in attenuated.permissions
assert attenuated.max_delegation_depth == 1
```

### FederationPolicy

`FederationPolicy(governance=, budget=, observability=)` — policy constraints propagated across federation boundaries.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `governance` | `dict` | `{}` | Governance constraints (e.g., `require_approval`, `allowed_agents`) |
| `budget` | `dict` | `{}` | Budget constraints (e.g., `max_llm_tokens`, `cost_ceiling_usd`) |
| `observability` | `dict` | `{}` | Observability requirements (e.g., `trace_required`, `log_level`) |

#### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `to_dict()` | `dict` | Serialize to dict |
| `FederationPolicy.from_dict(data)` | `FederationPolicy` | Deserialize from dict |
| `compose_strictest(other)` | `FederationPolicy` | Merge two policies taking the strictest constraint for each key |

```python
from openintent.federation import FederationPolicy

local = FederationPolicy(
    budget={"max_llm_tokens": 10000, "cost_ceiling_usd": 5.0},
    governance={"require_approval": False},
)

remote = FederationPolicy(
    budget={"max_llm_tokens": 5000, "cost_ceiling_usd": 10.0},
    governance={"require_approval": True},
)

merged = local.compose_strictest(remote)
assert merged.budget["max_llm_tokens"] == 5000
assert merged.governance["require_approval"] is True
```

### FederationEnvelope

`FederationEnvelope(dispatch_id, source_server, target_server, intent_id, intent_title, ...)` — the wire format for dispatching an intent to a remote server.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `dispatch_id` | `str` | required | Unique dispatch identifier |
| `source_server` | `str` | required | URL of the originating server |
| `target_server` | `str` | required | URL of the destination server |
| `intent_id` | `str` | required | ID of the intent being dispatched |
| `intent_title` | `str` | required | Title of the intent |
| `intent_description` | `str` | `""` | Description of the intent |
| `intent_state` | `dict` | `{}` | Current intent state |
| `intent_constraints` | `dict` | `{}` | Intent constraints |
| `agent_id` | `str \| None` | `None` | Target agent ID on the remote server |
| `delegation_scope` | `DelegationScope \| None` | `None` | Permissions granted to the remote server |
| `federation_policy` | `FederationPolicy \| None` | `None` | Policy constraints for remote execution |
| `trace_context` | `dict[str, str] \| None` | `None` | Distributed tracing context (RFC-0020) |
| `callback_url` | `str \| None` | `None` | URL for status callbacks |
| `idempotency_key` | `str \| None` | `None` | Idempotency key to prevent duplicate processing |
| `created_at` | `str \| None` | `None` | ISO 8601 creation timestamp |
| `signature` | `str \| None` | `None` | Cryptographic signature (RFC-0023) |

#### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `to_dict()` | `dict` | Serialize to dict (omits `None` fields) |
| `FederationEnvelope.from_dict(data)` | `FederationEnvelope` | Deserialize from dict |

### FederationCallback

`FederationCallback(dispatch_id, event_type, state_delta=, attestation=, trace_id=, idempotency_key=, timestamp=)` — callback message sent from a remote server back to the originator.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `dispatch_id` | `str` | required | The original dispatch ID |
| `event_type` | `CallbackEventType` | required | Type of callback event |
| `state_delta` | `dict` | `{}` | Partial state update |
| `attestation` | `FederationAttestation \| None` | `None` | Governance attestation |
| `trace_id` | `str \| None` | `None` | Distributed trace ID |
| `idempotency_key` | `str \| None` | `None` | Idempotency key |
| `timestamp` | `str \| None` | `None` | ISO 8601 timestamp |

#### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `to_dict()` | `dict` | Serialize to dict |
| `FederationCallback.from_dict(data)` | `FederationCallback` | Deserialize from dict |

### FederationAttestation

`FederationAttestation(dispatch_id, governance_compliant=, usage=, trace_references=, timestamp=, signature=)` — proof that remote work was executed within policy constraints.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `dispatch_id` | `str` | required | The dispatch this attests to |
| `governance_compliant` | `bool` | `True` | Whether governance policies were followed |
| `usage` | `dict` | `{}` | Resource usage (e.g., `{"llm_tokens": 500, "cost_usd": 0.02}`) |
| `trace_references` | `list[str]` | `[]` | Related trace/span IDs |
| `timestamp` | `str \| None` | `None` | ISO 8601 timestamp |
| `signature` | `str \| None` | `None` | Cryptographic signature |

#### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `to_dict()` | `dict` | Serialize to dict |
| `FederationAttestation.from_dict(data)` | `FederationAttestation` | Deserialize from dict |

### PeerInfo

`PeerInfo(server_url, server_did=, relationship=, trust_policy=, public_key=)` — metadata about a known federation peer.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `server_url` | `str` | required | Peer's base URL |
| `server_did` | `str \| None` | `None` | Peer's DID identifier |
| `relationship` | `PeerRelationship` | `PEER` | Relationship type |
| `trust_policy` | `TrustPolicy` | `ALLOWLIST` | Trust policy for this peer |
| `public_key` | `str \| None` | `None` | Peer's public key (base64) |

#### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `to_dict()` | `dict` | Serialize to dict |
| `PeerInfo.from_dict(data)` | `PeerInfo` | Deserialize from dict |

### FederationManifest

`FederationManifest(server_did, server_url, ...)` — the discovery document served at `/.well-known/openintent-federation.json`.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `server_did` | `str` | required | Server's DID identifier |
| `server_url` | `str` | required | Server's base URL |
| `protocol_version` | `str` | `"0.1"` | Federation protocol version |
| `trust_policy` | `TrustPolicy` | `ALLOWLIST` | Server's default trust policy |
| `visibility_default` | `AgentVisibility` | `PUBLIC` | Default agent visibility |
| `supported_rfcs` | `list[str]` | `["RFC-0022", "RFC-0023"]` | Supported RFC list |
| `peers` | `list[str]` | `[]` | Known peer server URLs |
| `public_key` | `str \| None` | `None` | Server's public key (base64) |
| `endpoints` | `dict[str, str]` | see below | Federation endpoint paths |

Default endpoints:

```python
{
    "status": "/api/v1/federation/status",
    "agents": "/api/v1/federation/agents",
    "dispatch": "/api/v1/federation/dispatch",
    "receive": "/api/v1/federation/receive",
}
```

#### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `to_dict()` | `dict` | Serialize to dict |
| `FederationManifest.from_dict(data)` | `FederationManifest` | Deserialize from dict |

### FederationStatus

`FederationStatus(enabled=, server_did=, trust_policy=, peer_count=, active_dispatches=, total_dispatches=, total_received=)` — runtime status of the federation subsystem.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | `bool` | `True` | Whether federation is active |
| `server_did` | `str \| None` | `None` | This server's DID |
| `trust_policy` | `TrustPolicy` | `ALLOWLIST` | Active trust policy |
| `peer_count` | `int` | `0` | Number of known peers |
| `active_dispatches` | `int` | `0` | Currently active outbound dispatches |
| `total_dispatches` | `int` | `0` | Total dispatches sent |
| `total_received` | `int` | `0` | Total dispatches received |

#### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `to_dict()` | `dict` | Serialize to dict |
| `FederationStatus.from_dict(data)` | `FederationStatus` | Deserialize from dict |

### DispatchResult

`DispatchResult(dispatch_id, status, target_server, message=, remote_intent_id=)` — result of a federation dispatch request.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `dispatch_id` | `str` | required | Dispatch identifier |
| `status` | `DispatchStatus` | required | Result status |
| `target_server` | `str` | required | Target server URL |
| `message` | `str` | `""` | Human-readable message |
| `remote_intent_id` | `str \| None` | `None` | Intent ID on the remote server |

#### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `to_dict()` | `dict` | Serialize to dict |
| `DispatchResult.from_dict(data)` | `DispatchResult` | Deserialize from dict |

### ReceiveResult

`ReceiveResult(dispatch_id, accepted, local_intent_id=, message=)` — result of receiving a federated intent.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `dispatch_id` | `str` | required | The original dispatch ID |
| `accepted` | `bool` | required | Whether the intent was accepted |
| `local_intent_id` | `str \| None` | `None` | Locally created intent ID |
| `message` | `str` | `""` | Human-readable message |

#### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `to_dict()` | `dict` | Serialize to dict |
| `ReceiveResult.from_dict(data)` | `ReceiveResult` | Deserialize from dict |

### FederatedAgent

`FederatedAgent(agent_id, server_url, capabilities=, visibility=, server_did=, status=)` — an agent visible via federation discovery.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `agent_id` | `str` | required | Agent identifier |
| `server_url` | `str` | required | Server hosting the agent |
| `capabilities` | `list[str]` | `[]` | Agent capabilities |
| `visibility` | `AgentVisibility` | `PUBLIC` | Visibility level |
| `server_did` | `str \| None` | `None` | DID of the hosting server |
| `status` | `str` | `"active"` | Agent status |

#### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `to_dict()` | `dict` | Serialize to dict |
| `FederatedAgent.from_dict(data)` | `FederatedAgent` | Deserialize from dict |

## Client Methods

Both `OpenIntentClient` (sync) and `AsyncOpenIntentClient` expose these federation methods:

### federation_status

`client.federation_status() -> FederationStatus` — get the federation status of the connected server.

### list_federated_agents

`client.list_federated_agents(source_server=) -> list[dict]` — list agents visible via federation. Pass `source_server` to include unlisted agents visible to that peer.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `source_server` | `str \| None` | `None` | Requesting server URL (sent as `X-Source-Server` header) |

### federation_dispatch

`client.federation_dispatch(intent_id, target_server, ...) -> DispatchResult` — dispatch an intent to a remote server.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `intent_id` | `str` | required | Intent to dispatch |
| `target_server` | `str` | required | Target server URL |
| `agent_id` | `str \| None` | `None` | Target agent on remote server |
| `delegation_scope` | `dict \| None` | `None` | Delegation scope dict |
| `federation_policy` | `dict \| None` | `None` | Policy constraints dict |
| `callback_url` | `str \| None` | `None` | Callback URL for status updates |
| `trace_context` | `dict[str, str] \| None` | `None` | Distributed tracing context |

### federation_receive

`client.federation_receive(dispatch_id, source_server, intent_id, intent_title, ...) -> ReceiveResult` — receive a federated intent from a remote server.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `dispatch_id` | `str` | required | Dispatch identifier |
| `source_server` | `str` | required | Source server URL |
| `intent_id` | `str` | required | Original intent ID |
| `intent_title` | `str` | required | Intent title |
| `intent_description` | `str` | `""` | Intent description |
| `intent_state` | `dict \| None` | `None` | Intent state |
| `agent_id` | `str \| None` | `None` | Target agent ID |
| `delegation_scope` | `dict \| None` | `None` | Delegation scope dict |
| `federation_policy` | `dict \| None` | `None` | Policy constraints dict |
| `callback_url` | `str \| None` | `None` | Callback URL |
| `idempotency_key` | `str \| None` | `None` | Idempotency key |

### send_federation_callback

`client.send_federation_callback(callback_url, dispatch_id, event_type, ...) -> dict` — send a callback to the originating server.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `callback_url` | `str` | required | Callback endpoint URL |
| `dispatch_id` | `str` | required | Original dispatch ID |
| `event_type` | `str` | required | Callback event type |
| `state_delta` | `dict \| None` | `None` | Partial state update |
| `attestation` | `dict \| None` | `None` | Governance attestation dict |
| `trace_id` | `str \| None` | `None` | Trace ID |

### federation_discover

`client.federation_discover() -> dict` — fetch the federation discovery document from `/.well-known/openintent-federation.json`.

## Server Endpoints

The federation router (registered via `@Federation` or `create_federation_router()`) exposes:

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/.well-known/openintent-federation.json` | Federation discovery manifest |
| `GET` | `/.well-known/did.json` | W3C DID Document for server identity |
| `GET` | `/api/v1/federation/status` | Federation runtime status |
| `GET` | `/api/v1/federation/agents` | List federally visible agents |
| `POST` | `/api/v1/federation/dispatch` | Dispatch an intent to a remote server |
| `POST` | `/api/v1/federation/receive` | Receive a dispatched intent from a remote server |

### Server Internal Classes

#### FederationState

Internal state manager for federation. Created as a module-level singleton `_federation_state`.

| Method | Description |
|--------|-------------|
| `register_agent(agent_id, capabilities=, visibility=, server_url=)` | Register an agent for federation discovery |
| `get_visible_agents(requesting_server=)` | Get agents visible to a requesting server |

#### configure_federation

`configure_federation(server_url, server_did=, trust_policy=, visibility_default=, peers=, identity=) -> FederationState` — initialize federation state with identity and trust configuration.

#### create_federation_router

`create_federation_router(validate_api_key=) -> APIRouter` — create the FastAPI router with all federation endpoints.
