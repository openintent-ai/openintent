#!/usr/bin/env python3
"""
Worker - Ultra-minimal agent for simple, single-purpose work.

This is the absolute simplest way to create an OpenIntent agent.
Just provide an agent ID and a handler function.

Run with:
    python examples/agents/worker.py
"""

import os

from openintent import Intent, Worker


async def process(intent: Intent) -> dict:
    """
    Process an intent and return results.

    This is all you need to implement. Return values
    are automatically patched to the intent's state,
    and the intent is marked complete.
    """
    print(f"Processing: {intent.title}")
    print(f"Description: {intent.description}")

    result = f"Processed by worker: {intent.title}"

    return {
        "processed": True,
        "result": result,
    }


if __name__ == "__main__":
    base_url = os.getenv("OPENINTENT_URL", "http://localhost:8000")
    api_key = os.getenv("OPENINTENT_API_KEY", "agent-synth-key")

    worker = Worker(
        agent_id="simple-worker",
        handler=process,
        base_url=base_url,
        api_key=api_key,
    )

    print("Simple worker started, waiting for assignments...")
    worker.run()
