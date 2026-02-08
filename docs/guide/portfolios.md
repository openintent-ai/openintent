---
title: Portfolios
---

# Portfolios

Portfolios group related intents under a shared namespace with aggregate status tracking and shared governance policies. Think of them as project folders for multi-intent coordination. Defined in [RFC-0007](../rfcs/0007-intent-portfolios.md).

## Creating a Portfolio

```python
portfolio = client.create_portfolio(
    name="Q1 Product Launch",
    description="Coordinate all launch activities",
    governance={
        "budget_limit_cents": 100000,
        "deadline": "2026-03-31T00:00:00Z",
        "require_all_completed": True
    }
)

print(f"Portfolio: {portfolio.name} ({portfolio.id})")
```

## Adding Intents

```python
# Create intents and add them to the portfolio
research = client.create_intent(title="Market research")
design = client.create_intent(title="Design mockups")
development = client.create_intent(title="Build MVP")

# Add with roles
client.add_intent_to_portfolio(portfolio.id, research.id, role="primary")
client.add_intent_to_portfolio(portfolio.id, design.id, role="member")
client.add_intent_to_portfolio(portfolio.id, development.id, role="member")
```

### Membership Roles

| Role | Description |
|------|-------------|
| `primary` | The main intent defining the portfolio's goal (one per portfolio) |
| `member` | Standard member that contributes to completion |

## Aggregate Status

Portfolios automatically track status across all member intents:

```python
portfolio = client.get_portfolio(portfolio.id)

status = portfolio.aggregate_status
print(f"Total intents: {status['total']}")
print(f"Completed: {status['by_status']['completed']}")
print(f"Active: {status['by_status']['active']}")
print(f"Progress: {status['completion_percentage']}%")
```

## Shared Governance

Governance policies apply to all intents in the portfolio:

```python
portfolio = client.create_portfolio(
    name="Compliance Review",
    governance={
        "budget_limit_cents": 50000,
        "require_all_completed": True,
        "allow_partial_completion": False,
        "shared_constraints": {
            "compliance_level": "SOC2",
            "review_required": True
        }
    }
)
```

## Listing Portfolios

```python
# List all portfolios
portfolios = client.list_portfolios()

for p in portfolios:
    pct = p.aggregate_status.get("completion_percentage", 0)
    print(f"{p.name}: {pct}% complete")
```

## Portfolio Subscriptions

Subscribe to events across all intents in a portfolio:

```python
for event in client.subscribe_portfolio(portfolio.id):
    print(f"[{event.intent_id}] {event.event_type}: {event.payload}")
```

## Using Portfolios with Coordinators

Coordinators use portfolios to organize delegated work:

```python
from openintent.agents import Coordinator, on_assignment
from openintent.models import PortfolioSpec, IntentSpec

@Coordinator("launch-coordinator", agents=["researcher", "designer", "developer"])
class LaunchCoordinator:

    @on_assignment
    async def plan(self, intent):
        spec = PortfolioSpec(
            name=intent.title,
            intents=[
                IntentSpec("Research", assign="researcher"),
                IntentSpec("Design", assign="designer", depends_on=["Research"]),
                IntentSpec("Develop", assign="developer", depends_on=["Design"]),
            ]
        )
        return await self.execute(spec)
```

## Portfolios vs Plans vs Graphs

| Concept | Purpose | RFC |
|---------|---------|-----|
| **Portfolio** | Organizational grouping with shared governance | RFC-0007 |
| **Intent Graph** | Structural dependencies between intents | RFC-0002 |
| **Plan** | Execution strategy with conditionals and checkpoints | RFC-0012 |

!!! info "Portfolios organize — Plans execute"
    A portfolio groups related intents for visibility and budget tracking. A plan defines *how* those intents should be executed. They work together: a plan operates within a portfolio's governance boundaries.

## Next Steps

- [Task Planning](task-planning.md) — Execution strategies and task decomposition
- [Coordinator Patterns](coordinators.md) — Multi-agent orchestration
- [Subscriptions & Streaming](subscriptions.md) — Real-time portfolio events
