# Coordinator Patterns

Coordinators orchestrate multiple agents with governance, decision records, and failover.

## Basic Coordinator

```python
from openintent.agents import (
    Coordinator, on_all_complete,
    IntentSpec, PortfolioSpec
)

workflow = PortfolioSpec(
    name="Data Processing",
    intents=[
        IntentSpec(title="Extract", assign="extractor"),
        IntentSpec(title="Transform", assign="transformer", depends_on=["Extract"]),
        IntentSpec(title="Load", assign="loader", depends_on=["Transform"]),
    ]
)

@Coordinator("etl-coordinator")
class ETLCoordinator:

    @on_all_complete
    async def finished(self, portfolio):
        print(f"ETL complete: {portfolio.name}")
        return {"status": "loaded"}
```

## Coordinator with Guardrails

```python
from openintent.agents import (
    Coordinator, on_conflict, on_escalation,
    on_quorum
)

@Coordinator(
    "review-coordinator",
    agents=["reviewer-a", "reviewer-b", "reviewer-c"],
    strategy="parallel",
    guardrails=[
        {"type": "budget", "max_cost_usd": 5.0},
        {"type": "timeout", "max_seconds": 300},
        {"type": "approval", "require_for": ["deploy"]},
    ]
)
class ReviewCoordinator:

    @on_conflict
    async def handle_conflict(self, intent, versions):
        # Arbitrate between conflicting agent updates
        winner = max(versions, key=lambda v: v.get("confidence", 0))
        await self.record_decision(
            intent_id=intent.id,
            decision="conflict_resolved",
            rationale=f"Chose version with highest confidence",
            chosen=winner
        )
        return winner

    @on_escalation
    async def handle_escalation(self, intent, reason):
        print(f"Escalated: {intent.title} — {reason}")
        await self.delegate(intent, to="senior-reviewer")

    @on_quorum(threshold=2)
    async def quorum_reached(self, intent, responses):
        approved = all(r.get("approved") for r in responses)
        return {"approved": approved, "votes": len(responses)}
```

## Delegation and Decision Records

```python
from openintent.agents import Coordinator, on_assignment

@Coordinator("project-lead", agents=["dev-a", "dev-b", "qa"])
class ProjectCoordinator:

    @on_assignment
    async def handle(self, intent):
        complexity = intent.state.get("complexity", "low")

        if complexity == "high":
            await self.record_decision(
                intent_id=intent.id,
                decision="delegate_to_senior",
                rationale="High complexity requires senior developer"
            )
            await self.delegate(intent, to="dev-a")
        else:
            await self.delegate(intent, to="dev-b")

        return {"delegated": True}
```

## Imperative Coordinator (no decorators)

```python
from openintent import OpenIntentClient

client = OpenIntentClient(
    base_url="http://localhost:8000",
    agent_id="coordinator"
)

# Create portfolio manually
portfolio = client.create_portfolio(
    name="Manual Pipeline",
    description="Imperative coordination"
)

step1 = client.create_intent(
    title="Fetch Data",
    portfolio_id=portfolio.id
)

step2 = client.create_intent(
    title="Process Data",
    portfolio_id=portfolio.id,
    depends_on=[step1.id]
)

# Acquire coordinator lease
lease = client.acquire_coordinator_lease(
    portfolio_id=portfolio.id,
    ttl_seconds=600
)

# Record a governance decision
client.record_decision(
    portfolio_id=portfolio.id,
    decision="approved_pipeline",
    rationale="All agents healthy, budget within limits"
)

# Assign agents
client.assign_agent(step1.id, "data-fetcher")
client.assign_agent(step2.id, "data-processor")
```

## YAML Workflow with Coordinator

```yaml
openintent: "1.0"
info:
  name: "Reviewed Content Pipeline"

coordinator:
  id: content-lead
  strategy: sequential
  guardrails:
    - type: budget
      max_cost_usd: 10.0
    - type: timeout
      max_seconds: 600

workflow:
  write:
    title: "Write Draft"
    assign: writer
    constraints: ["Formal tone", "Under 1000 words"]

  peer_review:
    title: "Peer Review"
    assign: [reviewer-a, reviewer-b]
    depends_on: [write]

  edit:
    title: "Final Edit"
    assign: editor
    depends_on: [peer_review]
```

```python
from openintent.workflow import load_workflow

wf = load_workflow("reviewed_content.yaml")
wf.run()
```
