"""
Entry point for running the server as a module.

Usage:
    python -m openintent.server
    python -m openintent.server --port 8000 --host 0.0.0.0
"""

from .cli import main

if __name__ == "__main__":
    main()
