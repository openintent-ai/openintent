"""
Server configuration for OpenIntent.
"""

import os
from dataclasses import dataclass, field
from typing import Optional, Set


@dataclass
class ServerConfig:
    """Configuration for the OpenIntent server."""

    host: str = "0.0.0.0"
    port: int = 8000

    database_url: Optional[str] = None

    api_keys: Set[str] = field(
        default_factory=lambda: {
            "dev-user-key",
            "agent-research-key",
            "agent-synth-key",
        }
    )

    cors_origins: list = field(default_factory=lambda: ["*"])

    debug: bool = False

    log_level: str = "info"

    protocol_version: str = "0.1"

    def __post_init__(self):
        if self.database_url is None:
            self.database_url = os.environ.get("DATABASE_URL", "sqlite:///./openintent.db")

        env_keys = os.environ.get("OPENINTENT_API_KEYS")
        if env_keys:
            self.api_keys = set(env_keys.split(","))

    @classmethod
    def from_env(cls) -> "ServerConfig":
        """Create configuration from environment variables."""
        return cls(
            host=os.environ.get("OPENINTENT_HOST", "0.0.0.0"),
            port=int(os.environ.get("OPENINTENT_PORT", "8000")),
            database_url=os.environ.get("DATABASE_URL"),
            debug=os.environ.get("OPENINTENT_DEBUG", "").lower() == "true",
            log_level=os.environ.get("OPENINTENT_LOG_LEVEL", "info"),
        )
