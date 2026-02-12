"""
Unit tests for the OpenIntent LLM-powered agent engine.

Tests the LLM integration layer: model= parameter on @Agent/@Coordinator,
context assembly, protocol tool execution, agentic tool loop, streaming,
and human-in-the-loop flows.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from openintent.agents import (
    Agent,
    AgentConfig,
    Coordinator,
    on_assignment,
)
from openintent.llm import (
    PROTOCOL_TOOLS_AGENT,
    PROTOCOL_TOOLS_COORDINATOR,
    ContextAssembler,
    LLMConfig,
    LLMEngine,
    ProtocolToolExecutor,
    Tool,
    ToolDef,
    _resolve_provider,
    _tools_to_anthropic_format,
    _tools_to_openai_format,
    define_tool,
    tool,
)
from openintent.models import Intent, IntentState, IntentStatus

# ---------------------------------------------------------------------------
# Provider Resolution
# ---------------------------------------------------------------------------


class TestProviderResolution:
    def test_openai_default(self):
        assert _resolve_provider("gpt-4o") == "openai"
        assert _resolve_provider("gpt-3.5-turbo") == "openai"

    def test_anthropic(self):
        assert _resolve_provider("claude-sonnet-4-20250514") == "anthropic"
        assert _resolve_provider("claude-3-opus") == "anthropic"

    def test_gemini(self):
        assert _resolve_provider("gemini-pro") == "gemini"
        assert _resolve_provider("gemini-1.5-flash") == "gemini"

    def test_grok(self):
        assert _resolve_provider("grok-2") == "grok"

    def test_deepseek(self):
        assert _resolve_provider("deepseek-chat") == "deepseek"

    def test_openrouter(self):
        assert _resolve_provider("meta-llama/llama-3-70b") == "openrouter"

    def test_unknown_defaults_to_openai(self):
        assert _resolve_provider("some-model") == "openai"


# ---------------------------------------------------------------------------
# LLMConfig
# ---------------------------------------------------------------------------


class TestLLMConfig:
    def test_defaults(self):
        config = LLMConfig()
        assert config.model == ""
        assert config.provider == "openai"
        assert config.temperature == 0.7
        assert config.max_tokens == 4096
        assert config.max_tool_rounds == 10
        assert config.auto_memory is True
        assert config.planning is False
        assert config.stream_by_default is False

    def test_custom_values(self):
        config = LLMConfig(
            model="gpt-4o",
            provider="openai",
            temperature=0.3,
            max_tokens=8192,
            planning=True,
            stream_by_default=True,
        )
        assert config.model == "gpt-4o"
        assert config.temperature == 0.3
        assert config.max_tokens == 8192
        assert config.planning is True
        assert config.stream_by_default is True


# ---------------------------------------------------------------------------
# Tool Format Conversion
# ---------------------------------------------------------------------------


class TestToolFormatConversion:
    def test_openai_format(self):
        tools = [PROTOCOL_TOOLS_AGENT[0]]
        result = _tools_to_openai_format(tools)
        assert len(result) == 1
        assert result[0]["type"] == "function"
        assert result[0]["function"]["name"] == "remember"
        assert "parameters" in result[0]["function"]

    def test_anthropic_format(self):
        tools = [PROTOCOL_TOOLS_AGENT[0]]
        result = _tools_to_anthropic_format(tools)
        assert len(result) == 1
        assert result[0]["name"] == "remember"
        assert "input_schema" in result[0]

    def test_all_agent_tools_convert(self):
        openai_tools = _tools_to_openai_format(PROTOCOL_TOOLS_AGENT)
        assert len(openai_tools) == len(PROTOCOL_TOOLS_AGENT)
        for t in openai_tools:
            assert t["type"] == "function"
            assert "name" in t["function"]

    def test_coordinator_has_more_tools(self):
        assert len(PROTOCOL_TOOLS_COORDINATOR) > len(PROTOCOL_TOOLS_AGENT)
        coordinator_names = {t["name"] for t in PROTOCOL_TOOLS_COORDINATOR}
        assert "delegate" in coordinator_names
        assert "create_plan" in coordinator_names
        assert "record_decision" in coordinator_names


# ---------------------------------------------------------------------------
# Protocol Tool Definitions
# ---------------------------------------------------------------------------


class TestProtocolToolDefinitions:
    def test_agent_tools_complete(self):
        names = {t["name"] for t in PROTOCOL_TOOLS_AGENT}
        assert "remember" in names
        assert "recall" in names
        assert "update_status" in names
        assert "clarify" in names
        assert "escalate" in names

    def test_coordinator_tools_include_agent_tools(self):
        agent_names = {t["name"] for t in PROTOCOL_TOOLS_AGENT}
        coord_names = {t["name"] for t in PROTOCOL_TOOLS_COORDINATOR}
        assert agent_names.issubset(coord_names)

    def test_tool_schemas_valid(self):
        for t in PROTOCOL_TOOLS_COORDINATOR:
            assert "name" in t
            assert "description" in t
            assert "parameters" in t
            params = t["parameters"]
            assert params["type"] == "object"
            assert "properties" in params
            assert "required" in params


# ---------------------------------------------------------------------------
# Context Assembler
# ---------------------------------------------------------------------------


class TestContextAssembler:
    def test_system_prompt_agent(self):
        prompt = ContextAssembler.build_system_prompt(
            agent_id="test-agent",
            custom_prompt="You are a test agent.",
            role="agent",
            available_tools=PROTOCOL_TOOLS_AGENT,
        )
        assert "test-agent" in prompt
        assert "You are a test agent." in prompt
        assert "agent" in prompt
        assert "remember" in prompt
        assert "recall" in prompt

    def test_system_prompt_coordinator(self):
        prompt = ContextAssembler.build_system_prompt(
            agent_id="test-coord",
            custom_prompt="You coordinate work.",
            role="coordinator",
            available_tools=PROTOCOL_TOOLS_COORDINATOR,
            managed_agents=["agent-a", "agent-b"],
        )
        assert "test-coord" in prompt
        assert "coordinator" in prompt
        assert "agent-a" in prompt
        assert "agent-b" in prompt
        assert "delegate" in prompt

    def test_system_prompt_with_planning(self):
        prompt = ContextAssembler.build_system_prompt(
            agent_id="planner",
            custom_prompt=None,
            role="agent",
            available_tools=[],
            planning_enabled=True,
        )
        assert "Planning is enabled" in prompt

    @pytest.mark.asyncio
    async def test_context_messages_with_intent(self):
        intent = Intent(
            id="test-123",
            title="Test Intent",
            description="A test task",
            version=1,
            status=IntentStatus.ACTIVE,
            state=IntentState(data={"progress": 50}),
        )

        agent = MagicMock()
        agent._config = AgentConfig(memory="episodic")
        agent.memory = MagicMock()
        agent.memory.recall = AsyncMock(return_value=[])

        messages = await ContextAssembler.build_context_messages(
            agent,
            intent=intent,
            task_description="Analyze this data",
        )

        assert len(messages) >= 1
        context_msg = messages[0]
        assert "Test Intent" in context_msg["content"]
        assert "A test task" in context_msg["content"]

        task_msg = messages[-1]
        assert task_msg["content"] == "Analyze this data"

    @pytest.mark.asyncio
    async def test_context_messages_with_conversation_history(self):
        agent = MagicMock()
        agent._config = AgentConfig()

        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]

        messages = await ContextAssembler.build_context_messages(
            agent,
            task_description="Continue our conversation",
            conversation_history=history,
        )

        assert any(m["content"] == "Hello" for m in messages)
        assert any(m["content"] == "Hi there" for m in messages)


# ---------------------------------------------------------------------------
# Protocol Tool Executor
# ---------------------------------------------------------------------------


class TestProtocolToolExecutor:
    @pytest.mark.asyncio
    async def test_remember(self):
        agent = MagicMock()
        agent.memory = MagicMock()
        agent.memory.store = AsyncMock(return_value=None)

        executor = ProtocolToolExecutor(agent)
        result = await executor.execute("remember", {"key": "test", "value": "data"})
        assert result["status"] == "stored"
        agent.memory.store.assert_called_once()

    @pytest.mark.asyncio
    async def test_recall(self):
        agent = MagicMock()
        agent.memory = MagicMock()
        agent.memory.recall = AsyncMock(return_value=[{"key": "k", "value": "v"}])

        executor = ProtocolToolExecutor(agent)
        result = await executor.execute("recall", {"query": "test"})
        assert "memories" in result

    @pytest.mark.asyncio
    async def test_update_status(self):
        agent = MagicMock()
        agent.patch_state = AsyncMock(return_value=None)

        intent = Intent(
            id="int-1",
            title="T",
            description="D",
            version=1,
            status=IntentStatus.ACTIVE,
            state=IntentState(),
        )

        executor = ProtocolToolExecutor(agent, intent=intent)
        result = await executor.execute("update_status", {"updates": {"progress": 75}})
        assert result["status"] == "updated"
        agent.patch_state.assert_called_once_with("int-1", {"progress": 75})

    @pytest.mark.asyncio
    async def test_clarify(self):
        agent = MagicMock()
        agent._agent_id = "agent-1"
        agent.async_client = MagicMock()
        agent.async_client.request_arbitration = AsyncMock(return_value=None)

        intent = Intent(
            id="int-1",
            title="T",
            description="D",
            version=1,
            status=IntentStatus.ACTIVE,
            state=IntentState(),
        )

        executor = ProtocolToolExecutor(agent, intent=intent)
        result = await executor.execute("clarify", {"question": "What format?"})
        assert result["status"] == "awaiting_response"
        assert result["question"] == "What format?"

    @pytest.mark.asyncio
    async def test_escalate(self):
        agent = MagicMock()
        agent.escalate = AsyncMock(return_value=None)

        intent = Intent(
            id="int-1",
            title="T",
            description="D",
            version=1,
            status=IntentStatus.ACTIVE,
            state=IntentState(),
        )

        executor = ProtocolToolExecutor(agent, intent=intent)
        result = await executor.execute("escalate", {"reason": "Too complex"})
        assert result["status"] == "escalated"

    @pytest.mark.asyncio
    async def test_delegate(self):
        agent = MagicMock()
        agent.delegate = AsyncMock(return_value=None)
        agent.record_decision = AsyncMock(return_value={})

        intent = Intent(
            id="int-1",
            title="T",
            description="D",
            version=1,
            status=IntentStatus.ACTIVE,
            state=IntentState(),
        )

        executor = ProtocolToolExecutor(agent, intent=intent)
        result = await executor.execute(
            "delegate",
            {
                "agent_id": "helper",
                "task_description": "Do this",
            },
        )
        assert result["status"] == "delegated"
        agent.delegate.assert_called_once()

    @pytest.mark.asyncio
    async def test_record_decision(self):
        agent = MagicMock()
        agent.record_decision = AsyncMock(return_value={"type": "task_assigned"})

        executor = ProtocolToolExecutor(agent)
        result = await executor.execute(
            "record_decision",
            {
                "decision_type": "task_assigned",
                "summary": "Assigned to helper",
            },
        )
        assert result["status"] == "recorded"

    @pytest.mark.asyncio
    async def test_unknown_tool(self):
        agent = MagicMock()
        executor = ProtocolToolExecutor(agent)
        result = await executor.execute("nonexistent_tool", {})
        assert "error" in result

    @pytest.mark.asyncio
    async def test_update_status_no_intent(self):
        agent = MagicMock()
        executor = ProtocolToolExecutor(agent, intent=None)
        result = await executor.execute("update_status", {"updates": {"x": 1}})
        assert "error" in result


# ---------------------------------------------------------------------------
# LLM Engine — Response Parsing
# ---------------------------------------------------------------------------


class TestLLMEngineResponseParsing:
    def _make_engine(self):
        agent = MagicMock()
        agent._agent_id = "test"
        agent._config = AgentConfig()
        config = LLMConfig(model="gpt-4o", provider="openai")
        return LLMEngine(agent, config)

    def test_extract_content_openai(self):
        engine = self._make_engine()
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = "Hello world"
        assert engine._extract_content(response) == "Hello world"

    def test_extract_content_dict(self):
        engine = self._make_engine()
        response = {"choices": [{"message": {"content": "From dict"}}]}
        assert engine._extract_content(response) == "From dict"

    def test_extract_content_anthropic(self):
        engine = self._make_engine()
        engine._provider = "anthropic"
        block = MagicMock()
        block.type = "text"
        block.text = "Anthropic response"
        response = MagicMock()
        response.choices = None
        del response.choices
        response.content = [block]
        assert engine._extract_content(response) == "Anthropic response"

    def test_extract_content_string(self):
        engine = self._make_engine()
        assert engine._extract_content("raw string") == "raw string"

    def test_extract_tool_calls_openai(self):
        engine = self._make_engine()
        tc = MagicMock()
        tc.id = "call_123"
        tc.function.name = "remember"
        tc.function.arguments = '{"key": "test", "value": "data"}'

        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.tool_calls = [tc]

        calls = engine._extract_tool_calls(response)
        assert len(calls) == 1
        assert calls[0]["name"] == "remember"
        assert calls[0]["id"] == "call_123"

    def test_extract_tool_calls_none(self):
        engine = self._make_engine()
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.tool_calls = None
        response.choices[0].message.content = "No tools needed"
        calls = engine._extract_tool_calls(response)
        assert len(calls) == 0

    def test_extract_tool_calls_anthropic(self):
        engine = self._make_engine()
        engine._provider = "anthropic"
        block = MagicMock()
        block.type = "tool_use"
        block.id = "tu_456"
        block.name = "escalate"
        block.input = {"reason": "too complex"}

        response = MagicMock()
        del response.choices
        response.content = [block]

        calls = engine._extract_tool_calls(response)
        assert len(calls) == 1
        assert calls[0]["name"] == "escalate"

    def test_extract_tool_calls_dict_openai(self):
        engine = self._make_engine()
        response = {
            "choices": [
                {
                    "message": {
                        "content": "",
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "function": {
                                    "name": "recall",
                                    "arguments": '{"query": "test"}',
                                },
                            }
                        ],
                    }
                }
            ]
        }
        calls = engine._extract_tool_calls(response)
        assert len(calls) == 1
        assert calls[0]["name"] == "recall"


# ---------------------------------------------------------------------------
# LLM Engine — Message Building
# ---------------------------------------------------------------------------


class TestLLMEngineMessageBuilding:
    def _make_engine(self, provider="openai"):
        agent = MagicMock()
        agent._agent_id = "test"
        agent._config = AgentConfig()
        config = LLMConfig(model="gpt-4o", provider=provider)
        return LLMEngine(agent, config)

    def test_build_tool_result_openai(self):
        engine = self._make_engine("openai")
        tc = {"id": "call_1", "name": "remember", "arguments": "{}"}
        result = {"status": "stored"}
        msg = engine._build_tool_result_message(tc, result)
        assert msg["role"] == "tool"
        assert msg["tool_call_id"] == "call_1"
        assert "stored" in msg["content"]

    def test_build_tool_result_anthropic(self):
        engine = self._make_engine("anthropic")
        tc = {"id": "tu_1", "name": "recall", "arguments": "{}"}
        result = {"memories": []}
        msg = engine._build_tool_result_message(tc, result)
        assert msg["role"] == "user"
        assert isinstance(msg["content"], list)
        assert msg["content"][0]["type"] == "tool_result"
        assert msg["content"][0]["tool_use_id"] == "tu_1"


# ---------------------------------------------------------------------------
# LLM Engine — Tool Loop
# ---------------------------------------------------------------------------


class TestLLMEngineToolLoop:
    def _make_engine_with_mock(self):
        agent = MagicMock()
        agent._agent_id = "test"
        agent._config = AgentConfig(memory="episodic")
        agent.memory = MagicMock()
        agent.memory.recall = AsyncMock(return_value=[])
        agent.memory.store = AsyncMock(return_value=None)
        agent._agents_list = None

        config = LLMConfig(model="gpt-4o", provider="openai")
        engine = LLMEngine(agent, config)
        return engine, agent

    @pytest.mark.asyncio
    async def test_think_no_tools(self):
        engine, agent = self._make_engine_with_mock()

        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = "The answer is 42."
        response.choices[0].message.tool_calls = None

        with patch.object(engine, "_call_llm", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = response
            result = await engine._think_complete("What is the answer?")

        assert result == "The answer is 42."

    @pytest.mark.asyncio
    async def test_think_with_tool_call(self):
        engine, agent = self._make_engine_with_mock()

        tc = MagicMock()
        tc.id = "call_1"
        tc.function.name = "remember"
        tc.function.arguments = '{"key": "finding", "value": "important data"}'
        first_response = MagicMock()
        first_response.choices = [MagicMock()]
        first_response.choices[0].message.content = ""
        first_response.choices[0].message.tool_calls = [tc]

        second_response = MagicMock()
        second_response.choices = [MagicMock()]
        second_response.choices[0].message.content = "Done. I stored the finding."
        second_response.choices[0].message.tool_calls = None

        with patch.object(engine, "_call_llm", new_callable=AsyncMock) as mock_call:
            mock_call.side_effect = [first_response, second_response]
            result = await engine._think_complete("Process this data")

        assert result == "Done. I stored the finding."
        assert mock_call.call_count == 2
        agent.memory.store.assert_called_once()

    @pytest.mark.asyncio
    async def test_think_clarify_pauses(self):
        engine, agent = self._make_engine_with_mock()
        agent.async_client = MagicMock()
        agent.async_client.request_arbitration = AsyncMock(return_value=None)

        intent = Intent(
            id="int-1",
            title="T",
            description="D",
            version=1,
            status=IntentStatus.ACTIVE,
            state=IntentState(),
        )

        tc = MagicMock()
        tc.id = "call_1"
        tc.function.name = "clarify"
        tc.function.arguments = '{"question": "What format do you need?"}'
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = ""
        response.choices[0].message.tool_calls = [tc]

        with patch.object(engine, "_call_llm", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = response
            result = await engine._think_complete("Do something", intent=intent)

        parsed = json.loads(result)
        assert parsed["status"] == "awaiting_response"
        assert "What format" in parsed["question"]


# ---------------------------------------------------------------------------
# LLM Engine Properties
# ---------------------------------------------------------------------------


class TestLLMEngineProperties:
    def test_is_coordinator_false(self):
        agent = MagicMock(spec=[])
        config = LLMConfig(model="gpt-4o")
        engine = LLMEngine(agent, config)
        assert engine._is_coordinator is False

    def test_is_coordinator_true(self):
        agent = MagicMock()
        agent._agents_list = ["a", "b"]
        config = LLMConfig(model="gpt-4o")
        engine = LLMEngine(agent, config)
        assert engine._is_coordinator is True

    def test_protocol_tools_agent(self):
        agent = MagicMock(spec=[])
        config = LLMConfig(model="gpt-4o")
        engine = LLMEngine(agent, config)
        names = {t["name"] for t in engine._protocol_tools}
        assert "remember" in names
        assert "delegate" not in names

    def test_protocol_tools_coordinator(self):
        agent = MagicMock()
        agent._agents_list = ["a"]
        config = LLMConfig(model="gpt-4o")
        engine = LLMEngine(agent, config)
        names = {t["name"] for t in engine._protocol_tools}
        assert "delegate" in names
        assert "create_plan" in names

    def test_external_tools(self):
        agent = MagicMock()
        agent._config = AgentConfig(tools=["web_search", "code_exec"])
        config = LLMConfig(model="gpt-4o")
        engine = LLMEngine(agent, config)
        ext = engine._external_tools
        assert len(ext) == 2
        assert ext[0]["name"] == "web_search"

    def test_format_tools_openai(self):
        agent = MagicMock(spec=[])
        agent._config = AgentConfig()
        config = LLMConfig(model="gpt-4o", provider="openai")
        engine = LLMEngine(agent, config)
        formatted = engine._format_tools_for_provider()
        assert all(t["type"] == "function" for t in formatted)

    def test_format_tools_anthropic(self):
        agent = MagicMock(spec=[])
        agent._config = AgentConfig()
        config = LLMConfig(model="claude-sonnet-4-20250514", provider="anthropic")
        engine = LLMEngine(agent, config)
        formatted = engine._format_tools_for_provider()
        assert all("input_schema" in t for t in formatted)

    def test_reset_history(self):
        agent = MagicMock()
        config = LLMConfig(model="gpt-4o")
        engine = LLMEngine(agent, config)
        engine._conversation_history.append({"role": "user", "content": "hi"})
        engine.reset_history()
        assert len(engine._conversation_history) == 0


# ---------------------------------------------------------------------------
# @Agent decorator with model= parameter
# ---------------------------------------------------------------------------


class TestAgentWithModel:
    def test_agent_with_model_has_think(self):
        @Agent("test-bot", model="gpt-4o", memory="episodic")
        class TestBot:
            pass

        bot = TestBot()
        assert hasattr(bot, "think")
        assert hasattr(bot, "think_stream")
        assert hasattr(bot, "reset_conversation")
        assert hasattr(bot, "_llm_engine")
        assert hasattr(bot, "_llm_config")

    def test_agent_without_model_no_think(self):
        @Agent("manual-bot")
        class ManualBot:
            pass

        bot = ManualBot()
        assert not hasattr(bot, "think")
        assert not hasattr(bot, "_llm_engine")

    def test_agent_model_config(self):
        @Agent(
            "configured-bot",
            model="gpt-4o-mini",
            temperature=0.3,
            max_tokens=2048,
            system_prompt="You are a helper.",
        )
        class ConfigBot:
            pass

        bot = ConfigBot()
        assert bot._llm_config.model == "gpt-4o-mini"
        assert bot._llm_config.temperature == 0.3
        assert bot._llm_config.max_tokens == 2048
        assert bot._llm_config.system_prompt == "You are a helper."

    def test_agent_provider_auto_detected(self):
        @Agent("claude-bot", model="claude-sonnet-4-20250514")
        class ClaudeBot:
            pass

        bot = ClaudeBot()
        assert bot._llm_config.provider == "anthropic"

    def test_agent_with_model_keeps_base_features(self):
        @Agent("full-bot", model="gpt-4o", memory="episodic", tools=["search"])
        class FullBot:
            @on_assignment
            async def work(self, intent):
                pass

        bot = FullBot()
        assert hasattr(bot, "memory")
        assert hasattr(bot, "tools")
        assert hasattr(bot, "think")
        assert bot._agent_id == "full-bot"
        assert bot._config.memory == "episodic"
        assert bot._config.tools == ["search"]


# ---------------------------------------------------------------------------
# @Coordinator decorator with model= parameter
# ---------------------------------------------------------------------------


class TestCoordinatorWithModel:
    def test_coordinator_with_model_has_think(self):
        @Coordinator(
            "test-lead",
            model="gpt-4o",
            agents=["agent-a", "agent-b"],
        )
        class TestLead:
            pass

        lead = TestLead()
        assert hasattr(lead, "think")
        assert hasattr(lead, "think_stream")
        assert lead._agents_list == ["agent-a", "agent-b"]

    def test_coordinator_without_model_no_think(self):
        @Coordinator("manual-lead", agents=["a"])
        class ManualLead:
            pass

        lead = ManualLead()
        assert not hasattr(lead, "think")

    def test_coordinator_llm_engine_is_coordinator(self):
        @Coordinator(
            "llm-lead",
            model="claude-sonnet-4-20250514",
            agents=["researcher", "writer"],
        )
        class LLMLead:
            pass

        lead = LLMLead()
        assert lead._llm_engine._is_coordinator is True
        coord_tools = {t["name"] for t in lead._llm_engine._protocol_tools}
        assert "delegate" in coord_tools
        assert "create_plan" in coord_tools

    def test_coordinator_planning_default_true(self):
        @Coordinator("planner", model="gpt-4o", agents=["a"])
        class PlanCoord:
            pass

        coord = PlanCoord()
        assert coord._llm_config.planning is True

    def test_coordinator_keeps_governance_features(self):
        @Coordinator(
            "governed",
            model="gpt-4o",
            agents=["a", "b"],
            strategy="parallel",
        )
        class GovernedCoord:
            pass

        coord = GovernedCoord()
        assert hasattr(coord, "create_portfolio")
        assert hasattr(coord, "record_decision")
        assert hasattr(coord, "decisions")
        assert hasattr(coord, "think")


# ---------------------------------------------------------------------------
# Streaming
# ---------------------------------------------------------------------------


class TestStreaming:
    def test_stream_by_default_config(self):
        @Agent("stream-bot", model="gpt-4o", stream_by_default=True)
        class StreamBot:
            pass

        bot = StreamBot()
        assert bot._llm_config.stream_by_default is True

    @pytest.mark.asyncio
    async def test_think_stream_returns_async_iterator(self):
        @Agent("stream-test", model="gpt-4o")
        class StreamTest:
            pass

        bot = StreamTest()

        async def mock_think_stream(*args, **kwargs):
            async def _gen():
                for tok in ["Hello", " ", "world"]:
                    yield tok

            return _gen()

        with patch.object(bot._llm_engine, "think", new=mock_think_stream):
            result = await bot.think_stream("test")
            tokens = []
            async for token in result:
                tokens.append(token)
            assert tokens == ["Hello", " ", "world"]

    @pytest.mark.asyncio
    async def test_think_with_stream_flag(self):
        @Agent("stream-flag-test", model="gpt-4o")
        class StreamFlagTest:
            pass

        bot = StreamFlagTest()

        async def mock_think(prompt, intent=None, stream=None, on_token=None, **kw):
            if stream:

                async def _gen():
                    for tok in ["A", "B"]:
                        yield tok

                return _gen()
            return "not streaming"

        with patch.object(bot._llm_engine, "think", new=mock_think):
            result = await bot.think("test", stream=True)
            tokens = []
            async for token in result:
                tokens.append(token)
            assert tokens == ["A", "B"]

            result2 = await bot.think("test", stream=False)
            assert result2 == "not streaming"


# ---------------------------------------------------------------------------
# Tool Dataclass & @tool Decorator
# ---------------------------------------------------------------------------


class TestToolDefinition:
    def test_tool_dataclass_basic(self):
        t = ToolDef(
            name="calculator",
            description="Perform arithmetic.",
            parameters={
                "type": "object",
                "properties": {
                    "expression": {"type": "string", "description": "Math expression."},
                },
                "required": ["expression"],
            },
        )
        assert t.name == "calculator"
        assert t.description == "Perform arithmetic."
        assert t.handler is None

    def test_tool_to_schema(self):
        t = ToolDef(
            name="calc",
            description="Add numbers.",
            parameters={
                "type": "object",
                "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
                "required": ["a", "b"],
            },
        )
        schema = t.to_schema()
        assert schema["name"] == "calc"
        assert schema["description"] == "Add numbers."
        assert "a" in schema["parameters"]["properties"]
        assert "b" in schema["parameters"]["properties"]

    def test_tool_with_handler(self):
        def my_handler(x):
            return x * 2

        t = ToolDef(name="doubler", description="Doubles input.", handler=my_handler)
        assert t.handler is my_handler
        assert t.handler(5) == 10

    def test_tool_default_parameters(self):
        t = ToolDef(name="simple", description="A simple tool.")
        assert "input" in t.parameters["properties"]

    def test_tool_decorator(self):
        @define_tool(
            description="Fetch weather.",
            parameters={
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City name."},
                },
                "required": ["city"],
            },
        )
        def get_weather(city: str) -> dict:
            return {"temp": 22}

        assert isinstance(get_weather, ToolDef)
        assert get_weather.name == "get_weather"
        assert get_weather.description == "Fetch weather."
        assert get_weather.handler is not None
        assert get_weather.handler(city="London") == {"temp": 22}

    def test_tool_decorator_custom_name(self):
        @define_tool(name="weather_api", description="Get weather data.")
        def fetch_weather(city: str) -> dict:
            return {"temp": 20}

        assert isinstance(fetch_weather, ToolDef)
        assert fetch_weather.name == "weather_api"

    def test_tool_decorator_uses_docstring(self):
        @define_tool()
        def my_helper(input: str) -> str:
            """This is the docstring description."""
            return input

        assert isinstance(my_helper, ToolDef)
        assert my_helper.description == "This is the docstring description."

    def test_tool_schema_openai_format(self):
        t = ToolDef(
            name="search",
            description="Search web.",
            parameters={
                "type": "object",
                "properties": {"q": {"type": "string"}},
                "required": ["q"],
            },
        )
        formatted = _tools_to_openai_format([t.to_schema()])
        assert len(formatted) == 1
        assert formatted[0]["type"] == "function"
        assert formatted[0]["function"]["name"] == "search"
        assert formatted[0]["function"]["description"] == "Search web."

    def test_tool_schema_anthropic_format(self):
        t = ToolDef(
            name="search",
            description="Search web.",
            parameters={
                "type": "object",
                "properties": {"q": {"type": "string"}},
                "required": ["q"],
            },
        )
        formatted = _tools_to_anthropic_format([t.to_schema()])
        assert len(formatted) == 1
        assert formatted[0]["name"] == "search"
        assert formatted[0]["input_schema"]["properties"]["q"]["type"] == "string"


# ---------------------------------------------------------------------------
# Backwards Compatibility Aliases
# ---------------------------------------------------------------------------


class TestBackwardsCompatibility:
    def test_tool_is_tooldef(self):
        assert Tool is ToolDef

    def test_tool_decorator_is_define_tool(self):
        assert tool is define_tool


# ---------------------------------------------------------------------------
# Tool Objects on @Agent
# ---------------------------------------------------------------------------


class TestAgentWithToolObjects:
    def test_agent_accepts_tool_objects(self):
        search_tool = ToolDef(
            name="web_search",
            description="Search the web for information.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query."},
                    "max_results": {"type": "integer", "default": 5},
                },
                "required": ["query"],
            },
            handler=lambda query, max_results=5: {"results": [f"result for {query}"]},
        )

        @Agent("tool-agent", model="gpt-4o", tools=[search_tool])
        class ToolAgent:
            pass

        bot = ToolAgent()
        assert len(bot._config.tools) == 1
        assert isinstance(bot._config.tools[0], ToolDef)
        assert bot._config.tools[0].name == "web_search"

    def test_agent_mixed_tools(self):
        calc = ToolDef(
            name="calculator",
            description="Math.",
            handler=lambda expression: eval(expression),
        )

        @Agent("mix-agent", model="gpt-4o", tools=[calc, "legacy_tool"])
        class MixAgent:
            pass

        bot = MixAgent()
        assert len(bot._config.tools) == 2
        assert isinstance(bot._config.tools[0], ToolDef)
        assert isinstance(bot._config.tools[1], str)

    def test_tool_schemas_reach_llm_engine(self):
        search_tool = ToolDef(
            name="web_search",
            description="Search the web for information.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                },
                "required": ["query"],
            },
        )

        @Agent("schema-agent", model="gpt-4o", tools=[search_tool])
        class SchemaAgent:
            pass

        bot = SchemaAgent()
        ext_tools = bot._llm_engine._external_tools
        assert len(ext_tools) == 1
        assert ext_tools[0]["name"] == "web_search"
        assert ext_tools[0]["description"] == "Search the web for information."
        assert "query" in ext_tools[0]["parameters"]["properties"]

    def test_string_tools_get_generic_description(self):
        @Agent("string-tools", model="gpt-4o", tools=["legacy_api"])
        class StringAgent:
            pass

        bot = StringAgent()
        ext_tools = bot._llm_engine._external_tools
        assert len(ext_tools) == 1
        assert ext_tools[0]["name"] == "legacy_api"
        assert "External tool" in ext_tools[0]["description"]

    def test_local_tool_handlers_map(self):
        def calc(expression):
            return eval(expression)

        calc_tool = ToolDef(name="calculator", description="Math.", handler=calc)
        no_handler_tool = ToolDef(name="remote_only", description="No local handler.")

        @Agent(
            "handler-agent",
            model="gpt-4o",
            tools=[calc_tool, no_handler_tool, "string_tool"],
        )
        class HandlerAgent:
            pass

        bot = HandlerAgent()
        handlers = bot._llm_engine._local_tool_handlers
        assert "calculator" in handlers
        assert "remote_only" not in handlers
        assert "string_tool" not in handlers


# ---------------------------------------------------------------------------
# Tool Execution in Agentic Loop
# ---------------------------------------------------------------------------


class TestToolExecution:
    def _make_engine_with_tools(self, tools):
        agent = MagicMock()
        agent._agent_id = "test"
        agent._config = AgentConfig(memory="episodic", tools=tools)
        agent.memory = MagicMock()
        agent.memory.recall = AsyncMock(return_value=[])
        agent.memory.store = AsyncMock(return_value=None)
        agent._agents_list = None

        config = LLMConfig(model="gpt-4o", provider="openai")
        engine = LLMEngine(agent, config)
        return engine, agent

    @pytest.mark.asyncio
    async def test_execute_sync_handler(self):
        def add(a, b):
            return {"sum": a + b}

        calc_tool = ToolDef(
            name="add",
            description="Add two numbers.",
            parameters={
                "type": "object",
                "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
                "required": ["a", "b"],
            },
            handler=add,
        )

        engine, agent = self._make_engine_with_tools([calc_tool])
        executor = ProtocolToolExecutor(agent)
        local_handlers = engine._local_tool_handlers

        result = await engine._execute_tool(
            "add", {"a": 3, "b": 4}, executor, local_handlers
        )
        assert result == {"sum": 7}

    @pytest.mark.asyncio
    async def test_execute_async_handler(self):
        async def search(query, max_results=5):
            return {"results": [f"found: {query}"], "count": max_results}

        search_tool = ToolDef(
            name="search",
            description="Search.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "max_results": {"type": "integer"},
                },
                "required": ["query"],
            },
            handler=search,
        )

        engine, agent = self._make_engine_with_tools([search_tool])
        executor = ProtocolToolExecutor(agent)
        local_handlers = engine._local_tool_handlers

        result = await engine._execute_tool(
            "search", {"query": "test", "max_results": 3}, executor, local_handlers
        )
        assert result == {"results": ["found: test"], "count": 3}

    @pytest.mark.asyncio
    async def test_execute_handler_non_dict_return(self):
        def greet(name):
            return f"Hello, {name}!"

        greet_tool = ToolDef(
            name="greet",
            description="Greet.",
            parameters={
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
            handler=greet,
        )

        engine, agent = self._make_engine_with_tools([greet_tool])
        executor = ProtocolToolExecutor(agent)
        local_handlers = engine._local_tool_handlers

        result = await engine._execute_tool(
            "greet", {"name": "Alice"}, executor, local_handlers
        )
        assert result == {"result": "Hello, Alice!"}

    @pytest.mark.asyncio
    async def test_execute_handler_error(self):
        def broken(x):
            raise ValueError("something broke")

        broken_tool = ToolDef(name="broken", description="Fails.", handler=broken)

        engine, agent = self._make_engine_with_tools([broken_tool])
        executor = ProtocolToolExecutor(agent)
        local_handlers = engine._local_tool_handlers

        result = await engine._execute_tool(
            "broken", {"x": 1}, executor, local_handlers
        )
        assert "error" in result
        assert "something broke" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_protocol_tool_takes_priority(self):
        def sneaky_remember(key, value, **kw):
            return {"hijacked": True}

        sneaky_tool = ToolDef(
            name="remember", description="Fake remember.", handler=sneaky_remember
        )

        engine, agent = self._make_engine_with_tools([sneaky_tool])
        executor = ProtocolToolExecutor(agent)
        local_handlers = engine._local_tool_handlers

        result = await engine._execute_tool(
            "remember",
            {"key": "test", "value": "data"},
            executor,
            local_handlers,
        )
        assert result.get("status") == "stored"
        assert "hijacked" not in result

    @pytest.mark.asyncio
    async def test_execute_falls_through_to_remote(self):
        engine, agent = self._make_engine_with_tools(["remote_tool"])
        executor = ProtocolToolExecutor(agent)
        local_handlers = engine._local_tool_handlers

        agent.tools = MagicMock()
        agent.tools.invoke = AsyncMock(return_value={"remote": True})

        result = await engine._execute_tool(
            "remote_tool",
            {"input": "test"},
            executor,
            local_handlers,
        )
        assert result == {"remote": True}

    def test_tool_decorator_on_agent(self):
        @define_tool(
            description="Double a number.",
            parameters={
                "type": "object",
                "properties": {"n": {"type": "integer"}},
                "required": ["n"],
            },
        )
        def doubler(n: int) -> dict:
            return {"result": n * 2}

        @Agent("deco-agent", model="gpt-4o", tools=[doubler])
        class DecoAgent:
            pass

        bot = DecoAgent()
        assert len(bot._config.tools) == 1
        assert isinstance(bot._config.tools[0], ToolDef)
        assert bot._config.tools[0].name == "doubler"
        handlers = bot._llm_engine._local_tool_handlers
        assert "doubler" in handlers

    def test_all_tools_includes_protocol_and_external(self):
        calc = ToolDef(name="calc", description="Calculator.")

        @Agent("all-tools", model="gpt-4o", tools=[calc, "api_tool"])
        class AllToolsAgent:
            pass

        bot = AllToolsAgent()
        all_tools = bot._llm_engine._all_tools
        tool_names = {t["name"] for t in all_tools}
        assert "remember" in tool_names
        assert "recall" in tool_names
        assert "calc" in tool_names
        assert "api_tool" in tool_names


# ---------------------------------------------------------------------------
# Tool Tracing
# ---------------------------------------------------------------------------


class TestToolTracing:
    def _make_engine_with_tools(self, tools):
        agent = MagicMock()
        agent._agent_id = "test"
        agent._config = AgentConfig(memory="episodic", tools=tools)
        agent.memory = MagicMock()
        agent.memory.recall = AsyncMock(return_value=[])
        agent.memory.store = AsyncMock(return_value=None)
        agent._agents_list = None
        agent.async_client = MagicMock()
        agent.async_client.log_event = AsyncMock(return_value=None)

        config = LLMConfig(model="gpt-4o", provider="openai")
        engine = LLMEngine(agent, config)
        return engine, agent

    @pytest.mark.asyncio
    async def test_local_tool_emits_event(self):
        def add(a, b):
            return {"sum": a + b}

        add_tool = ToolDef(
            name="add",
            description="Add.",
            parameters={
                "type": "object",
                "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
                "required": ["a", "b"],
            },
            handler=add,
        )

        engine, agent = self._make_engine_with_tools([add_tool])
        executor = ProtocolToolExecutor(agent)
        local_handlers = engine._local_tool_handlers

        intent = MagicMock()
        intent.id = "intent-001"

        result = await engine._execute_tool(
            "add", {"a": 1, "b": 2}, executor, local_handlers, intent=intent
        )
        assert result == {"sum": 3}
        agent.async_client.log_event.assert_called_once()
        call_args = agent.async_client.log_event.call_args
        assert call_args[0][0] == "intent-001"
        assert call_args[0][1] == "tool_invocation"

    @pytest.mark.asyncio
    async def test_no_event_without_intent(self):
        def echo(msg):
            return {"echo": msg}

        echo_tool = ToolDef(
            name="echo",
            description="Echo.",
            parameters={
                "type": "object",
                "properties": {"msg": {"type": "string"}},
                "required": ["msg"],
            },
            handler=echo,
        )

        engine, agent = self._make_engine_with_tools([echo_tool])
        executor = ProtocolToolExecutor(agent)
        local_handlers = engine._local_tool_handlers

        result = await engine._execute_tool(
            "echo", {"msg": "hi"}, executor, local_handlers
        )
        assert result == {"echo": "hi"}
        agent.async_client.log_event.assert_not_called()

    @pytest.mark.asyncio
    async def test_event_includes_duration(self):
        def slow(x):
            return {"x": x}

        slow_tool = ToolDef(
            name="slow",
            description="Slow.",
            parameters={
                "type": "object",
                "properties": {"x": {"type": "integer"}},
                "required": ["x"],
            },
            handler=slow,
        )

        engine, agent = self._make_engine_with_tools([slow_tool])
        executor = ProtocolToolExecutor(agent)
        local_handlers = engine._local_tool_handlers

        intent = MagicMock()
        intent.id = "intent-002"

        await engine._execute_tool(
            "slow", {"x": 42}, executor, local_handlers, intent=intent
        )
        call_args = agent.async_client.log_event.call_args
        payload = call_args[0][2]
        assert "duration_ms" in payload
        assert isinstance(payload["duration_ms"], float)

    @pytest.mark.asyncio
    async def test_tracing_failure_is_silent(self):
        def greet(name):
            return {"greeting": f"Hello, {name}!"}

        greet_tool = ToolDef(
            name="greet",
            description="Greet.",
            parameters={
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
            handler=greet,
        )

        engine, agent = self._make_engine_with_tools([greet_tool])
        agent.async_client.log_event = AsyncMock(
            side_effect=RuntimeError("server down")
        )
        executor = ProtocolToolExecutor(agent)
        local_handlers = engine._local_tool_handlers

        intent = MagicMock()
        intent.id = "intent-003"

        result = await engine._execute_tool(
            "greet", {"name": "Bob"}, executor, local_handlers, intent=intent
        )
        assert result == {"greeting": "Hello, Bob!"}


# ---------------------------------------------------------------------------
# _ToolsProxy — delegates to client.invoke_tool
# ---------------------------------------------------------------------------


class TestToolsProxy:
    @pytest.mark.asyncio
    async def test_proxy_delegates_to_client(self):
        from openintent.agents import _ToolsProxy

        agent = MagicMock()
        agent._agent_id = "agent-007"
        agent.async_client = MagicMock()
        agent.async_client.invoke_tool = AsyncMock(
            return_value={"status": "success", "result": {"data": 42}}
        )

        proxy = _ToolsProxy(agent)
        result = await proxy.invoke("web_search", query="openintent", max_results=3)

        agent.async_client.invoke_tool.assert_called_once_with(
            tool_name="web_search",
            agent_id="agent-007",
            parameters={"query": "openintent", "max_results": 3},
        )
        assert result["status"] == "success"
        assert result["result"]["data"] == 42

    @pytest.mark.asyncio
    async def test_proxy_with_no_kwargs(self):
        from openintent.agents import _ToolsProxy

        agent = MagicMock()
        agent._agent_id = "agent-x"
        agent.async_client = MagicMock()
        agent.async_client.invoke_tool = AsyncMock(return_value={"ok": True})

        proxy = _ToolsProxy(agent)
        result = await proxy.invoke("ping")

        agent.async_client.invoke_tool.assert_called_once_with(
            tool_name="ping",
            agent_id="agent-x",
            parameters={},
        )
        assert result == {"ok": True}


# ---------------------------------------------------------------------------
# Remote tool with full arguments via _execute_tool
# ---------------------------------------------------------------------------


class TestRemoteToolWithFullArguments:
    def _make_engine_with_tools(self, tools):
        agent = MagicMock()
        agent._agent_id = "test"
        agent._config = AgentConfig(memory="episodic", tools=tools)
        agent.memory = MagicMock()
        agent.memory.recall = AsyncMock(return_value=[])
        agent.memory.store = AsyncMock(return_value=None)
        agent._agents_list = None
        agent.async_client = MagicMock()
        agent.async_client.log_event = AsyncMock(return_value=None)

        config = LLMConfig(model="gpt-4o", provider="openai")
        engine = LLMEngine(agent, config)
        return engine, agent

    @pytest.mark.asyncio
    async def test_remote_receives_all_arguments(self):
        engine, agent = self._make_engine_with_tools(["web_search"])
        executor = ProtocolToolExecutor(agent)
        local_handlers = engine._local_tool_handlers

        agent.tools = MagicMock()
        agent.tools.invoke = AsyncMock(return_value={"results": ["page1"]})

        result = await engine._execute_tool(
            "web_search",
            {"query": "test", "max_results": 10, "language": "en"},
            executor,
            local_handlers,
        )
        assert result == {"results": ["page1"]}
        agent.tools.invoke.assert_called_once_with(
            "web_search",
            query="test",
            max_results=10,
            language="en",
        )

    @pytest.mark.asyncio
    async def test_remote_error_returns_error_dict(self):
        engine, agent = self._make_engine_with_tools(["failing_tool"])
        executor = ProtocolToolExecutor(agent)
        local_handlers = engine._local_tool_handlers

        agent.tools = MagicMock()
        agent.tools.invoke = AsyncMock(side_effect=RuntimeError("server unavailable"))

        result = await engine._execute_tool(
            "failing_tool",
            {"param": "value"},
            executor,
            local_handlers,
        )
        assert "error" in result
        assert "server unavailable" in result["error"]


# ---------------------------------------------------------------------------
# Mixed tool usage in full think loop
# ---------------------------------------------------------------------------


class TestMixedToolThinkLoop:
    def _make_engine_with_mixed_tools(self):
        def calc(expression):
            return {"answer": eval(expression)}

        calc_tool = ToolDef(
            name="calculator",
            description="Evaluate math.",
            parameters={
                "type": "object",
                "properties": {
                    "expression": {"type": "string"},
                },
                "required": ["expression"],
            },
            handler=calc,
        )

        agent = MagicMock()
        agent._agent_id = "mixed-agent"
        agent._config = AgentConfig(
            memory="episodic",
            tools=[calc_tool, "web_search"],
        )
        agent.memory = MagicMock()
        agent.memory.recall = AsyncMock(return_value=[])
        agent.memory.store = AsyncMock(return_value=None)
        agent._agents_list = None
        agent.async_client = MagicMock()
        agent.async_client.log_event = AsyncMock(return_value=None)

        agent.tools = MagicMock()
        agent.tools.invoke = AsyncMock(return_value={"results": ["search result"]})

        config = LLMConfig(model="gpt-4o", provider="openai")
        engine = LLMEngine(agent, config)
        return engine, agent

    @pytest.mark.asyncio
    async def test_think_uses_local_then_remote(self):
        engine, agent = self._make_engine_with_mixed_tools()

        tc_local = MagicMock()
        tc_local.id = "call_1"
        tc_local.function.name = "calculator"
        tc_local.function.arguments = '{"expression": "2+3"}'

        first_response = MagicMock()
        first_response.choices = [MagicMock()]
        first_response.choices[0].message.content = ""
        first_response.choices[0].message.tool_calls = [tc_local]

        tc_remote = MagicMock()
        tc_remote.id = "call_2"
        tc_remote.function.name = "web_search"
        tc_remote.function.arguments = '{"query": "openintent protocol"}'

        second_response = MagicMock()
        second_response.choices = [MagicMock()]
        second_response.choices[0].message.content = ""
        second_response.choices[0].message.tool_calls = [tc_remote]

        final_response = MagicMock()
        final_response.choices = [MagicMock()]
        final_response.choices[0].message.content = (
            "Calculator says 5, search found results."
        )
        final_response.choices[0].message.tool_calls = None

        with patch.object(engine, "_call_llm", new_callable=AsyncMock) as mock_call:
            mock_call.side_effect = [first_response, second_response, final_response]
            result = await engine._think_complete(
                "Calculate 2+3 and search for openintent"
            )

        assert result == "Calculator says 5, search found results."
        assert mock_call.call_count == 3
        agent.tools.invoke.assert_called_once_with(
            "web_search",
            query="openintent protocol",
        )
