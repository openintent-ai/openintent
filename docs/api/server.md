# Server API Reference

Built-in FastAPI server implementing all 17 OpenIntent RFCs.

## OpenIntentServer

::: openintent.server.OpenIntentServer
    options:
      show_source: false

## FastAPI Application

::: openintent.server.app.create_app
    options:
      show_source: false

## Database

::: openintent.server.database.Database
    options:
      show_source: false

## Configuration

::: openintent.server.config.ServerConfig
    options:
      show_source: false

## Tool Invocation Endpoint

The server provides a tool invocation proxy at `POST /api/v1/tools/invoke`. This endpoint:

1. Validates the agent has a matching tool grant (3-tier resolution)
2. Resolves credentials from the vault (never exposed to the agent)
3. Enforces rate limits on the grant
4. Selects the appropriate execution adapter based on credential metadata
5. Executes the tool against the external API (or returns a placeholder if no execution config)
6. Sanitizes secrets from the response
7. Records the invocation for audit with a request fingerprint

### Request

```json
{
  "tool_name": "web_search",
  "agent_id": "researcher",
  "parameters": {"query": "OpenIntent protocol"}
}
```

### Response (Real Execution)

```json
{
  "invocation_id": "inv-abc123",
  "tool_name": "web_search",
  "status": "success",
  "result": {"organic_results": [{"title": "OpenIntent", "link": "..."}]},
  "duration_ms": 342,
  "grant_id": "grant-abc123"
}
```

### Response (Placeholder Fallback)

When the credential has no execution config (`base_url`, `endpoints`), the endpoint returns a placeholder:

```json
{
  "tool_name": "web_search",
  "agent_id": "researcher",
  "result": {"placeholder": true, "tool_name": "web_search"},
  "duration_ms": 1,
  "grant_id": "grant-abc123"
}
```

### Error Responses

| HTTP Status | Meaning |
|-------------|---------|
| `403` | Grant not found, expired, revoked, or URL validation failed |
| `429` | Rate limit exceeded |
| `502` | Upstream service returned a server error |
| `504` | Upstream service timed out |

### Grant Resolution Order

| Priority | Source | Match Condition |
|----------|--------|-----------------|
| 1 | `grant.scopes` | Tool name found in scopes list |
| 2 | `grant.context["tools"]` | Tool name found in context tools array |
| 3 | `credential.service` | Credential service name matches tool name |

### Execution Adapters

| Adapter | Auth Types | Triggered When |
|---------|-----------|----------------|
| `RestToolAdapter` | API key, Bearer, Basic Auth | `auth_type` is `api_key`, `bearer_token`, or `basic_auth` and `base_url` present |
| `OAuth2ToolAdapter` | OAuth2 with token refresh | `auth_type` is `oauth2_token` and `base_url` present |
| `WebhookToolAdapter` | HMAC-signed dispatch | `adapter` is `webhook` or `auth_type` is `webhook` |

### Security Controls

All outbound requests are subject to:

- **URL validation**: Blocks private IPs, cloud metadata endpoints, non-HTTP schemes
- **Timeout bounds**: Clamped to 1–120 seconds
- **Response size**: Capped at 1 MB
- **Secret sanitization**: Keys and tokens replaced with `[REDACTED]` in outputs
- **Request fingerprinting**: SHA-256 fingerprint stored for audit correlation

## CLI

The server can be started via command line:

```bash
# Default options
openintent-server

# Custom host and port
openintent-server --host 0.0.0.0 --port 8080

# With custom database
DATABASE_URL=postgresql://... openintent-server
```

### CLI Options

| Option | Default | Description |
|--------|---------|-------------|
| `--host` | `0.0.0.0` | Bind address |
| `--port` | `8000` | Port number |
| `--reload` | `false` | Enable auto-reload |
| `--log-level` | `info` | Logging level |
