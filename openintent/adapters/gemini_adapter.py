"""Google Gemini provider adapter for automatic OpenIntent coordination.

This adapter wraps the Google Generative AI client to automatically log intent events
for content generation, tool calls, and streaming responses.

Installation:
    pip install openintent[gemini]

Example:
    import google.generativeai as genai
    from openintent import OpenIntentClient
    from openintent.adapters import GeminiAdapter

    openintent = OpenIntentClient(base_url="...", api_key="...")
    genai.configure(api_key="...")
    model = genai.GenerativeModel("gemini-1.5-pro")

    adapter = GeminiAdapter(model, openintent, intent_id="...")

    # Regular generation - automatically logs request events
    response = adapter.generate_content("Hello, how are you?")

    # Streaming - automatically logs stream events
    for chunk in adapter.generate_content("Tell me a story", stream=True):
        print(chunk.text, end="")
"""

import time
from typing import TYPE_CHECKING, Any, Iterator, Optional

from openintent.adapters.base import AdapterConfig, BaseAdapter

if TYPE_CHECKING:
    from openintent import OpenIntentClient


def _check_gemini_installed() -> None:
    """Check if the google-generativeai package is installed."""
    try:
        import google.generativeai  # noqa: F401
    except ImportError:
        raise ImportError(
            "GeminiAdapter requires the 'google-generativeai' package. "
            "Install it with: pip install openintent[gemini]"
        ) from None


class GeminiAdapter(BaseAdapter):
    """Adapter for the Google Generative AI (Gemini) Python client.

    Wraps a GenerativeModel instance to automatically log OpenIntent events
    for all content generation, tool calls, and streaming responses.

    The adapter exposes the same interface as the GenerativeModel, so you can
    use it as a drop-in replacement:

        adapter = GeminiAdapter(model, openintent, intent_id)
        response = adapter.generate_content("Hello")

    Events logged:
    - LLM_REQUEST_STARTED: When a generation request begins
    - LLM_REQUEST_COMPLETED: When generation finishes successfully
    - LLM_REQUEST_FAILED: When generation fails
    - TOOL_CALL_STARTED: When the model calls a function
    - STREAM_STARTED: When a streaming response begins
    - STREAM_CHUNK: Periodically during streaming (if configured)
    - STREAM_COMPLETED: When streaming finishes
    - STREAM_CANCELLED: If streaming is interrupted
    """

    def __init__(
        self,
        gemini_model: Any,
        openintent_client: "OpenIntentClient",
        intent_id: str,
        config: Optional[AdapterConfig] = None,
    ):
        """Initialize the Gemini adapter.

        Args:
            gemini_model: The GenerativeModel instance to wrap.
            openintent_client: The OpenIntent client for logging events.
            intent_id: The intent ID to associate events with.
            config: Optional adapter configuration.

        Raises:
            ImportError: If the google-generativeai package is not installed.
        """
        _check_gemini_installed()
        super().__init__(openintent_client, intent_id, config)
        self._model = gemini_model
        self._model_name = getattr(gemini_model, "model_name", "gemini")

    @property
    def model(self) -> Any:
        """The wrapped GenerativeModel."""
        return self._model

    def generate_content(
        self,
        contents: Any,
        *,
        stream: bool = False,
        **kwargs: Any,
    ) -> Any:
        """Generate content with automatic event logging.

        Args:
            contents: The prompt or conversation contents.
            stream: Whether to stream the response.
            **kwargs: Additional arguments passed to generate_content.

        Returns:
            GenerateContentResponse or iterator of chunks if streaming.
        """
        request_id = self._generate_id()
        model = self._model_name
        tools = kwargs.get("tools", [])
        temperature = kwargs.get("generation_config", {})
        if hasattr(temperature, "temperature"):
            temperature = temperature.temperature
        elif isinstance(temperature, dict):
            temperature = temperature.get("temperature")
        else:
            temperature = None

        messages_count = (
            1 if isinstance(contents, str) else len(contents) if isinstance(contents, list) else 1
        )

        if self._config.log_requests:
            try:
                tool_names = []
                if tools:
                    for tool in tools:
                        if hasattr(tool, "function_declarations"):
                            for fd in tool.function_declarations:
                                tool_names.append(getattr(fd, "name", "unknown"))

                self._client.log_llm_request_started(
                    self._intent_id,
                    request_id=request_id,
                    provider="google",
                    model=model,
                    messages_count=messages_count,
                    tools_available=tool_names if tool_names else None,
                    stream=stream,
                    temperature=temperature,
                )
            except Exception as e:
                self._handle_error(e, {"phase": "request_started", "request_id": request_id})

        start_time = time.time()

        try:
            if stream:
                return self._handle_stream(
                    contents, kwargs, request_id, model, messages_count, start_time
                )
            else:
                return self._handle_completion(
                    contents, kwargs, request_id, model, messages_count, start_time
                )
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            if self._config.log_requests:
                try:
                    self._client.log_llm_request_failed(
                        self._intent_id,
                        request_id=request_id,
                        provider="google",
                        model=model,
                        messages_count=messages_count,
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
        contents: Any,
        kwargs: dict[str, Any],
        request_id: str,
        model: str,
        messages_count: int,
        start_time: float,
    ) -> Any:
        """Handle a non-streaming completion."""
        response = self._model.generate_content(contents, **kwargs)
        duration_ms = int((time.time() - start_time) * 1000)

        if self._config.log_requests:
            try:
                usage = getattr(response, "usage_metadata", None)
                text_content = ""
                if response.candidates:
                    candidate = response.candidates[0]
                    if hasattr(candidate, "content") and candidate.content.parts:
                        for part in candidate.content.parts:
                            if hasattr(part, "text"):
                                text_content += part.text

                finish_reason = None
                if response.candidates:
                    finish_reason = str(response.candidates[0].finish_reason)

                self._client.log_llm_request_completed(
                    self._intent_id,
                    request_id=request_id,
                    provider="google",
                    model=model,
                    messages_count=messages_count,
                    response_content=text_content if text_content else None,
                    finish_reason=finish_reason,
                    prompt_tokens=(getattr(usage, "prompt_token_count", None) if usage else None),
                    completion_tokens=(
                        getattr(usage, "candidates_token_count", None) if usage else None
                    ),
                    total_tokens=(getattr(usage, "total_token_count", None) if usage else None),
                    duration_ms=duration_ms,
                )
            except Exception as e:
                self._handle_error(e, {"phase": "request_completed", "request_id": request_id})

        if self._config.log_tool_calls:
            self._log_function_calls(response, model)

        return response

    def _handle_stream(
        self,
        contents: Any,
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
                    provider="google",
                    model=model,
                )
            except Exception as e:
                self._handle_error(e, {"phase": "stream_started", "stream_id": stream_id})

        self._invoke_stream_start(stream_id, model, "google")

        stream = self._model.generate_content(contents, stream=True, **kwargs)
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
        function_calls: list[dict[str, Any]] = []
        usage_metadata: Any = None

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
                        self._handle_error(e, {"phase": "stream_chunk", "stream_id": stream_id})

                if getattr(chunk, "usage_metadata", None) is not None:
                    usage_metadata = chunk.usage_metadata

                if chunk.candidates:
                    candidate = chunk.candidates[0]
                    if hasattr(candidate, "content") and candidate.content.parts:
                        for part in candidate.content.parts:
                            if hasattr(part, "text") and part.text:
                                content_parts.append(part.text)
                                self._invoke_on_token(part.text, stream_id)
                            if hasattr(part, "function_call"):
                                fc = part.function_call
                                function_calls.append(
                                    {
                                        "name": fc.name,
                                        "args": dict(fc.args) if fc.args else {},
                                    }
                                )
                    if candidate.finish_reason:
                        finish_reason = str(candidate.finish_reason)

                yield chunk

            duration_ms = int((time.time() - start_time) * 1000)

            prompt_tokens = (
                getattr(usage_metadata, "prompt_token_count", None) if usage_metadata else None
            )
            completion_tokens = (
                getattr(usage_metadata, "candidates_token_count", None) if usage_metadata else None
            )
            total_tokens = (
                getattr(usage_metadata, "total_token_count", None) if usage_metadata else None
            )

            if self._config.log_streams:
                try:
                    self._client.complete_stream(
                        self._intent_id,
                        stream_id=stream_id,
                        provider="google",
                        model=model,
                        chunks_received=chunk_count,
                        tokens_streamed=completion_tokens
                        if completion_tokens is not None
                        else len("".join(content_parts)),
                    )
                except Exception as e:
                    self._handle_error(e, {"phase": "stream_completed", "stream_id": stream_id})

            self._invoke_stream_end(stream_id, "".join(content_parts), chunk_count)

            if self._config.log_requests:
                try:
                    self._client.log_llm_request_completed(
                        self._intent_id,
                        request_id=request_id,
                        provider="google",
                        model=model,
                        messages_count=messages_count,
                        response_content=("".join(content_parts) if content_parts else None),
                        finish_reason=finish_reason,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        total_tokens=total_tokens,
                        duration_ms=duration_ms,
                    )
                except Exception as e:
                    self._handle_error(e, {"phase": "request_completed", "request_id": request_id})

            if self._config.log_tool_calls and function_calls:
                for fc in function_calls:
                    try:
                        self._client.log_tool_call_started(
                            self._intent_id,
                            tool_name=fc["name"],
                            tool_id=self._generate_id(),
                            arguments=fc["args"],
                            provider="google",
                            model=model,
                        )
                    except Exception as e:
                        self._handle_error(e, {"phase": "tool_call_started"})

        except GeneratorExit:
            duration_ms = int((time.time() - start_time) * 1000)
            if self._config.log_streams:
                try:
                    self._client.cancel_stream(
                        self._intent_id,
                        stream_id=stream_id,
                        provider="google",
                        model=model,
                        reason="Generator closed",
                        chunks_received=chunk_count,
                    )
                except Exception as e:
                    self._handle_error(e, {"phase": "stream_cancelled", "stream_id": stream_id})
            self._invoke_stream_error(Exception("Generator closed"), stream_id)
            raise

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            if self._config.log_streams:
                try:
                    self._client.cancel_stream(
                        self._intent_id,
                        stream_id=stream_id,
                        provider="google",
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

    def _log_function_calls(self, response: Any, model: str) -> None:
        """Log function calls from a response."""
        if not response.candidates:
            return

        candidate = response.candidates[0]
        if not hasattr(candidate, "content") or not candidate.content.parts:
            return

        for part in candidate.content.parts:
            if not hasattr(part, "function_call"):
                continue

            fc = part.function_call
            tool_id = self._generate_id()

            try:
                self._client.log_tool_call_started(
                    self._intent_id,
                    tool_name=fc.name,
                    tool_id=tool_id,
                    arguments=dict(fc.args) if fc.args else {},
                    provider="google",
                    model=model,
                )
            except Exception as e:
                self._handle_error(e, {"phase": "tool_call_started", "tool_id": tool_id})

    def start_chat(self, **kwargs: Any) -> "GeminiChatSession":
        """Start a chat session with automatic event logging.

        Returns a wrapped chat session that logs events for each message.
        """
        chat = self._model.start_chat(**kwargs)
        return GeminiChatSession(self, chat)


class GeminiChatSession:
    """Wrapped chat session for event tracking."""

    def __init__(self, adapter: GeminiAdapter, chat: Any):
        self._adapter = adapter
        self._chat = chat

    @property
    def history(self) -> list[Any]:
        """The chat history."""
        return self._chat.history

    def send_message(self, content: Any, *, stream: bool = False, **kwargs: Any) -> Any:
        """Send a message with automatic event logging."""
        request_id = self._adapter._generate_id()
        model = self._adapter._model_name
        messages_count = len(self._chat.history) + 1

        if self._adapter._config.log_requests:
            try:
                self._adapter._client.log_llm_request_started(
                    self._adapter._intent_id,
                    request_id=request_id,
                    provider="google",
                    model=model,
                    messages_count=messages_count,
                    stream=stream,
                )
            except Exception as e:
                self._adapter._handle_error(
                    e, {"phase": "request_started", "request_id": request_id}
                )

        start_time = time.time()

        try:
            if stream:
                return self._handle_stream(
                    content, kwargs, request_id, model, messages_count, start_time
                )
            else:
                response = self._chat.send_message(content, **kwargs)
                duration_ms = int((time.time() - start_time) * 1000)

                if self._adapter._config.log_requests:
                    try:
                        text_content = response.text if hasattr(response, "text") else ""
                        self._adapter._client.log_llm_request_completed(
                            self._adapter._intent_id,
                            request_id=request_id,
                            provider="google",
                            model=model,
                            messages_count=messages_count,
                            response_content=text_content,
                            duration_ms=duration_ms,
                        )
                    except Exception as e:
                        self._adapter._handle_error(
                            e, {"phase": "request_completed", "request_id": request_id}
                        )

                return response

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            if self._adapter._config.log_requests:
                try:
                    self._adapter._client.log_llm_request_failed(
                        self._adapter._intent_id,
                        request_id=request_id,
                        provider="google",
                        model=model,
                        messages_count=messages_count,
                        error=f"{type(e).__name__}: {str(e)}",
                        duration_ms=duration_ms,
                    )
                except Exception as log_error:
                    self._adapter._handle_error(
                        log_error, {"phase": "request_failed", "request_id": request_id}
                    )
            raise

    def _handle_stream(
        self,
        content: Any,
        kwargs: dict[str, Any],
        request_id: str,
        model: str,
        messages_count: int,
        start_time: float,
    ) -> Iterator[Any]:
        """Handle streaming chat response."""
        stream_id = self._adapter._generate_id()

        if self._adapter._config.log_streams:
            try:
                self._adapter._client.start_stream(
                    self._adapter._intent_id,
                    stream_id=stream_id,
                    provider="google",
                    model=model,
                )
            except Exception as e:
                self._adapter._handle_error(e, {"phase": "stream_started", "stream_id": stream_id})

        response = self._chat.send_message(content, stream=True, **kwargs)
        return self._adapter._stream_wrapper(
            response, stream_id, request_id, model, messages_count, start_time
        )
