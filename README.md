# OpenIntent SDK for Python

[![PyPI version](https://badge.fury.io/py/openintent.svg)](https://badge.fury.io/py/openintent)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://github.com/openintent-ai/openintent-sdk-python/actions/workflows/test.yml/badge.svg)](https://github.com/openintent-ai/openintent-sdk-python/actions/workflows/test.yml)

A complete Python SDK for the [OpenIntent Coordination Protocol](https://openintent.ai) - enabling seamless coordination between humans and AI agents.

## Features

- **Synchronous and Async Clients** - Full support for both sync (`OpenIntentClient`) and async (`AsyncOpenIntentClient`) usage patterns
- **Complete RFC Coverage** - Implements all 8 RFCs of the OpenIntent Protocol:
  - RFC-0001: Intent Lifecycle & State Management
  - RFC-0002: Append-Only Event Log
  - RFC-0003: Agent Leasing & Scope Ownership
  - RFC-0004: Arbitration & Governance
  - RFC-0005: Attachments
  - RFC-0006: Subscriptions
  - RFC-0009: Cost Tracking
  - RFC-0010: Retry Policies
- **Intent Portfolios** - Multi-intent coordination for complex workflows
- **Context Managers** - Pythonic lease management with automatic cleanup
- **Input Validation** - Client-side validation with helpful error messages
- **Type Hints** - Full type annotations for IDE support
- **Production Ready** - Proper error handling, retries, and timeout configuration

## Installation

```bash
pip install openintent
```

For OpenAI integration:

```bash
pip install openintent[openai]
```

## Quick Start

### Option 1: Try with Docker (Recommended)

The fastest way to try the SDK with a live server:

```bash
# Clone the reference server
git clone https://github.com/openintent-ai/openintent.git
cd openintent

# Start the server with Docker
docker compose up -d

# Install the SDK
pip install openintent

# Run the basic example
cd reference-implementation
python examples/basic_usage.py
```

### Option 2: Connect to an OpenIntent Server

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

### Events (RFC-0002)

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
    print(f"{event.event_type} by {event.agent_id} at {event.created_at}")
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
git clone https://github.com/openintent-ai/openintent-sdk-python.git
cd openintent-sdk-python

# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

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
- [GitHub](https://github.com/openintent-ai/openintent-sdk-python)
