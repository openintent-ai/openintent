"""Provider adapters for automatic OpenIntent coordination.

These adapters wrap popular LLM provider clients to automatically log
intent events for tool calls, LLM requests, and streaming responses.

Supported providers:
- OpenAI (GPT-4, GPT-4o, GPT-5.2, codex models like gpt-5.2-codex, etc.)
- Anthropic (Claude 3, Claude 4, etc.)
- Google Gemini (Gemini 1.5, Gemini 2, etc.)
- xAI Grok (Grok-beta, etc.)
- DeepSeek (DeepSeek-chat, DeepSeek-coder, etc.)
- Azure OpenAI (GPT-4, GPT-4o via Azure endpoints)
- OpenRouter (200+ models via unified API)

Codex model support:
  OpenAI codex models (e.g. gpt-5.2-codex) use /v1/completions instead of
  /v1/chat/completions. The OpenAI adapter auto-detects codex models by name
  and routes to the correct endpoint. You can also use adapter.completions.create()
  directly for explicit completions access.

Streaming hooks:
All adapters support streaming hooks via AdapterConfig:
- on_stream_start(stream_id, model, provider): Called when a stream begins
- on_token(token, stream_id): Called for each content token during streaming
- on_stream_end(stream_id, content, chunks): Called when a stream completes
- on_stream_error(error, stream_id): Called when a stream fails

Example usage with OpenAI:

    from openai import OpenAI
    from openintent import OpenIntentClient
    from openintent.adapters import OpenAIAdapter

    client = OpenIntentClient(base_url="...", api_key="...")
    openai_client = OpenAI()

    # Wrap the OpenAI client
    adapter = OpenAIAdapter(openai_client, client, intent_id="...")

    # Use adapter.chat.completions.create() - automatically logs events
    response = adapter.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": "Hello"}]
    )

Example usage with streaming hooks:

    from openintent.adapters import AdapterConfig, OpenAIAdapter

    config = AdapterConfig(
        on_stream_start=lambda sid, model, provider: print(f"Stream {sid} started"),
        on_token=lambda token, sid: print(token, end=""),
        on_stream_end=lambda sid, content, chunks: print(f"\\nDone: {chunks} chunks"),
        on_stream_error=lambda err, sid: print(f"Error: {err}"),
    )

    adapter = OpenAIAdapter(openai_client, client, intent_id="...", config=config)

Example usage with Google Gemini:

    import google.generativeai as genai
    from openintent import OpenIntentClient
    from openintent.adapters import GeminiAdapter

    genai.configure(api_key="...")
    model = genai.GenerativeModel("gemini-1.5-pro")

    client = OpenIntentClient(base_url="...", api_key="...")
    adapter = GeminiAdapter(model, client, intent_id="...")

    response = adapter.generate_content("Hello, how are you?")
"""

from openintent.adapters.anthropic_adapter import AnthropicAdapter
from openintent.adapters.azure_openai_adapter import AzureOpenAIAdapter
from openintent.adapters.base import AdapterConfig, BaseAdapter
from openintent.adapters.deepseek_adapter import DeepSeekAdapter
from openintent.adapters.gemini_adapter import GeminiAdapter
from openintent.adapters.grok_adapter import GrokAdapter
from openintent.adapters.openai_adapter import OpenAIAdapter
from openintent.adapters.openrouter_adapter import OpenRouterAdapter

__all__ = [
    "BaseAdapter",
    "AdapterConfig",
    "OpenAIAdapter",
    "AnthropicAdapter",
    "GeminiAdapter",
    "GrokAdapter",
    "DeepSeekAdapter",
    "AzureOpenAIAdapter",
    "OpenRouterAdapter",
]
