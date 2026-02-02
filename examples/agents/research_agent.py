#!/usr/bin/env python3
"""
Research Agent - Minimal example using the @Agent decorator.

This demonstrates the most compact way to create an OpenIntent agent.
The decorator handles all setup, subscription, and lifecycle management.

Run with:
    python examples/agents/research_agent.py
"""

import os

from openintent import Agent, Intent, on_assignment, on_complete


@Agent("research-bot")
class ResearchAgent:
    """
    A research agent that processes assigned intents.

    The @Agent decorator:
    - Sets up the OpenIntent client
    - Subscribes to agent events via SSE
    - Routes events to decorated handlers
    - Handles lifecycle and cleanup
    """

    @on_assignment
    async def work(self, intent: Intent) -> dict:
        """
        Called when assigned to an intent.

        Return value is automatically patched to the intent's state.
        """
        print(f"Assigned to: {intent.title}")

        result = await self.do_research(intent.description)

        return {
            "research_complete": True,
            "findings": result,
            "agent": self.agent_id,
        }

    @on_complete
    async def on_done(self, intent: Intent):
        """Called when any intent completes."""
        print(f"Intent completed: {intent.title}")

    async def do_research(self, topic: str) -> str:
        """Simulate research work."""
        print(f"Researching: {topic}")
        return f"Key findings about {topic}: [simulated research results]"


if __name__ == "__main__":
    base_url = os.getenv("OPENINTENT_URL", "http://localhost:8000")
    api_key = os.getenv("OPENINTENT_API_KEY", "agent-research-key")

    print("Starting ResearchAgent...")
    print(f"Server: {base_url}")
    print("Waiting for assignments via SSE...")

    ResearchAgent.run(base_url=base_url, api_key=api_key)
