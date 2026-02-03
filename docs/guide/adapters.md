# LLM Adapters

LLM Adapters provide automatic observability for popular LLM providers. They log every LLM call with model, tokens, latency, and cost.

## Supported Providers

| Provider | Adapter | Package |
|----------|---------|---------|
| OpenAI | `OpenAIAdapter` | `openintent[openai]` |
| Anthropic | `AnthropicAdapter` | `openintent[anthropic]` |
| Google Gemini | `GeminiAdapter` | `openintent[gemini]` |
| xAI Grok | `GrokAdapter` | `openintent[grok]` |
| DeepSeek | `DeepSeekAdapter` | `openintent[deepseek]` |

## Installation

```bash
# Install the adapter you need
pip install openintent[openai]
pip install openintent[anthropic]

# Or all adapters
pip install openintent[all-adapters]
```

## OpenAI Adapter

```python
from openai import OpenAI
from openintent import OpenIntentClient
from openintent.adapters import OpenAIAdapter

# Setup
openai_client = OpenAI()
oi_client = OpenIntentClient(base_url="...", agent_id="my-agent")

# Create adapter
adapter = OpenAIAdapter(openai_client, oi_client, intent_id)

# Make LLM calls - automatically logged!
response = adapter.chat_complete(
    model="gpt-4",
    messages=[{"role": "user", "content": "Hello"}]
)
```

### Streaming

```python
for chunk in adapter.chat_complete_stream(
    model="gpt-4",
    messages=[{"role": "user", "content": "Tell me a story"}]
):
    print(chunk.choices[0].delta.content, end="")
```

## Anthropic Adapter

```python
from anthropic import Anthropic
from openintent.adapters import AnthropicAdapter

anthropic_client = Anthropic()
adapter = AnthropicAdapter(anthropic_client, oi_client, intent_id)

response = adapter.messages_create(
    model="claude-3-sonnet-20240229",
    max_tokens=1000,
    messages=[{"role": "user", "content": "Hello"}]
)
```

## What Gets Logged

Each LLM call creates events with full observability data:

**Request Started:**
```json
{
  "event_type": "llm_request_started",
  "payload": {
    "model": "gpt-4",
    "provider": "openai",
    "request_id": "req-abc123"
  }
}
```

**Request Completed:**
```json
{
  "event_type": "llm_request_completed",
  "payload": {
    "model": "gpt-4",
    "provider": "openai",
    "request_id": "req-abc123",
    "prompt_tokens": 150,
    "completion_tokens": 75,
    "total_tokens": 225,
    "duration_ms": 1234,
    "finish_reason": "stop"
  }
}
```

## Cost Tracking (v0.6.0)

The adapters automatically log token counts for cost estimation:

| Field | Description |
|-------|-------------|
| `prompt_tokens` | Input tokens sent to the model |
| `completion_tokens` | Output tokens generated |
| `total_tokens` | Sum of prompt + completion |
| `duration_ms` | Request latency in milliseconds |

Use these to calculate costs based on your provider's pricing:

```python
# Example cost calculation for gpt-4o-mini
cost_per_token = 0.00000015  # $0.15 per 1M tokens
total_cost = event.payload["total_tokens"] * cost_per_token
```

## Distributed Tracing

When using adapters with the demo or CLI, you get a complete workflow trace:

```
◉ ORCHESTRATOR
│
├─► ⬤ research │ Intent: Research AI Agent Coordination
│   ├── ★ LLM → gpt-4o-mini (156 tokens, 892ms)
│   └── ✓ COMPLETE
│
└─► ⬤ summary │ depends_on: research
    ├── ★ LLM → gpt-4o-mini (89 tokens, 423ms)
    └── ✓ COMPLETE

┌────────────────────────────────────────────────────────────────┐
│  LLM OPERATIONS                                                │
├────────────────────────────────────────────────────────────────┤
│  ★ research   │ gpt-4o-mini │  156 tok │ 892ms │ $0.000023    │
│  ★ summary    │ gpt-4o-mini │   89 tok │ 423ms │ $0.000013    │
├────────────────────────────────────────────────────────────────┤
│  TOTAL: 2 calls │ 245 tokens │ $0.000036 estimated cost       │
└────────────────────────────────────────────────────────────────┘
```

## Using with @Agent

```python
from openintent.agents import Agent, on_assignment
from openintent.adapters import OpenAIAdapter
from openai import OpenAI

@Agent("smart-agent")
class SmartAgent:
    def __init__(self):
        self.openai = OpenAI()
    
    @on_assignment
    async def handle(self, intent):
        # Create adapter with current intent
        adapter = OpenAIAdapter(self.openai, self.client, intent.id)
        
        response = adapter.chat_complete(
            model="gpt-4",
            messages=[
                {"role": "user", "content": intent.description}
            ]
        )
        
        return {"response": response.choices[0].message.content}
```

## Tool Calls

Track function/tool calls within LLM responses:

```python
# Automatically logged when using function calling
response = adapter.chat_complete(
    model="gpt-4",
    messages=messages,
    tools=[{"type": "function", "function": {...}}]
)

# Tool calls are logged as separate events
```

## Next Steps

- [Built-in Server](server.md) - Run your own OpenIntent server
- [API Reference](../api/adapters.md) - Complete adapter API
