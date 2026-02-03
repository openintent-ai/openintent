# OpenIntent Python SDK

**Production-ready Python SDK for the OpenIntent Coordination Protocol.**

[![PyPI version](https://badge.fury.io/py/openintent.svg)](https://pypi.org/project/openintent/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## What is OpenIntent?

OpenIntent is a **neutral protocol for coordinating intent across humans and AI agents**. It replaces unstructured chat-based agent coordination with:

- **Structured intent objects** as shared source of truth
- **Append-only event logs** for accountability and debugging
- **Optimistic concurrency control** for safe parallel operations
- **Agent leasing** for collision prevention
- **Portfolio management** for grouped intents

## Quick Start

```bash
# Install the SDK
pip install openintent

# Or with built-in server
pip install openintent[server]
```

```python
from openintent import OpenIntentClient

# Connect to an OpenIntent server
client = OpenIntentClient(
    base_url="http://localhost:8000",
    agent_id="my-agent"
)

# Create an intent
intent = client.create_intent(
    title="Research quantum computing",
    description="Find recent papers on quantum error correction"
)

# Update state
client.patch_state(intent.id, {"status": "researching", "papers_found": 0})

# Log events
client.log_event(intent.id, EventType.STATE_PATCHED, {"progress": 0.5})
```

## Features

### Complete RFC Implementation

The SDK implements all 8 OpenIntent RFCs:

| RFC | Feature | Description |
|-----|---------|-------------|
| 0001 | Intent Object | Core data structure with versioning |
| 0002 | Intent Graphs | Parent-child hierarchies and dependencies |
| 0003 | Agent Leasing | Scope ownership for collision prevention |
| 0004 | Governance | Human oversight and arbitration |
| 0005 | Attachments | File handling and metadata |
| 0006 | Subscriptions | Real-time SSE event streaming |
| 0009 | Cost Tracking | Compute and API cost management |
| 0010 | Retry Policies | Transient failure handling |

### High-Level Agent Abstractions

Zero-boilerplate agent development with decorators:

```python
from openintent.agents import Agent, on_assignment

@Agent("research-agent")
class ResearchAgent:
    @on_assignment
    async def handle_assignment(self, intent):
        # Your agent logic here
        return {"status": "completed", "result": "..."}
```

### LLM Adapters

Built-in observability for popular LLM providers:

```python
from openintent.adapters import OpenAIAdapter

adapter = OpenAIAdapter(openai_client, oi_client, intent_id)
response = adapter.chat_complete(messages=[...])
# Automatically logs: model, tokens, latency, cost
```

### Built-in Server

Run your own OpenIntent server with one command:

```bash
openintent-server
# Server runs on http://localhost:8000
# OpenAPI docs at /docs
```

## Next Steps

- [Installation Guide](getting-started/installation.md) - Detailed installation options
- [Quick Start](getting-started/quickstart.md) - Get up and running in minutes
- [User Guide](guide/intents.md) - Learn the core concepts
- [API Reference](api/client.md) - Complete API documentation

## Links

- [PyPI Package](https://pypi.org/project/openintent/)
- [GitHub Repository](https://github.com/openintent-ai/openintent)
- [OpenIntent Protocol](https://openintent.ai/)
