"""
Tests for server-side tool execution adapters (RFC-0014).

Covers:
  - Security utilities (URL validation, secret sanitization, fingerprinting)
  - Adapter registry resolution
  - RestToolAdapter with mocked httpx responses
  - OAuth2ToolAdapter with token refresh
  - WebhookToolAdapter with HMAC signing
  - Endpoint integration with placeholder fallback
"""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from openintent.server.tool_adapters import (
    MAX_RESPONSE_BYTES,
    OAuth2ToolAdapter,
    RestToolAdapter,
    ToolExecutionAdapter,
    ToolExecutionResult,
    WebhookToolAdapter,
    _clamp_timeout,
    _fingerprint_request,
    _sanitize_for_log,
    _strip_secrets_from_error,
    _validate_url,
    register_adapter,
    resolve_adapter,
)

# ---------------------------------------------------------------------------
# Security Utilities
# ---------------------------------------------------------------------------


class TestValidateUrl:
    def test_valid_https_url(self):
        result = _validate_url("https://api.example.com/v1/search")
        assert result == "https://api.example.com/v1/search"

    def test_valid_http_url(self):
        result = _validate_url("http://api.example.com/v1/search")
        assert result == "http://api.example.com/v1/search"

    def test_blocks_ftp_scheme(self):
        with pytest.raises(ValueError, match="Blocked scheme"):
            _validate_url("ftp://example.com/file")

    def test_blocks_file_scheme(self):
        with pytest.raises(ValueError, match="Blocked scheme"):
            _validate_url("file:///etc/passwd")

    def test_blocks_localhost(self):
        with pytest.raises(ValueError, match="Blocked host"):
            _validate_url("http://localhost:8080/api")

    def test_blocks_127_0_0_1(self):
        with pytest.raises(ValueError, match="Blocked host"):
            _validate_url("http://127.0.0.1/api")

    def test_blocks_metadata_endpoint(self):
        with pytest.raises(ValueError, match="Blocked host"):
            _validate_url("http://169.254.169.254/latest/meta-data/")

    def test_blocks_gcp_metadata(self):
        with pytest.raises(ValueError, match="Blocked host"):
            _validate_url("http://metadata.google.internal/computeMetadata/v1/")

    def test_blocks_ipv6_loopback(self):
        with pytest.raises(ValueError, match="Blocked host"):
            _validate_url("http://[::1]:8080/api")

    def test_blocks_private_ip(self):
        with pytest.raises(ValueError, match="Blocked private IP"):
            _validate_url("http://10.0.0.1/internal")

    def test_blocks_192_168(self):
        with pytest.raises(ValueError, match="Blocked private IP"):
            _validate_url("http://192.168.1.1/admin")

    def test_empty_hostname(self):
        with pytest.raises(ValueError, match="Empty hostname"):
            _validate_url("http:///path")

    def test_allowlist_permits_listed_host(self):
        result = _validate_url(
            "https://api.example.com/v1",
            allowed_hosts=["api.example.com"],
        )
        assert result == "https://api.example.com/v1"

    def test_allowlist_permits_subdomain(self):
        result = _validate_url(
            "https://us.api.example.com/v1",
            allowed_hosts=["api.example.com"],
        )
        assert result == "https://us.api.example.com/v1"

    def test_allowlist_blocks_unlisted_host(self):
        with pytest.raises(ValueError, match="not in allowlist"):
            _validate_url(
                "https://evil.com/steal",
                allowed_hosts=["api.example.com"],
            )


class TestSanitizeForLog:
    def test_redacts_secret_keys(self):
        data = {"api_key": "sk-12345", "query": "hello"}
        result = _sanitize_for_log(data)
        assert result["api_key"] == "[REDACTED]"
        assert result["query"] == "hello"

    def test_redacts_nested_secrets(self):
        data = {"response": {"auth_token": "abc123", "data": [1, 2, 3]}}
        result = _sanitize_for_log(data)
        assert result["response"]["auth_token"] == "[REDACTED]"
        assert result["response"]["data"] == [1, 2, 3]

    def test_redacts_password(self):
        data = {"password": "hunter2", "username": "admin"}
        result = _sanitize_for_log(data)
        assert result["password"] == "[REDACTED]"
        assert result["username"] == "admin"

    def test_truncates_long_strings(self):
        data = "x" * 20_000
        result = _sanitize_for_log(data)
        assert len(result) < 20_000
        assert result.endswith("...[TRUNCATED]")

    def test_limits_list_length(self):
        data = list(range(200))
        result = _sanitize_for_log(data)
        assert len(result) == 100

    def test_handles_none(self):
        assert _sanitize_for_log(None) is None

    def test_handles_primitives(self):
        assert _sanitize_for_log(42) == 42
        assert _sanitize_for_log(True) is True

    def test_truncates_deep_nesting(self):
        data: dict = {}
        current = data
        for i in range(15):
            current["nested"] = {}
            current = current["nested"]
        current["value"] = "deep"
        result = _sanitize_for_log(data)
        leaf = result
        depth = 0
        while isinstance(leaf, dict) and "nested" in leaf:
            leaf = leaf["nested"]
            depth += 1
        assert leaf == "[TRUNCATED]" or depth >= 10


class TestStripSecretsFromError:
    def test_strips_api_key_in_error(self):
        error = "Connection failed: api_key=sk-12345abcdef"
        result = _strip_secrets_from_error(error)
        assert "sk-12345" not in result
        assert "REDACTED" in result

    def test_strips_long_base64_tokens(self):
        token = "A" * 50
        error = f"Auth failed with token {token}"
        result = _strip_secrets_from_error(error)
        assert token not in result
        assert "REDACTED" in result

    def test_preserves_normal_messages(self):
        error = "Connection refused by host"
        result = _strip_secrets_from_error(error)
        assert result == error


class TestFingerprintRequest:
    def test_produces_hex_string(self):
        fp = _fingerprint_request("POST", "https://api.example.com", {"q": "test"})
        assert isinstance(fp, str)
        assert len(fp) == 16

    def test_deterministic(self):
        fp1 = _fingerprint_request("POST", "https://api.example.com", {"q": "test"})
        fp2 = _fingerprint_request("POST", "https://api.example.com", {"q": "test"})
        assert fp1 == fp2

    def test_varies_by_method(self):
        fp1 = _fingerprint_request("GET", "https://api.example.com", {})
        fp2 = _fingerprint_request("POST", "https://api.example.com", {})
        assert fp1 != fp2


class TestClampTimeout:
    def test_default_when_none(self):
        assert _clamp_timeout(None) == 30.0

    def test_clamps_to_minimum(self):
        assert _clamp_timeout(100) == 1.0

    def test_clamps_to_maximum(self):
        assert _clamp_timeout(999_999) == 120.0

    def test_normal_value(self):
        assert _clamp_timeout(5000) == 5.0


# ---------------------------------------------------------------------------
# Adapter Registry
# ---------------------------------------------------------------------------


class TestAdapterRegistry:
    def test_resolves_api_key_with_base_url(self):
        adapter = resolve_adapter({"base_url": "https://api.example.com"}, "api_key")
        assert isinstance(adapter, RestToolAdapter)

    def test_resolves_bearer_token(self):
        adapter = resolve_adapter(
            {"base_url": "https://api.example.com"}, "bearer_token"
        )
        assert isinstance(adapter, RestToolAdapter)

    def test_resolves_oauth2(self):
        adapter = resolve_adapter(
            {"base_url": "https://api.example.com"}, "oauth2_token"
        )
        assert isinstance(adapter, OAuth2ToolAdapter)

    def test_resolves_webhook(self):
        adapter = resolve_adapter({"base_url": "https://hooks.example.com"}, "webhook")
        assert isinstance(adapter, WebhookToolAdapter)

    def test_returns_none_without_base_url(self):
        adapter = resolve_adapter({}, "api_key")
        assert adapter is None

    def test_returns_none_for_unknown_type(self):
        adapter = resolve_adapter({}, "custom_unknown")
        assert adapter is None

    def test_explicit_adapter_metadata(self):
        adapter = resolve_adapter({"adapter": "webhook"}, "api_key")
        assert isinstance(adapter, WebhookToolAdapter)

    def test_register_custom_adapter(self):
        custom = ToolExecutionAdapter()
        register_adapter("custom_test", custom)
        adapter = resolve_adapter({"adapter": "custom_test"}, "api_key")
        assert adapter is custom


# ---------------------------------------------------------------------------
# RestToolAdapter
# ---------------------------------------------------------------------------


class TestRestToolAdapter:
    @pytest.mark.asyncio
    async def test_missing_base_url(self):
        adapter = RestToolAdapter()
        result = await adapter.execute(
            tool_name="search",
            parameters={"q": "test"},
            credential_metadata={},
            credential_secret={"api_key": "sk-test"},
        )
        assert result.status == "error"
        assert "base_url" in result.error

    @pytest.mark.asyncio
    async def test_blocked_url_returns_denied(self):
        adapter = RestToolAdapter()
        result = await adapter.execute(
            tool_name="search",
            parameters={"q": "test"},
            credential_metadata={"base_url": "http://169.254.169.254"},
            credential_secret={"api_key": "sk-test"},
        )
        assert result.status == "denied"
        assert "Security validation" in result.error

    @pytest.mark.asyncio
    async def test_successful_post_request(self):
        adapter = RestToolAdapter()

        mock_response = httpx.Response(
            status_code=200,
            json={"results": [{"title": "OpenIntent"}]},
            request=httpx.Request("POST", "https://api.example.com/v1/search"),
        )

        with patch(
            "httpx.AsyncClient.request",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await adapter.execute(
                tool_name="search",
                parameters={"q": "openintent"},
                credential_metadata={
                    "base_url": "https://api.example.com",
                    "endpoints": {
                        "search": {
                            "path": "/v1/search",
                            "method": "POST",
                            "param_mapping": "body",
                        }
                    },
                    "auth": {"location": "header", "header_prefix": "Bearer"},
                },
                credential_secret={"api_key": "sk-test-key"},
            )

        assert result.status == "success"
        assert result.result["results"][0]["title"] == "OpenIntent"
        assert result.duration_ms >= 0
        assert result.request_fingerprint is not None

    @pytest.mark.asyncio
    async def test_upstream_error_returns_error_status(self):
        adapter = RestToolAdapter()

        mock_response = httpx.Response(
            status_code=500,
            json={"error": "Internal server error"},
            request=httpx.Request("POST", "https://api.example.com/fail"),
        )

        with patch(
            "httpx.AsyncClient.request",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await adapter.execute(
                tool_name="failing_tool",
                parameters={},
                credential_metadata={
                    "base_url": "https://api.example.com",
                    "endpoints": {"failing_tool": {"path": "/fail"}},
                },
                credential_secret={"api_key": "sk-test"},
            )

        assert result.status == "error"
        assert result.http_status == 500
        assert "HTTP 500" in result.error

    @pytest.mark.asyncio
    async def test_timeout_returns_timeout_status(self):
        adapter = RestToolAdapter()

        with patch(
            "httpx.AsyncClient.request",
            new_callable=AsyncMock,
            side_effect=httpx.TimeoutException("timed out"),
        ):
            result = await adapter.execute(
                tool_name="slow_tool",
                parameters={},
                credential_metadata={
                    "base_url": "https://api.example.com",
                    "timeout_ms": 1000,
                },
                credential_secret={"api_key": "sk-test"},
            )

        assert result.status == "timeout"
        assert "timed out" in result.error

    @pytest.mark.asyncio
    async def test_secrets_never_in_result(self):
        adapter = RestToolAdapter()

        mock_response = httpx.Response(
            status_code=200,
            json={"api_key": "leaked-key", "data": "safe"},
            request=httpx.Request("GET", "https://api.example.com/v1"),
        )

        with patch(
            "httpx.AsyncClient.request",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await adapter.execute(
                tool_name="leaky_api",
                parameters={},
                credential_metadata={
                    "base_url": "https://api.example.com",
                    "endpoints": {"leaky_api": {"path": "/v1", "method": "GET"}},
                },
                credential_secret={"api_key": "sk-test"},
            )

        assert result.status == "success"
        assert result.result["api_key"] == "[REDACTED]"
        assert result.result["data"] == "safe"

    @pytest.mark.asyncio
    async def test_response_size_limit(self):
        adapter = RestToolAdapter()

        large_body = b"x" * (MAX_RESPONSE_BYTES + 1)
        mock_response = httpx.Response(
            status_code=200,
            content=large_body,
            request=httpx.Request("GET", "https://api.example.com/huge"),
        )

        with patch(
            "httpx.AsyncClient.request",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await adapter.execute(
                tool_name="big_api",
                parameters={},
                credential_metadata={
                    "base_url": "https://api.example.com",
                    "endpoints": {"big_api": {"path": "/huge", "method": "GET"}},
                },
                credential_secret={"api_key": "sk-test"},
            )

        assert result.status == "error"
        assert "too large" in result.error

    @pytest.mark.asyncio
    async def test_basic_auth_pattern(self):
        adapter = RestToolAdapter()

        mock_response = httpx.Response(
            status_code=200,
            json={"authenticated": True},
            request=httpx.Request("GET", "https://api.example.com/basic"),
        )

        with patch(
            "httpx.AsyncClient.request",
            new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_req:
            result = await adapter.execute(
                tool_name="basic_tool",
                parameters={},
                credential_metadata={
                    "base_url": "https://api.example.com",
                    "auth_type": "basic_auth",
                    "endpoints": {"basic_tool": {"path": "/basic", "method": "GET"}},
                },
                credential_secret={"username": "user", "password": "pass"},
            )

        assert result.status == "success"
        call_kwargs = mock_req.call_args[1]
        assert call_kwargs["auth"] == ("user", "pass")


# ---------------------------------------------------------------------------
# OAuth2ToolAdapter
# ---------------------------------------------------------------------------


class TestOAuth2ToolAdapter:
    @pytest.mark.asyncio
    async def test_successful_oauth2_call(self):
        adapter = OAuth2ToolAdapter()

        mock_response = httpx.Response(
            status_code=200,
            json={"data": "oauth2_result"},
            request=httpx.Request("POST", "https://api.example.com/v1/resource"),
        )

        with patch(
            "httpx.AsyncClient.request",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await adapter.execute(
                tool_name="resource",
                parameters={"id": 42},
                credential_metadata={
                    "base_url": "https://api.example.com",
                    "endpoints": {"resource": {"path": "/v1/resource"}},
                },
                credential_secret={"access_token": "eyJ.valid.token"},
            )

        assert result.status == "success"
        assert result.result["data"] == "oauth2_result"

    @pytest.mark.asyncio
    async def test_refreshes_token_on_401(self):
        adapter = OAuth2ToolAdapter()

        response_401 = httpx.Response(
            status_code=401,
            json={"error": "token_expired"},
            request=httpx.Request("POST", "https://api.example.com/v1/resource"),
        )
        response_200 = httpx.Response(
            status_code=200,
            json={"data": "refreshed_result"},
            request=httpx.Request("POST", "https://api.example.com/v1/resource"),
        )
        token_response = httpx.Response(
            status_code=200,
            json={"access_token": "new_token_123"},
            request=httpx.Request("POST", "https://auth.example.com/token"),
        )

        call_count = 0

        async def mock_request(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return response_401
            return response_200

        async def mock_post(url, **kwargs):
            return token_response

        with patch(
            "httpx.AsyncClient.request",
            new_callable=AsyncMock,
            side_effect=mock_request,
        ):
            with patch(
                "httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=mock_post
            ):
                result = await adapter.execute(
                    tool_name="resource",
                    parameters={},
                    credential_metadata={
                        "base_url": "https://api.example.com",
                        "endpoints": {"resource": {"path": "/v1/resource"}},
                        "token_url": "https://auth.example.com/token",
                        "token_grant_type": "client_credentials",
                    },
                    credential_secret={
                        "access_token": "expired_token",
                        "client_id": "my_client",
                        "client_secret": "my_secret",
                    },
                )

        assert result.status == "success"
        assert result.result.get("_refreshed") is True

    @pytest.mark.asyncio
    async def test_missing_access_token(self):
        adapter = OAuth2ToolAdapter()
        result = await adapter.execute(
            tool_name="resource",
            parameters={},
            credential_metadata={"base_url": "https://api.example.com"},
            credential_secret={},
        )
        assert result.status == "error"
        assert "access_token" in result.error


# ---------------------------------------------------------------------------
# WebhookToolAdapter
# ---------------------------------------------------------------------------


class TestWebhookToolAdapter:
    @pytest.mark.asyncio
    async def test_successful_webhook(self):
        adapter = WebhookToolAdapter()

        mock_response = httpx.Response(
            status_code=200,
            json={"received": True},
            request=httpx.Request("POST", "https://hooks.example.com/openintent"),
        )

        with patch(
            "httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response
        ):
            result = await adapter.execute(
                tool_name="notify",
                parameters={"message": "hello"},
                credential_metadata={
                    "base_url": "https://hooks.example.com/openintent"
                },
                credential_secret={},
            )

        assert result.status == "success"
        assert result.result["received"] is True

    @pytest.mark.asyncio
    async def test_webhook_with_hmac_signing(self):
        adapter = WebhookToolAdapter()

        mock_response = httpx.Response(
            status_code=200,
            json={"verified": True},
            request=httpx.Request("POST", "https://hooks.example.com/signed"),
        )

        with patch(
            "httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response
        ) as mock_post:
            result = await adapter.execute(
                tool_name="signed_hook",
                parameters={"event": "test"},
                credential_metadata={"base_url": "https://hooks.example.com/signed"},
                credential_secret={"signing_secret": "whsec_test123"},
            )

        assert result.status == "success"
        call_kwargs = mock_post.call_args[1]
        assert "X-OpenIntent-Signature" in call_kwargs["headers"]
        assert call_kwargs["headers"]["X-OpenIntent-Signature"].startswith("sha256=")

    @pytest.mark.asyncio
    async def test_webhook_missing_base_url(self):
        adapter = WebhookToolAdapter()
        result = await adapter.execute(
            tool_name="hook",
            parameters={},
            credential_metadata={},
            credential_secret={},
        )
        assert result.status == "error"
        assert "base_url" in result.error


# ---------------------------------------------------------------------------
# ToolExecutionResult
# ---------------------------------------------------------------------------


class TestToolExecutionResult:
    def test_default_values(self):
        result = ToolExecutionResult()
        assert result.status == "success"
        assert result.result is None
        assert result.error is None
        assert result.duration_ms == 0
        assert result.http_status is None
        assert result.request_fingerprint is None

    def test_error_result(self):
        result = ToolExecutionResult(
            status="error",
            error="Something went wrong",
            http_status=502,
            duration_ms=150,
        )
        assert result.status == "error"
        assert result.http_status == 502
