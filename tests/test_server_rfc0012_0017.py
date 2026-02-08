"""
Tests for OpenIntent server - RFCs 0012-0017 database operations and API endpoints.
"""

import os
import tempfile

import pytest

from openintent.server.config import ServerConfig
from openintent.server.database import Database


class TestDatabaseRFC0012:
    """Tests for RFC-0012 Task Decomposition & Planning database operations."""

    @pytest.fixture
    def db(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        db = Database(f"sqlite:///{db_path}")
        db.create_tables()
        yield db
        os.unlink(db_path)

    def _create_test_intent(self, db):
        """Helper to create a test intent."""
        session = db.get_session()
        try:
            intent = db.create_intent(session, title="Test", description="Test intent", created_by="agent-1")
            return intent.id
        finally:
            session.close()

    def test_create_task(self, db):
        intent_id = self._create_test_intent(db)
        session = db.get_session()
        try:
            task = db.create_task(session, intent_id=intent_id, name="Research")
            assert task.id is not None
            assert task.name == "Research"
            assert task.status == "pending"
            assert task.version == 1
        finally:
            session.close()

    def test_get_task(self, db):
        intent_id = self._create_test_intent(db)
        session = db.get_session()
        try:
            task = db.create_task(session, intent_id=intent_id, name="Research")
            found = db.get_task(session, task.id)
            assert found is not None
            assert found.name == "Research"
        finally:
            session.close()

    def test_get_task_not_found(self, db):
        session = db.get_session()
        try:
            assert db.get_task(session, "nonexistent") is None
        finally:
            session.close()

    def test_list_tasks(self, db):
        intent_id = self._create_test_intent(db)
        session = db.get_session()
        try:
            db.create_task(session, intent_id=intent_id, name="Task 1")
            db.create_task(session, intent_id=intent_id, name="Task 2")
            tasks = db.list_tasks(session, intent_id)
            assert len(tasks) == 2
        finally:
            session.close()

    def test_list_tasks_with_status_filter(self, db):
        intent_id = self._create_test_intent(db)
        session = db.get_session()
        try:
            db.create_task(session, intent_id=intent_id, name="Task 1")
            t2 = db.create_task(session, intent_id=intent_id, name="Task 2")
            db.update_task_status(session, t2.id, t2.version, "running")
            tasks = db.list_tasks(session, intent_id, status="running")
            assert len(tasks) == 1
            assert tasks[0].name == "Task 2"
        finally:
            session.close()

    def test_update_task_status(self, db):
        intent_id = self._create_test_intent(db)
        session = db.get_session()
        try:
            task = db.create_task(session, intent_id=intent_id, name="Task 1")
            updated = db.update_task_status(session, task.id, task.version, "running")
            assert updated is not None
            assert updated.status == "running"
            assert updated.version == 2
        finally:
            session.close()

    def test_update_task_status_version_conflict(self, db):
        intent_id = self._create_test_intent(db)
        session = db.get_session()
        try:
            task = db.create_task(session, intent_id=intent_id, name="Task 1")
            db.update_task_status(session, task.id, task.version, "running")
            result = db.update_task_status(session, task.id, 1, "completed")
            assert result is None
        finally:
            session.close()

    def test_create_plan(self, db):
        intent_id = self._create_test_intent(db)
        session = db.get_session()
        try:
            plan = db.create_plan(session, intent_id=intent_id)
            assert plan.id is not None
            assert plan.state == "draft"
            assert plan.version == 1
        finally:
            session.close()

    def test_get_plan(self, db):
        intent_id = self._create_test_intent(db)
        session = db.get_session()
        try:
            plan = db.create_plan(session, intent_id=intent_id, tasks=["t1", "t2"])
            found = db.get_plan(session, plan.id)
            assert found is not None
            assert found.tasks == ["t1", "t2"]
        finally:
            session.close()

    def test_list_plans(self, db):
        intent_id = self._create_test_intent(db)
        session = db.get_session()
        try:
            db.create_plan(session, intent_id=intent_id)
            db.create_plan(session, intent_id=intent_id)
            plans = db.list_plans(session, intent_id)
            assert len(plans) == 2
        finally:
            session.close()

    def test_update_plan(self, db):
        intent_id = self._create_test_intent(db)
        session = db.get_session()
        try:
            plan = db.create_plan(session, intent_id=intent_id)
            updated = db.update_plan(session, plan.id, plan.version, state="active")
            assert updated is not None
            assert updated.state == "active"
            assert updated.version == 2
        finally:
            session.close()


class TestDatabaseRFC0013:
    """Tests for RFC-0013 Coordinator Governance database operations."""

    @pytest.fixture
    def db(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        db = Database(f"sqlite:///{db_path}")
        db.create_tables()
        yield db
        os.unlink(db_path)

    def _create_test_intent(self, db):
        session = db.get_session()
        try:
            intent = db.create_intent(session, title="Test", description="Test", created_by="agent-1")
            return intent.id
        finally:
            session.close()

    def test_create_coordinator_lease(self, db):
        intent_id = self._create_test_intent(db)
        session = db.get_session()
        try:
            lease = db.create_coordinator_lease(session, agent_id="coordinator-1", intent_id=intent_id)
            assert lease.id is not None
            assert lease.agent_id == "coordinator-1"
            assert lease.status == "active"
        finally:
            session.close()

    def test_get_coordinator_lease(self, db):
        intent_id = self._create_test_intent(db)
        session = db.get_session()
        try:
            lease = db.create_coordinator_lease(session, agent_id="coordinator-1", intent_id=intent_id)
            found = db.get_coordinator_lease(session, lease.id)
            assert found is not None
            assert found.agent_id == "coordinator-1"
        finally:
            session.close()

    def test_list_coordinator_leases(self, db):
        intent_id = self._create_test_intent(db)
        session = db.get_session()
        try:
            db.create_coordinator_lease(session, agent_id="c-1", intent_id=intent_id)
            db.create_coordinator_lease(session, agent_id="c-2", intent_id=intent_id)
            leases = db.list_coordinator_leases(session, intent_id=intent_id)
            assert len(leases) == 2
        finally:
            session.close()

    def test_update_coordinator_heartbeat(self, db):
        intent_id = self._create_test_intent(db)
        session = db.get_session()
        try:
            lease = db.create_coordinator_lease(session, agent_id="coordinator-1", intent_id=intent_id)
            updated = db.update_coordinator_heartbeat(session, lease.id, "coordinator-1")
            assert updated is not None
            assert updated.last_heartbeat is not None
        finally:
            session.close()

    def test_create_decision_record(self, db):
        session = db.get_session()
        try:
            record = db.create_decision_record(
                session,
                coordinator_id="c-1",
                intent_id="i-1",
                decision_type="assignment",
                summary="Assigned task to agent",
                rationale="Best fit based on capabilities",
            )
            assert record.id is not None
            assert record.decision_type == "assignment"
        finally:
            session.close()

    def test_list_decision_records(self, db):
        session = db.get_session()
        try:
            db.create_decision_record(session, coordinator_id="c-1", intent_id="i-1", decision_type="assignment", summary="D1", rationale="R1")
            db.create_decision_record(session, coordinator_id="c-1", intent_id="i-1", decision_type="escalation", summary="D2", rationale="R2")
            records = db.list_decision_records(session, "i-1")
            assert len(records) == 2
        finally:
            session.close()


class TestDatabaseRFC0014:
    """Tests for RFC-0014 Credential Vaults & Tool Scoping database operations."""

    @pytest.fixture
    def db(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        db = Database(f"sqlite:///{db_path}")
        db.create_tables()
        yield db
        os.unlink(db_path)

    def test_create_vault(self, db):
        session = db.get_session()
        try:
            vault = db.create_vault(session, owner_id="user-1", name="My Vault")
            assert vault.id is not None
            assert vault.name == "My Vault"
        finally:
            session.close()

    def test_get_vault(self, db):
        session = db.get_session()
        try:
            vault = db.create_vault(session, owner_id="user-1", name="Vault")
            found = db.get_vault(session, vault.id)
            assert found is not None
            assert found.owner_id == "user-1"
        finally:
            session.close()

    def test_create_credential(self, db):
        session = db.get_session()
        try:
            vault = db.create_vault(session, owner_id="user-1", name="Vault")
            cred = db.create_credential(session, vault_id=vault.id, service="openai", label="GPT-4 Key", auth_type="api_key")
            assert cred.id is not None
            assert cred.service == "openai"
            assert cred.status == "active"
        finally:
            session.close()

    def test_get_credential(self, db):
        session = db.get_session()
        try:
            vault = db.create_vault(session, owner_id="user-1", name="Vault")
            cred = db.create_credential(session, vault_id=vault.id, service="openai", label="Key", auth_type="api_key")
            found = db.get_credential(session, cred.id)
            assert found is not None
            assert found.service == "openai"
        finally:
            session.close()

    def test_create_tool_grant(self, db):
        session = db.get_session()
        try:
            vault = db.create_vault(session, owner_id="user-1", name="Vault")
            cred = db.create_credential(session, vault_id=vault.id, service="openai", label="Key", auth_type="api_key")
            grant = db.create_tool_grant(session, credential_id=cred.id, agent_id="agent-1", granted_by="admin", scopes=["chat"])
            assert grant.id is not None
            assert grant.scopes == ["chat"]
            assert grant.status == "active"
        finally:
            session.close()

    def test_list_agent_grants(self, db):
        session = db.get_session()
        try:
            vault = db.create_vault(session, owner_id="user-1", name="Vault")
            cred = db.create_credential(session, vault_id=vault.id, service="openai", label="Key", auth_type="api_key")
            db.create_tool_grant(session, credential_id=cred.id, agent_id="agent-1", granted_by="admin")
            db.create_tool_grant(session, credential_id=cred.id, agent_id="agent-1", granted_by="admin")
            grants = db.list_agent_grants(session, "agent-1")
            assert len(grants) == 2
        finally:
            session.close()

    def test_revoke_grant(self, db):
        session = db.get_session()
        try:
            vault = db.create_vault(session, owner_id="user-1", name="Vault")
            cred = db.create_credential(session, vault_id=vault.id, service="openai", label="Key", auth_type="api_key")
            grant = db.create_tool_grant(session, credential_id=cred.id, agent_id="agent-1", granted_by="admin")
            revoked = db.revoke_grant(session, grant.id)
            assert revoked is not None
            assert revoked.status == "revoked"
        finally:
            session.close()

    def test_create_tool_invocation(self, db):
        session = db.get_session()
        try:
            vault = db.create_vault(session, owner_id="user-1", name="Vault")
            cred = db.create_credential(session, vault_id=vault.id, service="openai", label="Key", auth_type="api_key")
            grant = db.create_tool_grant(session, credential_id=cred.id, agent_id="agent-1", granted_by="admin")
            inv = db.create_tool_invocation(session, grant_id=grant.id, service="openai", tool="chat", agent_id="agent-1")
            assert inv.id is not None
            assert inv.service == "openai"
        finally:
            session.close()

    def test_list_tool_invocations(self, db):
        session = db.get_session()
        try:
            vault = db.create_vault(session, owner_id="user-1", name="Vault")
            cred = db.create_credential(session, vault_id=vault.id, service="openai", label="Key", auth_type="api_key")
            grant = db.create_tool_grant(session, credential_id=cred.id, agent_id="agent-1", granted_by="admin")
            db.create_tool_invocation(session, grant_id=grant.id, service="openai", tool="chat", agent_id="agent-1")
            db.create_tool_invocation(session, grant_id=grant.id, service="openai", tool="embed", agent_id="agent-1")
            invocations = db.list_tool_invocations(session, grant.id)
            assert len(invocations) == 2
        finally:
            session.close()


class TestDatabaseRFC0015:
    """Tests for RFC-0015 Agent Memory database operations."""

    @pytest.fixture
    def db(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        db = Database(f"sqlite:///{db_path}")
        db.create_tables()
        yield db
        os.unlink(db_path)

    def test_create_memory_entry(self, db):
        session = db.get_session()
        try:
            entry = db.create_memory_entry(session, agent_id="agent-1", namespace="default", key="greeting", value={"text": "hello"}, memory_type="working")
            assert entry.id is not None
            assert entry.key == "greeting"
            assert entry.version == 1
        finally:
            session.close()

    def test_get_memory_entry(self, db):
        session = db.get_session()
        try:
            entry = db.create_memory_entry(session, agent_id="agent-1", namespace="default", key="k", value={"v": 1}, memory_type="working")
            found = db.get_memory_entry(session, entry.id)
            assert found is not None
            assert found.value == {"v": 1}
        finally:
            session.close()

    def test_list_memory_entries(self, db):
        session = db.get_session()
        try:
            db.create_memory_entry(session, agent_id="agent-1", namespace="ns1", key="k1", value={}, memory_type="working")
            db.create_memory_entry(session, agent_id="agent-1", namespace="ns2", key="k2", value={}, memory_type="episodic")
            entries = db.list_memory_entries(session, "agent-1")
            assert len(entries) == 2
        finally:
            session.close()

    def test_list_memory_entries_with_namespace_filter(self, db):
        session = db.get_session()
        try:
            db.create_memory_entry(session, agent_id="agent-1", namespace="ns1", key="k1", value={}, memory_type="working")
            db.create_memory_entry(session, agent_id="agent-1", namespace="ns2", key="k2", value={}, memory_type="episodic")
            entries = db.list_memory_entries(session, "agent-1", namespace="ns1")
            assert len(entries) == 1
            assert entries[0].namespace == "ns1"
        finally:
            session.close()

    def test_update_memory_entry(self, db):
        session = db.get_session()
        try:
            entry = db.create_memory_entry(session, agent_id="agent-1", namespace="default", key="k", value={"old": True}, memory_type="working")
            updated = db.update_memory_entry(session, entry.id, entry.version, value={"new": True})
            assert updated is not None
            assert updated.value == {"new": True}
            assert updated.version == 2
        finally:
            session.close()

    def test_update_memory_entry_version_conflict(self, db):
        session = db.get_session()
        try:
            entry = db.create_memory_entry(session, agent_id="agent-1", namespace="default", key="k", value={}, memory_type="working")
            db.update_memory_entry(session, entry.id, entry.version, value={"v": 1})
            result = db.update_memory_entry(session, entry.id, 1, value={"v": 2})
            assert result is None
        finally:
            session.close()

    def test_delete_memory_entry(self, db):
        session = db.get_session()
        try:
            entry = db.create_memory_entry(session, agent_id="agent-1", namespace="default", key="k", value={}, memory_type="working")
            assert db.delete_memory_entry(session, entry.id) is True
            assert db.get_memory_entry(session, entry.id) is None
        finally:
            session.close()

    def test_delete_memory_entry_not_found(self, db):
        session = db.get_session()
        try:
            assert db.delete_memory_entry(session, "nonexistent") is False
        finally:
            session.close()


class TestDatabaseRFC0016:
    """Tests for RFC-0016 Agent Lifecycle database operations."""

    @pytest.fixture
    def db(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        db = Database(f"sqlite:///{db_path}")
        db.create_tables()
        yield db
        os.unlink(db_path)

    def test_register_agent(self, db):
        session = db.get_session()
        try:
            agent = db.register_agent(session, agent_id="agent-1", capabilities=["research", "code"])
            assert agent.agent_id == "agent-1"
            assert agent.status == "active"
            assert agent.capabilities == ["research", "code"]
        finally:
            session.close()

    def test_get_agent_record(self, db):
        session = db.get_session()
        try:
            db.register_agent(session, agent_id="agent-1")
            found = db.get_agent_record(session, "agent-1")
            assert found is not None
            assert found.agent_id == "agent-1"
        finally:
            session.close()

    def test_get_agent_record_not_found(self, db):
        session = db.get_session()
        try:
            assert db.get_agent_record(session, "nonexistent") is None
        finally:
            session.close()

    def test_list_agent_records(self, db):
        session = db.get_session()
        try:
            db.register_agent(session, agent_id="agent-1")
            db.register_agent(session, agent_id="agent-2")
            agents = db.list_agent_records(session)
            assert len(agents) == 2
        finally:
            session.close()

    def test_list_agent_records_with_status_filter(self, db):
        session = db.get_session()
        try:
            db.register_agent(session, agent_id="agent-1")
            db.register_agent(session, agent_id="agent-2")
            db.update_agent_status(session, "agent-2", "draining")
            agents = db.list_agent_records(session, status="active")
            assert len(agents) == 1
            assert agents[0].agent_id == "agent-1"
        finally:
            session.close()

    def test_update_agent_heartbeat(self, db):
        session = db.get_session()
        try:
            db.register_agent(session, agent_id="agent-1")
            updated = db.update_agent_heartbeat(session, "agent-1")
            assert updated is not None
            assert updated.last_heartbeat_at is not None
        finally:
            session.close()

    def test_update_agent_status(self, db):
        session = db.get_session()
        try:
            db.register_agent(session, agent_id="agent-1")
            updated = db.update_agent_status(session, "agent-1", "draining")
            assert updated is not None
            assert updated.status == "draining"
        finally:
            session.close()


class TestDatabaseRFC0017:
    """Tests for RFC-0017 Triggers database operations."""

    @pytest.fixture
    def db(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        db = Database(f"sqlite:///{db_path}")
        db.create_tables()
        yield db
        os.unlink(db_path)

    def test_create_trigger(self, db):
        session = db.get_session()
        try:
            trigger = db.create_trigger(session, name="Daily Report", type="schedule")
            assert trigger.trigger_id is not None
            assert trigger.name == "Daily Report"
            assert trigger.enabled is True
            assert trigger.fire_count == 0
        finally:
            session.close()

    def test_get_trigger(self, db):
        session = db.get_session()
        try:
            trigger = db.create_trigger(session, name="Report", type="schedule")
            found = db.get_trigger(session, trigger.trigger_id)
            assert found is not None
            assert found.name == "Report"
        finally:
            session.close()

    def test_list_triggers(self, db):
        session = db.get_session()
        try:
            db.create_trigger(session, name="T1", type="schedule")
            db.create_trigger(session, name="T2", type="event")
            triggers = db.list_triggers(session)
            assert len(triggers) == 2
        finally:
            session.close()

    def test_list_triggers_with_type_filter(self, db):
        session = db.get_session()
        try:
            db.create_trigger(session, name="T1", type="schedule")
            db.create_trigger(session, name="T2", type="event")
            triggers = db.list_triggers(session, trigger_type="event")
            assert len(triggers) == 1
            assert triggers[0].name == "T2"
        finally:
            session.close()

    def test_update_trigger(self, db):
        session = db.get_session()
        try:
            trigger = db.create_trigger(session, name="T1", type="schedule")
            updated = db.update_trigger(session, trigger.trigger_id, trigger.version, enabled=False)
            assert updated is not None
            assert updated.enabled is False
            assert updated.version == 2
        finally:
            session.close()

    def test_update_trigger_version_conflict(self, db):
        session = db.get_session()
        try:
            trigger = db.create_trigger(session, name="T1", type="schedule")
            db.update_trigger(session, trigger.trigger_id, trigger.version, enabled=False)
            result = db.update_trigger(session, trigger.trigger_id, 1, enabled=True)
            assert result is None
        finally:
            session.close()

    def test_fire_trigger(self, db):
        session = db.get_session()
        try:
            trigger = db.create_trigger(session, name="T1", type="schedule")
            fired = db.fire_trigger(session, trigger.trigger_id)
            assert fired is not None
            assert fired.fire_count == 1
            assert fired.last_fired_at is not None
            fired2 = db.fire_trigger(session, trigger.trigger_id)
            assert fired2.fire_count == 2
        finally:
            session.close()

    def test_delete_trigger(self, db):
        session = db.get_session()
        try:
            trigger = db.create_trigger(session, name="T1", type="schedule")
            assert db.delete_trigger(session, trigger.trigger_id) is True
            assert db.get_trigger(session, trigger.trigger_id) is None
        finally:
            session.close()

    def test_delete_trigger_not_found(self, db):
        session = db.get_session()
        try:
            assert db.delete_trigger(session, "nonexistent") is False
        finally:
            session.close()
