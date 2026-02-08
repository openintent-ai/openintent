# Governance & Arbitration

Control who can do what, resolve conflicts between agents, and maintain full audit trails.

## Governance Policies (Imperative)

```python
from openintent import OpenIntentClient

client = OpenIntentClient(
    base_url="http://localhost:8000",
    agent_id="admin"
)

# Create an intent with governance constraints
intent = client.create_intent(
    title="Deploy to Production",
    governance={
        "require_approval": True,
        "approvers": ["lead-agent", "qa-agent"],
        "min_approvals": 2
    }
)

# Approve as a designated approver
client_lead = OpenIntentClient(base_url="http://localhost:8000", agent_id="lead-agent")
client_lead.approve_intent(intent.id, rationale="Tests pass, LGTM")

client_qa = OpenIntentClient(base_url="http://localhost:8000", agent_id="qa-agent")
client_qa.approve_intent(intent.id, rationale="QA verified")

# Now the intent can proceed
```

## Arbitration on Conflicts

When agents disagree on state updates, governance resolves it:

```python
from openintent.agents import Coordinator, on_conflict

@Coordinator("arbiter", agents=["agent-a", "agent-b"])
class ArbitrationCoordinator:

    @on_conflict
    async def resolve(self, intent, versions):
        # versions = list of competing state patches
        # Pick the one with highest confidence score
        best = max(versions, key=lambda v: v.get("confidence", 0))

        await self.record_decision(
            intent_id=intent.id,
            decision="conflict_resolved",
            rationale=f"Selected version with confidence {best['confidence']}",
            chosen=best
        )
        return best
```

## Decision Records

Every governance decision is recorded for auditability:

```python
# Record a manual decision
client.record_decision(
    portfolio_id=portfolio.id,
    decision="approved_deployment",
    rationale="All checks passed, 2/2 approvals received",
    metadata={
        "approvers": ["lead-agent", "qa-agent"],
        "tests_passed": 142,
        "coverage": "94%"
    }
)

# Query decision history
decisions = client.list_decisions(portfolio_id)
for d in decisions:
    print(f"[{d.timestamp}] {d.decision}: {d.rationale}")
```

## Access Control (Unified Permissions)

```python
from openintent.agents import Coordinator

@Coordinator(
    "access-controlled",
    agents=["dev-a", "dev-b", "reviewer"]
)
class AccessCoordinator:

    async def setup_permissions(self, portfolio):
        # Set fine-grained permissions
        await self.set_permissions(
            portfolio_id=portfolio.id,
            policy="restricted",
            allow=[
                {"agent": "dev-a", "actions": ["read", "write"]},
                {"agent": "dev-b", "actions": ["read", "write"]},
                {"agent": "reviewer", "actions": ["read", "approve"]},
            ],
            delegate={
                "enabled": True,
                "max_depth": 2
            }
        )
```

## YAML Workflow with Governance

```yaml
openintent: "1.0"
info:
  name: "Governed Deployment"

permissions:
  policy: restricted
  allow:
    - agent: dev-team
      actions: [read, write]
    - agent: qa-team
      actions: [read, approve]
    - agent: ops-team
      actions: [read, deploy]

coordinator:
  id: deployment-lead
  strategy: sequential
  guardrails:
    - type: approval
      require_for: [deploy]
      min_approvals: 2
    - type: budget
      max_cost_usd: 50.0

workflow:
  build:
    title: "Build Artifacts"
    assign: dev-team

  test:
    title: "Run Test Suite"
    assign: qa-team
    depends_on: [build]

  approve:
    title: "Approval Gate"
    assign: [qa-team, ops-team]
    depends_on: [test]

  deploy:
    title: "Deploy to Production"
    assign: ops-team
    depends_on: [approve]
```

```python
from openintent.workflow import load_workflow

wf = load_workflow("governed_deployment.yaml")
wf.run()
```
