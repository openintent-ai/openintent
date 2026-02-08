# LLM Adapters & Observability

Seven adapters with built-in cost tracking, token counting, and streaming hooks.

## OpenAI Adapter

```python
from openai import OpenAI
from openintent import OpenIntentClient
from openintent.adapters import OpenAIAdapter

client = OpenIntentClient(base_url="http://localhost:8000", agent_id="llm-agent")
intent = client.create_intent(title="Summarize document")

# Wrap the OpenAI client
adapter = OpenAIAdapter(OpenAI(), client, intent.id)

response = adapter.chat_complete(
    model="gpt-4",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Summarize this text: ..."}
    ]
)

print(response.choices[0].message.content)
# Cost and token usage are automatically logged to the intent event log
```

## Anthropic Adapter

```python
from anthropic import Anthropic
from openintent.adapters import AnthropicAdapter

adapter = AnthropicAdapter(Anthropic(), client, intent.id)

response = adapter.chat_complete(
    model="claude-sonnet-4-20250514",
    messages=[{"role": "user", "content": "Explain quantum computing"}],
    max_tokens=1024
)
```

## Streaming with Hooks

All adapters support streaming with lifecycle hooks:

```python
from openintent.adapters import OpenAIAdapter, AdapterConfig

config = AdapterConfig(
    on_stream_start=lambda: print("Stream started"),
    on_token=lambda token: print(token, end="", flush=True),
    on_stream_end=lambda usage: print(f"\nTokens: {usage}"),
    on_stream_error=lambda e: print(f"Error: {e}")
)

adapter = OpenAIAdapter(OpenAI(), client, intent.id, config=config)

for chunk in adapter.chat_complete_stream(
    model="gpt-4",
    messages=[{"role": "user", "content": "Write a haiku"}]
):
    pass  # Hooks handle output
```

## Google Gemini

```python
import google.generativeai as genai
from openintent.adapters import GeminiAdapter

genai.configure(api_key="...")
model = genai.GenerativeModel("gemini-pro")

adapter = GeminiAdapter(model, client, intent.id)
response = adapter.chat_complete(
    messages=[{"role": "user", "content": "Explain machine learning"}]
)
```

## DeepSeek

```python
from openintent.adapters import DeepSeekAdapter

adapter = DeepSeekAdapter(
    api_key="...",
    client=client,
    intent_id=intent.id
)

response = adapter.chat_complete(
    model="deepseek-chat",
    messages=[{"role": "user", "content": "Write a Python function"}]
)
```

## OpenRouter (Multi-Model)

```python
from openintent.adapters import OpenRouterAdapter

adapter = OpenRouterAdapter(
    api_key="...",
    client=client,
    intent_id=intent.id
)

# Use any model available on OpenRouter
response = adapter.chat_complete(
    model="anthropic/claude-sonnet-4-20250514",
    messages=[{"role": "user", "content": "Compare SQL and NoSQL"}]
)
```

## Cost Tracking

Adapters automatically log cost data to the intent event log:

```python
# After an LLM call, events are logged automatically:
events = client.list_events(intent.id)

for event in events:
    if event.event_type == "llm_request_completed":
        print(f"Model: {event.payload['model']}")
        print(f"Input tokens: {event.payload['input_tokens']}")
        print(f"Output tokens: {event.payload['output_tokens']}")
        print(f"Cost: ${event.payload.get('cost_usd', 0):.4f}")

# Aggregate costs across a portfolio
portfolio_cost = client.get_portfolio_cost(portfolio.id)
print(f"Total cost: ${portfolio_cost.total_usd:.2f}")
```

## Agent with LLM Adapter

```python
from openintent.agents import Agent, on_assignment
from openintent.adapters import OpenAIAdapter
from openai import OpenAI

@Agent("smart-agent", auto_heartbeat=True)
class SmartAgent:

    def __init__(self):
        self.openai = OpenAI()

    @on_assignment
    async def handle(self, intent):
        adapter = OpenAIAdapter(self.openai, self.client, intent.id)

        response = adapter.chat_complete(
            model="gpt-4",
            messages=[{
                "role": "user",
                "content": f"Process this task: {intent.title}"
            }]
        )

        return {
            "result": response.choices[0].message.content,
            "status": "done"
        }
```
