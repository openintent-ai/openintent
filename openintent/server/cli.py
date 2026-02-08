"""
Command-line interface for the OpenIntent server.
"""

import argparse
import sys


def main():
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        prog="openintent-server",
        description="OpenIntent Protocol Server - Run a conformant OpenIntent server",
    )

    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind to (default: 8000)",
    )
    parser.add_argument(
        "--database-url",
        default=None,
        help="Database URL (default: sqlite:///./openintent.db)",
    )
    parser.add_argument(
        "--api-keys",
        default=None,
        help="Comma-separated list of API keys (default: dev-user-key,agent-research-key,agent-synth-key)",  # noqa: E501
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode",
    )
    parser.add_argument(
        "--log-level",
        default="info",
        choices=["debug", "info", "warning", "error"],
        help="Log level (default: info)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 0.4.0",
    )

    args = parser.parse_args()

    api_keys = None
    if args.api_keys:
        api_keys = set(args.api_keys.split(","))

    from .app import OpenIntentServer

    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                   OpenIntent Server v0.4.0                   ║
╠══════════════════════════════════════════════════════════════╣
║  Protocol: OpenIntent Coordination Protocol v0.1             ║
║  Host: {args.host:<54}║
║  Port: {args.port:<54}║
║  Database: {(args.database_url or "sqlite:///./openintent.db")[:50]:<50}║
╚══════════════════════════════════════════════════════════════╝

📖 API Documentation: http://{args.host}:{args.port}/docs
🔍 Protocol Discovery: http://{args.host}:{args.port}/.well-known/openintent.json

Press Ctrl+C to stop the server.
""")

    try:
        server = OpenIntentServer(
            host=args.host,
            port=args.port,
            database_url=args.database_url,
            api_keys=api_keys,
            debug=args.debug,
            log_level=args.log_level,
        )
        server.run()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        sys.exit(0)


if __name__ == "__main__":
    main()
