"""
OpenIntent SDK - Federation security (RFC-0023).

Server identity (did:web), HTTP Message Signatures (RFC 9421),
UCAN delegation tokens, and trust policy enforcement.
"""

import base64
import hashlib
import hmac
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from .models import DelegationScope, TrustPolicy

logger = logging.getLogger("openintent.federation.security")


try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
    )
    from cryptography.hazmat.primitives.serialization import (
        Encoding,
        NoEncryption,
        PrivateFormat,
        PublicFormat,
    )

    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False


@dataclass
class ServerIdentity:
    server_url: str
    did: str = ""
    private_key_bytes: Optional[bytes] = None
    public_key_bytes: Optional[bytes] = None

    def __post_init__(self):
        if not self.did:
            domain = self.server_url.replace("https://", "").replace("http://", "").rstrip("/")
            self.did = f"did:web:{domain}"

    @classmethod
    def generate(cls, server_url: str) -> "ServerIdentity":
        if not HAS_CRYPTO:
            return cls._generate_hmac_fallback(server_url)

        private_key = Ed25519PrivateKey.generate()
        private_bytes = private_key.private_bytes(
            Encoding.Raw, PrivateFormat.Raw, NoEncryption()
        )
        public_bytes = private_key.public_key().public_bytes(
            Encoding.Raw, PublicFormat.Raw
        )
        return cls(
            server_url=server_url,
            private_key_bytes=private_bytes,
            public_key_bytes=public_bytes,
        )

    @classmethod
    def _generate_hmac_fallback(cls, server_url: str) -> "ServerIdentity":
        import os

        secret = os.urandom(32)
        public = hashlib.sha256(secret).digest()
        return cls(
            server_url=server_url,
            private_key_bytes=secret,
            public_key_bytes=public,
        )

    @classmethod
    def from_key_file(cls, server_url: str, key_path: str) -> "ServerIdentity":
        with open(key_path, "rb") as f:
            key_data = f.read()

        if HAS_CRYPTO:
            private_key = Ed25519PrivateKey.from_private_bytes(key_data[:32])
            public_bytes = private_key.public_key().public_bytes(
                Encoding.Raw, PublicFormat.Raw
            )
            return cls(
                server_url=server_url,
                private_key_bytes=key_data[:32],
                public_key_bytes=public_bytes,
            )

        return cls(
            server_url=server_url,
            private_key_bytes=key_data[:32],
            public_key_bytes=hashlib.sha256(key_data[:32]).digest(),
        )

    def save_key(self, key_path: str) -> None:
        if self.private_key_bytes:
            with open(key_path, "wb") as f:
                f.write(self.private_key_bytes)

    @property
    def public_key_b64(self) -> str:
        if self.public_key_bytes:
            return base64.b64encode(self.public_key_bytes).decode()
        return ""

    def did_document(self) -> dict[str, Any]:
        return {
            "@context": ["https://www.w3.org/ns/did/v1"],
            "id": self.did,
            "verificationMethod": [
                {
                    "id": f"{self.did}#key-1",
                    "type": "Ed25519VerificationKey2020",
                    "controller": self.did,
                    "publicKeyBase64": self.public_key_b64,
                }
            ],
            "authentication": [f"{self.did}#key-1"],
        }

    def sign(self, message: bytes) -> str:
        if not self.private_key_bytes:
            raise ValueError("No private key available for signing")

        if HAS_CRYPTO:
            private_key = Ed25519PrivateKey.from_private_bytes(self.private_key_bytes)
            signature = private_key.sign(message)
            return base64.b64encode(signature).decode()

        signature = hmac.new(self.private_key_bytes, message, hashlib.sha256).digest()
        return base64.b64encode(signature).decode()

    def verify(self, message: bytes, signature_b64: str) -> bool:
        try:
            signature = base64.b64decode(signature_b64)
        except Exception:
            return False

        if HAS_CRYPTO and self.public_key_bytes and len(self.public_key_bytes) == 32:
            try:
                public_key = Ed25519PublicKey.from_public_bytes(self.public_key_bytes)
                public_key.verify(signature, message)
                return True
            except Exception:
                return False

        if self.private_key_bytes:
            expected = hmac.new(
                self.private_key_bytes, message, hashlib.sha256
            ).digest()
            return hmac.compare_digest(signature, expected)

        return False


def sign_envelope(identity: ServerIdentity, envelope_dict: dict[str, Any]) -> str:
    signing_data = _canonical_bytes(envelope_dict)
    return identity.sign(signing_data)


def verify_envelope_signature(
    public_key_b64: str, envelope_dict: dict[str, Any], signature_b64: str
) -> bool:
    try:
        public_key_bytes = base64.b64decode(public_key_b64)
    except Exception:
        return False

    signing_data = _canonical_bytes(envelope_dict)

    if HAS_CRYPTO and len(public_key_bytes) == 32:
        try:
            public_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)
            signature = base64.b64decode(signature_b64)
            public_key.verify(signature, signing_data)
            return True
        except Exception:
            return False

    return False


def _canonical_bytes(data: dict[str, Any]) -> bytes:
    filtered = {k: v for k, v in sorted(data.items()) if k != "signature"}
    return json.dumps(filtered, sort_keys=True, separators=(",", ":")).encode()


@dataclass
class MessageSignature:
    key_id: str
    algorithm: str = "ed25519"
    created: int = 0
    headers: list[str] = field(default_factory=lambda: [
        "@method", "@target-uri", "content-type", "content-digest"
    ])
    signature: str = ""

    def __post_init__(self):
        if not self.created:
            self.created = int(time.time())

    @classmethod
    def create(
        cls,
        identity: ServerIdentity,
        method: str,
        target_uri: str,
        content_type: str = "application/json",
        body: Optional[bytes] = None,
    ) -> "MessageSignature":
        sig = cls(key_id=identity.did)

        components = [
            f'"@method": {method.upper()}',
            f'"@target-uri": {target_uri}',
            f'"content-type": {content_type}',
        ]

        if body:
            digest = hashlib.sha256(body).hexdigest()
            components.append(f'"content-digest": sha-256=:{digest}:')

        components.append(f'"@signature-params": ({" ".join(sig.headers)})')
        signing_input = "\n".join(components)
        sig.signature = identity.sign(signing_input.encode())
        return sig

    def to_header(self) -> str:
        params = f'sig1=("{" ".join(self.headers)}");keyid="{self.key_id}";alg="{self.algorithm}";created={self.created}'
        return params

    def signature_header(self) -> str:
        return f"sig1=:{self.signature}:"


class TrustEnforcer:
    def __init__(
        self,
        policy: TrustPolicy,
        allowed_peers: Optional[list[str]] = None,
    ):
        self.policy = policy
        self.allowed_peers = set(allowed_peers or [])

    def is_trusted(self, source_server: str, source_did: Optional[str] = None) -> bool:
        if self.policy == TrustPolicy.OPEN:
            return True

        if self.policy == TrustPolicy.ALLOWLIST:
            if source_server in self.allowed_peers:
                return True
            if source_did and source_did in self.allowed_peers:
                return True
            return False

        if self.policy == TrustPolicy.TRUSTLESS:
            return False

        return False

    def add_peer(self, peer: str) -> None:
        self.allowed_peers.add(peer)

    def remove_peer(self, peer: str) -> None:
        self.allowed_peers.discard(peer)


@dataclass
class UCANToken:
    issuer: str
    audience: str
    scope: DelegationScope
    not_before: int = 0
    expires_at: int = 0
    nonce: str = ""
    proof_chain: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.not_before:
            self.not_before = int(time.time())
        if not self.expires_at:
            self.expires_at = self.not_before + 3600
        if not self.nonce:
            import os
            self.nonce = base64.b64encode(os.urandom(16)).decode()

    def to_dict(self) -> dict[str, Any]:
        return {
            "iss": self.issuer,
            "aud": self.audience,
            "scope": self.scope.to_dict(),
            "nbf": self.not_before,
            "exp": self.expires_at,
            "nonce": self.nonce,
            "prf": self.proof_chain,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UCANToken":
        return cls(
            issuer=data.get("iss", ""),
            audience=data.get("aud", ""),
            scope=DelegationScope.from_dict(data.get("scope", {})),
            not_before=data.get("nbf", 0),
            expires_at=data.get("exp", 0),
            nonce=data.get("nonce", ""),
            proof_chain=data.get("prf", []),
        )

    def encode(self, identity: ServerIdentity) -> str:
        header = base64.urlsafe_b64encode(
            json.dumps({"alg": "EdDSA", "typ": "UCAN"}).encode()
        ).decode().rstrip("=")
        payload = base64.urlsafe_b64encode(
            json.dumps(self.to_dict(), sort_keys=True).encode()
        ).decode().rstrip("=")
        signing_input = f"{header}.{payload}"
        signature = identity.sign(signing_input.encode())
        sig_part = base64.urlsafe_b64encode(
            base64.b64decode(signature)
        ).decode().rstrip("=")
        return f"{header}.{payload}.{sig_part}"

    @classmethod
    def decode(cls, token: str) -> "UCANToken":
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("Invalid UCAN token format")
        padding = 4 - len(parts[1]) % 4
        payload_bytes = base64.urlsafe_b64decode(parts[1] + "=" * padding)
        payload = json.loads(payload_bytes)
        return cls.from_dict(payload)

    def is_expired(self) -> bool:
        return int(time.time()) > self.expires_at

    def is_active(self) -> bool:
        now = int(time.time())
        return self.not_before <= now <= self.expires_at

    def attenuate(
        self,
        audience: str,
        child_scope: DelegationScope,
        identity: ServerIdentity,
    ) -> "UCANToken":
        new_scope = self.scope.attenuate(child_scope)
        if new_scope.max_delegation_depth < 0:
            raise ValueError("Delegation depth exceeded")
        parent_token = self.encode(identity)
        return UCANToken(
            issuer=self.audience,
            audience=audience,
            scope=new_scope,
            expires_at=self.expires_at,
            proof_chain=self.proof_chain + [parent_token],
        )


def resolve_did_web(did: str) -> str:
    if not did.startswith("did:web:"):
        raise ValueError(f"Not a did:web identifier: {did}")
    domain = did[len("did:web:"):]
    domain = domain.replace(":", "/")
    return f"https://{domain}/.well-known/did.json"


def validate_ssrf(url: str) -> bool:
    from urllib.parse import urlparse

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False
    hostname = parsed.hostname or ""
    if not hostname:
        return False
    blocked = [
        "localhost",
        "127.0.0.1",
        "0.0.0.0",
        "::1",
        "[::1]",
        "169.254.169.254",
        "metadata.google.internal",
    ]
    if hostname in blocked:
        return False
    if hostname.startswith("10.") or hostname.startswith("172.") or hostname.startswith("192.168."):
        return False
    if hostname.endswith(".internal") or hostname.endswith(".local"):
        return False
    return True
