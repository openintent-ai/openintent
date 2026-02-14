# OpenIntent SDK & Server for Python

[![PyPI version](https://badge.fury.io/py/openintent.svg)](https://badge.fury.io/py/openintent)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://github.com/openintent-ai/openintent/actions/workflows/test.yml/badge.svg)](https://github.com/openintent-ai/openintent/actions/workflows/test.yml)

A complete Python SDK and server for the [OpenIntent Coordination Protocol](https://openintent.ai) — enabling durable, interoperable, auditable coordination between humans and AI agents.

## 30-Second Quickstart

```bash
pip install openintent[server]
openintent-server

# In another terminal
curl -X POST http://localhost:8000/api/v1/intents \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-user-key" \
  -d '{"title": "Hello World", "created_by": "me"}'
```

Server runs at http://localhost:8000 with API docs at http://localhost:8000/docs

## Architecture

### Protocol Stack

```mermaid
graph TB
    subgraph Agents["Agent Abstractions"]
        A1["@Agent"] --- A2["@Coordinator"] --- A3["Worker"]
    end

    subgraph Intent["Intent Layer"]
        I1["Structured Intents · Versioned State · Event Logs · Concurrency Control"]
    end

    subgraph Coord["Coordination Layer"]
        C1["Leasing<br/>RFC-0003"] --- C2["Governance<br/>RFC-0003 · 0013"] --- C3["Access Control<br/>RFC-0011"] --- C4["Planning<br/>RFC-0012"]
    end

    subgraph Infra["Infrastructure Layer"]
        F1["Memory<br/>RFC-0015"] --- F2["Vaults & Tools<br/>RFC-0014"] --- F3["Lifecycle<br/>RFC-0016"] --- F4["Triggers<br/>RFC-0017"]
    end

    subgraph Transport["Transport & Observability"]
        T1["7 LLM Adapters"] --- T2["Tracing · Costs"] --- T3["REST · SSE · Webhooks"]
    end

    Agents --> Intent --> Coord --> Infra --> Transport

    style Agents fill:#ede9fe,color:#1e1b4b,stroke:#7c3aed,stroke-width:2px
    style Intent fill:#dbeafe,color:#1e3a5f,stroke:#3b82f6,stroke-width:2px
    style Coord fill:#cffafe,color:#164e63,stroke:#06b6d4,stroke-width:2px
    style Infra fill:#f3e8ff,color:#3b0764,stroke:#8b5cf6,stroke-width:2px
    style Transport fill:#e0e7ff,color:#1e1b4b,stroke:#6366f1,stroke-width:2px

    style A1 fill:#c4b5fd,color:#1e1b4b,stroke:#7c3aed
    style A2 fill:#c4b5fd,color:#1e1b4b,stroke:#7c3aed
    style A3 fill:#c4b5fd,color:#1e1b4b,stroke:#7c3aed
    style I1 fill:#93c5fd,color:#1e3a5f,stroke:#3b82f6
    style C1 fill:#a5f3fc,color:#164e63,stroke:#06b6d4
    style C2 fill:#a5f3fc,color:#164e63,stroke:#06b6d4
    style C3 fill:#a5f3fc,color:#164e63,stroke:#06b6d4
    style C4 fill:#a5f3fc,color:#164e63,stroke:#06b6d4
    style F1 fill:#d8b4fe,color:#3b0764,stroke:#8b5cf6
    style F2 fill:#d8b4fe,color:#3b0764,stroke:#8b5cf6
    style F3 fill:#d8b4fe,color:#3b0764,stroke:#8b5cf6
    style F4 fill:#d8b4fe,color:#3b0764,stroke:#8b5cf6
    style T1 fill:#a5b4fc,color:#1e1b4b,stroke:#6366f1
    style T2 fill:#a5b4fc,color:#1e1b4b,stroke:#6366f1
    style T3 fill:#a5b4fc,color:#1e1b4b,stroke:#6366f1
```

### Intent Lifecycle

Every intent follows a deterministic state machine with optimistic concurrency control:

```mermaid
stateDiagram-v2
    direction LR

    [*] --> Created: create_intent()
    Created --> Assigned: assign agent
    Assigned --> Leased: acquire_lease()
    Leased --> Executing: agent begins work

    Executing --> Executing: patch_state() + version bump
    Executing --> Conflict: concurrent write
    Conflict --> Executing: governance resolves

    Executing --> Completed: set_status("completed")
    Executing --> Failed: error / timeout
    Failed --> Assigned: retry policy re-assigns

    Completed --> [*]

    classDef active fill:#ede9fe,color:#1e1b4b,stroke:#7c3aed,stroke-width:2px
    classDef conflict fill:#fee2e2,color:#7f1d1d,stroke:#ef4444,stroke-width:2px
    classDef success fill:#d1fae5,color:#064e3b,stroke:#10b981,stroke-width:2px

    class Created,Assigned active
    class Leased,Executing active
    class Conflict conflict
    class Completed success
    class Failed conflict
```

### Agent Coordination Flow

How agents, coordinators, and the protocol server interact in a multi-agent pipeline:

```mermaid
sequenceDiagram
    participant C as Coordinator
    participant S as Protocol Server
    participant A1 as Agent A
    participant A2 as Agent B

    rect rgb(237, 233, 254)
        Note over C,S: Setup Phase
        C->>S: create_intent("Research Task")
        S-->>C: intent {id, version: 1}
        C->>S: delegate → Agent A
    end

    rect rgb(219, 234, 254)
        Note over S,A1: Execution Phase
        S-->>A1: @on_assignment fires
        A1->>S: acquire_lease("analysis")
        A1->>S: patch_state({findings: "..."})
        A1->>S: memory.store("research-123", data)
        A1->>S: set_status("completed")
    end

    rect rgb(243, 232, 255)
        Note over C,A2: Handoff Phase
        S-->>C: @on_all_complete fires
        C->>S: delegate → Agent B
        S-->>A2: @on_assignment fires
        A2->>S: memory.recall(tags=["research"])
        A2->>S: patch_state({summary: "..."})
        A2->>S: set_status("completed")
    end

    rect rgb(209, 250, 229)
        Note over C,S: Decision Record
        S-->>C: @on_all_complete fires
        C->>S: record_decision("pipeline_complete")
    end
```

### Decorator Lifecycle

How lifecycle decorators map to protocol events across `@Agent` and `@Coordinator`:

```mermaid
graph TB
    subgraph AgentDecorators["@Agent Lifecycle"]
        direction TB
        E1["Intent Created"]
        E2["@on_assignment"]
        E3["@on_state_change"]
        E4["@on_event"]
        E5["@on_task"]
        E6["@on_trigger"]
        E7["@on_access_requested"]
        E8["@on_complete"]
        E9["@on_drain"]

        E1 --> E2
        E2 --> E3
        E3 --> E4
        E4 --> E5
        E5 --> E8
        E6 -.-> E2
        E7 -.-> E3
        E9 -.-> E8
    end

    subgraph CoordDecorators["@Coordinator Lifecycle"]
        direction TB
        D1["Portfolio Created"]
        D2["Agents Delegated"]
        D3["@on_conflict"]
        D4["@on_escalation"]
        D5["@on_quorum"]
        D6["@on_all_complete"]

        D1 --> D2
        D2 --> D3
        D2 --> D4
        D2 --> D5
        D3 --> D6
        D4 --> D6
        D5 --> D6
    end

    subgraph LLM["LLM-Powered Mode  (model=)"]
        direction TB
        L1["self.think(prompt)"]
        L2["Protocol Tools"]
        L3["Local ToolDef Handlers"]
        L4["Remote Grants RFC-0014"]
        L5["self.think_stream(prompt)"]

        L1 --> L2
        L1 --> L3
        L1 --> L4
        L5 --> L2
        L5 --> L3
        L5 --> L4
    end

    AgentDecorators --- LLM
    CoordDecorators --- LLM

    style AgentDecorators fill:#ede9fe,color:#1e1b4b,stroke:#7c3aed,stroke-width:2px
    style CoordDecorators fill:#cffafe,color:#164e63,stroke:#06b6d4,stroke-width:2px
    style LLM fill:#f3e8ff,color:#3b0764,stroke:#8b5cf6,stroke-width:2px

    style E1 fill:#c4b5fd,color:#1e1b4b,stroke:#7c3aed
    style E2 fill:#c4b5fd,color:#1e1b4b,stroke:#7c3aed
    style E3 fill:#c4b5fd,color:#1e1b4b,stroke:#7c3aed
    style E4 fill:#c4b5fd,color:#1e1b4b,stroke:#7c3aed
    style E5 fill:#c4b5fd,color:#1e1b4b,stroke:#7c3aed
    style E6 fill:#c4b5fd,color:#1e1b4b,stroke:#7c3aed
    style E7 fill:#c4b5fd,color:#1e1b4b,stroke:#7c3aed
    style E8 fill:#c4b5fd,color:#1e1b4b,stroke:#7c3aed
    style E9 fill:#c4b5fd,color:#1e1b4b,stroke:#7c3aed

    style D1 fill:#a5f3fc,color:#164e63,stroke:#06b6d4
    style D2 fill:#a5f3fc,color:#164e63,stroke:#06b6d4
    style D3 fill:#a5f3fc,color:#164e63,stroke:#06b6d4
    style D4 fill:#a5f3fc,color:#164e63,stroke:#06b6d4
    style D5 fill:#a5f3fc,color:#164e63,stroke:#06b6d4
    style D6 fill:#a5f3fc,color:#164e63,stroke:#06b6d4

    style L1 fill:#d8b4fe,color:#3b0764,stroke:#8b5cf6
    style L2 fill:#d8b4fe,color:#3b0764,stroke:#8b5cf6
    style L3 fill:#d8b4fe,color:#3b0764,stroke:#8b5cf6
    style L4 fill:#d8b4fe,color:#3b0764,stroke:#8b5cf6
    style L5 fill:#d8b4fe,color:#3b0764,stroke:#8b5cf6
```

## Features

- **Built-in Server** — `openintent-server` for instant protocol server with FastAPI
- **Sync & Async Clients** — `OpenIntentClient` and `AsyncOpenIntentClient`
- **Decorator-First Agents** — `@Agent`, `@Coordinator`, and `Worker` for minimal-boilerplate agents
- **21 RFC Coverage** — Complete protocol implementation:
  - RFC-0001 through RFC-0006: Intent lifecycle, graphs, leasing, governance, attachments, subscriptions
  - RFC-0004: Intent Portfolios
  - RFC-0008: LLM Integration & Observability
  - RFC-0009: Cost Tracking
  - RFC-0010: Retry Policies
  - RFC-0011: Access-Aware Coordination (unified permissions, delegation, context injection)
  - RFC-0012: Task Decomposition & Planning
  - RFC-0013: Coordinator Governance & Meta-Coordination
  - RFC-0014: Credential Vaults & Tool Scoping
  - RFC-0015: Agent Memory & Persistent State
  - RFC-0016: Agent Lifecycle & Health
  - RFC-0017: Triggers & Reactive Scheduling
  - RFC-0018: Cryptographic Agent Identity
  - RFC-0019: Verifiable Event Logs
  - RFC-0020: Distributed Tracing
  - RFC-0021: Agent-to-Agent Messaging
- **MCP Integration** — Bidirectional Model Context Protocol support (16 MCP tools, 5 resources, RBAC with 3 permission tiers, first-class `MCPTool` for `@Agent`/`@Coordinator`)
- **7 LLM Adapters** — OpenAI, Anthropic, Gemini, Grok, DeepSeek, Azure OpenAI, OpenRouter
- **YAML Workflows** — Declarative multi-agent workflows
- **SSE Streaming** — Real-time event subscriptions
- **Type-Safe** — Full type annotations and Pydantic models

## Installation

```bash
# Client only
pip install openintent

# Client + Server
pip install openintent[server]

# With LLM adapters
pip install openintent[openai]
pip install openintent[anthropic]
pip install openintent[gemini]
pip install openintent[grok]
pip install openintent[deepseek]
pip install openintent[azure]
pip install openintent[openrouter]

# All adapters
pip install openintent[all-adapters]

# Everything (server + adapters + dev)
pip install openintent[all]
```

## Server

```bash
# Start with defaults (SQLite, port 8000)
openintent-server

# With PostgreSQL
openintent-server --port 9000 --database-url "postgresql://user:pass@localhost/db"
```

**Programmatic usage:**

```python
from openintent.server import OpenIntentServer, ServerConfig

config = ServerConfig(
    port=8000,
    database_url="postgresql://user:pass@localhost/openintent",
    api_keys={"my-secret-key", "agent-key"},
)

server = OpenIntentServer(config=config)
server.run()
```

## Agent Abstractions

Three levels of abstraction, all decorator-first:

### Worker (Simplest)

```python
from openintent import Worker

async def process(intent):
    return {"result": do_work(intent.title)}

worker = Worker("processor", process)
worker.run()
```

### @Agent (Recommended)

Zero-boilerplate agents with auto-subscription, state patching, and protocol-managed lifecycle:

```python
from openintent import Agent, on_assignment, on_complete, on_state_change

@Agent("research-agent",
    memory="episodic",
    tools=["web_search"],
    auto_heartbeat=True,
)
class ResearchAgent:

    @on_assignment
    async def handle_new(self, intent):
        past = await self.memory.recall(tags=["research"])
        findings = await do_research(intent.description, context=past)
        await self.memory.store(
            key=f"research-{intent.id}",
            value=findings,
            tags=["research", intent.title]
        )
        return {"findings": findings}

    @on_state_change(keys=["data"])
    async def on_data_ready(self, intent, old_state, new_state):
        return {"analysis": analyze(new_state["data"])}

    @on_complete
    async def done(self, intent):
        print(f"Intent {intent.id} completed!")
```

### @Coordinator (Multi-Agent)

Mirrors `@Agent` with added portfolio orchestration, delegation, and governance:

```python
from openintent import (
    Coordinator, on_all_complete,
    on_conflict, on_escalation, on_quorum,
)

@Coordinator("pipeline",
    agents=["researcher", "analyst", "writer"],
    strategy="sequential",
    guardrails=["budget < 1000", "max_retries: 3"],
)
class ResearchPipeline:

    @on_conflict
    async def resolve(self, intent, conflict):
        await self.record_decision(
            decision_type="conflict_resolution",
            summary=f"Resolved on {intent.id}",
            rationale="Latest write wins"
        )

    @on_escalation
    async def escalate(self, intent, source_agent):
        await self.delegate(intent.title, agents=["senior-agent"])

    @on_quorum(threshold=0.6)
    async def consensus(self, intent, votes):
        await self.record_decision(
            decision_type="quorum",
            summary="Consensus reached",
            rationale=f"{len(votes)} votes in favor"
        )

    @on_all_complete
    async def finalize(self, portfolio):
        return self._merge_results(portfolio)
```

### Lifecycle Decorators

| Decorator | Trigger |
|-----------|---------|
| `@on_assignment` | Agent assigned to intent |
| `@on_complete` | Intent completed |
| `@on_state_change(keys)` | State keys changed |
| `@on_event(event_type)` | Specific event type |
| `@on_task(status)` | Task lifecycle event (RFC-0012) |
| `@on_trigger(name)` | Trigger fires (RFC-0017) |
| `@on_drain` | Graceful shutdown signal (RFC-0016) |
| `@on_access_requested` | Access request received (RFC-0011) |
| `@on_all_complete` | All portfolio intents complete |
| `@on_conflict` | Version conflict (coordinator) |
| `@on_escalation` | Agent escalation (coordinator) |
| `@on_quorum(threshold)` | Voting threshold met (coordinator) |

### First-Class Protocol Objects

Declarative configuration classes for protocol features (import from `openintent.agents`):

```python
from openintent.agents import Plan, Vault, Memory, Trigger

@Plan(strategy="topological", checkpoints=True)
class DeploymentPlan:
    build = {"assign": "builder", "timeout": 300}
    test = {"assign": "tester", "depends_on": ["build"]}
    deploy = {"assign": "deployer", "depends_on": ["test"]}

@Vault(name="production-keys", rotation_policy="90d")
class ProdVault:
    openai = {"scopes": ["chat.completions"], "rate_limit": 100}
    database = {"scopes": ["read", "write"]}

@Memory(tier="episodic", capacity=1000, eviction="lru")
class AgentMemoryConfig:
    namespace = "research"
    auto_archive = True

@Trigger(type="schedule", cron="0 18 * * *")
class DailySummary:
    intent_template = {"title": "Daily Summary for {{ date }}"}
    assign = "summary-bot"
```

## Client Usage

```python
from openintent import OpenIntentClient

client = OpenIntentClient(
    base_url="https://api.openintent.ai",
    api_key="your-api-key",
    agent_id="my-agent"
)

intent = client.create_intent(
    title="Research market trends",
    description="Analyze Q4 market data",
    constraints={"deadline": "2024-02-01"}
)

client.update_state(
    intent.id, intent.version,
    {"progress": 0.5, "phase": "analysis"}
)

with client.lease(intent.id, "analysis", duration_seconds=300) as lease:
    pass  # Exclusive scope access

client.set_status(intent.id, intent.version + 1, "completed")
```

## MCP Integration

OpenIntent supports the [Model Context Protocol](https://modelcontextprotocol.io/) in two directions: expose OpenIntent to MCP clients (Claude Desktop, Cursor) and consume external MCP tool servers from OpenIntent agents.

### Quick Setup

```bash
pip install openintent[server] mcp
npm install -g @openintent/mcp-server
```

Or use the Makefile:

```bash
make setup-mcp    # Install Python + Node MCP dependencies
make server       # Start the OpenIntent server
```

### Direction 1: Expose OpenIntent to Claude Desktop

> **Prerequisite:** The OpenIntent server must be running before Claude connects. Start it with `make server` or `openintent-server`.

Add the MCP server to your Claude Desktop config:

- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux:** `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "openintent": {
      "command": "npx",
      "args": ["-y", "@openintent/mcp-server"],
      "env": {
        "OPENINTENT_SERVER_URL": "http://localhost:8000",
        "OPENINTENT_API_KEY": "dev-user-key",
        "OPENINTENT_MCP_ROLE": "operator"
      }
    }
  }
}
```

Restart Claude Desktop. It can now create intents, patch state, log events, and send agent messages — all through natural language.

**Least-privilege principle:** Always use the most restrictive role that covers an agent's needs. If `OPENINTENT_MCP_ROLE` is omitted, the server defaults to `reader` (safest). Each agent should declare its own role explicitly — never rely on a global environment variable for multi-agent setups.

| Role | Tools | Use Case |
|------|-------|----------|
| `reader` | 4 read-only | Dashboards, monitoring (default) |
| `operator` | 10 read+write | Standard agent work |
| `admin` | 16 (all) | Lifecycle, leasing, coordination (use sparingly) |

### Direction 2: Use MCP Tools in @Agent (MCPTool)

Declare MCP servers directly in your agent's tool list. The SDK handles the full lifecycle — connect, discover tools, register them for the LLM, route invocations, disconnect on shutdown.

Each `MCPTool` sets the role explicitly on its child process, isolating it from any ambient environment variables. This means multiple agents can each run at different privilege levels simultaneously — a reader-only watcher alongside an operator-level worker — without interfering with each other.

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
```

URI shorthand for the same thing:

```python
@Agent("analyst", model="gpt-4o", tools=[
    "mcp://npx/-y/@openintent/mcp-server?role=operator&env_OPENINTENT_SERVER_URL=http://localhost:8000",
])
```

Mix local tools, multiple MCP servers, and plain grant strings freely:

```python
@Agent("researcher", model="gpt-4o", tools=[
    web_search,                          # local ToolDef
    MCPTool(server="npx",               # OpenIntent MCP
        args=["-y", "@openintent/mcp-server"],
        role="operator"),
    MCPTool(server="npx",               # filesystem MCP
        args=["-y", "@modelcontextprotocol/server-filesystem", "/data"],
        allowed_tools=["read_file", "list_directory"]),
    "search_results",                    # plain RFC-0014 grant
])
```

### Direction 3: Low-Level Bridge (YAML Workflows)

For programmatic control without `@Agent`, use `MCPBridge` directly:

```python
from openintent.mcp import MCPBridge

bridge = MCPBridge()
await bridge.connect("fs", "npx", ["-y", "@modelcontextprotocol/server-filesystem", "/data"])
tools = await bridge.list_tools("fs")
result = await bridge.invoke("fs", "read_file", path="/data/report.csv")
await bridge.disconnect("fs")
```

Or declare servers in the YAML `mcp:` block for workflow-level configuration.

### Full Topology Example

Run the complete stack — server + MCP server + agent with MCPTool:

```bash
make full-stack   # Terminal 1: Start OpenIntent server

# Terminal 2: Run an agent that auto-connects to the MCP server
python examples/mcp_agent.py
```

See [docs/guide/mcp.md](docs/guide/mcp.md) for the full guide and [docs/examples/mcp.md](docs/examples/mcp.md) for more examples.

## LLM Adapters

Wrap your LLM client — same interface, automatic logging:

```python
from openai import OpenAI
from openintent import OpenIntentClient
from openintent.adapters import OpenAIAdapter

client = OpenIntentClient(base_url="...", api_key="...")
openai_client = OpenAI()
intent = client.create_intent(title="Research AI trends")

adapter = OpenAIAdapter(openai_client, client, intent_id=intent.id)

response = adapter.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Latest AI trends?"}]
)
```

| Provider | Adapter | Install |
|----------|---------|---------|
| OpenAI | `OpenAIAdapter` | `openintent[openai]` |
| Anthropic | `AnthropicAdapter` | `openintent[anthropic]` |
| Google Gemini | `GeminiAdapter` | `openintent[gemini]` |
| xAI Grok | `GrokAdapter` | `openintent[grok]` |
| DeepSeek | `DeepSeekAdapter` | `openintent[deepseek]` |
| Azure OpenAI | `AzureOpenAIAdapter` | `openintent[azure]` |
| OpenRouter | `OpenRouterAdapter` | `openintent[openrouter]` |

## Error Handling

```python
from openintent import (
    OpenIntentError, ConflictError,
    NotFoundError, LeaseConflictError, ValidationError,
)

try:
    intent = client.get_intent("nonexistent")
except NotFoundError:
    print("Not found")
except ConflictError:
    print("Version conflict")
except LeaseConflictError:
    print("Lease conflict")
```

## API Reference

### Client Methods

| Method | RFC | Description |
|--------|-----|-------------|
| `create_intent()` | 0001 | Create a new intent |
| `get_intent()` | 0001 | Retrieve an intent by ID |
| `list_intents()` | 0001 | List intents with filtering |
| `update_state()` | 0001 | Update intent state (with version check) |
| `set_status()` | 0001 | Change intent status |
| `log_event()` | 0001 | Add event to log |
| `get_events()` | 0001 | Retrieve event history |
| `create_child_intent()` | 0002 | Create child intent in graph |
| `get_children()` | 0002 | Get child intents |
| `acquire_lease()` | 0003 | Acquire scope lease |
| `release_lease()` | 0003 | Release scope lease |
| `renew_lease()` | 0003 | Renew a lease |
| `lease()` | 0003 | Context manager for lease lifecycle |
| `request_arbitration()` | 0004 | Request human arbitration |
| `record_decision()` | 0004 | Record governance decision |
| `add_attachment()` | 0005 | Add file attachment |
| `subscribe()` | 0006 | Subscribe to intent updates |
| `create_portfolio()` | 0007 | Create intent portfolio |
| `record_cost()` | 0009 | Record a cost entry |
| `set_retry_policy()` | 0010 | Configure retry behavior |
| `tasks.create()` | 0012 | Create a task in a plan |
| `coordinator.*` | 0013 | Coordinator governance |
| `tools.create_vault()` | 0014 | Create credential vault |
| `tools.grant()` | 0014 | Grant scoped tool access |
| `memory.store()` | 0015 | Store memory entry |
| `memory.recall()` | 0015 | Recall memory entries |
| `agents.register()` | 0016 | Register agent |
| `agents.heartbeat()` | 0016 | Send heartbeat |
| `agents.drain()` | 0016 | Graceful shutdown |
| `triggers.create()` | 0017 | Create trigger |
| `triggers.fire()` | 0017 | Manually fire trigger |

## Development

```bash
git clone https://github.com/openintent-ai/openintent.git
cd openintent

pip install -e ".[dev,server]"

pytest                  # Run tests
ruff check openintent/  # Lint
black openintent/       # Format
mypy openintent/        # Type check
openintent-server       # Start dev server
```

### Makefile

A `Makefile` is provided to aggregate common operations:

```bash
make install          # Install SDK with server + all adapters
make install-all      # Install everything including MCP dependencies
make server           # Start the OpenIntent server on port 8000
make test             # Run the full test suite
make lint             # Run linter + formatter + type checker
make setup-mcp        # Install MCP dependencies (Python mcp + Node @openintent/mcp-server)
make mcp-server       # Start the MCP server (connects to local OpenIntent server)
make full-stack       # Start OpenIntent server + MCP server together
make check            # Verify installation and connectivity
make clean            # Remove build artifacts and caches
make help             # Show all available targets
```

Run `make help` to see the full list with descriptions.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT License — see [LICENSE](LICENSE) file for details.

## Links

- [Documentation](https://openintent-ai.github.io/openintent/)
- [OpenIntent Protocol](https://openintent.ai)
- [RFC Documents](https://openintent.ai/rfc/0001)
- [GitHub](https://github.com/openintent-ai/openintent)
