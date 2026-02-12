"""OpenRouter provider adapter for automatic OpenIntent coordination.

This adapter wraps an OpenAI-compatible client configured for OpenRouter to
automatically log intent events for chat completions, tool calls, and streaming
responses.

OpenRouter provides unified access to hundreds of LLM models (OpenAI, Anthropic,
Google, Meta, Mistral, and more) through a single OpenAI-compatible API.

Installation:
    pip install openintent[openrouter]

Example:
    from openai import OpenAI
    from openintent import OpenIntentClient
    from openintent.adapters import OpenRouterAdapter

    openintent = OpenIntentClient(base_url="...", api_key="...")
    openrouter_client = OpenAI(
        api_key="sk-or-v1-...",
        base_url="https://openrouter.ai/api/v1"
    )

    adapter = OpenRouterAdapter(openrouter_client, openintent, intent_id="...")

    # Regular completion - automatically logs request events
    response = adapter.chat.completions.create(
        model="anthropic/claude-3.5-sonnet",
        messages=[{"role": "user", "content": "Hello"}]
    )

    # Streaming - automatically logs stream events
    stream = adapter.chat.completions.create(
        model="openai/gpt-5.2",
        messages=[{"role": "user", "content": "Hello"}],
        stream=True
    )
    for chunk in stream:
        print(chunk.choices[0].delta.content or "", end="")
"""

import time
from typing import TYPE_CHECKING, Any, Iterator, Optional

from openintent.adapters.base import AdapterConfig, BaseAdapter

if TYPE_CHECKING:
    from openintent import OpenIntentClient


def _check_openrouter_installed() -> None:
    """Check if the openai package is installed (OpenRouter uses OpenAI-compatible API)."""
    try:
        import openai  # noqa: F401
    except ImportError:
        raise ImportError(
            "OpenRouterAdapter requires the 'openai' package (OpenRouter uses OpenAI-compatible API). "  # noqa: E501
            "Install it with: pip install openintent[openrouter]"
        ) from None


class OpenRouterChatCompletions:
    """Wrapped chat.completions interface."""

    def __init__(self, adapter: "OpenRouterAdapter"):
        self._adapter = adapter

    def create(self, **kwargs: Any) -> Any:
        """Create a chat completion with automatic event logging."""
        return self._adapter._create_completion(**kwargs)


class OpenRouterChat:
    """Wrapped chat interface."""

    def __init__(self, adapter: "OpenRouterAdapter"):
        self.completions = OpenRouterChatCompletions(adapter)


class OpenRouterAdapter(BaseAdapter):
    """Adapter for the OpenRouter API (OpenAI-compatible client).

    Wraps an OpenAI client configured for OpenRouter's API to automatically log
    OpenIntent events for all chat completions, tool calls, and streaming.

    OpenRouter provides access to 200+ models from multiple providers through
    a single unified API. The adapter tracks which underlying model is used.

    The adapter exposes the same interface as the OpenAI client:

        adapter = OpenRouterAdapter(openrouter_client, openintent, intent_id)
        response = adapter.chat.completions.create(...)

    Events logged:
    - LLM_REQUEST_STARTED: When a completion request begins
    - LLM_REQUEST_COMPLETED: When a completion finishes successfully
    - LLM_REQUEST_FAILED: When a completion fails
    - TOOL_CALL_STARTED: When the model calls a tool
    - STREAM_STARTED: When a streaming response begins
    - STREAM_CHUNK: Periodically during streaming (if configured)
    - STREAM_COMPLETED: When streaming finishes
    - STREAM_CANCELLED: If streaming is interrupted

    Streaming hooks (on_stream_start, on_token, on_stream_end, on_stream_error)
    are fully supported via AdapterConfig.
    """

    def __init__(
        self,
        openrouter_client: Any,
        openintent_client: "OpenIntentClient",
        intent_id: str,
        config: Optional[AdapterConfig] = None,
    ):
        """Initialize the OpenRouter adapter.

        Args:
            openrouter_client: The OpenAI client configured for OpenRouter's API.
            openintent_client: The OpenIntent client for logging events.
            intent_id: The intent ID to associate events with.
            config: Optional adapter configuration.

        Raises:
            ImportError: If the openai package is not installed.
        """
        _check_openrouter_installed()
        super().__init__(openintent_client, intent_id, config)
        self._openrouter = openrouter_client
        self.chat = OpenRouterChat(self)

    @property
    def openrouter(self) -> Any:
        """The wrapped OpenRouter client."""
        return self._openrouter

    def _create_completion(self, **kwargs: Any) -> Any:
        """Create a completion with automatic event logging."""
        stream = kwargs.get("stream", False)
        model = kwargs.get("model", "auto")
        messages = kwargs.get("messages", [])
        tools = kwargs.get("tools", [])
        temperature = kwargs.get("temperature")

        request_id = self._generate_id()

        if self._config.log_requests:
            try:
                self._client.log_llm_request_started(
                    self._intent_id,
                    request_id=request_id,
                    provider="openrouter",
                    model=model,
                    messages_count=len(messages),
                    tools_available=(
                        [t.get("function", {}).get("name", "") for t in tools]
                        if tools
                        else None
                    ),
                    stream=stream,
                    temperature=temperature,
                )
            except Exception as e:
                self._handle_error(
                    e, {"phase": "request_started", "request_id": request_id}
                )

        start_time = time.time()

        try:
            if stream:
                return self._handle_stream(
                    kwargs, request_id, model, len(messages), start_time
                )
            else:
                return self._handle_completion(
                    kwargs, request_id, model, len(messages), start_time
                )
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            if self._config.log_requests:
                try:
                    self._client.log_llm_request_failed(
                        self._intent_id,
                        request_id=request_id,
                        provider="openrouter",
                        model=model,
                        messages_count=len(messages),
                        error=f"{type(e).__name__}: {str(e)}",
                        duration_ms=duration_ms,
                    )
                except Exception as log_error:
                    self._handle_error(
                        log_error, {"phase": "request_failed", "request_id": request_id}
                    )
            raise

    def _handle_completion(
        self,
        kwargs: dict[str, Any],
        request_id: str,
        model: str,
        messages_count: int,
        start_time: float,
    ) -> Any:
        """Handle a non-streaming completion."""
        response = self._openrouter.chat.completions.create(**kwargs)
        duration_ms = int((time.time() - start_time) * 1000)

        if self._config.log_requests:
            try:
                usage = getattr(response, "usage", None)
                choice = response.choices[0] if response.choices else None
                message = getattr(choice, "message", None) if choice else None

                self._client.log_llm_request_completed(
                    self._intent_id,
                    request_id=request_id,
                    provider="openrouter",
                    model=model,
                    messages_count=messages_count,
                    response_content=(
                        getattr(message, "content", None) if message else None
                    ),
                    finish_reason=(
                        getattr(choice, "finish_reason", None) if choice else None
                    ),
                    prompt_tokens=(
                        getattr(usage, "prompt_tokens", None) if usage else None
                    ),
                    completion_tokens=(
                        getattr(usage, "completion_tokens", None) if usage else None
                    ),
                    total_tokens=(
                        getattr(usage, "total_tokens", None) if usage else None
                    ),
                    duration_ms=duration_ms,
                )
            except Exception as e:
                self._handle_error(
                    e, {"phase": "request_completed", "request_id": request_id}
                )

        if self._config.log_tool_calls and response.choices:
            self._log_tool_calls(response.choices[0], model)

        return response

    def _handle_stream(
        self,
        kwargs: dict[str, Any],
        request_id: str,
        model: str,
        messages_count: int,
        start_time: float,
    ) -> Iterator[Any]:
        """Handle a streaming completion."""
        stream_id = self._generate_id()

        if self._config.log_streams:
            try:
                self._client.start_stream(
                    self._intent_id,
                    stream_id=stream_id,
                    provider="openrouter",
                    model=model,
                )
            except Exception as e:
                self._handle_error(
                    e, {"phase": "stream_started", "stream_id": stream_id}
                )

        self._invoke_stream_start(stream_id, model, "openrouter")

        if "stream_options" not in kwargs:
            kwargs["stream_options"] = {"include_usage": True}
        elif isinstance(kwargs["stream_options"], dict):
            kwargs["stream_options"].setdefault("include_usage", True)

        stream = self._openrouter.chat.completions.create(**kwargs)
        return self._stream_wrapper(
            stream,
            stream_id,
            request_id,
            model,
            messages_count,
            start_time,
        )

    def _stream_wrapper(
        self,
        stream: Iterator[Any],
        stream_id: str,
        request_id: str,
        model: str,
        messages_count: int,
        start_time: float,
    ) -> Iterator[Any]:
        """Wrap a stream to log events."""
        chunk_count = 0
        content_parts: list[str] = []
        finish_reason: Optional[str] = None
        tool_calls_accumulated: list[dict[str, Any]] = []
        usage: Any = None

        try:
            for chunk in stream:
                chunk_count += 1

                if (
                    self._config.log_stream_chunks
                    and chunk_count % self._config.chunk_log_interval == 0
                ):
                    try:
                        self._client.log_stream_chunk(
                            self._intent_id,
                            stream_id,
                            chunk_index=chunk_count,
                        )
                    except Exception as e:
                        self._handle_error(
                            e, {"phase": "stream_chunk", "stream_id": stream_id}
                        )

                if getattr(chunk, "usage", None) is not None:
                    usage = chunk.usage

                if chunk.choices:
                    delta = chunk.choices[0].delta
                    if hasattr(delta, "content") and delta.content:
                        content_parts.append(delta.content)
                        self._invoke_on_token(delta.content, stream_id)
                    if hasattr(delta, "tool_calls") and delta.tool_calls:
                        for tc in delta.tool_calls:
                            tc_dict = {
                                "id": getattr(tc, "id", None),
                                "type": getattr(tc, "type", None),
                                "function": None,
                            }
                            if hasattr(tc, "function") and tc.function:
                                tc_dict["function"] = {
                                    "name": getattr(tc.function, "name", None),
                                    "arguments": getattr(
                                        tc.function, "arguments", None
                                    ),
                                }
                            tool_calls_accumulated.append(tc_dict)
                    if chunk.choices[0].finish_reason:
                        finish_reason = chunk.choices[0].finish_reason

                yield chunk

            duration_ms = int((time.time() - start_time) * 1000)

            prompt_tokens = getattr(usage, "prompt_tokens", None) if usage else None
            completion_tokens = (
                getattr(usage, "completion_tokens", None) if usage else None
            )
            total_tokens = getattr(usage, "total_tokens", None) if usage else None

            if self._config.log_streams:
                try:
                    self._client.complete_stream(
                        self._intent_id,
                        stream_id=stream_id,
                        provider="openrouter",
                        model=model,
                        chunks_received=chunk_count,
                        tokens_streamed=(
                            completion_tokens
                            if completion_tokens is not None
                            else len("".join(content_parts))
                        ),
                    )
                except Exception as e:
                    self._handle_error(
                        e, {"phase": "stream_completed", "stream_id": stream_id}
                    )

            self._invoke_stream_end(stream_id, "".join(content_parts), chunk_count)

            if self._config.log_requests:
                try:
                    self._client.log_llm_request_completed(
                        self._intent_id,
                        request_id=request_id,
                        provider="openrouter",
                        model=model,
                        messages_count=messages_count,
                        response_content=(
                            "".join(content_parts) if content_parts else None
                        ),
                        finish_reason=finish_reason,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        total_tokens=total_tokens,
                        duration_ms=duration_ms,
                    )
                except Exception as e:
                    self._handle_error(
                        e, {"phase": "request_completed", "request_id": request_id}
                    )

            if self._config.log_tool_calls and tool_calls_accumulated:
                self._log_accumulated_tool_calls(tool_calls_accumulated, model)

        except GeneratorExit:
            duration_ms = int((time.time() - start_time) * 1000)
            if self._config.log_streams:
                try:
                    self._client.cancel_stream(
                        self._intent_id,
                        stream_id=stream_id,
                        provider="openrouter",
                        model=model,
                        reason="Generator closed",
                        chunks_received=chunk_count,
                    )
                except Exception as e:
                    self._handle_error(
                        e, {"phase": "stream_cancelled", "stream_id": stream_id}
                    )
            self._invoke_stream_error(Exception("Generator closed"), stream_id)
            raise

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            if self._config.log_streams:
                try:
                    self._client.cancel_stream(
                        self._intent_id,
                        stream_id=stream_id,
                        provider="openrouter",
                        model=model,
                        reason=str(e),
                        chunks_received=chunk_count,
                    )
                except Exception as log_error:
                    self._handle_error(
                        log_error, {"phase": "stream_cancelled", "stream_id": stream_id}
                    )
            self._invoke_stream_error(e, stream_id)
            raise

    def _log_tool_calls(self, choice: Any, model: str) -> None:
        """Log tool calls from a completion choice."""
        message = getattr(choice, "message", None)
        if not message:
            return

        tool_calls = getattr(message, "tool_calls", None)
        if not tool_calls:
            return

        for tc in tool_calls:
            tool_id = getattr(tc, "id", None) or self._generate_id()
            func = getattr(tc, "function", None)
            if not func:
                continue

            name = getattr(func, "name", "unknown")
            arguments_str = getattr(func, "arguments", "{}")

            try:
                import json

                arguments = json.loads(arguments_str)
            except Exception:
                arguments = {"raw": arguments_str}

            try:
                self._client.log_tool_call_started(
                    self._intent_id,
                    tool_name=name,
                    tool_id=tool_id,
                    arguments=arguments,
                    provider="openrouter",
                    model=model,
                )
            except Exception as e:
                self._handle_error(
                    e, {"phase": "tool_call_started", "tool_id": tool_id}
                )

    def _log_accumulated_tool_calls(
        self,
        tool_calls: list[dict[str, Any]],
        model: str,
    ) -> None:
        """Log tool calls accumulated during streaming."""
        merged: dict[str, dict[str, Any]] = {}

        for tc in tool_calls:
            tc_id = tc.get("id")
            if not tc_id:
                continue

            if tc_id not in merged:
                merged[tc_id] = {
                    "id": tc_id,
                    "type": tc.get("type"),
                    "name": None,
                    "arguments": "",
                }

            func = tc.get("function")
            if func:
                if func.get("name"):
                    merged[tc_id]["name"] = func["name"]
                if func.get("arguments"):
                    merged[tc_id]["arguments"] += func["arguments"]

        for tc_id, tc_data in merged.items():
            name = tc_data.get("name", "unknown")
            arguments_str = tc_data.get("arguments", "{}")

            try:
                import json

                arguments = json.loads(arguments_str)
            except Exception:
                arguments = {"raw": arguments_str}

            try:
                self._client.log_tool_call_started(
                    self._intent_id,
                    tool_name=name,
                    tool_id=tc_id,
                    arguments=arguments,
                    provider="openrouter",
                    model=model,
                )
            except Exception as e:
                self._handle_error(e, {"phase": "tool_call_started", "tool_id": tc_id})
