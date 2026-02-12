# Verifiable Event Logs

Hash-chained, Merkle-tree-backed event logs with tamper evidence, compact inclusion proofs, and optional external anchoring.

## Verify Hash Chain

```python
from openintent import OpenIntentClient

client = OpenIntentClient(
    base_url="http://localhost:8000",
    agent_id="auditor"
)

# Verify the complete hash chain for an intent's event log
chain = client.verify_event_chain("intent-123")
print(f"Valid: {chain.valid}")
print(f"Events verified: {chain.event_count}")
print(f"Breaks found: {chain.breaks}")  # Empty list if valid
```

## List and Inspect Checkpoints

```python
# List all checkpoints for an intent
checkpoints = client.list_checkpoints(intent_id="intent-123")
for cp in checkpoints:
    print(f"Checkpoint {cp.checkpoint_id}")
    print(f"  Merkle root: {cp.merkle_root}")
    print(f"  Events: {cp.first_sequence}..{cp.last_sequence}")
    print(f"  Anchored: {cp.anchor is not None}")
```

## Get Merkle Proof

```python
# Prove that a specific event is included in a checkpoint
proof = client.get_merkle_proof(
    checkpoint_id="chk-01",
    event_id="evt-42"
)

# Verify locally — recomputes the Merkle root from proof hashes
is_valid = proof.verify()
print(f"Inclusion proof valid: {is_valid}")
print(f"Proof size: {len(proof.proof_hashes)} hashes")
```

## Verify Checkpoint Consistency

```python
# Verify that two checkpoints are consistent
# (the later checkpoint extends the earlier one)
consistency = client.verify_consistency("chk-01", "chk-02")
print(f"Consistent: {consistency.consistent}")
print(f"Boundary event: seq {consistency.boundary_event.sequence}")
```

## Admin: Create Checkpoint

```python
# Manually trigger a checkpoint (admin operation)
checkpoint = client.admin.create_checkpoint(intent_id="intent-123")
print(f"Created: {checkpoint.checkpoint_id}")
print(f"Root: {checkpoint.merkle_root}")
```

## Admin: Anchor to External Service

```python
# Anchor a checkpoint to an external timestamping service
client.admin.anchor_checkpoint(
    checkpoint_id="chk-01",
    provider="timestamp-service-name"
)
```

## Event Hash Chain Visualization

```text
Event 1              Event 2              Event 3
+----------------+   +----------------+   +----------------+
| content        |   | content        |   | content        |
| prev: null     |-->| prev: hash_1   |-->| prev: hash_2   |
| seq: 1         |   | seq: 2         |   | seq: 3         |
| hash_1 = H(.)  |   | hash_2 = H(.)  |   | hash_3 = H(.)  |
+----------------+   +----------------+   +----------------+
```

Each hash covers the event's content **and** the previous event's hash. Modifying any event invalidates its hash — and every subsequent hash.

## YAML Workflow Configuration

```yaml
verification:
  enabled: true
  verify_chain: true
  checkpoint_interval: 100
  checkpoint_time_minutes: 5
```
