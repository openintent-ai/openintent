# Built-in Server

The OpenIntent SDK includes a full-featured FastAPI server implementing all 17 RFCs.

## Quick Start

```bash
# Install with server support
pip install openintent[server]

# Start the server
openintent-server
```

The server runs on `http://localhost:8000` by default.

## Endpoints

### Discovery

- `/.well-known/openintent.json` - Protocol discovery
- `/.well-known/openintent-compat.json` - Compatibility info
- `/docs` - OpenAPI documentation (Swagger UI)
- `/redoc` - ReDoc documentation

### Intent CRUD

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/intents` | Create intent |
| GET | `/api/v1/intents` | List intents |
| GET | `/api/v1/intents/{id}` | Get intent |
| PATCH | `/api/v1/intents/{id}/state` | Patch state |
| DELETE | `/api/v1/intents/{id}` | Delete intent |

### Events

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/intents/{id}/events` | Log event |
| GET | `/api/v1/intents/{id}/events` | Get events |

### Leasing

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/intents/{id}/leases` | Acquire lease |
| GET | `/api/v1/intents/{id}/leases` | List leases |
| PATCH | `/api/v1/intents/{id}/leases/{lid}` | Renew lease |
| DELETE | `/api/v1/intents/{id}/leases/{lid}` | Release lease |

### Subscriptions (SSE)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/intents/{id}/subscribe` | Subscribe to intent |
| GET | `/api/v1/agents/{id}/subscribe` | Subscribe to agent |
| GET | `/api/v1/portfolios/{id}/subscribe` | Subscribe to portfolio |

## Configuration

### Command Line

```bash
openintent-server --host 0.0.0.0 --port 8080
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENINTENT_HOST` | `0.0.0.0` | Bind address |
| `OPENINTENT_PORT` | `8000` | Port |
| `DATABASE_URL` | `sqlite:///openintent.db` | Database |
| `OPENINTENT_LOG_LEVEL` | `info` | Log level |

### Database

**SQLite (default):**
```bash
openintent-server
# Creates openintent.db in current directory
```

**PostgreSQL:**
```bash
export DATABASE_URL="postgresql://user:pass@localhost/openintent"
openintent-server
```

## Programmatic Usage

```python
from openintent.server import OpenIntentServer

server = OpenIntentServer(
    host="0.0.0.0",
    port=8000,
    database_url="sqlite:///my-app.db"
)
server.run()
```

### With Custom FastAPI App

```python
from fastapi import FastAPI
from openintent.server import create_openintent_app

app = FastAPI()
openintent_app = create_openintent_app()
app.mount("/openintent", openintent_app)
```

## Authentication

### Development Mode

Built-in API keys for testing:

- `dev-user-key` - Human user
- `agent-research-key` - Research agent
- `agent-synth-key` - Synthesis agent

```bash
curl -H "X-API-Key: dev-user-key" http://localhost:8000/api/v1/intents
```

### Production Mode

Configure OAuth 2.0:

```bash
export OPENINTENT_AUTH_MODE=oauth2
export OPENINTENT_OAUTH_ISSUER=https://auth.example.com
export OPENINTENT_OAUTH_AUDIENCE=openintent-api
openintent-server
```

## Next Steps

- [API Reference](../api/server.md) - Complete server API
- [Examples](../examples/multi-agent.md) - Full working examples
