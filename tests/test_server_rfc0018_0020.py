"""
Tests for OpenIntent server — RFC 0018-0020 API endpoints.

RFC-0018: Cryptographic Agent Identity endpoints
RFC-0019: Verifiable Event Logs endpoints
RFC-0020: Distributed Tracing (via IntentEvent trace fields)
"""

import os
import tempfile

import pytest

from openintent.server.config import ServerConfig


class TestRFC0018IdentityEndpoints:
    """Tests for RFC-0018 Cryptographic Agent Identity API endpoints."""

    API_KEY = "dev-user-key"
    HEADERS = {"X-API-Key": "dev-user-key"}

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient

        from openintent.server import database as db_module
        from openintent.server.app import create_app

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        db_module._database = None
        config = ServerConfig(database_url=f"sqlite:///{db_path}")
        app = create_app(config)
        with TestClient(app) as c:
            yield c

        db_module._database = None
        os.unlink(db_path)

    def test_register_identity(self, client):
        resp = client.post(
            "/api/v1/agents/agent-1/identity",
            json={"public_key": "pk_test_123", "key_algorithm": "Ed25519"},
            headers=self.HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "challenge" in data
        assert len(data["challenge"]) > 0
        assert "challenge_expires_at" in data

    def test_register_identity_with_expiry(self, client):
        resp = client.post(
            "/api/v1/agents/agent-1/identity",
            json={
                "public_key": "pk_test_123",
                "key_algorithm": "Ed25519",
                "key_expires_at": "2027-01-01T00:00:00Z",
            },
            headers=self.HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "challenge" in data

    def test_complete_identity_challenge(self, client):
        resp = client.post(
            "/api/v1/agents/agent-1/identity/challenge",
            json={"challenge": "nonce-abc", "signature": "sig-xyz"},
            headers=self.HEADERS,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["agent_id"] == "agent-1"
        assert "did" in data
        assert data["did"].startswith("did:key:")
        assert data["key_algorithm"] == "Ed25519"
        assert "registered_at" in data
        assert data["previous_keys"] == []

    def test_get_identity(self, client):
        resp = client.get(
            "/api/v1/agents/agent-1/identity",
            headers=self.HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["agent_id"] == "agent-1"
        assert data["did"].startswith("did:key:")
        assert data["key_algorithm"] == "Ed25519"
        assert data["previous_keys"] == []

    def test_get_identity_different_agent(self, client):
        resp = client.get(
            "/api/v1/agents/agent-42/identity",
            headers=self.HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["agent_id"] == "agent-42"
        assert "agent-42" in data["did"]

    def test_verify_signature(self, client):
        resp = client.post(
            "/api/v1/agents/agent-1/identity/verify",
            json={
                "payload": {"message": "hello"},
                "signature": "sig-abc",
            },
            headers=self.HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is True
        assert data["agent_id"] == "agent-1"
        assert data["did"].startswith("did:key:")
        assert "verified_at" in data

    def test_rotate_key(self, client):
        resp = client.post(
            "/api/v1/agents/agent-1/identity/rotate",
            json={
                "action": "rotate",
                "new_public_key": "new_pk_456",
                "old_public_key": "old_pk_123",
                "signature": "rotation-sig",
            },
            headers=self.HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["agent_id"] == "agent-1"
        assert data["public_key"] == "new_pk_456"
        assert "old_pk_123" in data["previous_keys"]
        assert data["key_algorithm"] == "Ed25519"

    def test_identity_flow_register_then_complete(self, client):
        reg_resp = client.post(
            "/api/v1/agents/agent-flow/identity",
            json={"public_key": "pk_flow", "key_algorithm": "Ed25519"},
            headers=self.HEADERS,
        )
        assert reg_resp.status_code == 200
        challenge = reg_resp.json()["challenge"]

        complete_resp = client.post(
            "/api/v1/agents/agent-flow/identity/challenge",
            json={"challenge": challenge, "signature": "signed-challenge"},
            headers=self.HEADERS,
        )
        assert complete_resp.status_code == 201
        assert complete_resp.json()["agent_id"] == "agent-flow"

    def test_identity_flow_register_verify_rotate(self, client):
        client.post(
            "/api/v1/agents/agent-full/identity/challenge",
            json={"challenge": "x", "signature": "y"},
            headers=self.HEADERS,
        )

        verify_resp = client.post(
            "/api/v1/agents/agent-full/identity/verify",
            json={"payload": {"data": "test"}, "signature": "sig"},
            headers=self.HEADERS,
        )
        assert verify_resp.json()["valid"] is True

        rotate_resp = client.post(
            "/api/v1/agents/agent-full/identity/rotate",
            json={
                "action": "rotate",
                "new_public_key": "new_key",
                "old_public_key": "old_key",
                "signature": "rotate_sig",
            },
            headers=self.HEADERS,
        )
        assert rotate_resp.json()["public_key"] == "new_key"
        assert "old_key" in rotate_resp.json()["previous_keys"]


class TestRFC0019VerifiableEventLogEndpoints:
    """Tests for RFC-0019 Verifiable Event Logs API endpoints."""

    API_KEY = "dev-user-key"
    HEADERS = {"X-API-Key": "dev-user-key"}

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient

        from openintent.server import database as db_module
        from openintent.server.app import create_app

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        db_module._database = None
        config = ServerConfig(database_url=f"sqlite:///{db_path}")
        app = create_app(config)
        with TestClient(app) as c:
            yield c

        db_module._database = None
        os.unlink(db_path)

    def _create_intent(self, client):
        resp = client.post(
            "/api/v1/intents",
            json={"title": "Verify Test", "description": "For verification"},
            headers=self.HEADERS,
        )
        assert resp.status_code == 200
        return resp.json()["id"]

    def test_verify_event_chain(self, client):
        intent_id = self._create_intent(client)
        resp = client.get(
            f"/api/v1/intents/{intent_id}/events/verify",
            headers=self.HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["intent_id"] == intent_id
        assert "chain_valid" in data or "valid" in data
        assert data.get("chain_valid", data.get("valid")) is True

    def test_verify_event_chain_includes_event_count(self, client):
        intent_id = self._create_intent(client)
        resp = client.get(
            f"/api/v1/intents/{intent_id}/events/verify",
            headers=self.HEADERS,
        )
        data = resp.json()
        assert "event_count" in data
        assert isinstance(data["event_count"], int)

    def test_list_checkpoints_empty(self, client):
        resp = client.get(
            "/api/v1/checkpoints",
            headers=self.HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_get_checkpoint(self, client):
        resp = client.get(
            "/api/v1/checkpoints/cp-test-123",
            headers=self.HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["checkpoint_id"] == "cp-test-123"
        assert data["scope"] == "intent"
        assert "merkle_root" in data
        assert "event_count" in data
        assert "first_sequence" in data
        assert "last_sequence" in data

    def test_get_checkpoint_returns_anchor_field(self, client):
        resp = client.get(
            "/api/v1/checkpoints/cp-abc",
            headers=self.HEADERS,
        )
        data = resp.json()
        assert "anchor" in data

    def test_get_merkle_proof(self, client):
        resp = client.get(
            "/api/v1/checkpoints/cp-1/proof/evt-42",
            headers=self.HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["event_id"] == "evt-42"
        assert data["checkpoint_id"] == "cp-1"
        assert "event_hash" in data
        assert "merkle_root" in data
        assert "proof_hashes" in data
        assert isinstance(data["proof_hashes"], list)
        assert "leaf_index" in data

    def test_verify_consistency(self, client):
        resp = client.get(
            "/api/v1/verify/consistency",
            params={"from_checkpoint": "cp-1", "to_checkpoint": "cp-2"},
            headers=self.HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["from_checkpoint"] == "cp-1"
        assert data["to_checkpoint"] == "cp-2"
        assert data["consistent"] is True

    def test_verify_consistency_empty_params(self, client):
        resp = client.get(
            "/api/v1/verify/consistency",
            headers=self.HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["from_checkpoint"] == ""
        assert data["to_checkpoint"] == ""

    def test_create_checkpoint_admin(self, client):
        intent_id = self._create_intent(client)
        resp = client.post(
            "/api/v1/admin/checkpoints",
            json={"intent_id": intent_id, "scope": "intent"},
            headers=self.HEADERS,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "checkpoint_id" in data
        assert data["checkpoint_id"].startswith("chk_")
        assert data["intent_id"] == intent_id
        assert data["scope"] == "intent"
        assert "created_at" in data

    def test_create_checkpoint_global_scope(self, client):
        resp = client.post(
            "/api/v1/admin/checkpoints",
            json={"scope": "global"},
            headers=self.HEADERS,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["scope"] == "global"

    def test_anchor_checkpoint(self, client):
        resp = client.post(
            "/api/v1/admin/checkpoints/cp-test/anchor",
            json={"provider": "opentimestamps"},
            headers=self.HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["checkpoint_id"] == "cp-test"
        assert "anchor" in data
        assert data["anchor"]["type"] == "external-timestamp"
        assert data["anchor"]["provider"] == "opentimestamps"
        assert "reference" in data["anchor"]
        assert "anchored_at" in data["anchor"]

    def test_checkpoint_lifecycle_create_get_anchor(self, client):
        create_resp = client.post(
            "/api/v1/admin/checkpoints",
            json={"intent_id": None, "scope": "global"},
            headers=self.HEADERS,
        )
        assert create_resp.status_code == 201
        cp_id = create_resp.json()["checkpoint_id"]

        get_resp = client.get(
            f"/api/v1/checkpoints/{cp_id}",
            headers=self.HEADERS,
        )
        assert get_resp.status_code == 200
        assert get_resp.json()["checkpoint_id"] == cp_id

        anchor_resp = client.post(
            f"/api/v1/admin/checkpoints/{cp_id}/anchor",
            json={"provider": "rfc3161"},
            headers=self.HEADERS,
        )
        assert anchor_resp.status_code == 200
        assert anchor_resp.json()["anchor"]["provider"] == "rfc3161"


class TestRFC0020DistributedTracingEndpoints:
    """Tests for RFC-0020 Distributed Tracing via event log fields."""

    API_KEY = "dev-user-key"
    HEADERS = {"X-API-Key": "dev-user-key"}

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient

        from openintent.server import database as db_module
        from openintent.server.app import create_app

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        db_module._database = None
        config = ServerConfig(database_url=f"sqlite:///{db_path}")
        app = create_app(config)
        with TestClient(app) as c:
            yield c

        db_module._database = None
        os.unlink(db_path)

    def _create_intent(self, client):
        resp = client.post(
            "/api/v1/intents",
            json={"title": "Tracing Test", "description": "For tracing"},
            headers=self.HEADERS,
        )
        assert resp.status_code == 200
        return resp.json()["id"]

    def test_log_event_with_trace_id_in_payload(self, client):
        intent_id = self._create_intent(client)
        resp = client.post(
            f"/api/v1/intents/{intent_id}/events",
            json={
                "event_type": "note",
                "actor": "agent-1",
                "payload": {
                    "message": "traced event",
                    "trace_id": "trace-abc123def456",
                },
            },
            headers=self.HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["intent_id"] == intent_id

    def test_log_event_with_trace_and_parent_in_payload(self, client):
        intent_id = self._create_intent(client)
        resp = client.post(
            f"/api/v1/intents/{intent_id}/events",
            json={
                "event_type": "note",
                "actor": "agent-1",
                "payload": {
                    "message": "child traced event",
                    "trace_id": "trace-abc123def456",
                    "parent_event_id": "evt-parent-001",
                },
            },
            headers=self.HEADERS,
        )
        assert resp.status_code == 200

    def test_log_event_without_tracing_still_works(self, client):
        intent_id = self._create_intent(client)
        resp = client.post(
            f"/api/v1/intents/{intent_id}/events",
            json={
                "event_type": "note",
                "actor": "agent-1",
                "payload": {"message": "no tracing"},
            },
            headers=self.HEADERS,
        )
        assert resp.status_code == 200

    def test_log_tool_invocation_event(self, client):
        intent_id = self._create_intent(client)
        resp = client.post(
            f"/api/v1/intents/{intent_id}/events",
            json={
                "event_type": "tool_invocation",
                "actor": "agent-1",
                "payload": {
                    "tool_name": "search",
                    "arguments": {"query": "test"},
                    "result": {"answer": "42"},
                    "duration_ms": 150.5,
                    "agent_id": "agent-1",
                    "trace_id": "trace-tool-001",
                    "parent_event_id": "evt-parent",
                },
            },
            headers=self.HEADERS,
        )
        assert resp.status_code == 200

    def test_events_list_returns_events(self, client):
        intent_id = self._create_intent(client)
        client.post(
            f"/api/v1/intents/{intent_id}/events",
            json={
                "event_type": "note",
                "actor": "agent-1",
                "payload": {"message": "test"},
            },
            headers=self.HEADERS,
        )
        resp = client.get(
            f"/api/v1/intents/{intent_id}/events",
            headers=self.HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1
