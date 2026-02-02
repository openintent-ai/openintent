"""
Database layer for OpenIntent server using SQLAlchemy.
Supports SQLite (default) and PostgreSQL.
"""

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


class IntentModel(Base):
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


class IntentEventModel(Base):
    __tablename__ = "intent_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    intent_id = Column(String(36), ForeignKey("intents.id"), nullable=False)
    event_type = Column(String(100), nullable=False)
    actor = Column(String(255), nullable=False)
    payload = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

    intent = relationship("IntentModel", back_populates="events")

    __table_args__ = (Index("idx_intent_events_intent_id", "intent_id"),)


class IntentAgentModel(Base):
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


class IntentLeaseModel(Base):
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


class PortfolioModel(Base):
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


class PortfolioMembershipModel(Base):
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


class IntentAttachmentModel(Base):
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


class IntentCostModel(Base):
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


class IntentRetryPolicyModel(Base):
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


class IntentFailureModel(Base):
    __tablename__ = "intent_failures"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    intent_id = Column(String(36), ForeignKey("intents.id"), nullable=False)
    error_type = Column(String(100), nullable=False)
    error_message = Column(Text, nullable=False)
    attempt_number = Column(Integer, nullable=False)
    agent_id = Column(String(255), nullable=True)
    occurred_at = Column(DateTime, default=datetime.utcnow)


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


_database: Optional[Database] = None


def get_database(database_url: str = "sqlite:///./openintent.db") -> Database:
    """Get or create the database instance."""
    global _database
    if _database is None:
        _database = Database(database_url)
        _database.create_tables()
    return _database
