"""
Tests for OpenIntent SDK validation module.
"""

import pytest

from openintent.exceptions import ValidationError as SDKValidationError
from openintent.validation import (
    InputValidationError,
    validate_agent_id,
    validate_cost_record,
    validate_intent_create,
    validate_lease_acquire,
    validate_non_negative,
    validate_positive_int,
    validate_required,
    validate_scope,
    validate_string_length,
    validate_subscription,
    validate_url,
    validate_uuid,
)


class TestExceptionInheritance:
    """Tests that InputValidationError inherits from SDK ValidationError."""

    def test_inherits_from_sdk_validation_error(self):
        assert issubclass(InputValidationError, SDKValidationError)

    def test_caught_by_sdk_validation_error(self):
        with pytest.raises(SDKValidationError):
            raise InputValidationError("test error", field="test")


class TestValidateRequired:
    """Tests for validate_required function."""

    def test_none_value_raises(self):
        with pytest.raises(InputValidationError) as exc:
            validate_required(None, "field")
        assert "field is required" in str(exc.value)
        assert exc.value.field == "field"

    def test_empty_string_raises(self):
        with pytest.raises(InputValidationError) as exc:
            validate_required("", "field")
        assert "cannot be empty" in str(exc.value)

    def test_whitespace_only_raises(self):
        with pytest.raises(InputValidationError) as exc:
            validate_required("   ", "field")
        assert "cannot be empty" in str(exc.value)

    def test_valid_string_passes(self):
        validate_required("value", "field")

    def test_valid_number_passes(self):
        validate_required(123, "field")

    def test_zero_passes(self):
        validate_required(0, "field")

    def test_false_passes(self):
        validate_required(False, "field")


class TestValidateStringLength:
    """Tests for validate_string_length function."""

    def test_none_passes(self):
        validate_string_length(None, "field", min_length=5)

    def test_min_length_raises(self):
        with pytest.raises(InputValidationError) as exc:
            validate_string_length("ab", "field", min_length=5)
        assert "at least 5 characters" in str(exc.value)

    def test_max_length_raises(self):
        with pytest.raises(InputValidationError) as exc:
            validate_string_length("abcdefghij", "field", max_length=5)
        assert "at most 5 characters" in str(exc.value)

    def test_within_bounds_passes(self):
        validate_string_length("hello", "field", min_length=3, max_length=10)

    def test_exact_min_passes(self):
        validate_string_length("abc", "field", min_length=3)

    def test_exact_max_passes(self):
        validate_string_length("abc", "field", max_length=3)


class TestValidatePositiveInt:
    """Tests for validate_positive_int function."""

    def test_none_passes(self):
        validate_positive_int(None, "field")

    def test_negative_raises(self):
        with pytest.raises(InputValidationError) as exc:
            validate_positive_int(-5, "field")
        assert "must be positive" in str(exc.value)

    def test_zero_raises(self):
        with pytest.raises(InputValidationError) as exc:
            validate_positive_int(0, "field")
        assert "must be positive" in str(exc.value)

    def test_positive_passes(self):
        validate_positive_int(5, "field")

    def test_float_raises(self):
        with pytest.raises(InputValidationError) as exc:
            validate_positive_int(5.5, "field")
        assert "must be an integer" in str(exc.value)

    def test_bool_raises(self):
        with pytest.raises(InputValidationError) as exc:
            validate_positive_int(True, "field")
        assert "must be an integer" in str(exc.value)


class TestValidateNonNegative:
    """Tests for validate_non_negative function."""

    def test_none_passes(self):
        validate_non_negative(None, "field")

    def test_negative_raises(self):
        with pytest.raises(InputValidationError) as exc:
            validate_non_negative(-0.01, "field")
        assert "cannot be negative" in str(exc.value)

    def test_zero_passes(self):
        validate_non_negative(0, "field")

    def test_positive_int_passes(self):
        validate_non_negative(5, "field")

    def test_positive_float_passes(self):
        validate_non_negative(5.5, "field")


class TestValidateUuid:
    """Tests for validate_uuid function."""

    def test_none_passes(self):
        validate_uuid(None, "field")

    def test_valid_uuid_passes(self):
        validate_uuid("550e8400-e29b-41d4-a716-446655440000", "field")

    def test_uppercase_uuid_passes(self):
        validate_uuid("550E8400-E29B-41D4-A716-446655440000", "field")

    def test_invalid_uuid_raises(self):
        with pytest.raises(InputValidationError) as exc:
            validate_uuid("not-a-uuid", "field")
        assert "valid UUID" in str(exc.value)

    def test_short_uuid_raises(self):
        with pytest.raises(InputValidationError) as exc:
            validate_uuid("550e8400-e29b-41d4", "field")
        assert "valid UUID" in str(exc.value)


class TestValidateUrl:
    """Tests for validate_url function."""

    def test_none_passes(self):
        validate_url(None, "field")

    def test_http_url_passes(self):
        validate_url("http://example.com", "field")

    def test_https_url_passes(self):
        validate_url("https://example.com/path", "field")

    def test_localhost_passes(self):
        validate_url("http://localhost:8000/api", "field")

    def test_ip_address_passes(self):
        validate_url("http://192.168.1.1:5000", "field")

    def test_invalid_url_raises(self):
        with pytest.raises(InputValidationError) as exc:
            validate_url("not-a-url", "field")
        assert "valid URL" in str(exc.value)

    def test_no_protocol_raises(self):
        with pytest.raises(InputValidationError) as exc:
            validate_url("example.com", "field")
        assert "valid URL" in str(exc.value)


class TestValidateScope:
    """Tests for validate_scope function."""

    def test_none_passes(self):
        validate_scope(None)

    def test_simple_scope_passes(self):
        validate_scope("research")

    def test_dotted_scope_passes(self):
        validate_scope("content.draft")

    def test_deep_scope_passes(self):
        validate_scope("section.chapter.paragraph")

    def test_underscores_passes(self):
        validate_scope("user_data.profile_info")

    def test_numeric_suffix_passes(self):
        validate_scope("section1.part2")

    def test_starts_with_number_raises(self):
        with pytest.raises(InputValidationError) as exc:
            validate_scope("1invalid")
        assert "dot-separated path" in str(exc.value)

    def test_special_chars_raises(self):
        with pytest.raises(InputValidationError) as exc:
            validate_scope("content-draft")
        assert "dot-separated path" in str(exc.value)


class TestValidateAgentId:
    """Tests for validate_agent_id function."""

    def test_none_passes(self):
        validate_agent_id(None)

    def test_simple_id_passes(self):
        validate_agent_id("agent-1")

    def test_namespaced_id_passes(self):
        validate_agent_id("user:alice")

    def test_complex_id_passes(self):
        validate_agent_id("agent:research-assistant-v2")

    def test_empty_raises(self):
        with pytest.raises(InputValidationError) as exc:
            validate_agent_id("")
        assert "cannot be empty" in str(exc.value)

    def test_too_long_raises(self):
        with pytest.raises(InputValidationError) as exc:
            validate_agent_id("a" * 256)
        assert "at most 255 characters" in str(exc.value)


class TestValidateIntentCreate:
    """Tests for validate_intent_create function."""

    def test_valid_minimal(self):
        validate_intent_create(title="Test")

    def test_valid_full(self):
        validate_intent_create(
            title="Test Intent",
            creator="user:alice",
            description="A test intent",
            constraints={"deadline": "2024-01-01"},
        )

    def test_empty_title_raises(self):
        with pytest.raises(InputValidationError) as exc:
            validate_intent_create(title="")
        assert "title" in str(exc.value).lower()

    def test_title_too_long_raises(self):
        with pytest.raises(InputValidationError) as exc:
            validate_intent_create(title="x" * 501)
        assert "500 characters" in str(exc.value)

    def test_description_too_long_raises(self):
        with pytest.raises(InputValidationError) as exc:
            validate_intent_create(title="Test", description="x" * 10001)
        assert "10000 characters" in str(exc.value)

    def test_invalid_constraints_raises(self):
        with pytest.raises(InputValidationError) as exc:
            validate_intent_create(title="Test", constraints="not-a-dict")
        assert "dictionary" in str(exc.value)


class TestValidateLeaseAcquire:
    """Tests for validate_lease_acquire function."""

    def test_valid(self):
        validate_lease_acquire(
            intent_id="123", agent_id="agent:1", scope="research", duration_seconds=300
        )

    def test_missing_intent_id_raises(self):
        with pytest.raises(InputValidationError) as exc:
            validate_lease_acquire(
                intent_id=None, agent_id="agent", scope="scope", duration_seconds=300
            )
        assert "intent_id is required" in str(exc.value)

    def test_invalid_scope_raises(self):
        with pytest.raises(InputValidationError) as exc:
            validate_lease_acquire(
                intent_id="123",
                agent_id="agent",
                scope="invalid-scope",
                duration_seconds=300,
            )
        assert "dot-separated path" in str(exc.value)

    def test_negative_duration_raises(self):
        with pytest.raises(InputValidationError) as exc:
            validate_lease_acquire(
                intent_id="123", agent_id="agent", scope="scope", duration_seconds=-1
            )
        assert "positive" in str(exc.value)

    def test_too_long_duration_raises(self):
        with pytest.raises(InputValidationError) as exc:
            validate_lease_acquire(
                intent_id="123",
                agent_id="agent",
                scope="scope",
                duration_seconds=100000,
            )
        assert "86400" in str(exc.value)


class TestValidateCostRecord:
    """Tests for validate_cost_record function."""

    def test_valid(self):
        validate_cost_record(
            intent_id="123",
            agent_id="agent:1",
            cost_type="api_call",
            amount=0.05,
            currency="USD",
        )

    def test_negative_amount_raises(self):
        with pytest.raises(InputValidationError) as exc:
            validate_cost_record(
                intent_id="123", agent_id="agent", cost_type="api_call", amount=-0.01
            )
        assert "negative" in str(exc.value)

    def test_invalid_currency_raises(self):
        with pytest.raises(InputValidationError) as exc:
            validate_cost_record(
                intent_id="123",
                agent_id="agent",
                cost_type="api_call",
                amount=1.0,
                currency="DOLLAR",
            )
        assert "3 characters" in str(exc.value)


class TestValidateSubscription:
    """Tests for validate_subscription function."""

    def test_valid(self):
        validate_subscription(
            intent_id="123",
            subscriber_id="service:dashboard",
            callback_url="https://example.com/webhook",
            event_types=["state_patched", "status_changed"],
        )

    def test_invalid_callback_url_raises(self):
        with pytest.raises(InputValidationError) as exc:
            validate_subscription(
                intent_id="123", subscriber_id="service", callback_url="not-a-url"
            )
        assert "valid URL" in str(exc.value)

    def test_missing_subscriber_id_raises(self):
        with pytest.raises(InputValidationError) as exc:
            validate_subscription(
                intent_id="123", subscriber_id=None, callback_url="https://example.com"
            )
        assert "subscriber_id is required" in str(exc.value)
