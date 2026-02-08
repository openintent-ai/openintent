---
title: LLM Adapters
---

# LLM Adapters

LLM Adapters provide automatic observability for popular LLM providers. They log every LLM call with model, tokens, latency, and cost — plus optional streaming hooks for real-time monitoring.

## Supported Providers

| Provider | Adapter | Package |
|----------|---------|---------|
| OpenAI | `OpenAIAdapter` | `openintent[openai]` |
| Anthropic | `AnthropicAdapter` | `openintent[anthropic]` |
| Google Gemini | `GeminiAdapter` | `openintent[gemini]` |
| xAI Grok | `GrokAdapter` | `openintent[grok]` |
| DeepSeek | `DeepSeekAdapter` | `openintent[deepseek]` |
| Azure OpenAI | `AzureOpenAIAdapter` | `openintent[azure]` |
| OpenRouter | `OpenRouterAdapter` | `openintent[openrouter]` |

```bash
pip install openintent[openai]        # Single adapter
pip install openintent[openai,anthropic]  # Multiple
pip install openintent[all-adapters]   # All adapters
```

---

## Usage

=== "OpenAI"

    ```python
    from openai import OpenAI
    from openintent import OpenIntentClient
    from openintent.adapters import OpenAIAdapter

    openai_client = OpenAI()
    oi_client = OpenIntentClient(base_url="...", agent_id="my-agent")

    adapter = OpenAIAdapter(openai_client, oi_client, intent_id)

    response = adapter.chat_complete(
        model="gpt-4",
        messages=[{"role": "user", "content": "Hello"}]
    )
    ```

=== "Anthropic"

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

=== "Azure OpenAI"

    ```python
    from openai import AzureOpenAI
    from openintent.adapters import AzureOpenAIAdapter

    azure_client = AzureOpenAI(
        azure_endpoint="https://my-resource.openai.azure.com/",
        api_key="...",
        api_version="2024-02-01"
    )
    adapter = AzureOpenAIAdapter(azure_client, oi_client, intent_id)

    response = adapter.chat_complete(
        model="gpt-4",
        messages=[{"role": "user", "content": "Hello"}]
    )
    ```

=== "OpenRouter"

    ```python
    from openintent.adapters import OpenRouterAdapter

    adapter = OpenRouterAdapter(openrouter_client, oi_client, intent_id)

    response = adapter.chat_complete(
        model="anthropic/claude-3-sonnet",
        messages=[{"role": "user", "content": "Hello"}]
    )
    ```

=== "Gemini"

    ```python
    from openintent.adapters import GeminiAdapter

    adapter = GeminiAdapter(gemini_client, oi_client, intent_id)

    response = adapter.generate_content(
        model="gemini-pro",
        contents=[{"role": "user", "parts": [{"text": "Hello"}]}]
    )
    ```

=== "Grok / DeepSeek"

    Both follow the OpenAI-compatible interface:

    ```python
    from openintent.adapters import GrokAdapter, DeepSeekAdapter

    grok = GrokAdapter(grok_client, oi_client, intent_id)
    deepseek = DeepSeekAdapter(deepseek_client, oi_client, intent_id)

    response = grok.chat_complete(model="grok-1", messages=[...])
    response = deepseek.chat_complete(model="deepseek-chat", messages=[...])
    ```

---

## Streaming

All adapters support streaming responses:

```python
for chunk in adapter.chat_complete_stream(
    model="gpt-4",
    messages=[{"role": "user", "content": "Tell me a story"}]
):
    print(chunk.choices[0].delta.content, end="")
```

---

## Streaming Hooks

All adapters accept an `AdapterConfig` with streaming hooks for real-time monitoring:

```python
from openintent.adapters import OpenAIAdapter, AdapterConfig

config = AdapterConfig(
    on_stream_start=lambda stream_id, model, provider:
        print(f"Stream {stream_id} started: {model}"),
    on_token=lambda token, stream_id:
        print(token, end=""),
    on_stream_end=lambda stream_id, model, total_tokens:
        print(f"\nDone: {total_tokens} tokens"),
    on_stream_error=lambda error, stream_id:
        print(f"Error in {stream_id}: {error}"),
)

adapter = OpenAIAdapter(openai_client, oi_client, intent_id, config=config)
```

| Hook | Signature | When |
|------|-----------|------|
| `on_stream_start` | `(stream_id, model, provider)` | Stream begins |
| `on_token` | `(token, stream_id)` | Each content token received |
| `on_stream_end` | `(stream_id, model, total_tokens)` | Stream completes |
| `on_stream_error` | `(error, stream_id)` | Stream fails |

!!! info "Fail-safe hooks"
    All hooks use a fail-safe pattern — exceptions in hooks are caught and logged without breaking the main flow.

---

## What Gets Logged

Each LLM call creates events with full observability data:

=== "Request Started"

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

=== "Request Completed"

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

### Token & Cost Tracking

| Field | Description |
|-------|-------------|
| `prompt_tokens` | Input tokens sent to the model |
| `completion_tokens` | Output tokens generated |
| `total_tokens` | Sum of prompt + completion |
| `duration_ms` | Request latency in milliseconds |

```python
cost_per_token = 0.00000015  # $0.15 per 1M tokens
total_cost = event.payload["total_tokens"] * cost_per_token
```

---

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
        adapter = OpenAIAdapter(self.openai, self.client, intent.id)

        response = adapter.chat_complete(
            model="gpt-4",
            messages=[
                {"role": "user", "content": intent.description}
            ]
        )

        return {"response": response.choices[0].message.content}
```

## Next Steps

<div class="oi-features" style="margin-top: 1em;">
  <div class="oi-feature">
    <div class="oi-feature__title">Agent Abstractions</div>
    <p class="oi-feature__desc">Build agents with decorators, lifecycle hooks, and protocol features.</p>
    <a href="../agents/" class="oi-feature__link">Build agents</a>
  </div>
  <div class="oi-feature">
    <div class="oi-feature__title">Built-in Server</div>
    <p class="oi-feature__desc">Run your own OpenIntent server with one command.</p>
    <a href="../server/" class="oi-feature__link">Start a server</a>
  </div>
  <div class="oi-feature">
    <div class="oi-feature__title">API Reference</div>
    <p class="oi-feature__desc">Complete adapter API documentation.</p>
    <a href="../../api/adapters/" class="oi-feature__link">View API</a>
  </div>
</div>
