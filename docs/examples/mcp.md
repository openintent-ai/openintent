# MCP Integration

Working examples for connecting MCP clients to OpenIntent and consuming external MCP tools from OpenIntent agents.

## Connecting Claude Desktop

Add the OpenIntent MCP server to your Claude Desktop configuration:

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

After restarting Claude Desktop, you can manage intents, events, and channels through natural language:

```python
from openintent import OpenIntentClient

client = OpenIntentClient(base_url="http://localhost:8000", api_key="dev-key")
intent = client.create_intent(
    title="Q1 Analysis",
    description="Analyze Q1 sales performance",
    initial_state={"phase": "planning"},
)
print(f"Created: {intent.id}")
```

Claude sees the same intent through MCP and can update its state:

```json
// Claude calls openintent_update_state
{
  "intent_id": "intent_01abc",
  "version": 1,
  "state_patch": {
    "phase": "in_progress",
    "assigned_to": "data-team"
  }
}
```

Read intent state as a resource:

```
openintent://intents/intent_01abc/state
→ { "phase": "in_progress", "assigned_to": "data-team" }
```

Browse the event log:

```
openintent://intents/intent_01abc/events
→ [{ "event_type": "state_patched", "actor": "mcp-agent", ... }]
```

---

## Role-Based Access Examples

### Read-Only Dashboard

A monitoring tool that can observe protocol state but never modify it:

```json
{
  "mcpServers": {
    "openintent-monitor": {
      "command": "npx",
      "args": ["-y", "@openintent/mcp-server"],
      "env": {
        "OPENINTENT_SERVER_URL": "https://openintent.example.com",
        "OPENINTENT_API_KEY": "monitor-api-key",
        "OPENINTENT_MCP_ROLE": "reader"
      }
    }
  }
}
```

Available tools: `get_intent`, `list_intents`, `get_events`, `get_messages` (4 tools).

### Worker Agent

An agent that creates intents, updates state, logs events, and sends messages — but cannot manage lifecycle, leases, or agent assignments:

```json
{
  "mcpServers": {
    "openintent-worker": {
      "command": "npx",
      "args": ["-y", "@openintent/mcp-server"],
      "env": {
        "OPENINTENT_SERVER_URL": "https://openintent.example.com",
        "OPENINTENT_API_KEY": "worker-api-key",
        "OPENINTENT_MCP_ROLE": "operator"
      }
    }
  }
}
```

Available tools: all `read` + `write` tier tools (10 tools).

### Trusted Orchestrator

A coordinator with full access to all protocol primitives:

```json
{
  "mcpServers": {
    "openintent-orchestrator": {
      "command": "npx",
      "args": ["-y", "@openintent/mcp-server"],
      "env": {
        "OPENINTENT_SERVER_URL": "https://openintent.example.com",
        "OPENINTENT_API_KEY": "orchestrator-api-key",
        "OPENINTENT_MCP_ROLE": "admin"
      }
    }
  }
}
```

Available tools: all 16 tools.

### Restricted Operator

An operator further limited to specific tools using the allowlist:

```json
{
  "server": {
    "url": "https://openintent.example.com",
    "api_key": "restricted-api-key",
    "agent_id": "data-writer"
  },
  "security": {
    "tls_required": true,
    "role": "operator",
    "allowed_tools": [
      "openintent_create_intent",
      "openintent_update_state",
      "openintent_get_intent",
      "openintent_list_intents"
    ],
    "audit_logging": true
  }
}
```

Available tools: only the 4 listed tools (even though `operator` grants 10).

---

## MCPTool in @Agent (First-Class Integration)

### LLM-Powered Agent with OpenIntent MCP Tools

An agent that uses `MCPTool` to automatically discover and call OpenIntent tools through MCP:

```python
from openintent import Agent, MCPTool, on_assignment

@Agent("analyst", model="gpt-4o", tools=[
    MCPTool(
        server="npx",
        args=["-y", "@openintent/mcp-server"],
        role="operator",
        env={"OPENINTENT_SERVER_URL": "http://localhost:8000"},
    ),
])
class Analyst:
    @on_assignment
    async def work(self, intent):
        return await self.think(intent.description)

Analyst.run()
```

At startup, the SDK connects to the MCP server, discovers all tools the `operator` role permits (10 tools), registers them as native `ToolDef` entries, and the LLM can call them during `self.think()`.

### Read-Only Watcher via mcp:// URI

```python
from openintent import Agent, on_assignment

@Agent("watcher", model="gpt-4o", tools=[
    "mcp://npx/-y/@openintent/mcp-server?role=reader",
])
class Watcher:
    @on_assignment
    async def work(self, intent):
        return await self.think("Summarize: " + intent.description)
```

### Mixed Tools — Local + Multiple MCP Servers

```python
from openintent import Agent, MCPTool, tool, on_assignment

@tool(description="Search the web.", parameters={
    "type": "object",
    "properties": {"query": {"type": "string"}},
    "required": ["query"],
})
async def web_search(query: str) -> dict:
    return {"results": [f"Result for {query}"]}

@Agent("researcher", model="gpt-4o", tools=[
    web_search,
    MCPTool(
        server="npx",
        args=["-y", "@openintent/mcp-server"],
        role="operator",
        allowed_tools=["get_intent", "list_intents", "set_status"],
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

### Coordinator with MCP-Backed Governance

```python
from openintent import Coordinator, MCPTool, on_assignment

@Coordinator(
    coordinator_id="ops-lead",
    agents=["analyst", "writer"],
    model="gpt-4o",
    tools=[
        MCPTool(
            server="npx",
            args=["-y", "@openintent/mcp-server"],
            role="admin",
            env={"OPENINTENT_SERVER_URL": "http://localhost:8000"},
        ),
    ],
)
class OpsLead:
    @on_assignment
    async def work(self, intent):
        return await self.think(
            f"Coordinate: {intent.description}"
        )
```

---

## Python Agent with MCP Tools (Low-Level Bridge)

An agent that reads data from a filesystem MCP server using the low-level `MCPBridge`:

```python
#!/usr/bin/env python3
"""
Agent that uses a filesystem MCP server to read input data.

Prerequisites:
    pip install openintent mcp
    npm install -g @modelcontextprotocol/server-filesystem

Usage:
    python mcp_agent.py
"""

import asyncio
from openintent.mcp import MCPServerConfig, MCPSecurityConfig, MCPBridge

async def main():
    config = MCPServerConfig(
        name="filesystem",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-filesystem", "/data"],
        allowed_tools=["read_file", "list_directory"],
        security=MCPSecurityConfig(audit=True),
    )

    bridge = MCPBridge()
    bridge.add_server(config)
    await bridge.connect_all()

    tools = await bridge.list_all_tools()
    print("Available tools:")
    for server, server_tools in tools.items():
        for tool in server_tools:
            print(f"  {server}/{tool['name']}")

    listing = await bridge.invoke(
        "filesystem", "list_directory", {"path": "/data"}
    )
    print(f"\nDirectory listing: {listing['content']}")

    result = await bridge.invoke(
        "filesystem", "read_file", {"path": "/data/input.txt"}
    )
    print(f"\nFile contents: {result['content']}")

    await bridge.disconnect_all()

asyncio.run(main())
```

Using `MCPToolProvider` as a context manager for a single server:

```python
from openintent.mcp import MCPToolProvider, MCPServerConfig

async def read_with_context_manager():
    config = MCPServerConfig(
        name="filesystem",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-filesystem", "/data"],
    )

    async with MCPToolProvider(config) as provider:
        tools = await provider.list_tools()
        result = await provider.invoke("read_file", {"path": "/data/input.txt"})
        return result
```

---

## YAML Workflow with MCP

A complete workflow that connects agents to external MCP servers:

```yaml
openintent: "1.0"

info:
  name: "MCP-Enhanced Research Pipeline"
  description: "Agents use MCP tools for file access and data retrieval"

mcp:
  servers:
    filesystem:
      command: "npx"
      args: ["-y", "@modelcontextprotocol/server-filesystem", "/data"]
      allowed_tools: ["read_file", "list_directory"]
      security:
        audit: true
    openintent-remote:
      command: "npx"
      args: ["-y", "@openintent/mcp-server"]
      env:
        OPENINTENT_SERVER_URL: "http://localhost:8000"
        OPENINTENT_API_KEY: "${OPENINTENT_API_KEY}"
        OPENINTENT_MCP_ROLE: "reader"
      security:
        tls_required: false
        credential_isolation: true
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
      - mcp:openintent-remote/openintent_get_intent
      - mcp:openintent-remote/openintent_get_events
```

Parse this workflow and create a bridge from the `mcp:` block:

```python
import yaml
from openintent.mcp import MCPBridge

with open("mcp_workflow.yaml") as f:
    workflow = yaml.safe_load(f)

bridge = MCPBridge.from_yaml(workflow["mcp"])
await bridge.connect_all()

tools = await bridge.list_all_tools()
for server, server_tools in tools.items():
    print(f"{server}: {[t['name'] for t in server_tools]}")

result = await bridge.invoke("filesystem", "read_file", {"path": "/data/report.csv"})

await bridge.disconnect_all()
```

---

## Secure Production Setup

A production configuration with TLS enforcement, role-based access control, tool allowlists, and audit logging.

### MCP Server Config (JSON)

```json
{
  "server": {
    "url": "https://openintent.example.com",
    "api_key": "prod-api-key",
    "agent_id": "prod-mcp-agent"
  },
  "security": {
    "tls_required": true,
    "role": "operator",
    "allowed_tools": [
      "openintent_get_intent",
      "openintent_list_intents",
      "openintent_get_events",
      "openintent_update_state",
      "openintent_log_event"
    ],
    "max_timeout": 60,
    "audit_logging": true
  },
  "network": {
    "timeout": 15000,
    "retries": 2,
    "retry_delay": 500
  }
}
```

### Claude Desktop Config (Production)

```json
{
  "mcpServers": {
    "openintent": {
      "command": "npx",
      "args": ["-y", "@openintent/mcp-server"],
      "env": {
        "OPENINTENT_SERVER_URL": "https://openintent.example.com",
        "OPENINTENT_API_KEY": "prod-api-key",
        "OPENINTENT_MCP_ROLE": "operator",
        "OPENINTENT_MCP_CONFIG": "/etc/openintent/mcp-config.json"
      }
    }
  }
}
```

### Python Bridge (Production)

```python
from openintent.mcp import MCPServerConfig, MCPSecurityConfig, MCPBridge

production_config = MCPServerConfig(
    name="openintent-prod",
    command="npx",
    args=["-y", "@openintent/mcp-server"],
    env={
        "OPENINTENT_SERVER_URL": "https://openintent.example.com",
        "OPENINTENT_API_KEY": "${OPENINTENT_API_KEY}",
        "OPENINTENT_MCP_ROLE": "operator",
    },
    timeout=15,
    allowed_tools=[
        "openintent_get_intent",
        "openintent_list_intents",
        "openintent_get_events",
    ],
    security=MCPSecurityConfig(
        tls_required=True,
        credential_isolation=True,
        audit=True,
        max_retries=2,
    ),
)

bridge = MCPBridge()
bridge.add_server(production_config)
```

The security layer validates configuration at startup and warns about potential issues:

- Missing API keys
- TLS disabled on non-localhost URLs
- Excessive timeout values (above 300s)
- Unknown role values (falls back to `reader`)
- `admin` role in use (flags for operator awareness)

All tool invocations are logged with sanitized parameters — sensitive fields like `api_key`, `password`, `secret`, and `token` are replaced with `[REDACTED]` in audit output.
