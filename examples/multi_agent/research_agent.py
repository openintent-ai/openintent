#!/usr/bin/env python3
"""
Research Agent - Uses the @Agent decorator for minimal boilerplate.

This agent handles research tasks using OpenAI's GPT-4, demonstrating:
- Automatic subscription to agent events via SSE
- Decorator-based event routing
- Auto-patching of state with return values
- LLM tracking with the OpenAI adapter

Run with:
    python examples/multi_agent/research_agent.py
"""

import os

from openai import OpenAI

from openintent import Agent, Intent, on_assignment, on_complete
from openintent.adapters import AdapterConfig, OpenAIAdapter


@Agent("research-agent")
class ResearchAgent:
    """
    A research agent powered by GPT-4.

    The @Agent decorator handles:
    - OpenIntent client setup
    - SSE subscription for real-time events
    - Event routing to decorated handlers
    - Lifecycle management
    """

    def __init__(self):
        self.openai = OpenAI()

    @on_assignment
    async def research(self, intent: Intent) -> dict:
        """
        Handle research assignments.

        Return value is automatically patched to the intent's state.
        Intent is automatically marked complete after handler returns.
        """
        print(f"\n[RESEARCH] Researching: {intent.title}")
        print(f"   Description: {intent.description}")

        # Wrap OpenAI client to auto-log LLM events
        adapter = OpenAIAdapter(
            self.openai,
            self.client,  # Injected by @Agent decorator
            intent_id=intent.id,
            config=AdapterConfig(log_requests=True, log_tool_calls=True),
        )

        # Call GPT-4 for research (automatically logged)
        response = adapter.chat.completions.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": "You are a research assistant. Provide concise, factual research findings.",
                },
                {
                    "role": "user",
                    "content": f"Research the following topic and provide key findings:\n\n{intent.description}",
                },
            ],
            max_tokens=1000,
        )

        findings = response.choices[0].message.content

        print("   [OK] Research complete!")

        # Return value is auto-patched to intent state
        return {
            "research": {
                "findings": findings,
                "model": "gpt-4",
                "agent": self.agent_id,
                "status": "complete",
            }
        }

    @on_complete
    async def on_done(self, intent: Intent):
        """Called when any intent we're assigned to completes."""
        print(f"   [DONE] Intent completed: {intent.title}")


if __name__ == "__main__":
    # Configuration from environment
    base_url = os.getenv("OPENINTENT_URL", "http://localhost:8000")
    api_key = os.getenv("OPENINTENT_API_KEY", "dev-agent-key")

    print("=" * 60)
    print("OpenIntent Research Agent (GPT-4)")
    print("=" * 60)
    print(f"Server: {base_url}")
    print("Agent ID: research-agent")
    print("Model: gpt-4")
    print("=" * 60)
    print("\nWaiting for assignments via SSE...")
    print("(Assign me to an intent to see research happen!)\n")

    # Run the agent - handles everything automatically
    ResearchAgent.run(base_url=base_url, api_key=api_key)
