#!/usr/bin/env python3
"""
Writing Agent - Uses the @Agent decorator with Anthropic's Claude.

This agent handles content writing tasks, demonstrating:
- Automatic subscription to agent events via SSE
- Reading input from intent state (research findings)
- LLM tracking with the Anthropic adapter
- Clean handoff between agents

Run with:
    python examples/multi_agent/writing_agent.py
"""

import os

from anthropic import Anthropic

from openintent import Agent, Intent, on_assignment, on_complete
from openintent.adapters import AdapterConfig, AnthropicAdapter


@Agent("writing-agent")
class WritingAgent:
    """
    A writing agent powered by Claude.

    Reads research findings from intent state and produces content.
    The @Agent decorator handles all the coordination boilerplate.
    """

    def __init__(self):
        self.anthropic = Anthropic()

    @on_assignment
    async def write(self, intent: Intent) -> dict:
        """
        Handle writing assignments.

        Reads research from intent state and produces content.
        """
        print(f"\n[WRITING] Writing: {intent.title}")
        print(f"   Description: {intent.description}")

        # Get research input from state (passed from research phase)
        state = (
            intent.state.to_dict()
            if hasattr(intent.state, "to_dict")
            else intent.state or {}
        )
        research = state.get("research", {})
        research_findings = research.get("findings", "No research provided.")

        print(f"   [INFO] Using research from: {research.get('agent', 'unknown')}")

        # Wrap Anthropic client to auto-log LLM events
        adapter = AnthropicAdapter(
            self.anthropic,
            self.client,  # Injected by @Agent decorator
            intent_id=intent.id,
            config=AdapterConfig(log_requests=True),
        )

        # Call Claude for writing (automatically logged)
        message = adapter.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=2000,
            messages=[
                {
                    "role": "user",
                    "content": f"""Based on the following research, write a compelling blog post.

RESEARCH FINDINGS:
{research_findings}

REQUIREMENTS:
- Write in an engaging, accessible style
- Include an introduction and conclusion
- Use headers to organize the content
- Target audience: technical professionals
""",
                }
            ],
        )

        content = message.content[0].text

        print("   [OK] Writing complete!")

        # Return value is auto-patched to intent state
        return {
            "content": {
                "text": content,
                "model": "claude-3-5-sonnet",
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
    print("OpenIntent Writing Agent (Claude)")
    print("=" * 60)
    print(f"Server: {base_url}")
    print("Agent ID: writing-agent")
    print("Model: claude-3-5-sonnet")
    print("=" * 60)
    print("\nWaiting for assignments via SSE...")
    print("(Assign me to an intent to see writing happen!)\n")

    # Run the agent - handles everything automatically
    WritingAgent.run(base_url=base_url, api_key=api_key)
