"""
OpenIntent Server - A conformant OpenIntent Protocol server implementation.

Run with:
    openintent-server          # CLI entry point
    python -m openintent.server  # Module entry point

Or programmatically:
    from openintent.server import OpenIntentServer
    server = OpenIntentServer(port=8000)
    server.run()
"""

from .app import OpenIntentServer, create_app
from .config import ServerConfig
from .database import Database, get_database

__all__ = [
    "create_app",
    "OpenIntentServer",
    "ServerConfig",
    "get_database",
    "Database",
]
