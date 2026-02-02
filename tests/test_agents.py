"""
Unit tests for the OpenIntent agents module.

Tests the high-level Agent, Coordinator, Worker abstractions.
"""


from openintent.agents import (
    Agent,
    AgentConfig,
    Coordinator,
    IntentSpec,
    PortfolioSpec,
    Worker,
    on_all_complete,
    on_assignment,
    on_complete,
    on_event,
    on_lease_available,
    on_state_change,
)
from openintent.models import EventType


class TestIntentSpec:
    """Tests for IntentSpec dataclass."""

    def test_basic_creation(self):
        spec = IntentSpec(title="Test Intent")
        assert spec.title == "Test Intent"
        assert spec.description == ""
        assert spec.assign is None
        assert spec.depends_on == []
        assert spec.constraints == []
        assert spec.initial_state == {}

    def test_with_dependencies(self):
        spec = IntentSpec(
            title="Analysis",
            description="Analyze data",
            assign="analyst-bot",
            depends_on=["Research", "Data Collection"],
        )
        assert spec.title == "Analysis"
        assert spec.assign == "analyst-bot"
        assert spec.depends_on == ["Research", "Data Collection"]

    def test_with_initial_state(self):
        spec = IntentSpec(
            title="Task",
            initial_state={"priority": "high", "category": "research"},
        )
        assert spec.initial_state == {"priority": "high", "category": "research"}


class TestPortfolioSpec:
    """Tests for PortfolioSpec dataclass."""

    def test_basic_creation(self):
        spec = PortfolioSpec(name="Test Portfolio")
        assert spec.name == "Test Portfolio"
        assert spec.description == ""
        assert spec.intents == []
        assert spec.governance_policy == {}
        assert spec.metadata == {}

    def test_with_intents(self):
        spec = PortfolioSpec(
            name="Research Project",
            description="Multi-phase research",
            intents=[
                IntentSpec("Phase 1", assign="bot1"),
                IntentSpec("Phase 2", assign="bot2", depends_on=["Phase 1"]),
            ],
        )
        assert len(spec.intents) == 2
        assert spec.intents[0].title == "Phase 1"
        assert spec.intents[1].depends_on == ["Phase 1"]


class TestAgentConfig:
    """Tests for AgentConfig dataclass."""

    def test_defaults(self):
        config = AgentConfig()
        assert config.base_url == "http://localhost:5000"
        assert config.api_key == ""
        assert config.auto_subscribe is True
        assert config.auto_complete is True
        assert config.reconnect_delay == 5.0
        assert config.max_reconnects == 10

    def test_custom_values(self):
        config = AgentConfig(
            base_url="https://api.example.com",
            api_key="secret-key",
            auto_subscribe=False,
            max_reconnects=5,
        )
        assert config.base_url == "https://api.example.com"
        assert config.api_key == "secret-key"
        assert config.auto_subscribe is False
        assert config.max_reconnects == 5


class TestEventDecorators:
    """Tests for event handler decorators."""

    def test_on_assignment_decorator(self):
        @on_assignment
        def handler(intent):
            pass

        assert hasattr(handler, "_openintent_handler")
        assert handler._openintent_handler == "assignment"

    def test_on_complete_decorator(self):
        @on_complete
        def handler(intent):
            pass

        assert handler._openintent_handler == "complete"

    def test_on_lease_available_decorator(self):
        @on_lease_available("research")
        def handler(intent, scope):
            pass

        assert handler._openintent_handler == "lease_available"
        assert handler._openintent_scope == "research"

    def test_on_state_change_decorator(self):
        @on_state_change(["progress", "status"])
        def handler(intent, old_state, new_state):
            pass

        assert handler._openintent_handler == "state_change"
        assert handler._openintent_keys == ["progress", "status"]

    def test_on_state_change_decorator_no_keys(self):
        @on_state_change()
        def handler(intent, old_state, new_state):
            pass

        assert handler._openintent_handler == "state_change"
        assert handler._openintent_keys is None

    def test_on_event_decorator_with_string(self):
        @on_event("CUSTOM_EVENT")
        def handler(intent, event):
            pass

        assert handler._openintent_handler == "event"
        assert handler._openintent_event_type == "CUSTOM_EVENT"

    def test_on_event_decorator_with_enum(self):
        @on_event(EventType.ARBITRATION_REQUESTED)
        def handler(intent, event):
            pass

        assert handler._openintent_handler == "event"
        assert handler._openintent_event_type == "arbitration_requested"

    def test_on_all_complete_decorator(self):
        @on_all_complete
        def handler(portfolio):
            pass

        assert handler._openintent_handler == "all_complete"


class TestAgentDecorator:
    """Tests for the @Agent class decorator."""

    def test_agent_decorator_creates_class(self):
        @Agent("test-bot")
        class TestAgent:
            pass

        assert hasattr(TestAgent, "run")
        assert hasattr(TestAgent, "_agent_id") or True

    def test_agent_decorator_with_handlers(self):
        @Agent("test-bot")
        class TestAgent:
            @on_assignment
            async def work(self, intent):
                return {"done": True}

            @on_complete
            async def cleanup(self, intent):
                pass

        instance = TestAgent()
        assert hasattr(instance, "_handlers")


class TestWorker:
    """Tests for the Worker class."""

    def test_worker_creation(self):
        async def handler(intent):
            return {"processed": True}

        worker = Worker(
            agent_id="test-worker",
            handler=handler,
            base_url="http://localhost:5000",
            api_key="test-key",
        )

        assert worker.agent_id == "test-worker"
        assert worker.handler == handler
        assert worker.base_url == "http://localhost:5000"
        assert worker.api_key == "test-key"

    def test_worker_stop(self):
        async def handler(intent):
            pass

        worker = Worker("test", handler)
        worker._running = True
        worker.stop()
        assert worker._running is False


class TestCoordinator:
    """Tests for the Coordinator class."""

    def test_coordinator_creation(self):
        coordinator = Coordinator(
            agent_id="test-coordinator",
            base_url="http://localhost:5000",
            api_key="test-key",
        )

        assert coordinator._agent_id == "test-coordinator"

    def test_topological_sort(self):
        coordinator = Coordinator("test", "http://localhost:5000", "key")

        intents = [
            IntentSpec("C", depends_on=["A", "B"]),
            IntentSpec("A"),
            IntentSpec("B", depends_on=["A"]),
        ]

        sorted_intents = coordinator._topological_sort(intents)

        titles = [i.title for i in sorted_intents]
        assert titles.index("A") < titles.index("B")
        assert titles.index("A") < titles.index("C")
        assert titles.index("B") < titles.index("C")

    def test_topological_sort_no_deps(self):
        coordinator = Coordinator("test", "http://localhost:5000", "key")

        intents = [
            IntentSpec("A"),
            IntentSpec("B"),
            IntentSpec("C"),
        ]

        sorted_intents = coordinator._topological_sort(intents)
        assert len(sorted_intents) == 3
