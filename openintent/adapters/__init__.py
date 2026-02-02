"""Provider adapters for automatic OpenIntent coordination.

These adapters wrap popular LLM provider clients to automatically log
intent events for tool calls, LLM requests, and streaming responses.

Supported providers:
- OpenAI (GPT-4, GPT-3.5, etc.)
- Anthropic (Claude 3, Claude 2, etc.)
- Google Gemini (Gemini 1.5, etc.)
- xAI Grok (Grok-beta, etc.)
- DeepSeek (DeepSeek-chat, DeepSeek-coder, etc.)

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
from openintent.adapters.base import AdapterConfig, BaseAdapter
from openintent.adapters.deepseek_adapter import DeepSeekAdapter
from openintent.adapters.gemini_adapter import GeminiAdapter
from openintent.adapters.grok_adapter import GrokAdapter
from openintent.adapters.openai_adapter import OpenAIAdapter

__all__ = [
    "BaseAdapter",
    "AdapterConfig",
    "OpenAIAdapter",
    "AnthropicAdapter",
    "GeminiAdapter",
    "GrokAdapter",
    "DeepSeekAdapter",
]
