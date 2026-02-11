"""
FastAPI application for OpenIntent server.
"""

# mypy: disable-error-code="arg-type, var-annotated, misc, union-attr, attr-defined"

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field
from sse_starlette.sse import EventSourceResponse

from .config import ServerConfig
from .database import (  # noqa: F401
    AccessRequestModel,
    ACLDefaultPolicyModel,
    ACLEntryModel,
    AgentRecordModel,
    CoordinatorLeaseModel,
    CredentialModel,
    CredentialVaultModel,
    Database,
    DecisionRecordModel,
    IntentModel,
    MemoryEntryModel,
    PlanModel,
    TaskModel,
    ToolGrantModel,
    ToolInvocationModel,
    TriggerModel,
    get_database,
)


class IntentCreate(BaseModel):
    title: str
    description: str = ""
    created_by: Optional[str] = None
    parent_id: Optional[str] = Field(None, alias="parent_intent_id")
    depends_on: List[str] = Field(default_factory=list)
    constraints: Dict[str, Any] = Field(default_factory=dict)
    state: Dict[str, Any] = Field(default_factory=dict)
    status: str = "draft"

    model_config = ConfigDict(populate_by_name=True)


class IntentResponse(BaseModel):
    id: str
    title: str
    description: str
    created_by: str
    parent_intent_id: Optional[str] = Field(None, alias="parent_id")
    depends_on: List[str] = Field(default_factory=list)
    constraints: Dict[str, Any]
    state: Dict[str, Any]
    status: str
    confidence: float
    version: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ChildIntentCreate(BaseModel):
    title: str
    description: str = ""
    depends_on: List[str] = Field(default_factory=list)
    constraints: Dict[str, Any] = Field(default_factory=dict)
    state: Dict[str, Any] = Field(default_factory=dict)


class DependencyAdd(BaseModel):
    dependency_id: str


class StatePatch(BaseModel):
    op: str
    path: str
    value: Any = None


class StatePatchRequest(BaseModel):
    # Support both formats:
    # 1. JSON Patch: {"patches": [{op, path, value}, ...]}
    # 2. Simple merge: {"state": {"key": "value"}}
    patches: Optional[List[StatePatch]] = None
    state: Optional[Dict[str, Any]] = None

    def get_patches(self) -> List[Dict[str, Any]]:
        """Convert to patches format, handling both input styles."""
        if self.patches:
            return [p.model_dump() for p in self.patches]
        elif self.state:
            # Convert simple state dict to set operations
            return [{"op": "set", "path": k, "value": v} for k, v in self.state.items()]
        return []


class StatusUpdateRequest(BaseModel):
    status: str


class LeaseRenewRequest(BaseModel):
    duration_seconds: int = 300


class PortfolioStatusRequest(BaseModel):
    status: str


class EventCreate(BaseModel):
    event_type: str
    actor: str
    payload: Dict[str, Any] = Field(default_factory=dict)


class EventResponse(BaseModel):
    id: str
    intent_id: str
    event_type: str
    actor: str
    payload: Dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AgentAssign(BaseModel):
    agent_id: str
    role: str = "worker"


class AgentResponse(BaseModel):
    id: str
    intent_id: str
    agent_id: str
    role: str
    assigned_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LeaseRequest(BaseModel):
    scope: str
    duration_seconds: int = 300


class LeaseResponse(BaseModel):
    id: str
    intent_id: str
    agent_id: str
    scope: str
    acquired_at: datetime
    expires_at: datetime
    released_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class PortfolioCreate(BaseModel):
    name: str
    description: str = ""
    created_by: str
    governance_policy: Dict[str, Any] = Field(default_factory=dict)


class PortfolioResponse(BaseModel):
    id: str
    name: str
    description: str
    created_by: str
    status: str
    governance_policy: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PortfolioMembershipCreate(BaseModel):
    intent_id: str
    role: str = "member"
    priority: int = 0


class AttachmentCreate(BaseModel):
    filename: str
    mime_type: str
    size: int
    storage_url: str


class AttachmentResponse(BaseModel):
    id: str
    intent_id: str
    filename: str
    mime_type: str
    size: int
    storage_url: str
    created_by: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CostRecord(BaseModel):
    agent_id: str
    cost_type: str
    amount: float
    unit: str
    provider: Optional[str] = None
    cost_metadata: Dict[str, Any] = Field(default_factory=dict)


class CostResponse(BaseModel):
    id: str
    intent_id: str
    agent_id: str
    cost_type: str
    amount: float
    unit: str
    provider: Optional[str]
    cost_metadata: Dict[str, Any]
    recorded_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RetryPolicyCreate(BaseModel):
    strategy: str
    max_retries: int = 3
    base_delay_ms: int = 1000
    max_delay_ms: int = 60000
    jitter: bool = True


class RetryPolicyResponse(BaseModel):
    id: str
    intent_id: str
    strategy: str
    max_retries: int
    base_delay_ms: int
    max_delay_ms: int
    jitter: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FailureRecord(BaseModel):
    error_type: str
    error_message: str
    attempt_number: int
    agent_id: Optional[str] = None


class ArbitrationRequest(BaseModel):
    reason: str
    requested_by: str
    context: Dict[str, Any] = Field(default_factory=dict)


class DecisionRecord(BaseModel):
    decision_type: str
    decided_by: str
    outcome: str
    rationale: str = ""


class ACLEntryCreate(BaseModel):
    principal_id: str
    principal_type: str = "agent"
    permission: str = "read"
    reason: Optional[str] = None
    expires_at: Optional[datetime] = None


class ACLEntryResponse(BaseModel):
    id: str
    intent_id: str
    principal_id: str
    principal_type: str
    permission: str
    granted_by: str
    granted_at: datetime
    expires_at: Optional[datetime]
    reason: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class ACLSetRequest(BaseModel):
    default_policy: str = "open"
    entries: List[Dict[str, Any]] = Field(default_factory=list)


class ACLResponse(BaseModel):
    intent_id: str
    default_policy: str
    entries: List[ACLEntryResponse]


class AccessRequestCreate(BaseModel):
    principal_id: str
    principal_type: str = "agent"
    requested_permission: str = "write"
    reason: str = ""
    capabilities: List[str] = Field(default_factory=list)


class AccessRequestResponse(BaseModel):
    id: str
    intent_id: str
    principal_id: str
    principal_type: str
    requested_permission: str
    reason: str
    status: str
    capabilities: List[str]
    decided_by: Optional[str]
    decided_at: Optional[datetime]
    decision_reason: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AccessRequestDecision(BaseModel):
    decided_by: str
    permission: Optional[str] = None
    expires_at: Optional[datetime] = None
    reason: Optional[str] = None


# RFC-0012: Task Decomposition & Planning
class TaskCreate(BaseModel):
    intent_id: str
    name: str
    plan_id: Optional[str] = None
    description: Optional[str] = None
    priority: str = "normal"
    input: Dict[str, Any] = Field(default_factory=dict)
    capabilities_required: List[str] = Field(default_factory=list)
    depends_on: List[str] = Field(default_factory=list)
    parent_task_id: Optional[str] = None
    timeout_seconds: Optional[int] = None
    max_attempts: int = 3
    permissions: str = "inherit"
    memory_policy: Optional[Dict[str, Any]] = None
    requires_tools: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TaskResponse(BaseModel):
    id: str
    intent_id: str
    plan_id: Optional[str]
    name: str
    description: Optional[str]
    status: str
    priority: str
    input: Dict[str, Any]
    output: Optional[Dict[str, Any]]
    artifacts: List[str]
    assigned_agent: Optional[str]
    lease_id: Optional[str]
    capabilities_required: List[str]
    depends_on: List[str]
    blocks: List[str]
    parent_task_id: Optional[str]
    retry_policy: Optional[str]
    timeout_seconds: Optional[int]
    attempt: int
    max_attempts: int
    permissions: str
    memory_policy: Optional[Dict[str, Any]]
    requires_tools: List[Dict[str, Any]]
    blocked_reason: Optional[str]
    error: Optional[str]
    task_metadata: Optional[Dict[str, Any]] = None
    version: int
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class TaskStatusUpdate(BaseModel):
    status: str
    assigned_agent: Optional[str] = None
    output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    blocked_reason: Optional[str] = None


class PlanCreate(BaseModel):
    intent_id: str
    tasks: List[str] = Field(default_factory=list)
    checkpoints: List[Dict[str, Any]] = Field(default_factory=list)
    conditions: List[Dict[str, Any]] = Field(default_factory=list)
    on_failure: str = "pause_and_escalate"
    on_complete: str = "notify"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PlanResponse(BaseModel):
    id: str
    intent_id: str
    version: int
    state: str
    tasks: List[str]
    checkpoints: List[Dict[str, Any]]
    conditions: List[Dict[str, Any]]
    on_failure: str
    on_complete: str
    plan_metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class PlanUpdate(BaseModel):
    state: Optional[str] = None
    tasks: Optional[List[str]] = None
    checkpoints: Optional[List[Dict[str, Any]]] = None


# RFC-0013: Coordinator Governance
class CoordinatorLeaseCreate(BaseModel):
    agent_id: str
    intent_id: Optional[str] = None
    portfolio_id: Optional[str] = None
    role: str = "coordinator"
    supervisor_id: Optional[str] = None
    coordinator_type: str = "llm"
    scope: str = "intent"
    guardrails: Optional[Dict[str, Any]] = None
    heartbeat_interval_seconds: int = 60
    expires_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CoordinatorLeaseResponse(BaseModel):
    id: str
    intent_id: Optional[str]
    portfolio_id: Optional[str]
    agent_id: str
    role: str
    supervisor_id: Optional[str]
    coordinator_type: str
    scope: str
    status: str
    guardrails: Optional[Dict[str, Any]]
    heartbeat_interval_seconds: int
    last_heartbeat: Optional[datetime]
    granted_at: datetime
    expires_at: Optional[datetime]
    version: int
    lease_metadata: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class DecisionRecordCreate(BaseModel):
    coordinator_id: str
    intent_id: str
    decision_type: str
    summary: str
    rationale: str
    alternatives_considered: List[Dict[str, Any]] = Field(default_factory=list)
    confidence: Optional[float] = None


class DecisionRecordResponse(BaseModel):
    id: str
    coordinator_id: str
    intent_id: str
    decision_type: str
    summary: str
    rationale: str
    alternatives_considered: List[Dict[str, Any]]
    confidence: Optional[float]
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)


# RFC-0014: Credential Vaults & Tool Scoping
class VaultCreate(BaseModel):
    owner_id: str
    name: str


class VaultResponse(BaseModel):
    id: str
    owner_id: str
    name: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CredentialCreate(BaseModel):
    vault_id: str
    service: str
    label: str
    auth_type: str = "api_key"
    scopes_available: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CredentialResponse(BaseModel):
    id: str
    vault_id: str
    service: str
    label: str
    auth_type: str
    scopes_available: List[str]
    status: str
    credential_metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
    rotated_at: Optional[datetime]
    expires_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class GrantCreate(BaseModel):
    credential_id: str
    agent_id: str
    granted_by: str
    scopes: List[str] = Field(default_factory=list)
    constraints: Optional[Dict[str, Any]] = None
    delegatable: bool = False
    context: Dict[str, Any] = Field(default_factory=dict)
    expires_at: Optional[datetime] = None


class GrantResponse(BaseModel):
    id: str
    credential_id: str
    agent_id: str
    granted_by: str
    scopes: List[str]
    constraints: Optional[Dict[str, Any]]
    source: str
    delegatable: bool
    delegation_depth: int
    delegated_from: Optional[str]
    context: Dict[str, Any]
    status: str
    expires_at: Optional[datetime]
    created_at: datetime
    revoked_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class ToolInvokeRequest(BaseModel):
    tool_name: str
    agent_id: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    idempotency_key: Optional[str] = None


class ToolInvokeResponse(BaseModel):
    invocation_id: str
    tool_name: str
    status: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    duration_ms: Optional[int] = None


class InvocationCreate(BaseModel):
    grant_id: str
    service: str
    tool: str
    agent_id: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    status: str = "success"
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None
    cost: Optional[Dict[str, Any]] = None
    duration_ms: Optional[int] = None
    idempotency_key: Optional[str] = None
    context: Dict[str, Any] = Field(default_factory=dict)


class InvocationResponse(BaseModel):
    id: str
    grant_id: str
    service: str
    tool: str
    agent_id: str
    parameters: Dict[str, Any]
    status: str
    result: Optional[Dict[str, Any]]
    error: Optional[Dict[str, Any]]
    cost: Optional[Dict[str, Any]]
    duration_ms: Optional[int]
    idempotency_key: Optional[str]
    context: Dict[str, Any]
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)


# RFC-0015: Agent Memory
class MemoryEntryCreate(BaseModel):
    agent_id: str
    namespace: str
    key: str
    value: Dict[str, Any]
    memory_type: str = "working"
    scope: Optional[Dict[str, Any]] = None
    tags: List[str] = Field(default_factory=list)
    ttl: Optional[str] = None
    pinned: bool = False
    priority: str = "normal"
    sensitivity: Optional[str] = None


class MemoryEntryResponse(BaseModel):
    id: str
    agent_id: str
    namespace: str
    key: str
    value: Dict[str, Any]
    memory_type: str
    version: int
    scope: Optional[Dict[str, Any]]
    tags: List[str]
    ttl: Optional[str]
    pinned: bool
    priority: str
    sensitivity: Optional[str]
    curated_by: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]
    expires_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class MemoryEntryUpdate(BaseModel):
    value: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None
    pinned: Optional[bool] = None
    priority: Optional[str] = None
    ttl: Optional[str] = None


# RFC-0016: Agent Lifecycle
class AgentRegister(BaseModel):
    agent_id: str
    name: Optional[str] = None
    role_id: Optional[str] = None
    capabilities: List[str] = Field(default_factory=list)
    capacity: Optional[Dict[str, Any]] = None
    endpoint: Optional[str] = None
    heartbeat_config: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    drain_timeout_seconds: Optional[int] = None


class AgentRecordResponse(BaseModel):
    agent_id: str
    status: str
    role_id: Optional[str]
    name: Optional[str]
    capabilities: List[str]
    capacity: Optional[Dict[str, Any]]
    endpoint: Optional[str]
    heartbeat_config: Optional[Dict[str, Any]]
    agent_metadata: Optional[Dict[str, Any]] = None
    registered_at: datetime
    last_heartbeat_at: Optional[datetime]
    drain_timeout_seconds: Optional[int]
    version: int

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class HeartbeatRequest(BaseModel):
    status: str = "active"
    current_load: int = 0
    tasks_in_progress: List[str] = Field(default_factory=list)


class AgentStatusUpdate(BaseModel):
    status: str


# RFC-0017: Triggers
class TriggerCreate(BaseModel):
    name: str
    type: str
    condition: Optional[Dict[str, Any]] = None
    intent_template: Optional[Dict[str, Any]] = None
    deduplication: str = "allow"
    namespace: Optional[str] = None


class TriggerResponse(BaseModel):
    trigger_id: str
    name: str
    type: str
    enabled: bool
    condition: Optional[Dict[str, Any]]
    intent_template: Optional[Dict[str, Any]]
    deduplication: str
    namespace: Optional[str]
    fire_count: int
    version: int
    created_at: datetime
    updated_at: Optional[datetime]
    last_fired_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class TriggerUpdate(BaseModel):
    enabled: Optional[bool] = None
    condition: Optional[Dict[str, Any]] = None
    intent_template: Optional[Dict[str, Any]] = None
    deduplication: Optional[str] = None


_event_queues: Dict[str, List[asyncio.Queue]] = {
    "intents": [],
    "portfolios": [],
    "agents": [],
}


def _broadcast_event(channel: str, event_data: Dict[str, Any]):
    """Broadcast event to all subscribers."""
    for queue in _event_queues.get(channel, []):
        try:
            queue.put_nowait(event_data)
        except asyncio.QueueFull:
            pass


def create_app(config: Optional[ServerConfig] = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    if config is None:
        config = ServerConfig.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        db = get_database(config.database_url)
        app.state.db = db
        app.state.config = config
        yield

    app = FastAPI(
        title="OpenIntent Server",
        description="A conformant OpenIntent Protocol server",
        version="0.7.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def get_db() -> Database:
        return app.state.db

    def validate_api_key(x_api_key: str = Header(None)) -> str:
        if x_api_key is None or x_api_key not in app.state.config.api_keys:
            raise HTTPException(status_code=401, detail="Invalid or missing API key")
        return x_api_key

    def get_version_header(if_match: str = Header(None)) -> Optional[int]:
        if if_match is None:
            return None
        try:
            return int(if_match)
        except ValueError:
            return None

    @app.get("/.well-known/openintent.json")
    async def discovery():
        return {
            "protocol": "OpenIntent Coordination Protocol",
            "version": config.protocol_version,
            "rfcUrls": [
                "/rfc/0001",
                "/rfc/0002",
                "/rfc/0003",
                "/rfc/0004",
                "/rfc/0005",
                "/rfc/0006",
                "/rfc/0009",
                "/rfc/0010",
                "/rfc/0011",
            ],
            "capabilities": [
                "intents",
                "events",
                "agents",
                "state-patches",
                "optimistic-concurrency",
                "portfolios",
                "attachments",
                "subscriptions",
                "cost-tracking",
                "retry-policies",
                "leasing",
                "governance",
                "access-control",
                "tools",
            ],
            "openApiUrl": "/openapi.json",
        }

    @app.get("/.well-known/openintent-compat.json")
    async def compatibility():
        return {
            "implementation": "OpenIntent Python Server",
            "version": "0.7.0",
            "rfcCompliance": {
                "RFC-0001": "full",
                "RFC-0002": "full",
                "RFC-0003": "full",
                "RFC-0004": "full",
                "RFC-0005": "full",
                "RFC-0006": "full",
                "RFC-0009": "full",
                "RFC-0010": "full",
                "RFC-0011": "full",
            },
            "features": {
                "intents": True,
                "events": True,
                "agents": True,
                "statePatches": True,
                "optimisticConcurrency": True,
                "leasing": True,
                "governance": True,
                "portfolios": True,
                "attachments": True,
                "subscriptions": True,
                "costTracking": True,
                "retryPolicies": True,
                "accessControl": True,
            },
        }

    @app.post("/api/v1/intents", response_model=IntentResponse)
    async def create_intent(
        intent: IntentCreate,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        creator = intent.created_by or api_key
        try:
            created = db.create_intent(
                session,
                title=intent.title,
                description=intent.description,
                created_by=creator,
                parent_id=intent.parent_id,
                constraints=intent.constraints,
                state=intent.state,
                status=intent.status,
            )

            db.create_event(
                session,
                intent_id=created.id,
                event_type="intent_created",
                actor=creator,
                payload={"title": intent.title},
            )

            _broadcast_event(
                "intents",
                {
                    "type": "intent_created",
                    "intent_id": created.id,
                    "data": IntentResponse.model_validate(created).model_dump(
                        mode="json"
                    ),
                },
            )

            return IntentResponse.model_validate(created)
        finally:
            session.close()

    @app.get("/api/v1/intents/{intent_id}", response_model=IntentResponse)
    async def get_intent(
        intent_id: str,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            intent = db.get_intent(session, intent_id)
            if not intent:
                raise HTTPException(status_code=404, detail="Intent not found")
            return IntentResponse.model_validate(intent)
        finally:
            session.close()

    # ==================== Intent Graphs (RFC-0002) ====================

    @app.post("/api/v1/intents/{parent_id}/children", response_model=IntentResponse)
    async def create_child_intent(
        parent_id: str,
        child: ChildIntentCreate,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            parent = db.get_intent(session, parent_id)
            if not parent:
                raise HTTPException(status_code=404, detail="Parent intent not found")

            if child.depends_on:
                cycle = _detect_cycle(session, db, None, child.depends_on)
                if cycle:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Dependency would create cycle: {cycle}",
                    )

            created = db.create_intent(
                session,
                title=child.title,
                description=child.description,
                created_by=api_key,
                parent_id=parent_id,
                depends_on=child.depends_on,
                constraints=child.constraints,
                state=child.state,
            )

            db.create_event(
                session,
                intent_id=created.id,
                event_type="intent_created",
                actor=api_key,
                payload={"parent_id": parent_id, "depends_on": child.depends_on},
            )

            return IntentResponse.model_validate(created)
        finally:
            session.close()

    @app.get("/api/v1/intents/{intent_id}/children")
    async def get_children(
        intent_id: str,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            intent = db.get_intent(session, intent_id)
            if not intent:
                raise HTTPException(status_code=404, detail="Intent not found")

            children = db.get_children(session, intent_id)
            return {
                "children": [
                    IntentResponse.model_validate(c).model_dump(mode="json")
                    for c in children
                ]
            }
        finally:
            session.close()

    @app.get("/api/v1/intents/{intent_id}/descendants")
    async def get_descendants(
        intent_id: str,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            intent = db.get_intent(session, intent_id)
            if not intent:
                raise HTTPException(status_code=404, detail="Intent not found")

            descendants = _get_descendants_recursive(session, db, intent_id)
            return {
                "descendants": [
                    IntentResponse.model_validate(d).model_dump(mode="json")
                    for d in descendants
                ]
            }
        finally:
            session.close()

    @app.get("/api/v1/intents/{intent_id}/ancestors")
    async def get_ancestors(
        intent_id: str,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            intent = db.get_intent(session, intent_id)
            if not intent:
                raise HTTPException(status_code=404, detail="Intent not found")

            ancestors = _get_ancestors_recursive(session, db, intent_id)
            return {
                "ancestors": [
                    IntentResponse.model_validate(a).model_dump(mode="json")
                    for a in ancestors
                ]
            }
        finally:
            session.close()

    @app.get("/api/v1/intents/{intent_id}/dependencies")
    async def get_dependencies(
        intent_id: str,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            intent = db.get_intent(session, intent_id)
            if not intent:
                raise HTTPException(status_code=404, detail="Intent not found")

            deps = db.get_dependencies(session, intent_id)
            return {
                "dependencies": [
                    IntentResponse.model_validate(d).model_dump(mode="json")
                    for d in deps
                ]
            }
        finally:
            session.close()

    @app.get("/api/v1/intents/{intent_id}/dependents")
    async def get_dependents(
        intent_id: str,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            intent = db.get_intent(session, intent_id)
            if not intent:
                raise HTTPException(status_code=404, detail="Intent not found")

            dependents = db.get_dependents(session, intent_id)
            return {
                "dependents": [
                    IntentResponse.model_validate(d).model_dump(mode="json")
                    for d in dependents
                ]
            }
        finally:
            session.close()

    @app.post("/api/v1/intents/{intent_id}/dependencies", response_model=IntentResponse)
    async def add_dependency(
        intent_id: str,
        request: DependencyAdd,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
        if_match: Optional[int] = Depends(get_version_header),
    ):
        if if_match is None:
            raise HTTPException(status_code=400, detail="If-Match header required")

        session = db.get_session()
        try:
            intent = db.get_intent(session, intent_id)
            if not intent:
                raise HTTPException(status_code=404, detail="Intent not found")

            dep = db.get_intent(session, request.dependency_id)
            if not dep:
                raise HTTPException(
                    status_code=404, detail="Dependency intent not found"
                )

            if intent.version != if_match:
                raise HTTPException(status_code=409, detail="Version conflict")

            current_deps = list(intent.depends_on or [])
            if request.dependency_id in current_deps:
                raise HTTPException(status_code=400, detail="Dependency already exists")

            new_deps = current_deps + [request.dependency_id]
            cycle = _detect_cycle(session, db, intent_id, new_deps)
            if cycle:
                raise HTTPException(
                    status_code=400, detail=f"Dependency would create cycle: {cycle}"
                )

            updated = db.add_dependency(
                session, intent_id, if_match, request.dependency_id
            )
            if not updated:
                raise HTTPException(status_code=409, detail="Version conflict")

            db.create_event(
                session,
                intent_id=intent_id,
                event_type="dependency_added",
                actor=api_key,
                payload={"dependency_id": request.dependency_id},
            )

            return IntentResponse.model_validate(updated)
        finally:
            session.close()

    @app.delete(
        "/api/v1/intents/{intent_id}/dependencies/{dependency_id}",
        response_model=IntentResponse,
    )
    async def remove_dependency(
        intent_id: str,
        dependency_id: str,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
        if_match: Optional[int] = Depends(get_version_header),
    ):
        if if_match is None:
            raise HTTPException(status_code=400, detail="If-Match header required")

        session = db.get_session()
        try:
            intent = db.get_intent(session, intent_id)
            if not intent:
                raise HTTPException(status_code=404, detail="Intent not found")

            if intent.version != if_match:
                raise HTTPException(status_code=409, detail="Version conflict")

            updated = db.remove_dependency(session, intent_id, if_match, dependency_id)
            if not updated:
                raise HTTPException(status_code=409, detail="Version conflict")

            db.create_event(
                session,
                intent_id=intent_id,
                event_type="dependency_removed",
                actor=api_key,
                payload={"dependency_id": dependency_id},
            )

            return IntentResponse.model_validate(updated)
        finally:
            session.close()

    @app.get("/api/v1/intents/{intent_id}/ready")
    async def get_ready_intents(
        intent_id: str,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            intent = db.get_intent(session, intent_id)
            if not intent:
                raise HTTPException(status_code=404, detail="Intent not found")

            children = db.get_children(session, intent_id)
            ready = [c for c in children if _all_dependencies_complete(session, db, c)]
            return {
                "ready": [
                    IntentResponse.model_validate(r).model_dump(mode="json")
                    for r in ready
                ]
            }
        finally:
            session.close()

    @app.get("/api/v1/intents/{intent_id}/blocked")
    async def get_blocked_intents(
        intent_id: str,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            intent = db.get_intent(session, intent_id)
            if not intent:
                raise HTTPException(status_code=404, detail="Intent not found")

            children = db.get_children(session, intent_id)
            blocked = [
                c for c in children if not _all_dependencies_complete(session, db, c)
            ]
            return {
                "blocked": [
                    IntentResponse.model_validate(b).model_dump(mode="json")
                    for b in blocked
                ]
            }
        finally:
            session.close()

    @app.get("/api/v1/intents/{intent_id}/graph")
    async def get_intent_graph(
        intent_id: str,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            intent = db.get_intent(session, intent_id)
            if not intent:
                raise HTTPException(status_code=404, detail="Intent not found")

            nodes = []
            edges = []
            visited = set()
            _build_graph(session, db, intent_id, nodes, edges, visited)

            completed = sum(1 for n in nodes if n.get("status") == "completed")
            total = len(nodes)

            return {
                "root_id": intent_id,
                "nodes": nodes,
                "edges": edges,
                "aggregate_status": {
                    "total": total,
                    "by_status": _count_by_status(nodes),
                    "completion_percentage": int(
                        (completed / total * 100) if total > 0 else 0
                    ),
                },
            }
        finally:
            session.close()

    def _detect_cycle(
        session, db: Database, intent_id: Optional[str], depends_on: List[str]
    ) -> Optional[str]:
        """Detect if adding dependencies would create a cycle."""
        visited = set()
        stack = list(depends_on)

        while stack:
            dep_id = stack.pop()
            if dep_id == intent_id:
                return f"{intent_id} -> {dep_id}"
            if dep_id in visited:
                continue
            visited.add(dep_id)

            dep = db.get_intent(session, dep_id)
            if dep and dep.depends_on:
                stack.extend(dep.depends_on)

        return None

    def _get_descendants_recursive(
        session, db: Database, intent_id: str
    ) -> List[IntentModel]:
        """Get all descendants of an intent recursively."""
        result = []
        children = db.get_children(session, intent_id)
        for child in children:
            result.append(child)
            result.extend(_get_descendants_recursive(session, db, child.id))
        return result

    def _get_ancestors_recursive(
        session, db: Database, intent_id: str
    ) -> List[IntentModel]:
        """Get all ancestors of an intent up to root."""
        result = []
        intent = db.get_intent(session, intent_id)
        if intent and intent.parent_id:
            parent = db.get_intent(session, intent.parent_id)
            if parent:
                result.append(parent)
                result.extend(_get_ancestors_recursive(session, db, parent.id))
        return result

    def _all_dependencies_complete(session, db: Database, intent: IntentModel) -> bool:
        """Check if all dependencies of an intent are complete."""
        if not intent.depends_on:
            return True
        for dep_id in intent.depends_on:
            dep = db.get_intent(session, dep_id)
            if not dep or dep.status != "completed":
                return False
        return True

    def _build_graph(
        session, db: Database, intent_id: str, nodes: List, edges: List, visited: set
    ):
        """Build graph structure from intent."""
        if intent_id in visited:
            return
        visited.add(intent_id)

        intent = db.get_intent(session, intent_id)
        if not intent:
            return

        nodes.append(
            {
                "id": intent.id,
                "title": intent.title,
                "status": intent.status,
                "parent_id": intent.parent_id,
                "depends_on": intent.depends_on or [],
            }
        )

        if intent.parent_id:
            edges.append({"from": intent.parent_id, "to": intent.id, "type": "parent"})

        for dep_id in intent.depends_on or []:
            edges.append({"from": dep_id, "to": intent.id, "type": "dependency"})
            _build_graph(session, db, dep_id, nodes, edges, visited)

        children = db.get_children(session, intent_id)
        for child in children:
            _build_graph(session, db, child.id, nodes, edges, visited)

    def _count_by_status(nodes: List) -> Dict[str, int]:
        """Count nodes by status."""
        counts: Dict[str, int] = {}
        for node in nodes:
            status = node.get("status", "unknown")
            counts[status] = counts.get(status, 0) + 1
        return counts

    @app.post("/api/v1/intents/{intent_id}/state", response_model=IntentResponse)
    async def patch_state(
        intent_id: str,
        request: StatePatchRequest,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
        if_match: Optional[int] = Depends(get_version_header),
    ):
        if if_match is None:
            raise HTTPException(status_code=400, detail="If-Match header required")

        session = db.get_session()
        try:
            patches = request.get_patches()
            updated = db.update_intent_state(session, intent_id, if_match, patches)

            if not updated:
                intent = db.get_intent(session, intent_id)
                if not intent:
                    raise HTTPException(status_code=404, detail="Intent not found")
                raise HTTPException(status_code=409, detail="Version conflict")

            db.create_event(
                session,
                intent_id=intent_id,
                event_type="state_patched",
                actor=api_key,
                payload={"patches": patches, "version": updated.version},
            )

            _broadcast_event(
                "intents",
                {
                    "type": "state_patched",
                    "intent_id": intent_id,
                    "data": IntentResponse.model_validate(updated).model_dump(
                        mode="json"
                    ),
                },
            )

            return IntentResponse.model_validate(updated)
        finally:
            session.close()

    @app.post("/api/v1/intents/{intent_id}/status", response_model=IntentResponse)
    async def update_status(
        intent_id: str,
        request: StatusUpdateRequest,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
        if_match: Optional[int] = Depends(get_version_header),
    ):
        if if_match is None:
            raise HTTPException(status_code=400, detail="If-Match header required")

        session = db.get_session()
        try:
            updated = db.update_intent_status(
                session, intent_id, if_match, request.status
            )

            if not updated:
                intent = db.get_intent(session, intent_id)
                if not intent:
                    raise HTTPException(status_code=404, detail="Intent not found")
                raise HTTPException(status_code=409, detail="Version conflict")

            db.create_event(
                session,
                intent_id=intent_id,
                event_type="status_changed",
                actor=api_key,
                payload={"status": request.status, "version": updated.version},
            )

            _broadcast_event(
                "intents",
                {
                    "type": "status_changed",
                    "intent_id": intent_id,
                    "data": IntentResponse.model_validate(updated).model_dump(
                        mode="json"
                    ),
                },
            )

            return IntentResponse.model_validate(updated)
        finally:
            session.close()

    @app.get("/api/v1/intents/{intent_id}/events", response_model=List[EventResponse])
    async def get_events(
        intent_id: str,
        limit: int = Query(100, ge=1, le=1000),
        offset: int = Query(0, ge=0),
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            events = db.get_events(session, intent_id, limit, offset)
            return [EventResponse.model_validate(e) for e in events]
        finally:
            session.close()

    @app.post("/api/v1/intents/{intent_id}/events", response_model=EventResponse)
    async def create_event(
        intent_id: str,
        event: EventCreate,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            intent = db.get_intent(session, intent_id)
            if not intent:
                raise HTTPException(status_code=404, detail="Intent not found")

            created = db.create_event(
                session,
                intent_id=intent_id,
                event_type=event.event_type,
                actor=event.actor,
                payload=event.payload,
            )

            _broadcast_event(
                "intents",
                {
                    "type": event.event_type,
                    "intent_id": intent_id,
                    "data": EventResponse.model_validate(created).model_dump(
                        mode="json"
                    ),
                },
            )

            return EventResponse.model_validate(created)
        finally:
            session.close()

    @app.get("/api/v1/intents/{intent_id}/agents", response_model=List[AgentResponse])
    async def get_agents(
        intent_id: str,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            agents = db.get_agents(session, intent_id)
            return [AgentResponse.model_validate(a) for a in agents]
        finally:
            session.close()

    @app.post("/api/v1/intents/{intent_id}/agents", response_model=AgentResponse)
    async def assign_agent(
        intent_id: str,
        agent: AgentAssign,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            intent = db.get_intent(session, intent_id)
            if not intent:
                raise HTTPException(status_code=404, detail="Intent not found")

            assigned = db.assign_agent(
                session,
                intent_id=intent_id,
                agent_id=agent.agent_id,
                role=agent.role,
            )

            db.create_event(
                session,
                intent_id=intent_id,
                event_type="agent_assigned",
                actor=api_key,
                payload={"agent_id": agent.agent_id, "role": agent.role},
            )

            _broadcast_event(
                "agents",
                {
                    "type": "agent_assigned",
                    "intent_id": intent_id,
                    "agent_id": agent.agent_id,
                    "data": AgentResponse.model_validate(assigned).model_dump(
                        mode="json"
                    ),
                },
            )

            return AgentResponse.model_validate(assigned)
        finally:
            session.close()

    @app.get("/api/v1/intents/{intent_id}/leases", response_model=List[LeaseResponse])
    async def get_leases(
        intent_id: str,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            leases = db.get_leases(session, intent_id)
            return [LeaseResponse.model_validate(lease) for lease in leases]
        finally:
            session.close()

    @app.post("/api/v1/intents/{intent_id}/leases", response_model=LeaseResponse)
    async def acquire_lease(
        intent_id: str,
        request: LeaseRequest,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            intent = db.get_intent(session, intent_id)
            if not intent:
                raise HTTPException(status_code=404, detail="Intent not found")

            lease = db.acquire_lease(
                session,
                intent_id=intent_id,
                agent_id=api_key,
                scope=request.scope,
                duration_seconds=request.duration_seconds,
            )

            if not lease:
                raise HTTPException(
                    status_code=409, detail="Lease already held for this scope"
                )

            db.create_event(
                session,
                intent_id=intent_id,
                event_type="lease_acquired",
                actor=api_key,
                payload={"scope": request.scope, "lease_id": lease.id},
            )

            return LeaseResponse.model_validate(lease)
        finally:
            session.close()

    @app.patch(
        "/api/v1/intents/{intent_id}/leases/{lease_id}", response_model=LeaseResponse
    )
    async def renew_lease(
        intent_id: str,
        lease_id: str,
        request: LeaseRenewRequest,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            renewed = db.renew_lease(
                session, lease_id, api_key, request.duration_seconds
            )
            if not renewed:
                raise HTTPException(
                    status_code=404, detail="Lease not found or not owned by you"
                )

            db.create_event(
                session,
                intent_id=intent_id,
                event_type="lease_renewed",
                actor=api_key,
                payload={
                    "lease_id": lease_id,
                    "duration_seconds": request.duration_seconds,
                },
            )

            return LeaseResponse.model_validate(renewed)
        finally:
            session.close()

    @app.delete("/api/v1/intents/{intent_id}/leases/{lease_id}")
    async def release_lease(
        intent_id: str,
        lease_id: str,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            released = db.release_lease(session, lease_id, api_key)
            if not released:
                raise HTTPException(
                    status_code=404, detail="Lease not found or not owned by you"
                )

            db.create_event(
                session,
                intent_id=intent_id,
                event_type="lease_released",
                actor=api_key,
                payload={"lease_id": lease_id},
            )

            return {"message": "Lease released"}
        finally:
            session.close()

    @app.get(
        "/api/v1/intents/{intent_id}/attachments",
        response_model=List[AttachmentResponse],
    )
    async def get_attachments(
        intent_id: str,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            attachments = db.get_attachments(session, intent_id)
            return [AttachmentResponse.model_validate(a) for a in attachments]
        finally:
            session.close()

    @app.post(
        "/api/v1/intents/{intent_id}/attachments", response_model=AttachmentResponse
    )
    async def create_attachment(
        intent_id: str,
        attachment: AttachmentCreate,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            intent = db.get_intent(session, intent_id)
            if not intent:
                raise HTTPException(status_code=404, detail="Intent not found")

            created = db.create_attachment(
                session,
                intent_id=intent_id,
                filename=attachment.filename,
                mime_type=attachment.mime_type,
                size=attachment.size,
                storage_url=attachment.storage_url,
                created_by=api_key,
            )

            return AttachmentResponse.model_validate(created)
        finally:
            session.close()

    @app.delete("/api/v1/intents/{intent_id}/attachments/{attachment_id}")
    async def delete_attachment(
        intent_id: str,
        attachment_id: str,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            deleted = db.delete_attachment(session, attachment_id)
            if not deleted:
                raise HTTPException(status_code=404, detail="Attachment not found")
            return Response(status_code=204)
        finally:
            session.close()

    @app.get(
        "/api/v1/intents/{intent_id}/portfolios", response_model=List[PortfolioResponse]
    )
    async def get_intent_portfolios(
        intent_id: str,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            portfolios = db.get_intent_portfolios(session, intent_id)
            return [PortfolioResponse.model_validate(p) for p in portfolios]
        finally:
            session.close()

    @app.get("/api/v1/intents/{intent_id}/costs", response_model=List[CostResponse])
    async def get_costs(
        intent_id: str,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            costs = db.get_costs(session, intent_id)
            return [CostResponse.model_validate(c) for c in costs]
        finally:
            session.close()

    @app.post("/api/v1/intents/{intent_id}/costs", response_model=CostResponse)
    async def record_cost(
        intent_id: str,
        cost: CostRecord,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            intent = db.get_intent(session, intent_id)
            if not intent:
                raise HTTPException(status_code=404, detail="Intent not found")

            created = db.record_cost(
                session,
                intent_id=intent_id,
                agent_id=cost.agent_id,
                cost_type=cost.cost_type,
                amount=cost.amount,
                unit=cost.unit,
                provider=cost.provider,
                cost_metadata=cost.cost_metadata,
            )

            return CostResponse.model_validate(created)
        finally:
            session.close()

    @app.get(
        "/api/v1/intents/{intent_id}/retry-policy", response_model=RetryPolicyResponse
    )
    async def get_retry_policy(
        intent_id: str,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            policy = db.get_retry_policy(session, intent_id)
            if not policy:
                raise HTTPException(status_code=404, detail="No retry policy set")
            return RetryPolicyResponse.model_validate(policy)
        finally:
            session.close()

    @app.put(
        "/api/v1/intents/{intent_id}/retry-policy", response_model=RetryPolicyResponse
    )
    async def set_retry_policy(
        intent_id: str,
        policy: RetryPolicyCreate,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            intent = db.get_intent(session, intent_id)
            if not intent:
                raise HTTPException(status_code=404, detail="Intent not found")

            created = db.set_retry_policy(
                session,
                intent_id=intent_id,
                strategy=policy.strategy,
                max_retries=policy.max_retries,
                base_delay_ms=policy.base_delay_ms,
                max_delay_ms=policy.max_delay_ms,
                jitter=policy.jitter,
            )

            return RetryPolicyResponse.model_validate(created)
        finally:
            session.close()

    @app.get("/api/v1/intents/{intent_id}/failures")
    async def get_failures(
        intent_id: str,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            failures = db.get_failures(session, intent_id)
            return failures
        finally:
            session.close()

    @app.post("/api/v1/intents/{intent_id}/failures")
    async def record_failure(
        intent_id: str,
        failure: FailureRecord,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            intent = db.get_intent(session, intent_id)
            if not intent:
                raise HTTPException(status_code=404, detail="Intent not found")

            created = db.record_failure(
                session,
                intent_id=intent_id,
                error_type=failure.error_type,
                error_message=failure.error_message,
                attempt_number=failure.attempt_number,
                agent_id=failure.agent_id,
            )

            return created
        finally:
            session.close()

    # ==================== Access Control (RFC-0011) ====================

    @app.get("/api/v1/intents/{intent_id}/acl")
    async def get_acl(
        intent_id: str,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            intent = db.get_intent(session, intent_id)
            if not intent:
                raise HTTPException(status_code=404, detail="Intent not found")

            acl_data = db.get_acl(session, intent_id)
            return {
                "intent_id": intent_id,
                "default_policy": acl_data["default_policy"],
                "entries": [
                    ACLEntryResponse.model_validate(e).model_dump(mode="json")
                    for e in acl_data["entries"]
                ],
            }
        finally:
            session.close()

    @app.put("/api/v1/intents/{intent_id}/acl")
    async def set_acl(
        intent_id: str,
        acl_request: ACLSetRequest,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            intent = db.get_intent(session, intent_id)
            if not intent:
                raise HTTPException(status_code=404, detail="Intent not found")

            result = db.set_acl(
                session,
                intent_id,
                default_policy=acl_request.default_policy,
                entries=[e for e in acl_request.entries],
            )

            db.create_event(
                session,
                intent_id=intent_id,
                event_type="access_granted",
                actor=api_key,
                payload={
                    "action": "acl_set",
                    "default_policy": acl_request.default_policy,
                },
            )

            return {
                "intent_id": intent_id,
                "default_policy": result["default_policy"],
                "entries": [
                    ACLEntryResponse.model_validate(e).model_dump(mode="json")
                    for e in result["entries"]
                ],
            }
        finally:
            session.close()

    @app.post("/api/v1/intents/{intent_id}/acl/entries")
    async def grant_access(
        intent_id: str,
        entry: ACLEntryCreate,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            intent = db.get_intent(session, intent_id)
            if not intent:
                raise HTTPException(status_code=404, detail="Intent not found")

            acl_entry = db.grant_access(
                session,
                intent_id=intent_id,
                granted_by=api_key,
                principal_id=entry.principal_id,
                principal_type=entry.principal_type,
                permission=entry.permission,
                reason=entry.reason,
                expires_at=entry.expires_at,
            )

            db.create_event(
                session,
                intent_id=intent_id,
                event_type="access_granted",
                actor=api_key,
                payload={
                    "principal_id": entry.principal_id,
                    "permission": entry.permission,
                },
            )

            _broadcast_event(
                "intents",
                {
                    "type": "access_granted",
                    "intent_id": intent_id,
                    "data": {
                        "principal_id": entry.principal_id,
                        "permission": entry.permission,
                    },
                },
            )

            return ACLEntryResponse.model_validate(acl_entry)
        finally:
            session.close()

    @app.delete("/api/v1/intents/{intent_id}/acl/entries/{entry_id}", status_code=204)
    async def revoke_access(
        intent_id: str,
        entry_id: str,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            entry = db.get_acl_entry(session, entry_id)
            principal_id = entry.principal_id if entry else "unknown"

            success = db.revoke_access(session, intent_id, entry_id)
            if not success:
                raise HTTPException(status_code=404, detail="ACL entry not found")

            db.create_event(
                session,
                intent_id=intent_id,
                event_type="access_revoked",
                actor=api_key,
                payload={"entry_id": entry_id, "principal_id": principal_id},
            )

            _broadcast_event(
                "intents",
                {
                    "type": "access_revoked",
                    "intent_id": intent_id,
                    "data": {"entry_id": entry_id, "principal_id": principal_id},
                },
            )

            return Response(status_code=204)
        finally:
            session.close()

    @app.post("/api/v1/intents/{intent_id}/access-requests")
    async def create_access_request(
        intent_id: str,
        request_body: AccessRequestCreate,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            intent = db.get_intent(session, intent_id)
            if not intent:
                raise HTTPException(status_code=404, detail="Intent not found")

            access_request = db.create_access_request(
                session,
                intent_id=intent_id,
                principal_id=request_body.principal_id,
                principal_type=request_body.principal_type,
                requested_permission=request_body.requested_permission,
                reason=request_body.reason,
                capabilities=request_body.capabilities,
            )

            db.create_event(
                session,
                intent_id=intent_id,
                event_type="access_requested",
                actor=request_body.principal_id,
                payload={
                    "request_id": access_request.id,
                    "requested_permission": request_body.requested_permission,
                    "capabilities": request_body.capabilities,
                },
            )

            _broadcast_event(
                "intents",
                {
                    "type": "access_requested",
                    "intent_id": intent_id,
                    "data": {
                        "request_id": access_request.id,
                        "principal_id": request_body.principal_id,
                        "requested_permission": request_body.requested_permission,
                    },
                },
            )

            return AccessRequestResponse.model_validate(access_request)
        finally:
            session.close()

    @app.get("/api/v1/intents/{intent_id}/access-requests")
    async def list_access_requests(
        intent_id: str,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            intent = db.get_intent(session, intent_id)
            if not intent:
                raise HTTPException(status_code=404, detail="Intent not found")

            requests = db.get_access_requests(session, intent_id)
            return {
                "access_requests": [
                    AccessRequestResponse.model_validate(r).model_dump(mode="json")
                    for r in requests
                ]
            }
        finally:
            session.close()

    @app.post("/api/v1/intents/{intent_id}/access-requests/{request_id}/approve")
    async def approve_access_request(
        intent_id: str,
        request_id: str,
        decision: AccessRequestDecision,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            result = db.approve_access_request(
                session,
                request_id=request_id,
                decided_by=decision.decided_by,
                permission=decision.permission,
                expires_at=decision.expires_at,
                reason=decision.reason,
            )
            if not result:
                raise HTTPException(
                    status_code=404,
                    detail="Access request not found or already decided",
                )

            db.create_event(
                session,
                intent_id=intent_id,
                event_type="access_request_approved",
                actor=decision.decided_by,
                payload={
                    "request_id": request_id,
                    "principal_id": result.principal_id,
                    "permission": decision.permission or result.requested_permission,
                },
            )

            _broadcast_event(
                "intents",
                {
                    "type": "access_request_approved",
                    "intent_id": intent_id,
                    "data": {
                        "request_id": request_id,
                        "principal_id": result.principal_id,
                    },
                },
            )

            return AccessRequestResponse.model_validate(result)
        finally:
            session.close()

    @app.post("/api/v1/intents/{intent_id}/access-requests/{request_id}/deny")
    async def deny_access_request(
        intent_id: str,
        request_id: str,
        decision: AccessRequestDecision,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            result = db.deny_access_request(
                session,
                request_id=request_id,
                decided_by=decision.decided_by,
                reason=decision.reason,
            )
            if not result:
                raise HTTPException(
                    status_code=404,
                    detail="Access request not found or already decided",
                )

            db.create_event(
                session,
                intent_id=intent_id,
                event_type="access_request_denied",
                actor=decision.decided_by,
                payload={
                    "request_id": request_id,
                    "principal_id": result.principal_id,
                    "reason": decision.reason,
                },
            )

            return AccessRequestResponse.model_validate(result)
        finally:
            session.close()

    @app.post("/api/v1/portfolios", response_model=PortfolioResponse)
    async def create_portfolio(
        portfolio: PortfolioCreate,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            created = db.create_portfolio(
                session,
                name=portfolio.name,
                description=portfolio.description,
                created_by=portfolio.created_by,
                governance_policy=portfolio.governance_policy,
            )

            _broadcast_event(
                "portfolios",
                {
                    "type": "portfolio_created",
                    "portfolio_id": created.id,
                    "data": PortfolioResponse.model_validate(created).model_dump(
                        mode="json"
                    ),
                },
            )

            return PortfolioResponse.model_validate(created)
        finally:
            session.close()

    @app.get("/api/v1/portfolios", response_model=List[PortfolioResponse])
    async def list_portfolios(
        created_by: Optional[str] = None,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            portfolios = db.list_portfolios(session, created_by)
            return [PortfolioResponse.model_validate(p) for p in portfolios]
        finally:
            session.close()

    @app.get("/api/v1/portfolios/{portfolio_id}", response_model=PortfolioResponse)
    async def get_portfolio(
        portfolio_id: str,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            portfolio = db.get_portfolio(session, portfolio_id)
            if not portfolio:
                raise HTTPException(status_code=404, detail="Portfolio not found")
            return PortfolioResponse.model_validate(portfolio)
        finally:
            session.close()

    @app.patch(
        "/api/v1/portfolios/{portfolio_id}/status", response_model=PortfolioResponse
    )
    async def update_portfolio_status(
        portfolio_id: str,
        request: PortfolioStatusRequest,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            portfolio = db.update_portfolio_status(
                session, portfolio_id, request.status
            )
            if not portfolio:
                raise HTTPException(status_code=404, detail="Portfolio not found")
            return PortfolioResponse.model_validate(portfolio)
        finally:
            session.close()

    @app.get(
        "/api/v1/portfolios/{portfolio_id}/intents", response_model=List[IntentResponse]
    )
    async def get_portfolio_intents(
        portfolio_id: str,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            intents = db.get_portfolio_intents(session, portfolio_id)
            return [IntentResponse.model_validate(i) for i in intents]
        finally:
            session.close()

    @app.post("/api/v1/portfolios/{portfolio_id}/intents")
    async def add_intent_to_portfolio(
        portfolio_id: str,
        membership: PortfolioMembershipCreate,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            portfolio = db.get_portfolio(session, portfolio_id)
            if not portfolio:
                raise HTTPException(status_code=404, detail="Portfolio not found")

            intent = db.get_intent(session, membership.intent_id)
            if not intent:
                raise HTTPException(status_code=404, detail="Intent not found")

            created = db.add_intent_to_portfolio(
                session,
                portfolio_id=portfolio_id,
                intent_id=membership.intent_id,
                role=membership.role,
                priority=membership.priority,
            )

            _broadcast_event(
                "portfolios",
                {
                    "type": "intent_added",
                    "portfolio_id": portfolio_id,
                    "intent_id": membership.intent_id,
                },
            )

            return {"message": "Intent added to portfolio", "membership_id": created.id}
        finally:
            session.close()

    @app.delete("/api/v1/portfolios/{portfolio_id}/intents/{intent_id}")
    async def remove_intent_from_portfolio(
        portfolio_id: str,
        intent_id: str,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            removed = db.remove_intent_from_portfolio(session, portfolio_id, intent_id)
            if not removed:
                raise HTTPException(status_code=404, detail="Membership not found")

            _broadcast_event(
                "portfolios",
                {
                    "type": "intent_removed",
                    "portfolio_id": portfolio_id,
                    "intent_id": intent_id,
                },
            )

            return {"message": "Intent removed from portfolio"}
        finally:
            session.close()

    @app.get("/api/v1/subscribe/intents/{intent_id}")
    async def subscribe_intent(
        intent_id: str,
        request: Request,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        """SSE subscription for intent events."""
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        _event_queues["intents"].append(queue)

        async def event_generator():
            try:
                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        event = await asyncio.wait_for(queue.get(), timeout=30.0)
                        if event.get("intent_id") == intent_id:
                            yield {
                                "event": event.get("type", "message"),
                                "data": str(event.get("data", {})),
                            }
                    except asyncio.TimeoutError:
                        yield {"event": "ping", "data": ""}
            finally:
                _event_queues["intents"].remove(queue)

        return EventSourceResponse(event_generator())

    @app.get("/api/v1/subscribe/portfolios/{portfolio_id}")
    async def subscribe_portfolio(
        portfolio_id: str,
        request: Request,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        """SSE subscription for portfolio events."""
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        _event_queues["portfolios"].append(queue)

        async def event_generator():
            try:
                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        event = await asyncio.wait_for(queue.get(), timeout=30.0)
                        if event.get("portfolio_id") == portfolio_id:
                            yield {
                                "event": event.get("type", "message"),
                                "data": str(event.get("data", {})),
                            }
                    except asyncio.TimeoutError:
                        yield {"event": "ping", "data": ""}
            finally:
                _event_queues["portfolios"].remove(queue)

        return EventSourceResponse(event_generator())

    @app.get("/api/v1/subscribe/agents/{agent_id}")
    async def subscribe_agent(
        agent_id: str,
        request: Request,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        """SSE subscription for agent events."""
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        _event_queues["agents"].append(queue)

        async def event_generator():
            try:
                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        event = await asyncio.wait_for(queue.get(), timeout=30.0)
                        if event.get("agent_id") == agent_id:
                            yield {
                                "event": event.get("type", "message"),
                                "data": str(event.get("data", {})),
                            }
                    except asyncio.TimeoutError:
                        yield {"event": "ping", "data": ""}
            finally:
                _event_queues["agents"].remove(queue)

        return EventSourceResponse(event_generator())

    @app.post("/api/v1/intents/{intent_id}/arbitrate")
    async def request_arbitration(
        intent_id: str,
        request: ArbitrationRequest,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            intent = db.get_intent(session, intent_id)
            if not intent:
                raise HTTPException(status_code=404, detail="Intent not found")

            db.create_event(
                session,
                intent_id=intent_id,
                event_type="arbitration_requested",
                actor=request.requested_by,
                payload={
                    "reason": request.reason,
                    "context": request.context,
                },
            )

            return {"message": "Arbitration requested", "status": "pending"}
        finally:
            session.close()

    @app.post("/api/v1/intents/{intent_id}/decisions")
    async def record_decision(
        intent_id: str,
        decision: DecisionRecord,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            intent = db.get_intent(session, intent_id)
            if not intent:
                raise HTTPException(status_code=404, detail="Intent not found")

            event = db.create_event(
                session,
                intent_id=intent_id,
                event_type="decision_recorded",
                actor=decision.decided_by,
                payload={
                    "decision_type": decision.decision_type,
                    "outcome": decision.outcome,
                    "rationale": decision.rationale,
                },
            )

            return {
                "message": "Decision recorded",
                "decision_id": event.id,
                "outcome": decision.outcome,
            }
        finally:
            session.close()

    # ==================== Tasks (RFC-0012) ====================

    @app.post("/api/v1/tasks", response_model=TaskResponse)
    async def create_task(
        task: TaskCreate,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            intent = db.get_intent(session, task.intent_id)
            if not intent:
                raise HTTPException(status_code=404, detail="Intent not found")

            created = db.create_task(
                session,
                intent_id=task.intent_id,
                name=task.name,
                plan_id=task.plan_id,
                description=task.description,
                priority=task.priority,
                input=task.input,
                capabilities_required=task.capabilities_required,
                depends_on=task.depends_on,
                parent_task_id=task.parent_task_id,
                timeout_seconds=task.timeout_seconds,
                max_attempts=task.max_attempts,
                permissions=task.permissions,
                memory_policy=task.memory_policy,
                requires_tools=task.requires_tools,
                task_metadata=task.metadata,
            )
            return TaskResponse.model_validate(created)
        finally:
            session.close()

    @app.get("/api/v1/tasks/{task_id}", response_model=TaskResponse)
    async def get_task(
        task_id: str,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            task = db.get_task(session, task_id)
            if not task:
                raise HTTPException(status_code=404, detail="Task not found")
            return TaskResponse.model_validate(task)
        finally:
            session.close()

    @app.get("/api/v1/intents/{intent_id}/tasks", response_model=List[TaskResponse])
    async def list_intent_tasks(
        intent_id: str,
        status: Optional[str] = Query(None),
        limit: int = Query(100),
        offset: int = Query(0),
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            tasks = db.list_tasks(
                session, intent_id, status=status, limit=limit, offset=offset
            )
            return [TaskResponse.model_validate(t) for t in tasks]
        finally:
            session.close()

    @app.patch("/api/v1/tasks/{task_id}", response_model=TaskResponse)
    async def update_task_status(
        task_id: str,
        update: TaskStatusUpdate,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
        if_match: Optional[int] = Depends(get_version_header),
    ):
        session = db.get_session()
        try:
            if if_match is None:
                raise HTTPException(status_code=428, detail="If-Match header required")

            kwargs = {}
            if update.assigned_agent is not None:
                kwargs["assigned_agent"] = update.assigned_agent
            if update.output is not None:
                kwargs["output"] = update.output
            if update.error is not None:
                kwargs["error"] = update.error
            if update.blocked_reason is not None:
                kwargs["blocked_reason"] = update.blocked_reason

            updated = db.update_task_status(
                session, task_id, if_match, update.status, **kwargs
            )
            if not updated:
                raise HTTPException(
                    status_code=409, detail="Version conflict or task not found"
                )
            return TaskResponse.model_validate(updated)
        finally:
            session.close()

    # ==================== Plans (RFC-0012) ====================

    @app.post("/api/v1/plans", response_model=PlanResponse)
    async def create_plan(
        plan: PlanCreate,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            intent = db.get_intent(session, plan.intent_id)
            if not intent:
                raise HTTPException(status_code=404, detail="Intent not found")

            created = db.create_plan(
                session,
                intent_id=plan.intent_id,
                tasks=plan.tasks,
                checkpoints=plan.checkpoints,
                conditions=plan.conditions,
                on_failure=plan.on_failure,
                on_complete=plan.on_complete,
                plan_metadata=plan.metadata,
            )
            return PlanResponse.model_validate(created)
        finally:
            session.close()

    @app.get("/api/v1/plans/{plan_id}", response_model=PlanResponse)
    async def get_plan(
        plan_id: str,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            plan = db.get_plan(session, plan_id)
            if not plan:
                raise HTTPException(status_code=404, detail="Plan not found")
            return PlanResponse.model_validate(plan)
        finally:
            session.close()

    @app.get("/api/v1/intents/{intent_id}/plans", response_model=List[PlanResponse])
    async def list_intent_plans(
        intent_id: str,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            plans = db.list_plans(session, intent_id)
            return [PlanResponse.model_validate(p) for p in plans]
        finally:
            session.close()

    @app.patch("/api/v1/plans/{plan_id}", response_model=PlanResponse)
    async def update_plan(
        plan_id: str,
        update: PlanUpdate,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
        if_match: Optional[int] = Depends(get_version_header),
    ):
        session = db.get_session()
        try:
            if if_match is None:
                raise HTTPException(status_code=428, detail="If-Match header required")

            kwargs = {}
            if update.state is not None:
                kwargs["state"] = update.state
            if update.tasks is not None:
                kwargs["tasks"] = update.tasks
            if update.checkpoints is not None:
                kwargs["checkpoints"] = update.checkpoints

            updated = db.update_plan(session, plan_id, if_match, **kwargs)
            if not updated:
                raise HTTPException(
                    status_code=409, detail="Version conflict or plan not found"
                )
            return PlanResponse.model_validate(updated)
        finally:
            session.close()

    # ==================== Coordinator Governance (RFC-0013) ====================

    @app.post("/api/v1/coordinators", response_model=CoordinatorLeaseResponse)
    async def create_coordinator_lease(
        lease: CoordinatorLeaseCreate,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            created = db.create_coordinator_lease(
                session,
                agent_id=lease.agent_id,
                intent_id=lease.intent_id,
                portfolio_id=lease.portfolio_id,
                role=lease.role,
                supervisor_id=lease.supervisor_id,
                coordinator_type=lease.coordinator_type,
                scope=lease.scope,
                guardrails=lease.guardrails,
                heartbeat_interval_seconds=lease.heartbeat_interval_seconds,
                expires_at=lease.expires_at,
                lease_metadata=lease.metadata,
            )
            return CoordinatorLeaseResponse.model_validate(created)
        finally:
            session.close()

    @app.get("/api/v1/coordinators/{lease_id}", response_model=CoordinatorLeaseResponse)
    async def get_coordinator_lease(
        lease_id: str,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            lease = db.get_coordinator_lease(session, lease_id)
            if not lease:
                raise HTTPException(
                    status_code=404, detail="Coordinator lease not found"
                )
            return CoordinatorLeaseResponse.model_validate(lease)
        finally:
            session.close()

    @app.get(
        "/api/v1/intents/{intent_id}/coordinators",
        response_model=List[CoordinatorLeaseResponse],
    )  # noqa: E501
    async def list_intent_coordinators(
        intent_id: str,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            leases = db.list_coordinator_leases(session, intent_id=intent_id)
            return [CoordinatorLeaseResponse.model_validate(item) for item in leases]
        finally:
            session.close()

    @app.post("/api/v1/coordinators/{lease_id}/heartbeat")
    async def coordinator_heartbeat(
        lease_id: str,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            lease = db.get_coordinator_lease(session, lease_id)
            if not lease:
                raise HTTPException(
                    status_code=404, detail="Coordinator lease not found"
                )

            updated = db.update_coordinator_heartbeat(session, lease_id, lease.agent_id)
            if not updated:
                raise HTTPException(
                    status_code=404, detail="Coordinator lease not found"
                )

            next_heartbeat = datetime.utcnow() + timedelta(
                seconds=updated.heartbeat_interval_seconds
            )  # noqa: E501
            return {"status": "ok", "next_heartbeat_at": next_heartbeat.isoformat()}
        finally:
            session.close()

    @app.post("/api/v1/decisions", response_model=DecisionRecordResponse)
    async def create_decision_record(
        decision: DecisionRecordCreate,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            created = db.create_decision_record(
                session,
                coordinator_id=decision.coordinator_id,
                intent_id=decision.intent_id,
                decision_type=decision.decision_type,
                summary=decision.summary,
                rationale=decision.rationale,
                alternatives_considered=decision.alternatives_considered,
                confidence=decision.confidence,
            )
            return DecisionRecordResponse.model_validate(created)
        finally:
            session.close()

    @app.get(
        "/api/v1/intents/{intent_id}/decisions",
        response_model=List[DecisionRecordResponse],
    )
    async def list_intent_decisions(
        intent_id: str,
        limit: int = Query(50),
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            records = db.list_decision_records(session, intent_id, limit=limit)
            return [DecisionRecordResponse.model_validate(r) for r in records]
        finally:
            session.close()

    # ==================== Credential Vaults & Tool Scoping (RFC-0014) ====================

    @app.post("/api/v1/vaults", response_model=VaultResponse)
    async def create_vault(
        vault: VaultCreate,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            created = db.create_vault(
                session,
                owner_id=vault.owner_id,
                name=vault.name,
            )
            return VaultResponse.model_validate(created)
        finally:
            session.close()

    @app.get("/api/v1/vaults/{vault_id}", response_model=VaultResponse)
    async def get_vault(
        vault_id: str,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            vault = db.get_vault(session, vault_id)
            if not vault:
                raise HTTPException(status_code=404, detail="Vault not found")
            return VaultResponse.model_validate(vault)
        finally:
            session.close()

    @app.post("/api/v1/credentials", response_model=CredentialResponse)
    async def create_credential(
        credential: CredentialCreate,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            vault = db.get_vault(session, credential.vault_id)
            if not vault:
                raise HTTPException(status_code=404, detail="Vault not found")

            created = db.create_credential(
                session,
                vault_id=credential.vault_id,
                service=credential.service,
                label=credential.label,
                auth_type=credential.auth_type,
                scopes_available=credential.scopes_available,
                credential_metadata=credential.metadata,
            )
            return CredentialResponse.model_validate(created)
        finally:
            session.close()

    @app.get("/api/v1/credentials/{credential_id}", response_model=CredentialResponse)
    async def get_credential(
        credential_id: str,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            credential = db.get_credential(session, credential_id)
            if not credential:
                raise HTTPException(status_code=404, detail="Credential not found")
            return CredentialResponse.model_validate(credential)
        finally:
            session.close()

    @app.post("/api/v1/grants", response_model=GrantResponse)
    async def create_grant(
        grant: GrantCreate,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            credential = db.get_credential(session, grant.credential_id)
            if not credential:
                raise HTTPException(status_code=404, detail="Credential not found")

            created = db.create_tool_grant(
                session,
                credential_id=grant.credential_id,
                agent_id=grant.agent_id,
                granted_by=grant.granted_by,
                scopes=grant.scopes,
                constraints=grant.constraints,
                delegatable=grant.delegatable,
                context=grant.context,
                expires_at=grant.expires_at,
            )
            return GrantResponse.model_validate(created)
        finally:
            session.close()

    @app.get("/api/v1/grants/{grant_id}", response_model=GrantResponse)
    async def get_grant(
        grant_id: str,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            grant = db.get_tool_grant(session, grant_id)
            if not grant:
                raise HTTPException(status_code=404, detail="Grant not found")
            return GrantResponse.model_validate(grant)
        finally:
            session.close()

    @app.get("/api/v1/agents/{agent_id}/grants", response_model=List[GrantResponse])
    async def list_agent_grants(
        agent_id: str,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            grants = db.list_agent_grants(session, agent_id)
            return [GrantResponse.model_validate(g) for g in grants]
        finally:
            session.close()

    @app.delete("/api/v1/grants/{grant_id}")
    async def revoke_grant(
        grant_id: str,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            revoked = db.revoke_grant(session, grant_id)
            if not revoked:
                raise HTTPException(status_code=404, detail="Grant not found")
            return {"status": "revoked", "grant_id": grant_id}
        finally:
            session.close()

    @app.post("/api/v1/invocations", response_model=InvocationResponse)
    async def create_invocation(
        invocation: InvocationCreate,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            grant = db.get_tool_grant(session, invocation.grant_id)
            if not grant:
                raise HTTPException(status_code=404, detail="Grant not found")

            created = db.create_tool_invocation(
                session,
                grant_id=invocation.grant_id,
                service=invocation.service,
                tool=invocation.tool,
                agent_id=invocation.agent_id,
                parameters=invocation.parameters,
                status=invocation.status,
                result=invocation.result,
                error=invocation.error,
                cost=invocation.cost,
                duration_ms=invocation.duration_ms,
                idempotency_key=invocation.idempotency_key,
                context=invocation.context,
            )
            return InvocationResponse.model_validate(created)
        finally:
            session.close()

    @app.get(
        "/api/v1/grants/{grant_id}/invocations", response_model=List[InvocationResponse]
    )
    async def list_grant_invocations(
        grant_id: str,
        limit: int = Query(50),
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            invocations = db.list_tool_invocations(session, grant_id, limit=limit)
            return [InvocationResponse.model_validate(i) for i in invocations]
        finally:
            session.close()

    # ==================== Tool Invoke Proxy (RFC-0014) ====================

    @app.post("/api/v1/tools/invoke", response_model=ToolInvokeResponse)
    async def invoke_tool(
        request: ToolInvokeRequest,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        """Invoke a tool through the server's tool proxy (RFC-0014).

        The server resolves the agent's grant, retrieves the credential,
        and records the invocation. For now, tool execution is stubbed
        — the server validates grant access and records the invocation
        with a placeholder result. External tool execution adapters
        will be added in a future release.
        """
        import time
        from uuid import uuid4

        session = db.get_session()
        try:
            grant = db.find_agent_grant_for_tool(
                session, request.agent_id, request.tool_name
            )
            if not grant:
                raise HTTPException(
                    status_code=403,
                    detail=f"No active grant found for agent '{request.agent_id}' to use tool '{request.tool_name}'"
                )

            if grant.expires_at and grant.expires_at < datetime.utcnow():
                raise HTTPException(
                    status_code=403,
                    detail=f"Grant for tool '{request.tool_name}' has expired"
                )

            credential = db.get_credential(session, grant.credential_id)
            if not credential:
                raise HTTPException(
                    status_code=500,
                    detail="Grant references a missing credential"
                )
            if credential.status != "active":
                raise HTTPException(
                    status_code=403,
                    detail=f"Credential for tool '{request.tool_name}' is {credential.status}"
                )

            if grant.constraints and isinstance(grant.constraints, dict):
                max_per_hour = grant.constraints.get("max_invocations_per_hour")
                if max_per_hour is not None:
                    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
                    recent_count = (
                        session.query(ToolInvocationModel)
                        .filter(
                            ToolInvocationModel.grant_id == grant.id,
                            ToolInvocationModel.timestamp >= one_hour_ago,
                        )
                        .count()
                    )
                    if recent_count >= max_per_hour:
                        raise HTTPException(
                            status_code=429,
                            detail=f"Rate limit exceeded: {max_per_hour} invocations per hour"
                        )

            invocation_id = str(uuid4())
            t0 = time.time()

            tool_result = {
                "tool_name": request.tool_name,
                "service": credential.service,
                "parameters": request.parameters,
                "message": f"Tool '{request.tool_name}' invoked via server proxy",
                "credential_service": credential.service,
                "credential_auth_type": credential.auth_type,
            }

            duration_ms = int((time.time() - t0) * 1000)

            db.create_tool_invocation(
                session,
                grant_id=grant.id,
                service=credential.service,
                tool=request.tool_name,
                agent_id=request.agent_id,
                parameters=request.parameters,
                status="success",
                result=tool_result,
                duration_ms=duration_ms,
                idempotency_key=request.idempotency_key,
            )

            return ToolInvokeResponse(
                invocation_id=invocation_id,
                tool_name=request.tool_name,
                status="success",
                result=tool_result,
                duration_ms=duration_ms,
            )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            session.close()

    # ==================== Agent Memory (RFC-0015) ====================

    @app.post("/api/v1/memory", response_model=MemoryEntryResponse)
    async def create_memory_entry(
        entry: MemoryEntryCreate,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            created = db.create_memory_entry(
                session,
                agent_id=entry.agent_id,
                namespace=entry.namespace,
                key=entry.key,
                value=entry.value,
                memory_type=entry.memory_type,
                scope=entry.scope,
                tags=entry.tags,
                ttl=entry.ttl,
                pinned=entry.pinned,
                priority=entry.priority,
                sensitivity=entry.sensitivity,
            )
            return MemoryEntryResponse.model_validate(created)
        finally:
            session.close()

    @app.get("/api/v1/memory/{entry_id}", response_model=MemoryEntryResponse)
    async def get_memory_entry(
        entry_id: str,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            entry = db.get_memory_entry(session, entry_id)
            if not entry:
                raise HTTPException(status_code=404, detail="Memory entry not found")
            return MemoryEntryResponse.model_validate(entry)
        finally:
            session.close()

    @app.get(
        "/api/v1/agents/{agent_id}/memory", response_model=List[MemoryEntryResponse]
    )
    async def list_agent_memory(
        agent_id: str,
        namespace: Optional[str] = Query(None),
        memory_type: Optional[str] = Query(None),
        tags: Optional[str] = Query(None),
        limit: int = Query(100),
        offset: int = Query(0),
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            tag_list = tags.split(",") if tags else None
            entries = db.list_memory_entries(
                session,
                agent_id,
                namespace=namespace,
                memory_type=memory_type,
                tags=tag_list,
                limit=limit,
            )
            return [MemoryEntryResponse.model_validate(e) for e in entries]
        finally:
            session.close()

    @app.patch("/api/v1/memory/{entry_id}", response_model=MemoryEntryResponse)
    async def update_memory_entry(
        entry_id: str,
        update: MemoryEntryUpdate,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
        if_match: Optional[int] = Depends(get_version_header),
    ):
        session = db.get_session()
        try:
            if if_match is None:
                raise HTTPException(status_code=428, detail="If-Match header required")

            kwargs = {}
            if update.value is not None:
                kwargs["value"] = update.value
            if update.tags is not None:
                kwargs["tags"] = update.tags
            if update.pinned is not None:
                kwargs["pinned"] = update.pinned
            if update.priority is not None:
                kwargs["priority"] = update.priority
            if update.ttl is not None:
                kwargs["ttl"] = update.ttl

            updated = db.update_memory_entry(session, entry_id, if_match, **kwargs)
            if not updated:
                raise HTTPException(
                    status_code=409, detail="Version conflict or entry not found"
                )
            return MemoryEntryResponse.model_validate(updated)
        finally:
            session.close()

    @app.delete("/api/v1/memory/{entry_id}")
    async def delete_memory_entry(
        entry_id: str,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            deleted = db.delete_memory_entry(session, entry_id)
            if not deleted:
                raise HTTPException(status_code=404, detail="Memory entry not found")
            return {"status": "deleted", "entry_id": entry_id}
        finally:
            session.close()

    # ==================== Agent Lifecycle (RFC-0016) ====================

    @app.post("/api/v1/agents/register", response_model=AgentRecordResponse)
    async def register_agent(
        agent: AgentRegister,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            created = db.register_agent(
                session,
                agent_id=agent.agent_id,
                name=agent.name,
                role_id=agent.role_id,
                capabilities=agent.capabilities,
                capacity=agent.capacity,
                endpoint=agent.endpoint,
                heartbeat_config=agent.heartbeat_config,
                agent_metadata=agent.metadata,
                drain_timeout_seconds=agent.drain_timeout_seconds,
            )
            return AgentRecordResponse.model_validate(created)
        finally:
            session.close()

    @app.get("/api/v1/agents/{agent_id}/record", response_model=AgentRecordResponse)
    async def get_agent_record(
        agent_id: str,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            agent = db.get_agent_record(session, agent_id)
            if not agent:
                raise HTTPException(status_code=404, detail="Agent not found")
            return AgentRecordResponse.model_validate(agent)
        finally:
            session.close()

    @app.get("/api/v1/agents", response_model=List[AgentRecordResponse])
    async def list_agents(
        status: Optional[str] = Query(None),
        role_id: Optional[str] = Query(None),
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            agents = db.list_agent_records(session, status=status, role_id=role_id)
            return [AgentRecordResponse.model_validate(a) for a in agents]
        finally:
            session.close()

    @app.post("/api/v1/agents/{agent_id}/heartbeat")
    async def agent_heartbeat(
        agent_id: str,
        heartbeat: HeartbeatRequest,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            updated = db.update_agent_heartbeat(
                session,
                agent_id,
                current_load=heartbeat.current_load,
                tasks_in_progress=heartbeat.tasks_in_progress,
            )
            if not updated:
                raise HTTPException(status_code=404, detail="Agent not found")

            next_heartbeat = datetime.utcnow() + timedelta(seconds=30)
            return {
                "status": "ok",
                "server_timestamp": datetime.utcnow().isoformat(),
                "next_heartbeat_at": next_heartbeat.isoformat(),
            }
        finally:
            session.close()

    @app.patch("/api/v1/agents/{agent_id}/status")
    async def update_agent_status(
        agent_id: str,
        update: AgentStatusUpdate,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            updated = db.update_agent_status(session, agent_id, update.status)
            if not updated:
                raise HTTPException(status_code=404, detail="Agent not found")
            return AgentRecordResponse.model_validate(updated)
        finally:
            session.close()

    # ==================== Triggers (RFC-0017) ====================

    @app.post("/api/v1/triggers", response_model=TriggerResponse)
    async def create_trigger(
        trigger: TriggerCreate,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            created = db.create_trigger(
                session,
                name=trigger.name,
                type=trigger.type,
                condition=trigger.condition,
                intent_template=trigger.intent_template,
                deduplication=trigger.deduplication,
                namespace=trigger.namespace,
            )
            return TriggerResponse.model_validate(created)
        finally:
            session.close()

    @app.get("/api/v1/triggers/{trigger_id}", response_model=TriggerResponse)
    async def get_trigger(
        trigger_id: str,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            trigger = db.get_trigger(session, trigger_id)
            if not trigger:
                raise HTTPException(status_code=404, detail="Trigger not found")
            return TriggerResponse.model_validate(trigger)
        finally:
            session.close()

    @app.get("/api/v1/triggers", response_model=List[TriggerResponse])
    async def list_triggers(
        namespace: Optional[str] = Query(None),
        type: Optional[str] = Query(None),
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            triggers = db.list_triggers(session, namespace=namespace, trigger_type=type)
            return [TriggerResponse.model_validate(t) for t in triggers]
        finally:
            session.close()

    @app.patch("/api/v1/triggers/{trigger_id}", response_model=TriggerResponse)
    async def update_trigger(
        trigger_id: str,
        update: TriggerUpdate,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
        if_match: Optional[int] = Depends(get_version_header),
    ):
        session = db.get_session()
        try:
            if if_match is None:
                raise HTTPException(status_code=428, detail="If-Match header required")

            kwargs = {}
            if update.enabled is not None:
                kwargs["enabled"] = update.enabled
            if update.condition is not None:
                kwargs["condition"] = update.condition
            if update.intent_template is not None:
                kwargs["intent_template"] = update.intent_template
            if update.deduplication is not None:
                kwargs["deduplication"] = update.deduplication

            updated = db.update_trigger(session, trigger_id, if_match, **kwargs)
            if not updated:
                raise HTTPException(
                    status_code=409, detail="Version conflict or trigger not found"
                )  # noqa: E501
            return TriggerResponse.model_validate(updated)
        finally:
            session.close()

    @app.post("/api/v1/triggers/{trigger_id}/fire")
    async def fire_trigger(
        trigger_id: str,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            fired = db.fire_trigger(session, trigger_id)
            if not fired:
                raise HTTPException(status_code=404, detail="Trigger not found")
            return {"status": "fired", "fire_count": fired.fire_count}
        finally:
            session.close()

    @app.delete("/api/v1/triggers/{trigger_id}")
    async def delete_trigger(
        trigger_id: str,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            deleted = db.delete_trigger(session, trigger_id)
            if not deleted:
                raise HTTPException(status_code=404, detail="Trigger not found")
            return {"status": "deleted", "trigger_id": trigger_id}
        finally:
            session.close()

    return app


class OpenIntentServer:
    """High-level server class for running OpenIntent."""

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8000,
        database_url: Optional[str] = None,
        api_keys: Optional[set] = None,
        **kwargs,
    ):
        self.config = ServerConfig(
            host=host,
            port=port,
            database_url=database_url,
            api_keys=api_keys or ServerConfig().api_keys,
            **kwargs,
        )
        self.app = create_app(self.config)

    def run(self):
        """Run the server (blocking)."""
        import uvicorn

        uvicorn.run(
            self.app,
            host=self.config.host,
            port=self.config.port,
            log_level=self.config.log_level,
        )

    async def run_async(self):
        """Run the server asynchronously."""
        import uvicorn

        config = uvicorn.Config(
            self.app,
            host=self.config.host,
            port=self.config.port,
            log_level=self.config.log_level,
        )
        server = uvicorn.Server(config)
        await server.serve()
