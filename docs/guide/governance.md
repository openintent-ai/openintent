---
title: Governance & Arbitration
---

# Governance & Arbitration

Governance provides structured escalation paths and auditable decision records when agents are uncertain, in conflict, or need human approval. Defined in [RFC-0004](../rfcs/0004-governance-arbitration.md).

## Arbitration Requests

When an agent encounters ambiguity or conflict, it can request arbitration — asking a human or higher-authority agent to make a decision:

```python
# Agent requests human decision
arbitration = client.request_arbitration(
    intent_id=intent.id,
    reason="Conflicting requirements: budget constraint vs. quality requirement",
    options=[
        {"label": "Prioritize budget", "value": "budget"},
        {"label": "Prioritize quality", "value": "quality"},
        {"label": "Find compromise", "value": "compromise"},
    ]
)

print(f"Arbitration {arbitration.id} — awaiting decision")
```

### Arbitration Lifecycle

```
pending → decided
       ↘ expired
```

| Status | Description |
|--------|-------------|
| `pending` | Awaiting a decision |
| `decided` | A decision has been recorded |
| `expired` | No decision was made within the timeout |

## Recording Decisions

Decisions are first-class objects with full audit trails:

```python
# Record the arbitration decision
decision = client.record_decision(
    intent_id=intent.id,
    arbitration_id=arbitration.id,
    decision="compromise",
    rationale="Reduce scope to stay within budget while maintaining core quality standards",
    decided_by="admin@example.com"
)

print(f"Decision: {decision.decision}")
print(f"Rationale: {decision.rationale}")
```

## Delegation Contracts

Delegation contracts formalize the relationship when one agent assigns work to another:

```python
# Create a delegation contract
delegation = client.delegate(
    intent_id=intent.id,
    from_agent="coordinator",
    to_agent="researcher",
    scope="literature_review",
    constraints={
        "max_sources": 20,
        "deadline": "2026-03-01T00:00:00Z"
    }
)
```

## Using Governance in Agents

### Coordinator Governance

The `@Coordinator` decorator provides built-in governance methods:

```python
from openintent.agents import Coordinator, on_assignment, on_conflict, on_escalation

@Coordinator("project-lead",
    agents=["researcher", "writer"],
    strategy="sequential",
    guardrails=["budget_check", "quality_gate"]
)
class ProjectCoordinator:

    @on_assignment
    async def plan(self, intent):
        await self.delegate(
            title="Research phase",
            agents=["researcher"],
            constraints={"max_cost_usd": 5.00}
        )

    @on_conflict
    async def handle_conflict(self, intent, conflict):
        """Called when agents produce conflicting results."""
        self.record_decision(
            decision="merge",
            rationale="Combined findings from both agents",
            metadata={"conflict_type": conflict.type}
        )

    @on_escalation
    async def handle_escalation(self, intent, escalation):
        """Called when an agent escalates to the coordinator."""
        if escalation.severity == "critical":
            await self.request_arbitration(
                intent.id,
                reason=escalation.reason
            )
```

### Decision Audit Trail

All decisions are queryable for audit purposes:

```python
# List all decisions for an intent
decisions = client.get_decisions(intent.id)

for d in decisions:
    print(f"Decision: {d.decision}")
    print(f"  By: {d.decided_by}")
    print(f"  Rationale: {d.rationale}")
    print(f"  At: {d.created_at}")
```

## Governance in YAML Workflows

```yaml
governance:
  max_cost_usd: 50.00
  timeout_hours: 24
  require_approval:
    when: "risk == 'high'"
    approvers: [admin, lead]
  access_review:
    on_request: approve
    approvers: [security-team]
    timeout_hours: 4
```

!!! info "Governance is non-blocking by default"
    Arbitration requests don't block the intent. Agents can continue working on other scopes while waiting for decisions.

## Next Steps

- [Leasing & Concurrency](leasing.md) — Exclusive ownership of scopes
- [Coordinator Patterns](coordinators.md) — Multi-agent orchestration with governance
- [Access Control](access-control.md) — Permission-based coordination
