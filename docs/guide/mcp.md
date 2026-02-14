---
title: Model Context Protocol (MCP) Integration
---

# Model Context Protocol (MCP) Integration

OpenIntent integrates with the [Model Context Protocol](https://modelcontextprotocol.io/) in two directions: the **MCP server** exposes OpenIntent tools and resources to MCP clients like Claude Desktop and Cursor, while the **MCP bridge** lets OpenIntent agents consume external MCP tool servers for filesystem access, database queries, and other capabilities.

MCP handles the last mile — connecting an LLM to tools and data sources over a standard protocol. OpenIntent handles what happens above that: multi-agent orchestration, intent lifecycle, leasing, governance, and audit. Together they give you a system where an LLM can both coordinate complex workflows and reach out to external tools without custom glue code.

---

## Architecture

### MCP Server: Exposing OpenIntent to LLMs

The `@openintent/mcp-server` package runs as a stdio-based MCP server. An MCP client connects to it and gains access to OpenIntent tools (create intents, patch state, send messages) and resources (read intent state, event logs, channel messages).

```
┌─────────────────────────────────────────┐
│  MCP Client (Claude, Cursor, etc.)      │
│  Connects via stdio transport           │
└──────────────┬──────────────────────────┘
               │ MCP Protocol (JSON-RPC)
┌──────────────▼──────────────────────────┐
│  OpenIntent MCP Server                  │
│  @openintent/mcp-server                 │
│                                         │
│  Security:     Tools:     Resources:    │
│  - Role RBAC   - Intents  - State      │
│  - Allowlist   - Leasing  - Events     │
│  - TLS         - Messages - Channels   │
│  - Audit       - Events   - Agents     │
└──────────────┬──────────────────────────┘
               │ REST API (HTTPS)
┌──────────────▼──────────────────────────┐
│  OpenIntent Server                      │
│  Protocol engine + storage              │
└─────────────────────────────────────────┘
```

The MCP server translates JSON-RPC tool calls into REST API requests against the OpenIntent server. Every operation goes through the security layer — role-based access control, tool allowlists, TLS enforcement, credential isolation, and audit logging.

### MCPTool: First-Class MCP Tools in @Agent

The `MCPTool` class makes MCP tools a first-class citizen in the SDK's tool system. When you declare an `MCPTool` in your `@Agent(tools=[...])` list, the SDK automatically connects to the MCP server at agent startup, discovers available tools (respecting RBAC role + allowlist), registers them as native `ToolDef` entries so the LLM can call them during the agentic loop, and disconnects cleanly on shutdown.

```
┌─────────────────────────────────────────┐
│  @Agent("analyst", model="gpt-4o",     │
│    tools=[MCPTool(...)])                │
│                                         │
│  1. Startup: connect to MCP server     │
│  2. Discover tools (role + allowlist)  │
│  3. Register as ToolDef (LLM-ready)    │
│  4. LLM calls → route via MCP          │
│  5. Shutdown: disconnect               │
└──────────────┬──────────────────────────┘
               │ MCP Protocol (stdio)
┌──────────────▼──────────────────────────┐
│  MCP Server                             │
│  (OpenIntent, filesystem, DB, etc.)     │
│                                         │
│  RBAC: role gate + allowlist gate      │
└─────────────────────────────────────────┘
```

**Explicit configuration:**

```python
from openintent import Agent, MCPTool, on_assignment

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
    @on_assignment
    async def work(self, intent):
        return await self.think(intent.description)
```

**URI shorthand:**

```python
@Agent("watcher", model="gpt-4o", tools=[
    "mcp://npx/-y/@openintent/mcp-server?role=reader",
])
class Watcher:
    @on_assignment
    async def work(self, intent):
        return await self.think("Summarize: " + intent.description)
```

**Mixed tools — local + MCP:**

```python
@Agent("researcher", model="gpt-4o", tools=[
    web_search,  # local ToolDef
    MCPTool(
        server="npx",
        args=["-y", "@openintent/mcp-server"],
        role="operator",
    ),
    MCPTool(
        server="npx",
        args=["-y", "@modelcontextprotocol/server-filesystem", "/data"],
        allowed_tools=["read_file", "list_directory"],
    ),
])
class Researcher:
    @on_assignment
    async def work(self, intent):
        return await self.think(intent.description)
```

!!! info "RBAC role determines tool visibility"
    The `role` field on `MCPTool` maps directly to the RBAC system. When connecting to `@openintent/mcp-server`, the server filters its tool listing based on the role: `reader` sees 4 read-only tools, `operator` sees 10 read+write tools, `admin` sees all 16 tools. The `allowed_tools` field further restricts within the role's permissions — both gates must pass.

!!! warning "Least-privilege by design"
    `MCPTool.role` defaults to `"reader"` — the most restrictive level. Each agent should declare exactly the minimum role it needs. In multi-agent topologies, each agent's MCP server runs as an isolated child process with its own explicit role, so one agent's privilege never leaks to another. Do **not** set `OPENINTENT_MCP_ROLE` as a global environment variable in multi-agent setups — declare the role per-agent on each `MCPTool` instead.

    Use `allowed_tools` to further narrow scope even within a role. For example, an agent with `role="operator"` that only needs to read and update state should also set `allowed_tools=["get_intent", "list_intents", "update_state"]`.

!!! warning "MCP SDK required"
    `MCPTool` requires the MCP SDK: `pip install mcp`. Without it, `MCPTool` entries in the tools list will raise `ImportError` at agent startup.

### MCP Bridge: Consuming External Tools (Low-Level)

For lower-level control, the Python SDK includes `MCPBridge`, which connects OpenIntent agents to external MCP tool servers. Define connections in the YAML `mcp:` block and agents can invoke tools from any MCP-compatible server. Most users should prefer `MCPTool` for `@Agent`/`@Coordinator` integration.

```
┌─────────────────────────────────────────┐
│  OpenIntent Workflow (YAML)             │
│  mcp:                                   │
│    servers:                              │
│      filesystem: ...                    │
│      database: ...                      │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│  MCPBridge (Python SDK)                 │
│  Consumes external MCP servers          │
│  as OpenIntent tool providers           │
└──────┬────────────────┬─────────────────┘
       │                │
┌──────▼─────┐  ┌──────▼──────┐
│ Filesystem │  │  Database   │
│ MCP Server │  │  MCP Server │
└────────────┘  └─────────────┘
```

---

## Quick Start

### 1. Install the MCP Server

```bash
npm install -g @openintent/mcp-server
```

### 2. Configure Claude Desktop

Add the server to your Claude Desktop configuration file:

=== "macOS"

    Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

=== "Windows"

    Edit `%APPDATA%\Claude\claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "openintent": {
      "command": "npx",
      "args": ["-y", "@openintent/mcp-server"],
      "env": {
        "OPENINTENT_SERVER_URL": "http://localhost:8000",
        "OPENINTENT_API_KEY": "your-api-key",
        "OPENINTENT_MCP_ROLE": "operator"
      }
    }
  }
}
```

Restart Claude Desktop. The OpenIntent tools appear in the tool picker.

!!! note "Default role is `reader`"
    If you omit `OPENINTENT_MCP_ROLE`, the server starts in **reader** mode and only exposes read-only tools. Set it to `operator` or `admin` based on what the MCP client needs to do. See [Role-Based Access Control](#role-based-access-control) for details.

### 3. Use the Tools

With the MCP server connected, Claude can interact with OpenIntent directly. Here's what a typical conversation looks like:

**You:** Create a research intent for analyzing Q1 sales data.

**Claude** calls `openintent_create_intent`:
```json
{
  "title": "Analyze Q1 Sales Data",
  "description": "Review and summarize Q1 sales performance across regions",
  "initial_state": { "phase": "planning", "regions": ["NA", "EU", "APAC"] }
}
```

**You:** Update the intent to mark research as in progress and assign the data team.

**Claude** calls `openintent_update_state`:
```json
{
  "intent_id": "intent_01abc",
  "version": 1,
  "state_patch": { "phase": "in_progress", "assigned_team": "data-analytics" }
}
```

**Claude** calls `openintent_assign_agent`:
```json
{
  "intent_id": "intent_01abc",
  "agent_id": "data-analytics",
  "role": "worker"
}
```

!!! warning "Role requirements"
    The conversation above requires **operator** role for `create_intent` and `update_state`, and **admin** role for `assign_agent`. If your role is too restrictive, the tool call returns an error explaining which tier is needed.

### Available Tools

| Tool | Tier | Description |
|------|------|-------------|
| `openintent_get_intent` | `read` | Retrieve an intent by ID |
| `openintent_list_intents` | `read` | List intents with optional status filter |
| `openintent_get_events` | `read` | Retrieve event history |
| `openintent_get_messages` | `read` | Retrieve messages from a channel |
| `openintent_create_intent` | `write` | Create a new intent |
| `openintent_update_state` | `write` | Patch intent state (optimistic concurrency) |
| `openintent_log_event` | `write` | Append an event to the audit log |
| `openintent_send_message` | `write` | Send a message on a channel |
| `openintent_ask` | `write` | Send a request and await a correlated response |
| `openintent_broadcast` | `write` | Broadcast to all channel members |
| `openintent_set_status` | `admin` | Change intent lifecycle status |
| `openintent_acquire_lease` | `admin` | Acquire an exclusive lease on a scope |
| `openintent_release_lease` | `admin` | Release a previously acquired lease |
| `openintent_assign_agent` | `admin` | Assign an agent to an intent |
| `openintent_unassign_agent` | `admin` | Remove an agent assignment |
| `openintent_create_channel` | `admin` | Create a messaging channel |

### Available Resources

| URI Template | Description |
|-------------|-------------|
| `openintent://intents` | List all intents (supports `?status=` filter) |
| `openintent://intents/{id}` | Full intent details |
| `openintent://intents/{id}/state` | Current state key-value data |
| `openintent://intents/{id}/events` | Immutable event log |
| `openintent://channels/{id}/messages` | Channel message history |

---

## Security Model

### Role-Based Access Control

Every tool belongs to a **permission tier** — `read`, `write`, or `admin`. Roles grant access to cumulative sets of tiers. The MCP server enforces the configured role before executing any tool call, and only advertises permitted tools to the MCP client.

#### Permission Tiers

| Tier | Purpose | Risk Level |
|------|---------|------------|
| **`read`** | Observe protocol state without side effects. Safe for dashboards, monitors, and reporting tools. | None |
| **`write`** | Progress work within an intent — create intents, patch state, log events, send messages. These operations are bounded by optimistic concurrency and append-only event semantics. | Low |
| **`admin`** | Lifecycle control and coordination primitives — change intent status, acquire/release leases, assign/unassign agents, create channels. These operations can disrupt workflow integrity if misused. | High |

#### Roles

| Role | Tiers Granted | Tool Count | Use Case |
|------|---------------|------------|----------|
| **`reader`** | `read` | 4 | Dashboards, monitoring, auditing. The MCP client can observe but never modify protocol state. |
| **`operator`** | `read` + `write` | 10 | Worker agents that create intents, update state, and communicate. Cannot change lifecycle status, manage leases, or restructure agent assignments. |
| **`admin`** | `read` + `write` + `admin` | 16 | Trusted orchestrators with full control. Required for lifecycle management, lease coordination, and structural operations. |

#### Tool Classification

**Read tier** — safe, no side effects:

| Tool | What it does |
|------|-------------|
| `openintent_get_intent` | Fetch a single intent by ID |
| `openintent_list_intents` | Query intents with status filters |
| `openintent_get_events` | Read the immutable event log |
| `openintent_get_messages` | Read channel message history |

**Write tier** — bounded mutations with protocol safety:

| Tool | What it does | Why it's safe |
|------|-------------|---------------|
| `openintent_create_intent` | Create a new intent | Creates new state, doesn't modify existing |
| `openintent_update_state` | Patch intent key-value state | Protected by optimistic concurrency (version check) |
| `openintent_log_event` | Append to audit log | Append-only, immutable once written |
| `openintent_send_message` | Send a channel message | Scoped to channel membership |
| `openintent_ask` | Request/reply on a channel | Scoped to channel membership |
| `openintent_broadcast` | Broadcast to channel | Scoped to channel membership |

**Admin tier** — structural and lifecycle operations:

| Tool | What it does | Why it requires admin |
|------|-------------|----------------------|
| `openintent_set_status` | Change intent lifecycle status | Controls whether an intent is active, blocked, completed, or abandoned. Incorrect transitions can strand workflows. |
| `openintent_acquire_lease` | Acquire exclusive scope lock | Holding a lease blocks other agents from working on that scope. Leaked leases cause deadlocks. |
| `openintent_release_lease` | Release a scope lock | Premature release can cause race conditions. |
| `openintent_assign_agent` | Add agent to intent | Changes who can work on an intent. |
| `openintent_unassign_agent` | Remove agent from intent | Removing an active agent disrupts in-progress work. |
| `openintent_create_channel` | Create messaging channel | Establishes communication topology between agents. |

#### Default Role

The default role is **`reader`**. This is intentionally restrictive — an unconfigured MCP server cannot modify any protocol state. You must explicitly opt in to `operator` or `admin` by setting the role in your configuration.

!!! danger "Do not use `admin` for general-purpose MCP clients"
    The `admin` role grants access to lifecycle and coordination primitives that can disrupt active workflows. Reserve it for trusted orchestrators that are specifically designed to manage intent lifecycles, agent assignments, and lease coordination. A general-purpose LLM chat session should almost never need `admin`.

#### How Role and Allowlist Interact

The MCP server enforces **two independent gates** on every tool call. Both must pass:

1. **Role gate** — does the configured role's tier set include this tool's tier?
2. **Allowlist gate** — is the tool name in `allowed_tools` (or is the allowlist `null`)?

```
Tool call arrives
    │
    ▼
┌─────────────────────┐     ┌─────────────────────┐
│  Role gate           │────▶│  Allowlist gate       │────▶ Execute
│  (tier check)        │     │  (name check)         │
│                      │     │                       │
│  Denied? → Error     │     │  Denied? → Error      │
│  with tier + role    │     │  with tool name       │
└─────────────────────┘     └─────────────────────┘
```

This means you can use `allowed_tools` to further restrict a role. For example, an `operator` with `allowed_tools` set to `["openintent_create_intent", "openintent_update_state"]` can only create and update — not log events or send messages, even though those are in the `write` tier.

Tools that fail either gate are **hidden from the tool listing**. The MCP client never sees tools it cannot use.

#### Setting the Role

=== "Environment Variable"

    ```bash
    export OPENINTENT_MCP_ROLE=operator
    ```

=== "JSON Config File"

    ```json
    {
      "security": {
        "role": "operator"
      }
    }
    ```

=== "Claude Desktop"

    ```json
    {
      "mcpServers": {
        "openintent": {
          "command": "npx",
          "args": ["-y", "@openintent/mcp-server"],
          "env": {
            "OPENINTENT_SERVER_URL": "https://openintent.example.com",
            "OPENINTENT_API_KEY": "your-api-key",
            "OPENINTENT_MCP_ROLE": "operator"
          }
        }
      }
    }
    ```

If the role is not set or is set to an unrecognized value, the server falls back to `reader` and emits a warning.

#### Startup Messages

The server logs its active role and tool count at startup:

```
[openintent-mcp] Server started – role="operator", tools=10/16, connected to http://localhost:8000
```

If the role is `admin`, a warning is emitted:

```
[openintent-mcp] WARNING: Role is set to "admin" which grants access to all tools including lifecycle and coordination primitives. Use this only for trusted orchestrators.
```

### Choosing a Role: Operational Guidance

| Scenario | Recommended Role | Rationale |
|----------|-----------------|-----------|
| Monitoring dashboard | `reader` | Only needs to observe intents, events, and messages. |
| Worker agent doing research or analysis | `operator` | Needs to create intents, update state, log events, and communicate. Does not need lifecycle control. |
| Human-in-the-loop orchestrator (Claude Desktop) | `operator` | Most natural-language coordination can be done with `operator`. Upgrade to `admin` only if the human needs to manage leases and agent assignments. |
| Automated coordinator or CI/CD pipeline | `admin` | Needs full control over intent lifecycle, agent assignments, and lease management. Should be a trusted system with its own API key. |
| Read-only audit tool | `reader` + `allowed_tools: [get_events]` | Maximum restriction — can only read the event log. |

### API Key Management

API keys are passed through environment variables, never stored in config files. The MCP server reads `OPENINTENT_API_KEY` from the environment and includes it in every request to the OpenIntent server as the `X-API-Key` header.

```json
{
  "env": {
    "OPENINTENT_API_KEY": "your-api-key"
  }
}
```

If the key is missing, the server emits a warning at startup:

```
[openintent-mcp] WARNING: OPENINTENT_API_KEY is not set – requests will fail authentication.
```

### TLS Enforcement

The `tls_required` flag enforces HTTPS for all connections. When enabled, any attempt to connect to a non-HTTPS URL throws an error immediately.

```json
{
  "security": {
    "tls_required": true
  }
}
```

The server also warns when TLS is disabled but the URL points to a non-localhost address — a strong signal that you should enable TLS.

### Tool Allowlists

Restrict which tools MCP clients can invoke by setting `allowed_tools` in the security config. When set, any call to a tool not in the list returns an error. The allowlist works **in addition to** the role gate — a tool must pass both checks.

```json
{
  "security": {
    "role": "operator",
    "allowed_tools": [
      "openintent_create_intent",
      "openintent_update_state",
      "openintent_get_intent",
      "openintent_list_intents"
    ]
  }
}
```

Set `allowed_tools` to `null` (the default) to allow all tools within the role's tier.

!!! tip "Role vs. allowlist"
    Use **role** as the primary access control mechanism — it provides sensible defaults organized around common use cases. Use **allowed_tools** for fine-grained restriction within a role when you need to limit a specific MCP client to an even narrower set of operations.

### Credential Isolation

The MCP server never exposes raw API keys or secrets to the MCP client. Credentials are resolved from environment variables at startup and stored in memory. The client only sees tool results, never the authentication headers or connection parameters.

### Audit Logging

Every MCP operation is logged as a structured audit entry with:

- **Timestamp** — ISO 8601
- **Operation** — HTTP method and path (e.g. `POST /api/v1/intents`)
- **Parameters** — sanitized (sensitive keys like `api_key`, `password`, `token` are replaced with `[REDACTED]`)
- **Result** — `success` or `error`
- **Duration** — milliseconds
- **Agent ID** — the configured agent identity

Audit entries are written to stderr:

```
[audit] {"timestamp":"2026-02-13T10:30:00.000Z","operation":"POST /api/v1/intents","params":{"status":201},"result":"success","duration_ms":45,"agent_id":"mcp-agent"}
```

Enable or disable with `security.audit_logging` (default: `true`).

### Network Boundaries

The MCP server communicates with the OpenIntent server over HTTP/HTTPS. By default, it connects to `http://localhost:8000`. For production deployments, set `OPENINTENT_SERVER_URL` to your server's address and enable `tls_required`.

The MCP server itself uses stdio transport — it does not bind to any network port. Communication with the MCP client happens entirely through stdin/stdout, so there is no network attack surface on the MCP server side.

---

## Configuration Reference

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENINTENT_SERVER_URL` | OpenIntent server base URL | `http://localhost:8000` |
| `OPENINTENT_API_KEY` | API key for authentication | (empty) |
| `OPENINTENT_AGENT_ID` | Agent identity for audit logs | `mcp-agent` |
| `OPENINTENT_MCP_ROLE` | Permission role: `reader`, `operator`, or `admin` | `reader` |
| `OPENINTENT_MCP_CONFIG` | Path to a JSON config file | (none) |

Environment variables take precedence over values in the config file.

### JSON Config File

Point `OPENINTENT_MCP_CONFIG` to a JSON file for full configuration:

```json
{
  "server": {
    "url": "http://localhost:8000",
    "api_key": "your-api-key",
    "agent_id": "mcp-agent"
  },
  "security": {
    "tls_required": false,
    "role": "operator",
    "allowed_tools": null,
    "max_timeout": 120,
    "audit_logging": true
  },
  "network": {
    "timeout": 30000,
    "retries": 3,
    "retry_delay": 1000
  }
}
```

| Section | Field | Type | Description |
|---------|-------|------|-------------|
| `server` | `url` | string | OpenIntent server base URL |
| `server` | `api_key` | string | API key for authentication |
| `server` | `agent_id` | string | Agent identity sent with every request |
| `security` | `tls_required` | boolean | Enforce HTTPS for all connections |
| `security` | `role` | string | Permission role: `reader`, `operator`, or `admin` (default: `reader`) |
| `security` | `allowed_tools` | string[] \| null | Tool allowlist, `null` allows all tools within the role's tier |
| `security` | `max_timeout` | number | Maximum request timeout in seconds |
| `security` | `audit_logging` | boolean | Write structured audit entries to stderr |
| `network` | `timeout` | number | Request timeout in milliseconds |
| `network` | `retries` | number | Number of retry attempts for server errors |
| `network` | `retry_delay` | number | Base delay between retries in milliseconds |

### YAML `mcp:` Block (Python SDK)

The Python SDK parses the `mcp:` block from workflow YAML files to configure MCP server connections:

```yaml
mcp:
  servers:
    filesystem:
      command: "npx"
      args: ["-y", "@modelcontextprotocol/server-filesystem", "/data"]
      timeout: 30
      allowed_tools: ["read_file", "list_directory"]
      env:
        DATA_DIR: "/data"
      security:
        tls_required: false
        api_key_env: null
        credential_isolation: true
        audit: true
        max_retries: 3
```

| Field | Type | Description |
|-------|------|-------------|
| `command` | string | Command to start the MCP server process |
| `args` | string[] | Arguments passed to the command |
| `timeout` | number | Connection timeout in seconds (default 30) |
| `allowed_tools` | string[] | Only expose these tools from the server |
| `env` | object | Environment variables passed to the server process |
| `security.tls_required` | boolean | Require TLS for the connection |
| `security.api_key_env` | string | Environment variable name holding the API key |
| `security.credential_isolation` | boolean | Isolate credentials from the MCP session |
| `security.audit` | boolean | Log tool invocations |
| `security.max_retries` | number | Retry failed invocations |

---

## Python MCP Bridge

The `MCPBridge` class in `openintent.mcp` manages connections to multiple external MCP servers and exposes their tools to OpenIntent agents.

### Creating a Connection

```python
from openintent.mcp import MCPServerConfig, MCPSecurityConfig, MCPBridge

config = MCPServerConfig(
    name="filesystem",
    command="npx",
    args=["-y", "@modelcontextprotocol/server-filesystem", "/data"],
    allowed_tools=["read_file", "list_directory"],
    security=MCPSecurityConfig(audit=True),
)

bridge = MCPBridge()
bridge.add_server(config)
```

### Connecting and Using Tools

```python
import asyncio

async def main():
    bridge = MCPBridge()
    bridge.add_server(config)

    await bridge.connect_all()

    tools = await bridge.list_all_tools()
    for server_name, server_tools in tools.items():
        for tool in server_tools:
            print(f"{server_name}/{tool['name']}: {tool['description']}")

    result = await bridge.invoke(
        "filesystem",
        "read_file",
        {"path": "/data/report.csv"},
    )
    print(result["content"])

    await bridge.disconnect_all()

asyncio.run(main())
```

`MCPToolProvider` also supports async context managers:

```python
from openintent.mcp import MCPToolProvider

async with MCPToolProvider(config) as provider:
    tools = await provider.list_tools()
    result = await provider.invoke("read_file", {"path": "/data/report.csv"})
```

### From YAML Configuration

Parse the `mcp:` block from a workflow YAML and create a bridge in one step:

```python
import yaml
from openintent.mcp import MCPBridge

with open("workflow.yaml") as f:
    workflow = yaml.safe_load(f)

bridge = MCPBridge.from_yaml(workflow["mcp"])
await bridge.connect_all()

tools = await bridge.list_all_tools()
result = await bridge.invoke("filesystem", "read_file", {"path": "/data/input.txt"})

await bridge.disconnect_all()
```

---

## Integration Patterns

### Pattern 1: Claude as Coordinator

Claude Desktop connects to the MCP server and uses OpenIntent tools to orchestrate a multi-agent workflow. Claude creates intents, assigns agents, monitors progress through events, and coordinates through channels — all via natural language.

```
Claude Desktop (role: admin)
  ├── openintent_create_intent("Analyze dataset")
  ├── openintent_assign_agent(intent, "researcher")
  ├── openintent_assign_agent(intent, "analyst")
  ├── openintent_create_channel(intent, "coordination")
  ├── ... monitor with openintent_get_events() ...
  └── openintent_set_status(intent, "completed")
```

This pattern works well when you want a human-in-the-loop coordinator. Claude handles the planning and delegation, OpenIntent agents do the work, and the protocol ensures consistency and audit trails.

!!! note "This pattern requires `admin` role"
    `assign_agent`, `create_channel`, and `set_status` are admin-tier tools. Set `OPENINTENT_MCP_ROLE=admin` for this use case.

### Pattern 2: Agent with External Tools

An OpenIntent agent uses the MCP bridge to access tools from external MCP servers. The agent's workflow declares which MCP servers to connect to and which tools the agent can use.

```yaml
mcp:
  servers:
    filesystem:
      command: "npx"
      args: ["-y", "@modelcontextprotocol/server-filesystem", "/data"]
      allowed_tools: ["read_file", "list_directory"]

agents:
  researcher:
    tools:
      - mcp:filesystem/read_file
      - mcp:filesystem/list_directory
```

```python
from openintent.agents import Agent, on_assignment

@Agent("researcher")
class ResearchAgent:
    @on_assignment
    async def handle(self, intent):
        result = await self.tools.invoke(
            "mcp:filesystem/read_file",
            path="/data/dataset.csv",
        )
        return {"data": result, "status": "gathered"}
```

### Pattern 3: Multi-Protocol Pipeline

Combine OpenIntent coordination with MCP tool access in a single workflow. Some agents use MCP tools for data gathering, others use OpenIntent's built-in coordination primitives for orchestration.

```yaml
openintent: "1.0"
info:
  name: "Research Pipeline"

mcp:
  servers:
    filesystem:
      command: "npx"
      args: ["-y", "@modelcontextprotocol/server-filesystem", "/data"]
      allowed_tools: ["read_file", "list_directory"]
      security:
        audit: true

channels:
  findings:
    members: [researcher, analyst]
    audit: true

workflow:
  gather:
    title: "Gather Data"
    assign: researcher
  analyze:
    title: "Analyze Findings"
    assign: analyst
    depends_on: [gather]

agents:
  researcher:
    tools:
      - mcp:filesystem/read_file
      - mcp:filesystem/list_directory
  analyst:
    tools:
      - mcp:filesystem/read_file
```

The researcher reads files through the MCP bridge, posts findings to the `findings` channel, and the analyst picks them up for processing. OpenIntent handles the dependency ordering, leasing, and event logging automatically.

---

## Next Steps

<div class="oi-features" style="margin-top: 1em;">
  <div class="oi-feature">
    <div class="oi-feature__title">MCP Examples</div>
    <p class="oi-feature__desc">Working code for Claude Desktop, Python bridge, and YAML workflows.</p>
    <a href="../../examples/mcp/" class="oi-feature__link">See examples</a>
  </div>
  <div class="oi-feature">
    <div class="oi-feature__title">Agent Abstractions</div>
    <p class="oi-feature__desc">Build agents with lifecycle hooks, memory, and tools.</p>
    <a href="../agents/" class="oi-feature__link">Build agents</a>
  </div>
  <div class="oi-feature">
    <div class="oi-feature__title">Workflows</div>
    <p class="oi-feature__desc">Declarative YAML workflows for multi-agent pipelines.</p>
    <a href="../workflows/" class="oi-feature__link">Define workflows</a>
  </div>
</div>
