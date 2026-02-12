#!/usr/bin/env python3
"""
Portfolio Multi-Intent Coordination Example

This example demonstrates how to use Intent Portfolios to coordinate
multiple related intents across different agents. It shows:

1. Creating a portfolio for a complex multi-step project
2. Adding multiple intents with different roles and priorities
3. Tracking aggregate progress across all intents
4. Coordinating agents working on different intents
5. Using governance policies for portfolio-level decisions

Use Case: Trip Planning
- A user wants to plan a complete vacation
- Multiple agents handle different aspects (flights, hotels, activities)
- The portfolio tracks overall completion and enforces constraints
"""

import asyncio
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from openintent import (
    AsyncOpenIntentClient,
    EventType,
    MembershipRole,
    PortfolioStatus,
)

OPENINTENT_API_URL = os.getenv("OPENINTENT_API_URL", "http://localhost:8000")
OPENINTENT_API_KEY = os.getenv("OPENINTENT_API_KEY", "dev-user-key")


class TripPlanningCoordinator:
    """
    Coordinator for a trip planning portfolio.
    Creates the portfolio and spawns intents for different aspects.
    """

    def __init__(self):
        self.client: AsyncOpenIntentClient = None

    async def connect(self):
        self.client = AsyncOpenIntentClient(
            base_url=OPENINTENT_API_URL,
            api_key=OPENINTENT_API_KEY,
            agent_id="coordinator",
        )

    async def disconnect(self):
        if self.client:
            await self.client.close()

    async def create_trip_portfolio(self, destination: str, budget: float) -> str:
        """Create a portfolio for the trip with governance policy."""
        print(f"\n{'=' * 60}")
        print(f"Creating Trip Portfolio: {destination}")
        print(f"{'=' * 60}")

        portfolio = await self.client.create_portfolio(
            name=f"Trip to {destination}",
            description=f"Complete vacation planning for {destination}",
            governance_policy={
                "require_all_completed": True,
                "allow_partial_completion": False,
                "shared_constraints": {
                    "budget": budget,
                    "destination": destination,
                },
            },
            metadata={
                "created_at": datetime.now().isoformat(),
                "trip_type": "vacation",
            },
        )

        print(f"Portfolio created: {portfolio.id}")
        print(f"  Name: {portfolio.name}")
        print(f"  Status: {portfolio.status.value}")
        return portfolio.id

    async def create_trip_intents(self, portfolio_id: str, destination: str) -> dict:
        """Create intents for each aspect of the trip."""
        intents = {}

        flight_intent = await self.client.create_intent(
            title=f"Book flights to {destination}",
            description="Find and book round-trip flights with best value",
        )
        intents["flight"] = flight_intent.id
        await self.client.add_intent_to_portfolio(
            portfolio_id,
            flight_intent.id,
            role=MembershipRole.PRIMARY,
            priority=100,
        )
        print(f"  Created flight intent: {flight_intent.id}")

        hotel_intent = await self.client.create_intent(
            title=f"Book hotel in {destination}",
            description="Find and book hotel near city center",
        )
        intents["hotel"] = hotel_intent.id
        await self.client.add_intent_to_portfolio(
            portfolio_id,
            hotel_intent.id,
            role=MembershipRole.MEMBER,
            priority=90,
        )
        print(f"  Created hotel intent: {hotel_intent.id}")

        activities_intent = await self.client.create_intent(
            title=f"Plan activities in {destination}",
            description="Research and book activities and experiences",
        )
        intents["activities"] = activities_intent.id
        await self.client.add_intent_to_portfolio(
            portfolio_id,
            activities_intent.id,
            role=MembershipRole.MEMBER,
            priority=80,
        )
        print(f"  Created activities intent: {activities_intent.id}")

        transport_intent = await self.client.create_intent(
            title=f"Arrange local transport in {destination}",
            description="Plan airport transfers and local transportation",
        )
        intents["transport"] = transport_intent.id
        await self.client.add_intent_to_portfolio(
            portfolio_id,
            transport_intent.id,
            role=MembershipRole.DEPENDENCY,
            priority=70,
        )
        print(f"  Created transport intent: {transport_intent.id}")

        return intents


class TripAgent:
    """
    An agent that works on a specific intent within the portfolio.
    Simulates work by updating state and completing the intent.
    """

    def __init__(self, agent_id: str, specialty: str):
        self.agent_id = agent_id
        self.specialty = specialty
        self.client: AsyncOpenIntentClient = None

    async def connect(self):
        self.client = AsyncOpenIntentClient(
            base_url=OPENINTENT_API_URL,
            api_key=OPENINTENT_API_KEY,
            agent_id=self.agent_id,
        )

    async def disconnect(self):
        if self.client:
            await self.client.close()

    async def work_on_intent(self, intent_id: str, simulate_time: float = 0.5):
        """Simulate working on an intent."""
        print(f"\n[{self.agent_id}] Starting work on {self.specialty}...")

        intent = await self.client.get_intent(intent_id)
        await self.client.update_status(intent_id, intent.version, "active")

        intent = await self.client.get_intent(intent_id)
        await self.client.update_state(
            intent_id,
            intent.version,
            {f"{self.specialty}_status": "researching"},
        )

        await asyncio.sleep(simulate_time)

        intent = await self.client.get_intent(intent_id)
        await self.client.update_state(
            intent_id,
            intent.version,
            {
                f"{self.specialty}_status": "found_options",
                f"{self.specialty}_options": [
                    {"name": f"Option A for {self.specialty}", "price": 100},
                    {"name": f"Option B for {self.specialty}", "price": 150},
                ],
            },
        )

        await asyncio.sleep(simulate_time)

        intent = await self.client.get_intent(intent_id)
        await self.client.update_state(
            intent_id,
            intent.version,
            {
                f"{self.specialty}_status": "booked",
                f"{self.specialty}_confirmation": f"CONF-{self.specialty.upper()}-12345",
            },
        )

        intent = await self.client.get_intent(intent_id)
        await self.client.update_status(intent_id, intent.version, "completed")

        await self.client.log_event(
            intent_id,
            EventType.COMMENT,
            {"message": f"{self.specialty} booking completed by {self.agent_id}"},
        )

        print(f"[{self.agent_id}] Completed {self.specialty}")


async def monitor_portfolio_progress(client: AsyncOpenIntentClient, portfolio_id: str):
    """Monitor and display portfolio aggregate progress."""
    portfolio = await client.get_portfolio(portfolio_id)

    print(f"\n{'=' * 60}")
    print("PORTFOLIO STATUS")
    print(f"{'=' * 60}")
    print(f"  Name: {portfolio.name}")
    print(f"  Status: {portfolio.status.value}")

    if portfolio.aggregate_status:
        agg = portfolio.aggregate_status
        print(f"\n  Progress: {agg.completion_percentage}%")
        print(f"  Total Intents: {agg.total}")
        print("  By Status:")
        for status, count in agg.by_status.items():
            print(f"    - {status}: {count}")

    return portfolio


async def main():
    """
    Main demo showing portfolio-based multi-intent coordination.
    """
    print("=" * 60)
    print("Portfolio Multi-Intent Coordination Demo")
    print("=" * 60)

    coordinator = TripPlanningCoordinator()

    flight_agent = TripAgent("agent-flights", "flight")
    hotel_agent = TripAgent("agent-hotels", "hotel")
    activities_agent = TripAgent("agent-activities", "activities")
    transport_agent = TripAgent("agent-transport", "transport")

    try:
        await coordinator.connect()
        await flight_agent.connect()
        await hotel_agent.connect()
        await activities_agent.connect()
        await transport_agent.connect()

        portfolio_id = await coordinator.create_trip_portfolio(
            destination="Paris",
            budget=5000,
        )

        intents = await coordinator.create_trip_intents(portfolio_id, "Paris")

        await monitor_portfolio_progress(coordinator.client, portfolio_id)

        print("\n" + "=" * 60)
        print("AGENTS WORKING IN PARALLEL")
        print("=" * 60)

        await asyncio.gather(
            flight_agent.work_on_intent(intents["flight"]),
            hotel_agent.work_on_intent(intents["hotel"]),
            activities_agent.work_on_intent(intents["activities"]),
            transport_agent.work_on_intent(intents["transport"]),
        )

        portfolio = await monitor_portfolio_progress(coordinator.client, portfolio_id)

        if portfolio.aggregate_status and portfolio.aggregate_status.completion_percentage == 100:
            print("\nAll intents completed! Marking portfolio as completed...")
            await coordinator.client.update_portfolio_status(
                portfolio_id,
                PortfolioStatus.COMPLETED,
            )

            final = await coordinator.client.get_portfolio(portfolio_id)
            print(f"Final portfolio status: {final.status.value}")

        print("\n" + "=" * 60)
        print("DEMO COMPLETE")
        print("=" * 60)
        print(f"\nPortfolio ID: {portfolio_id}")
        print("The portfolio coordinated 4 intents across 4 agents")
        print("Aggregate status tracked completion percentage in real-time")

        return portfolio_id

    finally:
        await coordinator.disconnect()
        await flight_agent.disconnect()
        await hotel_agent.disconnect()
        await activities_agent.disconnect()
        await transport_agent.disconnect()


async def demo_portfolio_queries():
    """
    Demonstrate portfolio query capabilities.
    """
    client = AsyncOpenIntentClient(
        base_url=OPENINTENT_API_URL,
        api_key=OPENINTENT_API_KEY,
        agent_id="demo-agent",
    )

    try:
        print("\n" + "=" * 60)
        print("Portfolio Query Demo")
        print("=" * 60)

        portfolios = await client.list_portfolios()
        print(f"\nTotal portfolios: {len(portfolios)}")

        for p in portfolios[:3]:
            print(f"\n  Portfolio: {p.name}")
            print(f"  Status: {p.status.value}")
            print(f"  Created by: {p.created_by}")

            if p.id:
                full = await client.get_portfolio(p.id)
                if full.aggregate_status:
                    print(f"  Completion: {full.aggregate_status.completion_percentage}%")
                print(f"  Intent count: {len(full.intents)}")

    finally:
        await client.close()


if __name__ == "__main__":
    portfolio_id = asyncio.run(main())
    asyncio.run(demo_portfolio_queries())
