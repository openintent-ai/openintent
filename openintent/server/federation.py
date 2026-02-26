"""
OpenIntent Server - Federation endpoints (RFC-0022 & RFC-0023).

Provides cross-server agent coordination: dispatch, receive, callbacks,
agent discovery, and federation status.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel

from ..federation.models import (
    AgentVisibility,
    CallbackEventType,
    DelegationScope,
    FederatedAgent,
    FederationCallback,
    FederationEnvelope,
    FederationManifest,
    FederationPolicy,
    FederationStatus,
    TrustPolicy,
)
from ..federation.security import (
    ServerIdentity,
    TrustEnforcer,
    sign_envelope,
    validate_ssrf,
)

logger = logging.getLogger("openintent.server.federation")


class DispatchRequest(BaseModel):
    intent_id: str
    target_server: str
    agent_id: Optional[str] = None
    delegation_scope: Optional[Dict[str, Any]] = None
    federation_policy: Optional[Dict[str, Any]] = None
    callback_url: Optional[str] = None
    trace_context: Optional[Dict[str, str]] = None


class ReceiveRequest(BaseModel):
    dispatch_id: str
    source_server: str
    intent_id: str
    intent_title: str
    intent_description: str = ""
    intent_state: Dict[str, Any] = {}
    intent_constraints: Dict[str, Any] = {}
    agent_id: Optional[str] = None
    delegation_scope: Optional[Dict[str, Any]] = None
    federation_policy: Optional[Dict[str, Any]] = None
    trace_context: Optional[Dict[str, str]] = None
    callback_url: Optional[str] = None
    idempotency_key: Optional[str] = None
    signature: Optional[str] = None


class CallbackRequest(BaseModel):
    dispatch_id: str
    event_type: str
    state_delta: Dict[str, Any] = {}
    attestation: Optional[Dict[str, Any]] = None
    trace_id: Optional[str] = None
    idempotency_key: Optional[str] = None


class FederationState:
    def __init__(self):
        self.enabled: bool = False
        self.identity: Optional[ServerIdentity] = None
        self.trust_enforcer: Optional[TrustEnforcer] = None
        self.manifest: Optional[FederationManifest] = None
        self.agents: Dict[str, FederatedAgent] = {}
        self.peers: Dict[str, Dict[str, Any]] = {}
        self.dispatches: Dict[str, Dict[str, Any]] = {}
        self.received: Dict[str, Dict[str, Any]] = {}
        self.processed_idempotency_keys: set = set()
        self.total_dispatches: int = 0
        self.total_received: int = 0

    def register_agent(
        self,
        agent_id: str,
        capabilities: Optional[list[str]] = None,
        visibility: AgentVisibility = AgentVisibility.PUBLIC,
        server_url: str = "",
    ) -> FederatedAgent:
        agent = FederatedAgent(
            agent_id=agent_id,
            server_url=server_url
            or (self.manifest.server_url if self.manifest else ""),
            capabilities=capabilities or [],
            visibility=visibility,
            server_did=self.identity.did if self.identity else None,
        )
        self.agents[agent_id] = agent
        return agent

    def get_visible_agents(
        self, requesting_server: Optional[str] = None
    ) -> list[FederatedAgent]:
        result = []
        for agent in self.agents.values():
            if agent.visibility == AgentVisibility.PUBLIC:
                result.append(agent)
            elif agent.visibility == AgentVisibility.UNLISTED and requesting_server:
                if requesting_server in self.peers:
                    result.append(agent)
        return result


_federation_state = FederationState()


def get_federation_state() -> FederationState:
    return _federation_state


def configure_federation(
    server_url: str,
    server_did: Optional[str] = None,
    trust_policy: TrustPolicy = TrustPolicy.ALLOWLIST,
    visibility_default: AgentVisibility = AgentVisibility.PUBLIC,
    peers: Optional[list[str]] = None,
    identity: Optional[ServerIdentity] = None,
) -> FederationState:
    state = get_federation_state()
    state.enabled = True

    if identity:
        state.identity = identity
    else:
        state.identity = ServerIdentity.generate(server_url)

    if server_did:
        state.identity.did = server_did

    state.trust_enforcer = TrustEnforcer(
        policy=trust_policy,
        allowed_peers=peers,
    )

    state.manifest = FederationManifest(
        server_did=state.identity.did,
        server_url=server_url,
        trust_policy=trust_policy,
        visibility_default=visibility_default,
        peers=peers or [],
        public_key=state.identity.public_key_b64,
    )

    return state


def create_federation_router(
    validate_api_key=None,
) -> APIRouter:
    router = APIRouter(tags=["federation"])

    def _get_api_key(x_api_key: str = Header(None)) -> str:
        if validate_api_key:
            return validate_api_key(x_api_key)
        return x_api_key or ""

    @router.get("/.well-known/openintent-federation.json")
    async def federation_discovery():
        state = get_federation_state()
        if not state.enabled or not state.manifest:
            raise HTTPException(status_code=404, detail="Federation not enabled")
        return state.manifest.to_dict()

    @router.get("/.well-known/did.json")
    async def did_document():
        state = get_federation_state()
        if not state.enabled or not state.identity:
            raise HTTPException(status_code=404, detail="Federation not enabled")
        return state.identity.did_document()

    @router.get("/api/v1/federation/status")
    async def federation_status(api_key: str = Depends(_get_api_key)):
        state = get_federation_state()
        if not state.enabled:
            return FederationStatus(enabled=False).to_dict()

        active_dispatches = sum(
            1 for d in state.dispatches.values() if d.get("status") == "active"
        )

        return FederationStatus(
            enabled=True,
            server_did=state.identity.did if state.identity else None,
            trust_policy=(
                state.trust_enforcer.policy
                if state.trust_enforcer
                else TrustPolicy.ALLOWLIST
            ),
            peer_count=len(state.peers),
            active_dispatches=active_dispatches,
            total_dispatches=state.total_dispatches,
            total_received=state.total_received,
        ).to_dict()

    @router.get("/api/v1/federation/agents")
    async def federation_agents(
        request: Request,
        api_key: str = Depends(_get_api_key),
    ):
        state = get_federation_state()
        if not state.enabled:
            return {"agents": []}

        requesting_server = request.headers.get("X-Source-Server")
        agents = state.get_visible_agents(requesting_server)
        return {"agents": [a.to_dict() for a in agents]}

    @router.post("/api/v1/federation/dispatch")
    async def federation_dispatch(
        body: DispatchRequest,
        request: Request,
        api_key: str = Depends(_get_api_key),
    ):
        state = get_federation_state()
        if not state.enabled:
            raise HTTPException(status_code=400, detail="Federation not enabled")

        if body.callback_url and not validate_ssrf(body.callback_url):
            raise HTTPException(
                status_code=400,
                detail="Invalid callback URL: blocked by SSRF protection",
            )

        if not validate_ssrf(body.target_server):
            raise HTTPException(
                status_code=400,
                detail="Invalid target server URL: blocked by SSRF protection",
            )

        dispatch_id = str(uuid.uuid4())

        delegation_scope = None
        if body.delegation_scope:
            delegation_scope = DelegationScope.from_dict(body.delegation_scope)

        federation_policy = None
        if body.federation_policy:
            federation_policy = FederationPolicy.from_dict(body.federation_policy)

        envelope = FederationEnvelope(
            dispatch_id=dispatch_id,
            source_server=state.manifest.server_url if state.manifest else "",
            target_server=body.target_server,
            intent_id=body.intent_id,
            intent_title="",
            agent_id=body.agent_id,
            delegation_scope=delegation_scope,
            federation_policy=federation_policy,
            trace_context=body.trace_context,
            callback_url=body.callback_url,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        envelope_dict = envelope.to_dict()
        if state.identity:
            envelope_dict["signature"] = sign_envelope(state.identity, envelope_dict)

        state.dispatches[dispatch_id] = {
            "envelope": envelope_dict,
            "status": "active",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        state.total_dispatches += 1

        asyncio.create_task(_deliver_dispatch(state, body.target_server, envelope_dict))

        return {
            "dispatch_id": dispatch_id,
            "status": "accepted",
            "target_server": body.target_server,
            "message": "Dispatch initiated",
        }

    @router.post("/api/v1/federation/receive")
    async def federation_receive(
        body: ReceiveRequest,
        request: Request,
        api_key: str = Depends(_get_api_key),
    ):
        state = get_federation_state()
        if not state.enabled:
            raise HTTPException(status_code=400, detail="Federation not enabled")

        if state.trust_enforcer and not state.trust_enforcer.is_trusted(
            body.source_server
        ):
            raise HTTPException(
                status_code=403,
                detail=f"Source server {body.source_server} not trusted",
            )

        if body.idempotency_key:
            if body.idempotency_key in state.processed_idempotency_keys:
                existing = state.received.get(body.dispatch_id, {})
                return {
                    "dispatch_id": body.dispatch_id,
                    "accepted": True,
                    "local_intent_id": existing.get("local_intent_id"),
                    "message": "Already processed (idempotent)",
                }
            state.processed_idempotency_keys.add(body.idempotency_key)

        if body.federation_policy:
            policy = FederationPolicy.from_dict(body.federation_policy)
            budget = policy.budget
            if budget.get("max_llm_tokens") == 0 or budget.get("cost_ceiling_usd") == 0:
                return {
                    "dispatch_id": body.dispatch_id,
                    "accepted": False,
                    "message": "Rejected: budget constraints too restrictive",
                }

        local_intent_id = f"fed-{body.dispatch_id[:8]}-{str(uuid.uuid4())[:8]}"

        state.received[body.dispatch_id] = {
            "dispatch_id": body.dispatch_id,
            "source_server": body.source_server,
            "local_intent_id": local_intent_id,
            "agent_id": body.agent_id,
            "delegation_scope": body.delegation_scope,
            "federation_policy": body.federation_policy,
            "callback_url": body.callback_url,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        state.total_received += 1

        if body.callback_url and validate_ssrf(body.callback_url):
            asyncio.create_task(
                _send_callback(
                    body.callback_url,
                    FederationCallback(
                        dispatch_id=body.dispatch_id,
                        event_type=CallbackEventType.STATE_DELTA,
                        state_delta={"status": "accepted"},
                        trace_id=(
                            body.trace_context.get("trace_id")
                            if body.trace_context
                            else None
                        ),
                        idempotency_key=f"accept-{body.dispatch_id}",
                        timestamp=datetime.now(timezone.utc).isoformat(),
                    ),
                    state.identity,
                )
            )

        return {
            "dispatch_id": body.dispatch_id,
            "accepted": True,
            "local_intent_id": local_intent_id,
            "message": "Intent received and accepted for processing",
        }

    return router


async def _deliver_dispatch(
    state: FederationState,
    target_server: str,
    envelope_dict: Dict[str, Any],
    max_retries: int = 3,
) -> None:
    import httpx

    url = f"{target_server.rstrip('/')}/api/v1/federation/receive"

    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=envelope_dict)
                if response.status_code < 400:
                    dispatch_id = envelope_dict.get("dispatch_id", "")
                    if dispatch_id in state.dispatches:
                        state.dispatches[dispatch_id]["status"] = "delivered"
                    logger.info(f"Dispatch {dispatch_id} delivered to {target_server}")
                    return
                else:
                    logger.warning(
                        f"Dispatch delivery attempt {attempt + 1} failed: {response.status_code}"
                    )
        except Exception as e:
            logger.warning(f"Dispatch delivery attempt {attempt + 1} failed: {e}")

        if attempt < max_retries - 1:
            await asyncio.sleep(2**attempt)

    dispatch_id = envelope_dict.get("dispatch_id", "")
    if dispatch_id in state.dispatches:
        state.dispatches[dispatch_id]["status"] = "failed"
    logger.error(f"Dispatch {dispatch_id} delivery failed after {max_retries} attempts")


async def _send_callback(
    callback_url: str,
    callback: FederationCallback,
    identity: Optional[ServerIdentity] = None,
    max_retries: int = 3,
) -> None:
    import httpx

    payload = callback.to_dict()
    if identity:
        payload["signature"] = sign_envelope(identity, payload)

    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(callback_url, json=payload)
                if response.status_code < 400:
                    logger.info(
                        f"Callback delivered for dispatch {callback.dispatch_id}"
                    )
                    return
        except Exception as e:
            logger.warning(f"Callback delivery attempt {attempt + 1} failed: {e}")

        if attempt < max_retries - 1:
            await asyncio.sleep(2**attempt)

    logger.error(f"Callback delivery failed for dispatch {callback.dispatch_id}")
