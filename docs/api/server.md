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

## Tool Invocation Endpoint (v0.9.0)

The server provides a tool invocation proxy at `POST /api/v1/tools/invoke`. This endpoint:

1. Validates the agent has a matching tool grant (3-tier resolution)
2. Resolves credentials from the vault (never exposed to the agent)
3. Enforces rate limits on the grant
4. Executes the tool
5. Records the invocation for audit

### Request

```json
{
  "tool_name": "web_search",
  "agent_id": "researcher",
  "parameters": {"query": "OpenIntent protocol"}
}
```

### Response

```json
{
  "tool_name": "web_search",
  "agent_id": "researcher",
  "result": {"results": ["..."]},
  "duration_ms": 230,
  "grant_id": "grant-abc123"
}
```

### Grant Resolution Order

| Priority | Source | Match Condition |
|----------|--------|-----------------|
| 1 | `grant.scopes` | Tool name found in scopes list |
| 2 | `grant.context["tools"]` | Tool name found in context tools array |
| 3 | `credential.service` | Credential service name matches tool name |

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
