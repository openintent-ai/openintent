"""Tests for RFC-0025: Human-in-the-Loop Intent Suspension."""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------


class TestIntentStatusSuspended:
    """IntentStatus.SUSPENDED_AWAITING_INPUT is present and correct."""

    def test_status_value(self):
        from openintent.models import IntentStatus

        assert IntentStatus.SUSPENDED_AWAITING_INPUT == "suspended_awaiting_input"

    def test_status_is_string(self):
        from openintent.models import IntentStatus

        assert isinstance(IntentStatus.SUSPENDED_AWAITING_INPUT, str)

    def test_status_in_enum(self):
        from openintent.models import IntentStatus

        members = [s.value for s in IntentStatus]
        assert "suspended_awaiting_input" in members


class TestEventTypeHITL:
    """New HITL EventType constants are present and correct."""

    def test_intent_suspended(self):
        from openintent.models import EventType

        assert EventType.INTENT_SUSPENDED == "intent.suspended"

    def test_intent_resumed(self):
        from openintent.models import EventType

        assert EventType.INTENT_RESUMED == "intent.resumed"

    def test_intent_suspension_expired(self):
        from openintent.models import EventType

        assert EventType.INTENT_SUSPENSION_EXPIRED == "intent.suspension_expired"

    def test_engagement_decision(self):
        from openintent.models import EventType

        assert EventType.ENGAGEMENT_DECISION == "engagement.decision"

    def test_all_hitl_events_in_enum(self):
        from openintent.models import EventType

        values = {e.value for e in EventType}
        assert "intent.suspended" in values
        assert "intent.resumed" in values
        assert "intent.suspension_expired" in values
        assert "engagement.decision" in values


class TestSuspensionRecord:
    """SuspensionRecord model: construction, serialisation, round-trip."""

    def _make_record(self, **kwargs):
        from openintent.models import SuspensionRecord

        defaults = dict(
            id="susp-001",
            question="Should we proceed with refund?",
            context={"amount": 500, "currency": "USD"},
            channel_hint="slack",
            suspended_at=datetime(2026, 3, 23, 10, 0, 0),
            timeout_seconds=300,
            expires_at=datetime(2026, 3, 23, 10, 5, 0),
            fallback_value="deny",
            fallback_policy="complete_with_fallback",
            confidence_at_suspension=0.55,
        )
        defaults.update(kwargs)
        return SuspensionRecord(**defaults)

    def test_construction(self):
        rec = self._make_record()
        assert rec.id == "susp-001"
        assert rec.question == "Should we proceed with refund?"
        assert rec.fallback_policy == "complete_with_fallback"
        assert rec.confidence_at_suspension == 0.55

    def test_to_dict_required_fields(self):
        rec = self._make_record()
        d = rec.to_dict()
        assert d["id"] == "susp-001"
        assert d["question"] == "Should we proceed with refund?"
        assert d["fallback_policy"] == "complete_with_fallback"
        assert d["context"]["amount"] == 500

    def test_to_dict_optional_fields(self):
        rec = self._make_record()
        d = rec.to_dict()
        assert d["channel_hint"] == "slack"
        assert d["timeout_seconds"] == 300
        assert d["fallback_value"] == "deny"
        assert d["confidence_at_suspension"] == 0.55

    def test_to_dict_timestamps_iso8601(self):
        rec = self._make_record()
        d = rec.to_dict()
        assert "T" in d["suspended_at"]
        assert "T" in d["expires_at"]

    def test_from_dict_round_trip(self):
        from openintent.models import SuspensionRecord

        rec = self._make_record()
        d = rec.to_dict()
        rec2 = SuspensionRecord.from_dict(d)
        assert rec2.id == rec.id
        assert rec2.question == rec.question
        assert rec2.fallback_policy == rec.fallback_policy
        assert rec2.confidence_at_suspension == rec.confidence_at_suspension

    def test_minimal_construction(self):
        from openintent.models import SuspensionRecord

        rec = SuspensionRecord(id="x", question="Proceed?")
        assert rec.fallback_policy == "fail"
        assert rec.context == {}
        assert rec.channel_hint is None
        assert rec.response is None

    def test_resolution_responded(self):
        rec = self._make_record(response="approve", resolution="responded")
        d = rec.to_dict()
        assert d["resolution"] == "responded"
        assert d["response"] == "approve"

    def test_from_dict_with_responded_at(self):
        from openintent.models import SuspensionRecord

        d = {
            "id": "s1",
            "question": "Q",
            "responded_at": "2026-03-23T10:01:00",
            "resolution": "responded",
        }
        rec = SuspensionRecord.from_dict(d)
        assert rec.responded_at is not None
        assert rec.resolution == "responded"


class TestEngagementSignals:
    """EngagementSignals model: defaults, serialisation, round-trip."""

    def test_defaults(self):
        from openintent.models import EngagementSignals

        sig = EngagementSignals()
        assert sig.confidence == 1.0
        assert sig.risk == 0.0
        assert sig.reversibility == 1.0
        assert sig.context == {}

    def test_custom_values(self):
        from openintent.models import EngagementSignals

        sig = EngagementSignals(confidence=0.6, risk=0.7, reversibility=0.3)
        assert sig.confidence == 0.6
        assert sig.risk == 0.7

    def test_to_dict(self):
        from openintent.models import EngagementSignals

        sig = EngagementSignals(confidence=0.6, risk=0.4, reversibility=0.8)
        d = sig.to_dict()
        assert d["confidence"] == 0.6
        assert d["risk"] == 0.4
        assert d["reversibility"] == 0.8

    def test_from_dict_round_trip(self):
        from openintent.models import EngagementSignals

        sig = EngagementSignals(confidence=0.75, risk=0.25, reversibility=0.9)
        d = sig.to_dict()
        sig2 = EngagementSignals.from_dict(d)
        assert sig2.confidence == 0.75
        assert sig2.risk == 0.25

    def test_from_dict_defaults(self):
        from openintent.models import EngagementSignals

        sig = EngagementSignals.from_dict({})
        assert sig.confidence == 1.0
        assert sig.risk == 0.0


class TestEngagementDecision:
    """EngagementDecision model: all modes, serialisation, round-trip."""

    def _make_decision(self, mode="autonomous", should_ask=False, **kwargs):
        from openintent.models import EngagementDecision, EngagementSignals

        return EngagementDecision(
            mode=mode,
            should_ask=should_ask,
            rationale="Test rationale",
            signals=EngagementSignals(),
            **kwargs,
        )

    def test_autonomous_mode(self):
        d = self._make_decision("autonomous", False)
        assert d.mode == "autonomous"
        assert d.should_ask is False

    def test_request_input_mode(self):
        d = self._make_decision("request_input", True)
        assert d.mode == "request_input"
        assert d.should_ask is True

    def test_require_input_mode(self):
        d = self._make_decision("require_input", True)
        assert d.mode == "require_input"
        assert d.should_ask is True

    def test_defer_mode(self):
        d = self._make_decision("defer", False)
        assert d.mode == "defer"
        assert d.should_ask is False

    def test_to_dict(self):
        d = self._make_decision("request_input", True)
        dd = d.to_dict()
        assert dd["mode"] == "request_input"
        assert dd["should_ask"] is True
        assert "signals" in dd

    def test_from_dict_round_trip(self):
        from openintent.models import EngagementDecision

        d = self._make_decision("require_input", True)
        dd = d.to_dict()
        d2 = EngagementDecision.from_dict(dd)
        assert d2.mode == "require_input"
        assert d2.should_ask is True
        assert d2.signals is not None

    def test_from_dict_no_signals(self):
        from openintent.models import EngagementDecision

        d = EngagementDecision.from_dict({"mode": "autonomous", "should_ask": False})
        assert d.signals is None


class TestInputResponse:
    """InputResponse model: construction, serialisation, round-trip."""

    def test_construction(self):
        from openintent.models import InputResponse

        r = InputResponse(
            suspension_id="susp-1",
            value="approve",
            responded_by="alice",
        )
        assert r.suspension_id == "susp-1"
        assert r.value == "approve"

    def test_to_dict(self):
        from openintent.models import InputResponse

        r = InputResponse(
            suspension_id="susp-1",
            value=42,
            responded_by="bob",
            responded_at=datetime(2026, 3, 23, 11, 0, 0),
        )
        d = r.to_dict()
        assert d["suspension_id"] == "susp-1"
        assert d["value"] == 42
        assert d["responded_by"] == "bob"
        assert "T" in d["responded_at"]

    def test_from_dict_round_trip(self):
        from openintent.models import InputResponse

        r = InputResponse(
            suspension_id="s",
            value={"decision": "approve"},
            responded_by="carol",
            responded_at=datetime(2026, 3, 23, 12, 0, 0),
        )
        d = r.to_dict()
        r2 = InputResponse.from_dict(d)
        assert r2.suspension_id == r.suspension_id
        assert r2.value == r.value
        assert r2.responded_by == r.responded_by

    def test_from_dict_without_timestamp(self):
        from openintent.models import InputResponse

        r = InputResponse.from_dict({"suspension_id": "x", "value": "ok"})
        assert r.responded_at is None


# ---------------------------------------------------------------------------
# Exception tests
# ---------------------------------------------------------------------------


class TestInputTimeoutError:
    """InputTimeoutError carries suspension metadata."""

    def test_basic_raise(self):
        from openintent.exceptions import InputTimeoutError

        with pytest.raises(InputTimeoutError) as exc_info:
            raise InputTimeoutError("timed out")
        assert "timed out" in str(exc_info.value)

    def test_suspension_id_attribute(self):
        from openintent.exceptions import InputTimeoutError

        err = InputTimeoutError("timed out", suspension_id="susp-99")
        assert err.suspension_id == "susp-99"

    def test_fallback_policy_attribute(self):
        from openintent.exceptions import InputTimeoutError

        err = InputTimeoutError("timed out", fallback_policy="complete_with_fallback")
        assert err.fallback_policy == "complete_with_fallback"

    def test_inherits_from_openintent_error(self):
        from openintent.exceptions import InputTimeoutError, OpenIntentError

        assert issubclass(InputTimeoutError, OpenIntentError)


class TestInputCancelledError:
    """InputCancelledError carries suspension metadata."""

    def test_basic_raise(self):
        from openintent.exceptions import InputCancelledError

        with pytest.raises(InputCancelledError) as exc_info:
            raise InputCancelledError("cancelled")
        assert "cancelled" in str(exc_info.value)

    def test_suspension_id_attribute(self):
        from openintent.exceptions import InputCancelledError

        err = InputCancelledError("cancelled", suspension_id="susp-77")
        assert err.suspension_id == "susp-77"

    def test_inherits_from_openintent_error(self):
        from openintent.exceptions import InputCancelledError, OpenIntentError

        assert issubclass(InputCancelledError, OpenIntentError)


# ---------------------------------------------------------------------------
# Decorator tests
# ---------------------------------------------------------------------------


class TestHITLDecorators:
    """HITL decorators set _openintent_handler correctly."""

    def test_on_input_requested(self):
        from openintent.agents import on_input_requested

        @on_input_requested
        def handler(self, intent, suspension):
            pass

        assert handler._openintent_handler == "input_requested"

    def test_on_input_received(self):
        from openintent.agents import on_input_received

        @on_input_received
        def handler(self, intent, response):
            pass

        assert handler._openintent_handler == "input_received"

    def test_on_suspension_expired(self):
        from openintent.agents import on_suspension_expired

        @on_suspension_expired
        def handler(self, intent, suspension):
            pass

        assert handler._openintent_handler == "suspension_expired"

    def test_on_engagement_decision(self):
        from openintent.agents import on_engagement_decision

        @on_engagement_decision
        def handler(self, intent, decision):
            pass

        assert handler._openintent_handler == "engagement_decision"

    def test_decorators_preserve_function(self):
        from openintent.agents import on_input_requested

        @on_input_requested
        async def my_handler(self, intent, suspension):
            """My handler."""
            return "ok"

        assert my_handler.__name__ == "my_handler"
        assert asyncio.iscoroutinefunction(my_handler)

    def test_handler_discovery(self):
        """Decorated methods are discovered in _discover_handlers."""
        from openintent.agents import Agent, on_input_requested, on_suspension_expired

        @Agent("test-agent-discovery")
        class MyAgent:
            @on_input_requested
            async def notify(self, intent, suspension):
                pass

            @on_suspension_expired
            async def expire(self, intent, suspension):
                pass

        # Instantiate to trigger _discover_handlers in __init__
        with patch.dict("os.environ", {"OPENINTENT_BASE_URL": "http://localhost:8000"}):
            agent_instance = MyAgent.__new__(MyAgent)
            agent_instance._agent_id = "test-agent-discovery"
            agent_instance._client = None
            agent_instance._async_client = None
            from openintent.agents import AgentConfig

            agent_instance._config = AgentConfig()
            agent_instance._config.auto_heartbeat = False
            agent_instance._governance_policy = None
            agent_instance._federation_visibility = None
            agent_instance._running = False
            agent_instance._mcp_bridge = None
            agent_instance._discover_handlers()

        assert len(agent_instance._handlers["input_requested"]) == 1
        assert len(agent_instance._handlers["suspension_expired"]) == 1


# ---------------------------------------------------------------------------
# should_request_input tests
# ---------------------------------------------------------------------------


class TestShouldRequestInput:
    """should_request_input() returns correct EngagementDecision modes."""

    def _make_agent_instance(self):
        """Create a minimal BaseAgent instance with mock async client."""
        from openintent.agents import AgentConfig, BaseAgent

        instance = BaseAgent.__new__(BaseAgent)
        instance._agent_id = "hitl-test-agent"
        instance._client = None
        instance._running = False
        instance._mcp_bridge = None
        instance._governance_policy = None
        instance._federation_visibility = None
        config = AgentConfig()
        config.auto_heartbeat = False
        instance._config = config
        instance._discover_handlers()

        mock_client = AsyncMock()
        mock_client.get_intent.return_value = MagicMock(id="intent-1")
        mock_client.log_event = AsyncMock()
        instance._async_client = mock_client
        return instance

    @pytest.mark.asyncio
    async def test_autonomous_mode(self):
        """High confidence, low risk, reversible → autonomous."""
        from openintent.models import EngagementSignals

        agent = self._make_agent_instance()
        signals = EngagementSignals(confidence=0.95, risk=0.05, reversibility=0.9)
        decision = await agent.should_request_input("intent-1", signals=signals)
        assert decision.mode == "autonomous"
        assert decision.should_ask is False

    @pytest.mark.asyncio
    async def test_request_input_mode(self):
        """Moderate confidence and risk → request_input."""
        from openintent.models import EngagementSignals

        agent = self._make_agent_instance()
        signals = EngagementSignals(confidence=0.7, risk=0.3, reversibility=0.7)
        decision = await agent.should_request_input("intent-1", signals=signals)
        assert decision.mode == "request_input"
        assert decision.should_ask is True

    @pytest.mark.asyncio
    async def test_require_input_mode(self):
        """Low confidence → require_input."""
        from openintent.models import EngagementSignals

        agent = self._make_agent_instance()
        signals = EngagementSignals(confidence=0.3, risk=0.4, reversibility=0.6)
        decision = await agent.should_request_input("intent-1", signals=signals)
        assert decision.mode == "require_input"
        assert decision.should_ask is True

    @pytest.mark.asyncio
    async def test_defer_mode_high_risk(self):
        """Very high risk → defer."""
        from openintent.models import EngagementSignals

        agent = self._make_agent_instance()
        signals = EngagementSignals(confidence=0.9, risk=0.9, reversibility=0.5)
        decision = await agent.should_request_input("intent-1", signals=signals)
        assert decision.mode == "defer"
        assert decision.should_ask is False

    @pytest.mark.asyncio
    async def test_defer_mode_irreversible(self):
        """Irreversible action → defer."""
        from openintent.models import EngagementSignals

        agent = self._make_agent_instance()
        signals = EngagementSignals(confidence=0.9, risk=0.5, reversibility=0.05)
        decision = await agent.should_request_input("intent-1", signals=signals)
        assert decision.mode == "defer"

    @pytest.mark.asyncio
    async def test_kwargs_shorthand(self):
        """Keyword shorthand works without EngagementSignals object."""
        agent = self._make_agent_instance()
        decision = await agent.should_request_input(
            "intent-1", confidence=0.95, risk=0.05, reversibility=0.9
        )
        assert decision.mode == "autonomous"

    @pytest.mark.asyncio
    async def test_decision_has_signals(self):
        """Decision object carries the EngagementSignals used."""
        from openintent.models import EngagementSignals

        agent = self._make_agent_instance()
        signals = EngagementSignals(confidence=0.9, risk=0.1, reversibility=0.8)
        decision = await agent.should_request_input("intent-1", signals=signals)
        assert decision.signals is not None
        assert decision.signals.confidence == 0.9

    @pytest.mark.asyncio
    async def test_engagement_decision_event_emitted(self):
        """should_request_input() emits an engagement.decision event."""
        from openintent.models import EngagementSignals

        agent = self._make_agent_instance()
        signals = EngagementSignals(confidence=0.9, risk=0.1, reversibility=0.8)
        await agent.should_request_input("intent-1", signals=signals)
        agent._async_client.log_event.assert_called_once()
        call_args = agent._async_client.log_event.call_args
        assert call_args[0][1].value == "engagement.decision"

    @pytest.mark.asyncio
    async def test_on_engagement_decision_hook_fired(self):
        """@on_engagement_decision handlers are called after should_request_input."""
        from openintent.agents import AgentConfig, BaseAgent, on_engagement_decision
        from openintent.models import EngagementSignals

        received = []

        class HookAgent(BaseAgent):
            @on_engagement_decision
            async def on_decision(self, intent, decision):
                received.append(decision.mode)

        instance = HookAgent.__new__(HookAgent)
        instance._agent_id = "hook-agent"
        instance._client = None
        instance._running = False
        instance._mcp_bridge = None
        instance._governance_policy = None
        instance._federation_visibility = None
        config = AgentConfig()
        config.auto_heartbeat = False
        instance._config = config
        instance._discover_handlers()

        mock_client = AsyncMock()
        mock_client.get_intent.return_value = MagicMock(id="intent-99")
        mock_client.log_event = AsyncMock()
        instance._async_client = mock_client

        signals = EngagementSignals(confidence=0.95, risk=0.05, reversibility=0.9)
        await instance.should_request_input("intent-99", signals=signals)
        assert received == ["autonomous"]


# ---------------------------------------------------------------------------
# Server endpoint tests
# ---------------------------------------------------------------------------


class TestSuspendRespondEndpoint:
    """POST /api/v1/intents/{id}/suspend/respond endpoint tests."""

    @pytest.fixture
    def client(self, tmp_path):
        from fastapi.testclient import TestClient

        from openintent.server.app import create_app
        from openintent.server.config import ServerConfig

        db_path = str(tmp_path / "test.db")
        config = ServerConfig(
            database_url=f"sqlite:///{db_path}",
            api_keys=["test-key"],
        )
        app = create_app(config)
        with TestClient(app) as tc:
            return tc

    def _create_intent(self, client, title="HITL Test Intent"):
        resp = client.post(
            "/api/v1/intents",
            json={"title": title},
            headers={"X-API-Key": "test-key"},
        )
        assert resp.status_code in (200, 201)
        return resp.json()

    def _set_status(self, client, intent_id, status, version):
        resp = client.post(
            f"/api/v1/intents/{intent_id}/status",
            json={"status": status},
            headers={"X-API-Key": "test-key", "If-Match": str(version)},
        )
        return resp

    def test_respond_to_suspended_intent(self, client):
        """Happy path: respond to a suspended intent."""
        intent = self._create_intent(client)
        intent_id = intent["id"]

        # Transition to suspended_awaiting_input
        set_resp = self._set_status(
            client, intent_id, "suspended_awaiting_input", intent["version"]
        )
        assert set_resp.status_code == 200

        # Respond
        resp = client.post(
            f"/api/v1/intents/{intent_id}/suspend/respond",
            json={
                "suspension_id": "susp-test",
                "value": "approve",
                "responded_by": "alice",
            },
            headers={"X-API-Key": "test-key"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["resolution"] == "responded"
        assert data["value"] == "approve"
        assert data["responded_by"] == "alice"

    def test_respond_transitions_to_active(self, client):
        """After respond, intent transitions back to active."""
        intent = self._create_intent(client)
        intent_id = intent["id"]

        self._set_status(
            client, intent_id, "suspended_awaiting_input", intent["version"]
        )

        client.post(
            f"/api/v1/intents/{intent_id}/suspend/respond",
            json={"suspension_id": "s1", "value": "yes"},
            headers={"X-API-Key": "test-key"},
        )

        # Fetch intent - should be active
        get_resp = client.get(
            f"/api/v1/intents/{intent_id}",
            headers={"X-API-Key": "test-key"},
        )
        assert get_resp.status_code == 200
        assert get_resp.json()["status"] == "active"

    def test_respond_to_non_suspended_intent_fails(self, client):
        """Responding to a non-suspended intent returns 409."""
        intent = self._create_intent(client)
        intent_id = intent["id"]

        # Intent is in draft status, not suspended
        resp = client.post(
            f"/api/v1/intents/{intent_id}/suspend/respond",
            json={"suspension_id": "s1", "value": "yes"},
            headers={"X-API-Key": "test-key"},
        )
        assert resp.status_code == 409

    def test_respond_to_missing_intent_fails(self, client):
        """Responding to non-existent intent returns 404."""
        resp = client.post(
            "/api/v1/intents/nonexistent-id/suspend/respond",
            json={"suspension_id": "s1", "value": "yes"},
            headers={"X-API-Key": "test-key"},
        )
        assert resp.status_code == 404

    def test_respond_with_complex_value(self, client):
        """Response value can be a complex object."""
        intent = self._create_intent(client)
        intent_id = intent["id"]
        self._set_status(
            client, intent_id, "suspended_awaiting_input", intent["version"]
        )

        complex_value = {"decision": "approve", "reason": "looks good", "amount": 500}
        resp = client.post(
            f"/api/v1/intents/{intent_id}/suspend/respond",
            json={"suspension_id": "s1", "value": complex_value},
            headers={"X-API-Key": "test-key"},
        )
        assert resp.status_code == 200
        assert resp.json()["value"] == complex_value

    def test_suspended_status_can_be_set(self, client):
        """Setting status to suspended_awaiting_input succeeds."""
        intent = self._create_intent(client)
        resp = self._set_status(
            client, intent["id"], "suspended_awaiting_input", intent["version"]
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "suspended_awaiting_input"

    def test_respond_without_api_key_fails(self, client):
        """Unauthenticated respond request returns 401 or 403."""
        intent = self._create_intent(client)
        intent_id = intent["id"]
        self._set_status(
            client, intent_id, "suspended_awaiting_input", intent["version"]
        )

        resp = client.post(
            f"/api/v1/intents/{intent_id}/suspend/respond",
            json={"suspension_id": "s1", "value": "yes"},
        )
        assert resp.status_code in (401, 403)

    def test_respond_response_has_timestamp(self, client):
        """Respond endpoint returns a responded_at timestamp."""
        intent = self._create_intent(client)
        intent_id = intent["id"]
        self._set_status(
            client, intent_id, "suspended_awaiting_input", intent["version"]
        )

        resp = client.post(
            f"/api/v1/intents/{intent_id}/suspend/respond",
            json={"suspension_id": "s1", "value": "ok"},
            headers={"X-API-Key": "test-key"},
        )
        assert resp.status_code == 200
        assert resp.json()["responded_at"] is not None

    # ------- helpers for suspension-with-choices tests -------

    def _suspend_with_choices(self, client, choices, response_type="choice"):
        """Create an intent, set suspension state with choices, suspend it."""
        intent = self._create_intent(client)
        intent_id = intent["id"]

        status_resp = self._set_status(
            client, intent_id, "suspended_awaiting_input", intent["version"]
        )
        new_version = status_resp.json()["version"]

        susp_data = {
            "id": "susp-choices",
            "question": "Pick one",
            "response_type": response_type,
            "choices": choices,
            "fallback_policy": "fail",
            "context": {},
        }
        patch_resp = client.post(
            f"/api/v1/intents/{intent_id}/state",
            json={
                "patches": [{"op": "set", "path": "/_suspension", "value": susp_data}]
            },
            headers={"X-API-Key": "test-key", "If-Match": str(new_version)},
        )
        assert patch_resp.status_code == 200, f"State patch failed: {patch_resp.json()}"
        return intent_id

    # ------- Structured choice validation -------

    def test_valid_choice_accepted(self, client):
        """Responding with a valid choice value succeeds."""
        choices = [
            {"value": "approve", "label": "Approve"},
            {"value": "deny", "label": "Deny", "description": "Reject the request"},
        ]
        intent_id = self._suspend_with_choices(client, choices)

        resp = client.post(
            f"/api/v1/intents/{intent_id}/suspend/respond",
            json={"suspension_id": "susp-choices", "value": "approve"},
            headers={"X-API-Key": "test-key"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["value"] == "approve"
        assert data["choice_label"] == "Approve"

    def test_invalid_choice_rejected(self, client):
        """Responding with an invalid choice value returns 422."""
        choices = [
            {"value": "approve", "label": "Approve"},
            {"value": "deny", "label": "Deny"},
        ]
        intent_id = self._suspend_with_choices(client, choices)

        resp = client.post(
            f"/api/v1/intents/{intent_id}/suspend/respond",
            json={"suspension_id": "susp-choices", "value": "maybe"},
            headers={"X-API-Key": "test-key"},
        )
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert detail["error"] == "invalid_choice"
        assert "maybe" in detail["message"]
        assert len(detail["valid_choices"]) == 2

    def test_choice_description_in_response(self, client):
        """Response includes the matching choice's description."""
        choices = [
            {"value": "approve", "label": "Approve", "description": "Issue the refund"},
            {"value": "deny", "label": "Deny", "description": "Reject the refund"},
        ]
        intent_id = self._suspend_with_choices(client, choices)

        resp = client.post(
            f"/api/v1/intents/{intent_id}/suspend/respond",
            json={"suspension_id": "susp-choices", "value": "deny"},
            headers={"X-API-Key": "test-key"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["choice_label"] == "Deny"
        assert data["choice_description"] == "Reject the refund"

    def test_confirm_type_yes_no(self, client):
        """Confirm response_type allows yes/no values."""
        choices = [
            {"value": "yes", "label": "Yes"},
            {"value": "no", "label": "No"},
        ]
        intent_id = self._suspend_with_choices(client, choices, response_type="confirm")

        resp = client.post(
            f"/api/v1/intents/{intent_id}/suspend/respond",
            json={"suspension_id": "susp-choices", "value": "yes"},
            headers={"X-API-Key": "test-key"},
        )
        assert resp.status_code == 200
        assert resp.json()["value"] == "yes"

    def test_text_response_type_accepts_freeform(self, client):
        """Text response_type accepts any value (no choice validation)."""
        intent_id = self._suspend_with_choices(client, [], response_type="text")

        resp = client.post(
            f"/api/v1/intents/{intent_id}/suspend/respond",
            json={"suspension_id": "susp-choices", "value": "some freeform text"},
            headers={"X-API-Key": "test-key"},
        )
        assert resp.status_code == 200
        assert resp.json()["value"] == "some freeform text"

    def test_suspension_id_mismatch_rejected(self, client):
        """Mismatched suspension_id returns 409."""
        choices = [{"value": "ok", "label": "OK"}]
        intent_id = self._suspend_with_choices(client, choices)

        resp = client.post(
            f"/api/v1/intents/{intent_id}/suspend/respond",
            json={"suspension_id": "wrong-id", "value": "ok"},
            headers={"X-API-Key": "test-key"},
        )
        assert resp.status_code == 409
        assert "mismatch" in resp.json()["detail"]

    def test_no_choices_allows_any_value(self, client):
        """If suspension has no choices defined, any value is accepted."""
        intent = self._create_intent(client)
        intent_id = intent["id"]
        self._set_status(
            client, intent_id, "suspended_awaiting_input", intent["version"]
        )

        resp = client.post(
            f"/api/v1/intents/{intent_id}/suspend/respond",
            json={"suspension_id": "susp-any", "value": "anything"},
            headers={"X-API-Key": "test-key"},
        )
        assert resp.status_code == 200

    def test_empty_suspension_id_rejected(self, client):
        """Empty suspension_id returns 422."""
        intent = self._create_intent(client)
        intent_id = intent["id"]
        self._set_status(
            client, intent_id, "suspended_awaiting_input", intent["version"]
        )

        resp = client.post(
            f"/api/v1/intents/{intent_id}/suspend/respond",
            json={"suspension_id": "", "value": "yes"},
            headers={"X-API-Key": "test-key"},
        )
        assert resp.status_code == 422
        assert "required" in resp.json()["detail"].lower()

    def test_missing_suspension_id_rejected(self, client):
        """Missing suspension_id returns 422."""
        intent = self._create_intent(client)
        intent_id = intent["id"]
        self._set_status(
            client, intent_id, "suspended_awaiting_input", intent["version"]
        )

        resp = client.post(
            f"/api/v1/intents/{intent_id}/suspend/respond",
            json={"value": "yes"},
            headers={"X-API-Key": "test-key"},
        )
        assert resp.status_code == 422

    def test_confirm_without_choices_validates_yes_no(self, client):
        """Confirm type without explicit choices still validates yes/no."""
        intent_id = self._suspend_with_choices(client, [], response_type="confirm")

        resp_valid = client.post(
            f"/api/v1/intents/{intent_id}/suspend/respond",
            json={"suspension_id": "susp-choices", "value": "yes"},
            headers={"X-API-Key": "test-key"},
        )
        assert resp_valid.status_code == 200

    def test_confirm_without_choices_rejects_invalid(self, client):
        """Confirm type without explicit choices rejects non-yes/no."""
        intent_id = self._suspend_with_choices(client, [], response_type="confirm")

        resp_invalid = client.post(
            f"/api/v1/intents/{intent_id}/suspend/respond",
            json={"suspension_id": "susp-choices", "value": "maybe"},
            headers={"X-API-Key": "test-key"},
        )
        assert resp_invalid.status_code == 422


# ---------------------------------------------------------------------------
# Model tests for ResponseType, SuspensionChoice
# ---------------------------------------------------------------------------


class TestResponseType:
    """ResponseType enum tests."""

    def test_values(self):
        from openintent.models import ResponseType

        assert ResponseType.CHOICE == "choice"
        assert ResponseType.CONFIRM == "confirm"
        assert ResponseType.TEXT == "text"
        assert ResponseType.FORM == "form"

    def test_is_string_enum(self):
        from openintent.models import ResponseType

        assert isinstance(ResponseType.CHOICE, str)


class TestSuspensionChoice:
    """SuspensionChoice model tests."""

    def test_construction(self):
        from openintent.models import SuspensionChoice

        c = SuspensionChoice(value="approve", label="Approve")
        assert c.value == "approve"
        assert c.label == "Approve"
        assert c.description == ""
        assert c.style == "default"
        assert c.metadata == {}

    def test_full_construction(self):
        from openintent.models import SuspensionChoice

        c = SuspensionChoice(
            value="deny",
            label="Deny",
            description="Reject the request",
            style="danger",
            metadata={"reason_required": True},
        )
        assert c.description == "Reject the request"
        assert c.style == "danger"
        assert c.metadata["reason_required"] is True

    def test_to_dict_minimal(self):
        from openintent.models import SuspensionChoice

        c = SuspensionChoice(value="ok", label="OK")
        d = c.to_dict()
        assert d == {"value": "ok", "label": "OK"}
        assert "style" not in d
        assert "description" not in d

    def test_to_dict_full(self):
        from openintent.models import SuspensionChoice

        c = SuspensionChoice(
            value="approve", label="Approve", description="Go ahead", style="primary"
        )
        d = c.to_dict()
        assert d["description"] == "Go ahead"
        assert d["style"] == "primary"

    def test_from_dict_round_trip(self):
        from openintent.models import SuspensionChoice

        c = SuspensionChoice(
            value="x", label="X", description="desc", style="danger", metadata={"a": 1}
        )
        d = c.to_dict()
        c2 = SuspensionChoice.from_dict(d)
        assert c2.value == c.value
        assert c2.label == c.label
        assert c2.description == c.description
        assert c2.style == c.style


class TestSuspensionRecordChoices:
    """SuspensionRecord with choices / response_type."""

    def test_default_response_type(self):
        from openintent.models import SuspensionRecord

        rec = SuspensionRecord(id="s1", question="Q")
        assert rec.response_type == "choice"
        assert rec.choices == []

    def test_choices_in_to_dict(self):
        from openintent.models import SuspensionChoice, SuspensionRecord

        rec = SuspensionRecord(
            id="s1",
            question="Pick one",
            response_type="choice",
            choices=[
                SuspensionChoice(value="a", label="Alpha"),
                SuspensionChoice(value="b", label="Beta"),
            ],
        )
        d = rec.to_dict()
        assert d["response_type"] == "choice"
        assert len(d["choices"]) == 2
        assert d["choices"][0]["value"] == "a"
        assert d["choices"][1]["label"] == "Beta"

    def test_from_dict_with_choices(self):
        from openintent.models import SuspensionRecord

        d = {
            "id": "s2",
            "question": "Continue?",
            "response_type": "confirm",
            "choices": [
                {"value": "yes", "label": "Yes"},
                {"value": "no", "label": "No"},
            ],
        }
        rec = SuspensionRecord.from_dict(d)
        assert rec.response_type == "confirm"
        assert len(rec.choices) == 2
        assert rec.choices[0].value == "yes"
        assert rec.choices[1].label == "No"

    def test_valid_values_with_choices(self):
        from openintent.models import SuspensionChoice, SuspensionRecord

        rec = SuspensionRecord(
            id="s3",
            question="Q",
            response_type="choice",
            choices=[
                SuspensionChoice(value="x", label="X"),
                SuspensionChoice(value="y", label="Y"),
            ],
        )
        assert rec.valid_values() == ["x", "y"]

    def test_valid_values_text_type(self):
        from openintent.models import SuspensionRecord

        rec = SuspensionRecord(id="s4", question="Q", response_type="text")
        assert rec.valid_values() is None

    def test_valid_values_form_type(self):
        from openintent.models import SuspensionRecord

        rec = SuspensionRecord(id="s5", question="Q", response_type="form")
        assert rec.valid_values() is None


class TestHITLExports:
    """Verify all HITL symbols are exported from the package."""

    def test_models_exported(self):
        import openintent

        assert hasattr(openintent, "ResponseType")
        assert hasattr(openintent, "SuspensionChoice")
        assert hasattr(openintent, "SuspensionRecord")
        assert hasattr(openintent, "EngagementSignals")
        assert hasattr(openintent, "EngagementDecision")
        assert hasattr(openintent, "InputResponse")

    def test_exceptions_exported(self):
        import openintent

        assert hasattr(openintent, "InputTimeoutError")
        assert hasattr(openintent, "InputCancelledError")

    def test_decorators_exported(self):
        import openintent

        assert hasattr(openintent, "on_input_requested")
        assert hasattr(openintent, "on_input_received")
        assert hasattr(openintent, "on_suspension_expired")
        assert hasattr(openintent, "on_engagement_decision")

    def test_version_is_0_16_0(self):
        import openintent

        assert openintent.__version__ == "0.16.0"
