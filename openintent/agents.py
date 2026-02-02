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

import asyncio
import logging
from abc import ABC
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, TypeVar, Union

from .client import AsyncOpenIntentClient, OpenIntentClient
from .models import (
    EventType,
    Intent,
    IntentPortfolio,
    IntentStatus,
    MembershipRole,
)
from .streaming import SSEEvent, SSEEventType, SSEStream, SSESubscription

logger = logging.getLogger("openintent.agents")


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

    def _discover_handlers(self) -> None:
        """Discover decorated handler methods."""
        self._handlers = {
            "assignment": [],
            "complete": [],
            "lease_available": [],
            "state_change": [],
            "event": [],
            "all_complete": [],
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
            else:
                await self._on_generic_event(event)
        except Exception as e:
            logger.exception(f"Error handling event {event.type}: {e}")

    async def _on_assignment(self, event: SSEEvent) -> None:
        """Handle assignment events."""
        intent_id = event.data.get("intent_id")
        if not intent_id:
            return

        intent = await self.async_client.get_intent(intent_id)

        for handler in self._handlers["assignment"]:
            try:
                result = await self._call_handler(handler, intent)
                if result and isinstance(result, dict) and self._config.auto_complete:
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


def Agent(  # noqa: N802 - intentionally capitalized as class-like decorator
    agent_id: str, config: Optional[AgentConfig] = None
) -> Callable[[type], type]:
    """
    Class decorator to create an Agent from a class.

    Example:
        ```python
        @Agent("research-bot")
        class ResearchAgent:
            @on_assignment
            async def work(self, intent):
                return {"result": "done"}

        ResearchAgent.run()
        ```
    """

    def decorator(cls: type) -> type:
        original_init = cls.__init__ if hasattr(cls, "__init__") else None

        def new_init(
            self, base_url: Optional[str] = None, api_key: Optional[str] = None
        ):
            BaseAgent.__init__(self, base_url, api_key, config)
            self._agent_id = agent_id
            if original_init and original_init is not object.__init__:
                original_init(self)

        cls.__init__ = new_init

        for name, method in BaseAgent.__dict__.items():
            if not name.startswith("__") and callable(method):
                if not hasattr(cls, name):
                    setattr(cls, name, method)

        for prop_name in ["agent_id", "client", "async_client"]:
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


# ==================== Coordinator Class ====================


class Coordinator(BaseAgent):
    """
    A specialized agent for coordinating portfolios of intents.

    Extends BaseAgent with portfolio management, dependency tracking,
    and multi-intent orchestration.

    Example:
        ```python
        class MyCoordinator(Coordinator):
            async def plan(self, goal: str) -> PortfolioSpec:
                return PortfolioSpec(
                    name=goal,
                    intents=[
                        IntentSpec("Research", assign="researcher"),
                        IntentSpec("Write", assign="writer", depends_on=["Research"]),
                    ]
                )

            @on_all_complete
            async def finalize(self, portfolio):
                return merge_results(portfolio.intents)
        ```
    """

    _portfolios: dict[str, IntentPortfolio] = {}
    _intent_to_portfolio: dict[str, str] = {}

    def __init__(
        self,
        agent_id: str,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        config: Optional[AgentConfig] = None,
    ):
        super().__init__(base_url, api_key, config)
        self._agent_id = agent_id
        self._portfolios = {}
        self._intent_to_portfolio = {}

    async def create_portfolio(self, spec: PortfolioSpec) -> IntentPortfolio:
        """
        Create a portfolio from a specification.

        Handles dependency ordering and intent creation.
        """
        portfolio = await self.async_client.create_portfolio(
            name=spec.name,
            description=spec.description,
            governance_policy=spec.governance_policy,
            metadata=spec.metadata,
        )

        intent_id_map: dict[str, str] = {}

        ordered = self._topological_sort(spec.intents)

        for intent_spec in ordered:
            wait_for = [intent_id_map[dep] for dep in (intent_spec.depends_on or [])]

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

    def _topological_sort(self, intents: list[IntentSpec]) -> list[IntentSpec]:
        """Sort intents by dependencies."""
        by_title = {i.title: i for i in intents}
        visited = set()
        result = []

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

    async def execute(self, spec: PortfolioSpec) -> dict[str, Any]:
        """
        Execute a portfolio and wait for completion.

        Creates the portfolio, subscribes to events, and returns
        merged results when all intents complete.
        """
        portfolio = await self.create_portfolio(spec)

        await self._subscribe_portfolio(portfolio.id)

        while True:
            portfolio_with_intents = await self.async_client.get_portfolio(portfolio.id)
            intents, aggregate = await self.async_client.get_portfolio_intents(
                portfolio.id
            )
            portfolio_with_intents.intents = intents
            portfolio_with_intents.aggregate_status = aggregate

            all_complete = all(i.status == IntentStatus.COMPLETED for i in intents)

            if all_complete:
                for handler in self._handlers["all_complete"]:
                    result = await self._call_handler(handler, portfolio_with_intents)
                    if result:
                        return result

                return self._merge_results(portfolio_with_intents)

            await asyncio.sleep(0.5)

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

    def _merge_results(self, portfolio: IntentPortfolio) -> dict[str, Any]:
        """Merge results from all intents in a portfolio."""
        return {
            "portfolio_id": portfolio.id,
            "name": portfolio.name,
            "intents": {i.title: i.state.to_dict() for i in portfolio.intents},
        }


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
