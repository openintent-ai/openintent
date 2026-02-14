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

---

## Server-Enforced Governance (v0.13.0)

### Approval Gate with Resume

The full pattern: agent attempts completion, server blocks with 403, agent requests approval, coordinator approves, SSE triggers resume.

```python
from openintent import Agent, Coordinator
from openintent import (
    on_assignment,
    on_governance_blocked,
    on_approval_granted,
    on_approval_denied,
)

@Agent("deploy-bot", governance_policy={
    "completion_mode": "require_approval",
    "write_scope": "assigned_only",
    "max_cost": 500.0,
})
class DeployAgent:

    @on_assignment
    async def deploy(self, intent):
        result = await run_deployment(intent)
        # Server returns 403 — governance violation
        await self.async_client.set_status(
            intent.id, "completed", version=intent.version
        )

    @on_governance_blocked
    async def blocked(self, intent, rule, detail):
        if rule == "completion_mode":
            await self.governance.request_approval(
                intent.id, "complete",
                "Deployment successful, requesting sign-off"
            )

    @on_approval_granted
    async def resume(self, intent, approval):
        if approval["action"] == "complete":
            await self.async_client.set_status(
                intent.id, "completed",
                version=intent.version,
                reason="Approved by coordinator"
            )


@Coordinator("lead", agents=["deploy-bot"], governance_policy={
    "completion_mode": "quorum",
    "quorum_threshold": 0.6,
})
class ProjectLead:

    @on_assignment
    async def plan(self, intent):
        await self.delegate(intent, "deploy-bot")

    @on_approval_denied
    async def handle_denial(self, intent, approval):
        await self.escalate(intent.id, "Approval denied")
```

### Querying Governance State

```python
# Get the governance policy for an intent
policy = client.get_governance_policy(intent.id)
print(f"Completion mode: {policy['completion_mode']}")
print(f"Max cost: {policy['max_cost']}")

# List pending approvals
approvals = client.list_approvals(intent.id, status="pending")
for a in approvals:
    print(f"  {a['agent_id']} requests '{a['action']}': {a['reason']}")

# Approve or deny
client.approve_approval(intent.id, approval_id, decided_by="lead")
client.deny_approval(intent.id, approval_id, decided_by="lead")
```

### Cost Ceiling Enforcement

```python
@Agent("expensive-bot", governance_policy={
    "max_cost": 100.0,
})
class ExpensiveAgent:

    @on_governance_blocked
    async def cost_exceeded(self, intent, rule, detail):
        if rule == "max_cost":
            print(f"Cost ceiling hit: {detail}")
            await self.escalate(intent.id, "Budget exceeded")
```
