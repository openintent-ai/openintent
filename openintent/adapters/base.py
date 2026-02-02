"""Base adapter for LLM provider integrations.

Adapters automatically log OpenIntent events for LLM interactions,
providing visibility into tool calls, requests, and streaming.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Optional

if TYPE_CHECKING:
    from openintent import OpenIntentClient


@dataclass
class AdapterConfig:
    """Configuration for provider adapters.

    Attributes:
        log_requests: Whether to log LLM request events. Default True.
        log_tool_calls: Whether to log tool call events. Default True.
        log_streams: Whether to log streaming events. Default True.
        log_stream_chunks: Whether to log individual stream chunks.
            Default False to reduce noise.
        chunk_log_interval: If log_stream_chunks is True, log every Nth chunk.
            Default 10.
        on_error: Optional callback for adapter errors. Signature:
            (error: Exception, context: dict) -> None
    """

    log_requests: bool = True
    log_tool_calls: bool = True
    log_streams: bool = True
    log_stream_chunks: bool = False
    chunk_log_interval: int = 10
    on_error: Optional[Callable[[Exception, dict[str, Any]], None]] = None
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseAdapter:
    """Base class for provider adapters.

    Subclasses implement provider-specific wrapping logic while this
    base class provides common utilities and configuration handling.
    """

    def __init__(
        self,
        openintent_client: "OpenIntentClient",
        intent_id: str,
        config: Optional[AdapterConfig] = None,
    ):
        """Initialize the adapter.

        Args:
            openintent_client: The OpenIntent client for logging events.
            intent_id: The intent ID to associate events with.
            config: Optional adapter configuration. Uses defaults if not provided.
        """
        self._client = openintent_client
        self._intent_id = intent_id
        self._config = config or AdapterConfig()

    @property
    def client(self) -> "OpenIntentClient":
        """The OpenIntent client."""
        return self._client

    @property
    def intent_id(self) -> str:
        """The intent ID for event logging."""
        return self._intent_id

    @property
    def config(self) -> AdapterConfig:
        """The adapter configuration."""
        return self._config

    def _handle_error(self, error: Exception, context: dict[str, Any]) -> None:
        """Handle adapter errors.

        If an on_error callback is configured, call it. Otherwise, ignore
        the error to prevent adapter issues from breaking the main flow.
        """
        if self._config.on_error:
            try:
                self._config.on_error(error, context)
            except Exception:
                pass

    def _generate_id(self) -> str:
        """Generate a unique ID for tracking."""
        import uuid

        return str(uuid.uuid4())
