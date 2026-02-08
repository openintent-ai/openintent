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
