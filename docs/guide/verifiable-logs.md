---
title: Verifiable Event Logs
---

# Verifiable Event Logs

RFC-0019 turns the append-only event log into a cryptographically verifiable structure. Every event receives a SHA-256 hash that chains to the previous event, forming an unbreakable sequence. Periodic checkpoints group events into Merkle trees for efficient verification.

## Key Concepts

- **Hash Chains** — Each event's hash includes the previous event's hash, creating a tamper-evident chain.
- **Merkle Trees** — Checkpoints build a Merkle tree over a batch of event hashes, producing a single `merkle_root`.
- **Inclusion Proofs** — Any event can be proven to be part of a checkpoint using a compact Merkle proof.
- **Consistency Proofs** — Two checkpoints can be verified to be consistent (the later checkpoint extends the earlier one).
- **Optional Anchoring** — Checkpoint roots can be anchored to external timestamping services for independent verification.

## Client API

```python
from openintent import OpenIntentClient

client = OpenIntentClient(base_url="...", api_key="...", agent_id="auditor")

# Verify the full hash chain for an intent
chain = client.verify_event_chain("intent-123")
print(f"Chain valid: {chain.valid}, events: {chain.event_count}")

# List checkpoints
checkpoints = client.list_checkpoints(intent_id="intent-123")

# Get a Merkle proof for a specific event
proof = client.get_merkle_proof(checkpoint_id="chk-1", event_id="evt-42")
print(f"Proof valid: {proof.verify()}")

# Verify consistency between two checkpoints
consistency = client.verify_consistency("chk-1", "chk-2")
print(f"Consistent: {consistency.consistent}")
```

## YAML Workflow

Verification can be configured declaratively:

```yaml
verification:
  enabled: true
  verify_chain: true
  checkpoint_interval: 100
  checkpoint_time_minutes: 5
```

## Data Models

Key models for verification:

- `ChainVerification` — Result of verifying an intent's hash chain.
- `LogCheckpoint` — A signed checkpoint over a batch of event hashes.
- `MerkleProof` — Proof that an event is included in a checkpoint. Call `.verify()` to recompute the root.
- `ConsistencyProof` — Result of verifying two checkpoints are consistent.
- `TimestampAnchor` — External timestamp anchor attached to a checkpoint.
