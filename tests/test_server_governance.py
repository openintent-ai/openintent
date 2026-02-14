"""
Unit tests for governance enforcement endpoints.

Tests governance policy management, approval flows,
governance enforcement (status transitions), and events.
"""

import os
import tempfile

import pytest

from openintent.server.config import ServerConfig
from openintent.server.database import Database


class TestGovernancePolicyManagement:
    """Tests for governance policy CRUD endpoints."""

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

    def _create_intent(self, client, **kwargs):
        body = {"title": "Governance Test Intent", "description": "Testing"}
        body.update(kwargs)
        resp = client.post(
            "/api/v1/intents",
            json=body,
            headers=self.HEADERS,
        )
        assert resp.status_code == 200
        return resp.json()

    def test_set_governance_policy(self, client):
        intent = self._create_intent(client)
        intent_id = intent["id"]
        version = intent["version"]

        resp = client.put(
            f"/api/v1/intents/{intent_id}/governance",
            json={"completion_mode": "require_approval", "write_scope": "any"},
            headers={**self.HEADERS, "If-Match": str(version)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["governance_policy"]["completion_mode"] == "require_approval"

    def test_get_governance_policy(self, client):
        intent = self._create_intent(client)
        intent_id = intent["id"]
        version = intent["version"]

        client.put(
            f"/api/v1/intents/{intent_id}/governance",
            json={"completion_mode": "quorum", "quorum_threshold": 0.8},
            headers={**self.HEADERS, "If-Match": str(version)},
        )

        resp = client.get(
            f"/api/v1/intents/{intent_id}/governance",
            headers=self.HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["intent_id"] == intent_id
        assert data["governance_policy"]["completion_mode"] == "quorum"
        assert data["governance_policy"]["quorum_threshold"] == 0.8
        assert "effective_policy" in data

    def test_get_governance_policy_empty(self, client):
        intent = self._create_intent(client)
        intent_id = intent["id"]

        resp = client.get(
            f"/api/v1/intents/{intent_id}/governance",
            headers=self.HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["governance_policy"] == {}
        assert data["effective_policy"]["completion_mode"] == "auto"
        assert data["effective_policy"]["write_scope"] == "any"

    def test_set_policy_invalid_completion_mode(self, client):
        intent = self._create_intent(client)
        intent_id = intent["id"]
        version = intent["version"]

        resp = client.put(
            f"/api/v1/intents/{intent_id}/governance",
            json={"completion_mode": "invalid_mode"},
            headers={**self.HEADERS, "If-Match": str(version)},
        )
        assert resp.status_code == 422

    def test_set_policy_invalid_write_scope(self, client):
        intent = self._create_intent(client)
        intent_id = intent["id"]
        version = intent["version"]

        resp = client.put(
            f"/api/v1/intents/{intent_id}/governance",
            json={"write_scope": "nobody"},
            headers={**self.HEADERS, "If-Match": str(version)},
        )
        assert resp.status_code == 422

    def test_set_policy_invalid_quorum_threshold_zero(self, client):
        intent = self._create_intent(client)
        intent_id = intent["id"]
        version = intent["version"]

        resp = client.put(
            f"/api/v1/intents/{intent_id}/governance",
            json={"quorum_threshold": 0},
            headers={**self.HEADERS, "If-Match": str(version)},
        )
        assert resp.status_code == 422

    def test_set_policy_invalid_quorum_threshold_above_one(self, client):
        intent = self._create_intent(client)
        intent_id = intent["id"]
        version = intent["version"]

        resp = client.put(
            f"/api/v1/intents/{intent_id}/governance",
            json={"quorum_threshold": 1.5},
            headers={**self.HEADERS, "If-Match": str(version)},
        )
        assert resp.status_code == 422

    def test_set_policy_invalid_quorum_threshold_negative(self, client):
        intent = self._create_intent(client)
        intent_id = intent["id"]
        version = intent["version"]

        resp = client.put(
            f"/api/v1/intents/{intent_id}/governance",
            json={"quorum_threshold": -0.5},
            headers={**self.HEADERS, "If-Match": str(version)},
        )
        assert resp.status_code == 422

    def test_set_policy_without_if_match_header(self, client):
        intent = self._create_intent(client)
        intent_id = intent["id"]

        resp = client.put(
            f"/api/v1/intents/{intent_id}/governance",
            json={"completion_mode": "auto"},
            headers=self.HEADERS,
        )
        assert resp.status_code == 400

    def test_set_policy_version_conflict(self, client):
        intent = self._create_intent(client)
        intent_id = intent["id"]

        resp = client.put(
            f"/api/v1/intents/{intent_id}/governance",
            json={"completion_mode": "auto"},
            headers={**self.HEADERS, "If-Match": "999"},
        )
        assert resp.status_code == 409

    def test_set_policy_valid_quorum_threshold(self, client):
        intent = self._create_intent(client)
        intent_id = intent["id"]
        version = intent["version"]

        resp = client.put(
            f"/api/v1/intents/{intent_id}/governance",
            json={
                "completion_mode": "quorum",
                "quorum_threshold": 0.5,
            },
            headers={**self.HEADERS, "If-Match": str(version)},
        )
        assert resp.status_code == 200

    def test_set_policy_with_max_cost(self, client):
        intent = self._create_intent(client)
        intent_id = intent["id"]
        version = intent["version"]

        resp = client.put(
            f"/api/v1/intents/{intent_id}/governance",
            json={"max_cost": 100.0},
            headers={**self.HEADERS, "If-Match": str(version)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["governance_policy"]["max_cost"] == 100.0


class TestApprovalFlow:
    """Tests for approval request creation, retrieval, approve, and deny."""

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
            json={"title": "Approval Test Intent", "description": "Testing"},
            headers=self.HEADERS,
        )
        assert resp.status_code == 200
        return resp.json()

    def _create_approval(self, client, intent_id):
        resp = client.post(
            f"/api/v1/intents/{intent_id}/approvals",
            json={
                "requested_by": "agent-1",
                "action": "complete",
                "reason": "done",
            },
            headers=self.HEADERS,
        )
        assert resp.status_code == 200
        return resp.json()

    def test_create_approval_request(self, client):
        intent = self._create_intent(client)
        intent_id = intent["id"]

        resp = client.post(
            f"/api/v1/intents/{intent_id}/approvals",
            json={
                "requested_by": "agent-1",
                "action": "complete",
                "reason": "done",
            },
            headers=self.HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["intent_id"] == intent_id
        assert data["requested_by"] == "agent-1"
        assert data["action"] == "complete"
        assert data["reason"] == "done"
        assert data["status"] == "pending"
        assert "id" in data

    def test_create_approval_with_context(self, client):
        intent = self._create_intent(client)
        intent_id = intent["id"]

        resp = client.post(
            f"/api/v1/intents/{intent_id}/approvals",
            json={
                "requested_by": "agent-2",
                "action": "complete",
                "reason": "all tasks finished",
                "context": {"progress": 1.0},
            },
            headers=self.HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["context"] == {"progress": 1.0}

    def test_get_approval_status(self, client):
        intent = self._create_intent(client)
        intent_id = intent["id"]
        approval = self._create_approval(client, intent_id)
        approval_id = approval["id"]

        resp = client.get(
            f"/api/v1/intents/{intent_id}/approvals/{approval_id}",
            headers=self.HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == approval_id
        assert data["status"] == "pending"

    def test_approve_approval(self, client):
        intent = self._create_intent(client)
        intent_id = intent["id"]
        approval = self._create_approval(client, intent_id)
        approval_id = approval["id"]

        resp = client.post(
            f"/api/v1/intents/{intent_id}/approvals/{approval_id}/approve",
            headers=self.HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "approved"
        assert data["decided_by"] == self.API_KEY

    def test_deny_approval(self, client):
        intent = self._create_intent(client)
        intent_id = intent["id"]
        approval = self._create_approval(client, intent_id)
        approval_id = approval["id"]

        resp = client.post(
            f"/api/v1/intents/{intent_id}/approvals/{approval_id}/deny",
            headers=self.HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "denied"
        assert data["decided_by"] == self.API_KEY

    def test_double_approve(self, client):
        intent = self._create_intent(client)
        intent_id = intent["id"]
        approval = self._create_approval(client, intent_id)
        approval_id = approval["id"]

        client.post(
            f"/api/v1/intents/{intent_id}/approvals/{approval_id}/approve",
            headers=self.HEADERS,
        )

        resp = client.post(
            f"/api/v1/intents/{intent_id}/approvals/{approval_id}/approve",
            headers=self.HEADERS,
        )
        assert resp.status_code == 409

    def test_double_deny(self, client):
        intent = self._create_intent(client)
        intent_id = intent["id"]
        approval = self._create_approval(client, intent_id)
        approval_id = approval["id"]

        client.post(
            f"/api/v1/intents/{intent_id}/approvals/{approval_id}/deny",
            headers=self.HEADERS,
        )

        resp = client.post(
            f"/api/v1/intents/{intent_id}/approvals/{approval_id}/deny",
            headers=self.HEADERS,
        )
        assert resp.status_code == 409

    def test_approve_then_deny(self, client):
        intent = self._create_intent(client)
        intent_id = intent["id"]
        approval = self._create_approval(client, intent_id)
        approval_id = approval["id"]

        client.post(
            f"/api/v1/intents/{intent_id}/approvals/{approval_id}/approve",
            headers=self.HEADERS,
        )

        resp = client.post(
            f"/api/v1/intents/{intent_id}/approvals/{approval_id}/deny",
            headers=self.HEADERS,
        )
        assert resp.status_code == 409

    def test_get_nonexistent_approval(self, client):
        intent = self._create_intent(client)
        intent_id = intent["id"]

        resp = client.get(
            f"/api/v1/intents/{intent_id}/approvals/nonexistent-id",
            headers=self.HEADERS,
        )
        assert resp.status_code == 404


class TestGovernanceEnforcement:
    """Tests for governance enforcement on status transitions and cost limits."""

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

    def _create_intent(self, client, **kwargs):
        body = {"title": "Enforcement Test", "description": "Testing"}
        body.update(kwargs)
        resp = client.post(
            "/api/v1/intents",
            json=body,
            headers=self.HEADERS,
        )
        assert resp.status_code == 200
        return resp.json()

    def test_completion_blocked_without_approval(self, client):
        intent = self._create_intent(
            client,
            governance_policy={
                "completion_mode": "require_approval",
                "write_scope": "any",
            },
        )
        intent_id = intent["id"]
        version = intent["version"]

        resp = client.post(
            f"/api/v1/intents/{intent_id}/status",
            json={"status": "completed"},
            headers={**self.HEADERS, "If-Match": str(version)},
        )
        assert resp.status_code == 403
        detail = resp.json()["detail"]
        assert detail["error"] == "governance_violation"
        assert detail["rule"] == "completion_mode"

    def test_completion_allowed_after_approval(self, client):
        intent = self._create_intent(
            client,
            governance_policy={
                "completion_mode": "require_approval",
                "write_scope": "any",
            },
        )
        intent_id = intent["id"]
        version = intent["version"]

        approval_resp = client.post(
            f"/api/v1/intents/{intent_id}/approvals",
            json={
                "requested_by": "agent-1",
                "action": "complete",
                "reason": "done",
            },
            headers=self.HEADERS,
        )
        approval_id = approval_resp.json()["id"]

        client.post(
            f"/api/v1/intents/{intent_id}/approvals/{approval_id}/approve",
            headers=self.HEADERS,
        )

        resp = client.post(
            f"/api/v1/intents/{intent_id}/status",
            json={"status": "completed"},
            headers={**self.HEADERS, "If-Match": str(version)},
        )
        assert resp.status_code == 200

    def test_write_scope_assigned_only_blocks_unassigned(self, client):
        intent = self._create_intent(
            client,
            governance_policy={
                "completion_mode": "auto",
                "write_scope": "assigned_only",
            },
        )
        intent_id = intent["id"]
        version = intent["version"]

        resp = client.post(
            f"/api/v1/intents/{intent_id}/status",
            json={"status": "active"},
            headers={**self.HEADERS, "If-Match": str(version)},
        )
        assert resp.status_code == 403
        detail = resp.json()["detail"]
        assert detail["error"] == "governance_violation"
        assert detail["rule"] == "write_scope"

    def test_max_cost_enforcement(self, client):
        intent = self._create_intent(
            client,
            governance_policy={"max_cost": 50.0, "write_scope": "any"},
        )
        intent_id = intent["id"]

        resp1 = client.post(
            f"/api/v1/intents/{intent_id}/costs",
            json={
                "agent_id": "agent-1",
                "cost_type": "tokens",
                "amount": 30.0,
                "unit": "tokens",
                "provider": "openai",
            },
            headers=self.HEADERS,
        )
        assert resp1.status_code == 200

        resp2 = client.post(
            f"/api/v1/intents/{intent_id}/costs",
            json={
                "agent_id": "agent-1",
                "cost_type": "tokens",
                "amount": 25.0,
                "unit": "tokens",
                "provider": "openai",
            },
            headers=self.HEADERS,
        )
        assert resp2.status_code == 403
        detail = resp2.json()["detail"]
        assert detail["error"] == "governance_violation"
        assert detail["rule"] == "max_cost"

    def test_max_cost_allows_within_budget(self, client):
        intent = self._create_intent(
            client,
            governance_policy={"max_cost": 100.0, "write_scope": "any"},
        )
        intent_id = intent["id"]

        resp = client.post(
            f"/api/v1/intents/{intent_id}/costs",
            json={
                "agent_id": "agent-1",
                "cost_type": "tokens",
                "amount": 50.0,
                "unit": "tokens",
            },
            headers=self.HEADERS,
        )
        assert resp.status_code == 200

    def test_non_completed_status_not_blocked_by_require_approval(self, client):
        intent = self._create_intent(
            client,
            governance_policy={
                "completion_mode": "require_approval",
                "write_scope": "any",
            },
        )
        intent_id = intent["id"]
        version = intent["version"]

        resp = client.post(
            f"/api/v1/intents/{intent_id}/status",
            json={"status": "active"},
            headers={**self.HEADERS, "If-Match": str(version)},
        )
        assert resp.status_code == 200


class TestGovernanceEvents:
    """Tests for governance-related event creation."""

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

    def _create_intent(self, client, **kwargs):
        body = {"title": "Events Test", "description": "Testing"}
        body.update(kwargs)
        resp = client.post(
            "/api/v1/intents",
            json=body,
            headers=self.HEADERS,
        )
        assert resp.status_code == 200
        return resp.json()

    def _create_approval(self, client, intent_id):
        resp = client.post(
            f"/api/v1/intents/{intent_id}/approvals",
            json={
                "requested_by": "agent-1",
                "action": "complete",
                "reason": "done",
            },
            headers=self.HEADERS,
        )
        assert resp.status_code == 200
        return resp.json()

    def _get_events(self, client, intent_id):
        resp = client.get(
            f"/api/v1/intents/{intent_id}/events",
            headers=self.HEADERS,
        )
        assert resp.status_code == 200
        return resp.json()

    def test_policy_set_event(self, client):
        intent = self._create_intent(client)
        intent_id = intent["id"]
        version = intent["version"]

        client.put(
            f"/api/v1/intents/{intent_id}/governance",
            json={"completion_mode": "require_approval"},
            headers={**self.HEADERS, "If-Match": str(version)},
        )

        events = self._get_events(client, intent_id)
        policy_events = [
            e for e in events if e["event_type"] == "governance.policy_set"
        ]
        assert len(policy_events) >= 1
        assert (
            policy_events[0]["payload"]["governance_policy"]["completion_mode"]
            == "require_approval"
        )

    def test_approval_granted_event(self, client):
        intent = self._create_intent(client)
        intent_id = intent["id"]
        approval = self._create_approval(client, intent_id)
        approval_id = approval["id"]

        client.post(
            f"/api/v1/intents/{intent_id}/approvals/{approval_id}/approve",
            headers=self.HEADERS,
        )

        events = self._get_events(client, intent_id)
        granted_events = [
            e for e in events if e["event_type"] == "governance.approval_granted"
        ]
        assert len(granted_events) >= 1
        assert granted_events[0]["payload"]["approval_id"] == approval_id
        assert granted_events[0]["payload"]["decision"] == "approved"

    def test_approval_denied_event(self, client):
        intent = self._create_intent(client)
        intent_id = intent["id"]
        approval = self._create_approval(client, intent_id)
        approval_id = approval["id"]

        client.post(
            f"/api/v1/intents/{intent_id}/approvals/{approval_id}/deny",
            headers=self.HEADERS,
        )

        events = self._get_events(client, intent_id)
        denied_events = [
            e for e in events if e["event_type"] == "governance.approval_denied"
        ]
        assert len(denied_events) >= 1
        assert denied_events[0]["payload"]["approval_id"] == approval_id
        assert denied_events[0]["payload"]["decision"] == "denied"

    def test_governance_violation_event_on_blocked_completion(self, client):
        intent = self._create_intent(
            client,
            governance_policy={
                "completion_mode": "require_approval",
                "write_scope": "any",
            },
        )
        intent_id = intent["id"]
        version = intent["version"]

        client.post(
            f"/api/v1/intents/{intent_id}/status",
            json={"status": "completed"},
            headers={**self.HEADERS, "If-Match": str(version)},
        )

        events = self._get_events(client, intent_id)
        violation_events = [
            e for e in events if e["event_type"] == "governance.violation"
        ]
        assert len(violation_events) >= 1
        assert violation_events[0]["payload"]["rule"] == "completion_mode"
