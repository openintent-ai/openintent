# OpenIntent SDK & Server for Python

[![PyPI version](https://badge.fury.io/py/openintent.svg)](https://badge.fury.io/py/openintent)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://github.com/openintent-ai/openintent/actions/workflows/test.yml/badge.svg)](https://github.com/openintent-ai/openintent/actions/workflows/test.yml)

A complete Python SDK and server for the [OpenIntent Coordination Protocol](https://openintent.ai) - enabling seamless coordination between humans and AI agents.

## 30-Second Quickstart

```bash
# Install with server support
pip install openintent[server]

# Start the server (SQLite, zero config)
openintent-server

# In another terminal, create your first intent
curl -X POST http://localhost:8000/api/v1/intents \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-user-key" \
  -d '{"title": "Hello World", "created_by": "me"}'
```

That's it! You now have a running OpenIntent server with API docs at http://localhost:8000/docs

## Features

- **Built-in Server** - Run `openintent-server` for instant OpenIntent Protocol server
- **Synchronous and Async Clients** - Full support for both sync (`OpenIntentClient`) and async (`AsyncOpenIntentClient`) usage patterns
- **High-Level Agent Abstractions** - `@Agent` decorator, `Coordinator`, and `Worker` for minimal-boilerplate agents
- **Complete RFC Coverage** - Implements all 8 RFCs of the OpenIntent Protocol:
  - RFC-0001: Intent Lifecycle & State Management
  - RFC-0002: Intent Graphs (parent-child hierarchies and dependency DAGs)
  - RFC-0003: Agent Leasing & Scope Ownership
  - RFC-0004: Arbitration & Governance
  - RFC-0005: Attachments
  - RFC-0006: Subscriptions
  - RFC-0009: Cost Tracking
  - RFC-0010: Retry Policies
- **Intent Portfolios** - Multi-intent coordination for complex workflows
- **SSE Streaming** - Real-time event subscriptions
- **Context Managers** - Pythonic lease management with automatic cleanup
- **Input Validation** - Client-side validation with helpful error messages
- **Type Hints** - Full type annotations for IDE support
- **Production Ready** - Proper error handling, retries, and timeout configuration

## Installation

```bash
# Client only
pip install openintent

# Client + Server
pip install openintent[server]

# With LLM adapters (optional - install only what you need)
pip install openintent[openai]     # OpenAI GPT models
pip install openintent[anthropic]  # Anthropic Claude models
pip install openintent[gemini]     # Google Gemini models
pip install openintent[grok]       # xAI Grok models
pip install openintent[deepseek]   # DeepSeek models

# Multiple providers
pip install openintent[openai,anthropic]

# All adapters
pip install openintent[all-adapters]

# Everything (server + all adapters)
pip install openintent[all]
```

## Quick Start: Run Your Own Server

```bash
# Start with defaults (SQLite, port 8000)
openintent-server

# Or customize
openintent-server --port 9000 --database-url "postgresql://user:pass@localhost/db"

# Or use environment variables
DATABASE_URL=postgresql://... OPENINTENT_PORT=9000 openintent-server
```

**Programmatic usage:**

```python
from openintent.server import OpenIntentServer

server = OpenIntentServer(
    port=8000,
    database_url="sqlite:///./my-intents.db",
    api_keys={"my-secret-key", "agent-key"},
)
server.run()
```

## Quick Start: Client Usage

```python
from openintent import OpenIntentClient

# Initialize client
client = OpenIntentClient(
    base_url="https://api.openintent.ai",
    api_key="your-api-key",
    agent_id="my-agent"
)

# Create an intent
intent = client.create_intent(
    title="Research market trends",
    description="Analyze Q4 market data and identify patterns",
    constraints={"deadline": "2024-02-01"}
)

# Update state with optimistic concurrency
client.update_state(
    intent.id,
    intent.version,
    {"progress": 0.5, "current_phase": "analysis"}
)

# Acquire lease for exclusive scope access
with client.lease(intent.id, "analysis", duration_seconds=300) as lease:
    # Perform exclusive work within this scope
    # Other agents cannot acquire "analysis" scope until released
    pass

# Mark complete
client.set_status(intent.id, intent.version + 1, "completed")
```

## Async Usage

```python
import asyncio
from openintent import AsyncOpenIntentClient

async def main():
    client = AsyncOpenIntentClient(
        base_url="https://api.openintent.ai",
        api_key="your-api-key",
        agent_id="my-agent"
    )
    
    try:
        intent = await client.create_intent(
            title="Async research task",
            description="Process data asynchronously",
        )
        
        # Update state
        await client.update_state(
            intent.id,
            intent.version,
            {"status": "processing"}
        )
    finally:
        await client.close()

asyncio.run(main())
```

## Core Concepts

### Intents (RFC-0001)

Intents are the fundamental unit of work. They represent goals with structured state:

```python
# Create an intent with full configuration
intent = client.create_intent(
    title="Analyze customer feedback",
    description="Process and categorize all Q4 customer feedback",
    constraints={
        "max_cost": 50.0,
        "deadline": "2024-01-15",
        "quality_threshold": 0.95
    }
)

# Get an intent
intent = client.get_intent(intent.id)

# List all intents
intents = client.list_intents()
```

### Intent Graphs (RFC-0002)

Build hierarchical goal structures with parent-child relationships and dependency DAGs:

```python
# Create a parent intent for complex goals
parent = client.create_intent(
    title="Resolve Production Incident INC-2024-001",
    description="Critical payment processing failure"
)

# Create child intents that break down the work
diagnose = client.create_child_intent(
    parent_id=parent.id,
    title="Diagnose Root Cause",
    assign="agent:diagnostics"
)

communicate = client.create_child_intent(
    parent_id=parent.id,
    title="Notify Stakeholders", 
    assign="agent:comms"
)

# Create intent that depends on another (DAG dependency)
hotfix = client.create_child_intent(
    parent_id=parent.id,
    title="Develop Hotfix",
    assign="agent:dev",
    depends_on=[diagnose.id]  # Blocked until diagnose completes
)

# Multi-dependency gate - blocked until ALL dependencies complete
deploy = client.create_child_intent(
    parent_id=parent.id,
    title="Deploy Fix to Production",
    assign="agent:deploy",
    depends_on=[diagnose.id, hotfix.id]
)

# Navigate the graph
children = client.get_children(parent.id)
ancestors = client.get_ancestors(deploy.id)
dependencies = client.get_dependencies(deploy.id)
dependents = client.get_dependents(diagnose.id)
```

When dependencies are specified, intents automatically start in `blocked` status and transition to `pending` when all dependencies complete successfully.

### Events

Every modification creates an immutable event in the append-only log:

```python
# Log an event
client.log_event(
    intent.id,
    event_type="comment",
    payload={"message": "Starting analysis phase"}
)

# Get the event history for an intent
events = client.get_events(intent.id)

for event in events:
    print(f"{event.event_type} by {event.actor} at {event.created_at}")
```

### Agent Leasing (RFC-0003)

Leases prevent conflicts when multiple agents work on the same intent:

```python
# Acquire a lease for a specific scope
lease = client.acquire_lease(
    intent.id,
    scope="content.draft",
    duration_seconds=300  # 5 minutes
)

# Use context manager for automatic cleanup
with client.lease(intent.id, scope="content.draft") as lease:
    # Do work while holding the lease
    client.update_state(
        intent.id,
        intent.version,
        {"draft_content": "..."}
    )
    # Lease automatically released on exit

# Renew a lease to extend its duration
renewed = client.renew_lease(
    intent.id,
    lease_id=lease.id,
    duration_seconds=600
)

# Check for active leases
leases = client.get_leases(intent.id)
```

### Arbitration & Governance (RFC-0004)

Handle conflicts between agents through structured arbitration:

```python
# Request arbitration when agents disagree
arbitration = client.request_arbitration(
    intent.id,
    reason="Conflicting interpretations of requirements"
)

# Human or designated arbiter makes a decision
decision = client.record_decision(
    intent.id,
    decision="proceed_with_option_a",
    rationale="Option A better aligns with business objectives"
)
```

### Attachments (RFC-0005)

Associate files and artifacts with intents:

```python
import base64

# Add a file attachment
with open("analysis.pdf", "rb") as f:
    content = base64.b64encode(f.read()).decode()

attachment = client.add_attachment(
    intent.id,
    filename="quarterly_analysis.pdf",
    content_type="application/pdf",
    content_base64=content,
    description="Q4 financial analysis report"
)

# List attachments
attachments = client.get_attachments(intent.id)

# Delete an attachment
client.delete_attachment(intent.id, attachment.id)
```

### Subscriptions (RFC-0006)

Subscribe to real-time updates on intents:

```python
# Subscribe to intent updates
subscription = client.subscribe(
    intent.id,
    subscriber_id="service:dashboard",
    callback_url="https://dashboard.example.com/webhooks/intent",
    event_types=["state_patched", "status_changed"]
)

# Get active subscriptions
subscriptions = client.get_subscriptions(intent.id)

# Unsubscribe
client.unsubscribe(intent.id, subscription.id)
```

### Cost Tracking (RFC-0009)

Track compute and API costs associated with intents:

```python
# Record a cost entry
cost = client.record_cost(
    intent.id,
    cost_type="api_call",
    amount=0.05,
    unit="USD",
    provider="openai",
    metadata={"model": "gpt-4", "tokens": 1500}
)

# Get cost breakdown
costs = client.get_costs(intent.id)
total = sum(c.amount for c in costs)

# Get cost summary
summary = client.get_cost_summary(intent.id)
print(f"Total: ${summary['total']}")
print(f"By type: {summary['by_type']}")
```

### Retry Policies (RFC-0010)

Configure automatic retry behavior for failed operations:

```python
# Set a retry policy
policy = client.set_retry_policy(
    intent.id,
    max_attempts=5,
    base_delay_seconds=1.0,
    max_delay_seconds=60.0,
    backoff_multiplier=2.0,
    retryable_errors=["timeout", "rate_limit", "temporary_failure"]
)

# Get the current retry policy
policy = client.get_retry_policy(intent.id)

# Record a failure
client.record_failure(
    intent.id,
    error_type="rate_limit",
    error_message="API rate limit exceeded",
    attempt=1,
    will_retry=True
)

# Get failure history
failures = client.get_failures(intent.id)
```

### Tool Call Logging

Track LLM-initiated tool calls with structured payloads:

```python
import uuid

# Log when an LLM initiates a tool call
tool_call_id = str(uuid.uuid4())
client.log_tool_call_started(
    intent.id,
    tool_name="web_search",
    tool_id=tool_call_id,
    arguments={"query": "latest AI news"},
    provider="openai",
    model="gpt-4",
)

# Log successful completion with result
client.log_tool_call_completed(
    intent.id,
    tool_name="web_search",
    tool_id=tool_call_id,
    arguments={"query": "latest AI news"},
    result={"articles": ["..."]},
    duration_ms=1500,
    provider="openai",
    model="gpt-4",
)

# Or log failure
client.log_tool_call_failed(
    intent.id,
    tool_name="web_search",
    tool_id=tool_call_id,
    arguments={"query": "..."},
    error="Connection timeout",
    duration_ms=5000,
)
```

### LLM Request Logging

Track LLM API requests with full context:

```python
request_id = str(uuid.uuid4())

# Log when starting an LLM request
client.log_llm_request_started(
    intent.id,
    request_id=request_id,
    provider="openai",
    model="gpt-4",
    messages_count=5,
    tools_available=["web_search", "calculator"],
    stream=False,
    temperature=0.7,
)

# Log successful completion with token usage
client.log_llm_request_completed(
    intent.id,
    request_id=request_id,
    provider="openai",
    model="gpt-4",
    messages_count=5,
    response_content="Here is the analysis...",
    finish_reason="stop",
    prompt_tokens=500,
    completion_tokens=200,
    total_tokens=700,
    duration_ms=2500,
)
```

### Stream Coordination

Coordinate streaming LLM responses across agents:

```python
stream_id = str(uuid.uuid4())

# Signal stream start
client.start_stream(
    intent.id,
    stream_id=stream_id,
    provider="openai",
    model="gpt-4",
)

# Optionally log chunks (use sparingly for performance)
# Only log significant chunks, not every token
for i, chunk in enumerate(stream_response):
    if i % 10 == 0:  # Every 10th chunk
        client.log_stream_chunk(intent.id, stream_id, chunk_index=i)

# Signal successful completion
client.complete_stream(
    intent.id,
    stream_id=stream_id,
    provider="openai",
    model="gpt-4",
    chunks_received=100,
    tokens_streamed=1500,
)

# Or cancel the stream
client.cancel_stream(
    intent.id,
    stream_id=stream_id,
    provider="openai",
    model="gpt-4",
    reason="User interrupted",
    chunks_received=50,
    tokens_streamed=750,
)
```

## Intent Portfolios

Portfolios enable coordinating multiple related intents as a single unit:

```python
# Create a portfolio for a complex project
portfolio = client.create_portfolio(
    name="Paris Trip 2024",
    description="Complete vacation planning",
    governance_policy={
        "require_all_completed": True,
        "shared_constraints": {"budget": 5000},
    },
)

# Create intents for different aspects
flight_intent = client.create_intent(title="Book flights to Paris")
hotel_intent = client.create_intent(title="Book hotel in Paris")

# Add intents to portfolio with roles and priorities
client.add_intent_to_portfolio(
    portfolio.id,
    flight_intent.id,
    role="primary",
    priority=100,
)
client.add_intent_to_portfolio(
    portfolio.id,
    hotel_intent.id,
    role="member",
    priority=90,
)

# Get portfolio with aggregate status
portfolio = client.get_portfolio(portfolio.id)

# Update portfolio status when complete
client.update_portfolio_status(portfolio.id, "completed")
```

## Provider Adapters

The SDK includes pluggable adapters for popular LLM providers. These adapters wrap your existing client instances and automatically log OpenIntent events for all LLM interactions.

### OpenAI Adapter

```python
from openai import OpenAI
from openintent import OpenIntentClient
from openintent.adapters import OpenAIAdapter, AdapterConfig

# Initialize clients
openintent = OpenIntentClient(base_url="...", api_key="...")
openai_client = OpenAI()

# Create an intent for tracking
intent = openintent.create_intent(title="Research AI trends")

# Wrap the OpenAI client - uses same interface
adapter = OpenAIAdapter(openai_client, openintent, intent_id=intent.id)

# Regular completion - automatically logs LLM_REQUEST_* events
response = adapter.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "What are the latest AI trends?"}]
)

# Streaming - automatically logs STREAM_* events
stream = adapter.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Explain machine learning"}],
    stream=True
)
for chunk in stream:
    print(chunk.choices[0].delta.content or "", end="")

# Tool calls are automatically logged as TOOL_CALL_* events
response = adapter.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "What's the weather in NYC?"}],
    tools=[{
        "type": "function",
        "function": {"name": "get_weather", "parameters": {...}}
    }]
)
```

### Anthropic Adapter

```python
from anthropic import Anthropic
from openintent import OpenIntentClient
from openintent.adapters import AnthropicAdapter

# Initialize clients
openintent = OpenIntentClient(base_url="...", api_key="...")
anthropic_client = Anthropic()

# Create an intent
intent = openintent.create_intent(title="Draft blog post")

# Wrap the Anthropic client
adapter = AnthropicAdapter(anthropic_client, openintent, intent_id=intent.id)

# Regular message - automatically logs events
message = adapter.messages.create(
    model="claude-3-opus-20240229",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Draft a blog post about AI"}]
)

# Streaming with context manager
with adapter.messages.stream(
    model="claude-3-opus-20240229",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Explain quantum computing"}]
) as stream:
    for text in stream.text_stream:
        print(text, end="")
```

### Adapter Configuration

Customize logging behavior with `AdapterConfig`:

```python
from openintent.adapters import AdapterConfig

def error_handler(error: Exception, context: dict):
    print(f"Adapter error: {error} in {context['phase']}")

config = AdapterConfig(
    log_requests=True,          # Log LLM request events (default: True)
    log_tool_calls=True,        # Log tool call events (default: True)
    log_streams=True,           # Log stream events (default: True)
    log_stream_chunks=False,    # Log individual chunks (default: False)
    chunk_log_interval=10,      # Log every Nth chunk if enabled (default: 10)
    on_error=error_handler,     # Custom error callback (default: None)
)

adapter = OpenAIAdapter(openai_client, openintent, intent.id, config=config)
```

### Events Logged by Adapters

| Event Type | When Logged |
|------------|-------------|
| `LLM_REQUEST_STARTED` | When an LLM request begins |
| `LLM_REQUEST_COMPLETED` | When request completes successfully |
| `LLM_REQUEST_FAILED` | When request fails with an error |
| `TOOL_CALL_STARTED` | When the model initiates a tool call |
| `STREAM_STARTED` | When streaming begins |
| `STREAM_CHUNK` | Periodically during streaming (if enabled) |
| `STREAM_COMPLETED` | When streaming finishes |
| `STREAM_CANCELLED` | When streaming is interrupted |

## Error Handling

```python
from openintent import (
    OpenIntentError,
    ConflictError,
    NotFoundError,
    LeaseConflictError,
    ValidationError,
)

try:
    intent = client.get_intent("nonexistent-id")
except NotFoundError as e:
    print(f"Intent not found: {e}")
except ConflictError as e:
    print(f"Version conflict: {e}")
except LeaseConflictError as e:
    print(f"Lease conflict: {e}")
except ValidationError as e:
    print(f"Validation error: {e}")
except OpenIntentError as e:
    print(f"API error: {e}")
```

### Common Errors

| Exception | Status Code | Description |
|-----------|-------------|-------------|
| `AuthenticationError` | 401 | Invalid or missing API key |
| `NotFoundError` | 404 | Intent, lease, or resource not found |
| `ConflictError` | 409 | Version mismatch on update |
| `LeaseConflictError` | 409 | Scope already leased by another agent |
| `RateLimitError` | 429 | Too many requests |
| `ValidationError` | 400 | Invalid input parameters |

## Input Validation

The SDK includes client-side validation to catch errors early:

```python
from openintent.validation import (
    validate_intent_create,
    validate_lease_acquire,
    InputValidationError,
)

try:
    validate_intent_create(title="")  # Empty title
except InputValidationError as e:
    print(f"Invalid input: {e}")  # "title cannot be empty"
    print(f"Field: {e.field}")    # "title"
```

## API Reference

### OpenIntentClient / AsyncOpenIntentClient

| Method | RFC | Description |
|--------|-----|-------------|
| `create_intent()` | RFC-0001 | Create a new intent |
| `get_intent()` | RFC-0001 | Retrieve an intent by ID |
| `list_intents()` | RFC-0001 | List intents with filtering |
| `update_state()` | RFC-0001 | Update intent state (with version check) |
| `set_status()` | RFC-0001 | Change intent status |
| `log_event()` | RFC-0002 | Add event to log |
| `get_events()` | RFC-0002 | Retrieve event history |
| `acquire_lease()` | RFC-0003 | Acquire scope lease |
| `release_lease()` | RFC-0003 | Release scope lease |
| `renew_lease()` | RFC-0003 | Renew a lease to extend duration |
| `get_leases()` | RFC-0003 | List active leases |
| `lease()` | RFC-0003 | Context manager for lease lifecycle |
| `request_arbitration()` | RFC-0004 | Request human arbitration |
| `record_decision()` | RFC-0004 | Record governance decision |
| `add_attachment()` | RFC-0005 | Add file attachment to intent |
| `get_attachments()` | RFC-0005 | List intent attachments |
| `delete_attachment()` | RFC-0005 | Remove an attachment |
| `subscribe()` | RFC-0006 | Subscribe to intent updates |
| `get_subscriptions()` | RFC-0006 | List active subscriptions |
| `unsubscribe()` | RFC-0006 | Remove a subscription |
| `record_cost()` | RFC-0009 | Record a cost entry |
| `get_costs()` | RFC-0009 | Get cost history |
| `get_cost_summary()` | RFC-0009 | Get aggregated cost summary |
| `set_retry_policy()` | RFC-0010 | Configure retry behavior |
| `get_retry_policy()` | RFC-0010 | Get current retry policy |
| `record_failure()` | RFC-0010 | Record a failure attempt |
| `get_failures()` | RFC-0010 | Get failure history |
| `assign_agent()` | - | Assign agent to intent |
| `discover()` | - | Get protocol metadata |
| `create_portfolio()` | - | Create intent portfolio |
| `get_portfolio()` | - | Get portfolio with aggregate status |
| `add_intent_to_portfolio()` | - | Add intent to portfolio |

## Examples

See the `examples/` directory for production-ready patterns:

- **`basic_usage.py`** - Complete intent lifecycle from creation to completion
- **`openai_multi_agent.py`** - Two OpenAI-powered agents collaborating with leases
- **`streaming_adapter.py`** - Performance-optimized LLM streaming with protocol conformance
- **`auth_identity.py`** - Authentication and identity patterns (API keys, agent registry, RBAC)
- **`portfolio_multi_intent.py`** - Multi-intent portfolio coordination

## Development

```bash
# Clone the repository
git clone https://github.com/openintent-ai/openintent.git
cd openintent

# Install dev dependencies
pip install -e ".[dev,server]"

# Run tests
pytest

# Start the development server
openintent-server

# Format code
black openintent/

# Lint
ruff check openintent/

# Type check
mypy openintent/
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Links

- [OpenIntent Protocol](https://openintent.ai)
- [Protocol Specification](https://openintent.ai/docs)
- [RFC Documents](https://openintent.ai/rfc/0001)
- [GitHub](https://github.com/openintent-ai/openintent)
