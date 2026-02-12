# OpenIntent SDK v0.9.1 — Streaming Token Usage Fix

**Release date:** 2026-02-12

This patch release fixes streaming token usage tracking across all 7 supported LLM provider adapters. Previously, `tokens_streamed` relied on character count as a proxy for token usage during streaming responses. All adapters now capture real `prompt_tokens`, `completion_tokens`, and `total_tokens` from provider APIs.

---

## What changed

### Fixed

- **Streaming token usage capture** — All 7 LLM provider adapters now report actual token counts during streaming responses instead of approximating with character length.

- **OpenAI-compatible adapters** (OpenAI, DeepSeek, Azure OpenAI, OpenRouter, Grok) — Inject `stream_options={"include_usage": True}` to receive usage data in the final stream chunk. Token counts are extracted and passed through to `complete_stream()` and `log_llm_request_completed()`.

- **Gemini adapter** — Captures `usage_metadata` from stream chunks (`prompt_token_count`, `candidates_token_count`, `total_token_count`) and maps them to the standard `prompt_tokens` / `completion_tokens` / `total_tokens` fields.

- **Anthropic adapter** — Extracts usage from the stream's internal message snapshot in `__exit__`, removing the need for a manual `get_final_message()` call.

- **`tokens_streamed` field** — Now reports the actual completion token count from the provider API. Falls back to character count only when usage data is unavailable.

---

## Affected adapters

| Adapter | Provider | Fix applied |
|---------|----------|-------------|
| `OpenAIAdapter` | OpenAI | `stream_options` injection + chunk usage capture |
| `DeepSeekAdapter` | DeepSeek | `stream_options` injection + chunk usage capture |
| `AzureOpenAIAdapter` | Azure OpenAI | `stream_options` injection + chunk usage capture |
| `OpenRouterAdapter` | OpenRouter | `stream_options` injection + chunk usage capture |
| `GrokAdapter` | xAI Grok | `stream_options` injection + chunk usage capture |
| `GeminiAdapter` | Google Gemini | `usage_metadata` capture from stream chunks |
| `AnthropicAdapter` | Anthropic | Message snapshot usage extraction in `__exit__` |

---

## Upgrade

```bash
pip install openintent==0.9.1
```

No breaking changes. This is a drop-in replacement for v0.9.0.

---

## Full changelog

See [CHANGELOG.md](./CHANGELOG.md) for the complete history.
