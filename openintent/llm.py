"""
OpenIntent SDK - LLM-Powered Agent Engine

Provides the core LLM integration layer that turns @Agent and @Coordinator
into autonomous, thinking agents when model= is specified. Handles context
assembly, agentic tool loops, streaming, memory management, and
human-in-the-loop flows.

Usage:
    ```python
    from openintent import Agent, ToolDef, define_tool, on_assignment

    @define_tool(description="Search the web.", parameters={...})
    async def web_search(query: str) -> dict:
        return {"results": [...]}

    @Agent("analyst", model="gpt-4o", memory="episodic", tools=[web_search])
    class Analyst:
        @on_assignment
        async def work(self, intent):
            return await self.think(intent.description)

    Analyst.run()
    ```
"""

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Callable, Optional, Union

logger = logging.getLogger("openintent.llm")

OPENAI_STYLE_PROVIDERS = {"openai", "azure_openai", "deepseek", "grok", "openrouter"}
ANTHROPIC_STYLE_PROVIDERS = {"anthropic"}
GEMINI_STYLE_PROVIDERS = {"gemini"}


@dataclass
class ToolDef:
    """Definition for a tool that an LLM-powered agent can call.

    Provides the LLM with a rich description and parameter schema so it
    knows *what* the tool does, *what arguments* it accepts, and *how* to
    call it.  When the LLM decides to invoke the tool, the ``handler``
    callable is executed locally and — when connected to an OpenIntent
    server — each invocation is automatically recorded as a protocol
    event for auditability.

    Example — inline definition::

        ToolDef(
            name="web_search",
            description="Search the web and return top results.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query."},
                    "max_results": {"type": "integer", "description": "Max results.", "default": 5},
                },
                "required": ["query"],
            },
            handler=my_search_function,
        )

    Example — via ``@define_tool`` decorator::

        @define_tool(description="Search the web.", parameters={...})
        async def web_search(query: str, max_results: int = 5) -> dict:
            ...
    """

    name: str
    description: str
    parameters: dict = field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "input": {"type": "string", "description": "Input for the tool."},
            },
            "required": ["input"],
        }
    )
    handler: Optional[Callable] = None

    def to_schema(self) -> dict:
        """Return the tool definition as a JSON-schema dict for the LLM."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


Tool = ToolDef


def define_tool(
    name: Optional[str] = None,
    description: str = "",
    parameters: Optional[dict] = None,
) -> Callable:
    """Decorator that turns a function into a :class:`ToolDef`.

    The decorated function becomes the tool handler.  Its ``__name__`` is
    used as the tool name unless *name* is supplied explicitly.

    Usage::

        @define_tool(description="Fetch current weather.", parameters={
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City name."},
            },
            "required": ["city"],
        })
        async def get_weather(city: str) -> dict:
            return {"temperature": 22, "unit": "C"}
    """

    def decorator(func: Callable) -> ToolDef:
        tool_name = name or func.__name__
        tool_params = parameters or {
            "type": "object",
            "properties": {
                "input": {"type": "string", "description": "Input for the tool."},
            },
            "required": ["input"],
        }
        return ToolDef(
            name=tool_name,
            description=description or func.__doc__ or f"Tool: {tool_name}",
            parameters=tool_params,
            handler=func,
        )

    return decorator


tool = define_tool

ToolInput = Union[str, ToolDef]


@dataclass
class LLMConfig:
    """Configuration for LLM-powered agent behavior."""

    model: str = ""
    provider: str = "openai"
    api_key: Optional[str] = None
    system_prompt: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 4096
    max_tool_rounds: int = 10
    auto_memory: bool = True
    planning: bool = False
    context_window: int = 128000
    stream_by_default: bool = False


def _resolve_provider(model: str) -> str:
    """Infer provider from model name if not explicitly set."""
    m = model.lower()
    if m.startswith("claude"):
        return "anthropic"
    if m.startswith("gemini"):
        return "gemini"
    if m.startswith("grok"):
        return "grok"
    if m.startswith("deepseek"):
        return "deepseek"
    if "/" in m:
        return "openrouter"
    return "openai"


# ---------------------------------------------------------------------------
# Built-in Protocol Tools
# ---------------------------------------------------------------------------

PROTOCOL_TOOLS_AGENT = [
    {
        "name": "remember",
        "description": "Store a key-value pair in agent memory for later retrieval. Use this to save important observations, intermediate results, or context you'll need later.",
        "parameters": {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "A descriptive key for the memory entry.",
                },
                "value": {"type": "string", "description": "The value to store."},
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional tags for categorizing the memory.",
                },
            },
            "required": ["key", "value"],
        },
    },
    {
        "name": "recall",
        "description": "Search agent memory for previously stored information. Returns relevant memory entries matching the query.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query to find relevant memories.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of entries to return. Default 5.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "update_status",
        "description": "Update the current intent's state with progress information.",
        "parameters": {
            "type": "object",
            "properties": {
                "updates": {
                    "type": "object",
                    "description": "Key-value pairs to merge into the intent state.",
                    "additionalProperties": True,
                },
            },
            "required": ["updates"],
        },
    },
    {
        "name": "clarify",
        "description": "Ask a clarifying question when you need human input to proceed. This pauses the intent and waits for a response. Use sparingly - only when genuinely blocked.",
        "parameters": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The clarifying question to ask.",
                },
                "options": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of suggested answers.",
                },
            },
            "required": ["question"],
        },
    },
    {
        "name": "escalate",
        "description": "Escalate the current task to a human or higher-authority coordinator. Use when the task is beyond your capability or authority.",
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Why this needs escalation.",
                },
                "context": {
                    "type": "object",
                    "description": "Additional context for the reviewer.",
                    "additionalProperties": True,
                },
            },
            "required": ["reason"],
        },
    },
]

PROTOCOL_TOOLS_COORDINATOR = PROTOCOL_TOOLS_AGENT + [
    {
        "name": "delegate",
        "description": "Assign a task or intent to a specific agent from your managed pool.",
        "parameters": {
            "type": "object",
            "properties": {
                "agent_id": {
                    "type": "string",
                    "description": "The ID of the agent to delegate to.",
                },
                "task_description": {
                    "type": "string",
                    "description": "What the agent should do.",
                },
                "priority": {
                    "type": "string",
                    "enum": ["low", "normal", "high"],
                    "description": "Task priority.",
                },
            },
            "required": ["agent_id", "task_description"],
        },
    },
    {
        "name": "create_plan",
        "description": "Decompose the current goal into a structured plan with ordered tasks.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Name for the plan."},
                "tasks": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "description": {"type": "string"},
                            "assign_to": {
                                "type": "string",
                                "description": "Agent ID to assign to.",
                            },
                            "depends_on": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Titles of tasks this depends on.",
                            },
                        },
                        "required": ["title"],
                    },
                    "description": "Ordered list of tasks in the plan.",
                },
            },
            "required": ["name", "tasks"],
        },
    },
    {
        "name": "record_decision",
        "description": "Record an auditable governance decision with reasoning.",
        "parameters": {
            "type": "object",
            "properties": {
                "decision_type": {
                    "type": "string",
                    "enum": [
                        "task_assigned",
                        "plan_created",
                        "escalation_resolved",
                        "failure_handled",
                        "plan_modified",
                    ],
                    "description": "Category of decision.",
                },
                "summary": {
                    "type": "string",
                    "description": "Brief description of the decision.",
                },
                "rationale": {
                    "type": "string",
                    "description": "Reasoning behind the decision.",
                },
            },
            "required": ["decision_type", "summary"],
        },
    },
]


def _tools_to_openai_format(tools: list[dict]) -> list[dict]:
    """Convert protocol tool definitions to OpenAI function-calling format."""
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["parameters"],
            },
        }
        for t in tools
    ]


def _tools_to_anthropic_format(tools: list[dict]) -> list[dict]:
    """Convert protocol tool definitions to Anthropic tool format."""
    return [
        {
            "name": t["name"],
            "description": t["description"],
            "input_schema": t["parameters"],
        }
        for t in tools
    ]


# ---------------------------------------------------------------------------
# Context Assembly
# ---------------------------------------------------------------------------


class ContextAssembler:
    """Assembles LLM prompts from protocol state.

    Packs memory, task state, plan progress, tool descriptions, and
    conversation history into a coherent prompt the LLM can reason over.
    """

    @staticmethod
    def build_system_prompt(
        agent_id: str,
        custom_prompt: Optional[str],
        role: str,
        available_tools: list[dict],
        managed_agents: Optional[list[str]] = None,
        planning_enabled: bool = False,
    ) -> str:
        parts = []

        if custom_prompt:
            parts.append(custom_prompt)

        parts.append(
            f"\nYou are operating as an OpenIntent {role} with ID '{agent_id}'."
        )

        if role == "coordinator" and managed_agents:
            parts.append(
                f"You coordinate these agents: {', '.join(managed_agents)}. "
                "You delegate work, resolve conflicts, and make governance decisions."
            )

        parts.append(
            "\nYou have access to the following protocol tools that let you "
            "interact with the coordination system. Use them when appropriate:"
        )
        for tool in available_tools:
            parts.append(f"  - {tool['name']}: {tool['description']}")

        if planning_enabled:
            parts.append(
                "\nPlanning is enabled. You can decompose complex goals into "
                "structured task plans using the create_plan tool."
            )

        parts.append(
            "\nGuidelines:"
            "\n- Use 'remember' to save important observations for later."
            "\n- Use 'recall' to retrieve relevant context before making decisions."
            "\n- Use 'clarify' only when genuinely blocked and need human input."
            "\n- Use 'escalate' when the task exceeds your authority or capability."
            "\n- Always provide clear, structured responses."
        )

        return "\n".join(parts)

    @staticmethod
    async def build_context_messages(
        agent: Any,
        intent: Any = None,
        task_description: Optional[str] = None,
        conversation_history: Optional[list[dict]] = None,
    ) -> list[dict]:
        """Build the context messages for the LLM call."""
        messages = []

        context_parts = []

        if intent:
            context_parts.append(
                f"Current intent: {intent.title}\n"
                f"Description: {intent.description}\n"
                f"Status: {intent.status.value if hasattr(intent.status, 'value') else intent.status}\n"
                f"State: {json.dumps(intent.state.to_dict() if hasattr(intent.state, 'to_dict') else intent.state, default=str)}"
            )

            if hasattr(intent, "ctx") and intent.ctx:
                ctx = intent.ctx
                if hasattr(ctx, "dependencies") and ctx.dependencies:
                    context_parts.append(
                        f"Dependencies: {json.dumps(ctx.dependencies, default=str)}"
                    )
                if hasattr(ctx, "delegated_by") and ctx.delegated_by:
                    context_parts.append(f"Delegated by: {ctx.delegated_by}")

        if hasattr(agent, "_config") and agent._config.memory:
            try:
                memories = await agent.memory.recall(limit=10)
                if memories:
                    memory_text = "\n".join(
                        f"  [{m.get('key', '?')}]: {m.get('value', '')}"
                        for m in (memories if isinstance(memories, list) else [])
                    )
                    if memory_text.strip():
                        context_parts.append(f"Relevant memories:\n{memory_text}")
            except Exception:
                pass

        if context_parts:
            messages.append(
                {
                    "role": "user",
                    "content": "Context:\n" + "\n\n".join(context_parts),
                }
            )

        if conversation_history:
            messages.extend(conversation_history)

        if task_description:
            messages.append({"role": "user", "content": task_description})

        return messages


# ---------------------------------------------------------------------------
# Protocol Tool Executor
# ---------------------------------------------------------------------------


class ProtocolToolExecutor:
    """Executes built-in protocol tools against the agent's protocol state."""

    def __init__(self, agent: Any, intent: Any = None) -> None:
        self._agent = agent
        self._intent = intent

    async def execute(self, tool_name: str, arguments: dict) -> dict:
        """Execute a protocol tool and return the result."""
        handler = getattr(self, f"_exec_{tool_name}", None)
        if handler:
            return await handler(arguments)  # type: ignore[no-any-return]
        return {"error": f"Unknown tool: {tool_name}"}

    async def _exec_remember(self, args: dict) -> dict:
        try:
            await self._agent.memory.store(
                key=args["key"],
                value=args["value"],
                tags=args.get("tags", []),
            )
            return {"status": "stored", "key": args["key"]}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def _exec_recall(self, args: dict) -> dict:
        try:
            results = await self._agent.memory.recall(
                query=args.get("query"),
                limit=args.get("limit", 5),
            )
            if isinstance(results, list):
                return {"memories": results}
            return {"memories": []}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def _exec_update_status(self, args: dict) -> dict:
        if not self._intent:
            return {"error": "No active intent"}
        try:
            await self._agent.patch_state(self._intent.id, args["updates"])
            return {"status": "updated", "updates": args["updates"]}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def _exec_clarify(self, args: dict) -> dict:
        if not self._intent:
            return {"error": "No active intent"}
        try:
            await self._agent.async_client.request_arbitration(
                self._intent.id,
                reason=f"Clarification needed: {args['question']}",
                context={
                    "type": "clarification",
                    "question": args["question"],
                    "options": args.get("options", []),
                    "agent_id": self._agent._agent_id,
                },
            )
            return {
                "status": "awaiting_response",
                "question": args["question"],
                "message": "Intent paused. Waiting for human response.",
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def _exec_escalate(self, args: dict) -> dict:
        if not self._intent:
            return {"error": "No active intent"}
        try:
            await self._agent.escalate(
                self._intent.id,
                reason=args["reason"],
                data=args.get("context", {}),
            )
            return {"status": "escalated", "reason": args["reason"]}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def _exec_delegate(self, args: dict) -> dict:
        if not self._intent:
            return {"error": "No active intent"}
        try:
            await self._agent.delegate(
                self._intent.id,
                target_agent_id=args["agent_id"],
                payload={
                    "task": args.get("task_description", ""),
                    "priority": args.get("priority", "normal"),
                },
            )
            if hasattr(self._agent, "record_decision"):
                await self._agent.record_decision(
                    "task_assigned",
                    f"Delegated to {args['agent_id']}: {args.get('task_description', '')}",
                )
            return {"status": "delegated", "agent_id": args["agent_id"]}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def _exec_create_plan(self, args: dict) -> dict:
        try:
            from .agents import IntentSpec, PortfolioSpec

            intents = []
            for t in args.get("tasks", []):
                intents.append(
                    IntentSpec(
                        title=t["title"],
                        description=t.get("description", ""),
                        assign=t.get("assign_to"),
                        depends_on=t.get("depends_on", []),
                    )
                )

            spec = PortfolioSpec(name=args["name"], intents=intents)

            if hasattr(self._agent, "create_portfolio"):
                portfolio = await self._agent.create_portfolio(spec)
                return {
                    "status": "plan_created",
                    "portfolio_id": portfolio.id,
                    "task_count": len(intents),
                }

            return {
                "status": "plan_defined",
                "name": args["name"],
                "task_count": len(intents),
                "tasks": [t["title"] for t in args.get("tasks", [])],
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def _exec_record_decision(self, args: dict) -> dict:
        try:
            if hasattr(self._agent, "record_decision"):
                record = await self._agent.record_decision(
                    decision_type=args["decision_type"],
                    summary=args["summary"],
                    rationale=args.get("rationale", ""),
                )
                return {"status": "recorded", "decision": record}
            return {"error": "record_decision not available (not a coordinator)"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


# ---------------------------------------------------------------------------
# LLM Engine — The core think() and think_stream() implementation
# ---------------------------------------------------------------------------


class LLMEngine:
    """Core engine that powers self.think() and self.think_stream().

    Handles the agentic loop: send messages to LLM, process tool calls,
    feed results back, repeat until the LLM produces a final answer.
    Supports both OpenAI-style and Anthropic-style APIs.
    """

    def __init__(self, agent: Any, llm_config: LLMConfig) -> None:
        self._agent = agent
        self._config = llm_config
        self._conversation_history: list[dict] = []
        self._provider = llm_config.provider or _resolve_provider(llm_config.model)

    @property
    def _is_coordinator(self) -> bool:
        return hasattr(self._agent, "_agents_list")

    @property
    def _protocol_tools(self) -> list[dict]:
        if self._is_coordinator:
            return PROTOCOL_TOOLS_COORDINATOR
        return PROTOCOL_TOOLS_AGENT

    @property
    def _external_tools(self) -> list[dict]:
        """Get external tool definitions from the agent's tool list.

        Accepts both ``ToolDef`` objects (rich schema + local handler) and
        plain strings (protocol grant names resolved via RFC-0014).
        """
        tool_defs = []
        if hasattr(self._agent, "_config") and self._agent._config.tools:
            for entry in self._agent._config.tools:
                if isinstance(entry, ToolDef):
                    tool_defs.append(entry.to_schema())
                else:
                    tool_defs.append(
                        {
                            "name": entry,
                            "description": f"External tool: {entry}. Invoke through the protocol's tool grant system (RFC-0014).",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "input": {
                                        "type": "string",
                                        "description": "Input for the tool.",
                                    },
                                },
                                "required": ["input"],
                            },
                        }
                    )
        return tool_defs

    @property
    def _local_tool_handlers(self) -> dict[str, Callable]:
        """Map of tool name -> callable handler for locally defined ToolDefs."""
        handlers: dict[str, Callable] = {}
        if hasattr(self._agent, "_config") and self._agent._config.tools:
            for entry in self._agent._config.tools:
                if isinstance(entry, ToolDef) and entry.handler is not None:
                    handlers[entry.name] = entry.handler
        return handlers

    @property
    def _all_tools(self) -> list[dict]:
        return self._protocol_tools + self._external_tools

    def _build_system(self, intent: Any = None) -> str:
        managed = getattr(self._agent, "_agents_list", None)
        return ContextAssembler.build_system_prompt(
            agent_id=self._agent._agent_id,
            custom_prompt=self._config.system_prompt,
            role="coordinator" if self._is_coordinator else "agent",
            available_tools=self._all_tools,
            managed_agents=managed,
            planning_enabled=self._config.planning,
        )

    async def think(
        self,
        prompt: str,
        intent: Any = None,
        stream: Optional[bool] = None,
        on_token: Optional[Callable[[str], None]] = None,
        **kwargs: Any,
    ) -> Union[str, AsyncIterator[str]]:
        """Run the agentic loop: reason, act, observe, repeat.

        Args:
            prompt: The task or question for the LLM.
            intent: Optional intent context.
            stream: Whether to stream the final response. Defaults to config.
            on_token: Optional callback for each streamed token.
            **kwargs: Additional parameters passed to the LLM.

        Returns:
            Final text response (str) or async iterator of tokens if streaming.
        """
        should_stream = stream if stream is not None else self._config.stream_by_default

        if should_stream:
            return self._think_stream(prompt, intent, on_token, **kwargs)

        return await self._think_complete(prompt, intent, **kwargs)

    async def _think_complete(
        self,
        prompt: str,
        intent: Any = None,
        **kwargs: Any,
    ) -> str:
        """Non-streaming agentic loop."""
        system = self._build_system(intent)
        context_messages = await ContextAssembler.build_context_messages(
            self._agent,
            intent=intent,
            task_description=prompt,
            conversation_history=list(self._conversation_history),
        )

        messages = [{"role": "system", "content": system}] + context_messages

        tools_formatted = self._format_tools_for_provider()
        executor = ProtocolToolExecutor(self._agent, intent)
        local_handlers = self._local_tool_handlers

        for _round in range(self._config.max_tool_rounds):
            response = await self._call_llm(messages, tools_formatted, **kwargs)

            tool_calls = self._extract_tool_calls(response)

            if not tool_calls:
                content = self._extract_content(response)
                self._conversation_history.append({"role": "user", "content": prompt})
                self._conversation_history.append(
                    {"role": "assistant", "content": content}
                )

                if self._config.auto_memory and intent:
                    try:
                        await self._agent.memory.store(
                            key=f"task_result_{intent.id}_{int(time.time())}",
                            value=content[:500],
                            tags=["auto", "task_result"],
                        )
                    except Exception:
                        pass

                return content

            messages.append(self._build_assistant_message(response))

            for tc in tool_calls:
                tool_name = tc["name"]
                try:
                    arguments = (
                        json.loads(tc["arguments"])
                        if isinstance(tc["arguments"], str)
                        else tc["arguments"]
                    )
                except (json.JSONDecodeError, TypeError):
                    arguments = {}

                result = await self._execute_tool(
                    tool_name,
                    arguments,
                    executor,
                    local_handlers,
                    intent,
                )

                if (
                    tool_name == "clarify"
                    and result.get("status") == "awaiting_response"
                ):
                    return json.dumps(result)

                messages.append(self._build_tool_result_message(tc, result))

        return self._extract_content(await self._call_llm(messages, [], **kwargs))

    async def _think_stream(
        self,
        prompt: str,
        intent: Any = None,
        on_token: Optional[Callable[[str], None]] = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Streaming agentic loop.

        Runs the tool loop internally (non-streaming) for intermediate rounds,
        then streams the final response token by token.
        """
        system = self._build_system(intent)
        context_messages = await ContextAssembler.build_context_messages(
            self._agent,
            intent=intent,
            task_description=prompt,
            conversation_history=list(self._conversation_history),
        )

        messages = [{"role": "system", "content": system}] + context_messages

        tools_formatted = self._format_tools_for_provider()
        executor = ProtocolToolExecutor(self._agent, intent)
        local_handlers = self._local_tool_handlers

        for _round in range(self._config.max_tool_rounds):
            response = await self._call_llm(messages, tools_formatted, **kwargs)

            tool_calls = self._extract_tool_calls(response)

            if not tool_calls:
                break

            messages.append(self._build_assistant_message(response))

            for tc in tool_calls:
                tool_name = tc["name"]
                try:
                    arguments = (
                        json.loads(tc["arguments"])
                        if isinstance(tc["arguments"], str)
                        else tc["arguments"]
                    )
                except (json.JSONDecodeError, TypeError):
                    arguments = {}

                result = await self._execute_tool(
                    tool_name,
                    arguments,
                    executor,
                    local_handlers,
                    intent,
                )

                if (
                    tool_name == "clarify"
                    and result.get("status") == "awaiting_response"
                ):
                    yield json.dumps(result)
                    return

                messages.append(self._build_tool_result_message(tc, result))

        async for token in self._stream_llm(messages, **kwargs):
            if on_token:
                try:
                    on_token(token)
                except Exception:
                    pass
            yield token

        self._conversation_history.append({"role": "user", "content": prompt})

    # -----------------------------------------------------------------------
    # Provider-specific LLM calling
    # -----------------------------------------------------------------------

    async def _emit_tool_event(
        self,
        tool_name: str,
        arguments: dict,
        result: dict,
        duration_ms: float,
        intent: Any = None,
    ) -> None:
        """Emit a protocol event recording a tool invocation for auditability.

        Automatically called after every local tool handler execution.
        Silently skipped when there is no active intent or the server is
        unreachable — tracing is a best-effort benefit, never a blocker.
        """
        target_intent = intent or getattr(self, "_current_intent", None)
        if not target_intent:
            return
        try:
            await self._agent.async_client.log_event(
                target_intent.id,
                "tool_invocation",
                {
                    "tool_name": tool_name,
                    "arguments": arguments,
                    "result": result,
                    "duration_ms": round(duration_ms, 2),
                    "agent_id": self._agent._agent_id,
                },
            )
        except Exception:
            pass

    async def _execute_tool(
        self,
        tool_name: str,
        arguments: dict,
        executor: "ProtocolToolExecutor",
        local_handlers: dict[str, Callable[..., Any]],
        intent: Any = None,
    ) -> dict:
        """Route a tool call to the right handler.

        Priority:
        1. Protocol tools (remember, recall, clarify, …)
        2. Local handlers (ToolDef objects with a callable handler)
        3. Remote protocol grants (plain string tool names via RFC-0014)

        Local handler invocations are automatically traced as protocol
        events when connected to an OpenIntent server.
        """
        if tool_name in {t["name"] for t in self._protocol_tools}:
            return await executor.execute(tool_name, arguments)

        if tool_name in local_handlers:
            t0 = time.time()
            try:
                handler = local_handlers[tool_name]
                if asyncio.iscoroutinefunction(handler):
                    raw = await handler(**arguments)
                else:
                    raw = handler(**arguments)
                result = raw if isinstance(raw, dict) else {"result": str(raw)}
            except Exception as e:
                result = {"error": str(e)}
            duration_ms = (time.time() - t0) * 1000
            await self._emit_tool_event(
                tool_name,
                arguments,
                result,
                duration_ms,
                intent,
            )
            return result

        try:
            raw = await self._agent.tools.invoke(
                tool_name,
                input=arguments.get("input", ""),
            )
            if isinstance(raw, dict):
                return raw
            return {"result": str(raw)}
        except Exception as e:
            return {"error": str(e)}

    def _format_tools_for_provider(self) -> list[dict]:
        tools = self._all_tools
        if not tools:
            return []
        if self._provider in ANTHROPIC_STYLE_PROVIDERS:
            return _tools_to_anthropic_format(tools)
        return _tools_to_openai_format(tools)

    async def _call_llm(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]], **kwargs: Any
    ) -> Any:
        """Call the LLM (non-streaming) and return the raw response."""
        call_kwargs = {
            "model": self._config.model,
            "messages": messages,
            "temperature": kwargs.get("temperature", self._config.temperature),
            "max_tokens": kwargs.get("max_tokens", self._config.max_tokens),
        }

        if tools:
            if self._provider in ANTHROPIC_STYLE_PROVIDERS:
                call_kwargs["tools"] = tools
            else:
                call_kwargs["tools"] = tools

        if self._provider in ANTHROPIC_STYLE_PROVIDERS:
            call_kwargs["system"] = messages[0]["content"]
            call_kwargs["messages"] = [m for m in messages[1:] if m["role"] != "system"]

        adapter = getattr(self._agent, "_llm_adapter", None)
        if adapter:
            if self._provider in ANTHROPIC_STYLE_PROVIDERS:
                response = adapter.messages.create(**call_kwargs)
            elif self._provider in GEMINI_STYLE_PROVIDERS:
                response = adapter.generate_content(
                    messages[-1]["content"] if messages else "",
                )
            else:
                call_kwargs.pop("system", None)
                response = adapter.chat.completions.create(**call_kwargs)
        else:
            response = await self._call_raw_provider(call_kwargs)

        if asyncio.iscoroutine(response):
            response = await response

        return response

    async def _call_raw_provider(self, call_kwargs: dict) -> Any:
        """Fallback: call provider API directly without adapter wrapper."""
        if self._provider in OPENAI_STYLE_PROVIDERS:
            try:
                import openai

                client = openai.OpenAI(api_key=self._config.api_key)
                call_kwargs.pop("system", None)
                return client.chat.completions.create(**call_kwargs)
            except ImportError:
                raise ImportError(
                    "openai package required. Install with: pip install openai"
                )

        elif self._provider in ANTHROPIC_STYLE_PROVIDERS:
            try:
                import anthropic

                client = anthropic.Anthropic(api_key=self._config.api_key)
                return client.messages.create(**call_kwargs)
            except ImportError:
                raise ImportError(
                    "anthropic package required. Install with: pip install anthropic"
                )

        raise ValueError(f"Unsupported provider: {self._provider}")

    async def _stream_llm(
        self, messages: list[dict[str, Any]], **kwargs: Any
    ) -> AsyncIterator[str]:
        """Stream the final LLM response token by token."""
        call_kwargs = {
            "model": self._config.model,
            "messages": messages,
            "temperature": kwargs.get("temperature", self._config.temperature),
            "max_tokens": kwargs.get("max_tokens", self._config.max_tokens),
            "stream": True,
        }

        if self._provider in ANTHROPIC_STYLE_PROVIDERS:
            call_kwargs["system"] = messages[0]["content"]
            call_kwargs["messages"] = [m for m in messages[1:] if m["role"] != "system"]

        adapter = getattr(self._agent, "_llm_adapter", None)

        if adapter:
            if self._provider in ANTHROPIC_STYLE_PROVIDERS:
                stream = adapter.messages.stream(**call_kwargs)
                async for token in self._iter_anthropic_stream(stream):
                    yield token
            elif self._provider in GEMINI_STYLE_PROVIDERS:
                response = adapter.generate_content(
                    messages[-1]["content"] if messages else "",
                    stream=True,
                )
                for chunk in response:
                    if hasattr(chunk, "text") and chunk.text:
                        yield chunk.text
            else:
                call_kwargs.pop("system", None)
                stream = adapter.chat.completions.create(**call_kwargs)
                async for token in self._iter_openai_stream(stream):
                    yield token
        else:
            async for token in self._stream_raw_provider(call_kwargs):
                yield token

    async def _stream_raw_provider(self, call_kwargs: dict) -> AsyncIterator[str]:
        """Fallback streaming without adapter."""
        if self._provider in OPENAI_STYLE_PROVIDERS:
            try:
                import openai

                client = openai.OpenAI(api_key=self._config.api_key)
                call_kwargs.pop("system", None)
                stream = client.chat.completions.create(**call_kwargs)
                async for token in self._iter_openai_stream(stream):
                    yield token
            except ImportError:
                raise ImportError("openai package required.")
        elif self._provider in ANTHROPIC_STYLE_PROVIDERS:
            try:
                import anthropic

                client = anthropic.Anthropic(api_key=self._config.api_key)
                with client.messages.stream(**call_kwargs) as stream:
                    for text in stream.text_stream:
                        yield text
            except ImportError:
                raise ImportError("anthropic package required.")

    async def _iter_openai_stream(self, stream: Any) -> AsyncIterator[str]:
        """Iterate an OpenAI-style stream (sync iterator) yielding tokens."""
        for chunk in stream:
            if hasattr(chunk, "choices") and chunk.choices:
                delta = chunk.choices[0].delta
                if hasattr(delta, "content") and delta.content:
                    yield delta.content
            elif isinstance(chunk, dict):
                choices = chunk.get("choices", [])
                if choices:
                    content = choices[0].get("delta", {}).get("content")
                    if content:
                        yield content

    async def _iter_anthropic_stream(self, stream: Any) -> AsyncIterator[str]:
        """Iterate an Anthropic-style stream yielding tokens."""
        if hasattr(stream, "__enter__"):
            with stream as s:
                if hasattr(s, "text_stream"):
                    for text in s.text_stream:
                        yield text
                else:
                    for event in s:
                        if (
                            hasattr(event, "type")
                            and event.type == "content_block_delta"
                        ):
                            if hasattr(event, "delta") and hasattr(event.delta, "text"):
                                yield event.delta.text
        else:
            for event in stream:
                if hasattr(event, "type") and event.type == "content_block_delta":
                    if hasattr(event, "delta") and hasattr(event.delta, "text"):
                        yield event.delta.text

    # -----------------------------------------------------------------------
    # Response parsing (provider-agnostic)
    # -----------------------------------------------------------------------

    def _extract_content(self, response: Any) -> str:
        """Extract text content from any provider's response."""
        if isinstance(response, str):
            return response
        if isinstance(response, dict):
            choices = response.get("choices", [])
            if choices:
                return str(choices[0].get("message", {}).get("content", ""))
            content = response.get("content", [])
            if isinstance(content, list):
                return " ".join(
                    b.get("text", "")
                    for b in content
                    if isinstance(b, dict) and b.get("type") == "text"
                )
            return str(response)

        if hasattr(response, "choices") and response.choices:
            msg = response.choices[0].message
            return msg.content or ""

        if hasattr(response, "content"):
            content = response.content
            if isinstance(content, list):
                return " ".join(
                    getattr(b, "text", "")
                    for b in content
                    if getattr(b, "type", "") == "text"
                )
            if isinstance(content, str):
                return content

        if hasattr(response, "text"):
            return str(response.text)

        return str(response)

    def _extract_tool_calls(self, response: Any) -> list[dict[str, Any]]:
        """Extract tool calls from any provider's response."""
        calls = []

        if isinstance(response, dict):
            choices = response.get("choices", [])
            if choices:
                msg = choices[0].get("message", {})
                for tc in msg.get("tool_calls", []):
                    calls.append(
                        {
                            "id": tc.get("id", str(uuid.uuid4())),
                            "name": tc.get("function", {}).get("name", ""),
                            "arguments": tc.get("function", {}).get("arguments", "{}"),
                        }
                    )
            content = response.get("content", [])
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        calls.append(
                            {
                                "id": block.get("id", str(uuid.uuid4())),
                                "name": block.get("name", ""),
                                "arguments": block.get("input", {}),
                            }
                        )
            return calls

        if hasattr(response, "choices") and response.choices:
            msg = response.choices[0].message
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    calls.append(
                        {
                            "id": tc.id if hasattr(tc, "id") else str(uuid.uuid4()),
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        }
                    )

        if hasattr(response, "content") and isinstance(response.content, list):
            for block in response.content:
                if getattr(block, "type", "") == "tool_use":
                    calls.append(
                        {
                            "id": getattr(block, "id", str(uuid.uuid4())),
                            "name": block.name,
                            "arguments": block.input if hasattr(block, "input") else {},
                        }
                    )

        return calls

    def _build_assistant_message(self, response: Any) -> dict[str, Any]:
        """Build assistant message from response (with tool calls)."""
        if self._provider in ANTHROPIC_STYLE_PROVIDERS:
            content = []
            if hasattr(response, "content") and isinstance(response.content, list):
                for block in response.content:
                    if getattr(block, "type", "") == "text":
                        content.append({"type": "text", "text": block.text})
                    elif getattr(block, "type", "") == "tool_use":
                        content.append(
                            {
                                "type": "tool_use",
                                "id": block.id,
                                "name": block.name,
                                "input": block.input,
                            }
                        )
            return {"role": "assistant", "content": content}

        msg: dict[str, Any] = {
            "role": "assistant",
            "content": self._extract_content(response),
        }

        tool_calls = self._extract_tool_calls(response)
        if tool_calls:
            msg["tool_calls"] = [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {
                        "name": tc["name"],
                        "arguments": (
                            tc["arguments"]
                            if isinstance(tc["arguments"], str)
                            else json.dumps(tc["arguments"])
                        ),
                    },
                }
                for tc in tool_calls
            ]

        return msg

    def _build_tool_result_message(self, tool_call: dict, result: dict) -> dict:
        """Build tool result message for the conversation."""
        result_str = json.dumps(result, default=str)

        if self._provider in ANTHROPIC_STYLE_PROVIDERS:
            return {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_call["id"],
                        "content": result_str,
                    }
                ],
            }

        return {
            "role": "tool",
            "tool_call_id": tool_call["id"],
            "content": result_str,
        }

    def reset_history(self) -> None:
        """Clear conversation history."""
        self._conversation_history.clear()
