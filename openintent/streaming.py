"""
OpenIntent SDK - SSE Streaming Support

Provides Server-Sent Events (SSE) streaming for real-time event subscriptions
instead of polling. This enables high-performance multi-agent coordination.
"""

import json
import threading
import time
from dataclasses import dataclass
from enum import Enum
from queue import Empty, Queue
from typing import Any, Callable, Generator, Iterator, Optional

import httpx


class SSEEventType(str, Enum):
    """Types of events that can be received via SSE."""

    CONNECTED = "connected"
    STATE_CHANGED = "STATE_CHANGED"
    STATUS_CHANGED = "STATUS_CHANGED"
    AGENT_ASSIGNED = "AGENT_ASSIGNED"
    INTENT_ASSIGNED = "INTENT_ASSIGNED"
    INTENT_COMPLETED = "INTENT_COMPLETED"
    INTENT_FAILED = "INTENT_FAILED"
    LEASE_ACQUIRED = "LEASE_ACQUIRED"
    LEASE_RELEASED = "LEASE_RELEASED"
    PORTFOLIO_PROGRESS = "PORTFOLIO_PROGRESS"
    ESCALATION_REQUIRED = "ESCALATION_REQUIRED"
    ERROR = "error"
    KEEPALIVE = "keepalive"


@dataclass
class SSEEvent:
    """An event received from the SSE stream."""

    type: str
    data: dict[str, Any]
    id: Optional[str] = None
    retry: Optional[int] = None

    @classmethod
    def from_raw(
        cls, event_type: str, data_str: str, event_id: Optional[str] = None
    ) -> "SSEEvent":
        """Create an SSEEvent from raw SSE data."""
        try:
            data = json.loads(data_str) if data_str else {}
        except json.JSONDecodeError:
            data = {"raw": data_str}
        return cls(type=event_type, data=data, id=event_id)

    @property
    def intent_id(self) -> Optional[str]:
        """Get the intent ID from the event data if present."""
        return self.data.get("intent_id")

    @property
    def portfolio_id(self) -> Optional[str]:
        """Get the portfolio ID from the event data if present."""
        return self.data.get("portfolio_id")

    @property
    def agent_id(self) -> Optional[str]:
        """Get the agent ID from the event data if present."""
        return self.data.get("agent_id")


class SSEStream:
    """
    A streaming SSE connection that yields events as they arrive.

    Usage:
        ```python
        stream = SSEStream(url, headers)
        for event in stream:
            if event.type == "STATE_CHANGED":
                handle_state_change(event.data)
        ```
    """

    def __init__(
        self,
        url: str,
        headers: dict[str, str],
        timeout: float = 60.0,
        reconnect_delay: float = 5.0,
        max_reconnects: int = 10,
    ):
        self.url = url
        self.headers = headers
        self.timeout = timeout
        self.reconnect_delay = reconnect_delay
        self.max_reconnects = max_reconnects
        self._running = False
        self._client: Optional[httpx.Client] = None
        self._response: Optional[httpx.Response] = None
        self._reconnect_count = 0
        self._last_event_id: Optional[str] = None

    def __iter__(self) -> Iterator[SSEEvent]:
        """Iterate over events from the stream."""
        self._running = True
        self._reconnect_count = 0

        while self._running and self._reconnect_count <= self.max_reconnects:
            try:
                yield from self._connect_and_stream()
            except (
                httpx.ReadTimeout,
                httpx.ConnectError,
                httpx.RemoteProtocolError,
            ) as e:
                if not self._running:
                    break
                self._reconnect_count += 1
                if self._reconnect_count > self.max_reconnects:
                    yield SSEEvent(
                        type=SSEEventType.ERROR,
                        data={"error": f"Max reconnects exceeded: {e}"},
                    )
                    break
                time.sleep(self.reconnect_delay)
            finally:
                self._cleanup()

    def _connect_and_stream(self) -> Generator[SSEEvent, None, None]:
        """Connect to SSE endpoint and yield events."""
        headers = dict(self.headers)
        headers["Accept"] = "text/event-stream"
        headers["Cache-Control"] = "no-cache"
        if self._last_event_id:
            headers["Last-Event-ID"] = self._last_event_id

        self._client = httpx.Client(timeout=None)

        with self._client.stream("GET", self.url, headers=headers) as response:
            if response.status_code != 200:
                yield SSEEvent(
                    type=SSEEventType.ERROR,
                    data={
                        "error": f"HTTP {response.status_code}",
                        "status_code": response.status_code,
                    },
                )
                return

            self._response = response
            self._reconnect_count = 0

            event_type = "message"
            event_data = ""
            event_id: Optional[str] = None

            for line in response.iter_lines():
                if not self._running:
                    break

                line = line.strip()

                if line.startswith(":"):
                    continue

                if not line:
                    if event_data:
                        event = SSEEvent.from_raw(event_type, event_data.strip(), event_id)
                        if event_id:
                            self._last_event_id = event_id
                        yield event
                    event_type = "message"
                    event_data = ""
                    event_id = None
                    continue

                if ":" in line:
                    field, _, value = line.partition(":")
                    value = value.lstrip(" ")
                else:
                    field = line
                    value = ""

                if field == "event":
                    event_type = value
                elif field == "data":
                    event_data += value + "\n"
                elif field == "id":
                    event_id = value
                elif field == "retry":
                    try:
                        self.reconnect_delay = int(value) / 1000
                    except ValueError:
                        pass

    def _cleanup(self) -> None:
        """Clean up resources."""
        if self._response:
            try:
                self._response.close()
            except Exception:
                pass
            self._response = None
        if self._client:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None

    def stop(self) -> None:
        """Stop the stream."""
        self._running = False
        self._cleanup()

    def __enter__(self) -> "SSEStream":
        return self

    def __exit__(self, *args: Any) -> None:
        self.stop()


class SSESubscription:
    """
    A managed subscription that processes events in the background.

    Usage:
        ```python
        def on_event(event):
            print(f"Got event: {event.type}")

        sub = SSESubscription(url, headers, on_event)
        sub.start()
        # ... do other work ...
        sub.stop()
        ```
    """

    def __init__(
        self,
        url: str,
        headers: dict[str, str],
        callback: Callable[[SSEEvent], None],
        error_callback: Optional[Callable[[Exception], None]] = None,
    ):
        self.url = url
        self.headers = headers
        self.callback = callback
        self.error_callback = error_callback
        self._stream: Optional[SSEStream] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False

    def start(self) -> None:
        """Start the subscription in a background thread."""
        if self._running:
            return

        self._running = True
        self._stream = SSEStream(self.url, self.headers)
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        """Background thread that processes events."""
        try:
            if self._stream:
                for event in self._stream:
                    if not self._running:
                        break
                    try:
                        self.callback(event)
                    except Exception as e:
                        if self.error_callback:
                            self.error_callback(e)
        except Exception as e:
            if self.error_callback:
                self.error_callback(e)

    def stop(self) -> None:
        """Stop the subscription."""
        self._running = False
        if self._stream:
            self._stream.stop()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)

    def __enter__(self) -> "SSESubscription":
        self.start()
        return self

    def __exit__(self, *args: Any) -> None:
        self.stop()


class EventQueue:
    """
    A queue-based subscription for event-driven processing.

    Usage:
        ```python
        with EventQueue(url, headers) as queue:
            while True:
                event = queue.get(timeout=10)
                if event:
                    process(event)
        ```
    """

    def __init__(self, url: str, headers: dict[str, str], maxsize: int = 100):
        self.url = url
        self.headers = headers
        self._queue: Queue[SSEEvent] = Queue(maxsize=maxsize)
        self._subscription: Optional[SSESubscription] = None

    def start(self) -> None:
        """Start the subscription."""
        self._subscription = SSESubscription(
            self.url,
            self.headers,
            callback=self._on_event,
            error_callback=self._on_error,
        )
        self._subscription.start()

    def _on_event(self, event: SSEEvent) -> None:
        """Handle incoming events."""
        try:
            self._queue.put_nowait(event)
        except Exception:
            pass

    def _on_error(self, error: Exception) -> None:
        """Handle errors."""
        self._queue.put(SSEEvent(type=SSEEventType.ERROR, data={"error": str(error)}))

    def get(self, timeout: Optional[float] = None) -> Optional[SSEEvent]:
        """Get the next event from the queue."""
        try:
            return self._queue.get(timeout=timeout)
        except Empty:
            return None

    def stop(self) -> None:
        """Stop the subscription."""
        if self._subscription:
            self._subscription.stop()

    def __enter__(self) -> "EventQueue":
        self.start()
        return self

    def __exit__(self, *args: Any) -> None:
        self.stop()
