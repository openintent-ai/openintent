#!/usr/bin/env python3
"""
Coordinator - Orchestrates research -> writing workflow.

This demonstrates the Coordinator class for multi-agent orchestration:
- Declarative portfolio specification with dependencies
- Automatic intent creation and agent assignment
- Dependency resolution (writing waits for research)
- Aggregate completion handling

Run with:
    python examples/multi_agent/coordinator.py --task "Write about AI coordination"
"""

import argparse
import asyncio
import os

from openintent import (
    Coordinator,
    IntentPortfolio,
    IntentSpec,
    PortfolioSpec,
    on_all_complete,
)


class ContentCoordinator(Coordinator):
    """
    Coordinates a two-phase content creation workflow:

    1. Research Agent (GPT-4) gathers information
    2. Writing Agent (Claude) creates content

    The Coordinator class handles:
    - Portfolio creation from declarative specs
    - Automatic dependency ordering
    - Real-time progress tracking via SSE
    - Aggregate completion detection
    """

    async def plan(self, topic: str) -> PortfolioSpec:
        """
        Define the content creation workflow.

        Returns a PortfolioSpec that declares intents and their dependencies.
        The Coordinator handles execution order automatically.
        """
        return PortfolioSpec(
            name=f"Content: {topic[:50]}",
            description=f"Create content about: {topic}",
            governance_policy={
                "require_all_completed": True,
                "allow_parallel_execution": False,
                "max_cost_usd": 1.50,
            },
            intents=[
                # Phase 1: Research
                IntentSpec(
                    title="Research Phase",
                    description=f"Research the topic: {topic}",
                    assign="research-agent",
                    constraints=["max_cost_usd:0.50", "required_confidence:0.75"],
                    initial_state={"phase": "research"},
                ),
                # Phase 2: Writing (depends on Research)
                IntentSpec(
                    title="Writing Phase",
                    description=f"Write a blog post about: {topic}",
                    assign="writing-agent",
                    depends_on=["Research Phase"],  # Waits for research
                    constraints=["max_cost_usd:1.00", "style:engaging"],
                    initial_state={"phase": "writing"},
                ),
            ],
        )

    @on_all_complete
    async def finalize(self, portfolio: IntentPortfolio) -> dict:
        """
        Called when all intents in the portfolio complete.

        Collects results from all phases and returns the final output.
        """
        print("\n" + "=" * 60)
        print("ALL PHASES COMPLETE!")
        print("=" * 60)

        results = {}
        for membership in portfolio.intents or []:
            intent = await self.client.get_intent(membership.intent_id)
            state = (
                intent.state.to_dict() if hasattr(intent.state, "to_dict") else intent.state or {}
            )
            results[intent.title] = state

        return {
            "portfolio_id": portfolio.id,
            "name": portfolio.name,
            "results": results,
            "status": "complete",
        }


async def main():
    parser = argparse.ArgumentParser(description="Coordinate multi-agent content creation")
    parser.add_argument("--task", required=True, help="Topic to research and write about")
    parser.add_argument("--timeout", type=int, default=300, help="Timeout in seconds")
    args = parser.parse_args()

    base_url = os.getenv("OPENINTENT_URL", "http://localhost:8000")
    api_key = os.getenv("OPENINTENT_API_KEY", "dev-user-key")

    print("=" * 60)
    print("OpenIntent Content Coordinator")
    print("=" * 60)
    print(f"Task: {args.task}")
    print(f"Server: {base_url}")
    print("=" * 60)

    # Create the coordinator
    coordinator = ContentCoordinator(
        agent_id="coordinator",
        base_url=base_url,
        api_key=api_key,
    )

    # Create the plan
    print("\nCreating workflow plan...")
    spec = await coordinator.plan(args.task)
    print(f"   Portfolio: {spec.name}")
    print(f"   Intents: {len(spec.intents)}")
    for i, intent in enumerate(spec.intents, 1):
        deps = f" (depends on: {', '.join(intent.depends_on)})" if intent.depends_on else ""
        print(f"   {i}. {intent.title} -> {intent.assign}{deps}")

    # Execute the workflow
    print("\nExecuting workflow...")
    print("   (Make sure research-agent and writing-agent are running!)\n")

    try:
        result = await coordinator.execute(spec, timeout=args.timeout)

        print("\n" + "=" * 60)
        print("FINAL RESULT")
        print("=" * 60)

        if "results" in result:
            for phase, state in result["results"].items():
                print(f"\n{phase}:")
                if "research" in state:
                    print(f"   Research by: {state['research'].get('agent', 'unknown')}")
                if "content" in state:
                    content = state["content"].get("text", "")
                    preview = content[:200] + "..." if len(content) > 200 else content
                    print(f"   Content preview: {preview}")

        print("\n[OK] Workflow completed successfully!")

    except TimeoutError:
        print(f"\n[TIMEOUT] After {args.timeout}s")
        print("   Make sure the agents are running!")


if __name__ == "__main__":
    asyncio.run(main())
