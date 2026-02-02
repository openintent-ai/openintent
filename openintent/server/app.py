"""
FastAPI application for OpenIntent server.
"""

# mypy: disable-error-code="arg-type, var-annotated, misc, union-attr, attr-defined"

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from .config import ServerConfig
from .database import Database, IntentModel, get_database


class IntentCreate(BaseModel):
    title: str
    description: str = ""
    created_by: Optional[str] = None
    parent_id: Optional[str] = Field(None, alias="parent_intent_id")
    depends_on: List[str] = Field(default_factory=list)
    constraints: Dict[str, Any] = Field(default_factory=dict)
    state: Dict[str, Any] = Field(default_factory=dict)
    status: str = "draft"

    class Config:
        populate_by_name = True


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

    class Config:
        from_attributes = True
        populate_by_name = True


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

    class Config:
        from_attributes = True


class AgentAssign(BaseModel):
    agent_id: str
    role: str = "worker"


class AgentResponse(BaseModel):
    id: str
    intent_id: str
    agent_id: str
    role: str
    assigned_at: datetime

    class Config:
        from_attributes = True


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

    class Config:
        from_attributes = True


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

    class Config:
        from_attributes = True


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

    class Config:
        from_attributes = True


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

    class Config:
        from_attributes = True


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

    class Config:
        from_attributes = True


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
        version="0.4.0",
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
            ],
            "openApiUrl": "/openapi.json",
        }

    @app.get("/.well-known/openintent-compat.json")
    async def compatibility():
        return {
            "implementation": "OpenIntent Python Server",
            "version": "0.4.0",
            "rfcCompliance": {
                "RFC-0001": "full",
                "RFC-0002": "full",
                "RFC-0003": "full",
                "RFC-0004": "full",
                "RFC-0005": "full",
                "RFC-0006": "full",
                "RFC-0009": "full",
                "RFC-0010": "full",
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

    @app.patch("/api/v1/intents/{intent_id}/leases/{lease_id}", response_model=LeaseResponse)
    async def renew_lease(
        intent_id: str,
        lease_id: str,
        request: LeaseRenewRequest,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            renewed = db.renew_lease(session, lease_id, api_key, request.duration_seconds)
            if not renewed:
                raise HTTPException(
                    status_code=404, detail="Lease not found or not owned by you"
                )

            db.create_event(
                session,
                intent_id=intent_id,
                event_type="lease_renewed",
                actor=api_key,
                payload={"lease_id": lease_id, "duration_seconds": request.duration_seconds},
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

    @app.get("/api/v1/intents/{intent_id}/portfolios", response_model=List[PortfolioResponse])
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

    @app.patch("/api/v1/portfolios/{portfolio_id}/status", response_model=PortfolioResponse)
    async def update_portfolio_status(
        portfolio_id: str,
        request: PortfolioStatusRequest,
        db: Database = Depends(get_db),
        api_key: str = Depends(validate_api_key),
    ):
        session = db.get_session()
        try:
            portfolio = db.update_portfolio_status(session, portfolio_id, request.status)
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
