#!/usr/bin/env python3
"""
Agent-to-Agent Messaging Example
=================================

Demonstrates direct communication between agents using channels.
Two agents coordinate through ask/reply and broadcast patterns.

Prerequisites:
    pip install openintent

Usage:
    1. Start the server: openintent-server
    2. Run this script: python agent_messaging.py
"""

import asyncio

from openintent import AsyncOpenIntentClient
from openintent.agents import Agent, on_assignment, on_message


@Agent("data-agent")
class DataAgent:
    """Answers questions from other agents on the data-sync channel."""

    @on_assignment
    async def handle(self, intent):
        return {"status": "data-agent-ready"}

    @on_message(channel="data-sync")
    async def answer_questions(self, message):
        """Respond to data queries. Return value auto-sends as reply."""
        if message.message_type == "request":
            return {
                "answer": "v2.3",
                "confidence": 0.95,
            }


@Agent("researcher")
class ResearchAgent:
    """Asks data-agent for schema info, then broadcasts progress."""

    @on_assignment
    async def handle(self, intent):
        ch = await self.channels.open("data-sync", intent_id=intent.id)

        response = await ch.ask(
            "data-agent",
            {
                "question": "What schema version?",
            },
            timeout=30,
        )

        schema = response.payload["answer"]

        progress = await self.channels.open("progress", intent_id=intent.id)
        await progress.broadcast(
            {
                "phase": "research",
                "schema_used": schema,
                "status": "complete",
            }
        )

        return {"findings": f"Dataset uses {schema}", "schema": schema}


async def main():
    """Run the messaging example using the client directly."""
    client = AsyncOpenIntentClient(
        base_url="http://localhost:8000",
        api_key="dev-agent-key-001",
        agent_id="demo-runner",
    )

    intent = await client.create_intent(
        title="Research Q1 Financials",
        description="Analyze the Q1 financial dataset",
    )

    channel = await client.create_channel(
        intent_id=intent["id"],
        name="demo-channel",
        members=["demo-runner", "data-agent"],
        member_policy="explicit",
        options={"audit": True},
    )

    response = await client.ask(
        channel_id=channel["id"],
        sender="demo-runner",
        to="data-agent",
        payload={"question": "What format is the dataset?"},
        timeout=15,
    )

    print(f"Response: {response['payload']}")

    await client.send_message(
        channel_id=channel["id"],
        sender="demo-runner",
        message_type="broadcast",
        payload={"status": "demo complete"},
    )

    print("Messaging example complete.")


if __name__ == "__main__":
    asyncio.run(main())
