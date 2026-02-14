"""
OpenIntent SDK - MCP (Model Context Protocol) Bridge.

Enables bidirectional integration between OpenIntent workflows and MCP tool servers:
  - Consume external MCP tools as OpenIntent tool providers
  - Expose OpenIntent tools outward as MCP tools
  - First-class ``MCPTool`` for ``@Agent(tools=[...])`` declarations
  - ``mcp://`` URI scheme for inline tool references
  - YAML ``mcp:`` block configuration for declarative MCP server connections
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    _MCP_AVAILABLE = True
except ImportError:
    _MCP_AVAILABLE = False

logger = logging.getLogger("openintent.mcp")


def _require_mcp() -> None:
    """Raise a helpful error if the MCP SDK is not installed."""
    if not _MCP_AVAILABLE:
        raise ImportError(
            "MCP SDK is required for live MCP server connections. "
            "Install with: pip install mcp"
        )


@dataclass
class MCPSecurityConfig:
    """Security settings for MCP connections."""

    tls_required: bool = False
    api_key_env: Optional[str] = None
    credential_isolation: bool = True
    audit: bool = True
    max_retries: int = 3


@dataclass
class MCPServerConfig:
    """Configuration for connecting to an external MCP server."""

    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    timeout: int = 30
    allowed_tools: Optional[list[str]] = None
    security: Optional[MCPSecurityConfig] = None


class MCPToolProvider:
    """Wraps an external MCP server connection as an OpenIntent tool provider."""

    def __init__(self, config: MCPServerConfig) -> None:
        self._config = config
        self._session: Any = None
        self._connected = False
        self._cached_tools: list[dict[str, Any]] = []

    @property
    def connected(self) -> bool:
        """Whether the provider is currently connected to the MCP server."""
        return self._connected

    async def connect(self) -> None:
        """Establish connection to the MCP server via stdio transport."""
        _require_mcp()
        resolved_env = {
            k: os.environ.get(v.strip("${}"), v) if v.startswith("${") else v
            for k, v in self._config.env.items()
        }
        server_params = StdioServerParameters(
            command=self._config.command,
            args=self._config.args,
            env=resolved_env or None,
        )
        logger.info(
            "Connecting to MCP server '%s': %s %s",
            self._config.name,
            self._config.command,
            " ".join(self._config.args),
        )
        self._stdio_context = stdio_client(server_params)
        streams = await self._stdio_context.__aenter__()
        self._session = ClientSession(*streams)
        await self._session.__aenter__()
        await self._session.initialize()
        self._connected = True
        logger.info("Connected to MCP server '%s'", self._config.name)

    async def disconnect(self) -> None:
        """Close the connection to the MCP server."""
        if self._session is not None:
            try:
                await self._session.__aexit__(None, None, None)
            except Exception:
                pass
            self._session = None
        if hasattr(self, "_stdio_context") and self._stdio_context is not None:
            try:
                await self._stdio_context.__aexit__(None, None, None)
            except Exception:
                pass
            self._stdio_context = None
        self._connected = False
        logger.info("Disconnected from MCP server '%s'", self._config.name)

    async def list_tools(self) -> list[dict[str, Any]]:
        """List available tools from the MCP server, applying allowlist filter."""
        if not self._connected or self._session is None:
            raise RuntimeError(
                f"Not connected to MCP server '{self._config.name}'. "
                "Call connect() first."
            )
        response = await self._session.list_tools()
        tools: list[dict[str, Any]] = []
        for t in response.tools:
            tool_dict: dict[str, Any] = {
                "name": t.name,
                "description": getattr(t, "description", ""),
                "inputSchema": getattr(t, "inputSchema", {}),
            }
            if self._config.allowed_tools is not None:
                if t.name not in self._config.allowed_tools:
                    continue
            tools.append(tool_dict)
        self._cached_tools = tools
        return tools

    async def invoke(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        context: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Invoke a tool on the MCP server."""
        if not self._connected or self._session is None:
            raise RuntimeError(
                f"Not connected to MCP server '{self._config.name}'. "
                "Call connect() first."
            )
        security = self._config.security or MCPSecurityConfig()
        if security.audit:
            logger.info(
                "MCP tool invoke: server='%s' tool='%s' args=%s",
                self._config.name,
                tool_name,
                list(arguments.keys()),
            )
        last_error: Optional[Exception] = None
        for attempt in range(1, security.max_retries + 1):
            try:
                result = await self._session.call_tool(tool_name, arguments)
                response: dict[str, Any] = {
                    "server": self._config.name,
                    "tool": tool_name,
                    "content": [
                        {
                            "type": getattr(c, "type", "text"),
                            "text": getattr(c, "text", str(c)),
                        }
                        for c in result.content
                    ],
                    "isError": getattr(result, "isError", False),
                }
                if security.audit:
                    logger.info(
                        "MCP tool result: server='%s' tool='%s' error=%s",
                        self._config.name,
                        tool_name,
                        response["isError"],
                    )
                return response
            except Exception as exc:
                last_error = exc
                if attempt < security.max_retries:
                    logger.warning(
                        "MCP invoke attempt %d/%d failed for '%s.%s': %s",
                        attempt,
                        security.max_retries,
                        self._config.name,
                        tool_name,
                        exc,
                    )
                    continue
                break
        raise RuntimeError(
            f"MCP tool invocation failed after {security.max_retries} attempts: "
            f"{last_error}"
        )

    async def __aenter__(self) -> MCPToolProvider:
        await self.connect()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.disconnect()


class MCPToolExporter:
    """Exposes OpenIntent tools as MCP tools."""

    def __init__(self, tools: list[dict[str, Any]]) -> None:
        self._tools = tools
        self._handlers: dict[str, Any] = {}
        for t in tools:
            name = t.get("name", "")
            handler = t.get("handler")
            if name and handler:
                self._handlers[name] = handler

    def to_mcp_tools(self) -> list[dict[str, Any]]:
        """Convert OpenIntent tool definitions to MCP tool format."""
        mcp_tools: list[dict[str, Any]] = []
        for t in self._tools:
            mcp_tool: dict[str, Any] = {
                "name": t.get("name", ""),
                "description": t.get("description", ""),
                "inputSchema": t.get(
                    "parameters",
                    t.get(
                        "inputSchema",
                        {
                            "type": "object",
                            "properties": {},
                        },
                    ),
                ),
            }
            mcp_tools.append(mcp_tool)
        return mcp_tools

    async def handle_call(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """Route an MCP tool call to the corresponding OpenIntent handler."""
        handler = self._handlers.get(tool_name)
        if handler is None:
            return {
                "error": f"Unknown tool: {tool_name}",
                "available_tools": list(self._handlers.keys()),
            }
        import asyncio

        if asyncio.iscoroutinefunction(handler):
            result = await handler(**arguments)
        else:
            result = handler(**arguments)
        if isinstance(result, dict):
            return result
        return {"result": result}


class MCPBridge:
    """High-level bridge managing multiple MCP server connections."""

    def __init__(self) -> None:
        self._providers: dict[str, MCPToolProvider] = {}

    def add_server(self, config: MCPServerConfig) -> None:
        """Register an MCP server configuration."""
        self._providers[config.name] = MCPToolProvider(config)

    async def connect_all(self) -> None:
        """Connect to all registered MCP servers."""
        for name, provider in self._providers.items():
            try:
                await provider.connect()
            except Exception as exc:
                logger.error("Failed to connect to MCP server '%s': %s", name, exc)
                raise

    async def disconnect_all(self) -> None:
        """Disconnect from all MCP servers."""
        for name, provider in self._providers.items():
            try:
                await provider.disconnect()
            except Exception as exc:
                logger.warning(
                    "Error disconnecting from MCP server '%s': %s", name, exc
                )

    async def list_all_tools(self) -> dict[str, list[dict[str, Any]]]:
        """List tools from all connected MCP servers, keyed by server name."""
        all_tools: dict[str, list[dict[str, Any]]] = {}
        for name, provider in self._providers.items():
            if provider.connected:
                all_tools[name] = await provider.list_tools()
        return all_tools

    async def invoke(
        self, server_name: str, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """Invoke a tool on a specific MCP server."""
        provider = self._providers.get(server_name)
        if provider is None:
            raise KeyError(
                f"Unknown MCP server: '{server_name}'. "
                f"Available: {list(self._providers.keys())}"
            )
        if not provider.connected:
            raise RuntimeError(
                f"MCP server '{server_name}' is not connected. "
                "Call connect_all() first."
            )
        return await provider.invoke(tool_name, arguments)

    @classmethod
    def from_yaml(cls, mcp_config: dict[str, Any]) -> MCPBridge:
        """Create a bridge from a parsed YAML ``mcp:`` block.

        Example YAML structure::

            mcp:
              servers:
                filesystem:
                  command: "npx"
                  args: ["-y", "@modelcontextprotocol/server-filesystem", "/data"]
                  allowed_tools: ["read_file", "write_file"]
                  security:
                    audit: true
        """
        bridge = cls()
        configs = parse_mcp_yaml(mcp_config)
        for cfg in configs:
            bridge.add_server(cfg)
        return bridge


def parse_mcp_yaml(yaml_config: dict[str, Any]) -> list[MCPServerConfig]:
    """Parse the ``mcp:`` block from a YAML workflow into server configs.

    Args:
        yaml_config: The parsed YAML dict (the value of the ``mcp`` key).

    Returns:
        List of MCPServerConfig objects ready for use with MCPBridge.
    """
    servers_block = yaml_config.get("servers", {})
    configs: list[MCPServerConfig] = []
    for name, server_def in servers_block.items():
        security_def = server_def.get("security")
        security: Optional[MCPSecurityConfig] = None
        if security_def is not None:
            security = MCPSecurityConfig(
                tls_required=security_def.get("tls_required", False),
                api_key_env=security_def.get("api_key_env"),
                credential_isolation=security_def.get("credential_isolation", True),
                audit=security_def.get("audit", True),
                max_retries=security_def.get("max_retries", 3),
            )
        config = MCPServerConfig(
            name=name,
            command=server_def.get("command", ""),
            args=server_def.get("args", []),
            env=server_def.get("env", {}),
            timeout=server_def.get("timeout", 30),
            allowed_tools=server_def.get("allowed_tools"),
            security=security,
        )
        configs.append(config)
    return configs


# ---------------------------------------------------------------------------
# MCPTool — First-class MCP tool integration for @Agent(tools=[...])
# ---------------------------------------------------------------------------

MCPRole = str


@dataclass
class MCPTool:
    """Declare an MCP server as a tool source for an ``@Agent`` or ``@Coordinator``.

    When placed in the ``tools=[...]`` list of an ``@Agent`` or ``@Coordinator``
    decorator, the SDK automatically:

    1. Connects to the MCP server at agent startup.
    2. Discovers available tools (filtered by ``allowed_tools`` and ``role``).
    3. Registers each discovered tool as a native ``ToolDef`` so the LLM can
       call it during the agentic loop.
    4. Routes tool invocations back through the MCP connection.
    5. Disconnects cleanly on agent shutdown.

    The ``role`` field maps to the RBAC system on the MCP server. When
    connecting to an ``@openintent/mcp-server``, the role determines which
    tools are visible: ``reader`` (4 read-only tools), ``operator``
    (10 read+write tools), or ``admin`` (all 16 tools).

    Examples — explicit configuration::

        from openintent.mcp import MCPTool

        @Agent("analyst", model="gpt-4o", tools=[
            MCPTool(
                server="npx",
                args=["-y", "@openintent/mcp-server"],
                role="operator",
                allowed_tools=["get_intent", "list_intents", "set_status"],
                env={"OPENINTENT_SERVER_URL": "http://localhost:8000"},
            ),
        ])
        class Analyst:
            ...

    Examples — ``mcp://`` URI shorthand::

        @Agent("watcher", model="gpt-4o", tools=[
            "mcp://npx/-y/@openintent/mcp-server?role=reader",
        ])
        class Watcher:
            ...

    Args:
        server: The executable command to start the MCP server (e.g. ``"npx"``).
        args: Command-line arguments for the server process.
        name: Human-readable name for the server (auto-derived if omitted).
        role: RBAC role for the connection (``"reader"``, ``"operator"``,
              ``"admin"``).  Defaults to ``"reader"`` (least privilege).
              Each agent should declare exactly the minimum role it needs.
              The role is set explicitly on the child process, isolating it
              from any ambient ``OPENINTENT_MCP_ROLE`` in the parent env.
        allowed_tools: Optional allowlist of tool names. Only these tools
                       will be registered even if the role permits more.
                       Use this to further restrict an agent's surface area.
                       ``None`` means all tools the role permits.
        env: Extra environment variables for the server process. Values
             starting with ``${...}`` are resolved from the host environment.
        timeout: Connection timeout in seconds.
        audit: Whether to log tool invocations.
    """

    server: str = ""
    args: list[str] = field(default_factory=list)
    name: str = ""
    role: MCPRole = "reader"
    allowed_tools: Optional[list[str]] = None
    env: dict[str, str] = field(default_factory=dict)
    timeout: int = 30
    audit: bool = True

    def __post_init__(self) -> None:
        if not self.name:
            parts = [self.server] + self.args
            pkg = next(
                (a for a in parts if a.startswith("@") or "/" in a),
                self.server,
            )
            self.name = pkg.rsplit("/", 1)[-1] if "/" in pkg else pkg

    def to_server_config(self) -> MCPServerConfig:
        """Convert to a low-level ``MCPServerConfig`` for ``MCPBridge``.

        The role is always set explicitly in the child process environment,
        overriding any ambient ``OPENINTENT_MCP_ROLE`` inherited from the
        parent shell.  This ensures each agent's MCP server runs at exactly
        the privilege level declared in the ``MCPTool``, regardless of what
        the host environment contains.
        """
        env = dict(self.env)
        env["OPENINTENT_MCP_ROLE"] = self.role
        return MCPServerConfig(
            name=self.name,
            command=self.server,
            args=list(self.args),
            env=env,
            timeout=self.timeout,
            allowed_tools=self.allowed_tools,
            security=MCPSecurityConfig(audit=self.audit),
        )


def parse_mcp_uri(uri: str) -> MCPTool:
    """Parse an ``mcp://`` URI into an :class:`MCPTool`.

    URI format::

        mcp://<command>/<arg1>/<arg2>/...?role=<role>&allow=<t1>,<t2>&env_KEY=val

    The *command* becomes ``MCPTool.server``.  Path segments after the
    command become ``MCPTool.args``.  Query parameters:

    - ``role``  — RBAC role (default ``"reader"``).
    - ``allow`` — Comma-separated tool allowlist.
    - ``name``  — Server name override.
    - ``env_*`` — Environment variables (prefix stripped).

    Examples::

        mcp://npx/-y/@openintent/mcp-server?role=operator
        mcp://npx/-y/@openintent/mcp-server?role=reader&allow=get_intent,list_intents
        mcp://python/-m/my_mcp_server?env_API_KEY=${MY_KEY}

    Returns:
        A fully populated :class:`MCPTool` instance.

    Raises:
        ValueError: If the URI scheme is not ``mcp``.
    """
    parsed = urlparse(uri)
    if parsed.scheme != "mcp":
        raise ValueError(
            f"Expected 'mcp://' URI scheme, got '{parsed.scheme}://' in '{uri}'"
        )

    command = parsed.netloc
    raw_path = parsed.path.lstrip("/")
    args = raw_path.split("/") if raw_path else []

    qs = parse_qs(parsed.query)

    role = qs.get("role", ["reader"])[0]
    allow_raw = qs.get("allow", [None])[0]
    allowed_tools = allow_raw.split(",") if allow_raw else None
    name = qs.get("name", [""])[0]

    env: dict[str, str] = {}
    for key, values in qs.items():
        if key.startswith("env_"):
            env_key = key[4:]
            env[env_key] = values[0]

    return MCPTool(
        server=command,
        args=args,
        name=name,
        role=role,
        allowed_tools=allowed_tools,
        env=env,
    )


def is_mcp_uri(value: Any) -> bool:
    """Check whether *value* is a string starting with ``mcp://``."""
    return isinstance(value, str) and value.startswith("mcp://")


async def resolve_mcp_tools(
    mcp_entries: list[Any],
) -> tuple[MCPBridge, list[Any]]:
    """Connect to MCP servers and produce ``ToolDef`` objects for each tool.

    This is the core wiring function called during agent startup. It:

    1. Collects all ``MCPTool`` and ``mcp://`` URI entries.
    2. Builds an :class:`MCPBridge` and connects to each server.
    3. Lists available tools (filtered by role + allowlist).
    4. Creates a ``ToolDef`` for each discovered tool, with a handler
       that invokes the tool through the MCP connection.

    Args:
        mcp_entries: The subset of the agent's ``tools`` list that are
                     ``MCPTool`` instances or ``mcp://`` URI strings.

    Returns:
        A tuple of ``(bridge, tool_defs)`` where *bridge* must be kept
        alive for the duration of the agent's run and *tool_defs* are
        ready to be appended to the agent's tool list.
    """
    from .llm import ToolDef

    bridge = MCPBridge()
    tool_defs: list[Any] = []

    configs: list[MCPTool] = []
    for entry in mcp_entries:
        if isinstance(entry, MCPTool):
            configs.append(entry)
        elif is_mcp_uri(entry):
            configs.append(parse_mcp_uri(entry))

    for mcp_tool in configs:
        bridge.add_server(mcp_tool.to_server_config())

    await bridge.connect_all()

    all_server_tools = await bridge.list_all_tools()

    for server_name, tools in all_server_tools.items():
        for t in tools:
            tool_name = t["name"]
            description = t.get("description", f"MCP tool: {tool_name}")
            input_schema = t.get(
                "inputSchema",
                {
                    "type": "object",
                    "properties": {
                        "input": {
                            "type": "string",
                            "description": "Input for the tool.",
                        },
                    },
                    "required": ["input"],
                },
            )

            captured_server = server_name
            captured_tool = tool_name

            async def _handler(
                _srv: str = captured_server,
                _tool: str = captured_tool,
                **kwargs: Any,
            ) -> dict[str, Any]:
                result = await bridge.invoke(_srv, _tool, kwargs)
                content = result.get("content", [])
                if content and len(content) == 1:
                    return {"result": content[0].get("text", str(content[0]))}
                if content:
                    return {"results": [c.get("text", str(c)) for c in content]}
                return result

            td = ToolDef(
                name=tool_name,
                description=f"[MCP:{server_name}] {description}",
                parameters=input_schema,
                handler=_handler,
            )
            tool_defs.append(td)

    logger.info(
        "MCP tools resolved: %d tools from %d servers",
        len(tool_defs),
        len(all_server_tools),
    )
    return bridge, tool_defs
