"""
Unit tests for the OpenIntent server module.

Tests server configuration, database, and API endpoints.
"""

import os
import tempfile
from unittest.mock import patch

import pytest

from openintent.server.config import ServerConfig
from openintent.server.database import Database


class TestServerConfig:
    """Tests for ServerConfig."""

    def test_defaults(self):
        config = ServerConfig()
        assert config.host == "0.0.0.0"
        assert config.port == 8000
        assert config.protocol_version == "0.1"
        assert "dev-user-key" in config.api_keys
        assert "agent-research-key" in config.api_keys

    def test_custom_values(self):
        config = ServerConfig(
            host="127.0.0.1",
            port=9000,
            database_url="postgresql://localhost/test",
            debug=True,
        )
        assert config.host == "127.0.0.1"
        assert config.port == 9000
        assert config.database_url == "postgresql://localhost/test"
        assert config.debug is True

    def test_from_env(self):
        with patch.dict(
            os.environ,
            {
                "OPENINTENT_HOST": "0.0.0.0",
                "OPENINTENT_PORT": "9999",
                "OPENINTENT_DEBUG": "true",
            },
        ):
            config = ServerConfig.from_env()
            assert config.port == 9999
            assert config.debug is True


class TestDatabase:
    """Tests for Database operations."""

    @pytest.fixture
    def db(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        db = Database(f"sqlite:///{db_path}")
        db.create_tables()
        yield db

        os.unlink(db_path)

    def test_create_intent(self, db):
        session = db.get_session()
        try:
            intent = db.create_intent(
                session,
                title="Test Intent",
                description="A test",
                created_by="test-user",
            )

            assert intent.id is not None
            assert intent.title == "Test Intent"
            assert intent.description == "A test"
            assert intent.created_by == "test-user"
            assert intent.status == "draft"
            assert intent.version == 1
        finally:
            session.close()

    def test_get_intent(self, db):
        session = db.get_session()
        try:
            created = db.create_intent(
                session,
                title="Get Test",
                created_by="user",
            )

            fetched = db.get_intent(session, created.id)
            assert fetched is not None
            assert fetched.id == created.id
            assert fetched.title == "Get Test"
        finally:
            session.close()

    def test_get_intent_not_found(self, db):
        session = db.get_session()
        try:
            result = db.get_intent(session, "nonexistent-id")
            assert result is None
        finally:
            session.close()

    def test_update_intent_state(self, db):
        session = db.get_session()
        try:
            intent = db.create_intent(
                session,
                title="State Test",
                created_by="user",
            )

            patches = [
                {"op": "set", "path": "/progress", "value": 0.5},
                {"op": "set", "path": "/status", "value": "running"},
            ]

            updated = db.update_intent_state(session, intent.id, 1, patches)

            assert updated is not None
            assert updated.version == 2
            assert updated.state["progress"] == 0.5
            assert updated.state["status"] == "running"
        finally:
            session.close()

    def test_update_intent_state_version_conflict(self, db):
        session = db.get_session()
        try:
            intent = db.create_intent(
                session,
                title="Conflict Test",
                created_by="user",
            )

            patches = [{"op": "set", "path": "/x", "value": 1}]
            result = db.update_intent_state(session, intent.id, 999, patches)

            assert result is None
        finally:
            session.close()

    def test_update_intent_status(self, db):
        session = db.get_session()
        try:
            intent = db.create_intent(
                session,
                title="Status Test",
                created_by="user",
            )

            updated = db.update_intent_status(session, intent.id, 1, "active")

            assert updated is not None
            assert updated.status == "active"
            assert updated.version == 2
        finally:
            session.close()

    def test_create_event(self, db):
        session = db.get_session()
        try:
            intent = db.create_intent(
                session,
                title="Event Test",
                created_by="user",
            )

            event = db.create_event(
                session,
                intent_id=intent.id,
                event_type="test_event",
                actor="test-actor",
                payload={"key": "value"},
            )

            assert event.id is not None
            assert event.intent_id == intent.id
            assert event.event_type == "test_event"
            assert event.actor == "test-actor"
            assert event.payload == {"key": "value"}
        finally:
            session.close()

    def test_get_events(self, db):
        session = db.get_session()
        try:
            intent = db.create_intent(
                session,
                title="Events Test",
                created_by="user",
            )

            for i in range(5):
                db.create_event(
                    session,
                    intent_id=intent.id,
                    event_type=f"event_{i}",
                    actor="actor",
                )

            events = db.get_events(session, intent.id)
            assert len(events) == 5

            limited = db.get_events(session, intent.id, limit=2)
            assert len(limited) == 2
        finally:
            session.close()

    def test_assign_agent(self, db):
        session = db.get_session()
        try:
            intent = db.create_intent(
                session,
                title="Agent Test",
                created_by="user",
            )

            agent = db.assign_agent(
                session,
                intent_id=intent.id,
                agent_id="test-agent",
                role="worker",
            )

            assert agent.id is not None
            assert agent.agent_id == "test-agent"
            assert agent.role == "worker"
        finally:
            session.close()

    def test_get_agents(self, db):
        session = db.get_session()
        try:
            intent = db.create_intent(
                session,
                title="Agents List Test",
                created_by="user",
            )

            db.assign_agent(session, intent_id=intent.id, agent_id="agent-1")
            db.assign_agent(session, intent_id=intent.id, agent_id="agent-2")

            agents = db.get_agents(session, intent.id)
            assert len(agents) == 2
        finally:
            session.close()

    def test_acquire_lease(self, db):
        session = db.get_session()
        try:
            intent = db.create_intent(
                session,
                title="Lease Test",
                created_by="user",
            )

            lease = db.acquire_lease(
                session,
                intent_id=intent.id,
                agent_id="agent-1",
                scope="research",
                duration_seconds=300,
            )

            assert lease is not None
            assert lease.scope == "research"
            assert lease.agent_id == "agent-1"
        finally:
            session.close()

    def test_acquire_lease_conflict(self, db):
        session = db.get_session()
        try:
            intent = db.create_intent(
                session,
                title="Lease Conflict Test",
                created_by="user",
            )

            lease1 = db.acquire_lease(
                session,
                intent_id=intent.id,
                agent_id="agent-1",
                scope="research",
                duration_seconds=300,
            )

            lease2 = db.acquire_lease(
                session,
                intent_id=intent.id,
                agent_id="agent-2",
                scope="research",
                duration_seconds=300,
            )

            assert lease1 is not None
            assert lease2 is None
        finally:
            session.close()

    def test_release_lease(self, db):
        session = db.get_session()
        try:
            intent = db.create_intent(
                session,
                title="Release Test",
                created_by="user",
            )

            lease = db.acquire_lease(
                session,
                intent_id=intent.id,
                agent_id="agent-1",
                scope="research",
                duration_seconds=300,
            )

            released = db.release_lease(session, lease.id, "agent-1")
            assert released is not None
            assert released.released_at is not None
        finally:
            session.close()

    def test_create_portfolio(self, db):
        session = db.get_session()
        try:
            portfolio = db.create_portfolio(
                session,
                name="Test Portfolio",
                description="A test portfolio",
                created_by="user",
            )

            assert portfolio.id is not None
            assert portfolio.name == "Test Portfolio"
            assert portfolio.status == "active"
        finally:
            session.close()

    def test_add_intent_to_portfolio(self, db):
        session = db.get_session()
        try:
            portfolio = db.create_portfolio(
                session,
                name="Portfolio",
                created_by="user",
            )

            intent = db.create_intent(
                session,
                title="Intent",
                created_by="user",
            )

            membership = db.add_intent_to_portfolio(
                session,
                portfolio_id=portfolio.id,
                intent_id=intent.id,
                role="primary",
            )

            assert membership.id is not None
            assert membership.portfolio_id == portfolio.id
            assert membership.intent_id == intent.id
        finally:
            session.close()

    def test_get_portfolio_intents(self, db):
        session = db.get_session()
        try:
            portfolio = db.create_portfolio(
                session,
                name="Portfolio",
                created_by="user",
            )

            intent1 = db.create_intent(session, title="Intent 1", created_by="user")
            intent2 = db.create_intent(session, title="Intent 2", created_by="user")

            db.add_intent_to_portfolio(
                session, portfolio_id=portfolio.id, intent_id=intent1.id
            )
            db.add_intent_to_portfolio(
                session, portfolio_id=portfolio.id, intent_id=intent2.id
            )

            intents = db.get_portfolio_intents(session, portfolio.id)
            assert len(intents) == 2
        finally:
            session.close()

    def test_create_attachment(self, db):
        session = db.get_session()
        try:
            intent = db.create_intent(
                session,
                title="Attachment Test",
                created_by="user",
            )

            attachment = db.create_attachment(
                session,
                intent_id=intent.id,
                filename="test.pdf",
                mime_type="application/pdf",
                size=1024,
                storage_url="https://storage.example.com/test.pdf",
                created_by="user",
            )

            assert attachment.id is not None
            assert attachment.filename == "test.pdf"
        finally:
            session.close()

    def test_record_cost(self, db):
        session = db.get_session()
        try:
            intent = db.create_intent(
                session,
                title="Cost Test",
                created_by="user",
            )

            cost = db.record_cost(
                session,
                intent_id=intent.id,
                agent_id="agent-1",
                cost_type="tokens",
                amount=1500.0,
                unit="tokens",
                provider="openai",
            )

            assert cost.id is not None
            assert cost.amount == 1500.0
        finally:
            session.close()

    def test_set_retry_policy(self, db):
        session = db.get_session()
        try:
            intent = db.create_intent(
                session,
                title="Retry Test",
                created_by="user",
            )

            policy = db.set_retry_policy(
                session,
                intent_id=intent.id,
                strategy="exponential",
                max_retries=5,
            )

            assert policy.id is not None
            assert policy.strategy == "exponential"
            assert policy.max_retries == 5
        finally:
            session.close()

    def test_record_failure(self, db):
        session = db.get_session()
        try:
            intent = db.create_intent(
                session,
                title="Failure Test",
                created_by="user",
            )

            failure = db.record_failure(
                session,
                intent_id=intent.id,
                error_type="timeout",
                error_message="Request timed out",
                attempt_number=1,
            )

            assert failure.id is not None
            assert failure.error_type == "timeout"
        finally:
            session.close()


class TestPatchApplication:
    """Tests for state patch application."""

    @pytest.fixture
    def db(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        db = Database(f"sqlite:///{db_path}")
        db.create_tables()
        yield db

        os.unlink(db_path)

    def test_set_simple(self, db):
        result = db._apply_patches(
            {}, [{"op": "set", "path": "/key", "value": "value"}]
        )
        assert result == {"key": "value"}

    def test_set_nested(self, db):
        result = db._apply_patches({}, [{"op": "set", "path": "/a/b/c", "value": 123}])
        assert result == {"a": {"b": {"c": 123}}}

    def test_append(self, db):
        result = db._apply_patches(
            {"items": []}, [{"op": "append", "path": "/items", "value": "new"}]
        )
        assert result == {"items": ["new"]}

    def test_append_creates_array(self, db):
        result = db._apply_patches(
            {}, [{"op": "append", "path": "/items", "value": "first"}]
        )
        assert result == {"items": ["first"]}

    def test_remove(self, db):
        result = db._apply_patches({"a": 1, "b": 2}, [{"op": "remove", "path": "/a"}])
        assert result == {"b": 2}

    def test_remove_nested(self, db):
        result = db._apply_patches(
            {"a": {"b": 1, "c": 2}}, [{"op": "remove", "path": "/a/b"}]
        )
        assert result == {"a": {"c": 2}}


class TestAccessControl:
    """Tests for ACL and Access Request API endpoints (RFC-0011)."""

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
            json={"title": "ACL Test Intent", "description": "For ACL testing"},
            headers=self.HEADERS,
        )
        assert resp.status_code == 200
        return resp.json()["id"]

    def test_get_acl_empty(self, client):
        intent_id = self._create_intent(client)
        resp = client.get(
            f"/api/v1/intents/{intent_id}/acl",
            headers=self.HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["intent_id"] == intent_id
        assert data["default_policy"] == "open"
        assert data["entries"] == []

    def test_set_acl(self, client):
        intent_id = self._create_intent(client)
        resp = client.put(
            f"/api/v1/intents/{intent_id}/acl",
            json={"default_policy": "closed", "entries": []},
            headers=self.HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["intent_id"] == intent_id
        assert data["default_policy"] == "closed"

    def test_grant_access(self, client):
        intent_id = self._create_intent(client)
        resp = client.post(
            f"/api/v1/intents/{intent_id}/acl/entries",
            json={
                "principal_id": "agent-1",
                "principal_type": "agent",
                "permission": "read",
                "reason": "Needs read access",
            },
            headers=self.HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["intent_id"] == intent_id
        assert data["principal_id"] == "agent-1"
        assert data["principal_type"] == "agent"
        assert data["permission"] == "read"
        assert data["granted_by"] == self.API_KEY
        assert "id" in data

    def test_grant_access_and_get_acl(self, client):
        intent_id = self._create_intent(client)
        grant_resp = client.post(
            f"/api/v1/intents/{intent_id}/acl/entries",
            json={
                "principal_id": "agent-2",
                "principal_type": "agent",
                "permission": "write",
            },
            headers=self.HEADERS,
        )
        assert grant_resp.status_code == 200

        acl_resp = client.get(
            f"/api/v1/intents/{intent_id}/acl",
            headers=self.HEADERS,
        )
        assert acl_resp.status_code == 200
        data = acl_resp.json()
        assert len(data["entries"]) == 1
        assert data["entries"][0]["principal_id"] == "agent-2"
        assert data["entries"][0]["permission"] == "write"

    def test_revoke_access(self, client):
        intent_id = self._create_intent(client)
        grant_resp = client.post(
            f"/api/v1/intents/{intent_id}/acl/entries",
            json={
                "principal_id": "agent-revoke",
                "principal_type": "agent",
                "permission": "read",
            },
            headers=self.HEADERS,
        )
        assert grant_resp.status_code == 200
        entry_id = grant_resp.json()["id"]

        revoke_resp = client.delete(
            f"/api/v1/intents/{intent_id}/acl/entries/{entry_id}",
            headers=self.HEADERS,
        )
        assert revoke_resp.status_code == 204

    def test_revoke_nonexistent(self, client):
        intent_id = self._create_intent(client)
        resp = client.delete(
            f"/api/v1/intents/{intent_id}/acl/entries/nonexistent-entry-id",
            headers=self.HEADERS,
        )
        assert resp.status_code == 404

    def test_create_access_request(self, client):
        intent_id = self._create_intent(client)
        resp = client.post(
            f"/api/v1/intents/{intent_id}/access-requests",
            json={
                "principal_id": "agent-requester",
                "principal_type": "agent",
                "requested_permission": "write",
                "reason": "Need write access for updates",
                "capabilities": ["nlp"],
            },
            headers=self.HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["intent_id"] == intent_id
        assert data["principal_id"] == "agent-requester"
        assert data["requested_permission"] == "write"
        assert data["status"] == "pending"
        assert data["reason"] == "Need write access for updates"
        assert "id" in data

    def test_list_access_requests(self, client):
        intent_id = self._create_intent(client)
        client.post(
            f"/api/v1/intents/{intent_id}/access-requests",
            json={
                "principal_id": "agent-a",
                "principal_type": "agent",
                "requested_permission": "read",
                "reason": "reason a",
            },
            headers=self.HEADERS,
        )
        client.post(
            f"/api/v1/intents/{intent_id}/access-requests",
            json={
                "principal_id": "agent-b",
                "principal_type": "agent",
                "requested_permission": "write",
                "reason": "reason b",
            },
            headers=self.HEADERS,
        )

        resp = client.get(
            f"/api/v1/intents/{intent_id}/access-requests",
            headers=self.HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_requests" in data
        assert len(data["access_requests"]) >= 2

    def test_approve_access_request(self, client):
        intent_id = self._create_intent(client)
        req_resp = client.post(
            f"/api/v1/intents/{intent_id}/access-requests",
            json={
                "principal_id": "agent-approve",
                "principal_type": "agent",
                "requested_permission": "write",
                "reason": "Approve me",
            },
            headers=self.HEADERS,
        )
        assert req_resp.status_code == 200
        request_id = req_resp.json()["id"]

        approve_resp = client.post(
            f"/api/v1/intents/{intent_id}/access-requests/{request_id}/approve",
            json={"decided_by": "admin-user", "reason": "Approved"},
            headers=self.HEADERS,
        )
        assert approve_resp.status_code == 200
        data = approve_resp.json()
        assert data["status"] == "approved"
        assert data["decided_by"] == "admin-user"

        acl_resp = client.get(
            f"/api/v1/intents/{intent_id}/acl",
            headers=self.HEADERS,
        )
        assert acl_resp.status_code == 200
        principals = [e["principal_id"] for e in acl_resp.json()["entries"]]
        assert "agent-approve" in principals

    def test_deny_access_request(self, client):
        intent_id = self._create_intent(client)
        req_resp = client.post(
            f"/api/v1/intents/{intent_id}/access-requests",
            json={
                "principal_id": "agent-deny",
                "principal_type": "agent",
                "requested_permission": "admin",
                "reason": "Deny me",
            },
            headers=self.HEADERS,
        )
        assert req_resp.status_code == 200
        request_id = req_resp.json()["id"]

        deny_resp = client.post(
            f"/api/v1/intents/{intent_id}/access-requests/{request_id}/deny",
            json={"decided_by": "admin-user", "reason": "Not allowed"},
            headers=self.HEADERS,
        )
        assert deny_resp.status_code == 200
        data = deny_resp.json()
        assert data["status"] == "denied"
        assert data["decided_by"] == "admin-user"

    def test_approve_already_decided(self, client):
        intent_id = self._create_intent(client)
        req_resp = client.post(
            f"/api/v1/intents/{intent_id}/access-requests",
            json={
                "principal_id": "agent-double",
                "principal_type": "agent",
                "requested_permission": "read",
                "reason": "Double approve",
            },
            headers=self.HEADERS,
        )
        assert req_resp.status_code == 200
        request_id = req_resp.json()["id"]

        client.post(
            f"/api/v1/intents/{intent_id}/access-requests/{request_id}/approve",
            json={"decided_by": "admin-user"},
            headers=self.HEADERS,
        )

        second_resp = client.post(
            f"/api/v1/intents/{intent_id}/access-requests/{request_id}/approve",
            json={"decided_by": "admin-user"},
            headers=self.HEADERS,
        )
        assert second_resp.status_code == 404

    def test_acl_on_nonexistent_intent(self, client):
        resp = client.get(
            "/api/v1/intents/bad-id-does-not-exist/acl",
            headers=self.HEADERS,
        )
        assert resp.status_code == 404
