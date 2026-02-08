---
title: Coordinator Patterns
---

# Coordinator Patterns

Coordinators manage portfolios of intents, delegate work to agents, track dependencies, and provide governance for multi-agent systems. Defined in [RFC-0013](../rfcs/0013-coordinator-governance.md).

## The @Coordinator Decorator

```python
from openintent.agents import Coordinator, on_assignment, on_conflict, on_escalation

@Coordinator("orchestrator",
    agents=["researcher", "writer", "reviewer"],
    strategy="sequential",
    guardrails=["budget_check", "quality_gate"]
)
class ProjectOrchestrator:

    @on_assignment
    async def plan(self, intent):
        await self.delegate(
            title="Research phase",
            agents=["researcher"],
            constraints={"deadline": "2h"}
        )

    @on_conflict
    async def resolve(self, intent, conflict):
        self.record_decision(
            decision="use_latest",
            rationale="Later result supersedes earlier one"
        )
```

## Delegation

Delegation creates intents and assigns them to agents:

```python
@Coordinator("project-lead", agents=["researcher", "writer"])
class ProjectLead:

    @on_assignment
    async def plan(self, intent):
        # Delegate sequential work
        await self.delegate(
            title="Research the topic",
            agents=["researcher"]
        )

        await self.delegate(
            title="Write the report",
            agents=["writer"],
            depends_on=["Research the topic"]
        )
```

### Portfolio-Based Delegation

For complex workflows, use `PortfolioSpec` for structured delegation:

```python
from openintent.models import PortfolioSpec, IntentSpec

@Coordinator("launch-lead", agents=["researcher", "designer", "developer"])
class LaunchCoordinator:

    @on_assignment
    async def plan(self, intent):
        spec = PortfolioSpec(
            name=intent.title,
            intents=[
                IntentSpec("Market research", assign="researcher"),
                IntentSpec("UI design", assign="designer", depends_on=["Market research"]),
                IntentSpec("Build MVP", assign="developer", depends_on=["UI design"]),
            ]
        )
        return await self.execute(spec)
```

## Coordination Strategies

| Strategy | Description |
|----------|-------------|
| `sequential` | Agents work one after another |
| `parallel` | All agents work simultaneously |
| `pipeline` | Output of one feeds into the next |
| `adaptive` | Coordinator adjusts assignments based on intermediate results |

```python
# Parallel strategy — all agents start at once
@Coordinator("parallel-lead",
    agents=["agent-a", "agent-b", "agent-c"],
    strategy="parallel"
)
class ParallelCoordinator:

    @on_assignment
    async def fan_out(self, intent):
        for agent in ["agent-a", "agent-b", "agent-c"]:
            await self.delegate(
                title=f"Process segment for {agent}",
                agents=[agent]
            )
```

## Governance & Guardrails

Guardrails define constraints that the coordinator enforces:

```python
@Coordinator("governed-lead",
    agents=["researcher"],
    guardrails=["budget_check", "quality_gate", "safety_review"]
)
class GovernedCoordinator:

    @on_assignment
    async def plan(self, intent):
        # Guardrails are checked before delegation
        await self.delegate(
            title="Expensive research",
            agents=["researcher"],
            constraints={"max_cost_usd": 10.00}
        )
```

## Conflict Resolution

When agents produce conflicting results, the coordinator handles resolution:

```python
@Coordinator("merger", agents=["agent-a", "agent-b"])
class ConflictResolver:

    @on_conflict
    async def handle_conflict(self, intent, conflict):
        """Called when two agents produce conflicting state updates."""
        # Record the decision for audit
        self.record_decision(
            decision="merge",
            rationale="Combined results from both agents using weighted average",
            metadata={
                "conflict_type": conflict.type,
                "agents": [conflict.agent_a, conflict.agent_b]
            }
        )

        # Apply the merged result
        merged = merge_results(conflict.value_a, conflict.value_b)
        return {"merged_result": merged}
```

## Escalation Handling

```python
@Coordinator("escalation-handler", agents=["worker-1", "worker-2"])
class EscalationHandler:

    @on_escalation
    async def handle(self, intent, escalation):
        """Called when an agent escalates an issue."""
        if escalation.severity == "critical":
            # Request human arbitration
            await self.request_arbitration(
                intent.id,
                reason=escalation.reason,
                options=[
                    {"label": "Retry with different agent", "value": "retry"},
                    {"label": "Abandon this path", "value": "abandon"},
                ]
            )
        else:
            # Reassign to a different agent
            await self.delegate(
                title=f"Retry: {escalation.task}",
                agents=["worker-2"]
            )
```

## Quorum-Based Decisions

```python
from openintent.agents import on_quorum

@Coordinator("voter", agents=["judge-1", "judge-2", "judge-3"])
class QuorumCoordinator:

    @on_quorum(threshold=0.67)
    async def on_consensus(self, intent, votes):
        """Called when 67% of agents agree on a decision."""
        winner = max(votes, key=votes.get)
        self.record_decision(
            decision=winner,
            rationale=f"Quorum reached: {votes}"
        )
        return {"decision": winner}
```

## Decision Audit Trail

All coordinator decisions are recorded and queryable:

```python
# Access decision log
for d in coordinator.decisions:
    print(f"Decision: {d.decision}")
    print(f"  Rationale: {d.rationale}")
    print(f"  Timestamp: {d.created_at}")
```

## Coordinator Lifecycle

Coordinators have their own lease lifecycle (RFC-0013):

| Feature | Description |
|---------|-------------|
| Coordinator lease | Exclusive coordination rights for a portfolio |
| Supervisor hierarchy | Coordinators can supervise other coordinators |
| Failover | Automatic handoff when a coordinator becomes unhealthy |
| Decision records | Full audit trail of every coordination decision |

## Next Steps

- [Task Planning](task-planning.md) — Plans, checkpoints, and execution strategies
- [Governance & Arbitration](governance.md) — Arbitration and delegation contracts
- [Agent Abstractions](agents.md) — `@Coordinator` API reference
