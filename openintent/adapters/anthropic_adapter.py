"""Anthropic provider adapter for automatic OpenIntent coordination.

This adapter wraps the Anthropic client to automatically log intent events
for message creation, tool use, and streaming responses.

Installation:
    pip install openintent[anthropic]

Example:
    from anthropic import Anthropic
    from openintent import OpenIntentClient
    from openintent.adapters import AnthropicAdapter

    openintent = OpenIntentClient(base_url="...", api_key="...")
    anthropic_client = Anthropic()

    adapter = AnthropicAdapter(anthropic_client, openintent, intent_id="...")

    # Regular message - automatically logs request events
    message = adapter.messages.create(
        model="claude-3-opus-20240229",
        max_tokens=1024,
        messages=[{"role": "user", "content": "Hello"}]
    )

    # Streaming - automatically logs stream events
    with adapter.messages.stream(
        model="claude-3-opus-20240229",
        max_tokens=1024,
        messages=[{"role": "user", "content": "Hello"}]
    ) as stream:
        for text in stream.text_stream:
            print(text, end="")
"""

import time
from typing import TYPE_CHECKING, Any, Iterator, Optional

from openintent.adapters.base import AdapterConfig, BaseAdapter

if TYPE_CHECKING:
    from openintent import OpenIntentClient


def _check_anthropic_installed() -> None:
    """Check if the anthropic package is installed."""
    try:
        import anthropic  # noqa: F401
    except ImportError:
        raise ImportError(
            "AnthropicAdapter requires the 'anthropic' package. "
            "Install it with: pip install openintent[anthropic]"
        ) from None


class AnthropicMessages:
    """Wrapped messages interface."""

    def __init__(self, adapter: "AnthropicAdapter"):
        self._adapter = adapter

    def create(self, **kwargs: Any) -> Any:
        """Create a message with automatic event logging."""
        return self._adapter._create_message(**kwargs)

    def stream(self, **kwargs: Any) -> Any:
        """Create a streaming message with automatic event logging."""
        return self._adapter._create_stream(**kwargs)


class AnthropicAdapter(BaseAdapter):
    """Adapter for the Anthropic Python client.

    Wraps an Anthropic client instance to automatically log OpenIntent events
    for all message creations, tool use, and streaming responses.

    The adapter exposes the same interface as the Anthropic client, so you can
    use it as a drop-in replacement:

        adapter = AnthropicAdapter(anthropic_client, openintent, intent_id)
        message = adapter.messages.create(...)

    Events logged:
    - LLM_REQUEST_STARTED: When a message request begins
    - LLM_REQUEST_COMPLETED: When a message finishes successfully
    - LLM_REQUEST_FAILED: When a message request fails
    - TOOL_CALL_STARTED: When the model uses a tool
    - STREAM_STARTED: When a streaming response begins
    - STREAM_CHUNK: Periodically during streaming (if configured)
    - STREAM_COMPLETED: When streaming finishes
    - STREAM_CANCELLED: If streaming is interrupted
    """

    def __init__(
        self,
        anthropic_client: Any,
        openintent_client: "OpenIntentClient",
        intent_id: str,
        config: Optional[AdapterConfig] = None,
    ):
        """Initialize the Anthropic adapter.

        Args:
            anthropic_client: The Anthropic client instance to wrap.
            openintent_client: The OpenIntent client for logging events.
            intent_id: The intent ID to associate events with.
            config: Optional adapter configuration.

        Raises:
            ImportError: If the anthropic package is not installed.
        """
        _check_anthropic_installed()
        super().__init__(openintent_client, intent_id, config)
        self._anthropic = anthropic_client
        self.messages = AnthropicMessages(self)

    @property
    def anthropic(self) -> Any:
        """The wrapped Anthropic client."""
        return self._anthropic

    def _create_message(self, **kwargs: Any) -> Any:
        """Create a message with automatic event logging."""
        model = kwargs.get("model", "unknown")
        messages = kwargs.get("messages", [])
        tools = kwargs.get("tools", [])
        temperature = kwargs.get("temperature")

        request_id = self._generate_id()

        if self._config.log_requests:
            try:
                self._client.log_llm_request_started(
                    self._intent_id,
                    request_id=request_id,
                    provider="anthropic",
                    model=model,
                    messages_count=len(messages),
                    tools_available=([t.get("name", "") for t in tools] if tools else None),
                    stream=False,
                    temperature=temperature,
                )
            except Exception as e:
                self._handle_error(e, {"phase": "request_started", "request_id": request_id})

        start_time = time.time()

        try:
            response = self._anthropic.messages.create(**kwargs)
            duration_ms = int((time.time() - start_time) * 1000)

            if self._config.log_requests:
                try:
                    usage = getattr(response, "usage", None)
                    content_blocks = getattr(response, "content", [])
                    text_content = ""
                    for block in content_blocks:
                        if getattr(block, "type", None) == "text":
                            text_content += getattr(block, "text", "")

                    self._client.log_llm_request_completed(
                        self._intent_id,
                        request_id=request_id,
                        provider="anthropic",
                        model=model,
                        messages_count=len(messages),
                        response_content=text_content if text_content else None,
                        finish_reason=getattr(response, "stop_reason", None),
                        prompt_tokens=(getattr(usage, "input_tokens", None) if usage else None),
                        completion_tokens=(
                            getattr(usage, "output_tokens", None) if usage else None
                        ),
                        total_tokens=(
                            (
                                getattr(usage, "input_tokens", 0)
                                + getattr(usage, "output_tokens", 0)
                            )
                            if usage
                            else None
                        ),
                        duration_ms=duration_ms,
                    )
                except Exception as e:
                    self._handle_error(e, {"phase": "request_completed", "request_id": request_id})

            if self._config.log_tool_calls:
                self._log_tool_use(response, model)

            return response

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            if self._config.log_requests:
                try:
                    self._client.log_llm_request_failed(
                        self._intent_id,
                        request_id=request_id,
                        provider="anthropic",
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

    def _create_stream(self, **kwargs: Any) -> "AnthropicStreamContext":
        """Create a streaming message context manager."""
        return AnthropicStreamContext(self, **kwargs)

    def _log_tool_use(self, response: Any, model: str) -> None:
        """Log tool use blocks from a response."""
        content_blocks = getattr(response, "content", [])

        for block in content_blocks:
            if getattr(block, "type", None) != "tool_use":
                continue

            tool_id = getattr(block, "id", None) or self._generate_id()
            name = getattr(block, "name", "unknown")
            input_data = getattr(block, "input", {})

            try:
                self._client.log_tool_call_started(
                    self._intent_id,
                    tool_name=name,
                    tool_id=tool_id,
                    arguments=(
                        input_data if isinstance(input_data, dict) else {"raw": str(input_data)}
                    ),
                    provider="anthropic",
                    model=model,
                )
            except Exception as e:
                self._handle_error(e, {"phase": "tool_call_started", "tool_id": tool_id})


class AnthropicStreamContext:
    """Context manager for streaming Anthropic messages."""

    def __init__(self, adapter: AnthropicAdapter, **kwargs: Any):
        self._adapter = adapter
        self._kwargs = kwargs
        self._stream: Optional[Any] = None
        self._stream_id: Optional[str] = None
        self._request_id: Optional[str] = None
        self._start_time: float = 0
        self._chunk_count: int = 0
        self._content_parts: list[str] = []
        self._tool_use_blocks: list[dict[str, Any]] = []
        self._stop_reason: Optional[str] = None
        self._usage: Optional[dict[str, int]] = None

    def __enter__(self) -> "AnthropicStreamWrapper":
        model = self._kwargs.get("model", "unknown")
        messages = self._kwargs.get("messages", [])
        tools = self._kwargs.get("tools", [])
        temperature = self._kwargs.get("temperature")

        self._request_id = self._adapter._generate_id()
        self._stream_id = self._adapter._generate_id()
        self._start_time = time.time()

        if self._adapter._config.log_requests:
            try:
                self._adapter._client.log_llm_request_started(
                    self._adapter._intent_id,
                    request_id=self._request_id,
                    provider="anthropic",
                    model=model,
                    messages_count=len(messages),
                    tools_available=([t.get("name", "") for t in tools] if tools else None),
                    stream=True,
                    temperature=temperature,
                )
            except Exception as e:
                self._adapter._handle_error(
                    e, {"phase": "request_started", "request_id": self._request_id}
                )

        if self._adapter._config.log_streams:
            try:
                self._adapter._client.start_stream(
                    self._adapter._intent_id,
                    stream_id=self._stream_id,
                    provider="anthropic",
                    model=model,
                )
            except Exception as e:
                self._adapter._handle_error(
                    e, {"phase": "stream_started", "stream_id": self._stream_id}
                )

        self._adapter._invoke_stream_start(self._stream_id, model, "anthropic")

        self._stream = self._adapter._anthropic.messages.stream(**self._kwargs)
        inner_stream = self._stream.__enter__()

        return AnthropicStreamWrapper(self, inner_stream)

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        model = self._kwargs.get("model", "unknown")
        messages = self._kwargs.get("messages", [])
        duration_ms = int((time.time() - self._start_time) * 1000)

        if self._usage is None and self._stream and exc_type is None:
            try:
                inner_stream = (
                    self._stream._MessageStreamManager__stream
                    if hasattr(self._stream, "_MessageStreamManager__stream")
                    else None
                )
                if inner_stream is None:
                    inner_stream = getattr(self._stream, "_stream", None)
                if inner_stream is not None:
                    snapshot = getattr(inner_stream, "current_message_snapshot", None)
                    if snapshot is not None:
                        usage = getattr(snapshot, "usage", None)
                        if usage:
                            self._usage = {
                                "input_tokens": getattr(usage, "input_tokens", 0),
                                "output_tokens": getattr(usage, "output_tokens", 0),
                            }
                        if self._stop_reason is None:
                            self._stop_reason = getattr(snapshot, "stop_reason", None)
            except Exception:
                pass

        if self._stream:
            try:
                self._stream.__exit__(exc_type, exc_val, exc_tb)
            except Exception:
                pass

        stream_id = self._stream_id or ""
        request_id = self._request_id or ""

        if exc_type is not None:
            if self._adapter._config.log_streams and stream_id:
                try:
                    self._adapter._client.cancel_stream(
                        self._adapter._intent_id,
                        stream_id=stream_id,
                        provider="anthropic",
                        model=model,
                        reason=str(exc_val) if exc_val else "Exception",
                        chunks_received=self._chunk_count,
                    )
                except Exception as e:
                    self._adapter._handle_error(
                        e, {"phase": "stream_cancelled", "stream_id": stream_id}
                    )
            self._adapter._invoke_stream_error(
                exc_val if exc_val else Exception("Stream cancelled"),
                self._stream_id or "",
            )  # noqa: E501
            return

        if self._adapter._config.log_streams and stream_id:
            try:
                completion_tokens = self._usage.get("output_tokens") if self._usage else None
                self._adapter._client.complete_stream(
                    self._adapter._intent_id,
                    stream_id=stream_id,
                    provider="anthropic",
                    model=model,
                    chunks_received=self._chunk_count,
                    tokens_streamed=completion_tokens
                    if completion_tokens is not None
                    else len("".join(self._content_parts)),
                )
            except Exception as e:
                self._adapter._handle_error(
                    e, {"phase": "stream_completed", "stream_id": stream_id}
                )

        self._adapter._invoke_stream_end(
            self._stream_id or "", "".join(self._content_parts), self._chunk_count
        )  # noqa: E501

        if self._adapter._config.log_requests and request_id:
            try:
                total_tokens = None
                if self._usage:
                    total_tokens = self._usage.get("input_tokens", 0) + self._usage.get(
                        "output_tokens", 0
                    )

                self._adapter._client.log_llm_request_completed(
                    self._adapter._intent_id,
                    request_id=request_id,
                    provider="anthropic",
                    model=model,
                    messages_count=len(messages),
                    response_content=(
                        "".join(self._content_parts) if self._content_parts else None
                    ),
                    finish_reason=self._stop_reason,
                    prompt_tokens=(self._usage.get("input_tokens") if self._usage else None),
                    completion_tokens=(self._usage.get("output_tokens") if self._usage else None),
                    total_tokens=total_tokens,
                    duration_ms=duration_ms,
                )
            except Exception as e:
                self._adapter._handle_error(
                    e, {"phase": "request_completed", "request_id": request_id}
                )

        if self._adapter._config.log_tool_calls and self._tool_use_blocks:
            for tool in self._tool_use_blocks:
                try:
                    self._adapter._client.log_tool_call_started(
                        self._adapter._intent_id,
                        tool_name=tool.get("name", "unknown"),
                        tool_id=tool.get("id", self._adapter._generate_id()),
                        arguments=tool.get("input", {}),
                        provider="anthropic",
                        model=model,
                    )
                except Exception as e:
                    self._adapter._handle_error(
                        e, {"phase": "tool_call_started", "tool_id": tool.get("id")}
                    )


class AnthropicStreamWrapper:
    """Wrapper around Anthropic stream for event tracking."""

    def __init__(self, context: AnthropicStreamContext, stream: Any):
        self._context = context
        self._stream = stream

    @property
    def text_stream(self) -> Iterator[str]:
        """Iterate over text chunks from the stream."""
        for text in self._stream.text_stream:
            self._context._chunk_count += 1
            self._context._content_parts.append(text)
            self._context._adapter._invoke_on_token(text, self._context._stream_id or "")

            stream_id = self._context._stream_id
            if (
                self._context._adapter._config.log_stream_chunks
                and stream_id
                and self._context._chunk_count % self._context._adapter._config.chunk_log_interval
                == 0
            ):
                try:
                    self._context._adapter._client.log_stream_chunk(
                        self._context._adapter._intent_id,
                        stream_id,
                        chunk_index=self._context._chunk_count,
                    )
                except Exception as e:
                    self._context._adapter._handle_error(
                        e,
                        {
                            "phase": "stream_chunk",
                            "stream_id": stream_id,
                        },
                    )

            yield text

    def get_final_message(self) -> Any:
        """Get the final message after streaming completes."""
        message = self._stream.get_final_message()

        usage = getattr(message, "usage", None)
        if usage:
            self._context._usage = {
                "input_tokens": getattr(usage, "input_tokens", 0),
                "output_tokens": getattr(usage, "output_tokens", 0),
            }

        self._context._stop_reason = getattr(message, "stop_reason", None)

        content_blocks = getattr(message, "content", [])
        for block in content_blocks:
            if getattr(block, "type", None) == "tool_use":
                self._context._tool_use_blocks.append(
                    {
                        "id": getattr(block, "id", None),
                        "name": getattr(block, "name", None),
                        "input": getattr(block, "input", {}),
                    }
                )

        return message
