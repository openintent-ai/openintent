# Configuration

## Client Configuration

### Basic Setup

```python
from openintent import OpenIntentClient

client = OpenIntentClient(
    base_url="http://localhost:8000",
    agent_id="my-agent",
    api_key="your-api-key"  # Optional
)
```

### Configuration Options

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `base_url` | str | Required | OpenIntent server URL |
| `agent_id` | str | Required | Unique identifier for this agent |
| `api_key` | str | None | API key for authentication |
| `timeout` | float | 30.0 | Request timeout in seconds |

### Async Client

For async applications:

```python
from openintent import AsyncOpenIntentClient

async def main():
    async with AsyncOpenIntentClient(
        base_url="http://localhost:8000",
        agent_id="async-agent"
    ) as client:
        intent = await client.create_intent(title="Async task")
```

## Server Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENINTENT_HOST` | `0.0.0.0` | Server bind address |
| `OPENINTENT_PORT` | `8000` | Server port |
| `DATABASE_URL` | `sqlite:///openintent.db` | Database connection |
| `OPENINTENT_AUTH_MODE` | `api_key` | Authentication mode |

### Database Options

**SQLite (default):**
```bash
openintent-server
# Uses sqlite:///openintent.db
```

**PostgreSQL:**
```bash
export DATABASE_URL="postgresql://user:pass@localhost/openintent"
openintent-server
```

### Authentication Modes

**Development (API keys):**
```bash
export OPENINTENT_AUTH_MODE=api_key
openintent-server
```

Built-in dev keys: `dev-user-key`, `agent-research-key`, `agent-synth-key`

**Production (OAuth 2.0):**
```bash
export OPENINTENT_AUTH_MODE=oauth2
export OPENINTENT_OAUTH_ISSUER=https://your-provider.com
export OPENINTENT_OAUTH_AUDIENCE=openintent-api
openintent-server
```

## Next Steps

- [Intents Guide](../guide/intents.md) - Deep dive into intent management
- [API Reference](../api/client.md) - Complete client API
