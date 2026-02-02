"""Tests for provider adapters."""

from unittest.mock import MagicMock, patch

import pytest

from openintent.adapters import (
    AdapterConfig,
    AnthropicAdapter,
    BaseAdapter,
    OpenAIAdapter,
)


class TestAdapterConfig:
    """Tests for AdapterConfig."""

    def test_default_values(self):
        """Test default configuration values."""
        config = AdapterConfig()
        assert config.log_requests is True
        assert config.log_tool_calls is True
        assert config.log_streams is True
        assert config.log_stream_chunks is False
        assert config.chunk_log_interval == 10
        assert config.on_error is None
        assert config.metadata == {}

    def test_custom_values(self):
        """Test custom configuration values."""
        error_handler = MagicMock()
        config = AdapterConfig(
            log_requests=False,
            log_tool_calls=False,
            log_streams=False,
            log_stream_chunks=True,
            chunk_log_interval=5,
            on_error=error_handler,
            metadata={"custom": "value"},
        )
        assert config.log_requests is False
        assert config.log_tool_calls is False
        assert config.log_streams is False
        assert config.log_stream_chunks is True
        assert config.chunk_log_interval == 5
        assert config.on_error is error_handler
        assert config.metadata == {"custom": "value"}


class TestBaseAdapter:
    """Tests for BaseAdapter."""

    def test_initialization(self):
        """Test base adapter initialization."""
        mock_client = MagicMock()
        adapter = BaseAdapter(mock_client, intent_id="test-intent")

        assert adapter.client is mock_client
        assert adapter.intent_id == "test-intent"
        assert isinstance(adapter.config, AdapterConfig)

    def test_initialization_with_config(self):
        """Test base adapter with custom config."""
        mock_client = MagicMock()
        config = AdapterConfig(log_requests=False)
        adapter = BaseAdapter(mock_client, intent_id="test-intent", config=config)

        assert adapter.config.log_requests is False

    def test_generate_id(self):
        """Test ID generation."""
        mock_client = MagicMock()
        adapter = BaseAdapter(mock_client, intent_id="test-intent")

        id1 = adapter._generate_id()
        id2 = adapter._generate_id()

        assert isinstance(id1, str)
        assert len(id1) == 36
        assert id1 != id2

    def test_handle_error_with_callback(self):
        """Test error handling with callback."""
        mock_client = MagicMock()
        error_handler = MagicMock()
        config = AdapterConfig(on_error=error_handler)
        adapter = BaseAdapter(mock_client, intent_id="test-intent", config=config)

        error = ValueError("test error")
        context = {"phase": "test"}
        adapter._handle_error(error, context)

        error_handler.assert_called_once_with(error, context)

    def test_handle_error_without_callback(self):
        """Test error handling without callback (should not raise)."""
        mock_client = MagicMock()
        adapter = BaseAdapter(mock_client, intent_id="test-intent")

        error = ValueError("test error")
        adapter._handle_error(error, {"phase": "test"})

    def test_handle_error_callback_exception(self):
        """Test that callback exceptions are silently caught."""
        mock_client = MagicMock()
        error_handler = MagicMock(side_effect=RuntimeError("callback error"))
        config = AdapterConfig(on_error=error_handler)
        adapter = BaseAdapter(mock_client, intent_id="test-intent", config=config)

        adapter._handle_error(ValueError("test"), {})


class TestOpenAIAdapter:
    """Tests for OpenAIAdapter."""

    @patch("openintent.adapters.openai_adapter._check_openai_installed")
    def test_initialization(self, mock_check):
        """Test OpenAI adapter initialization."""
        mock_openai = MagicMock()
        mock_client = MagicMock()

        adapter = OpenAIAdapter(mock_openai, mock_client, intent_id="test-intent")

        assert adapter.openai is mock_openai
        assert adapter.client is mock_client
        assert adapter.intent_id == "test-intent"
        assert hasattr(adapter, "chat")
        assert hasattr(adapter.chat, "completions")
        mock_check.assert_called_once()

    @patch("openintent.adapters.openai_adapter._check_openai_installed")
    def test_create_completion_logs_request(self, mock_check):
        """Test that completion logs request events."""
        mock_openai = MagicMock()
        mock_client = MagicMock()

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message = MagicMock()
        mock_response.choices[0].message.content = "Hello!"
        mock_response.choices[0].message.tool_calls = None
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.usage.total_tokens = 15

        mock_openai.chat.completions.create.return_value = mock_response

        adapter = OpenAIAdapter(mock_openai, mock_client, intent_id="test-intent")
        response = adapter.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": "Hello"}],
        )

        assert response is mock_response
        mock_client.log_llm_request_started.assert_called_once()
        mock_client.log_llm_request_completed.assert_called_once()

    @patch("openintent.adapters.openai_adapter._check_openai_installed")
    def test_create_completion_with_tools(self, mock_check):
        """Test completion with tool calls."""
        mock_openai = MagicMock()
        mock_client = MagicMock()

        mock_tool_call = MagicMock()
        mock_tool_call.id = "call_123"
        mock_tool_call.function = MagicMock()
        mock_tool_call.function.name = "get_weather"
        mock_tool_call.function.arguments = '{"location": "NYC"}'

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message = MagicMock()
        mock_response.choices[0].message.content = None
        mock_response.choices[0].message.tool_calls = [mock_tool_call]
        mock_response.choices[0].finish_reason = "tool_calls"
        mock_response.usage = None

        mock_openai.chat.completions.create.return_value = mock_response

        adapter = OpenAIAdapter(mock_openai, mock_client, intent_id="test-intent")
        adapter.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": "What's the weather?"}],
            tools=[{"type": "function", "function": {"name": "get_weather"}}],
        )

        mock_client.log_tool_call_started.assert_called()

    @patch("openintent.adapters.openai_adapter._check_openai_installed")
    def test_create_completion_failure(self, mock_check):
        """Test that failures are logged."""
        mock_openai = MagicMock()
        mock_client = MagicMock()

        mock_openai.chat.completions.create.side_effect = RuntimeError("API Error")

        adapter = OpenAIAdapter(mock_openai, mock_client, intent_id="test-intent")

        with pytest.raises(RuntimeError):
            adapter.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": "Hello"}],
            )

        mock_client.log_llm_request_started.assert_called_once()
        mock_client.log_llm_request_failed.assert_called_once()

    @patch("openintent.adapters.openai_adapter._check_openai_installed")
    def test_config_disables_logging(self, mock_check):
        """Test that config can disable logging."""
        mock_openai = MagicMock()
        mock_client = MagicMock()

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message = MagicMock()
        mock_response.choices[0].message.content = "Hello!"
        mock_response.choices[0].message.tool_calls = None
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage = None

        mock_openai.chat.completions.create.return_value = mock_response

        config = AdapterConfig(log_requests=False, log_tool_calls=False)
        adapter = OpenAIAdapter(
            mock_openai, mock_client, intent_id="test-intent", config=config
        )
        adapter.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": "Hello"}],
        )

        mock_client.log_llm_request_started.assert_not_called()
        mock_client.log_llm_request_completed.assert_not_called()


class TestAnthropicAdapter:
    """Tests for AnthropicAdapter."""

    @patch("openintent.adapters.anthropic_adapter._check_anthropic_installed")
    def test_initialization(self, mock_check):
        """Test Anthropic adapter initialization."""
        mock_anthropic = MagicMock()
        mock_client = MagicMock()

        adapter = AnthropicAdapter(mock_anthropic, mock_client, intent_id="test-intent")

        assert adapter.anthropic is mock_anthropic
        assert adapter.client is mock_client
        assert adapter.intent_id == "test-intent"
        assert hasattr(adapter, "messages")

    @patch("openintent.adapters.anthropic_adapter._check_anthropic_installed")
    def test_create_message_logs_request(self, mock_check):
        """Test that message creation logs request events."""
        mock_anthropic = MagicMock()
        mock_client = MagicMock()

        mock_content = MagicMock()
        mock_content.type = "text"
        mock_content.text = "Hello!"

        mock_response = MagicMock()
        mock_response.content = [mock_content]
        mock_response.stop_reason = "end_turn"
        mock_response.usage = MagicMock()
        mock_response.usage.input_tokens = 10
        mock_response.usage.output_tokens = 5

        mock_anthropic.messages.create.return_value = mock_response

        adapter = AnthropicAdapter(mock_anthropic, mock_client, intent_id="test-intent")
        response = adapter.messages.create(
            model="claude-3-opus-20240229",
            max_tokens=1024,
            messages=[{"role": "user", "content": "Hello"}],
        )

        assert response is mock_response
        mock_client.log_llm_request_started.assert_called_once()
        mock_client.log_llm_request_completed.assert_called_once()

    @patch("openintent.adapters.anthropic_adapter._check_anthropic_installed")
    def test_create_message_with_tool_use(self, mock_check):
        """Test message with tool use blocks."""
        mock_anthropic = MagicMock()
        mock_client = MagicMock()

        mock_tool_use = MagicMock()
        mock_tool_use.type = "tool_use"
        mock_tool_use.id = "toolu_123"
        mock_tool_use.name = "get_weather"
        mock_tool_use.input = {"location": "NYC"}

        mock_response = MagicMock()
        mock_response.content = [mock_tool_use]
        mock_response.stop_reason = "tool_use"
        mock_response.usage = None

        mock_anthropic.messages.create.return_value = mock_response

        adapter = AnthropicAdapter(mock_anthropic, mock_client, intent_id="test-intent")
        adapter.messages.create(
            model="claude-3-opus-20240229",
            max_tokens=1024,
            messages=[{"role": "user", "content": "What's the weather?"}],
            tools=[{"name": "get_weather"}],
        )

        mock_client.log_tool_call_started.assert_called()

    @patch("openintent.adapters.anthropic_adapter._check_anthropic_installed")
    def test_create_message_failure(self, mock_check):
        """Test that failures are logged."""
        mock_anthropic = MagicMock()
        mock_client = MagicMock()

        mock_anthropic.messages.create.side_effect = RuntimeError("API Error")

        adapter = AnthropicAdapter(mock_anthropic, mock_client, intent_id="test-intent")

        with pytest.raises(RuntimeError):
            adapter.messages.create(
                model="claude-3-opus-20240229",
                max_tokens=1024,
                messages=[{"role": "user", "content": "Hello"}],
            )

        mock_client.log_llm_request_started.assert_called_once()
        mock_client.log_llm_request_failed.assert_called_once()

    @patch("openintent.adapters.anthropic_adapter._check_anthropic_installed")
    def test_config_disables_logging(self, mock_check):
        """Test that config can disable logging."""
        mock_anthropic = MagicMock()
        mock_client = MagicMock()

        mock_content = MagicMock()
        mock_content.type = "text"
        mock_content.text = "Hello!"

        mock_response = MagicMock()
        mock_response.content = [mock_content]
        mock_response.stop_reason = "end_turn"
        mock_response.usage = None

        mock_anthropic.messages.create.return_value = mock_response

        config = AdapterConfig(log_requests=False, log_tool_calls=False)
        adapter = AnthropicAdapter(
            mock_anthropic, mock_client, intent_id="test-intent", config=config
        )
        adapter.messages.create(
            model="claude-3-opus-20240229",
            max_tokens=1024,
            messages=[{"role": "user", "content": "Hello"}],
        )

        mock_client.log_llm_request_started.assert_not_called()
        mock_client.log_llm_request_completed.assert_not_called()
