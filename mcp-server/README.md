# @openintentai/mcp-server

MCP (Model Context Protocol) server that exposes the full [OpenIntent Coordination Protocol](https://openintent.wintermute.wiki) as MCP tools and resources. Any MCP-compatible client — Claude Desktop, Cursor, Windsurf, or custom agents — can orchestrate OpenIntent agents via natural language.

## Quick Start

```bash
npx -y @openintentai/mcp-server
```

Or install globally:

```bash
npm install -g @openintentai/mcp-server
openintent-mcp
```

## Configuration

The server reads configuration from environment variables or a JSON config file.

### Environment Variables

| Variable | Description | Default |
|---|---|---|
| `OPENINTENT_API_URL` | OpenIntent server base URL | `http://localhost:8000` |
| `OPENINTENT_API_KEY` | API key for authentication | (required) |
| `OPENINTENT_MCP_ROLE` | Permission role: `reader`, `operator`, or `admin` | `reader` |

### JSON Config File

Place `openintent-mcp.config.json` in the working directory:

```json
{
  "api": {
    "url": "http://localhost:8000",
    "key": "dev-api-key"
  },
  "security": {
    "role": "operator",
    "allowed_tools": ["create_intent", "list_intents", "get_intent"]
  }
}
```

## Claude Desktop Integration

Add to your Claude Desktop MCP config (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "openintent": {
      "command": "npx",
      "args": ["-y", "@openintentai/mcp-server"],
      "env": {
        "OPENINTENT_API_URL": "http://localhost:8000",
        "OPENINTENT_API_KEY": "your-api-key",
        "OPENINTENT_MCP_ROLE": "operator"
      }
    }
  }
}
```

## RBAC Roles

The server enforces role-based access control with three tiers:

| Role | Tools | Description |
|---|---|---|
| `reader` | 25 | Read-only observation: list/get intents, events, agents, costs, retry policies, failures |
| `operator` | 43 | Bounded mutations: create intents, post events, manage leases, record failures |
| `admin` | 70 | Full lifecycle: governance, identity, vaults, triggers, plans, retry policies |

Tools not permitted by the assigned role are hidden from the MCP tool listing entirely.

The role gate works alongside the `allowed_tools` allowlist — both must pass for a tool to be available.

## Tool Categories

- **Intent Management** — Create, read, update, patch, complete, cancel intents
- **Event Logging** — Append events, query event history, stream via SSE
- **Agent Coordination** — Register agents, manage leases, arbitration
- **Task Decomposition** (RFC-0012) — Plans, tasks, dependencies
- **Governance** (RFC-0013) — Policies, approvals, escalation
- **Credential Vaults** (RFC-0014) — Secrets, tool grants, scoped access
- **Agent Memory** (RFC-0015) — Working, episodic, semantic memory tiers
- **Lifecycle** (RFC-0016) — Registration, heartbeats, drain
- **Triggers** (RFC-0017) — Cron, event, webhook scheduling
- **Identity** (RFC-0018) — Ed25519 keys, DIDs, challenge-response
- **Verifiable Logs** (RFC-0019) — Hash chains, Merkle proofs
- **Tracing** (RFC-0020) — Distributed trace propagation
- **Messaging** (RFC-0021) — Agent-to-agent channels
- **Retry Policies** (RFC-0010) — Set/get retry policies, record and query failures

## Resources

The server also exposes 5 MCP resources:

- `openintent://intents` — List all intents
- `openintent://intents/{id}` — Get intent details
- `openintent://intents/{id}/events` — Get intent events
- `openintent://intents/{id}/agents` — Get assigned agents
- `openintent://intents/{id}/graph` — Get intent graph

## Python SDK Integration

The Python SDK can also consume this MCP server as a tool provider:

```python
from openintent import Agent

agent = Agent(
    name="my-agent",
    model="gpt-4o",
    tools=["mcp://npx/-y/@openintentai/mcp-server?role=operator"],
)
```

## License

MIT
