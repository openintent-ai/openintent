# Server SDK & Deployment

Run the OpenIntent server with one command, or embed it in your application.

## Quick Start (CLI)

```bash
# Install with server extras
pip install openintent[server]

# Run with default settings (SQLite, port 8000)
openintent-server

# Run with PostgreSQL
openintent-server --database postgresql://user:pass@localhost/openintent

# Run with custom port and workers
openintent-server --port 9000 --workers 4
```

## Programmatic Server

```python
from openintent.server import OpenIntentServer, ServerConfig

config = ServerConfig(
    host="0.0.0.0",
    port=8000,
    database_url="sqlite:///openintent.db",
    cors_origins=["http://localhost:3000"],
    api_key="dev-key-123",
    log_level="info"
)

server = OpenIntentServer(config)
app = server.create_app()

# Run directly
server.run()
```

## Embedding in an Existing FastAPI App

```python
from fastapi import FastAPI
from openintent.server import create_app, ServerConfig

# Your existing app
app = FastAPI(title="My App")

@app.get("/health")
async def health():
    return {"status": "ok"}

# Mount OpenIntent as a sub-application
openintent_app = create_app(ServerConfig(
    database_url="sqlite:///openintent.db"
))
app.mount("/openintent", openintent_app)

# OpenIntent API is now at /openintent/api/v1/...
```

## Environment Variables

```bash
# All settings can be configured via environment variables
export OPENINTENT_HOST=0.0.0.0
export OPENINTENT_PORT=8000
export OPENINTENT_DATABASE_URL=postgresql://localhost/openintent
export OPENINTENT_API_KEY=my-secret-key
export OPENINTENT_LOG_LEVEL=info
export OPENINTENT_CORS_ORIGINS=http://localhost:3000,http://localhost:5173
export OPENINTENT_WORKERS=4

openintent-server  # Picks up env vars automatically
```

## ServerConfig Reference

```python
from openintent.server import ServerConfig

config = ServerConfig(
    host="0.0.0.0",                          # Bind address
    port=8000,                               # Port number
    database_url="sqlite:///openintent.db",  # SQLite or PostgreSQL
    api_key=None,                            # Optional API key auth
    cors_origins=["*"],                       # CORS allowed origins
    log_level="info",                        # debug, info, warning, error
    workers=1,                               # Uvicorn workers (production)
    enable_docs=True,                        # Swagger UI at /docs
    enable_metrics=False,                    # Prometheus metrics endpoint
    max_lease_ttl_seconds=3600,              # Maximum lease duration
    heartbeat_timeout_seconds=60,            # Agent heartbeat timeout
    event_retention_days=30,                 # Event log retention
)
```

## Docker Deployment

```dockerfile
FROM python:3.11-slim

WORKDIR /app
RUN pip install openintent[server]

EXPOSE 8000

CMD ["openintent-server", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "4"]
```

```bash
docker build -t openintent-server .
docker run -p 8000:8000 \
  -e OPENINTENT_DATABASE_URL=postgresql://host/db \
  openintent-server
```

## Client Connection

```python
from openintent import OpenIntentClient

# Connect to the server
client = OpenIntentClient(
    base_url="http://localhost:8000",
    agent_id="my-agent",
    api_key="dev-key-123"  # If server requires auth
)

# Verify connection
info = client.server_info()
print(f"Server version: {info.version}")
print(f"RFCs supported: {info.rfc_count}")
```
