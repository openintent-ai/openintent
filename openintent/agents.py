"""
OpenIntent SDK - High-Level Agent Abstractions

Provides declarative, minimal-boilerplate abstractions for building
multi-agent systems with OpenIntent.

Usage:
    ```python
    from openintent import Agent, on_assignment

    @Agent("research-bot")
    class ResearchAgent:
        @on_assignment
        async def work(self, intent):
            return {"result": "done"}  # Auto-patches state

    ResearchAgent.run()
    ```
"""

# mypy: disable-error-code="attr-defined, arg-type, misc, call-arg"

import asyncio
import logging
from abc import ABC
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, TypeVar, Union

from .client import AsyncOpenIntentClient, OpenIntentClient
from .models import (
    AccessRequest,
    ACLEntry,
    EventType,
    Intent,
    IntentContext,
    IntentPortfolio,
    IntentStatus,
    MembershipRole,
    PeerInfo,
    Permission,
)
from .streaming import SSEEvent, SSEEventType, SSEStream, SSESubscription

logger = logging.getLogger("openintent.agents")


class _ToolsProxy:
    """Proxy for agent tool operations."""

    def __init__(self, agent):
        self._agent = agent

    async def invoke(self, tool_name, **kwargs):
        return await self._agent.async_client.invoke_tool(
            tool_name=tool_name,
            agent_id=self._agent._agent_id,
            parameters=kwargs,
        )


# ==================== Event Handler Decorators ====================


def on_assignment(func: Callable) -> Callable:
    """
    Decorator: Called when the agent is assigned to an intent.

    The handler receives the intent and should return state updates.
    Return values are automatically patched to the intent's state.

    Example:
        ```python
        @on_assignment
        async def handle(self, intent):
            result = await do_work(intent.title)
            return {"result": result}  # Auto-patched to state
        ```
    """
    func._openintent_handler = "assignment"
    return func


def on_complete(func: Callable) -> Callable:
    """
    Decorator: Called when an intent completes.

    Useful for cleanup, notification, or triggering follow-up work.

    Example:
        ```python
        @on_complete
        async def cleanup(self, intent):
            await notify_completion(intent.id)
        ```
    """
    func._openintent_handler = "complete"
    return func


def on_lease_available(scope: str) -> Callable:
    """
    Decorator: Called when a lease becomes available for a specific scope.

    Args:
        scope: The scope to watch for lease availability.

    Example:
        ```python
        @on_lease_available("research")
        async def claim(self, intent, scope):
            async with self.lease(intent.id, scope):
                await do_exclusive_work()
        ```
    """

    def decorator(func: Callable) -> Callable:
        func._openintent_handler = "lease_available"
        func._openintent_scope = scope
        return func

    return decorator


def on_state_change(keys: Optional[list[str]] = None) -> Callable:
    """
    Decorator: Called when intent state changes.

    Args:
        keys: Optional list of state keys to watch. If None, triggers on any change.

    Example:
        ```python
        @on_state_change(["progress"])
        async def track_progress(self, intent, old_state, new_state):
            print(f"Progress: {new_state.get('progress')}")
        ```
    """

    def decorator(func: Callable) -> Callable:
        func._openintent_handler = "state_change"
        func._openintent_keys = keys
        return func

    return decorator


def on_event(event_type: Union[str, EventType]) -> Callable:
    """
    Decorator: Called when a specific event type occurs.

    Args:
        event_type: The event type to handle.

    Example:
        ```python
        @on_event(EventType.ARBITRATION_REQUESTED)
        async def handle_arbitration(self, intent, event):
            await escalate(intent.id)
        ```
    """

    def decorator(func: Callable) -> Callable:
        func._openintent_handler = "event"
        func._openintent_event_type = (
            event_type if isinstance(event_type, str) else event_type.value
        )
        return func

    return decorator


def on_all_complete(func: Callable) -> Callable:
    """
    Decorator: Called when all intents in a portfolio complete.

    Only applicable for Coordinator agents managing portfolios.

    Example:
        ```python
        @on_all_complete
        async def finalize(self, portfolio):
            return merge_results(portfolio.intents)
        ```
    """
    func._openintent_handler = "all_complete"
    return func


def on_access_requested(func: Callable) -> Callable:
    """
    Decorator: Called when another principal requests access to an intent
    this agent administers. Return "approve", "deny", or "defer".

    Enables policy-as-code for automated access decisions.

    Example:
        ```python
        @on_access_requested
        async def policy(self, intent, request):
            if "ocr" in request.capabilities:
                return "approve"
            return "defer"
        ```
    """
    func._openintent_handler = "access_requested"
    return func


def on_task(status: Optional[str] = None) -> Callable:
    """
    Decorator: Called when a task lifecycle event occurs.

    Args:
        status: Optional task status filter (e.g., "completed", "failed").
                If None, triggers on any task event.
    """

    def decorator(func: Callable) -> Callable:
        func._openintent_handler = "task"
        func._openintent_task_status = status
        return func

    return decorator


def on_trigger(name: Optional[str] = None) -> Callable:
    """
    Decorator: Called when a trigger fires and creates an intent for this agent.

    Args:
        name: Optional trigger name filter. If None, handles any trigger.
    """

    def decorator(func: Callable) -> Callable:
        func._openintent_handler = "trigger"
        func._openintent_trigger_name = name
        return func

    return decorator


def on_drain(func: Callable) -> Callable:
    """
    Decorator: Called when the agent receives a drain signal.

    The handler should finish in-progress work and prepare for shutdown.
    The agent will stop accepting new assignments after this is called.
    """
    func._openintent_handler = "drain"
    return func


def on_conflict(func: Callable) -> Callable:
    """Decorator: Called when version conflicts occur between agents (RFC-0002).
    Handler receives (self, intent, conflict) with conflict details."""
    func._openintent_handler = "conflict"
    return func


def on_escalation(func: Callable) -> Callable:
    """Decorator: Called when an agent requests coordinator intervention.
    Handler receives (self, intent, agent_id, reason)."""
    func._openintent_handler = "escalation"
    return func


def on_quorum(threshold: float = 0.5) -> Callable:
    """Decorator: Called when multi-agent voting reaches a threshold.
    Args: threshold - fraction of agents needed (0.0 to 1.0).
    Handler receives (self, intent, votes)."""

    def decorator(func: Callable) -> Callable:
        func._openintent_handler = "quorum"
        func._openintent_quorum_threshold = threshold
        return func

    return decorator


def on_handoff(func: Callable) -> Callable:
    """
    Decorator: Called when this agent receives work delegated from another agent.

    Unlike @on_assignment which fires for all assignments, @on_handoff fires
    only when the assignment includes delegation context (delegated_by is set).
    The handler receives the intent and the delegating agent's ID.

    Example:
        ```python
        @on_handoff
        async def received(self, intent, from_agent):
            previous = await self.memory.recall(key=f"handoff:{intent.id}")
            return {"status": "continuing", "from": from_agent}
        ```
    """
    func._openintent_handler = "handoff"
    return func


def on_retry(func: Callable) -> Callable:
    """
    Decorator: Called when an intent is reassigned after a previous failure.

    The handler receives the intent and retry metadata (attempt number,
    previous failure reason). Allows agents to adapt behaviour on retries
    (e.g. use a different strategy, reduce scope, or escalate).

    Example:
        ```python
        @on_retry
        async def handle_retry(self, intent, attempt, last_error):
            if attempt >= 3:
                await self.escalate(intent.id, "Too many retries")
                return
            return await self.think(f"Retry attempt {attempt}: {intent.title}")
        ```
    """
    func._openintent_handler = "retry"
    return func


def input_guardrail(func: Callable) -> Callable:
    """
    Decorator: Validates or transforms intent data before assignment handlers run.

    Input guardrails execute in registration order before any @on_assignment
    handler. If a guardrail raises ``GuardrailError`` (or returns ``False``),
    the assignment is rejected and the intent can be escalated.

    Example:
        ```python
        @input_guardrail
        async def check_scope(self, intent):
            if len(intent.description) > 10_000:
                raise GuardrailError("Input too long")
        ```
    """
    func._openintent_handler = "input_guardrail"
    return func


def output_guardrail(func: Callable) -> Callable:
    """
    Decorator: Validates or transforms handler results before they are committed.

    Output guardrails execute in registration order after @on_assignment
    handlers return. The guardrail receives the intent and the result dict.
    If it raises ``GuardrailError`` (or returns ``False``), the result is
    discarded and the intent can be escalated.

    Example:
        ```python
        @output_guardrail
        async def check_pii(self, intent, result):
            for key, val in result.items():
                if contains_pii(str(val)):
                    raise GuardrailError(f"PII detected in '{key}'")
        ```
    """
    func._openintent_handler = "output_guardrail"
    return func


class GuardrailError(Exception):
    """Raised by input/output guardrails to reject processing."""

    pass


# ==================== Portfolio DSL ====================


@dataclass
class IntentSpec:
    """Specification for an intent to be created within a portfolio."""

    title: str
    description: str = ""
    assign: Optional[str] = None
    depends_on: Optional[list[str]] = None
    constraints: list[str] = field(default_factory=list)
    initial_state: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.depends_on is None:
            self.depends_on = []


@dataclass
class PortfolioSpec:
    """
    Declarative portfolio specification.

    Example:
        ```python
        spec = PortfolioSpec(
            name="Research Project",
            intents=[
                IntentSpec("Research", assign="researcher"),
                IntentSpec("Write", assign="writer", depends_on=["Research"]),
                IntentSpec("Review", depends_on=["Write"]),
            ]
        )
        ```
    """

    name: str
    description: str = ""
    intents: list[IntentSpec] = field(default_factory=list)
    governance_policy: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


# ==================== Agent Configuration ====================


@dataclass
class AgentConfig:
    """Configuration for an Agent."""

    base_url: str = "http://localhost:5000"
    api_key: str = ""
    auto_subscribe: bool = True
    auto_complete: bool = True
    reconnect_delay: float = 5.0
    max_reconnects: int = 10
    log_level: int = logging.INFO
    capabilities: list[str] = field(default_factory=list)
    auto_request_access: bool = False
    # v0.8.0: Lifecycle (RFC-0016)
    auto_heartbeat: bool = True
    heartbeat_interval: float = 30.0
    drain_timeout: float = 60.0
    # v0.8.0: Memory (RFC-0015)
    memory: Optional[str] = None  # "working", "episodic", "semantic"
    memory_namespace: Optional[str] = None
    # v0.8.0: Tools (RFC-0014)
    tools: list = field(default_factory=list)


# ==================== Base Agent Class ====================


T = TypeVar("T", bound="BaseAgent")


class BaseAgent(ABC):
    """
    Base class for OpenIntent agents.

    Provides automatic subscription management, event routing,
    and lifecycle handling.
    """

    _agent_id: str = ""
    _config: AgentConfig = field(default_factory=AgentConfig)
    _handlers: dict[str, list[Callable]] = field(default_factory=dict)

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        config: Optional[AgentConfig] = None,
    ):
        self._config = config or AgentConfig()
        if base_url:
            self._config.base_url = base_url
        if api_key:
            self._config.api_key = api_key

        self._client: Optional[OpenIntentClient] = None
        self._async_client: Optional[AsyncOpenIntentClient] = None
        self._subscription: Optional[SSESubscription] = None
        self._running = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None

        self._discover_handlers()

        # v0.8.0 proxies
        self._memory_proxy: Optional[_MemoryProxy] = None
        self._tasks_proxy: Optional[_TasksProxy] = None
        self._tools_proxy: Optional[_ToolsProxy] = None

    def _discover_handlers(self) -> None:
        """Discover decorated handler methods."""
        self._handlers = {
            "assignment": [],
            "complete": [],
            "lease_available": [],
            "state_change": [],
            "event": [],
            "all_complete": [],
            "access_requested": [],
            "task": [],
            "trigger": [],
            "drain": [],
            "handoff": [],
            "retry": [],
            "input_guardrail": [],
            "output_guardrail": [],
        }

        for name in dir(self):
            if name.startswith("_"):
                continue
            method = getattr(self, name, None)
            if method and callable(method) and hasattr(method, "_openintent_handler"):
                handler_type = method._openintent_handler
                if handler_type in self._handlers:
                    self._handlers[handler_type].append(method)

    @property
    def agent_id(self) -> str:
        """The agent's unique identifier."""
        return self._agent_id

    @property
    def client(self) -> OpenIntentClient:
        """Get or create the synchronous client."""
        if not self._client:
            self._client = OpenIntentClient(
                base_url=self._config.base_url,
                api_key=self._config.api_key,
                agent_id=self._agent_id,
            )
        return self._client

    @property
    def async_client(self) -> AsyncOpenIntentClient:
        """Get or create the asynchronous client."""
        if not self._async_client:
            self._async_client = AsyncOpenIntentClient(
                base_url=self._config.base_url,
                api_key=self._config.api_key,
                agent_id=self._agent_id,
            )
        return self._async_client

    @property
    def memory(self) -> "_MemoryProxy":
        """Access agent memory (RFC-0015). Configure via @Agent(memory="episodic")."""
        if not self._memory_proxy:
            self._memory_proxy = _MemoryProxy(
                self.async_client,
                self._agent_id,
                memory_type=self._config.memory or "episodic",
                namespace=self._config.memory_namespace,
            )
        return self._memory_proxy

    @property
    def tasks(self) -> "_TasksProxy":
        """Access task operations (RFC-0012)."""
        if not self._tasks_proxy:
            self._tasks_proxy = _TasksProxy(self.async_client, self._agent_id)
        return self._tasks_proxy

    @property
    def tools(self) -> _ToolsProxy:
        """Access tool invocation (RFC-0014). Configure via @Agent(tools=["web_search"])."""
        if not self._tools_proxy:
            self._tools_proxy = _ToolsProxy(self)
        return self._tools_proxy

    def lease(self, intent_id: str, scope: str, duration_seconds: int = 300):
        """
        Acquire a lease as a context manager.

        Example:
            ```python
            async with self.lease(intent.id, "research"):
                await do_exclusive_work()
            ```
        """
        return self.client.lease(intent_id, scope, duration_seconds)

    async def patch_state(self, intent_id: str, updates: dict[str, Any]) -> None:
        """
        Patch intent state with updates.

        Automatically handles version tracking.
        """
        intent = await self.async_client.get_intent(intent_id)
        await self.async_client.update_state(intent_id, intent.version, updates)

    async def complete_intent(
        self, intent_id: str, final_state: Optional[dict[str, Any]] = None
    ) -> None:
        """Mark an intent as completed with optional final state."""
        intent = await self.async_client.get_intent(intent_id)
        if final_state:
            await self.async_client.update_state(intent_id, intent.version, final_state)
            intent = await self.async_client.get_intent(intent_id)
        await self.async_client.set_status(
            intent_id, IntentStatus.COMPLETED, intent.version
        )

    async def log(self, intent_id: str, message: str, **data: Any) -> None:
        """Log a comment event to an intent."""
        await self.async_client.log_event(
            intent_id, EventType.COMMENT, {"message": message, **data}
        )

    # ==================== Access Control (RFC-0011) ====================

    async def _build_context(self, intent: Intent) -> "IntentContext":
        """
        Build an IntentContext for an intent, auto-populating based on
        this agent's permission level.
        """
        ctx = IntentContext()

        try:
            if intent.parent_intent_id:
                ctx.parent = await self.async_client.get_intent(intent.parent_intent_id)
        except Exception:
            pass

        if intent.depends_on:
            for dep_id in intent.depends_on:
                try:
                    dep = await self.async_client.get_intent(dep_id)
                    ctx.dependencies[dep.title] = dep.state.to_dict()
                except Exception:
                    pass

        try:
            events = await self.async_client.get_events(intent.id, limit=20)
            ctx.events = events
        except Exception:
            pass

        try:
            acl = await self.async_client.get_acl(intent.id)
            ctx.acl = acl
            for entry in acl.entries:
                if entry.principal_id == self._agent_id:
                    ctx.my_permission = entry.permission
                ctx.peers.append(
                    PeerInfo(
                        principal_id=entry.principal_id,
                        principal_type=entry.principal_type,
                        permission=entry.permission,
                    )
                )
        except Exception:
            pass

        return ctx

    async def grant_access(
        self,
        intent_id: str,
        principal_id: str,
        permission: str = "write",
        reason: Optional[str] = None,
    ) -> ACLEntry:
        """Grant access to another principal on an intent."""
        return await self.async_client.grant_access(
            intent_id,
            principal_id,
            principal_type="agent",
            permission=Permission(permission),
            reason=reason,
        )

    async def revoke_access(self, intent_id: str, entry_id: str) -> None:
        """Revoke access from a principal."""
        await self.async_client.revoke_access(intent_id, entry_id)

    def temp_access(
        self,
        intent_id: str,
        principal_id: str,
        permission: str = "write",
        reason: Optional[str] = None,
    ) -> "_TempAccessContext":
        """
        Context manager for temporary access grants with automatic revocation.

        Example:
            ```python
            async with self.temp_access(intent.id, "helper-agent", "write"):
                await self.client.assign_agent(intent.id, "helper-agent")
            # Access automatically revoked
            ```
        """
        return _TempAccessContext(self, intent_id, principal_id, permission, reason)

    async def delegate(
        self,
        intent_id: str,
        target_agent_id: str,
        payload: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        Delegate work on an intent to another agent.

        The target agent receives the assignment with intent.ctx.delegated_by set.
        """
        await self.async_client.log_event(
            intent_id,
            EventType.AGENT_ASSIGNED,
            {
                "agent_id": target_agent_id,
                "delegated_by": self._agent_id,
                "payload": payload or {},
            },
        )
        await self.async_client.assign_agent(intent_id, target_agent_id)

    async def escalate(
        self, intent_id: str, reason: str, data: Optional[dict[str, Any]] = None
    ) -> None:  # noqa: E501
        """
        Escalate an intent to administrators for review.

        Creates an arbitration request through the governance pipeline.
        """
        await self.async_client.request_arbitration(
            intent_id,
            reason=reason,
            context=data or {},
        )

    # ==================== Event Routing ====================

    async def _handle_event(self, event: SSEEvent) -> None:
        """Route SSE events to appropriate handlers."""
        try:
            if (
                event.type == SSEEventType.AGENT_ASSIGNED
                or event.type == "AGENT_ASSIGNED"
            ):
                await self._on_assignment(event)
            elif (
                event.type == SSEEventType.STATUS_CHANGED
                or event.type == "STATUS_CHANGED"
            ):
                await self._on_status_change(event)
            elif (
                event.type == SSEEventType.LEASE_RELEASED
                or event.type == "LEASE_RELEASED"
            ):
                await self._on_lease_released(event)
            elif (
                event.type == SSEEventType.STATE_CHANGED
                or event.type == "STATE_CHANGED"
            ):
                await self._on_state_change(event)
            elif (
                event.type == SSEEventType.INTENT_COMPLETED
                or event.type == "INTENT_COMPLETED"
            ):
                await self._on_intent_complete(event)
            elif (
                event.type == SSEEventType.ACCESS_REQUESTED
                or event.type == "ACCESS_REQUESTED"
                or event.type == "access_requested"
            ):
                await self._on_access_requested(event)
            else:
                await self._on_generic_event(event)
        except Exception as e:
            logger.exception(f"Error handling event {event.type}: {e}")

    async def _on_assignment(self, event: SSEEvent) -> None:
        """Handle assignment events with guardrails, handoff, and retry support."""
        intent_id = event.data.get("intent_id")
        if not intent_id:
            return

        intent = await self.async_client.get_intent(intent_id)

        ctx = await self._build_context(intent)
        delegated_by = event.data.get("delegated_by")
        if delegated_by:
            ctx.delegated_by = delegated_by
        intent.ctx = ctx

        retry_attempt = event.data.get("retry_attempt", 0)
        last_error = event.data.get("last_error")

        if retry_attempt and self._handlers["retry"]:
            for handler in self._handlers["retry"]:
                try:
                    result = await self._call_handler(
                        handler, intent, retry_attempt, last_error
                    )
                    if result and isinstance(result, dict) and self._config.auto_complete:
                        await self.patch_state(intent_id, result)
                except Exception as e:
                    logger.exception(f"Retry handler error: {e}")
            return

        if delegated_by and self._handlers["handoff"]:
            for handler in self._handlers["handoff"]:
                try:
                    result = await self._call_handler(handler, intent, delegated_by)
                    if result and isinstance(result, dict) and self._config.auto_complete:
                        await self.patch_state(intent_id, result)
                except Exception as e:
                    logger.exception(f"Handoff handler error: {e}")
            return

        for guardrail in self._handlers["input_guardrail"]:
            try:
                check = await self._call_handler(guardrail, intent)
                if check is False:
                    logger.warning(
                        f"Input guardrail rejected intent {intent_id}"
                    )
                    return
            except GuardrailError as e:
                logger.warning(f"Input guardrail rejected intent {intent_id}: {e}")
                return
            except Exception as e:
                logger.exception(f"Input guardrail error: {e}")
                return

        for handler in self._handlers["assignment"]:
            try:
                result = await self._call_handler(handler, intent)
                if result and isinstance(result, dict):
                    for guardrail in self._handlers["output_guardrail"]:
                        try:
                            check = await self._call_handler(guardrail, intent, result)
                            if check is False:
                                logger.warning(
                                    f"Output guardrail rejected result for {intent_id}"
                                )
                                result = None
                                break
                        except GuardrailError as e:
                            logger.warning(
                                f"Output guardrail rejected result for {intent_id}: {e}"
                            )
                            result = None
                            break
                        except Exception as e:
                            logger.exception(f"Output guardrail error: {e}")
                            result = None
                            break

                    if result and self._config.auto_complete:
                        await self.patch_state(intent_id, result)
            except Exception as e:
                logger.exception(f"Assignment handler error: {e}")

    async def _on_status_change(self, event: SSEEvent) -> None:
        """Handle status change events."""
        new_status = event.data.get("new_status")
        if new_status == "completed":
            await self._on_intent_complete(event)

    async def _on_intent_complete(self, event: SSEEvent) -> None:
        """Handle intent completion events."""
        intent_id = event.data.get("intent_id")
        if not intent_id:
            return

        intent = await self.async_client.get_intent(intent_id)

        for handler in self._handlers["complete"]:
            try:
                await self._call_handler(handler, intent)
            except Exception as e:
                logger.exception(f"Complete handler error: {e}")

    async def _on_lease_released(self, event: SSEEvent) -> None:
        """Handle lease release events."""
        intent_id = event.data.get("intent_id")
        scope = event.data.get("scope")
        if not intent_id or not scope:
            return

        intent = await self.async_client.get_intent(intent_id)

        for handler in self._handlers["lease_available"]:
            handler_scope = getattr(handler, "_openintent_scope", None)
            if handler_scope == scope:
                try:
                    await self._call_handler(handler, intent, scope)
                except Exception as e:
                    logger.exception(f"Lease available handler error: {e}")

    async def _on_state_change(self, event: SSEEvent) -> None:
        """Handle state change events."""
        intent_id = event.data.get("intent_id")
        if not intent_id:
            return

        old_state = event.data.get("old_state", {})
        new_state = event.data.get("new_state", {})
        intent = await self.async_client.get_intent(intent_id)

        for handler in self._handlers["state_change"]:
            keys = getattr(handler, "_openintent_keys", None)
            if keys is None or any(k in new_state for k in keys):
                try:
                    await self._call_handler(handler, intent, old_state, new_state)
                except Exception as e:
                    logger.exception(f"State change handler error: {e}")

    async def _on_generic_event(self, event: SSEEvent) -> None:
        """Handle generic events via @on_event decorators."""
        intent_id = event.data.get("intent_id")
        if not intent_id:
            return

        intent = await self.async_client.get_intent(intent_id)

        for handler in self._handlers["event"]:
            handler_type = getattr(handler, "_openintent_event_type", None)
            if handler_type == event.type:
                try:
                    await self._call_handler(handler, intent, event)
                except Exception as e:
                    logger.exception(f"Event handler error: {e}")

    async def _on_access_requested(self, event: SSEEvent) -> None:
        """Handle access request events via @on_access_requested decorator."""
        intent_id = event.data.get("intent_id")
        if not intent_id:
            return

        intent = await self.async_client.get_intent(intent_id)
        request = AccessRequest.from_dict(event.data.get("request", event.data))

        for handler in self._handlers["access_requested"]:
            try:
                result = await self._call_handler(handler, intent, request)
                if result == "approve":
                    await self.async_client.approve_access_request(
                        intent_id,
                        request.id,
                        permission=request.requested_permission,
                        reason="Auto-approved by agent policy",
                    )
                elif result == "deny":
                    await self.async_client.deny_access_request(
                        intent_id,
                        request.id,
                        reason="Denied by agent policy",
                    )
            except Exception as e:
                logger.exception(f"Access request handler error: {e}")

    async def _call_handler(self, handler: Callable, *args: Any) -> Any:
        """Call a handler, handling both sync and async methods."""
        if asyncio.iscoroutinefunction(handler):
            return await handler(*args)
        else:
            return handler(*args)

    # ==================== Lifecycle ====================

    def run(self) -> None:
        """
        Start the agent and begin processing events.

        This method blocks until stop() is called.
        """
        logger.info(f"Starting agent: {self._agent_id}")
        self._running = True

        asyncio.run(self._run_async())

    async def _run_async(self) -> None:
        """Async run loop."""
        self._loop = asyncio.get_event_loop()

        if self._config.auto_subscribe:
            await self._subscribe()

        while self._running:
            await asyncio.sleep(0.1)

    async def _subscribe(self) -> None:
        """Set up SSE subscription for this agent."""
        url = f"{self._config.base_url}/api/v1/agents/{self._agent_id}/subscribe"
        headers = {
            "X-API-Key": self._config.api_key,
            "X-Agent-ID": self._agent_id,
        }

        async def event_loop():
            stream = SSEStream(
                url,
                headers,
                reconnect_delay=self._config.reconnect_delay,
                max_reconnects=self._config.max_reconnects,
            )
            for event in stream:
                if not self._running:
                    break
                await self._handle_event(event)

        asyncio.create_task(event_loop())

    def stop(self) -> None:
        """Stop the agent."""
        logger.info(f"Stopping agent: {self._agent_id}")
        self._running = False
        if self._subscription:
            self._subscription.stop()


class _MemoryProxy:
    """Proxy for natural memory access from agent methods."""

    def __init__(
        self,
        client_ref,
        agent_id: str,
        memory_type: str = "episodic",
        namespace: Optional[str] = None,
    ):  # noqa: E501
        self._client_ref = client_ref
        self._agent_id = agent_id
        self._memory_type = memory_type
        self._namespace = namespace

    async def store(
        self, key: str, value: Any, tags: Optional[list[str]] = None
    ) -> Any:
        """Store a memory entry."""
        return await self._client_ref.memory.store(
            agent_id=self._agent_id,
            key=key,
            value=value,
            memory_type=self._memory_type,
            tags=tags or [],
            namespace=self._namespace,
        )

    async def recall(
        self, key: Optional[str] = None, tags: Optional[list[str]] = None
    ) -> Any:
        """Recall memories by key or tags."""
        return await self._client_ref.memory.query(
            agent_id=self._agent_id,
            namespace=self._namespace,
            key=key,
            tags=tags,
        )

    async def forget(self, key: str) -> None:
        """Remove a memory entry."""
        await self._client_ref.memory.delete(agent_id=self._agent_id, key=key)

    async def pin(self, key: str) -> None:
        """Pin a memory to prevent eviction."""
        await self._client_ref.memory.pin(agent_id=self._agent_id, key=key)


class _TasksProxy:
    """Proxy for task operations from agent methods."""

    def __init__(self, client_ref, agent_id: str):
        self._client_ref = client_ref
        self._agent_id = agent_id

    async def create(self, intent_id: str, title: str, **kwargs) -> Any:
        """Create a subtask within an intent."""
        return await self._client_ref.tasks.create(
            intent_id=intent_id,
            title=title,
            assigned_to=kwargs.get("assigned_to", self._agent_id),
            **{k: v for k, v in kwargs.items() if k != "assigned_to"},
        )

    async def complete(self, task_id: str, result: Optional[dict] = None) -> Any:
        """Mark a task as completed."""
        return await self._client_ref.tasks.update_status(
            task_id, status="completed", result=result
        )  # noqa: E501

    async def fail(self, task_id: str, error: Optional[str] = None) -> Any:
        """Mark a task as failed."""
        return await self._client_ref.tasks.update_status(
            task_id, status="failed", error=error
        )

    async def list(self, intent_id: str, status: Optional[str] = None) -> list:
        """List tasks for an intent, optionally filtered by status."""
        return await self._client_ref.tasks.list(intent_id=intent_id, status=status)


class _TempAccessContext:
    """Async context manager for temporary access grants."""

    def __init__(
        self,
        agent: BaseAgent,
        intent_id: str,
        principal_id: str,
        permission: str,
        reason: Optional[str],
    ):
        self._agent = agent
        self._intent_id = intent_id
        self._principal_id = principal_id
        self._permission = permission
        self._reason = reason
        self._entry: Optional[ACLEntry] = None

    async def __aenter__(self) -> ACLEntry:
        self._entry = await self._agent.grant_access(
            self._intent_id,
            self._principal_id,
            self._permission,
            self._reason,
        )
        return self._entry

    async def __aexit__(self, *args: Any) -> None:
        if self._entry:
            try:
                await self._agent.revoke_access(self._intent_id, self._entry.id)
            except Exception:
                pass


def _setup_llm_engine(
    agent_instance,
    model: str,
    provider: Optional[str] = None,
    system_prompt: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
    max_tool_rounds: int = 10,
    planning: bool = False,
    stream_by_default: bool = False,
    api_key_override: Optional[str] = None,
) -> None:
    """Attach LLM engine, think(), and think_stream() to an agent instance."""
    from .llm import LLMConfig, LLMEngine, _resolve_provider

    resolved_provider = provider or _resolve_provider(model)

    llm_config = LLMConfig(
        model=model,
        provider=resolved_provider,
        api_key=api_key_override,
        system_prompt=system_prompt,
        temperature=temperature,
        max_tokens=max_tokens,
        max_tool_rounds=max_tool_rounds,
        planning=planning,
        stream_by_default=stream_by_default,
    )

    engine = LLMEngine(agent_instance, llm_config)
    agent_instance._llm_engine = engine
    agent_instance._llm_config = llm_config
    agent_instance._llm_adapter = None

    async def think(prompt, intent=None, stream=None, on_token=None, **kw):
        return await engine.think(
            prompt, intent=intent, stream=stream, on_token=on_token, **kw
        )

    async def think_stream(prompt, intent=None, on_token=None, **kw):
        return await engine.think(
            prompt, intent=intent, stream=True, on_token=on_token, **kw
        )

    agent_instance.think = think
    agent_instance.think_stream = think_stream
    agent_instance.reset_conversation = engine.reset_history


def Agent(  # noqa: N802 - intentionally capitalized as class-like decorator
    agent_id: str,
    config: Optional[AgentConfig] = None,
    capabilities: Optional[list[str]] = None,
    memory: Optional[str] = None,
    tools: Optional[list] = None,
    auto_heartbeat: bool = True,
    model: Optional[str] = None,
    provider: Optional[str] = None,
    system_prompt: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
    max_tool_rounds: int = 10,
    planning: bool = False,
    stream_by_default: bool = False,
    **kwargs: Any,
) -> Callable[[type], type]:
    """
    Class decorator to create an Agent from a class.

    When ``model`` is provided, the agent becomes LLM-powered:
    ``self.think(prompt)`` runs an agentic loop that reasons, calls
    protocol tools (memory, escalation, clarification), and returns a
    result. ``self.think_stream(prompt)`` does the same but yields tokens.

    Tools can be plain strings (resolved via RFC-0014 protocol grants)
    or ``Tool`` objects with rich descriptions, parameter schemas, and
    local callable handlers.

    Example — manual agent (no model):
        ```python
        @Agent("research-bot")
        class ResearchAgent:
            @on_assignment
            async def work(self, intent):
                return {"result": "done"}
        ```

    Example — LLM-powered agent with Tool objects:
        ```python
        from openintent import Agent, Tool, tool, on_assignment

        @tool(description="Search the web.", parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query."},
            },
            "required": ["query"],
        })
        async def web_search(query: str) -> dict:
            return {"results": [...]}

        @Agent("analyst", model="gpt-4o", tools=[web_search])
        class Analyst:
            @on_assignment
            async def work(self, intent):
                return await self.think(intent.description)
        ```
    """

    def decorator(cls: type) -> type:
        original_init = cls.__init__ if hasattr(cls, "__init__") else None

        def new_init(
            self, base_url: Optional[str] = None, api_key: Optional[str] = None
        ):
            BaseAgent.__init__(self, base_url, api_key, config)
            self._agent_id = agent_id
            if capabilities:
                self._config.capabilities = capabilities
            if memory:
                self._config.memory = memory
            if tools:
                self._config.tools = tools
            self._config.auto_heartbeat = auto_heartbeat

            if model:
                _setup_llm_engine(
                    self,
                    model=model,
                    provider=provider,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    max_tool_rounds=max_tool_rounds,
                    planning=planning,
                    stream_by_default=stream_by_default,
                    api_key_override=kwargs.get("llm_api_key"),
                )

            if original_init and original_init is not object.__init__:
                original_init(self)

        cls.__init__ = new_init

        for name, method in BaseAgent.__dict__.items():
            if not name.startswith("__") and callable(method):
                if not hasattr(cls, name):
                    setattr(cls, name, method)

        for prop_name in [
            "agent_id",
            "client",
            "async_client",
            "memory",
            "tasks",
            "tools",
        ]:
            if not hasattr(cls, prop_name):
                setattr(cls, prop_name, getattr(BaseAgent, prop_name))

        @classmethod
        def run_agent(
            cls_self, base_url: Optional[str] = None, api_key: Optional[str] = None
        ):
            instance = cls_self(base_url, api_key)
            instance.run()

        cls.run = run_agent

        return cls

    return decorator


def _install_builtin_guardrails(
    agent_instance, guardrail_names: list[str]
) -> None:
    """Install built-in guardrail handlers based on guardrail name strings.

    Supported guardrails:
    - "require_approval": logs a decision record before any assignment is processed
    - "budget_limit": rejects intents whose cost estimate exceeds constraints
    - "agent_allowlist": rejects delegation to agents not in the managed list
    """
    for name in guardrail_names:
        if name == "require_approval":

            async def _approval_guardrail(intent):
                logger.info(
                    f"Guardrail 'require_approval': assignment to intent "
                    f"{intent.id} requires approval"
                )
                if hasattr(agent_instance, "record_decision"):
                    await agent_instance.record_decision(
                        "guardrail",
                        f"require_approval check for intent {intent.id}",
                        rationale="Built-in guardrail: require_approval",
                    )

            _approval_guardrail._openintent_handler = "input_guardrail"
            agent_instance._handlers["input_guardrail"].append(_approval_guardrail)

        elif name == "budget_limit":

            async def _budget_guardrail(intent):
                cost_limit = getattr(intent, "constraints", {})
                if isinstance(cost_limit, dict) and cost_limit.get("max_cost"):
                    current = getattr(intent, "cost_total", 0) or 0
                    if current > cost_limit["max_cost"]:
                        raise GuardrailError(
                            f"Budget exceeded: {current} > {cost_limit['max_cost']}"
                        )

            _budget_guardrail._openintent_handler = "input_guardrail"
            agent_instance._handlers["input_guardrail"].append(_budget_guardrail)

        elif name == "agent_allowlist":

            async def _allowlist_guardrail(intent, result):
                delegated_to = (
                    result.get("delegated_to") if isinstance(result, dict) else None
                )
                if delegated_to and hasattr(agent_instance, "_agents_list"):
                    if delegated_to not in agent_instance._agents_list:
                        raise GuardrailError(
                            f"Agent '{delegated_to}' not in managed agent list"
                        )

            _allowlist_guardrail._openintent_handler = "output_guardrail"
            agent_instance._handlers["output_guardrail"].append(_allowlist_guardrail)

        else:
            logger.warning(f"Unknown built-in guardrail: '{name}' — ignored")


# ==================== Coordinator Decorator ====================


def Coordinator(  # noqa: N802
    coordinator_id: str,
    agents: Optional[list[str]] = None,
    strategy: str = "sequential",
    guardrails: Optional[list[str]] = None,
    config: Optional[AgentConfig] = None,
    capabilities: Optional[list[str]] = None,
    memory: Optional[str] = None,
    tools: Optional[list] = None,
    auto_heartbeat: bool = True,
    model: Optional[str] = None,
    provider: Optional[str] = None,
    system_prompt: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
    max_tool_rounds: int = 10,
    planning: bool = True,
    stream_by_default: bool = False,
    **kwargs: Any,
) -> Callable[[type], type]:
    """
    Class decorator to create a Coordinator from a class.

    A Coordinator manages portfolios of intents, handles dependency
    tracking, multi-intent orchestration, and governance.

    When ``model`` is provided, the coordinator becomes LLM-powered:
    ``self.think(prompt)`` reasons about delegation, planning, and
    governance decisions. The LLM can call coordinator-specific tools
    like ``delegate``, ``create_plan``, and ``record_decision``.

    Example — manual coordinator:
        ```python
        @Coordinator("orchestrator", agents=["researcher", "writer"])
        class MyCoordinator:
            @on_assignment
            async def plan(self, intent):
                spec = PortfolioSpec(
                    name=intent.title,
                    intents=[
                        IntentSpec("Research", assign="researcher"),
                        IntentSpec("Write", assign="writer", depends_on=["Research"]),
                    ]
                )
                return await self.execute(spec)
        ```

    Example — LLM-powered coordinator:
        ```python
        @Coordinator(
            "lead",
            model="claude-sonnet-4-20250514",
            agents=["researcher", "writer", "reviewer"],
            memory="episodic",
        )
        class ProjectLead:
            @on_assignment
            async def plan(self, intent):
                return await self.think(
                    f"Break down this project and delegate to your team: {intent.description}"
                )
        ```
    """

    def decorator(cls: type) -> type:
        original_init = cls.__init__ if hasattr(cls, "__init__") else None

        def new_init(
            self, base_url: Optional[str] = None, api_key: Optional[str] = None
        ):
            BaseAgent.__init__(self, base_url, api_key, config)
            self._agent_id = coordinator_id
            if capabilities:
                self._config.capabilities = capabilities
            if memory:
                self._config.memory = memory
            if tools:
                self._config.tools = tools
            self._config.auto_heartbeat = auto_heartbeat
            self._agents_list = agents or []
            self._strategy = strategy
            self._guardrails = guardrails or []
            self._decision_log = []
            self._portfolios = {}
            self._intent_to_portfolio = {}
            self._pending_approvals: dict[str, asyncio.Future] = {}
            self._handlers.update({"conflict": [], "escalation": [], "quorum": []})
            _install_builtin_guardrails(self, self._guardrails)
            registered_funcs = set()
            for handler_type, handler_list in self._handlers.items():
                for h in handler_list:
                    registered_funcs.add(getattr(h, "__func__", h))
            for attr_name in dir(self):
                if attr_name.startswith("_"):
                    continue
                method = getattr(self, attr_name, None)
                if (
                    method
                    and callable(method)
                    and hasattr(method, "_openintent_handler")
                ):
                    handler_type = method._openintent_handler
                    func = getattr(method, "__func__", method)
                    if handler_type in self._handlers and func not in registered_funcs:
                        self._handlers[handler_type].append(method)
                        registered_funcs.add(func)
            if model:
                _setup_llm_engine(
                    self,
                    model=model,
                    provider=provider,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    max_tool_rounds=max_tool_rounds,
                    planning=planning,
                    stream_by_default=stream_by_default,
                    api_key_override=kwargs.get("llm_api_key"),
                )

            if original_init and original_init is not object.__init__:
                original_init(self)

        cls.__init__ = new_init

        for name, method in BaseAgent.__dict__.items():
            if not name.startswith("__") and callable(method):
                if not hasattr(cls, name):
                    setattr(cls, name, method)

        for prop_name in [
            "agent_id",
            "client",
            "async_client",
            "memory",
            "tasks",
            "tools",
        ]:
            if not hasattr(cls, prop_name):
                setattr(cls, prop_name, getattr(BaseAgent, prop_name))

        async def create_portfolio(self, spec: PortfolioSpec) -> IntentPortfolio:
            """Create a portfolio from a specification."""
            portfolio = await self.async_client.create_portfolio(
                name=spec.name,
                description=spec.description,
                governance_policy=spec.governance_policy,
                metadata=spec.metadata,
            )

            intent_id_map: dict[str, str] = {}
            ordered = self._topological_sort(spec.intents)

            for intent_spec in ordered:
                wait_for = [
                    intent_id_map[dep] for dep in (intent_spec.depends_on or [])
                ]
                initial_state = dict(intent_spec.initial_state)

                intent = await self.async_client.create_intent(
                    title=intent_spec.title,
                    description=intent_spec.description,
                    constraints=intent_spec.constraints,
                    initial_state=initial_state,
                    depends_on=wait_for,
                )

                intent_id_map[intent_spec.title] = intent.id

                await self.async_client.add_intent_to_portfolio(
                    portfolio.id,
                    intent.id,
                    role=MembershipRole.MEMBER,
                )

                if intent_spec.assign:
                    await self.async_client.assign_agent(intent.id, intent_spec.assign)

                self._intent_to_portfolio[intent.id] = portfolio.id

            self._portfolios[portfolio.id] = portfolio
            return portfolio

        cls.create_portfolio = create_portfolio

        def _topological_sort(self, intents: list[IntentSpec]) -> list[IntentSpec]:
            """Sort intents by dependencies."""
            by_title = {i.title: i for i in intents}
            visited: set[str] = set()
            result: list[IntentSpec] = []

            def visit(spec: IntentSpec):
                if spec.title in visited:
                    return
                visited.add(spec.title)
                for dep in spec.depends_on or []:
                    if dep in by_title:
                        visit(by_title[dep])
                result.append(spec)

            for spec in intents:
                visit(spec)

            return result

        cls._topological_sort = _topological_sort

        async def execute(self, spec: PortfolioSpec) -> dict[str, Any]:
            """Execute a portfolio and wait for completion."""
            portfolio = await self.create_portfolio(spec)
            await self._subscribe_portfolio(portfolio.id)

            while True:
                portfolio_with_intents = await self.async_client.get_portfolio(
                    portfolio.id
                )
                intents_list, aggregate = await self.async_client.get_portfolio_intents(
                    portfolio.id
                )
                portfolio_with_intents.intents = intents_list
                portfolio_with_intents.aggregate_status = aggregate

                all_complete = all(
                    i.status == IntentStatus.COMPLETED for i in intents_list
                )

                if all_complete:
                    for handler in self._handlers["all_complete"]:
                        result = await self._call_handler(
                            handler, portfolio_with_intents
                        )
                        if result:
                            return result
                    return self._merge_results(portfolio_with_intents)

                await asyncio.sleep(0.5)

        cls.execute = execute

        async def _subscribe_portfolio(self, portfolio_id: str) -> None:
            """Subscribe to portfolio events."""
            url = f"{self._config.base_url}/api/v1/portfolios/{portfolio_id}/subscribe"
            headers = {
                "X-API-Key": self._config.api_key,
                "X-Agent-ID": self._agent_id,
            }

            async def event_loop():
                stream = SSEStream(
                    url,
                    headers,
                    reconnect_delay=self._config.reconnect_delay,
                    max_reconnects=self._config.max_reconnects,
                )
                for event in stream:
                    if not self._running:
                        break
                    await self._handle_event(event)

            asyncio.create_task(event_loop())

        cls._subscribe_portfolio = _subscribe_portfolio

        def _merge_results(self, portfolio: IntentPortfolio) -> dict[str, Any]:
            """Merge results from all intents in a portfolio."""
            return {
                "portfolio_id": portfolio.id,
                "name": portfolio.name,
                "intents": {i.title: i.state.to_dict() for i in portfolio.intents},
            }

        cls._merge_results = _merge_results

        async def coord_delegate(self, intent_id: str, agent_id: str, **kw):
            """Delegate work on an intent to another agent."""
            await self.record_decision(
                "delegation", f"Delegating to {agent_id}", agent_id=agent_id
            )  # noqa: E501
            return await self.async_client.assign_agent(intent_id, agent_id)

        cls.delegate = coord_delegate

        async def coord_escalate(self, intent_id: str, reason: str, **kw):
            """Escalate an intent to the coordinator for review."""
            await self.record_decision("escalation", reason)
            return await self.async_client.request_arbitration(
                intent_id,
                reason=reason,
                context=kw,
            )

        cls.escalate = coord_escalate

        async def record_decision(
            self, decision_type: str, summary: str, rationale: str = "", **data: Any
        ) -> dict[str, Any]:  # noqa: E501
            """Record an auditable coordinator decision (RFC-0013)."""
            record = {
                "type": decision_type,
                "summary": summary,
                "rationale": rationale,
                "coordinator_id": self._agent_id,
                **data,
            }
            self._decision_log.append(record)
            return record

        cls.record_decision = record_decision

        decisions_prop = property(lambda self: list(self._decision_log))
        decisions_prop.__doc__ = "Access the coordinator's decision log."
        cls.decisions = decisions_prop

        agents_prop = property(lambda self: list(self._agents_list))
        agents_prop.__doc__ = "List of managed agent IDs."
        cls.agents = agents_prop

        @classmethod
        def run_agent(
            cls_self, base_url: Optional[str] = None, api_key: Optional[str] = None
        ):
            instance = cls_self(base_url, api_key)
            instance.run()

        cls.run = run_agent

        return cls

    return decorator


# ==================== First-class Protocol Decorators ====================


def Plan(  # noqa: N802
    name: str,
    strategy: str = "sequential",
    max_concurrent: int = 5,
    failure_policy: str = "fail_fast",
) -> Callable[[type], type]:
    """Declarative plan definition (RFC-0012). Defines task decomposition strategy."""

    def decorator(cls: type) -> type:
        cls._plan_name = name
        cls._plan_strategy = strategy
        cls._plan_max_concurrent = max_concurrent
        cls._plan_failure_policy = failure_policy

        def to_spec(self) -> PortfolioSpec:
            """Convert plan to PortfolioSpec for execution."""
            plan_tasks = []
            for attr_name in dir(self):
                attr = getattr(self, attr_name, None)
                if isinstance(attr, IntentSpec):
                    plan_tasks.append(attr)
            return PortfolioSpec(name=name, intents=plan_tasks)

        cls.to_spec = to_spec
        return cls

    return decorator


def Vault(  # noqa: N802
    name: str,
    rotate_keys: bool = False,
) -> Callable[[type], type]:
    """Declarative credential vault (RFC-0014). Defines tool access and credential policies."""

    def decorator(cls: type) -> type:
        cls._vault_name = name
        cls._vault_rotate_keys = rotate_keys

        def get_tools(self) -> list[str]:
            """List all tools declared in this vault."""
            found_tools = []
            for attr_name in dir(self):
                if not attr_name.startswith("_"):
                    attr = getattr(self, attr_name, None)
                    if isinstance(attr, dict) and "scopes" in attr:
                        found_tools.append(attr_name)
            return found_tools

        cls.get_tools = get_tools
        return cls

    return decorator


def Memory(  # noqa: N802
    namespace: str,
    tier: str = "episodic",
    ttl: Optional[int] = None,
    max_entries: int = 1000,
) -> Callable[[type], type]:
    """Declarative memory configuration (RFC-0015). Defines memory tier and policies."""

    def decorator(cls: type) -> type:
        cls._memory_namespace = namespace
        cls._memory_tier = tier
        cls._memory_ttl = ttl
        cls._memory_max_entries = max_entries
        return cls

    return decorator


def Trigger(  # noqa: N802
    name: str,
    type: str = "schedule",
    condition: Optional[str] = None,
    cron: Optional[str] = None,
    dedup: str = "skip",
) -> Callable[[type], type]:
    """Declarative trigger definition (RFC-0017). Creates intents when conditions are met."""

    def decorator(cls: type) -> type:
        cls._trigger_name = name
        cls._trigger_type = type
        cls._trigger_condition = condition
        cls._trigger_cron = cron
        cls._trigger_dedup = dedup
        return cls

    return decorator


# ==================== Simple Worker ====================


class Worker:
    """
    Ultra-minimal worker for simple, single-purpose agents.

    Example:
        ```python
        async def process(intent):
            return {"result": do_work(intent.title)}

        worker = Worker("processor", process)
        worker.run()
        ```
    """

    def __init__(
        self,
        agent_id: str,
        handler: Callable[[Intent], Any],
        base_url: str = "http://localhost:5000",
        api_key: str = "",
    ):
        self.agent_id = agent_id
        self.handler = handler
        self.base_url = base_url
        self.api_key = api_key
        self._running = False

    def run(self) -> None:
        """Run the worker."""
        asyncio.run(self._run_async())

    async def _run_async(self) -> None:
        """Async run loop."""
        client = AsyncOpenIntentClient(
            base_url=self.base_url,
            api_key=self.api_key,
            agent_id=self.agent_id,
        )

        url = f"{self.base_url}/api/v1/agents/{self.agent_id}/subscribe"
        headers = {
            "X-API-Key": self.api_key,
            "X-Agent-ID": self.agent_id,
        }

        self._running = True
        stream = SSEStream(url, headers)

        for event in stream:
            if not self._running:
                break

            if event.type in ("AGENT_ASSIGNED", SSEEventType.AGENT_ASSIGNED):
                intent_id = event.data.get("intent_id")
                if intent_id:
                    intent = await client.get_intent(intent_id)

                    try:
                        if asyncio.iscoroutinefunction(self.handler):
                            result = await self.handler(intent)
                        else:
                            result = self.handler(intent)

                        if result and isinstance(result, dict):
                            await client.update_state(intent_id, intent.version, result)
                            intent = await client.get_intent(intent_id)

                        await client.set_status(
                            intent_id, IntentStatus.COMPLETED, intent.version
                        )
                    except Exception as e:
                        logger.exception(f"Worker error: {e}")

    def stop(self) -> None:
        """Stop the worker."""
        self._running = False
