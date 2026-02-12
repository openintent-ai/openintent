# RFC-0018: Cryptographic Agent Identity

**Status:** Proposed  
**Created:** 2026-02-12  
**Authors:** OpenIntent Contributors  
**Depends on:** RFC-0001 (Intent Objects), RFC-0003 (Agent Leasing), RFC-0011 (Access Control), RFC-0014 (Credential Vaults & Tool Scoping), RFC-0016 (Agent Lifecycle & Health)

---

## Abstract

This RFC introduces cryptographic identity as a protocol primitive. Agents generate Ed25519 key pairs, register their public keys with the protocol, and sign all protocol events they author. Identity is self-sovereign: an agent proves who it is by demonstrating control of a private key, not by presenting a shared secret issued by a central authority. Each public key derives a Decentralized Identifier (DID) using the `did:key` method, giving agents a portable, globally unique identity that is meaningful across servers, deployments, and ecosystems.

## Motivation

The protocol currently authenticates agents using API keys — shared secrets passed in request headers. This model has served single-server deployments well, but it creates five critical gaps as the protocol scales toward multi-server, multi-party, and decentralized operation:

1. **API keys are shared secrets.** Both the agent and the server know the key. If the key is compromised, there is no cryptographic evidence of which party leaked it. The attacker can fully impersonate the agent — creating intents, emitting events, claiming leases — and neither the agent nor the server can prove they were not the author. Shared secrets provide authentication but not accountability.

2. **No event authorship verification.** Any holder of an API key can forge events claiming to be any agent associated with that key. There is no mechanism for a third party — another agent, a coordinator, an auditor — to independently verify that a specific agent authored a specific event. The event log (RFC-0001) records what happened, but not provably *who* did it.

3. **No portable identity.** Agent IDs are server-local strings. `agent_billing_01` on server A has no relationship to `agent_billing_01` on server B. An agent cannot prove to a new server that it is the same entity that operated on a previous server. Identity is trapped within a single deployment.

4. **No trust without a central server.** Two agents cannot verify each other's identity peer-to-peer. All trust flows through the server that issued the API keys. In a federated or mesh topology (RFC-0020), agents need to establish trust directly — which requires identity that does not depend on a shared authority.

5. **No bridge to external identity systems.** Agents cannot link their protocol identity to external identity providers, registries, or verification systems. There is no protocol-level mechanism for an agent to prove its OpenIntent identity to an outside system, or to import a verified external identity into the protocol.

## Terminology

| Term | Definition |
|------|-----------|
| **Key Pair** | An Ed25519 public/private key pair owned by an agent. The private key is held exclusively by the agent; the public key is registered with the protocol. |
| **Agent DID** | A Decentralized Identifier derived from the agent's public key using the `did:key` method (e.g., `did:key:z6Mk...`). Globally unique, self-certifying, and portable across servers. |
| **Identity Proof** | A signed challenge proving an agent controls the private key for a registered public key. Used during key registration to prevent impersonation. |
| **Signed Event** | An intent event (RFC-0001) with a cryptographic signature in its `proof` field, verifiable by any party holding the agent's public key. |
| **Key Rotation** | The act of replacing an agent's active key pair while maintaining identity continuity through a signed transition record. The old key authorizes the new key. |

## Specification

### 1. Agent Identity Object

The agent record (RFC-0016) is extended with cryptographic identity fields. These fields are optional — agents without registered keys continue to authenticate via API keys. An agent MAY register a key at any time after initial registration.

```json
{
  "agent_id": "agent_billing_01",
  "public_key": "ed25519:yKHfKtE9w5aBSvMhi0yrQg8x3bWmHqYE8RSxU6zT7Wo",
  "did": "did:key:z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
  "key_algorithm": "Ed25519",
  "registered_at": "2026-02-12T10:00:00Z",
  "key_expires_at": null,
  "previous_keys": [],
  "metadata": {}
}
```

#### 1.1 Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `agent_id` | string | Yes | The agent's protocol-level identifier (RFC-0016). Identity fields extend this record. |
| `public_key` | string | Yes | The agent's active public key, prefixed with the algorithm name. Format: `ed25519:<base64url-encoded-32-bytes>`. |
| `did` | string | Yes | The agent's Decentralized Identifier, derived deterministically from the public key using the `did:key` method. Server-generated upon key registration. |
| `key_algorithm` | string | Yes | The cryptographic algorithm. This RFC specifies `Ed25519`. Future RFCs may add additional algorithms. |
| `registered_at` | string (ISO 8601) | Yes | Timestamp when the current key was registered. |
| `key_expires_at` | string (ISO 8601) or null | No | Optional expiry for the current key. After this time, signatures made with this key are rejected. `null` means no expiry. |
| `previous_keys` | string[] | No | Ordered list of previously active public keys, most recent first. Enables historical signature verification. |
| `metadata` | object | No | Implementation-specific data. The protocol does not inspect this field. |

### 2. Key Registration

Key registration uses a challenge-response protocol to prove the agent controls the private key corresponding to the public key being registered.

#### 2.1 Registration Flow

1. The agent generates an Ed25519 key pair locally. The private key never leaves the agent's runtime.
2. The agent sends a registration request with the public key.
3. The server generates a random 32-byte challenge and returns it.
4. The agent signs the challenge with its private key and returns the signature.
5. The server verifies the signature against the provided public key.
6. On success, the server stores the public key, derives the DID, and updates the agent record.

#### 2.2 Step 1: Registration Request

```
POST /api/v1/agents/{agent_id}/identity
Content-Type: application/json
X-API-Key: {api_key}

{
  "public_key": "ed25519:yKHfKtE9w5aBSvMhi0yrQg8x3bWmHqYE8RSxU6zT7Wo",
  "key_algorithm": "Ed25519",
  "key_expires_at": null
}
```

#### 2.3 Step 2: Challenge Response

```
200 OK
Content-Type: application/json

{
  "challenge": "base64url-encoded-32-random-bytes",
  "challenge_expires_at": "2026-02-12T10:05:00Z"
}
```

The challenge expires after a short window (default: 5 minutes) to prevent replay attacks.

#### 2.4 Step 3: Challenge Signature

```
POST /api/v1/agents/{agent_id}/identity/challenge
Content-Type: application/json
X-API-Key: {api_key}

{
  "challenge": "base64url-encoded-32-random-bytes",
  "signature": "base64url-encoded-64-byte-ed25519-signature"
}
```

#### 2.5 Step 4: Registration Confirmation

```
201 Created
Content-Type: application/json

{
  "agent_id": "agent_billing_01",
  "public_key": "ed25519:yKHfKtE9w5aBSvMhi0yrQg8x3bWmHqYE8RSxU6zT7Wo",
  "did": "did:key:z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
  "key_algorithm": "Ed25519",
  "registered_at": "2026-02-12T10:00:30Z",
  "key_expires_at": null,
  "previous_keys": []
}
```

#### 2.6 Registration Semantics

- An agent that already has a registered key MUST use the key rotation flow (Section 5) to change keys. A second registration request returns `409 Conflict`.
- The initial registration still requires API key authentication (`X-API-Key`). The cryptographic identity supplements — but does not replace — the API key for server authentication. The API key says "this request is authorized to access this server." The cryptographic key says "this event was authored by this specific agent."
- The server MUST verify the challenge signature before storing the key. A failed verification returns `403 Forbidden`.

### 3. Signed Events

The Event Object (RFC-0001) gains an optional `proof` field containing the agent's cryptographic signature over the event content.

#### 3.1 Signed Event Object

```json
{
  "id": "evt_01HXYZ",
  "intent_id": "intent_01HABC",
  "event_type": "state_change",
  "actor": "agent_billing_01",
  "payload": {
    "op": "set",
    "path": "/status",
    "value": "completed"
  },
  "created_at": "2026-02-12T10:15:00Z",
  "proof": {
    "type": "Ed25519Signature2026",
    "created": "2026-02-12T10:15:00Z",
    "verification_method": "did:key:z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
    "signature": "base64url-encoded-64-byte-ed25519-signature"
  }
}
```

#### 3.2 Signature Construction

The signed content is the canonical JSON serialization of the event **without** the `proof` field:

1. Construct the event object with all fields except `proof`.
2. Serialize to canonical JSON (keys sorted alphabetically, no whitespace, UTF-8 encoding).
3. Sign the resulting byte string with the agent's Ed25519 private key.
4. Attach the signature in the `proof` field.

Canonical JSON ensures that any party can reconstruct the exact byte string that was signed, regardless of JSON parser implementation.

#### 3.3 Signature Verification

Any party holding the agent's public key can verify a signed event:

1. Remove the `proof` field from the event.
2. Serialize the remaining fields to canonical JSON (same rules as construction).
3. Verify the `proof.signature` against the canonical JSON bytes using the public key identified by `proof.verification_method`.

The `verification_method` is the agent's DID. The verifier resolves the DID to a public key (for `did:key`, the key is embedded in the DID itself) and performs Ed25519 signature verification.

#### 3.4 Backward Compatibility

- Events without a `proof` field remain valid. The `proof` field is optional.
- Servers MAY enforce a signature policy requiring all events from agents with registered keys to include a valid `proof`. This policy is configured per-deployment, not mandated by the protocol.
- Events with an invalid `proof` (signature does not verify) MUST be rejected with `403 Forbidden`.
- A server that does not implement RFC-0018 ignores the `proof` field. Signed events are valid RFC-0001 events.

### 4. Identity Verification Endpoints

#### 4.1 Retrieve Agent Identity

```
GET /api/v1/agents/{agent_id}/identity
```

Response:

```json
{
  "agent_id": "agent_billing_01",
  "public_key": "ed25519:yKHfKtE9w5aBSvMhi0yrQg8x3bWmHqYE8RSxU6zT7Wo",
  "did": "did:key:z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
  "key_algorithm": "Ed25519",
  "registered_at": "2026-02-12T10:00:30Z",
  "key_expires_at": null,
  "previous_keys": []
}
```

If the agent has no registered key, the server returns `404 Not Found`.

#### 4.2 Verify a Signed Payload

```
POST /api/v1/agents/{agent_id}/identity/verify
Content-Type: application/json

{
  "payload": { ... },
  "signature": "base64url-encoded-64-byte-ed25519-signature"
}
```

Response:

```json
{
  "valid": true,
  "agent_id": "agent_billing_01",
  "did": "did:key:z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
  "verified_at": "2026-02-12T10:20:00Z"
}
```

This endpoint enables any party to verify a signature without holding the agent's public key locally. The server acts as a resolver, not an authority — the cryptographic verification is deterministic and could be performed offline by any party with the public key.

### 5. Key Rotation

Key rotation replaces an agent's active key pair while maintaining identity continuity. The old key authorizes the transition to the new key, creating a verifiable chain of custody.

#### 5.1 Rotation Request

The agent signs a rotation record with the **old** key:

```
POST /api/v1/agents/{agent_id}/identity/rotate
Content-Type: application/json
X-API-Key: {api_key}

{
  "action": "rotate",
  "new_public_key": "ed25519:newKeyBase64urlEncoded32Bytes",
  "old_public_key": "ed25519:yKHfKtE9w5aBSvMhi0yrQg8x3bWmHqYE8RSxU6zT7Wo",
  "signature": "base64url-encoded-64-byte-signature-by-old-key"
}
```

The signed content is the canonical JSON of `{ "action": "rotate", "new_public_key": "...", "old_public_key": "..." }` — the `signature` field is excluded from the signed payload.

#### 5.2 Rotation Semantics

1. The server verifies the signature against the currently registered (old) public key.
2. On success, the server replaces the active key with `new_public_key`.
3. The old key is prepended to `previous_keys`.
4. A new DID is derived from the new public key.
5. `registered_at` is updated to the rotation timestamp.
6. An `agent.identity.rotated` event is emitted to the system event log.
7. All subsequent events from this agent MUST be signed with the new key.
8. Signatures made with previous keys remain verifiable for historical events — the `previous_keys` list enables auditors to verify old signatures.

#### 5.3 Rotation Response

```
200 OK
Content-Type: application/json

{
  "agent_id": "agent_billing_01",
  "public_key": "ed25519:newKeyBase64urlEncoded32Bytes",
  "did": "did:key:z6MkNewDIDDerivedFromNewKey",
  "key_algorithm": "Ed25519",
  "registered_at": "2026-02-12T11:00:00Z",
  "key_expires_at": null,
  "previous_keys": [
    "ed25519:yKHfKtE9w5aBSvMhi0yrQg8x3bWmHqYE8RSxU6zT7Wo"
  ]
}
```

### 6. Agent Discovery by Public Key

The agent registry (RFC-0016) is extended with query parameters for cryptographic identity lookup.

#### 6.1 Discovery by Public Key

```
GET /api/v1/agents?public_key=ed25519:yKHfKtE9w5aBSvMhi0yrQg8x3bWmHqYE8RSxU6zT7Wo
```

#### 6.2 Discovery by DID

```
GET /api/v1/agents?did=did:key:z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK
```

Response (same format as RFC-0016 registry listing, with identity fields included):

```json
{
  "agents": [
    {
      "agent_id": "agent_billing_01",
      "public_key": "ed25519:yKHfKtE9w5aBSvMhi0yrQg8x3bWmHqYE8RSxU6zT7Wo",
      "did": "did:key:z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
      "status": "active",
      "capabilities": ["billing", "invoicing"],
      "last_heartbeat_at": "2026-02-12T10:29:45Z"
    }
  ],
  "total": 1
}
```

These queries enable cross-server agent lookup: given a DID from a signed event, any party can discover which server hosts the agent and retrieve its full record. This is foundational for federation (RFC-0020).

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/agents/{agent_id}/identity` | Register a public key (initiates challenge-response) |
| `POST` | `/api/v1/agents/{agent_id}/identity/challenge` | Submit signed challenge to complete registration |
| `GET` | `/api/v1/agents/{agent_id}/identity` | Retrieve agent's public key, DID, and identity metadata |
| `POST` | `/api/v1/agents/{agent_id}/identity/verify` | Verify a signed payload against the agent's registered key |
| `POST` | `/api/v1/agents/{agent_id}/identity/rotate` | Rotate the agent's key pair (signed by old key) |
| `GET` | `/api/v1/agents?public_key={key}` | Discover agent by public key |
| `GET` | `/api/v1/agents?did={did}` | Discover agent by DID |

## SDK Usage

```python
from openintent import OpenIntentClient

client = OpenIntentClient(base_url="https://openintent.example.com", api_key="...")

# Register cryptographic identity
identity = client.agents.register_identity(
    agent_id="agent-research",
    key_algorithm="Ed25519",
)
# identity.public_key  → "ed25519:yKHfKtE9w5..."
# identity.did         → "did:key:z6Mk..."
# identity.private_key → Ed25519 private key (local only, never sent to server)

# Sign and emit an event
client.emit_event(
    intent_id="intent_01HABC",
    event_type="state_change",
    payload={"op": "set", "path": "/status", "value": "completed"},
    sign=True,  # automatically signs with registered key
)

# Verify a signed event
verified = client.verify_event(event)
# verified.valid           → True
# verified.signer_did      → "did:key:z6Mk..."
# verified.signer_agent_id → "agent-research"

# Key rotation
new_identity = client.agents.rotate_key(agent_id="agent-research")
# new_identity.public_key → new key
# new_identity.did        → new DID
# Previous key archived in new_identity.previous_keys
```

## Security Considerations

1. **Private key custody.** Private keys MUST never leave the agent's runtime. The server stores only public keys. The SDK generates keys locally and never transmits private key material. Implementations SHOULD use secure memory for private key storage and zeroize key material when no longer needed.

2. **Non-repudiation.** Signed events provide non-repudiation: an agent cannot deny authoring an event it signed. This is a stronger guarantee than API key authentication, where any party with the key could have authored the event.

3. **Key compromise and rotation.** Key rotation requires signing with the old key — a compromised key can still be used to rotate to an attacker-controlled key. Operators SHOULD monitor for unexpected rotations. The protocol provides an admin API for force-revoking a key without the old key's signature, for use when compromise is detected. Force revocation invalidates the current key and requires a new registration with challenge-response.

4. **Challenge-response replay prevention.** Challenges are single-use and time-bounded (default: 5-minute expiry). A challenge that has been used or has expired MUST be rejected. Challenges SHOULD contain sufficient entropy (32 bytes) to prevent collision.

5. **Canonical JSON determinism.** Signature verification depends on both parties producing identical canonical JSON. Implementations MUST use the same canonicalization rules (sorted keys, no whitespace, UTF-8). The protocol specifies RFC 8785 (JCS — JSON Canonicalization Scheme) as the canonicalization standard.

## Relationship to Other RFCs

| RFC | Relationship |
|-----|-------------|
| **RFC-0001** (Intent Objects) | Extends the Event Object with the optional `proof` field for signed events. |
| **RFC-0003** (Agent Leasing) | Lease acquisition can require signed requests. A server policy can mandate that lease claims include a valid signature, preventing impersonation in task assignment. |
| **RFC-0011** (Access Control) | Access control policies can require signed identity. A policy rule like `require: signed_identity` ensures that only agents with registered keys can perform certain operations. |
| **RFC-0014** (Credential Vaults) | Tool grants can reference a DID instead of an `agent_id`, enabling cross-server grant portability. An agent moving between servers retains its grants if they are DID-addressed. |
| **RFC-0016** (Agent Lifecycle) | Extends the Agent Record with identity fields (`public_key`, `did`, `previous_keys`). Identity registration produces an `agent.identity.registered` lifecycle event. |
| **RFC-0019** (Verifiable Event Logs) | Signed events feed into verifiable event logs. An event log where every event is signed becomes a tamper-evident, attributable audit trail. |
| **RFC-0020** (Federation) | DIDs enable cross-server agent identity. When servers federate, agents are identified by DID rather than server-local `agent_id`, enabling seamless cross-server coordination. |

## Non-Goals

- **This RFC does not define a PKI or certificate authority hierarchy.** Identity is self-sovereign. Agents generate their own keys. There is no certificate chain, no root of trust, and no central key authority. Trust relationships are built through protocol mechanisms (grants, reputation) rather than hierarchical certification.

- **This RFC does not require integration with any external identity system.** The protocol functions fully as a standalone coordination layer. Agents have complete cryptographic identity within the OpenIntent ecosystem without depending on any external registry or identity provider.

- **This RFC does not define agent reputation or trust scoring.** Cryptographic identity proves *who* an agent is, not *how trustworthy* it is. Reputation, trust scoring, and behavioral analysis are the domain of a future RFC that builds on the identity foundation defined here.

- **This RFC does not specify key storage mechanisms.** Whether an agent stores its private key in an HSM, a TPM, a secure enclave, an environment variable, or a file on disk is an implementation concern. The protocol defines the interface (public key registration, challenge-response, signed events) but not the storage backend.

- **This RFC does not define multi-signature or threshold schemes.** An event is signed by a single agent key. Multi-party authorization (e.g., requiring two agents to co-sign) is a coordination-level concern addressed by governance policies (RFC-0013), not by the identity layer.
