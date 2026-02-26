# Cross-Server Federation

Coordinate agents across multiple OpenIntent servers.

## Basic Dispatch and Receive

Dispatch an intent from one server to another:

```python
from openintent import OpenIntentClient

client = OpenIntentClient(base_url="http://localhost:8000", api_key="dev-key")

result = client.federation_dispatch(
    target_server="https://partner.example.com",
    intent_id="intent_01",
    intent_title="Analyze Q1 data",
    intent_description="Run financial analysis on Q1 dataset",
    delegation_scope={
        "permissions": ["state.patch", "events.log"],
        "max_delegation_depth": 1,
    },
)

print(result["dispatch_id"])   # "dispatch_abc123"
print(result["status"])        # "accepted"
```

The receiving server processes the envelope automatically:

```python
from openintent import OpenIntentClient

remote_client = OpenIntentClient(base_url="https://partner.example.com", api_key="partner-key")

received = remote_client.federation_receive(
    dispatch_id="dispatch_abc123",
    source_server="http://localhost:8000",
    intent_id="intent_01",
    intent_title="Analyze Q1 data",
)

print(received["accepted"])        # True
print(received["local_intent_id"]) # "intent_remote_42"
```

## YAML Federation Workflow

Define federation peers and trust policies declaratively:

```yaml
openintent: "1.0"
info:
  name: "Federated Research Pipeline"

federation:
  server_did: "did:web:research.example.com"
  trust_policy: allowlist
  visibility_default: public
  peers:
    - url: "https://partner-a.example.com"
      relationship: peer
      trust_policy: allowlist
    - url: "https://partner-b.example.com"
      relationship: downstream
      trust_policy: open

workflow:
  collect:
    assign: data-collector
    federation_visibility: public
  analyze:
    assign: remote-analyzer
    dispatch_to: "https://partner-a.example.com"
    delegation_scope:
      permissions: [state.patch, events.log]
      max_delegation_depth: 1
    depends_on: [collect]
  summarize:
    assign: report-writer
    depends_on: [analyze]
```

## Envelope Signing

Sign federation envelopes with Ed25519 keys for tamper-proof dispatch:

```python
from openintent.federation.security import ServerIdentity, sign_envelope, verify_envelope_signature
from openintent.federation.models import FederationEnvelope

identity = ServerIdentity.generate("https://my-server.example.com")

envelope = FederationEnvelope(
    dispatch_id="dispatch_001",
    source_server="https://my-server.example.com",
    target_server="https://partner.example.com",
    intent_id="intent_01",
    intent_title="Analyze dataset",
)

envelope_dict = envelope.to_dict()
signature = sign_envelope(identity, envelope_dict)
envelope_dict["signature"] = signature

print(signature)  # base64-encoded Ed25519 signature
```

Verify on the receiving end:

```python
public_key_b64 = identity.public_key_b64

valid = verify_envelope_signature(
    public_key_b64=public_key_b64,
    envelope_dict=envelope_dict,
    signature_b64=envelope_dict["signature"],
)

print(valid)  # True
```

## UCAN Delegation Tokens

Create capability tokens that scope what remote servers can do:

```python
from openintent.federation.security import ServerIdentity, UCANToken
from openintent.federation.models import DelegationScope

identity = ServerIdentity.generate("https://my-server.example.com")

scope = DelegationScope(
    permissions=["state.patch", "events.log"],
    denied_operations=["intent.delete"],
    max_delegation_depth=2,
)

token = UCANToken(
    issuer=identity.did,
    audience="did:web:partner.example.com",
    scope=scope,
)

encoded = token.encode(identity)
print(encoded)  # eyJhbGci...

decoded = UCANToken.decode(encoded)
print(decoded.issuer)    # "did:web:my-server.example.com"
print(decoded.audience)  # "did:web:partner.example.com"
print(decoded.is_active())  # True
```

## Trust Enforcement

Control which peers can dispatch intents to your server:

```python
from openintent.federation.security import TrustEnforcer
from openintent.federation.models import TrustPolicy

enforcer = TrustEnforcer(
    policy=TrustPolicy.ALLOWLIST,
    allowed_peers=["https://partner-a.example.com", "did:web:partner-b.example.com"],
)

print(enforcer.is_trusted("https://partner-a.example.com"))   # True
print(enforcer.is_trusted("https://unknown.example.com"))       # False
print(enforcer.is_trusted("https://x.com", "did:web:partner-b.example.com"))  # True

enforcer.add_peer("https://new-partner.example.com")
print(enforcer.is_trusted("https://new-partner.example.com"))  # True
```

Open trust accepts all peers:

```python
open_enforcer = TrustEnforcer(policy=TrustPolicy.OPEN)
print(open_enforcer.is_trusted("https://anyone.example.com"))  # True
```

Trustless mode rejects everything:

```python
strict_enforcer = TrustEnforcer(policy=TrustPolicy.TRUSTLESS)
print(strict_enforcer.is_trusted("https://partner-a.example.com"))  # False
```

## Multi-Hop Delegation

Attenuate UCAN tokens when re-delegating to a third server:

```python
from openintent.federation.security import ServerIdentity, UCANToken
from openintent.federation.models import DelegationScope

server_a = ServerIdentity.generate("https://server-a.example.com")
server_b = ServerIdentity.generate("https://server-b.example.com")

root_scope = DelegationScope(
    permissions=["state.patch", "events.log", "intent.create"],
    max_delegation_depth=3,
)

root_token = UCANToken(
    issuer=server_a.did,
    audience=server_b.did,
    scope=root_scope,
)

child_scope = DelegationScope(
    permissions=["state.patch", "events.log"],
    max_delegation_depth=2,
)

child_token = root_token.attenuate(
    audience="did:web:server-c.example.com",
    child_scope=child_scope,
    identity=server_a,
)

print(child_token.issuer)                    # server_b's DID
print(child_token.audience)                  # "did:web:server-c.example.com"
print(child_token.scope.permissions)         # ["events.log", "state.patch"]
print(child_token.scope.max_delegation_depth)  # 2
print(len(child_token.proof_chain))          # 1 (parent token)
```

## Federation Decorator

Configure a server class for federation with a single decorator:

```python
from openintent.federation.decorators import Federation, on_federation_received, on_federation_callback
from openintent.agents import Agent, on_assignment

@Federation(
    server_url="https://my-server.example.com",
    trust_policy="allowlist",
    visibility_default="public",
    peers=["https://partner.example.com"],
)
class MyFederatedServer:
    pass

server = MyFederatedServer()
print(server._federation_identity.did)  # "did:web:my-server.example.com"
```

Handle incoming federated work and callbacks:

```python
@Agent("federated-worker", federation_visibility="public")
class FederatedWorker:
    @on_assignment
    async def handle(self, intent):
        return {"result": "done"}

    @on_federation_received
    async def on_received(self, envelope):
        print(f"Received dispatch {envelope['dispatch_id']} from {envelope['source_server']}")

    @on_federation_callback
    async def on_callback(self, callback):
        print(f"Callback for {callback['dispatch_id']}: {callback['event_type']}")

FederatedWorker.run()
```

## Discovery Manifest

Fetch the well-known federation manifest from any peer:

```python
import httpx

response = httpx.get("https://partner.example.com/.well-known/openintent-federation.json")
manifest = response.json()

print(manifest["server_did"])         # "did:web:partner.example.com"
print(manifest["trust_policy"])       # "allowlist"
print(manifest["supported_rfcs"])     # ["RFC-0022", "RFC-0023"]
print(manifest["endpoints"]["dispatch"])  # "/api/v1/federation/dispatch"
```
