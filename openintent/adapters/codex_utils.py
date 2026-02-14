"""Utilities for detecting and handling OpenAI codex (completions-only) models.

Codex models (e.g. gpt-5.2-codex, o3-codex) use the /v1/completions endpoint
instead of /v1/chat/completions. This module provides helpers to detect codex
models, convert chat messages to a prompt string, and adapt completions-style
kwargs for the completions API.
"""

from typing import Any

CODEX_PATTERNS = ("-codex", "codex-")


def is_codex_model(model: str) -> bool:
    """Return True if the model name indicates a codex/completions model."""
    model_lower = model.lower()
    return any(pattern in model_lower for pattern in CODEX_PATTERNS)


def messages_to_prompt(messages: list[dict[str, Any]]) -> str:
    """Convert a list of chat messages into a single prompt string.

    Concatenates message contents with role prefixes, producing a
    prompt suitable for the /v1/completions endpoint.
    """
    parts: list[str] = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "system":
            parts.append(content)
        elif role == "assistant":
            parts.append(f"Assistant: {content}")
        else:
            parts.append(f"User: {content}")
    return "\n\n".join(parts)


def chat_kwargs_to_completions_kwargs(kwargs: dict[str, Any]) -> dict[str, Any]:
    """Convert chat.completions.create kwargs to completions.create kwargs.

    Moves ``messages`` → ``prompt``, removes unsupported chat-only params
    like ``tools`` and ``tool_choice``, and passes through everything else.
    """
    out = dict(kwargs)

    messages = out.pop("messages", [])
    prompt = out.pop("prompt", None)
    if prompt is None:
        prompt = messages_to_prompt(messages) if messages else ""
    out["prompt"] = prompt

    out.pop("tools", None)
    out.pop("tool_choice", None)
    out.pop("response_format", None)
    out.pop("stream_options", None)

    return out
