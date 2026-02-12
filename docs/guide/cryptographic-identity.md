---
title: Cryptographic Agent Identity
---

# Cryptographic Agent Identity

RFC-0018 adds verifiable, key-based identity to every agent in the protocol. Each agent can generate or load an Ed25519 key pair, register it with the server via a challenge-response flow, and automatically sign all emitted events.

## Key Concepts

- **Ed25519 Key Pairs** — Agents use Ed25519 for compact, fast digital signatures.
- **DID Identifiers** — Each registered key produces a `did:key:z6Mk...` decentralized identifier.
- **Challenge-Response Registration** — The server issues a random challenge; the agent signs it to prove key ownership.
- **Key Rotation** — Agents can rotate keys while preserving a history of previous public keys.

## Decorator Approach

The simplest way to add identity is the `@Identity` decorator:

```python
from openintent import Agent, Identity, on_assignment

@Agent("secure-agent")
@Identity(auto_sign=True, auto_register=True)
class SecureAgent:
    @on_assignment
    async def handle(self, intent):
        return {"result": "cryptographically signed"}
```

When `auto_register=True`, the agent registers its public key with the server on startup. When `auto_sign=True`, every event the agent emits includes an `EventProof` with the agent's signature.

## Client API

For programmatic control, use the client directly:

```python
from openintent import OpenIntentClient

client = OpenIntentClient(base_url="...", api_key="...", agent_id="bot-1")

# Step 1: Register public key and receive a challenge
challenge = client.register_identity("bot-1", public_key="base64-encoded-key")

# Step 2: Sign the challenge and complete registration
identity = client.complete_identity_challenge("bot-1", challenge.challenge, signature="...")

# Step 3: Verify a signed payload
result = client.verify_signature("bot-1", payload={"action": "transfer"}, signature="...")

# Step 4: Rotate keys
new_identity = client.rotate_key("bot-1", new_public_key="...", old_public_key="...", signature="...")
```

## YAML Workflow

Identity can also be configured declaratively:

```yaml
identity:
  enabled: true
  key_algorithm: Ed25519
  auto_register: true
  auto_sign: true
```

## Lifecycle Hook

Use `@on_identity_registered` to run code after the agent's identity is confirmed:

```python
from openintent import on_identity_registered

@on_identity_registered
async def on_registered(self, identity):
    print(f"Registered as {identity.did}")
```
