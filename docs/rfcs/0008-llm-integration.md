# RFC-0008: LLM Integration & Observability v1.0

**Status:** Proposed  
**Created:** 2026-02-01  
**Authors:** OpenIntent Contributors  
**Requires:** [RFC-0001 (Intents)](./0001-intent-objects.md), [RFC-0009 (Cost Tracking)](./0009-cost-tracking.md)

---

## Abstract

This RFC defines the integration layer between the OpenIntent protocol and Large Language Model providers. It standardizes how LLM calls are initiated, tracked, and audited within the protocol, including token usage, cost attribution, streaming support, and distributed tracing.

## Motivation

LLMs are the primary reasoning engine for most AI agents. The protocol must:

- **Track token usage:** Every LLM call consumes tokens with associated costs
- **Attribute costs:** Link LLM usage to specific intents and agents
- **Enable observability:** Distributed tracing across multi-model workflows
- **Support streaming:** Real-time token streaming for responsive agents
- **Remain provider-neutral:** Work with any LLM provider through adapters

## Adapter Architecture

The SDK provides a pluggable adapter system for LLM providers:

```python
from openintent.adapters import (
    OpenAIAdapter,
    AnthropicAdapter,
    GeminiAdapter,
    GrokAdapter,
    DeepSeekAdapter,
    AzureOpenAIAdapter,
    OpenRouterAdapter,
)
```

### Base Adapter Interface

All adapters implement a common interface:

```python
class BaseAdapter:
    async def complete(self, messages, **kwargs) -> LLMResponse
    async def stream(self, messages, **kwargs) -> AsyncIterator[str]
    
    # Streaming hooks
    def _invoke_stream_start(self, metadata)
    def _invoke_on_token(self, token)
    def _invoke_stream_end(self, metadata)
    def _invoke_stream_error(self, error)
```

### Streaming Hooks

Adapters support lifecycle hooks for observability:

```python
from openintent.adapters import AdapterConfig

config = AdapterConfig(
    on_stream_start=lambda meta: print(f"Stream started: {meta}"),
    on_token=lambda token: print(token, end=""),
    on_stream_end=lambda meta: print(f"\nStream ended: {meta}"),
    on_stream_error=lambda err: print(f"Error: {err}"),
)
```

All hooks use a fail-safe pattern — exceptions in hooks are caught and logged without breaking the main flow.

## Event Types

LLM interactions produce protocol events:

| Event Type | Description |
|-----------|-------------|
| `llm_request_started` | LLM call initiated with model, prompt tokens |
| `llm_request_completed` | LLM call finished with completion tokens, latency |
| `llm_request_failed` | LLM call failed with error details |
| `llm_stream_started` | Streaming response began |
| `llm_stream_completed` | Streaming response finished |

## Cost Attribution

Each LLM call automatically records cost data (RFC-0009):

```json
{
  "intent_id": "uuid",
  "agent_id": "agent-research",
  "cost_type": "tokens",
  "provider": "openai",
  "metadata": {
    "model": "gpt-4",
    "prompt_tokens": 1200,
    "completion_tokens": 300,
    "total_tokens": 1500,
    "latency_ms": 2340
  }
}
```

## Distributed Tracing

LLM calls are integrated with distributed tracing (OpenTelemetry compatible):

- Each LLM call creates a span linked to the parent intent
- Spans include model, token counts, latency, and provider
- Trace context propagates across agent-to-agent coordination

## Context Packing

The adapter layer manages context window packing strategy:

- Selects which memory entries (RFC-0015) to include in prompts
- Respects token limits per model
- Prioritizes recent and relevant context
- Supports structured context injection from permissions (RFC-0011)

## Cross-RFC Interactions

| RFC | Interaction |
|-----|------------|
| RFC-0009 (Costs) | Automatic token and cost tracking per LLM call |
| RFC-0011 (Access) | Context injection based on agent permissions |
| RFC-0012 (Tasks) | LLM adapters used within task execution |
| RFC-0015 (Memory) | Memory entries packed into LLM context windows |
