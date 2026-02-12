"""
OpenIntent Server - Tool Execution Adapters (RFC-0014)

Provides the execution layer that turns grant-validated tool invocations
into real external API calls. The adapter system is designed around three
security principles:

1. **Secret Isolation** — Credentials are injected at execution time and
   never logged, returned in responses, or exposed in error messages.
2. **Bounded Execution** — All external calls enforce strict timeouts,
   response size limits, and URL validation to prevent abuse.
3. **Full Audit Trail** — Every invocation (success or failure) is recorded
   with sanitized request/response metadata for protocol observability.

Architecture:
    ToolExecutionAdapter (base)
      ├── RestToolAdapter      — API key, Bearer, Basic Auth
      ├── OAuth2ToolAdapter    — OAuth2 with token refresh
      └── WebhookToolAdapter   — Simple webhook dispatch

    AdapterRegistry resolves the correct adapter from credential metadata
    or auth_type, falling back to a no-op stub for backward compatibility.
"""

import hashlib
import logging
import re
import time
from dataclasses import dataclass
from ipaddress import ip_address
from typing import Any, Optional
from urllib.parse import urlparse

import httpx

logger = logging.getLogger("openintent.server.tool_adapters")

MAX_RESPONSE_BYTES = 1_048_576  # 1 MB
DEFAULT_TIMEOUT_MS = 30_000  # 30 seconds
MAX_TIMEOUT_MS = 120_000  # 2 minutes
MIN_TIMEOUT_MS = 1_000  # 1 second

BLOCKED_HOSTS = frozenset(
    {
        "localhost",
        "127.0.0.1",
        "0.0.0.0",
        "::1",
        "[::1]",
        "metadata.google.internal",
        "169.254.169.254",
    }
)

ALLOWED_SCHEMES = frozenset({"https", "http"})


# ---------------------------------------------------------------------------
# Result Model
# ---------------------------------------------------------------------------


@dataclass
class ToolExecutionResult:
    """Outcome of a tool execution attempt.

    Fields:
        status: "success" | "error" | "timeout" | "denied"
        result: Sanitized response payload (secrets stripped).
        error: Human-readable error description (no secrets).
        duration_ms: Wall-clock execution time.
        http_status: Upstream HTTP status code (if applicable).
        request_fingerprint: SHA-256 of the outbound request for correlation.
    """

    status: str = "success"
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    duration_ms: int = 0
    http_status: Optional[int] = None
    request_fingerprint: Optional[str] = None


# ---------------------------------------------------------------------------
# Security Utilities
# ---------------------------------------------------------------------------


def _validate_url(url: str, allowed_hosts: Optional[list[str]] = None) -> str:
    """Validate and sanitize a URL before making an external request.

    Raises ValueError on:
      - Non-HTTP(S) schemes
      - Private/loopback/metadata IPs
      - Cloud metadata endpoints
      - Hosts not in the allowlist (when configured)
    """
    parsed = urlparse(url)

    if parsed.scheme not in ALLOWED_SCHEMES:
        raise ValueError(f"Blocked scheme: {parsed.scheme}")

    hostname = (parsed.hostname or "").lower().strip(".")

    if not hostname:
        raise ValueError("Empty hostname")

    if hostname in BLOCKED_HOSTS:
        raise ValueError(f"Blocked host: {hostname}")

    try:
        addr = ip_address(hostname)
        if addr.is_private or addr.is_loopback or addr.is_link_local:
            raise ValueError(f"Blocked private IP: {hostname}")
    except ValueError as e:
        if "Blocked" in str(e):
            raise
        pass

    if allowed_hosts:
        normalized = [h.lower().strip(".") for h in allowed_hosts]
        if hostname not in normalized:
            if not any(hostname.endswith(f".{h}") for h in normalized):
                raise ValueError(f"Host '{hostname}' not in allowlist")

    return url


def _sanitize_for_log(data: Any, depth: int = 0) -> Any:
    """Recursively strip sensitive-looking values from data before logging.

    Keys matching common secret patterns are replaced with "[REDACTED]".
    Limits recursion depth to prevent stack overflow on pathological input.
    """
    if depth > 10:
        return "[TRUNCATED]"

    sensitive_pattern = re.compile(
        r"(secret|password|token|key|auth|credential|api.?key|bearer|access.?token)",
        re.IGNORECASE,
    )

    if isinstance(data, dict):
        sanitized = {}
        for k, v in data.items():
            if sensitive_pattern.search(str(k)):
                sanitized[k] = "[REDACTED]"
            else:
                sanitized[k] = _sanitize_for_log(v, depth + 1)
        return sanitized

    if isinstance(data, list):
        return [_sanitize_for_log(item, depth + 1) for item in data[:100]]

    if isinstance(data, str) and len(data) > 10_000:
        return data[:10_000] + "...[TRUNCATED]"

    return data


def _fingerprint_request(method: str, url: str, body: Any) -> str:
    """Create a SHA-256 fingerprint of the outbound request for correlation.

    The fingerprint captures *what* was sent without including secrets,
    allowing audit log correlation without secret exposure.
    """
    content = f"{method}|{url}|{str(body)[:2000]}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def _clamp_timeout(timeout_ms: Optional[int]) -> float:
    """Clamp timeout to safe bounds and convert to seconds."""
    if timeout_ms is None:
        timeout_ms = DEFAULT_TIMEOUT_MS
    clamped = max(MIN_TIMEOUT_MS, min(timeout_ms, MAX_TIMEOUT_MS))
    return clamped / 1000.0


# ---------------------------------------------------------------------------
# Base Adapter
# ---------------------------------------------------------------------------


class ToolExecutionAdapter:
    """Base class for tool execution adapters.

    Subclasses implement _do_execute() with the actual HTTP call.
    The base class handles:
      - URL validation
      - Timeout enforcement
      - Response size limits
      - Error normalization
      - Request fingerprinting
      - Secret sanitization in results
    """

    async def execute(
        self,
        tool_name: str,
        parameters: dict[str, Any],
        credential_metadata: dict[str, Any],
        credential_secret: dict[str, Any],
        grant_constraints: Optional[dict[str, Any]] = None,
    ) -> ToolExecutionResult:
        """Execute a tool call with full security wrapping.

        Args:
            tool_name: Name of the tool being invoked.
            parameters: Agent-supplied parameters for the tool call.
            credential_metadata: Non-secret config (base_url, endpoints, etc).
            credential_secret: Secret auth material (keys, tokens). Never logged.
            grant_constraints: Optional constraints from the grant (allowed_hosts, etc).

        Returns:
            ToolExecutionResult with sanitized output.
        """
        t0 = time.time()
        try:
            base_url = credential_metadata.get("base_url", "")
            allowed_hosts = (grant_constraints or {}).get("allowed_hosts")
            if base_url:
                _validate_url(base_url, allowed_hosts)

            result = await self._do_execute(
                tool_name,
                parameters,
                credential_metadata,
                credential_secret,
                grant_constraints,
            )

            result.duration_ms = int((time.time() - t0) * 1000)

            if result.result:
                result.result = _sanitize_for_log(result.result)

            return result

        except ValueError as e:
            return ToolExecutionResult(
                status="denied",
                error=f"Security validation failed: {e}",
                duration_ms=int((time.time() - t0) * 1000),
            )
        except httpx.TimeoutException:
            return ToolExecutionResult(
                status="timeout",
                error="External service timed out",
                duration_ms=int((time.time() - t0) * 1000),
            )
        except httpx.ConnectError as e:
            return ToolExecutionResult(
                status="error",
                error=f"Connection failed: {_strip_secrets_from_error(str(e))}",
                duration_ms=int((time.time() - t0) * 1000),
            )
        except Exception as e:
            logger.exception("Tool execution failed")
            return ToolExecutionResult(
                status="error",
                error=f"Execution failed: {_strip_secrets_from_error(str(e))}",
                duration_ms=int((time.time() - t0) * 1000),
            )

    async def _do_execute(
        self,
        tool_name: str,
        parameters: dict[str, Any],
        credential_metadata: dict[str, Any],
        credential_secret: dict[str, Any],
        grant_constraints: Optional[dict[str, Any]] = None,
    ) -> ToolExecutionResult:
        """Override in subclasses to implement actual execution."""
        raise NotImplementedError


def _strip_secrets_from_error(error_str: str) -> str:
    """Remove anything that looks like a secret from error messages."""
    cleaned = re.sub(
        r"(api[_-]?key|token|secret|password|bearer)\s*[=:]\s*\S+",
        r"\1=[REDACTED]",
        error_str,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"[A-Za-z0-9+/]{40,}={0,2}", "[REDACTED]", cleaned)
    return cleaned


# ---------------------------------------------------------------------------
# REST Adapter — API Key / Bearer / Basic Auth
# ---------------------------------------------------------------------------


class RestToolAdapter(ToolExecutionAdapter):
    """Executes tool calls via REST API using injected credentials.

    Supports three auth patterns based on credential auth_type:
      - api_key: Key placed in header or query parameter
      - bearer_token: Authorization: Bearer <token>
      - basic_auth: HTTP Basic Authentication

    Execution config is read from credential_metadata:
      {
        "base_url": "https://api.example.com",
        "endpoints": {
          "tool_name": {
            "path": "/v1/search",
            "method": "POST",          # GET, POST, PUT, DELETE
            "headers": {"X-Custom": "value"},
            "param_mapping": "body"     # "body", "query", "path"
          }
        },
        "auth": {
          "location": "header",         # "header" or "query"
          "header_name": "X-API-Key",   # custom header name
          "query_param": "apikey",      # custom query param name
          "header_prefix": "Bearer"     # prefix for header value
        },
        "timeout_ms": 30000,
        "allowed_hosts": ["api.example.com"]
      }

    Secrets in credential_secret:
      {
        "api_key": "sk-...",
        "username": "user",         # for basic_auth
        "password": "pass"          # for basic_auth
      }
    """

    async def _do_execute(
        self,
        tool_name: str,
        parameters: dict[str, Any],
        credential_metadata: dict[str, Any],
        credential_secret: dict[str, Any],
        grant_constraints: Optional[dict[str, Any]] = None,
    ) -> ToolExecutionResult:
        base_url = credential_metadata.get("base_url", "")
        if not base_url:
            return ToolExecutionResult(
                status="error",
                error="Credential metadata missing 'base_url'",
            )

        endpoints = credential_metadata.get("endpoints", {})
        endpoint_config = endpoints.get(tool_name, {})

        path = endpoint_config.get("path", f"/{tool_name}")
        method = endpoint_config.get("method", "POST").upper()
        extra_headers = endpoint_config.get("headers", {})
        param_mapping = endpoint_config.get("param_mapping", "body")

        url = f"{base_url.rstrip('/')}{path}"
        allowed_hosts = (grant_constraints or {}).get(
            "allowed_hosts",
            credential_metadata.get("allowed_hosts"),
        )
        _validate_url(url, allowed_hosts)

        auth_config = credential_metadata.get("auth", {})
        auth_type = credential_metadata.get("auth_type", "api_key")

        headers = {"User-Agent": "OpenIntent-Server/1.0"}
        headers.update(extra_headers)
        query_params: dict[str, Any] = {}
        auth_tuple = None

        if auth_type in ("api_key", "bearer_token"):
            secret_value = credential_secret.get(
                "api_key",
                credential_secret.get("token", ""),
            )
            location = auth_config.get("location", "header")

            if location == "header":
                header_name = auth_config.get("header_name", "Authorization")
                prefix = auth_config.get("header_prefix", "")
                if auth_type == "bearer_token" and not prefix:
                    prefix = "Bearer"
                if prefix:
                    headers[header_name] = f"{prefix} {secret_value}"
                else:
                    headers[header_name] = secret_value
            elif location == "query":
                param_name = auth_config.get("query_param", "api_key")
                query_params[param_name] = secret_value

        elif auth_type == "basic_auth":
            username = credential_secret.get("username", "")
            password = credential_secret.get("password", "")
            auth_tuple = (username, password)

        timeout = _clamp_timeout(credential_metadata.get("timeout_ms"))
        fingerprint = _fingerprint_request(method, url, parameters)

        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=False,
            max_redirects=0,
        ) as client:
            kwargs: dict[str, Any] = {
                "method": method,
                "url": url,
                "headers": headers,
                "params": query_params if query_params else None,
            }
            if auth_tuple:
                kwargs["auth"] = auth_tuple

            if method in ("POST", "PUT", "PATCH"):
                if param_mapping == "body":
                    kwargs["json"] = parameters
                elif param_mapping == "query":
                    kwargs["params"] = {**(query_params or {}), **parameters}
            elif method == "GET":
                kwargs["params"] = {**(query_params or {}), **parameters}

            response = await client.request(**kwargs)

        if len(response.content) > MAX_RESPONSE_BYTES:
            return ToolExecutionResult(
                status="error",
                error=f"Response too large: {len(response.content)} bytes (limit: {MAX_RESPONSE_BYTES})",
                http_status=response.status_code,
                duration_ms=0,
                request_fingerprint=fingerprint,
            )

        try:
            response_data = response.json()
        except Exception:
            response_data = {"raw": response.text[:5000]}

        if response.is_success:
            return ToolExecutionResult(
                status="success",
                result=response_data,
                http_status=response.status_code,
                request_fingerprint=fingerprint,
            )
        else:
            return ToolExecutionResult(
                status="error",
                result=_sanitize_for_log(response_data),
                error=f"Upstream returned HTTP {response.status_code}",
                http_status=response.status_code,
                request_fingerprint=fingerprint,
            )


# ---------------------------------------------------------------------------
# OAuth2 Adapter — Token Refresh + Bearer Execution
# ---------------------------------------------------------------------------


class OAuth2ToolAdapter(ToolExecutionAdapter):
    """Executes tool calls using OAuth2 credentials with automatic token refresh.

    Builds on RestToolAdapter's execution logic but adds:
      - Automatic token refresh on 401 responses
      - Token refresh via client_credentials or refresh_token grant

    Secrets in credential_secret:
      {
        "access_token": "eyJ...",
        "refresh_token": "dGhp...",    # optional
        "client_id": "abc",
        "client_secret": "xyz"
      }

    Additional credential_metadata fields:
      {
        "token_url": "https://auth.example.com/oauth/token",
        "token_grant_type": "client_credentials"  # or "refresh_token"
      }
    """

    async def _do_execute(
        self,
        tool_name: str,
        parameters: dict[str, Any],
        credential_metadata: dict[str, Any],
        credential_secret: dict[str, Any],
        grant_constraints: Optional[dict[str, Any]] = None,
    ) -> ToolExecutionResult:
        access_token = credential_secret.get("access_token", "")
        if not access_token:
            return ToolExecutionResult(
                status="error",
                error="OAuth2 credential missing 'access_token'",
            )

        result = await self._execute_with_token(
            tool_name,
            parameters,
            credential_metadata,
            credential_secret,
            access_token,
            grant_constraints,
        )

        if result.http_status == 401 and self._can_refresh(
            credential_metadata, credential_secret
        ):
            new_token = await self._refresh_token(
                credential_metadata, credential_secret
            )
            if new_token:
                result = await self._execute_with_token(
                    tool_name,
                    parameters,
                    credential_metadata,
                    credential_secret,
                    new_token,
                    grant_constraints,
                )
                if result.status == "success":
                    result.result = result.result or {}
                    result.result["_refreshed"] = True

        return result

    async def _execute_with_token(
        self,
        tool_name: str,
        parameters: dict[str, Any],
        credential_metadata: dict[str, Any],
        credential_secret: dict[str, Any],
        access_token: str,
        grant_constraints: Optional[dict[str, Any]] = None,
    ) -> ToolExecutionResult:
        patched_metadata = {**credential_metadata, "auth_type": "bearer_token"}
        patched_secret = {**credential_secret, "token": access_token}

        rest_adapter = RestToolAdapter()
        return await rest_adapter._do_execute(
            tool_name, parameters, patched_metadata, patched_secret, grant_constraints
        )

    def _can_refresh(
        self,
        credential_metadata: dict[str, Any],
        credential_secret: dict[str, Any],
    ) -> bool:
        token_url = credential_metadata.get("token_url")
        has_client_creds = credential_secret.get("client_id") and credential_secret.get(
            "client_secret"
        )
        has_refresh_token = bool(credential_secret.get("refresh_token"))
        return bool(token_url and (has_client_creds or has_refresh_token))

    async def _refresh_token(
        self,
        credential_metadata: dict[str, Any],
        credential_secret: dict[str, Any],
    ) -> Optional[str]:
        token_url = credential_metadata.get("token_url", "")
        if not token_url:
            return None

        try:
            _validate_url(token_url)
        except ValueError:
            logger.warning("Token URL blocked by security validation")
            return None

        grant_type = credential_metadata.get("token_grant_type", "client_credentials")
        timeout = _clamp_timeout(credential_metadata.get("timeout_ms"))

        payload: dict[str, str] = {"grant_type": grant_type}

        if grant_type == "refresh_token":
            refresh_token = credential_secret.get("refresh_token", "")
            if not refresh_token:
                return None
            payload["refresh_token"] = refresh_token

        client_id = credential_secret.get("client_id", "")
        client_secret = credential_secret.get("client_secret", "")

        try:
            async with httpx.AsyncClient(
                timeout=timeout,
                follow_redirects=False,
                max_redirects=0,
            ) as client:
                response = await client.post(
                    token_url,
                    data=payload,
                    auth=(client_id, client_secret) if client_id else None,
                    headers={"User-Agent": "OpenIntent-Server/1.0"},
                )

            if response.is_success:
                data = response.json()
                return data.get("access_token")
            else:
                logger.warning(f"Token refresh failed: HTTP {response.status_code}")
                return None
        except Exception as e:
            logger.warning(f"Token refresh error: {_strip_secrets_from_error(str(e))}")
            return None


# ---------------------------------------------------------------------------
# Webhook Adapter — Simple POST dispatch
# ---------------------------------------------------------------------------


class WebhookToolAdapter(ToolExecutionAdapter):
    """Dispatches tool calls as webhook POST requests.

    Minimal adapter for services that accept a standardized webhook payload.
    Wraps tool_name + parameters into a structured body and POSTs to the
    configured webhook URL.

    credential_metadata:
      {
        "base_url": "https://hooks.example.com/openintent",
        "timeout_ms": 10000
      }

    credential_secret:
      {
        "signing_secret": "whsec_..."    # optional HMAC signing
      }
    """

    async def _do_execute(
        self,
        tool_name: str,
        parameters: dict[str, Any],
        credential_metadata: dict[str, Any],
        credential_secret: dict[str, Any],
        grant_constraints: Optional[dict[str, Any]] = None,
    ) -> ToolExecutionResult:
        webhook_url = credential_metadata.get("base_url", "")
        if not webhook_url:
            return ToolExecutionResult(
                status="error",
                error="Webhook credential missing 'base_url'",
            )

        allowed_hosts = (grant_constraints or {}).get(
            "allowed_hosts",
            credential_metadata.get("allowed_hosts"),
        )
        _validate_url(webhook_url, allowed_hosts)

        payload = {
            "tool_name": tool_name,
            "parameters": parameters,
            "timestamp": time.time(),
        }

        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "User-Agent": "OpenIntent-Server/1.0",
        }

        signing_secret = credential_secret.get("signing_secret")
        if signing_secret:
            import hmac
            import json as json_mod

            body_bytes = json_mod.dumps(payload, sort_keys=True).encode()
            signature = hmac.new(
                signing_secret.encode(), body_bytes, hashlib.sha256
            ).hexdigest()
            headers["X-OpenIntent-Signature"] = f"sha256={signature}"

        timeout = _clamp_timeout(credential_metadata.get("timeout_ms"))
        fingerprint = _fingerprint_request("POST", webhook_url, payload)

        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=False,
            max_redirects=0,
        ) as client:
            response = await client.post(
                webhook_url,
                json=payload,
                headers=headers,
            )

        if len(response.content) > MAX_RESPONSE_BYTES:
            return ToolExecutionResult(
                status="error",
                error=f"Response too large: {len(response.content)} bytes",
                http_status=response.status_code,
                request_fingerprint=fingerprint,
            )

        try:
            response_data = response.json()
        except Exception:
            response_data = {"raw": response.text[:5000]}

        if response.is_success:
            return ToolExecutionResult(
                status="success",
                result=response_data,
                http_status=response.status_code,
                request_fingerprint=fingerprint,
            )
        else:
            return ToolExecutionResult(
                status="error",
                result=_sanitize_for_log(response_data),
                error=f"Webhook returned HTTP {response.status_code}",
                http_status=response.status_code,
                request_fingerprint=fingerprint,
            )


# ---------------------------------------------------------------------------
# Adapter Registry
# ---------------------------------------------------------------------------


_ADAPTERS: dict[str, ToolExecutionAdapter] = {
    "rest": RestToolAdapter(),
    "api_key": RestToolAdapter(),
    "bearer_token": RestToolAdapter(),
    "basic_auth": RestToolAdapter(),
    "oauth2_token": OAuth2ToolAdapter(),
    "oauth2_client_credentials": OAuth2ToolAdapter(),
    "webhook": WebhookToolAdapter(),
}


def register_adapter(name: str, adapter: ToolExecutionAdapter) -> None:
    """Register a custom tool execution adapter."""
    _ADAPTERS[name] = adapter


def resolve_adapter(
    credential_metadata: dict[str, Any],
    auth_type: str,
) -> Optional[ToolExecutionAdapter]:
    """Resolve the appropriate adapter for a credential.

    Resolution order:
      1. Explicit 'adapter' key in credential_metadata
      2. auth_type of the credential
      3. None (fall back to stub behavior)

    Returns None when no execution config is present, signaling the
    endpoint to use the backward-compatible placeholder response.
    """
    explicit = credential_metadata.get("adapter")
    if explicit and explicit in _ADAPTERS:
        return _ADAPTERS[explicit]

    if credential_metadata.get("base_url"):
        if auth_type in _ADAPTERS:
            return _ADAPTERS[auth_type]

    return None
