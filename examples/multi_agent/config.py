"""
Configuration for multi-agent example.

Simple configuration constants - the heavy lifting is done by the SDK.
"""

import os

# OpenIntent server configuration
OPENINTENT_URL = os.getenv("OPENINTENT_URL", "http://localhost:8000")
OPENINTENT_API_KEY = os.getenv("OPENINTENT_API_KEY", "dev-agent-key")

# Agent definitions
AGENTS = {
    "research": {
        "id": "research-agent",
        "provider": "openai",
        "model": "gpt-4",
    },
    "writing": {
        "id": "writing-agent",
        "provider": "anthropic",
        "model": "claude-3-5-sonnet-20241022",
    },
}
