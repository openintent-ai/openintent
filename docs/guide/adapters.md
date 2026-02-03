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

Each LLM call creates events with:

**Request Started:**
```json
{
  "event_type": "llm_request_started",
  "payload": {
    "model": "gpt-4",
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
    "request_id": "req-abc123",
    "input_tokens": 150,
    "output_tokens": 75,
    "latency_ms": 1234,
    "finish_reason": "stop"
  }
}
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
