# Cryptographic Agent Identity

Ed25519-based agent identity with DIDs, signed events, challenge-response registration, and key rotation.

## Register Agent Identity

```python
from openintent import OpenIntentClient

client = OpenIntentClient(
    base_url="http://localhost:8000",
    agent_id="secure-bot"
)

# Step 1: Register public key — server returns a challenge
challenge = client.register_identity(
    "secure-bot",
    public_key="MCowBQYDK2VwAyEA..."  # Base64-encoded Ed25519 public key
)
print(f"Challenge: {challenge.challenge}")

# Step 2: Sign the challenge and complete registration
identity = client.complete_identity_challenge(
    "secure-bot",
    challenge=challenge.challenge,
    signature="base64-encoded-signature"
)
print(f"DID: {identity.did}")  # did:key:z6Mk...
```

## Decorator-First Identity

```python
from openintent import Agent, Identity, on_assignment

@Agent("verified-agent")
@Identity(auto_sign=True, auto_register=True)
class VerifiedAgent:
    @on_assignment
    async def handle(self, intent):
        # All events emitted by this agent are automatically signed
        return {"status": "verified"}
```

## Key Rotation

```python
# Rotate to a new key pair while preserving identity history
new_identity = client.rotate_key(
    "secure-bot",
    new_public_key="MCowBQYDK2VwAyEA...",
    old_public_key="MCowBQYDK2VwAyEA...",
    signature="proof-of-old-key-ownership"
)
print(f"New DID: {new_identity.did}")
```

## Verify Event Signatures

```python
# Verify that an event was signed by the claimed agent
result = client.verify_signature(
    "secure-bot",
    payload={"event_type": "state_change", "data": "..."},
    signature="base64-encoded-signature"
)
print(f"Valid: {result.valid}")
```

## Lifecycle Hook

```python
from openintent import on_identity_registered

@on_identity_registered
async def on_registered(self, identity):
    print(f"Agent registered as {identity.did}")
    print(f"Key algorithm: {identity.key_algorithm}")
```

## YAML Workflow Configuration

```yaml
identity:
  enabled: true
  key_algorithm: Ed25519
  auto_register: true
  auto_sign: true
```
