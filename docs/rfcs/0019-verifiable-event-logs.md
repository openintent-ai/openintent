# RFC-0019: Verifiable Event Logs

**Status:** Proposed  
**Created:** 2026-02-12  
**Authors:** OpenIntent Contributors  
**Depends on:** RFC-0001 (Intent Objects), RFC-0018 (Cryptographic Agent Identity)

---

## Abstract

This RFC defines a hash-chained, Merkle-tree-backed event log that transforms OpenIntent's append-only event history into a cryptographically verifiable audit trail. Any participant — agent, coordinator, auditor, or external verifier — can independently prove that an event occurred, that the log has not been tampered with, and that the ordering is authentic. When combined with RFC-0018 signed events, this produces a complete chain of custody: who did what, when, in what order, with cryptographic proof. Optionally, Merkle roots can be anchored to an external timestamping service for public, immutable timestamping — bridging to external verification systems for cross-ecosystem trust.

## Motivation

The protocol's event log (RFC-0001) is append-only by convention, but append-only is not tamper-evident. The server is trusted to faithfully record and preserve events. As the protocol scales toward multi-party coordination, federation, and external attestation, this trust assumption creates four critical gaps:

1. **Append-only is not tamper-evident.** The server could rewrite, reorder, or delete events and no client would know. An append-only API is a policy, not a guarantee. Without cryptographic binding between events, the server can silently mutate history — changing an agent's reported actions, altering timestamps, or removing inconvenient records — and no client can detect the change.

2. **No proof of inclusion.** An agent cannot prove to a third party that a specific event exists in the log without that third party trusting the server. If agent A claims it submitted a result, agent B must ask the server to confirm — and trust the server's answer. There is no mechanism for A to produce a compact, self-contained proof that B can verify independently.

3. **No cross-server audit.** When federation (RFC-0020) enables cross-server coordination, a server receives events from remote servers. There is no way to verify that a remote server's event log is authentic, complete, and correctly ordered. Federation without verifiability is federation without trust.

4. **No bridge to external verification.** The protocol has no mechanism to produce cryptographic proofs that external verification systems can consume. The event log is invisible to systems outside the OpenIntent deployment.

## Terminology

| Term | Definition |
|------|-----------|
| **Event Hash** | SHA-256 hash of an event's canonical content, serving as a unique fingerprint. |
| **Hash Chain** | A sequence where each event's hash includes the previous event's hash, forming a tamper-evident linked list. |
| **Merkle Tree** | A binary hash tree built over a batch of event hashes, producing a single root hash that summarizes the entire batch. |
| **Merkle Root** | The single hash at the top of a Merkle tree — changes if any event in the batch is modified. |
| **Merkle Proof** | A minimal set of sibling hashes that proves a specific event is included in a Merkle tree without revealing the entire tree. |
| **Log Checkpoint** | A signed record containing a Merkle root, a sequence number, a timestamp, and optionally an external timestamp anchor. |
| **Anchor** | A record in an external timestamping service (append-only ledger, notary, or similar) that pins a Merkle root for public immutability (optional). |

## Specification

### 1. Event Hashing

Each event is hashed using SHA-256 over its canonical JSON representation (sorted keys, no whitespace, UTF-8 encoding). The hash is stored as a new field `event_hash` on the Event Object (RFC-0001). If the event has a `proof` field (RFC-0018), the signature is included in the hash — this binds authorship to the chain.

#### 1.1 Extended Event Object

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
  },
  "event_hash": "sha256:7d2Kp9Lm3nQrStUvWxYz1a2B3c4D5e6F7g8H9iJkLmN",
  "previous_event_hash": "sha256:Xk9Lp2Mn3oQr4StUv5WxYz6a7B8c9D0eF1g2H3iJkLm",
  "sequence": 42
}
```

#### 1.2 Field Semantics

| Field | Type | Description |
|-------|------|-------------|
| `event_hash` | string | SHA-256 of the canonical JSON of all fields except `event_hash` itself. Format: `sha256:<base64url-encoded>`. |
| `previous_event_hash` | string or null | The `event_hash` of the preceding event in this intent's log. `null` for the first event in an intent. |
| `sequence` | integer | Monotonically increasing integer within the intent's event log. Starts at 1. |

#### 1.3 Hash Construction

1. Construct the event object with all fields **except** `event_hash`.
2. Include `previous_event_hash` and `sequence` in the object (these are inputs to the hash, not outputs).
3. If the event has a `proof` field (RFC-0018), include it — this binds the author's signature into the chain.
4. Serialize to canonical JSON (keys sorted alphabetically, no whitespace, UTF-8 encoding).
5. Compute SHA-256 over the resulting byte string.
6. Encode as `sha256:<base64url>` and store in `event_hash`.

#### 1.4 Backward Compatibility

Events without `event_hash`, `previous_event_hash`, and `sequence` remain valid RFC-0001 events. These fields are optional additions. A server that does not implement RFC-0019 ignores them. A server that does implement RFC-0019 MUST populate these fields on all new events.

### 2. Hash Chain

Events for each intent form a hash chain: event N's hash covers event N-1's hash via the `previous_event_hash` field. This makes insertion, deletion, or reordering detectable by any client that remembers the last hash it observed.

#### 2.1 Chain Structure

```
Event 1              Event 2              Event 3
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ content      │     │ content      │     │ content      │
│ prev: null   │──>  │ prev: hash_1 │──>  │ prev: hash_2 │
│ seq: 1       │     │ seq: 2       │     │ seq: 3       │
│ hash_1 = H(.)│     │ hash_2 = H(.)│     │ hash_3 = H(.)│
└──────────────┘     └──────────────┘     └──────────────┘
```

Each hash covers the event's content **and** the previous event's hash. Modifying any event invalidates its hash — and the hash of every subsequent event. This is the fundamental tamper-evidence property.

#### 2.2 Client-Side Verification

A client that remembers the `event_hash` and `sequence` of the last event it observed can verify continuity:

1. Fetch events starting from the remembered sequence.
2. Verify that the first returned event's `previous_event_hash` matches the remembered hash.
3. For each subsequent event, verify that `previous_event_hash` matches the preceding event's `event_hash`.
4. For each event, recompute the hash from the event content and verify it matches `event_hash`.

If any check fails, the chain has been tampered with. The client SHOULD reject the log and alert the operator.

### 3. Merkle Tree & Checkpoints

The server periodically builds a Merkle tree over recent event hashes. The tree produces a single Merkle root that summarizes an entire batch of events. This root is stored in a Log Checkpoint — a signed, timestamped record that acts as a commitment to the log's state at a point in time.

#### 3.1 Checkpoint Frequency

Checkpoints are created based on configurable triggers:

- **Event count:** Every N events (default: 100).
- **Time interval:** Every T minutes (default: 5).
- **On demand:** An administrator can trigger a checkpoint at any time.

Whichever trigger fires first wins. A checkpoint is never created for an empty batch.

#### 3.2 Log Checkpoint Object

```json
{
  "checkpoint_id": "chk_01HXYZ",
  "intent_id": "intent_01HABC",
  "scope": "intent",
  "merkle_root": "sha256:Rt7Kp9Lm3nQrStUvWxYz1a2B3c4D5e6F7g8H9iJkLmN",
  "event_count": 100,
  "first_sequence": 1,
  "last_sequence": 100,
  "created_at": "2026-02-12T11:00:00Z",
  "signed_by": "did:key:z6MkServerIdentityKey",
  "signature": "base64url-encoded-64-byte-ed25519-signature",
  "anchor": null
}
```

#### 3.3 Checkpoint Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `checkpoint_id` | string | Yes | Unique identifier for the checkpoint. |
| `intent_id` | string or null | Yes | The intent this checkpoint covers. `null` for server-scoped checkpoints. |
| `scope` | string | Yes | `"intent"` for a single intent's events; `"server"` for all events across the server. |
| `merkle_root` | string | Yes | SHA-256 root of the Merkle tree built over the batch's event hashes. |
| `event_count` | integer | Yes | Number of events in this checkpoint's batch. |
| `first_sequence` | integer | Yes | Sequence number of the first event in the batch. |
| `last_sequence` | integer | Yes | Sequence number of the last event in the batch. |
| `created_at` | string (ISO 8601) | Yes | When the checkpoint was created. |
| `signed_by` | string | Yes | DID of the server's signing key (servers have identity per RFC-0018). |
| `signature` | string | Yes | Ed25519 signature over the canonical JSON of all fields except `signature`. |
| `anchor` | object or null | No | External timestamp anchor, if the Merkle root has been published to an external timestamping service (Section 5). |

#### 3.4 Merkle Tree Construction

1. Collect the `event_hash` values for the batch, ordered by `sequence`.
2. These are the leaves of the binary Merkle tree.
3. If the number of leaves is not a power of two, duplicate the last leaf until it is.
4. Recursively hash pairs: `parent = SHA-256(left_child || right_child)`.
5. The final root is the `merkle_root`.

### 4. Merkle Proofs

Any party can request a proof that a specific event is included in a checkpoint. The proof is a minimal set of sibling hashes — one per level of the tree — that allows the verifier to recompute the Merkle root from the event's hash alone.

#### 4.1 Merkle Proof Object

```json
{
  "event_id": "evt_01HXYZ",
  "event_hash": "sha256:7d2Kp9Lm3nQrStUvWxYz1a2B3c4D5e6F7g8H9iJkLmN",
  "checkpoint_id": "chk_01HXYZ",
  "merkle_root": "sha256:Rt7Kp9Lm3nQrStUvWxYz1a2B3c4D5e6F7g8H9iJkLmN",
  "proof_hashes": [
    { "hash": "sha256:aB3c4D5e6F7g8H9iJkLmN0pQrStUvWxYz1a2B3c4D5e", "position": "left" },
    { "hash": "sha256:Xk9Lp2Mn3oQr4StUv5WxYz6a7B8c9D0eF1g2H3iJkLm", "position": "right" },
    { "hash": "sha256:Mn3oQr4StUv5WxYz6a7B8c9D0eF1g2H3iJkLmNoPqRs", "position": "left" }
  ],
  "leaf_index": 42
}
```

#### 4.2 Verification Algorithm

To verify a Merkle proof:

1. Start with `current = event_hash`.
2. For each entry in `proof_hashes`, in order:
   - If `position` is `"left"`: `current = SHA-256(entry.hash || current)`
   - If `position` is `"right"`: `current = SHA-256(current || entry.hash)`
3. After processing all entries, `current` should equal `merkle_root`.
4. Verify the checkpoint's `signature` against the server's public key to confirm the root is authentic.

If both checks pass, the event is provably included in the checkpoint. The proof is O(log n) in size — a log with 1,000,000 events requires only ~20 hashes.

### 5. External Timestamp Anchoring (Optional)

A server MAY publish Merkle roots to an external timestamping service for immutable, public timestamping. Anchoring is entirely optional — the hash chain and Merkle proofs provide full verifiability without any external dependency.

#### 5.1 Why Anchor

- The server signs checkpoints with its own key. A compromised server could produce fraudulent checkpoints with correct signatures. An external timestamp anchor creates an independent witness that the server cannot retroactively alter.
- The external timestamp proves the log existed at a specific point in time. No one — not even the server operator — can backdate events past an anchor.

#### 5.2 Anchor Object

```json
{
  "type": "external-timestamp",
  "provider": "string",
  "reference": "string",
  "timestamp_proof": "string",
  "anchored_at": "2026-02-12T12:00:00Z"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | Always `"external-timestamp"`. |
| `provider` | string | Name of the external timestamping service (e.g., `"opentimestamps"`, `"rfc3161-notary"`, `"custom-ledger"`). |
| `reference` | string | The proof identifier issued by the provider (e.g., a transaction hash, a notary receipt ID, a ledger entry reference). |
| `timestamp_proof` | string | The verifiable proof returned by the provider, enabling independent verification. |
| `anchored_at` | string (ISO 8601) | When the anchor was confirmed by the external service. |

The anchor format is provider-agnostic. Any service that can accept a hash, return a verifiable proof, and guarantee append-only immutability is a valid anchoring provider.

#### 5.3 Anchoring Flow

1. Server creates a checkpoint (Section 3).
2. Server submits the `merkle_root`, `checkpoint_id`, and `event_count` to the configured external timestamping service.
3. The server waits for the service to confirm the submission and return a verifiable proof.
4. Once confirmed, the server updates the checkpoint's `anchor` field with the provider reference and proof.
5. The anchor is immutable — once recorded by the external service, it cannot be altered by the server.

#### 5.4 Anchor Verification

Any party can verify an anchor:

1. Retrieve the checkpoint from the OpenIntent server.
2. Query the external timestamping service using the `reference` and `timestamp_proof` fields.
3. Confirm the Merkle root recorded by the service matches the checkpoint's `merkle_root`.
4. Confirm the service's recorded timestamp is consistent with the checkpoint's `created_at`.

This verification requires no trust in the OpenIntent server — the external timestamping service is the independent witness.

### 6. Log Consistency Verification

The protocol provides two verification modes: full chain verification for intent-scoped logs, and checkpoint-based consistency proofs for efficient cross-checkpoint verification.

#### 6.1 Full Chain Verification

```
GET /api/v1/intents/{id}/events/verify
```

The server returns the complete hash chain for the specified intent. The client verifies locally by recomputing each event's hash and checking `previous_event_hash` linkage. This is O(n) and suitable for intent-scoped logs (typically hundreds to thousands of events).

Response:

```json
{
  "intent_id": "intent_01HABC",
  "event_count": 247,
  "first_sequence": 1,
  "last_sequence": 247,
  "chain_valid": true,
  "events": [
    {
      "sequence": 1,
      "event_hash": "sha256:...",
      "previous_event_hash": null,
      "verified": true
    }
  ]
}
```

#### 6.2 Checkpoint Consistency Proof

```
GET /api/v1/verify/consistency?from_checkpoint=chk_01&to_checkpoint=chk_02
```

Proves that checkpoint 2 extends checkpoint 1 without gaps — the `last_sequence` of checkpoint 1 is immediately followed by the `first_sequence` of checkpoint 2, and the hash chain is continuous across the boundary.

Response:

```json
{
  "from_checkpoint": "chk_01",
  "to_checkpoint": "chk_02",
  "consistent": true,
  "boundary_event": {
    "sequence": 101,
    "event_hash": "sha256:...",
    "previous_event_hash": "sha256:..."
  }
}
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/intents/{id}/events` | List events with `event_hash`, `previous_event_hash`, and `sequence` fields |
| `GET` | `/api/v1/intents/{id}/events/{event_id}` | Get a single event including its hash chain fields |
| `GET` | `/api/v1/intents/{id}/events/verify` | Verify the full hash chain for an intent's event log |
| `GET` | `/api/v1/checkpoints` | List checkpoints (filterable by `intent_id`, `scope`) |
| `GET` | `/api/v1/checkpoints/{checkpoint_id}` | Get a specific checkpoint with its Merkle root and anchor |
| `GET` | `/api/v1/checkpoints/{checkpoint_id}/proof/{event_id}` | Get a Merkle proof for a specific event within a checkpoint |
| `GET` | `/api/v1/verify/consistency` | Verify consistency between two checkpoints |
| `POST` | `/api/v1/admin/checkpoints` | Create a checkpoint on demand (admin) |
| `POST` | `/api/v1/admin/checkpoints/{checkpoint_id}/anchor` | Anchor a checkpoint to an external timestamping service (admin) |

## SDK Usage

```python
from openintent import OpenIntentClient

client = OpenIntentClient(base_url="https://openintent.example.com", api_key="...")

# Events automatically include hashes
events = client.list_events(intent_id="intent_01HABC")
for event in events:
    print(event.event_hash, event.previous_event_hash)

# Verify hash chain locally
verified = client.verify_event_chain(intent_id="intent_01HABC")
# verified.valid       → True
# verified.event_count → 247
# verified.breaks      → [] (list of any gaps or hash mismatches)

# Get Merkle proof for a specific event
proof = client.get_merkle_proof(event_id="evt_01HXYZ")
# proof.verify() → True/False (recomputes root from proof_hashes)
# proof.merkle_root → "sha256:..."
# proof.checkpoint_id → "chk_01HXYZ"

# List checkpoints
checkpoints = client.list_checkpoints(intent_id="intent_01HABC")
for cp in checkpoints:
    print(cp.checkpoint_id, cp.merkle_root, cp.anchor)

# Verify consistency between checkpoints
consistency = client.verify_consistency(
    from_checkpoint="chk_01",
    to_checkpoint="chk_02",
)
# consistency.consistent → True

# For server operators: create a checkpoint on demand
client.admin.create_checkpoint(intent_id="intent_01HABC")

# For server operators: anchor a checkpoint to an external timestamping service
client.admin.anchor_checkpoint(
    checkpoint_id="chk_01HXYZ",
    provider="timestamp-service",
)
```

## Security Considerations

1. **Hash chain verification cost.** Hash chain verification is O(n) in event count. This is practical for intent-scoped logs (typically hundreds to thousands of events), but server-scoped logs may contain millions of events. Server-scoped verification SHOULD use checkpoint-based consistency proofs rather than full chain traversal.

2. **Merkle proof efficiency.** Merkle proofs are O(log n) in size and verification time. A checkpoint covering 1,000,000 events produces proofs of ~20 hashes (~640 bytes). This is efficient for network transmission, storage, and external verification.

3. **Server compromise.** The server signs checkpoints with its own Ed25519 key. A compromised server can produce fraudulent checkpoints with valid signatures. External timestamp anchoring mitigates this by creating an independent witness — the externally recorded proof cannot be altered by the server. For high-assurance deployments, multiple independent verifiers SHOULD monitor checkpoints and cross-check against anchors.

4. **Quantum resistance.** SHA-256 is not quantum-resistant. When post-quantum hash functions (e.g., SHA-3 variants) stabilize for production use, the `sha256:` prefix in hash fields provides a migration path — future events can use a different algorithm prefix without breaking existing verification of historical events.

5. **Canonical JSON determinism.** Signature and hash verification depend on both parties producing identical canonical JSON. The spec requires sorted keys, no whitespace, UTF-8 encoding (RFC 8785 — JSON Canonicalization Scheme). Implementations MUST NOT use locale-dependent serialization, floating-point normalization differences, or non-deterministic key ordering.

6. **Clock trust.** Timestamps in events and checkpoints are server-asserted. A malicious server can lie about timestamps. External timestamp anchoring provides an independent timestamp that the server cannot control. Clients SHOULD cross-reference checkpoint `created_at` with the anchor's externally recorded timestamp when anchors are available.

## Relationship to Other RFCs

| RFC | Relationship |
|-----|-------------|
| **RFC-0001** (Intent Objects) | Extends the Event Object with `event_hash`, `previous_event_hash`, and `sequence` fields. The hash chain is built over RFC-0001 events. |
| **RFC-0006** (Subscriptions) | Subscription consumers can verify events they receive against the hash chain. A consumer that tracks `previous_event_hash` can detect if the server omits or reorders events in the subscription stream. |
| **RFC-0018** (Cryptographic Agent Identity) | Signed events (the `proof` field) are included in the event hash — binding authorship to the chain. A verified event proves both *who* authored it (RFC-0018) and *that it has not been altered* (RFC-0019). Together, they produce a complete chain of custody. |
| **RFC-0020** (Federation) | Federated servers exchange checkpoints to verify each other's logs. A receiving server can validate a remote checkpoint's Merkle root, verify individual event proofs, and check external timestamp anchors — establishing trust in remote event history without trusting the remote server. |

## Non-Goals

- **This RFC does not define a consensus protocol.** The server is the sole writer of the event log. There is no multi-party agreement on log contents. Verifiability means any party can *detect* tampering — not *prevent* it.

- **This RFC does not replace the server's authority.** It provides transparency, not decentralization of writes. The server appends events, builds trees, and signs checkpoints. Clients verify.

- **This RFC does not define the external timestamping service.** It uses external anchoring for optional immutability — a single hash published to a trusted service — not as the primary storage layer. Events live in the OpenIntent server, not in the external service.

- **This RFC does not specify archival or pruning.** Long-running intents may accumulate large event histories. Archival, compression, and pruning strategies are implementation concerns outside the scope of this specification.
