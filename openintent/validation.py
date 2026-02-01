"""
OpenIntent SDK - Input validation helpers.

Provides validation functions for client-side parameter checking before API calls.
"""

import re
from typing import Any, Optional

from .exceptions import ValidationError as SDKValidationError


class InputValidationError(SDKValidationError):
    """Raised when input validation fails before making an API request."""
    
    def __init__(self, message: str, field: str = None, value: Any = None):
        super().__init__(message, status_code=None, response=None)
        self.field = field
        self.value = value


ValidationError = InputValidationError


def validate_required(value: Any, field_name: str) -> None:
    """Validate that a required field is not None or empty."""
    if value is None:
        raise ValidationError(f"{field_name} is required", field=field_name)
    if isinstance(value, str) and not value.strip():
        raise ValidationError(f"{field_name} cannot be empty", field=field_name, value=value)


def validate_string_length(
    value: str,
    field_name: str,
    min_length: int = None,
    max_length: int = None
) -> None:
    """Validate string length constraints."""
    if value is None:
        return
    
    if min_length is not None and len(value) < min_length:
        raise ValidationError(
            f"{field_name} must be at least {min_length} characters",
            field=field_name,
            value=value
        )
    
    if max_length is not None and len(value) > max_length:
        raise ValidationError(
            f"{field_name} must be at most {max_length} characters",
            field=field_name,
            value=value
        )


def validate_positive_int(value: int, field_name: str) -> None:
    """Validate that a number is a positive integer."""
    if value is None:
        return
    
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValidationError(
            f"{field_name} must be an integer",
            field=field_name,
            value=value
        )
    
    if value <= 0:
        raise ValidationError(
            f"{field_name} must be positive",
            field=field_name,
            value=value
        )


def validate_non_negative(value: float, field_name: str) -> None:
    """Validate that a number is non-negative."""
    if value is None:
        return
    
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValidationError(
            f"{field_name} must be a number",
            field=field_name,
            value=value
        )
    
    if value < 0:
        raise ValidationError(
            f"{field_name} cannot be negative",
            field=field_name,
            value=value
        )


def validate_uuid(value: str, field_name: str) -> None:
    """Validate UUID format."""
    if value is None:
        return
    
    uuid_pattern = re.compile(
        r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
        re.IGNORECASE
    )
    
    if not uuid_pattern.match(value):
        raise ValidationError(
            f"{field_name} must be a valid UUID",
            field=field_name,
            value=value
        )


def validate_url(value: str, field_name: str) -> None:
    """Validate URL format."""
    if value is None:
        return
    
    url_pattern = re.compile(
        r'^https?://'
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'
        r'localhost|'
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
        r'(?::\d+)?'
        r'(?:/?|[/?]\S+)$',
        re.IGNORECASE
    )
    
    if not url_pattern.match(value):
        raise ValidationError(
            f"{field_name} must be a valid URL",
            field=field_name,
            value=value
        )


def validate_email(value: str, field_name: str) -> None:
    """Validate email format."""
    if value is None:
        return
    
    email_pattern = re.compile(
        r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    )
    
    if not email_pattern.match(value):
        raise ValidationError(
            f"{field_name} must be a valid email address",
            field=field_name,
            value=value
        )


def validate_in_list(value: Any, field_name: str, allowed_values: list) -> None:
    """Validate that a value is in a list of allowed values."""
    if value is None:
        return
    
    if value not in allowed_values:
        raise ValidationError(
            f"{field_name} must be one of: {', '.join(str(v) for v in allowed_values)}",
            field=field_name,
            value=value
        )


def validate_dict(value: Any, field_name: str) -> None:
    """Validate that a value is a dictionary."""
    if value is None:
        return
    
    if not isinstance(value, dict):
        raise ValidationError(
            f"{field_name} must be a dictionary",
            field=field_name,
            value=value
        )


def validate_list(value: Any, field_name: str, item_type: type = None) -> None:
    """Validate that a value is a list with optional item type checking."""
    if value is None:
        return
    
    if not isinstance(value, list):
        raise ValidationError(
            f"{field_name} must be a list",
            field=field_name,
            value=value
        )
    
    if item_type is not None:
        for i, item in enumerate(value):
            if not isinstance(item, item_type):
                raise ValidationError(
                    f"{field_name}[{i}] must be of type {item_type.__name__}",
                    field=f"{field_name}[{i}]",
                    value=item
                )


def validate_base64(value: str, field_name: str) -> None:
    """Validate that a string is valid base64."""
    if value is None:
        return
    
    import base64
    try:
        base64.b64decode(value, validate=True)
    except Exception:
        raise ValidationError(
            f"{field_name} must be valid base64 encoded data",
            field=field_name,
            value=value[:50] + "..." if len(value) > 50 else value
        )


def validate_scope(value: str, field_name: str = "scope") -> None:
    """Validate scope format (dot-separated path)."""
    if value is None:
        return
    
    scope_pattern = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)*$')
    
    if not scope_pattern.match(value):
        raise ValidationError(
            f"{field_name} must be a valid dot-separated path (e.g., 'content.draft')",
            field=field_name,
            value=value
        )


def validate_agent_id(value: str, field_name: str = "agent_id") -> None:
    """Validate agent ID format (optional namespace:id pattern)."""
    if value is None:
        return
    
    if not value.strip():
        raise ValidationError(
            f"{field_name} cannot be empty",
            field=field_name,
            value=value
        )
    
    if len(value) > 255:
        raise ValidationError(
            f"{field_name} must be at most 255 characters",
            field=field_name,
            value=value
        )


def validate_intent_create(
    title: str,
    creator: str = None,
    description: str = None,
    constraints: dict = None,
) -> None:
    """Validate parameters for intent creation."""
    validate_required(title, "title")
    validate_string_length(title, "title", min_length=1, max_length=500)
    
    if description is not None:
        validate_string_length(description, "description", max_length=10000)
    
    if creator is not None:
        validate_agent_id(creator, "creator")
    
    if constraints is not None:
        validate_dict(constraints, "constraints")


def validate_lease_acquire(
    intent_id: str,
    agent_id: str,
    scope: str,
    duration_seconds: int,
) -> None:
    """Validate parameters for lease acquisition."""
    validate_required(intent_id, "intent_id")
    validate_required(agent_id, "agent_id")
    validate_required(scope, "scope")
    validate_required(duration_seconds, "duration_seconds")
    
    validate_scope(scope)
    validate_positive_int(duration_seconds, "duration_seconds")
    
    if duration_seconds > 86400:
        raise ValidationError(
            "duration_seconds cannot exceed 86400 (24 hours)",
            field="duration_seconds",
            value=duration_seconds
        )


def validate_cost_record(
    intent_id: str,
    agent_id: str,
    cost_type: str,
    amount: float,
    currency: str = None,
) -> None:
    """Validate parameters for cost recording."""
    validate_required(intent_id, "intent_id")
    validate_required(agent_id, "agent_id")
    validate_required(cost_type, "cost_type")
    validate_required(amount, "amount")
    
    validate_non_negative(amount, "amount")
    
    if currency is not None:
        validate_string_length(currency, "currency", min_length=3, max_length=3)


def validate_subscription(
    intent_id: str,
    subscriber_id: str,
    callback_url: str,
    event_types: list[str] = None,
) -> None:
    """Validate parameters for subscription creation."""
    validate_required(intent_id, "intent_id")
    validate_required(subscriber_id, "subscriber_id")
    validate_required(callback_url, "callback_url")
    
    validate_url(callback_url, "callback_url")
    
    if event_types is not None:
        validate_list(event_types, "event_types", str)
