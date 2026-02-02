#!/usr/bin/env python3
"""
Coordinator - Orchestrates multiple agents using portfolios.

This demonstrates:
- Declarative portfolio specification with dependencies
- Automatic intent creation and agent assignment
- Wait for all intents to complete
- Merge results from multiple agents

Run with:
    python examples/agents/coordinator.py
"""

import asyncio
import os

from openintent import (
    Coordinator,
    IntentPortfolio,
    IntentSpec,
    PortfolioSpec,
    on_all_complete,
)


class ResearchCoordinator(Coordinator):
    """
    Coordinates a research workflow across multiple agents.

    The Coordinator class:
    - Creates portfolios from declarative specs
    - Handles dependency ordering
    - Subscribes to portfolio-level events
    - Waits for completion and merges results
    """

    async def plan(self, topic: str) -> PortfolioSpec:
        """
        Define the research workflow.

        Returns a PortfolioSpec with intents and their dependencies.
        """
        return PortfolioSpec(
            name=f"Research: {topic}",
            description=f"Comprehensive research on {topic}",
            intents=[
                IntentSpec(
                    title="Background Research",
                    description=f"Gather background information on {topic}",
                    assign="research-bot",
                ),
                IntentSpec(
                    title="Data Collection",
                    description=f"Collect relevant data about {topic}",
                    assign="research-bot",
                ),
                IntentSpec(
                    title="Analysis",
                    description=f"Analyze findings about {topic}",
                    assign="analyst-bot",
                    depends_on=["Background Research", "Data Collection"],
                ),
                IntentSpec(
                    title="Report Writing",
                    description=f"Write final report on {topic}",
                    assign="writer-bot",
                    depends_on=["Analysis"],
                ),
            ],
        )

    @on_all_complete
    async def finalize(self, portfolio: IntentPortfolio) -> dict:
        """
        Called when all intents complete.

        Merges results from all agents into final output.
        """
        print(f"Portfolio complete: {portfolio.name}")

        results = {}
        for intent in portfolio.intents:
            results[intent.title] = intent.state.to_dict()

        return {
            "portfolio_id": portfolio.id,
            "name": portfolio.name,
            "results": results,
            "success": True,
        }


async def main():
    base_url = os.getenv("OPENINTENT_URL", "http://localhost:8000")
    api_key = os.getenv("OPENINTENT_API_KEY", "dev-user-key")

    coordinator = ResearchCoordinator(
        agent_id="coordinator",
        base_url=base_url,
        api_key=api_key,
    )

    topic = "AI Agent Coordination"

    print(f"Creating research plan for: {topic}")
    spec = await coordinator.plan(topic)

    print(f"Executing portfolio with {len(spec.intents)} intents...")
    result = await coordinator.execute(spec)

    print("\nFinal result:")
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
