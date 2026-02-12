---
title: Built-in Server
---

# Built-in Server

The OpenIntent SDK includes a full-featured FastAPI server implementing all 20 RFCs.

## Quick Start

=== "CLI"

    ```bash
    pip install openintent[server]
    openintent-server
    ```

=== "Programmatic"

    ```python
    from openintent.server import OpenIntentServer

    server = OpenIntentServer(
        host="0.0.0.0",
        port=8000,
        database_url="sqlite:///my-app.db"
    )
    server.run()
    ```

=== "Mount on existing app"

    ```python
    from fastapi import FastAPI
    from openintent.server import create_openintent_app

    app = FastAPI()
    openintent_app = create_openintent_app()
    app.mount("/openintent", openintent_app)
    ```

!!! info "Server is running"
    The server runs on `http://localhost:8000` by default. OpenAPI docs at `/docs`, ReDoc at `/redoc`.

---

## Endpoints

### Discovery

| Endpoint | Description |
|----------|-------------|
| `/.well-known/openintent.json` | Protocol discovery |
| `/.well-known/openintent-compat.json` | Compatibility info |
| `/docs` | OpenAPI documentation (Swagger UI) |
| `/redoc` | ReDoc documentation |

### Intent CRUD

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/intents` | Create intent |
| `GET` | `/api/v1/intents` | List intents |
| `GET` | `/api/v1/intents/{id}` | Get intent |
| `PATCH` | `/api/v1/intents/{id}/state` | Patch state |
| `DELETE` | `/api/v1/intents/{id}` | Delete intent |

### Events

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/intents/{id}/events` | Log event |
| `GET` | `/api/v1/intents/{id}/events` | Get events |

### Leasing

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/intents/{id}/leases` | Acquire lease |
| `GET` | `/api/v1/intents/{id}/leases` | List leases |
| `PATCH` | `/api/v1/intents/{id}/leases/{lid}` | Renew lease |
| `DELETE` | `/api/v1/intents/{id}/leases/{lid}` | Release lease |

### Subscriptions (SSE)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/intents/{id}/subscribe` | Subscribe to intent |
| `GET` | `/api/v1/agents/{id}/subscribe` | Subscribe to agent |
| `GET` | `/api/v1/portfolios/{id}/subscribe` | Subscribe to portfolio |

### Tool Execution (RFC-0014)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/tools/invoke` | Invoke tool via server proxy |
| `GET` | `/api/v1/vaults` | List vaults |
| `POST` | `/api/v1/vaults` | Create vault |
| `POST` | `/api/v1/credentials` | Store credential |
| `POST` | `/api/v1/tool-grants` | Create tool grant |
| `POST` | `/api/v1/tool-grants/{id}/revoke` | Revoke grant |

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENINTENT_HOST` | `0.0.0.0` | Bind address |
| `OPENINTENT_PORT` | `8000` | Port |
| `DATABASE_URL` | `sqlite:///openintent.db` | Database connection |
| `OPENINTENT_LOG_LEVEL` | `info` | Log level |

### Database

=== "SQLite (default)"

    ```bash
    openintent-server
    # Creates openintent.db in current directory
    ```

    !!! tip "Zero-config"
        SQLite requires no setup. Great for development, prototyping, and single-node deployments.

=== "PostgreSQL"

    ```bash
    export DATABASE_URL="postgresql://user:pass@localhost/openintent"
    openintent-server
    ```

    !!! tip "Production recommended"
        PostgreSQL supports concurrent access, better durability, and scales with your workload.

---

## Authentication

=== "Development mode"

    Built-in API keys for testing:

    | Key | Identity |
    |-----|----------|
    | `dev-user-key` | Human user |
    | `agent-research-key` | Research agent |
    | `agent-synth-key` | Synthesis agent |

    ```bash
    curl -H "X-API-Key: dev-user-key" \
      http://localhost:8000/api/v1/intents
    ```

=== "Production (OAuth 2.0)"

    ```bash
    export OPENINTENT_AUTH_MODE=oauth2
    export OPENINTENT_OAUTH_ISSUER=https://auth.example.com
    export OPENINTENT_OAUTH_AUDIENCE=openintent-api
    openintent-server
    ```

!!! warning "Development keys"
    The built-in API keys are for local development only. Always configure proper authentication in production.

---

## Architecture

```mermaid
graph TD
    C[Client / Agent] -->|"HTTP + X-API-Key"| S[FastAPI Server]
    S --> Auth[Auth Middleware]
    Auth --> R[Route Handlers]
    R --> DB[(SQLAlchemy + DB)]
    R --> SSE[SSE Streams]
    R --> TP[Tool Proxy]
    TP --> EA[Execution Adapters]
    EA -->|"REST / OAuth2 / Webhook"| EXT[External APIs]

    style C fill:#f6f8fa,stroke:#e3e8ee,color:#0a2540
    style S fill:#635bff,stroke:#4b44d1,color:#fff
    style Auth fill:#f6f8fa,stroke:#e3e8ee,color:#0a2540
    style R fill:#00d4aa,stroke:#00b894,color:#0a2540
    style DB fill:#f6f8fa,stroke:#e3e8ee,color:#0a2540
    style SSE fill:#f6f8fa,stroke:#e3e8ee,color:#0a2540
    style TP fill:#635bff,stroke:#4b44d1,color:#fff
    style EA fill:#00d4aa,stroke:#00b894,color:#0a2540
    style EXT fill:#f6f8fa,stroke:#e3e8ee,color:#0a2540
```

## Next Steps

<div class="oi-features" style="margin-top: 1em;">
  <div class="oi-feature">
    <div class="oi-feature__title">API Reference</div>
    <p class="oi-feature__desc">Complete server API documentation with all endpoint details.</p>
    <a href="../../api/server/" class="oi-feature__link">View API</a>
  </div>
  <div class="oi-feature">
    <div class="oi-feature__title">Examples</div>
    <p class="oi-feature__desc">Full working examples of multi-agent coordination.</p>
    <a href="../../examples/multi-agent/" class="oi-feature__link">See examples</a>
  </div>
</div>
