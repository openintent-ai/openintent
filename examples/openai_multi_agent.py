#!/usr/bin/env python3
"""
OpenIntent + OpenAI Multi-Agent Coordination Example

This example demonstrates how multiple AI agents can coordinate through
the OpenIntent Protocol to accomplish complex tasks collaboratively.

Scenario: Research and Synthesis Pipeline
- Research Agent: Gathers and analyzes information
- Synthesis Agent: Synthesizes findings into coherent output
- Both agents coordinate through a shared intent with leases for scope ownership

Prerequisites:
    pip install openai httpx

Usage:
    export OPENAI_API_KEY=your-key
    export OPENINTENT_API_URL=http://localhost:8000
    export OPENINTENT_API_KEY=dev-user-key
    python openai_multi_agent.py
"""

import asyncio
import json
import os
import sys
from datetime import datetime

from openai import AsyncOpenAI

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from openintent import (
    AsyncOpenIntentClient,
    EventType,
    IntentStatus,
    LeaseConflictError,
)

OPENINTENT_API_URL = os.getenv("OPENINTENT_API_URL", "http://localhost:8000")
OPENINTENT_API_KEY = os.getenv("OPENINTENT_API_KEY", "dev-user-key")


class BaseAgent:
    """Base class for AI agents that coordinate through OpenIntent."""

    def __init__(self, agent_id: str, role: str, system_prompt: str):
        self.agent_id = agent_id
        self.role = role
        self.system_prompt = system_prompt
        self.openai = AsyncOpenAI()
        self.intent_client: AsyncOpenIntentClient = None

    async def connect(self):
        """Connect to the OpenIntent coordination server."""
        self.intent_client = AsyncOpenIntentClient(
            base_url=OPENINTENT_API_URL,
            api_key=OPENINTENT_API_KEY,
            agent_id=self.agent_id,
        )

    async def disconnect(self):
        """Disconnect from the coordination server."""
        if self.intent_client:
            await self.intent_client.close()

    async def think(self, prompt: str, context: dict = None) -> str:
        """Use OpenAI to generate a response based on prompt and context."""
        messages = [{"role": "system", "content": self.system_prompt}]

        if context:
            messages.append(
                {
                    "role": "user",
                    "content": f"Current context:\n{json.dumps(context, indent=2)}",
                }
            )

        messages.append({"role": "user", "content": prompt})

        response = await self.openai.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0.7,
        )

        return response.choices[0].message.content

    async def log_activity(self, intent_id: str, message: str, data: dict = None):
        """Log agent activity to the intent's event stream."""
        await self.intent_client.log_event(
            intent_id,
            EventType.COMMENT,
            {
                "agent": self.agent_id,
                "role": self.role,
                "message": message,
                "data": data or {},
                "timestamp": datetime.now().isoformat(),
            },
        )
        print(f"[{self.role}] {message}")


class ResearchAgent(BaseAgent):
    """
    Agent specialized in gathering and analyzing information.
    Acquires lease on 'research' scope to prevent conflicts.
    """

    def __init__(self):
        super().__init__(
            agent_id="agent-research",
            role="Research Agent",
            system_prompt="""You are a research agent. Your job is to:
1. Analyze research topics and break them into components
2. Gather relevant information and insights
3. Organize findings in a structured format
4. Identify key points that will be useful for synthesis

Be thorough but concise. Focus on factual, actionable information.
Respond with JSON containing: {"findings": [...], "key_points": [...], "sources_needed": [...]}""",
        )

    async def conduct_research(self, intent_id: str, topic: str) -> dict:
        """
        Conduct research on a topic while holding exclusive lease.
        """
        print(f"\n[{self.role}] Acquiring lease for research scope...")

        lease = None
        try:
            lease = await self.intent_client.acquire_lease(
                intent_id,
                scope="research",
                duration_seconds=300,
            )
            print(f"[{self.role}] Lease acquired: {lease.id}")

            await self.log_activity(intent_id, "Starting research phase", {"topic": topic})

            intent = await self.intent_client.get_intent(intent_id)

            await self.intent_client.update_state(
                intent_id,
                intent.version,
                {
                    "research_status": "in_progress",
                    "research_started_at": datetime.now().isoformat(),
                },
            )

            prompt = f"""Research the following topic and provide structured findings:

Topic: {topic}

Analyze this topic and provide:
1. Key findings (3-5 main points)
2. Important details for each finding
3. Any areas that need further investigation"""

            response = await self.think(prompt)

            try:
                findings = json.loads(response)
            except json.JSONDecodeError:
                findings = {
                    "findings": [response],
                    "key_points": [],
                    "sources_needed": [],
                }

            intent = await self.intent_client.get_intent(intent_id)
            await self.intent_client.update_state(
                intent_id,
                intent.version,
                {
                    "research_status": "completed",
                    "research_completed_at": datetime.now().isoformat(),
                    "research_findings": findings,
                },
            )

            await self.log_activity(
                intent_id,
                "Research phase completed",
                {"findings_count": len(findings.get("findings", []))},
            )

            return findings

        except LeaseConflictError as e:
            print(f"[{self.role}] Could not acquire lease - scope is busy")
            await self.log_activity(
                intent_id, "Research blocked - lease conflict", {"error": str(e)}
            )
            raise

        finally:
            if lease:
                try:
                    await self.intent_client.release_lease(intent_id, lease.id)
                    print(f"[{self.role}] Lease released")
                except Exception:
                    pass


class SynthesisAgent(BaseAgent):
    """
    Agent specialized in synthesizing research into coherent output.
    Waits for research to complete, then acquires 'synthesis' scope lease.
    """

    def __init__(self):
        super().__init__(
            agent_id="agent-synthesis",
            role="Synthesis Agent",
            system_prompt="""You are a synthesis agent. Your job is to:
1. Take research findings and synthesize them into coherent output
2. Create clear, well-structured summaries
3. Highlight key insights and actionable recommendations
4. Ensure the output is accessible and useful

Transform raw findings into polished, professional content.
Respond with JSON containing: {"summary": "...", "key_insights": [...], "recommendations": [...]}""",
        )

    async def wait_for_research(self, intent_id: str, timeout: int = 60) -> dict:
        """
        Poll intent state waiting for research to complete.
        Demonstrates coordination without direct agent communication.
        """
        print(f"\n[{self.role}] Waiting for research to complete...")

        start_time = datetime.now()
        while True:
            intent = await self.intent_client.get_intent(intent_id)
            state = intent.state.to_dict()

            if state.get("research_status") == "completed":
                print(f"[{self.role}] Research data available!")
                return state.get("research_findings", {})

            elapsed = (datetime.now() - start_time).seconds
            if elapsed > timeout:
                raise TimeoutError("Research did not complete in time")

            print(
                f"[{self.role}] Research status: {state.get('research_status', 'pending')} - waiting..."
            )
            await asyncio.sleep(2)

    async def synthesize(self, intent_id: str, research_findings: dict) -> dict:
        """
        Synthesize research findings into final output.
        """
        print(f"\n[{self.role}] Acquiring lease for synthesis scope...")

        lease = None
        try:
            lease = await self.intent_client.acquire_lease(
                intent_id,
                scope="synthesis",
                duration_seconds=300,
            )
            print(f"[{self.role}] Lease acquired: {lease.id}")

            await self.log_activity(
                intent_id,
                "Starting synthesis phase",
                {"input_findings": len(research_findings.get("findings", []))},
            )

            intent = await self.intent_client.get_intent(intent_id)

            await self.intent_client.update_state(
                intent_id,
                intent.version,
                {
                    "synthesis_status": "in_progress",
                    "synthesis_started_at": datetime.now().isoformat(),
                },
            )

            prompt = f"""Synthesize the following research findings into a coherent summary:

Research Findings:
{json.dumps(research_findings, indent=2)}

Create:
1. A clear executive summary
2. Key insights (3-5 bullet points)
3. Actionable recommendations"""

            response = await self.think(prompt)

            try:
                synthesis = json.loads(response)
            except json.JSONDecodeError:
                synthesis = {
                    "summary": response,
                    "key_insights": [],
                    "recommendations": [],
                }

            intent = await self.intent_client.get_intent(intent_id)
            await self.intent_client.update_state(
                intent_id,
                intent.version,
                {
                    "synthesis_status": "completed",
                    "synthesis_completed_at": datetime.now().isoformat(),
                    "synthesis_output": synthesis,
                },
            )

            await self.log_activity(
                intent_id,
                "Synthesis phase completed",
                {"output_sections": len(synthesis)},
            )

            return synthesis

        except LeaseConflictError as e:
            print(f"[{self.role}] Could not acquire lease - scope is busy")
            await self.log_activity(
                intent_id, "Synthesis blocked - lease conflict", {"error": str(e)}
            )
            raise

        finally:
            if lease:
                try:
                    await self.intent_client.release_lease(intent_id, lease.id)
                    print(f"[{self.role}] Lease released")
                except Exception:
                    pass


class Coordinator:
    """
    Human-in-the-loop coordinator that creates intents and orchestrates agents.
    Demonstrates governance capabilities.
    """

    def __init__(self):
        self.client: AsyncOpenIntentClient = None

    async def connect(self):
        """Connect to OpenIntent server."""
        self.client = AsyncOpenIntentClient(
            base_url=OPENINTENT_API_URL,
            api_key=OPENINTENT_API_KEY,
            agent_id="coordinator",
        )

    async def disconnect(self):
        """Disconnect from server."""
        if self.client:
            await self.client.close()

    async def create_research_intent(self, topic: str) -> str:
        """
        Create a new intent for the research and synthesis pipeline.
        """
        print(f"\n[Coordinator] Creating intent for topic: {topic}")

        intent = await self.client.create_intent(
            title=f"Research: {topic}",
            description=f"Conduct research and synthesize findings on: {topic}",
            constraints=[
                "Research must be completed before synthesis",
                "Only one agent may work on each scope at a time",
                "All activities must be logged to the event stream",
            ],
            initial_state={
                "topic": topic,
                "research_status": "pending",
                "synthesis_status": "pending",
            },
        )

        print(f"[Coordinator] Intent created: {intent.id}")
        return intent.id

    async def complete_intent(self, intent_id: str):
        """Mark intent as completed after all work is done."""
        intent = await self.client.get_intent(intent_id)

        await self.client.set_status(
            intent_id,
            intent.version,
            IntentStatus.COMPLETED,
        )

        await self.client.log_event(
            intent_id,
            EventType.STATUS_CHANGED,
            {
                "old_status": "active",
                "new_status": "completed",
                "completed_by": "coordinator",
            },
        )

        await self.client.record_decision(
            intent_id,
            decision_type="completion",
            outcome="approved",
            reasoning="All phases completed successfully - research and synthesis both finished",
        )

        print(f"[Coordinator] Intent {intent_id} marked as completed")

    async def get_final_output(self, intent_id: str) -> dict:
        """Retrieve the final synthesized output."""
        intent = await self.client.get_intent(intent_id)
        return intent.state.to_dict()

    async def get_audit_trail(self, intent_id: str) -> list:
        """Retrieve complete audit trail of events."""
        events = await self.client.get_events(intent_id)
        return [e.to_dict() for e in events]


async def run_pipeline(topic: str):
    """
    Run the complete research and synthesis pipeline.

    This demonstrates:
    1. Intent creation by coordinator
    2. Research agent acquiring lease and working on research scope
    3. Synthesis agent waiting for research, then working on synthesis scope
    4. Coordinator reviewing and completing the intent
    5. Full audit trail via event log
    """

    coordinator = Coordinator()
    research_agent = ResearchAgent()
    synthesis_agent = SynthesisAgent()

    try:
        await coordinator.connect()
        await research_agent.connect()
        await synthesis_agent.connect()

        print("=" * 60)
        print("OpenIntent Multi-Agent Coordination Demo")
        print("=" * 60)

        intent_id = await coordinator.create_research_intent(topic)

        research_task = asyncio.create_task(research_agent.conduct_research(intent_id, topic))

        await asyncio.sleep(1)

        synthesis_task = asyncio.create_task(
            run_synthesis_after_research(synthesis_agent, intent_id)
        )

        await asyncio.gather(research_task, synthesis_task)

        await coordinator.complete_intent(intent_id)

        print("\n" + "=" * 60)
        print("FINAL OUTPUT")
        print("=" * 60)

        final_state = await coordinator.get_final_output(intent_id)

        if final_state.get("synthesis_output"):
            output = final_state["synthesis_output"]
            print(f"\nSummary:\n{output.get('summary', 'N/A')}")
            print("\nKey Insights:")
            for insight in output.get("key_insights", []):
                print(f"  - {insight}")
            print("\nRecommendations:")
            for rec in output.get("recommendations", []):
                print(f"  - {rec}")

        print("\n" + "=" * 60)
        print("AUDIT TRAIL")
        print("=" * 60)

        events = await coordinator.get_audit_trail(intent_id)
        for event in events[-10:]:
            print(f"  [{event['event_type']}] {event.get('payload', {}).get('message', 'N/A')}")

        return intent_id

    finally:
        await coordinator.disconnect()
        await research_agent.disconnect()
        await synthesis_agent.disconnect()


async def run_synthesis_after_research(synthesis_agent: SynthesisAgent, intent_id: str):
    """Helper to run synthesis after research completes."""
    research_findings = await synthesis_agent.wait_for_research(intent_id)
    await synthesis_agent.synthesize(intent_id, research_findings)


async def demo_conflict_handling():
    """
    Demonstrate how OpenIntent handles conflicts between agents.

    This shows:
    1. Two agents trying to acquire the same scope
    2. Lease conflict detection
    3. Arbitration request
    """

    print("\n" + "=" * 60)
    print("Conflict Handling Demo")
    print("=" * 60)

    client1 = AsyncOpenIntentClient(
        base_url=OPENINTENT_API_URL,
        api_key=OPENINTENT_API_KEY,
        agent_id="agent-1",
    )

    client2 = AsyncOpenIntentClient(
        base_url=OPENINTENT_API_URL,
        api_key=OPENINTENT_API_KEY,
        agent_id="agent-2",
    )

    try:
        intent = await client1.create_intent(
            title="Conflict Demo",
            description="Demonstrating lease conflict handling",
        )

        print("[Agent 1] Acquiring lease on 'shared-scope'...")
        lease1 = await client1.acquire_lease(intent.id, "shared-scope", duration_seconds=60)
        print(f"[Agent 1] Lease acquired: {lease1.id}")

        print("[Agent 2] Attempting to acquire same scope...")
        try:
            await client2.acquire_lease(intent.id, "shared-scope", duration_seconds=60)
        except LeaseConflictError:
            print("[Agent 2] Lease conflict detected! Requesting arbitration...")

            arb = await client2.request_arbitration(
                intent.id,
                reason="Need access to shared-scope for urgent task",
                context={
                    "requesting_agent": "agent-2",
                    "current_holder": "agent-1",
                    "scope": "shared-scope",
                },
            )
            print(f"[Agent 2] Arbitration requested: {arb.id}")

        print("[Agent 1] Releasing lease...")
        await client1.release_lease(intent.id, lease1.id)

        print("[Agent 2] Retrying lease acquisition...")
        lease2 = await client2.acquire_lease(intent.id, "shared-scope", duration_seconds=60)
        print(f"[Agent 2] Lease acquired: {lease2.id}")

        await client2.release_lease(intent.id, lease2.id)
        print("Conflict resolution complete!")

    finally:
        await client1.close()
        await client2.close()


async def main():
    """Main entry point."""

    if not os.getenv("OPENAI_API_KEY"):
        print("Warning: OPENAI_API_KEY not set - using mock responses")
        print("Set OPENAI_API_KEY to enable real AI responses\n")

    topic = "The future of AI agent coordination protocols"

    await run_pipeline(topic)
    await demo_conflict_handling()

    print("\n" + "=" * 60)
    print("Demo Complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
