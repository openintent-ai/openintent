"""
OpenIntent SDK - Custom exceptions for error handling.
"""

from typing import Any, Optional


class OpenIntentError(Exception):
    """Base exception for all OpenIntent SDK errors."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response = response


class NotFoundError(OpenIntentError):
    """Raised when a requested resource is not found."""

    pass


class ConflictError(OpenIntentError):
    """Raised when there's a version conflict during optimistic concurrency control."""

    def __init__(self, message: str, current_version: Optional[int] = None, **kwargs: Any) -> None:
        super().__init__(message, **kwargs)
        self.current_version = current_version


class LeaseConflictError(OpenIntentError):
    """Raised when attempting to acquire a lease that's already held."""

    def __init__(
        self,
        message: str,
        existing_lease: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)
        self.existing_lease = existing_lease


class ValidationError(OpenIntentError):
    """Raised when request validation fails."""

    def __init__(self, message: str, errors: Optional[list[Any]] = None, **kwargs: Any) -> None:
        super().__init__(message, **kwargs)
        self.errors = errors or []


class APIError(OpenIntentError):
    """Raised when an API request fails with an unexpected error."""

    pass


class AuthenticationError(OpenIntentError):
    """Raised when authentication fails or API key is invalid."""

    pass
