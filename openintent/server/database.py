"""
Database layer for OpenIntent server using SQLAlchemy.
Supports SQLite (default) and PostgreSQL.
"""

# mypy: disable-error-code="assignment"

from datetime import datetime, timedelta
from typing import Dict, List, Optional
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    create_engine,
    desc,
)
from sqlalchemy.orm import Session, declarative_base, relationship, sessionmaker
from sqlalchemy.pool import StaticPool

Base = declarative_base()


class IntentModel(Base):  # type: ignore[misc, valid-type]
    __tablename__ = "intents"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    title = Column(String(255), nullable=False)
    description = Column(Text, default="")
    created_by = Column(String(255), nullable=False)
    parent_id = Column(String(36), ForeignKey("intents.id"), nullable=True)
    depends_on = Column(JSON, default=list)
    constraints = Column(JSON, default=dict)
    state = Column(JSON, default=dict)
    status = Column(String(50), default="draft")
    confidence = Column(Float, default=0.0)
    version = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    events = relationship(
        "IntentEventModel", back_populates="intent", cascade="all, delete-orphan"
    )
    agents = relationship(
        "IntentAgentModel", back_populates="intent", cascade="all, delete-orphan"
    )
    leases = relationship(
        "IntentLeaseModel", back_populates="intent", cascade="all, delete-orphan"
    )
    attachments = relationship(
        "IntentAttachmentModel", back_populates="intent", cascade="all, delete-orphan"
    )
    costs = relationship(
        "IntentCostModel", back_populates="intent", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("idx_intents_parent_id", "parent_id"),)


class IntentEventModel(Base):  # type: ignore[misc, valid-type]
    __tablename__ = "intent_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    intent_id = Column(String(36), ForeignKey("intents.id"), nullable=False)
    event_type = Column(String(100), nullable=False)
    actor = Column(String(255), nullable=False)
    payload = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

    intent = relationship("IntentModel", back_populates="events")

    __table_args__ = (Index("idx_intent_events_intent_id", "intent_id"),)


class IntentAgentModel(Base):  # type: ignore[misc, valid-type]
    __tablename__ = "intent_agents"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    intent_id = Column(String(36), ForeignKey("intents.id"), nullable=False)
    agent_id = Column(String(255), nullable=False)
    role = Column(String(100), default="worker")
    assigned_at = Column(DateTime, default=datetime.utcnow)

    intent = relationship("IntentModel", back_populates="agents")

    __table_args__ = (
        Index("idx_intent_agents_intent_id", "intent_id"),
        Index("idx_intent_agents_agent_id", "agent_id"),
    )


class IntentLeaseModel(Base):  # type: ignore[misc, valid-type]
    __tablename__ = "intent_leases"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    intent_id = Column(String(36), ForeignKey("intents.id"), nullable=False)
    agent_id = Column(String(255), nullable=False)
    scope = Column(String(255), nullable=False)
    acquired_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    released_at = Column(DateTime, nullable=True)

    intent = relationship("IntentModel", back_populates="leases")

    __table_args__ = (Index("idx_intent_leases_intent_scope", "intent_id", "scope"),)


class PortfolioModel(Base):  # type: ignore[misc, valid-type]
    __tablename__ = "portfolios"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name = Column(String(255), nullable=False)
    description = Column(Text, default="")
    created_by = Column(String(255), nullable=False)
    status = Column(String(50), default="active")
    governance_policy = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    memberships = relationship(
        "PortfolioMembershipModel",
        back_populates="portfolio",
        cascade="all, delete-orphan",
    )


class PortfolioMembershipModel(Base):  # type: ignore[misc, valid-type]
    __tablename__ = "portfolio_memberships"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    portfolio_id = Column(String(36), ForeignKey("portfolios.id"), nullable=False)
    intent_id = Column(String(36), ForeignKey("intents.id"), nullable=False)
    role = Column(String(100), default="member")
    priority = Column(Integer, default=0)
    added_at = Column(DateTime, default=datetime.utcnow)

    portfolio = relationship("PortfolioModel", back_populates="memberships")

    __table_args__ = (
        Index("idx_portfolio_memberships_portfolio", "portfolio_id"),
        Index("idx_portfolio_memberships_intent", "intent_id"),
    )


class IntentAttachmentModel(Base):  # type: ignore[misc, valid-type]
    __tablename__ = "intent_attachments"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    intent_id = Column(String(36), ForeignKey("intents.id"), nullable=False)
    filename = Column(String(255), nullable=False)
    mime_type = Column(String(100), nullable=False)
    size = Column(Integer, nullable=False)
    storage_url = Column(Text, nullable=False)
    created_by = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    intent = relationship("IntentModel", back_populates="attachments")


class IntentCostModel(Base):  # type: ignore[misc, valid-type]
    __tablename__ = "intent_costs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    intent_id = Column(String(36), ForeignKey("intents.id"), nullable=False)
    agent_id = Column(String(255), nullable=False)
    cost_type = Column(String(100), nullable=False)
    amount = Column(Float, nullable=False)
    unit = Column(String(50), nullable=False)
    provider = Column(String(100), nullable=True)
    cost_metadata = Column(JSON, default=dict)
    recorded_at = Column(DateTime, default=datetime.utcnow)

    intent = relationship("IntentModel", back_populates="costs")


class IntentRetryPolicyModel(Base):  # type: ignore[misc, valid-type]
    __tablename__ = "intent_retry_policies"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    intent_id = Column(
        String(36), ForeignKey("intents.id"), nullable=False, unique=True
    )
    strategy = Column(String(50), nullable=False)
    max_retries = Column(Integer, default=3)
    base_delay_ms = Column(Integer, default=1000)
    max_delay_ms = Column(Integer, default=60000)
    jitter = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class IntentFailureModel(Base):  # type: ignore[misc, valid-type]
    __tablename__ = "intent_failures"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    intent_id = Column(String(36), ForeignKey("intents.id"), nullable=False)
    error_type = Column(String(100), nullable=False)
    error_message = Column(Text, nullable=False)
    attempt_number = Column(Integer, nullable=False)
    agent_id = Column(String(255), nullable=True)
    occurred_at = Column(DateTime, default=datetime.utcnow)


class ACLEntryModel(Base):  # type: ignore[misc, valid-type]
    __tablename__ = "acl_entries"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    intent_id = Column(String(36), ForeignKey("intents.id"), nullable=False)
    principal_id = Column(String(255), nullable=False)
    principal_type = Column(String(50), default="agent")
    permission = Column(String(50), nullable=False, default="read")
    granted_by = Column(String(255), nullable=False)
    granted_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    reason = Column(Text, nullable=True)

    __table_args__ = (
        Index("idx_acl_entries_intent", "intent_id"),
        Index("idx_acl_entries_principal", "principal_id"),
    )


class ACLDefaultPolicyModel(Base):  # type: ignore[misc, valid-type]
    __tablename__ = "acl_default_policies"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    intent_id = Column(
        String(36), ForeignKey("intents.id"), nullable=False, unique=True
    )
    default_policy = Column(String(50), default="open")

    __table_args__ = (Index("idx_acl_default_policy_intent", "intent_id"),)


class AccessRequestModel(Base):  # type: ignore[misc, valid-type]
    __tablename__ = "access_requests"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    intent_id = Column(String(36), ForeignKey("intents.id"), nullable=False)
    principal_id = Column(String(255), nullable=False)
    principal_type = Column(String(50), default="agent")
    requested_permission = Column(String(50), nullable=False, default="write")
    reason = Column(Text, default="")
    status = Column(String(50), default="pending")
    capabilities = Column(JSON, default=list)
    decided_by = Column(String(255), nullable=True)
    decided_at = Column(DateTime, nullable=True)
    decision_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_access_requests_intent", "intent_id"),
        Index("idx_access_requests_principal", "principal_id"),
    )


class TaskModel(Base):  # type: ignore[misc, valid-type]
    __tablename__ = "tasks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    intent_id = Column(String(36), ForeignKey("intents.id"), nullable=False)
    plan_id = Column(String(36), nullable=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(50), default="pending")
    priority = Column(String(50), default="normal")
    input = Column(JSON, default=dict)
    output = Column(JSON, nullable=True)
    artifacts = Column(JSON, default=list)
    assigned_agent = Column(String(255), nullable=True)
    lease_id = Column(String(36), nullable=True)
    capabilities_required = Column(JSON, default=list)
    depends_on = Column(JSON, default=list)
    blocks = Column(JSON, default=list)
    parent_task_id = Column(String(36), nullable=True)
    retry_policy = Column(String(255), nullable=True)
    timeout_seconds = Column(Integer, nullable=True)
    attempt = Column(Integer, default=1)
    max_attempts = Column(Integer, default=3)
    permissions = Column(String(50), default="inherit")
    memory_policy = Column(JSON, nullable=True)
    requires_tools = Column(JSON, default=list)
    blocked_reason = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    task_metadata = Column("metadata", JSON, default=dict)
    version = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_tasks_intent_id", "intent_id"),
        Index("idx_tasks_plan_id", "plan_id"),
        Index("idx_tasks_status", "status"),
        Index("idx_tasks_assigned_agent", "assigned_agent"),
    )


class PlanModel(Base):  # type: ignore[misc, valid-type]
    __tablename__ = "plans"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    intent_id = Column(String(36), ForeignKey("intents.id"), nullable=False)
    version = Column(Integer, default=1)
    state = Column(String(50), default="draft")
    tasks = Column(JSON, default=list)
    checkpoints = Column(JSON, default=list)
    conditions = Column(JSON, default=list)
    on_failure = Column(String(50), default="pause_and_escalate")
    on_complete = Column(String(50), default="notify")
    plan_metadata = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (Index("idx_plans_intent_id", "intent_id"),)


class CoordinatorLeaseModel(Base):  # type: ignore[misc, valid-type]
    __tablename__ = "coordinator_leases"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    intent_id = Column(String(36), nullable=True)
    portfolio_id = Column(String(36), nullable=True)
    agent_id = Column(String(255), nullable=False)
    role = Column(String(100), default="coordinator")
    supervisor_id = Column(String(255), nullable=True)
    coordinator_type = Column(String(50), default="llm")
    scope = Column(String(50), default="intent")
    status = Column(String(50), default="active")
    guardrails = Column(JSON, nullable=True)
    heartbeat_interval_seconds = Column(Integer, default=60)
    last_heartbeat = Column(DateTime, nullable=True)
    granted_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    version = Column(Integer, default=1)
    lease_metadata = Column("metadata", JSON, default=dict)

    __table_args__ = (
        Index("idx_coordinator_leases_intent", "intent_id"),
        Index("idx_coordinator_leases_agent", "agent_id"),
    )


class DecisionRecordModel(Base):  # type: ignore[misc, valid-type]
    __tablename__ = "decision_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    coordinator_id = Column(String(36), nullable=False)
    intent_id = Column(String(36), nullable=False)
    decision_type = Column(String(100), nullable=False)
    summary = Column(Text, nullable=False)
    rationale = Column(Text, nullable=False)
    alternatives_considered = Column(JSON, default=list)
    confidence = Column(Float, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_decision_records_coordinator", "coordinator_id"),
        Index("idx_decision_records_intent", "intent_id"),
    )


class CredentialVaultModel(Base):  # type: ignore[misc, valid-type]
    __tablename__ = "credential_vaults"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    owner_id = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (Index("idx_credential_vaults_owner", "owner_id"),)


class CredentialModel(Base):  # type: ignore[misc, valid-type]
    __tablename__ = "credentials"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    vault_id = Column(String(36), ForeignKey("credential_vaults.id"), nullable=False)
    service = Column(String(255), nullable=False)
    label = Column(String(255), nullable=False)
    auth_type = Column(String(50), nullable=False)
    scopes_available = Column(JSON, default=list)
    status = Column(String(50), default="active")
    credential_metadata = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    rotated_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_credentials_vault", "vault_id"),
        Index("idx_credentials_service", "service"),
    )


class ToolGrantModel(Base):  # type: ignore[misc, valid-type]
    __tablename__ = "tool_grants"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    credential_id = Column(String(36), ForeignKey("credentials.id"), nullable=False)
    agent_id = Column(String(255), nullable=False)
    granted_by = Column(String(255), nullable=False)
    scopes = Column(JSON, default=list)
    constraints = Column(JSON, nullable=True)
    source = Column(String(50), default="direct")
    delegatable = Column(Boolean, default=False)
    delegation_depth = Column(Integer, default=0)
    delegated_from = Column(String(36), nullable=True)
    context = Column(JSON, default=dict)
    status = Column(String(50), default="active")
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    revoked_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_tool_grants_agent", "agent_id"),
        Index("idx_tool_grants_credential", "credential_id"),
    )


class ToolInvocationModel(Base):  # type: ignore[misc, valid-type]
    __tablename__ = "tool_invocations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    grant_id = Column(String(36), ForeignKey("tool_grants.id"), nullable=False)
    service = Column(String(255), nullable=False)
    tool = Column(String(255), nullable=False)
    agent_id = Column(String(255), nullable=False)
    parameters = Column(JSON, default=dict)
    status = Column(String(50), default="success")
    result = Column(JSON, nullable=True)
    error = Column(JSON, nullable=True)
    cost = Column(JSON, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    idempotency_key = Column(String(255), nullable=True)
    context = Column(JSON, default=dict)
    timestamp = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_tool_invocations_grant", "grant_id"),
        Index("idx_tool_invocations_agent", "agent_id"),
    )


class MemoryEntryModel(Base):  # type: ignore[misc, valid-type]
    __tablename__ = "memory_entries"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    agent_id = Column(String(255), nullable=False)
    namespace = Column(String(255), nullable=False)
    key = Column(String(255), nullable=False)
    value = Column(JSON, nullable=False)
    memory_type = Column(String(50), nullable=False)
    version = Column(Integer, default=1)
    scope = Column(JSON, nullable=True)
    tags = Column(JSON, default=list)
    ttl = Column(String(50), nullable=True)
    pinned = Column(Boolean, default=False)
    priority = Column(String(50), default="normal")
    sensitivity = Column(String(50), nullable=True)
    curated_by = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_memory_entries_agent", "agent_id"),
        Index("idx_memory_entries_namespace", "namespace"),
        Index("idx_memory_entries_type", "memory_type"),
    )


class AgentRecordModel(Base):  # type: ignore[misc, valid-type]
    __tablename__ = "agent_records"

    agent_id = Column(String(255), primary_key=True)
    status = Column(String(50), default="active")
    role_id = Column(String(255), nullable=True)
    name = Column(String(255), nullable=True)
    capabilities = Column(JSON, default=list)
    capacity = Column(JSON, nullable=True)
    endpoint = Column(Text, nullable=True)
    heartbeat_config = Column(JSON, nullable=True)
    agent_metadata = Column("metadata", JSON, default=dict)
    registered_at = Column(DateTime, default=datetime.utcnow)
    last_heartbeat_at = Column(DateTime, nullable=True)
    drain_timeout_seconds = Column(Integer, nullable=True)
    version = Column(Integer, default=1)

    __table_args__ = (
        Index("idx_agent_records_status", "status"),
        Index("idx_agent_records_role", "role_id"),
    )


class TriggerModel(Base):  # type: ignore[misc, valid-type]
    __tablename__ = "triggers"

    trigger_id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name = Column(String(255), nullable=False)
    type = Column(String(50), nullable=False)
    enabled = Column(Boolean, default=True)
    condition = Column(JSON, nullable=True)
    intent_template = Column(JSON, nullable=True)
    deduplication = Column(String(50), default="allow")
    namespace = Column(String(255), nullable=True)
    fire_count = Column(Integer, default=0)
    version = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_fired_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_triggers_namespace", "namespace"),
        Index("idx_triggers_type", "type"),
    )


class Database:
    """Database interface for OpenIntent server."""

    def __init__(self, database_url: str):
        self.database_url = database_url

        connect_args = {}
        if database_url.startswith("sqlite"):
            connect_args["check_same_thread"] = False

        self.engine = create_engine(
            database_url,
            connect_args=connect_args,
            poolclass=StaticPool if database_url.startswith("sqlite") else None,
        )
        self.SessionLocal = sessionmaker(bind=self.engine)

    def create_tables(self):
        """Create all tables."""
        Base.metadata.create_all(self.engine)

    def get_session(self) -> Session:
        """Get a new database session."""
        return self.SessionLocal()

    def create_intent(self, session: Session, **kwargs) -> IntentModel:
        intent = IntentModel(**kwargs)
        session.add(intent)
        session.commit()
        session.refresh(intent)
        return intent

    def get_intent(self, session: Session, intent_id: str) -> Optional[IntentModel]:
        return session.query(IntentModel).filter(IntentModel.id == intent_id).first()

    # ==================== Intent Graphs (RFC-0002) ====================

    def get_children(self, session: Session, parent_id: str) -> List[IntentModel]:
        """Get immediate children of an intent."""
        return (
            session.query(IntentModel).filter(IntentModel.parent_id == parent_id).all()
        )

    def get_dependencies(self, session: Session, intent_id: str) -> List[IntentModel]:
        """Get intents that this intent depends on."""
        intent = self.get_intent(session, intent_id)
        if not intent or not intent.depends_on:
            return []
        return (
            session.query(IntentModel)
            .filter(IntentModel.id.in_(intent.depends_on))
            .all()
        )

    def get_dependents(self, session: Session, intent_id: str) -> List[IntentModel]:
        """Get intents that depend on this intent."""
        all_intents = session.query(IntentModel).all()
        dependents = []
        for intent in all_intents:
            if intent.depends_on and intent_id in intent.depends_on:
                dependents.append(intent)
        return dependents

    def add_dependency(
        self, session: Session, intent_id: str, version: int, dependency_id: str
    ) -> Optional[IntentModel]:
        """Add a dependency to an intent."""
        intent = self.get_intent(session, intent_id)
        if not intent or intent.version != version:
            return None

        current_deps = list(intent.depends_on or [])
        if dependency_id not in current_deps:
            current_deps.append(dependency_id)

        intent.depends_on = current_deps
        intent.version = version + 1
        intent.updated_at = datetime.utcnow()
        session.commit()
        session.refresh(intent)
        return intent

    def remove_dependency(
        self, session: Session, intent_id: str, version: int, dependency_id: str
    ) -> Optional[IntentModel]:
        """Remove a dependency from an intent."""
        intent = self.get_intent(session, intent_id)
        if not intent or intent.version != version:
            return None

        current_deps = list(intent.depends_on or [])
        if dependency_id in current_deps:
            current_deps.remove(dependency_id)

        intent.depends_on = current_deps
        intent.version = version + 1
        intent.updated_at = datetime.utcnow()
        session.commit()
        session.refresh(intent)
        return intent

    def update_intent_state(
        self, session: Session, intent_id: str, version: int, patches: List[Dict]
    ) -> Optional[IntentModel]:
        intent = self.get_intent(session, intent_id)
        if not intent or intent.version != version:
            return None

        state = dict(intent.state) if intent.state else {}
        state = self._apply_patches(state, patches)

        intent.state = state
        intent.version = version + 1
        intent.updated_at = datetime.utcnow()
        session.commit()
        session.refresh(intent)
        return intent

    def update_intent_status(
        self, session: Session, intent_id: str, version: int, status: str
    ) -> Optional[IntentModel]:
        intent = self.get_intent(session, intent_id)
        if not intent or intent.version != version:
            return None

        intent.status = status
        intent.version = version + 1
        intent.updated_at = datetime.utcnow()
        session.commit()
        session.refresh(intent)
        return intent

    def _apply_patches(self, state: Dict, patches: List[Dict]) -> Dict:
        """Apply JSON patches to state."""
        result = dict(state)

        for patch in patches:
            op = patch.get("op")
            path = patch.get("path", "")
            value = patch.get("value")

            path_parts = [p for p in path.split("/") if p]

            if op == "set":
                if len(path_parts) == 1:
                    result[path_parts[0]] = value
                else:
                    current = result
                    for part in path_parts[:-1]:
                        if part not in current:
                            current[part] = {}
                        current = current[part]
                    current[path_parts[-1]] = value

            elif op == "append":
                if len(path_parts) >= 1:
                    current = result
                    for part in path_parts[:-1]:
                        current = current.get(part, {})
                    key = path_parts[-1]
                    if key not in current or not isinstance(current[key], list):
                        current[key] = []
                    current[key].append(value)

            elif op == "remove":
                if len(path_parts) == 1:
                    result.pop(path_parts[0], None)
                elif len(path_parts) > 1:
                    current = result
                    for part in path_parts[:-1]:
                        current = current.get(part, {})
                    current.pop(path_parts[-1], None)

        return result

    def create_event(self, session: Session, **kwargs) -> IntentEventModel:
        event = IntentEventModel(**kwargs)
        session.add(event)
        session.commit()
        session.refresh(event)
        return event

    def get_events(
        self, session: Session, intent_id: str, limit: int = 100, offset: int = 0
    ) -> List[IntentEventModel]:
        return (
            session.query(IntentEventModel)
            .filter(IntentEventModel.intent_id == intent_id)
            .order_by(desc(IntentEventModel.created_at))
            .offset(offset)
            .limit(limit)
            .all()
        )

    def assign_agent(self, session: Session, **kwargs) -> IntentAgentModel:
        agent = IntentAgentModel(**kwargs)
        session.add(agent)
        session.commit()
        session.refresh(agent)
        return agent

    def get_agents(self, session: Session, intent_id: str) -> List[IntentAgentModel]:
        return (
            session.query(IntentAgentModel)
            .filter(IntentAgentModel.intent_id == intent_id)
            .all()
        )

    def get_agent_assignments(
        self, session: Session, agent_id: str
    ) -> List[IntentAgentModel]:
        return (
            session.query(IntentAgentModel)
            .filter(IntentAgentModel.agent_id == agent_id)
            .all()
        )

    def acquire_lease(
        self,
        session: Session,
        intent_id: str,
        agent_id: str,
        scope: str,
        duration_seconds: int,
    ) -> Optional[IntentLeaseModel]:
        now = datetime.utcnow()
        existing = (
            session.query(IntentLeaseModel)
            .filter(
                IntentLeaseModel.intent_id == intent_id,
                IntentLeaseModel.scope == scope,
                IntentLeaseModel.expires_at > now,
                IntentLeaseModel.released_at.is_(None),
            )
            .first()
        )

        if existing:
            return None

        lease = IntentLeaseModel(
            intent_id=intent_id,
            agent_id=agent_id,
            scope=scope,
            expires_at=now + timedelta(seconds=duration_seconds),
        )
        session.add(lease)
        session.commit()
        session.refresh(lease)
        return lease

    def get_leases(self, session: Session, intent_id: str) -> List[IntentLeaseModel]:
        return (
            session.query(IntentLeaseModel)
            .filter(IntentLeaseModel.intent_id == intent_id)
            .all()
        )

    def release_lease(
        self, session: Session, lease_id: str, agent_id: str
    ) -> Optional[IntentLeaseModel]:
        lease = (
            session.query(IntentLeaseModel)
            .filter(IntentLeaseModel.id == lease_id)
            .first()
        )
        if not lease or lease.agent_id != agent_id:
            return None

        lease.released_at = datetime.utcnow()
        session.commit()
        session.refresh(lease)
        return lease

    def renew_lease(
        self, session: Session, lease_id: str, agent_id: str, duration_seconds: int
    ) -> Optional[IntentLeaseModel]:
        lease = (
            session.query(IntentLeaseModel)
            .filter(IntentLeaseModel.id == lease_id)
            .first()
        )
        if not lease or lease.agent_id != agent_id:
            return None
        if lease.released_at is not None:
            return None  # Already released

        lease.expires_at = datetime.utcnow() + timedelta(seconds=duration_seconds)
        session.commit()
        session.refresh(lease)
        return lease

    def create_portfolio(self, session: Session, **kwargs) -> PortfolioModel:
        portfolio = PortfolioModel(**kwargs)
        session.add(portfolio)
        session.commit()
        session.refresh(portfolio)
        return portfolio

    def get_portfolio(
        self, session: Session, portfolio_id: str
    ) -> Optional[PortfolioModel]:
        return (
            session.query(PortfolioModel)
            .filter(PortfolioModel.id == portfolio_id)
            .first()
        )

    def list_portfolios(
        self, session: Session, created_by: Optional[str] = None
    ) -> List[PortfolioModel]:
        query = session.query(PortfolioModel)
        if created_by:
            query = query.filter(PortfolioModel.created_by == created_by)
        return query.all()

    def add_intent_to_portfolio(
        self, session: Session, **kwargs
    ) -> PortfolioMembershipModel:
        membership = PortfolioMembershipModel(**kwargs)
        session.add(membership)
        session.commit()
        session.refresh(membership)
        return membership

    def update_portfolio_status(
        self, session: Session, portfolio_id: str, status: str
    ) -> Optional[PortfolioModel]:
        portfolio = (
            session.query(PortfolioModel)
            .filter(PortfolioModel.id == portfolio_id)
            .first()
        )
        if not portfolio:
            return None
        portfolio.status = status
        session.commit()
        session.refresh(portfolio)
        return portfolio

    def get_portfolio_intents(
        self, session: Session, portfolio_id: str
    ) -> List[IntentModel]:
        memberships = (
            session.query(PortfolioMembershipModel)
            .filter(PortfolioMembershipModel.portfolio_id == portfolio_id)
            .all()
        )
        intent_ids = [m.intent_id for m in memberships]
        if not intent_ids:
            return []
        return session.query(IntentModel).filter(IntentModel.id.in_(intent_ids)).all()

    def create_attachment(self, session: Session, **kwargs) -> IntentAttachmentModel:
        attachment = IntentAttachmentModel(**kwargs)
        session.add(attachment)
        session.commit()
        session.refresh(attachment)
        return attachment

    def get_attachments(
        self, session: Session, intent_id: str
    ) -> List[IntentAttachmentModel]:
        return (
            session.query(IntentAttachmentModel)
            .filter(IntentAttachmentModel.intent_id == intent_id)
            .all()
        )

    def delete_attachment(self, session: Session, attachment_id: str) -> bool:
        attachment = (
            session.query(IntentAttachmentModel)
            .filter(IntentAttachmentModel.id == attachment_id)
            .first()
        )
        if not attachment:
            return False
        session.delete(attachment)
        session.commit()
        return True

    def get_intent_portfolios(
        self, session: Session, intent_id: str
    ) -> List[PortfolioModel]:
        memberships = (
            session.query(PortfolioMembershipModel)
            .filter(PortfolioMembershipModel.intent_id == intent_id)
            .all()
        )
        portfolio_ids = [m.portfolio_id for m in memberships]
        if not portfolio_ids:
            return []
        return (
            session.query(PortfolioModel)
            .filter(PortfolioModel.id.in_(portfolio_ids))
            .all()
        )

    def remove_intent_from_portfolio(
        self, session: Session, portfolio_id: str, intent_id: str
    ) -> bool:
        membership = (
            session.query(PortfolioMembershipModel)
            .filter(
                PortfolioMembershipModel.portfolio_id == portfolio_id,
                PortfolioMembershipModel.intent_id == intent_id,
            )
            .first()
        )
        if not membership:
            return False
        session.delete(membership)
        session.commit()
        return True

    def record_cost(self, session: Session, **kwargs) -> IntentCostModel:
        cost = IntentCostModel(**kwargs)
        session.add(cost)
        session.commit()
        session.refresh(cost)
        return cost

    def get_costs(self, session: Session, intent_id: str) -> List[IntentCostModel]:
        return (
            session.query(IntentCostModel)
            .filter(IntentCostModel.intent_id == intent_id)
            .all()
        )

    def set_retry_policy(self, session: Session, **kwargs) -> IntentRetryPolicyModel:
        existing = (
            session.query(IntentRetryPolicyModel)
            .filter(IntentRetryPolicyModel.intent_id == kwargs.get("intent_id"))
            .first()
        )
        if existing:
            for key, value in kwargs.items():
                setattr(existing, key, value)
            session.commit()
            session.refresh(existing)
            return existing

        policy = IntentRetryPolicyModel(**kwargs)
        session.add(policy)
        session.commit()
        session.refresh(policy)
        return policy

    def get_retry_policy(
        self, session: Session, intent_id: str
    ) -> Optional[IntentRetryPolicyModel]:
        return (
            session.query(IntentRetryPolicyModel)
            .filter(IntentRetryPolicyModel.intent_id == intent_id)
            .first()
        )

    def record_failure(self, session: Session, **kwargs) -> IntentFailureModel:
        failure = IntentFailureModel(**kwargs)
        session.add(failure)
        session.commit()
        session.refresh(failure)
        return failure

    def get_failures(
        self, session: Session, intent_id: str
    ) -> List[IntentFailureModel]:
        return (
            session.query(IntentFailureModel)
            .filter(IntentFailureModel.intent_id == intent_id)
            .all()
        )

    # ==================== Access Control (RFC-0011) ====================

    def get_acl(self, session: Session, intent_id: str) -> Dict:
        """Get the ACL for an intent (default policy + entries)."""
        policy = (
            session.query(ACLDefaultPolicyModel)
            .filter(ACLDefaultPolicyModel.intent_id == intent_id)
            .first()
        )
        entries = (
            session.query(ACLEntryModel)
            .filter(ACLEntryModel.intent_id == intent_id)
            .all()
        )
        return {
            "intent_id": intent_id,
            "default_policy": policy.default_policy if policy else "open",
            "entries": entries,
        }

    def set_acl(
        self,
        session: Session,
        intent_id: str,
        default_policy: str = "open",
        entries: Optional[List[Dict]] = None,
    ) -> Dict:
        """Set/replace the ACL for an intent."""
        # Upsert default policy
        existing_policy = (
            session.query(ACLDefaultPolicyModel)
            .filter(ACLDefaultPolicyModel.intent_id == intent_id)
            .first()
        )
        if existing_policy:
            existing_policy.default_policy = default_policy
        else:
            session.add(
                ACLDefaultPolicyModel(
                    intent_id=intent_id,
                    default_policy=default_policy,
                )
            )

        # Replace all entries
        session.query(ACLEntryModel).filter(
            ACLEntryModel.intent_id == intent_id
        ).delete()

        new_entries = []
        for entry_data in entries or []:
            entry = ACLEntryModel(
                intent_id=intent_id,
                principal_id=entry_data["principal_id"],
                principal_type=entry_data.get("principal_type", "agent"),
                permission=entry_data.get("permission", "read"),
                granted_by=entry_data.get("granted_by", "system"),
                reason=entry_data.get("reason"),
                expires_at=(
                    datetime.fromisoformat(entry_data["expires_at"])
                    if entry_data.get("expires_at")
                    else None
                ),
            )
            session.add(entry)
            new_entries.append(entry)

        session.commit()

        # Refresh all new entries
        for entry in new_entries:
            session.refresh(entry)

        return {
            "intent_id": intent_id,
            "default_policy": default_policy,
            "entries": new_entries,
        }

    def grant_access(
        self, session: Session, intent_id: str, granted_by: str, **kwargs
    ) -> ACLEntryModel:
        """Create a new ACL entry (grant access)."""
        entry = ACLEntryModel(
            intent_id=intent_id,
            granted_by=granted_by,
            **kwargs,
        )
        session.add(entry)
        session.commit()
        session.refresh(entry)
        return entry

    def get_acl_entry(self, session: Session, entry_id: str) -> Optional[ACLEntryModel]:
        """Get a single ACL entry by ID."""
        return session.query(ACLEntryModel).filter(ACLEntryModel.id == entry_id).first()

    def revoke_access(self, session: Session, intent_id: str, entry_id: str) -> bool:
        """Remove an ACL entry (revoke access)."""
        entry = (
            session.query(ACLEntryModel)
            .filter(
                ACLEntryModel.id == entry_id,
                ACLEntryModel.intent_id == intent_id,
            )
            .first()
        )
        if not entry:
            return False
        session.delete(entry)
        session.commit()
        return True

    def create_access_request(self, session: Session, **kwargs) -> AccessRequestModel:
        """Create a new access request."""
        request = AccessRequestModel(**kwargs)
        session.add(request)
        session.commit()
        session.refresh(request)
        return request

    def get_access_requests(
        self, session: Session, intent_id: str
    ) -> List[AccessRequestModel]:
        """List access requests for an intent."""
        return (
            session.query(AccessRequestModel)
            .filter(AccessRequestModel.intent_id == intent_id)
            .all()
        )

    def get_access_request(
        self, session: Session, request_id: str
    ) -> Optional[AccessRequestModel]:
        """Get a single access request by ID."""
        return (
            session.query(AccessRequestModel)
            .filter(AccessRequestModel.id == request_id)
            .first()
        )

    def approve_access_request(
        self,
        session: Session,
        request_id: str,
        decided_by: str,
        permission: Optional[str] = None,
        expires_at: Optional[datetime] = None,
        reason: Optional[str] = None,
    ) -> Optional[AccessRequestModel]:
        """Approve an access request and create a corresponding ACL entry."""
        request = self.get_access_request(session, request_id)
        if not request or request.status != "pending":
            return None

        request.status = "approved"
        request.decided_by = decided_by
        request.decided_at = datetime.utcnow()
        request.decision_reason = reason

        # Auto-create ACL entry
        grant_permission = permission or request.requested_permission
        self.grant_access(
            session,
            intent_id=request.intent_id,
            granted_by=decided_by,
            principal_id=request.principal_id,
            principal_type=request.principal_type,
            permission=grant_permission,
            reason=f"Approved access request: {reason or ''}".strip(),
            expires_at=expires_at,
        )

        session.commit()
        session.refresh(request)
        return request

    def deny_access_request(
        self,
        session: Session,
        request_id: str,
        decided_by: str,
        reason: Optional[str] = None,
    ) -> Optional[AccessRequestModel]:
        """Deny an access request."""
        request = self.get_access_request(session, request_id)
        if not request or request.status != "pending":
            return None

        request.status = "denied"
        request.decided_by = decided_by
        request.decided_at = datetime.utcnow()
        request.decision_reason = reason
        session.commit()
        session.refresh(request)
        return request

    # ==================== Tasks (RFC-0012) ====================

    def create_task(self, session: Session, **kwargs) -> TaskModel:
        task = TaskModel(**kwargs)
        session.add(task)
        session.commit()
        session.refresh(task)
        return task

    def get_task(self, session: Session, task_id: str) -> Optional[TaskModel]:
        return session.query(TaskModel).filter(TaskModel.id == task_id).first()

    def list_tasks(
        self,
        session: Session,
        intent_id: str,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[TaskModel]:
        query = session.query(TaskModel).filter(TaskModel.intent_id == intent_id)
        if status:
            query = query.filter(TaskModel.status == status)
        return query.offset(offset).limit(limit).all()

    def update_task_status(
        self, session: Session, task_id: str, version: int, status: str, **kwargs
    ) -> Optional[TaskModel]:
        task = self.get_task(session, task_id)
        if not task or task.version != version:
            return None

        task.status = status
        task.version = version + 1
        for key, value in kwargs.items():
            setattr(task, key, value)
        session.commit()
        session.refresh(task)
        return task

    # ==================== Plans (RFC-0012) ====================

    def create_plan(self, session: Session, **kwargs) -> PlanModel:
        plan = PlanModel(**kwargs)
        session.add(plan)
        session.commit()
        session.refresh(plan)
        return plan

    def get_plan(self, session: Session, plan_id: str) -> Optional[PlanModel]:
        return session.query(PlanModel).filter(PlanModel.id == plan_id).first()

    def list_plans(self, session: Session, intent_id: str) -> List[PlanModel]:
        return session.query(PlanModel).filter(PlanModel.intent_id == intent_id).all()

    def update_plan(
        self, session: Session, plan_id: str, version: int, **kwargs
    ) -> Optional[PlanModel]:
        plan = self.get_plan(session, plan_id)
        if not plan or plan.version != version:
            return None

        plan.version = version + 1
        plan.updated_at = datetime.utcnow()
        for key, value in kwargs.items():
            setattr(plan, key, value)
        session.commit()
        session.refresh(plan)
        return plan

    # ==================== Coordinator Leases (RFC-0013) ====================

    def create_coordinator_lease(
        self, session: Session, **kwargs
    ) -> CoordinatorLeaseModel:
        lease = CoordinatorLeaseModel(**kwargs)
        session.add(lease)
        session.commit()
        session.refresh(lease)
        return lease

    def get_coordinator_lease(
        self, session: Session, lease_id: str
    ) -> Optional[CoordinatorLeaseModel]:
        return (
            session.query(CoordinatorLeaseModel)
            .filter(CoordinatorLeaseModel.id == lease_id)
            .first()
        )

    def list_coordinator_leases(
        self, session: Session, intent_id: Optional[str] = None
    ) -> List[CoordinatorLeaseModel]:
        query = session.query(CoordinatorLeaseModel)
        if intent_id:
            query = query.filter(CoordinatorLeaseModel.intent_id == intent_id)
        return query.all()

    def update_coordinator_heartbeat(
        self, session: Session, lease_id: str, agent_id: str
    ) -> Optional[CoordinatorLeaseModel]:
        lease = (
            session.query(CoordinatorLeaseModel)
            .filter(CoordinatorLeaseModel.id == lease_id)
            .first()
        )
        if not lease or lease.agent_id != agent_id:
            return None

        lease.last_heartbeat = datetime.utcnow()
        session.commit()
        session.refresh(lease)
        return lease

    # ==================== Decision Records (RFC-0013) ====================

    def create_decision_record(self, session: Session, **kwargs) -> DecisionRecordModel:
        record = DecisionRecordModel(**kwargs)
        session.add(record)
        session.commit()
        session.refresh(record)
        return record

    def list_decision_records(
        self, session: Session, intent_id: str, limit: int = 50
    ) -> List[DecisionRecordModel]:
        return (
            session.query(DecisionRecordModel)
            .filter(DecisionRecordModel.intent_id == intent_id)
            .order_by(desc(DecisionRecordModel.timestamp))
            .limit(limit)
            .all()
        )

    # ==================== Credential Vaults (RFC-0014) ====================

    def create_vault(self, session: Session, **kwargs) -> CredentialVaultModel:
        vault = CredentialVaultModel(**kwargs)
        session.add(vault)
        session.commit()
        session.refresh(vault)
        return vault

    def get_vault(
        self, session: Session, vault_id: str
    ) -> Optional[CredentialVaultModel]:
        return (
            session.query(CredentialVaultModel)
            .filter(CredentialVaultModel.id == vault_id)
            .first()
        )

    # ==================== Credentials (RFC-0014) ====================

    def create_credential(self, session: Session, **kwargs) -> CredentialModel:
        credential = CredentialModel(**kwargs)
        session.add(credential)
        session.commit()
        session.refresh(credential)
        return credential

    def get_credential(
        self, session: Session, credential_id: str
    ) -> Optional[CredentialModel]:
        return (
            session.query(CredentialModel)
            .filter(CredentialModel.id == credential_id)
            .first()
        )

    # ==================== Tool Grants (RFC-0014) ====================

    def create_tool_grant(self, session: Session, **kwargs) -> ToolGrantModel:
        grant = ToolGrantModel(**kwargs)
        session.add(grant)
        session.commit()
        session.refresh(grant)
        return grant

    def get_tool_grant(
        self, session: Session, grant_id: str
    ) -> Optional[ToolGrantModel]:
        return (
            session.query(ToolGrantModel).filter(ToolGrantModel.id == grant_id).first()
        )

    def list_agent_grants(
        self, session: Session, agent_id: str
    ) -> List[ToolGrantModel]:
        return (
            session.query(ToolGrantModel)
            .filter(ToolGrantModel.agent_id == agent_id)
            .all()
        )

    def revoke_grant(self, session: Session, grant_id: str) -> Optional[ToolGrantModel]:
        grant = self.get_tool_grant(session, grant_id)
        if not grant:
            return None

        grant.status = "revoked"
        grant.revoked_at = datetime.utcnow()
        session.commit()
        session.refresh(grant)
        return grant

    def find_agent_grant_for_tool(
        self, session: Session, agent_id: str, tool_name: str
    ) -> Optional[ToolGrantModel]:
        """Find an active grant for an agent that covers a specific tool/service name.

        Matches in priority order:
        1. Grant scopes contain the tool name (e.g. scopes=["web_search"])
        2. Grant context has a 'tools' list containing the tool name
        3. Credential service matches the tool name exactly
        """
        grants = (
            session.query(ToolGrantModel)
            .filter(
                ToolGrantModel.agent_id == agent_id,
                ToolGrantModel.status == "active",
            )
            .all()
        )
        for grant in grants:
            if grant.scopes and tool_name in grant.scopes:
                return grant
            ctx = grant.context or {}
            if isinstance(ctx, dict) and tool_name in ctx.get("tools", []):
                return grant
        for grant in grants:
            credential = self.get_credential(session, grant.credential_id)
            if credential and credential.service == tool_name:
                return grant
        return None

    # ==================== Tool Invocations (RFC-0014) ====================

    def create_tool_invocation(self, session: Session, **kwargs) -> ToolInvocationModel:
        invocation = ToolInvocationModel(**kwargs)
        session.add(invocation)
        session.commit()
        session.refresh(invocation)
        return invocation

    def list_tool_invocations(
        self, session: Session, grant_id: str, limit: int = 50
    ) -> List[ToolInvocationModel]:
        return (
            session.query(ToolInvocationModel)
            .filter(ToolInvocationModel.grant_id == grant_id)
            .order_by(desc(ToolInvocationModel.timestamp))
            .limit(limit)
            .all()
        )

    # ==================== Memory Entries (RFC-0015) ====================

    def create_memory_entry(self, session: Session, **kwargs) -> MemoryEntryModel:
        entry = MemoryEntryModel(**kwargs)
        session.add(entry)
        session.commit()
        session.refresh(entry)
        return entry

    def get_memory_entry(
        self, session: Session, entry_id: str
    ) -> Optional[MemoryEntryModel]:
        return (
            session.query(MemoryEntryModel)
            .filter(MemoryEntryModel.id == entry_id)
            .first()
        )

    def list_memory_entries(
        self,
        session: Session,
        agent_id: str,
        namespace: Optional[str] = None,
        memory_type: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 100,
    ) -> List[MemoryEntryModel]:
        query = session.query(MemoryEntryModel).filter(
            MemoryEntryModel.agent_id == agent_id
        )
        if namespace:
            query = query.filter(MemoryEntryModel.namespace == namespace)
        if memory_type:
            query = query.filter(MemoryEntryModel.memory_type == memory_type)
        return query.limit(limit).all()

    def update_memory_entry(
        self, session: Session, entry_id: str, version: int, **kwargs
    ) -> Optional[MemoryEntryModel]:
        entry = self.get_memory_entry(session, entry_id)
        if not entry or entry.version != version:
            return None

        entry.version = version + 1
        entry.updated_at = datetime.utcnow()
        for key, value in kwargs.items():
            setattr(entry, key, value)
        session.commit()
        session.refresh(entry)
        return entry

    def delete_memory_entry(self, session: Session, entry_id: str) -> bool:
        entry = (
            session.query(MemoryEntryModel)
            .filter(MemoryEntryModel.id == entry_id)
            .first()
        )
        if not entry:
            return False
        session.delete(entry)
        session.commit()
        return True

    # ==================== Agent Records (RFC-0016) ====================

    def register_agent(self, session: Session, **kwargs) -> AgentRecordModel:
        agent = AgentRecordModel(**kwargs)
        session.add(agent)
        session.commit()
        session.refresh(agent)
        return agent

    def get_agent_record(
        self, session: Session, agent_id: str
    ) -> Optional[AgentRecordModel]:
        return (
            session.query(AgentRecordModel)
            .filter(AgentRecordModel.agent_id == agent_id)
            .first()
        )

    def list_agent_records(
        self,
        session: Session,
        status: Optional[str] = None,
        role_id: Optional[str] = None,
    ) -> List[AgentRecordModel]:
        query = session.query(AgentRecordModel)
        if status:
            query = query.filter(AgentRecordModel.status == status)
        if role_id:
            query = query.filter(AgentRecordModel.role_id == role_id)
        return query.all()

    def update_agent_heartbeat(
        self,
        session: Session,
        agent_id: str,
        current_load: Optional[dict] = None,
        tasks_in_progress: Optional[list] = None,
    ) -> Optional[AgentRecordModel]:
        agent = self.get_agent_record(session, agent_id)
        if not agent:
            return None

        agent.last_heartbeat_at = datetime.utcnow()
        if current_load is not None or tasks_in_progress is not None:
            capacity = dict(agent.capacity) if agent.capacity else {}
            if current_load is not None:
                capacity["current_load"] = current_load
            if tasks_in_progress is not None:
                capacity["tasks_in_progress"] = tasks_in_progress
            agent.capacity = capacity
        session.commit()
        session.refresh(agent)
        return agent

    def update_agent_status(
        self, session: Session, agent_id: str, status: str
    ) -> Optional[AgentRecordModel]:
        agent = self.get_agent_record(session, agent_id)
        if not agent:
            return None

        agent.status = status
        session.commit()
        session.refresh(agent)
        return agent

    # ==================== Triggers (RFC-0017) ====================

    def create_trigger(self, session: Session, **kwargs) -> TriggerModel:
        trigger = TriggerModel(**kwargs)
        session.add(trigger)
        session.commit()
        session.refresh(trigger)
        return trigger

    def get_trigger(self, session: Session, trigger_id: str) -> Optional[TriggerModel]:
        return (
            session.query(TriggerModel)
            .filter(TriggerModel.trigger_id == trigger_id)
            .first()
        )

    def list_triggers(
        self,
        session: Session,
        namespace: Optional[str] = None,
        trigger_type: Optional[str] = None,
    ) -> List[TriggerModel]:
        query = session.query(TriggerModel)
        if namespace:
            query = query.filter(TriggerModel.namespace == namespace)
        if trigger_type:
            query = query.filter(TriggerModel.type == trigger_type)
        return query.all()

    def update_trigger(
        self, session: Session, trigger_id: str, version: int, **kwargs
    ) -> Optional[TriggerModel]:
        trigger = self.get_trigger(session, trigger_id)
        if not trigger or trigger.version != version:
            return None

        trigger.version = version + 1
        trigger.updated_at = datetime.utcnow()
        for key, value in kwargs.items():
            setattr(trigger, key, value)
        session.commit()
        session.refresh(trigger)
        return trigger

    def fire_trigger(self, session: Session, trigger_id: str) -> Optional[TriggerModel]:
        trigger = self.get_trigger(session, trigger_id)
        if not trigger:
            return None

        trigger.fire_count = (trigger.fire_count or 0) + 1
        trigger.last_fired_at = datetime.utcnow()
        session.commit()
        session.refresh(trigger)
        return trigger

    def delete_trigger(self, session: Session, trigger_id: str) -> bool:
        trigger = (
            session.query(TriggerModel)
            .filter(TriggerModel.trigger_id == trigger_id)
            .first()
        )
        if not trigger:
            return False
        session.delete(trigger)
        session.commit()
        return True


_database: Optional[Database] = None


def get_database(database_url: str = "sqlite:///./openintent.db") -> Database:
    """Get or create the database instance."""
    global _database
    if _database is None:
        _database = Database(database_url)
        _database.create_tables()
    return _database
