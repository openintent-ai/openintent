# RFC-0023: Federation Security

**Status:** Proposed  
**Created:** 2026-02-25  
**Authors:** OpenIntent Contributors  
**Requires:** RFC-0001 (Intents), RFC-0018 (Cryptographic Identity), RFC-0019 (Verifiable Event Logs), RFC-0022 (Federation Protocol)

---

## Abstract

This RFC layers authentication, authorization, and verification onto federation (RFC-0022). It defines server identity, signed envelopes, delegation tokens, trust policies, and cross-server event log reconciliation.

## Motivation

RFC-0022 defines the federation contract — what data moves between servers and when. It deliberately defers security to this companion RFC so that trusted intra-org deployments can federate without cryptographic overhead.

Cross-org and public federation require answers to four questions:

1. **Identity.** How does Server B verify that a request actually came from Server A?
2. **Authorization.** How does Server B verify that Server A is allowed to dispatch this particular intent with these permissions?
3. **Integrity.** How does Server A verify that Server B's results haven't been tampered with?
4. **Delegation.** How does Server B prove to Server C that it's acting on behalf of Server A, with narrowed permissions?

## Specification

### Server Identity

Servers identify themselves using `did:web` decentralized identifiers backed by Ed25519 key pairs:

```python
from openintent.federation.security import ServerIdentity

identity = ServerIdentity.generate(server_url="https://server-a.example.com")
# identity.did => "did:web:server-a.example.com"
# identity.public_key => Ed25519 public key bytes
# identity.private_key => Ed25519 private key bytes
```

The DID document is published at `/.well-known/did.json`:

```json
{
  "@context": "https://www.w3.org/ns/did/v1",
  "id": "did:web:server-a.example.com",
  "verificationMethod": [{
    "id": "did:web:server-a.example.com#key-1",
    "type": "Ed25519VerificationKey2020",
    "controller": "did:web:server-a.example.com",
    "publicKeyMultibase": "z6Mk..."
  }],
  "authentication": ["did:web:server-a.example.com#key-1"]
}
```

### Envelope Signing

Federation envelopes are signed using Ed25519:

```python
from openintent.federation.security import sign_envelope, verify_envelope_signature

signed = sign_envelope(envelope, identity)
# signed.signature is set

is_valid = verify_envelope_signature(signed, identity.public_key)
```

### HTTP Message Signatures (RFC 9421)

For transport-level authentication, `MessageSignature` implements RFC 9421:

```python
from openintent.federation.security import MessageSignature

sig = MessageSignature.create(
    method="POST",
    url="/api/v1/federation/dispatch",
    body=envelope_bytes,
    identity=identity
)

is_valid = MessageSignature.verify(sig, identity.public_key)
```

### Trust Policies

`TrustEnforcer` implements three trust modes:

| Policy | Behavior |
|---|---|
| `open` | Accept all federation requests |
| `allowlist` | Accept only from listed server DIDs |
| `trustless` | Require valid signature and UCAN delegation chain |

```python
from openintent.federation.security import TrustEnforcer, TrustPolicy

enforcer = TrustEnforcer(
    policy=TrustPolicy.ALLOWLIST,
    allowed_servers=["did:web:server-b.example.com"]
)

enforcer.enforce(envelope)  # raises if not allowed
```

### UCAN Delegation Tokens

UCAN (User Controlled Authorization Networks) tokens encode delegation chains:

```python
from openintent.federation.security import UCANToken

token = UCANToken.create(
    issuer=identity,
    audience="did:web:server-b.example.com",
    capabilities=["dispatch", "receive"],
    expiry_seconds=3600
)

encoded = token.encode()  # base64url JWT-style string
decoded = UCANToken.decode(encoded)

# Attenuate for sub-delegation
narrowed = token.attenuate(capabilities=["receive"])
```

### SSRF Protection

Outbound federation URLs are validated to prevent Server-Side Request Forgery:

```python
from openintent.federation.security import validate_ssrf

validate_ssrf("https://server-b.example.com")  # OK
validate_ssrf("http://localhost:8080")  # raises ValueError
validate_ssrf("http://169.254.169.254")  # raises ValueError (cloud metadata)
```

Blocked ranges: localhost, `127.0.0.0/8`, `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `169.254.0.0/16`, IPv6 loopback.

### Cross-Server Event Log Reconciliation

Federated intents produce events on both the originating and receiving servers. RFC-0019 Merkle primitives allow both servers to verify event log consistency:

1. Each server maintains its own hash chain for federated events
2. Attestations include the Merkle root at completion time
3. Either server can request an inclusion proof for any event

## Security Considerations

- **Key rotation:** `ServerIdentity` supports key rotation by publishing updated DID documents. Old keys remain valid for signature verification during a transition period.
- **Token expiry:** UCAN tokens include mandatory expiry. Expired tokens are rejected regardless of signature validity.
- **HMAC fallback:** For environments without Ed25519 support, HMAC-SHA256 signing is available as a fallback (shared secret required).

## SDK Implementation

See the [Federation Guide](../guide/federation.md) for usage examples and the [Federation API Reference](../api/federation.md) for complete class documentation.
