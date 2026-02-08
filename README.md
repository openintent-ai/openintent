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

## Features

- **Built-in Server** — `openintent-server` for instant protocol server with FastAPI
- **Sync & Async Clients** — `OpenIntentClient` and `AsyncOpenIntentClient`
- **Decorator-First Agents** — `@Agent`, `@Coordinator`, and `Worker` for minimal-boilerplate agents
- **17 RFC Coverage** — Complete protocol implementation:
  - RFC-0001 through RFC-0006: Intent lifecycle, graphs, leasing, governance, attachments, subscriptions
  - RFC-0007: Intent Portfolios
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

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT License — see [LICENSE](LICENSE) file for details.

## Links

- [OpenIntent Protocol](https://openintent.ai)
- [Protocol Specification](https://openintent.ai/docs)
- [RFC Documents](https://openintent.ai/rfc/0001)
- [GitHub](https://github.com/openintent-ai/openintent)
