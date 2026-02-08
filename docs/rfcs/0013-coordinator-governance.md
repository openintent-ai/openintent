# RFC-0013: Coordinator Governance & Meta-Coordination

**Status:** Proposed  
**Created:** 2026-02-07  
**Authors:** OpenIntent Contributors  
**Requires:** RFC-0001 (Intents), RFC-0003 (Leasing), RFC-0004 (Governance), RFC-0011 (Access Control), RFC-0012 (Task Decomposition & Planning)

---

## Abstract

This RFC formalizes the **Coordinator** as a governed participant in the OpenIntent protocol. A coordinator — whether an LLM, a human, or a composite system — is subject to the same accountability, leasing, and auditability mechanisms as any other agent. The RFC introduces supervisor hierarchies, coordinator guardrails, plan review gates, coordinator handoff and failover, and decision auditing. Together, these ensure that the entity orchestrating multi-agent work is itself observable, bounded, and overridable.

## Motivation

RFC-0012 introduced Plans and Tasks, enabling a coordinator to decompose intents into concrete work. But the coordinator itself operates outside the protocol's governance model. This creates a critical gap:

1. **No accountability for bad plans.** A coordinator can create an arbitrarily expensive, risky, or nonsensical plan. Nothing in the protocol constrains this or requires review before execution begins.

2. **No failover.** If a coordinator crashes, stalls, or becomes unresponsive, plans in flight have no recovery mechanism. The lease model (RFC-0003) applies to tasks and intents, but not to the coordination role itself.

3. **No supervision hierarchy.** In practice, coordination is layered — an LLM coordinator should have a human supervisor who can override, redirect, or pause. The protocol doesn't model this relationship.

4. **No guardrails.** Budget limits, scope boundaries, delegation depth limits, and escalation thresholds are ad-hoc. The protocol should express these as declarative constraints that the coordinator is bound by.

5. **No decision auditing at the coordination level.** Task events capture what agents do. But the coordinator's *decisions* — why it chose this plan, why it delegated to this agent, why it re-planned — are invisible to the audit trail.

Without these, the "virtuous loop" of LLM-as-coordinator is incomplete: the loop has no governor.

## Terminology

| Term | Definition |
|------|-----------|
| **Coordinator** | An agent (LLM, human, or composite) responsible for plan creation, task scheduling, monitoring, and escalation for one or more intents |
| **Supervisor** | A coordinator's designated overseer, with authority to override, pause, or replace the coordinator |
| **Coordinator Lease** | A lease (RFC-0003) granting an agent the coordinator role for a specific intent or portfolio |
| **Guardrail** | A declarative constraint bounding what a coordinator is allowed to do |
| **Decision Record** | An auditable log entry capturing a coordination decision (plan creation, re-planning, delegation, escalation) with rationale |
| **Plan Review Gate** | A checkpoint requiring supervisor approval before a plan is activated |
| **Heartbeat** | A periodic signal from a coordinator proving it is still active and responsive |

## Design

### 1. Coordinator as a Governed Agent

A coordinator is an agent with a special role. It holds a **coordinator lease** on an intent (or portfolio), granting it authority to create plans, schedule tasks, and make orchestration decisions. Like any lease, it has a TTL, is revocable, and is exclusive.

#### 1.1 Coordinator Lease

```json
{
  "id": "clease_01HABC",
  "intent_id": "intent_01HXYZ",
  "agent_id": "llm-coordinator-01",
  "role": "coordinator",
  "supervisor_id": "human-operator-01",
  "granted_at": "2026-02-07T10:00:00Z",
  "expires_at": "2026-02-07T22:00:00Z",
  "heartbeat_interval_seconds": 60,
  "last_heartbeat": "2026-02-07T10:15:00Z",
  "guardrails": {
    "max_budget_usd": 50.00,
    "max_tasks_per_plan": 20,
    "max_delegation_depth": 3,
    "max_concurrent_tasks": 10,
    "allowed_capabilities": ["data_access", "analytics", "reporting"],
    "requires_plan_review": true,
    "auto_escalate_after_failures": 3,
    "scope": "intent"
  },
  "status": "active",
  "version": 1
}
```

Key properties:
- **`supervisor_id`**: Every coordinator has a supervisor. For LLM coordinators, this is typically a human. For sub-coordinators, it may be a parent coordinator. The chain terminates at a human.
- **`heartbeat_interval_seconds`**: The coordinator must send heartbeats at this interval. Miss two consecutive heartbeats, and failover triggers.
- **`guardrails`**: Declarative constraints the coordinator must operate within (see Section 3).
- **`scope`**: Whether this coordinator lease covers a single intent (`"intent"`) or an entire portfolio (`"portfolio"`).

#### 1.2 Coordinator Registration

A coordinator registers its capabilities and preferences:

```json
{
  "agent_id": "llm-coordinator-01",
  "type": "llm",
  "model": "claude-4",
  "capabilities": ["planning", "monitoring", "escalation", "re-planning"],
  "supported_domains": ["compliance", "data-pipeline", "content"],
  "max_concurrent_intents": 5,
  "preferred_heartbeat_interval": 60,
  "metadata": {
    "provider": "anthropic",
    "context_window": 200000,
    "supports_tools": true
  }
}
```

The `type` field distinguishes coordinator kinds:
- `"llm"` — An LLM acting as coordinator (via MCP or tool integration)
- `"human"` — A human coordinator (via dashboard or API)
- `"composite"` — LLM + human working together (LLM proposes, human approves)
- `"system"` — Automated rule-based coordinator (cron-like, no judgment)

### 2. Supervisor Hierarchy

Every coordinator has a supervisor. This creates a chain of accountability that terminates at a human.

```
Human Operator (ultimate authority)
  └── LLM Coordinator A (portfolio-level)
        ├── LLM Coordinator B (intent-level, compliance domain)
        │     └── Agent workers (task-level)
        └── LLM Coordinator C (intent-level, data domain)
              └── Agent workers (task-level)
```

#### 2.1 Supervisor Authority

A supervisor can:

| Action | Description | Event Logged |
|--------|-------------|-------------|
| **Override plan** | Replace or modify coordinator's plan | `coordinator.plan_overridden` |
| **Pause coordinator** | Temporarily suspend coordinator activity | `coordinator.paused` |
| **Resume coordinator** | Resume a paused coordinator | `coordinator.resumed` |
| **Replace coordinator** | Revoke lease and assign a new coordinator | `coordinator.replaced` |
| **Adjust guardrails** | Tighten or loosen coordinator constraints | `coordinator.guardrails_updated` |
| **Approve plan** | Sign off on a plan at a review gate | `plan.approved_by_supervisor` |
| **Reject plan** | Reject a plan with feedback | `plan.rejected_by_supervisor` |
| **Force-escalate** | Force a specific task to escalate to human | `task.force_escalated` |

#### 2.2 Escalation Chain

When a coordinator encounters something outside its guardrails or capabilities, it escalates to its supervisor:

1. Coordinator hits guardrail (e.g., budget exceeded) → auto-escalates
2. Coordinator is uncertain (e.g., ambiguous requirements) → voluntary escalation
3. Supervisor reviews context (intent, plan, events, coordinator decisions)
4. Supervisor decides: adjust guardrails, override plan, provide guidance, or escalate further
5. Decision is recorded as a `coordinator.escalation_resolved` event

If the supervisor is also a coordinator (not a human), the escalation continues up the chain until it reaches a human. The protocol guarantees the chain terminates — a coordinator lease cannot be created without a `supervisor_id`, and at least one ancestor must have `type: "human"`.

### 3. Guardrails

Guardrails are declarative constraints that the protocol enforces. The coordinator cannot violate these — attempts are rejected with a `guardrail_violation` error, and the attempt is logged.

#### 3.1 Budget Guardrails

```json
{
  "max_budget_usd": 50.00,
  "warn_at_percentage": 80,
  "on_exceed": "pause_and_escalate"
}
```

Integrates with RFC-0009 (Cost Tracking). When cumulative task costs approach the budget, a warning event is logged. On exceed, the specified action triggers (pause, escalate, or fail).

#### 3.2 Scope Guardrails

```json
{
  "max_tasks_per_plan": 20,
  "max_delegation_depth": 3,
  "max_concurrent_tasks": 10,
  "max_plan_versions": 5,
  "allowed_capabilities": ["data_access", "analytics", "reporting"]
}
```

These prevent runaway decomposition (infinite sub-tasks), unbounded delegation chains, resource exhaustion from too many concurrent tasks, and scope creep through capability restrictions.

#### 3.3 Temporal Guardrails

```json
{
  "max_plan_duration_hours": 48,
  "max_task_wait_hours": 4,
  "checkpoint_timeout_hours": 24,
  "require_progress_every_minutes": 30
}
```

These ensure things don't stall indefinitely. If no progress events are recorded within the `require_progress_every_minutes` window, an `coordinator.stalled` event is logged and the supervisor is notified.

#### 3.4 Review Guardrails

```json
{
  "requires_plan_review": true,
  "requires_replan_review": false,
  "auto_escalate_after_failures": 3,
  "require_human_for_capabilities": ["financial_approval", "legal_review"]
}
```

`requires_plan_review` means the coordinator must submit plans for supervisor approval before activation. `require_human_for_capabilities` ensures certain capability requirements always route to humans, never to other LLMs.

### 4. Decision Records

Every significant coordinator decision produces a **Decision Record** — an event on the intent's audit trail capturing what the coordinator decided, why, and what alternatives were considered.

#### 4.1 Decision Record Object

```json
{
  "id": "drec_01HABC",
  "type": "coordinator.decision",
  "coordinator_id": "llm-coordinator-01",
  "intent_id": "intent_01HXYZ",
  "decision_type": "plan_created",
  "summary": "Created 4-task plan for Q1 compliance report",
  "rationale": "Decomposed into data gathering (2 parallel tasks), analysis (1 task dependent on gathering), and report generation (1 task dependent on analysis). Added checkpoint after analysis for compliance officer review.",
  "alternatives_considered": [
    {
      "description": "Single-task approach: one agent does everything",
      "rejected_reason": "No agent has all required capabilities (data_access + analytics + reporting)"
    },
    {
      "description": "5-task plan with separate financial and HR analysis",
      "rejected_reason": "Added complexity with minimal benefit; combined analysis is sufficient"
    }
  ],
  "confidence": 0.85,
  "timestamp": "2026-02-07T10:01:00Z"
}
```

#### 4.2 Decision Types

| Decision Type | When Logged |
|--------------|-------------|
| `plan_created` | Coordinator creates a new plan |
| `plan_modified` | Coordinator re-plans (adds/removes/reorders tasks) |
| `task_assigned` | Coordinator selects an agent for a task |
| `task_delegated` | Coordinator approves or initiates delegation |
| `escalation_initiated` | Coordinator escalates to supervisor |
| `escalation_resolved` | Coordinator receives supervisor guidance and acts |
| `checkpoint_evaluated` | Coordinator makes a decision at a plan checkpoint |
| `failure_handled` | Coordinator decides how to respond to a task failure |
| `guardrail_approached` | Coordinator adjusts behavior to stay within guardrails |
| `coordinator_handoff` | Coordinator transfers control to another coordinator |

Decision records are what make LLM coordination auditable. When a human asks "why did the agent do that?", the decision record provides the answer — not just what happened, but the reasoning and alternatives.

### 5. Coordinator Lifecycle & Failover

#### 5.1 Lifecycle States

```
┌──────────┐    ┌──────┐    ┌──────────┐
│registering├───►│active├───►│completing│
└──────────┘    └──┬─┬─┘    └────┬─────┘
                   │ │           │
                   │ │       ┌───▼────┐
                   │ │       │completed│
                   │ │       └────────┘
                   │ │
              ┌────▼─┘
              │    │
         ┌────▼┐  ┌▼──────────┐
         │paused│  │unresponsive│
         └──┬──┘  └─────┬─────┘
            │           │
            │      ┌────▼────┐
            │      │failed_over│
            │      └─────────┘
            │
        ┌───▼──┐
        │active│ (resumed)
        └──────┘
```

| State | Description |
|-------|-------------|
| `registering` | Coordinator is being set up, guardrails applied |
| `active` | Coordinator is operational, sending heartbeats |
| `paused` | Supervisor has paused the coordinator |
| `unresponsive` | Missed 2+ heartbeats, failover pending |
| `failed_over` | Another coordinator has taken over |
| `completing` | All tasks finishing, coordinator wrapping up |
| `completed` | Coordination finished successfully |

#### 5.2 Heartbeat & Failover

Coordinators send periodic heartbeats:

```json
{
  "type": "coordinator.heartbeat",
  "coordinator_id": "llm-coordinator-01",
  "intent_id": "intent_01HXYZ",
  "timestamp": "2026-02-07T10:15:00Z",
  "active_tasks": 3,
  "pending_decisions": 0,
  "budget_used_usd": 12.50,
  "status_summary": "3 tasks running, analysis 60% complete"
}
```

If two consecutive heartbeats are missed:
1. Coordinator state transitions to `unresponsive`
2. `coordinator.unresponsive` event is logged
3. Supervisor is notified
4. After a grace period (`heartbeat_interval * 3`), failover triggers:
   - A new coordinator is assigned (from a configured failover pool, or the supervisor takes over)
   - The new coordinator receives the full plan, task states, and event history
   - The new coordinator resumes from the last known state
   - `coordinator.failed_over` event records the transition

#### 5.3 Coordinator Handoff

A coordinator can voluntarily hand off to another coordinator:

```json
{
  "type": "coordinator.handoff",
  "from_coordinator": "llm-coordinator-01",
  "to_coordinator": "llm-coordinator-02",
  "reason": "Context window approaching limit, transferring to fresh coordinator",
  "state_summary": {
    "plan_version": 3,
    "tasks_completed": 5,
    "tasks_remaining": 3,
    "key_decisions": ["drec_01", "drec_02", "drec_03"],
    "open_items": ["Checkpoint cp_02 pending approval"]
  }
}
```

This is critical for LLM coordinators: context windows have limits. When a long-running coordination approaches the limit, the coordinator packages its state summary, hands off to a fresh instance, and the new coordinator picks up with the full protocol state (plan, tasks, events) plus the summarized context.

### 6. Composite Coordination

The `composite` coordinator type formalizes the human-LLM collaboration pattern:

```json
{
  "agent_id": "composite-coord-01",
  "type": "composite",
  "components": {
    "proposer": "llm-coordinator-01",
    "approver": "human-operator-01"
  },
  "mode": "propose-approve",
  "auto_approve_threshold": 0.95
}
```

Modes:
- **`propose-approve`**: LLM proposes plans/decisions, human approves or rejects. The default for high-stakes coordination.
- **`act-notify`**: LLM acts autonomously, human is notified of all decisions. For lower-stakes or time-sensitive coordination.
- **`act-audit`**: LLM acts fully autonomously, human can audit asynchronously. For routine, well-understood workflows.

The `auto_approve_threshold` allows high-confidence decisions to proceed without blocking on human approval (only in `propose-approve` mode). If the coordinator's confidence (from the Decision Record) exceeds this threshold, the decision auto-approves with a `decision.auto_approved` event.

### 7. Permissions Integration (RFC-0011)

Coordinator governance integrates with the existing permissions model:

#### 7.1 Coordinator Permissions

```yaml
intent:
  compliance_report:
    permissions:
      policy: restricted
      allow:
        - agent: llm-coordinator-01
          grant: [coordinate, read, delegate]
        - agent: data-agent
          grant: [execute]
        - agent: compliance-officer
          grant: [approve, read]
    
    coordinator:
      agent: llm-coordinator-01
      supervisor: compliance-officer
      guardrails:
        max_budget_usd: 50
        requires_plan_review: true
```

New permission grants:
- **`coordinate`**: Authority to create plans, assign tasks, and make orchestration decisions
- **`approve`**: Authority to approve plans at review gates and resolve checkpoints
- **`supervise`**: Authority to override, pause, or replace a coordinator

#### 7.2 Task-Level Permission Delegation

When a coordinator assigns a task, it delegates a scoped subset of its permissions:

1. Coordinator holds `[coordinate, read, delegate]` on the intent
2. Coordinator creates Task A and assigns it to `data-agent`
3. `data-agent` receives `[execute, read]` on Task A (scoped from coordinator's delegation grant)
4. `data-agent` cannot access other tasks, modify the plan, or escalate outside the task scope

### 8. Python SDK

#### 8.1 Coordinator Definition

```python
from openintent import coordinator, CoordinatorContext, Plan, Guardrails

@coordinator(
    name="compliance-coordinator",
    type="composite",
    mode="propose-approve",
    guardrails=Guardrails(
        max_budget_usd=50.0,
        max_tasks_per_plan=20,
        requires_plan_review=True,
        auto_escalate_after_failures=3,
    ),
)
async def compliance_coordinator(ctx: CoordinatorContext) -> Plan:
    # Coordinator has access to intent, capabilities registry, and agent pool
    available_agents = await ctx.discover_agents(
        capabilities=["data_access", "analytics", "reporting"]
    )
    
    # Create plan with decision rationale
    plan = await ctx.propose_plan(
        tasks=[
            fetch_financials.t(quarter=ctx.intent.input["quarter"]),
            fetch_hr_data.t(quarter=ctx.intent.input["quarter"]),
            run_analysis.t().depends_on(fetch_financials, fetch_hr_data),
            generate_report.t().depends_on(run_analysis),
        ],
        checkpoints=[
            Checkpoint(after=run_analysis, approvers=["compliance-officer"]),
        ],
        rationale="Parallel data gathering, sequential analysis, human review before report generation",
    )
    
    # In propose-approve mode, this blocks until supervisor approves
    return plan
```

#### 8.2 Supervisor Hooks

```python
from openintent import on_plan_proposed, on_escalation, on_guardrail_warning

@on_plan_proposed
async def review_plan(ctx: SupervisorContext, plan: Plan):
    """Called when a coordinator proposes a plan for review."""
    if plan.estimated_cost_usd > 30:
        return ctx.reject(reason="Budget too high, simplify the plan")
    return ctx.approve()

@on_escalation
async def handle_escalation(ctx: SupervisorContext, escalation: Escalation):
    """Called when a coordinator escalates a decision."""
    return ctx.decide(
        action="proceed",
        guidance="Use the conservative interpretation of section 4.2",
    )

@on_guardrail_warning
async def handle_guardrail(ctx: SupervisorContext, warning: GuardrailWarning):
    """Called when a coordinator approaches a guardrail limit."""
    if warning.guardrail == "budget" and warning.percentage > 90:
        return ctx.adjust_guardrail(max_budget_usd=75.0)
```

#### 8.3 Coordinator Context API

```python
class CoordinatorContext:
    intent: Intent                        # The intent being coordinated
    plan: Plan | None                     # Current plan (if exists)
    guardrails: Guardrails                # Active guardrails
    supervisor: AgentRef                  # Supervisor reference
    
    async def propose_plan(self, tasks, checkpoints, rationale) -> Plan:
        """Create a plan and submit for review (if required by guardrails)."""
    
    async def replan(self, reason: str, changes: PlanChanges) -> Plan:
        """Modify the active plan with a new version."""
    
    async def discover_agents(self, capabilities: list[str]) -> list[Agent]:
        """Find agents matching required capabilities."""
    
    async def assign_task(self, task_id: str, agent_id: str, rationale: str) -> None:
        """Assign a task to an agent (creates decision record)."""
    
    async def escalate(self, reason: str, context: dict = None) -> Decision:
        """Escalate to supervisor, blocks until resolved."""
    
    async def record_decision(self, decision_type: str, summary: str,
                               rationale: str, confidence: float = None) -> None:
        """Explicitly log a coordination decision."""
    
    async def heartbeat(self, status_summary: str = None) -> None:
        """Send a heartbeat (automatic in SDK, manual override available)."""
    
    async def handoff(self, to_coordinator: str, reason: str) -> None:
        """Transfer coordination to another coordinator."""
    
    async def check_guardrails(self) -> GuardrailStatus:
        """Check current guardrail usage and remaining budget."""
```

#### 8.4 YAML Workflow Integration

```yaml
name: quarterly_compliance
version: "1.0"

coordinator:
  agent: llm-coordinator
  type: composite
  mode: propose-approve
  supervisor: compliance-officer
  guardrails:
    max_budget_usd: 50
    max_tasks_per_plan: 20
    max_delegation_depth: 3
    requires_plan_review: true
    auto_escalate_after_failures: 3
    require_progress_every_minutes: 30
  heartbeat_interval: 60
  failover:
    pool: [llm-coordinator-backup]
    grace_period_seconds: 180

intents:
  compliance_report:
    description: "Generate quarterly compliance report"
    permissions:
      policy: restricted
      allow:
        - agent: llm-coordinator
          grant: [coordinate, delegate]
        - agent: data-agent
          grant: [execute]
        - agent: compliance-officer
          grant: [approve, supervise]

    plan:
      tasks:
        - name: fetch_financials
          capabilities: [data_access, finance]
          timeout: 300
        - name: fetch_hr_data
          capabilities: [data_access, hr]
          timeout: 300
        - name: run_analysis
          capabilities: [analytics]
          depends_on: [fetch_financials, fetch_hr_data]
        - name: generate_report
          capabilities: [reporting]
          depends_on: [run_analysis]

      checkpoints:
        - after: run_analysis
          requires_approval: true
          approvers: [compliance-officer]

      on_failure: pause_and_escalate
```

### 9. API Endpoints

#### Coordinator Management

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/v1/coordinators` | Register a coordinator |
| `GET` | `/v1/coordinators/{id}` | Get coordinator details |
| `PATCH` | `/v1/coordinators/{id}` | Update coordinator registration |
| `POST` | `/v1/intents/{id}/coordinator` | Assign coordinator to intent |
| `DELETE` | `/v1/intents/{id}/coordinator` | Remove coordinator from intent |
| `POST` | `/v1/coordinators/{id}/heartbeat` | Send heartbeat |
| `POST` | `/v1/coordinators/{id}/handoff` | Initiate coordinator handoff |

#### Guardrails

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/v1/coordinators/{id}/guardrails` | Get active guardrails |
| `PATCH` | `/v1/coordinators/{id}/guardrails` | Update guardrails (supervisor only) |
| `GET` | `/v1/coordinators/{id}/guardrails/status` | Get guardrail usage and remaining budget |

#### Decision Records

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/v1/intents/{id}/decisions` | List decision records for an intent |
| `GET` | `/v1/decisions/{id}` | Get a specific decision record |
| `POST` | `/v1/intents/{id}/decisions` | Create a decision record |

#### Supervisor Actions

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/v1/coordinators/{id}/pause` | Pause coordinator |
| `POST` | `/v1/coordinators/{id}/resume` | Resume coordinator |
| `POST` | `/v1/coordinators/{id}/replace` | Replace coordinator |
| `POST` | `/v1/plans/{id}/approve` | Approve a plan at review gate |
| `POST` | `/v1/plans/{id}/reject` | Reject a plan at review gate |

All endpoints support optimistic concurrency via `If-Match` headers.

### 10. Event Types

| Event | Data |
|-------|------|
| `coordinator.registered` | coordinator_id, type, capabilities |
| `coordinator.assigned` | coordinator_id, intent_id, supervisor_id |
| `coordinator.heartbeat` | coordinator_id, active_tasks, budget_used |
| `coordinator.paused` | coordinator_id, paused_by, reason |
| `coordinator.resumed` | coordinator_id, resumed_by |
| `coordinator.unresponsive` | coordinator_id, last_heartbeat, missed_count |
| `coordinator.failed_over` | old_coordinator_id, new_coordinator_id, state_transferred |
| `coordinator.handoff` | from_coordinator, to_coordinator, reason |
| `coordinator.replaced` | old_coordinator_id, new_coordinator_id, replaced_by, reason |
| `coordinator.completed` | coordinator_id, summary |
| `coordinator.decision` | decision_type, summary, rationale, confidence |
| `coordinator.escalation_initiated` | coordinator_id, reason, escalated_to |
| `coordinator.escalation_resolved` | coordinator_id, resolved_by, action |
| `coordinator.plan_overridden` | coordinator_id, overridden_by, old_plan_version, new_plan_version |
| `coordinator.guardrails_updated` | coordinator_id, updated_by, changes |
| `coordinator.guardrail_warning` | coordinator_id, guardrail, current_value, limit |
| `coordinator.guardrail_violation` | coordinator_id, guardrail, attempted_value, limit |
| `plan.approved_by_supervisor` | plan_id, approved_by |
| `plan.rejected_by_supervisor` | plan_id, rejected_by, reason |
| `decision.auto_approved` | decision_id, confidence, threshold |

### 11. Interaction with Existing RFCs

| RFC | Interaction |
|-----|-------------|
| RFC-0001 (Intents) | Coordinators are assigned to intents. Intent state reflects coordinator status. |
| RFC-0003 (Leasing) | Coordinator lease extends lease model with heartbeat, guardrails, and supervisor. |
| RFC-0004 (Governance) | Coordinator decisions integrate with governance pipeline. Supervisor actions use arbitration. |
| RFC-0006 (Subscriptions) | Clients can subscribe to coordinator events (heartbeats, decisions, escalations). |
| RFC-0007 (Portfolios) | Coordinator lease can scope to a portfolio for cross-intent coordination. |
| RFC-0009 (Cost Tracking) | Budget guardrails integrate with cost tracking. Decision records include cost impact. |
| RFC-0010 (Retry Policies) | Coordinator failure triggers retry/failover. Task retry counts towards guardrail limits. |
| RFC-0011 (Access Control) | New permission grants (coordinate, approve, supervise). Task-level delegation scoping. |
| RFC-0012 (Tasks & Plans) | Coordinator creates and manages plans and tasks. Plan review gates are coordinator-level checkpoints. |

## Open Questions

1. **Coordinator-to-coordinator trust**: When a coordinator delegates sub-coordination to another LLM coordinator, what trust model applies? Should there be capability attestation or reputation scoring?

2. **Decision record granularity**: How much detail should decision records contain? Every micro-decision (which agent to pick) vs. only major decisions (plan creation, re-planning)? Too much noise defeats the purpose of auditability.

3. **Guardrail inheritance**: Should sub-coordinators inherit their parent coordinator's guardrails, or should they be independently configured? Inheritance is simpler but may be too restrictive.

4. **Multi-coordinator consensus**: For high-stakes intents, should the protocol support multiple coordinators that must reach consensus before acting? This adds resilience but also complexity and latency.

## References

- [RFC-0001: Intent Objects](./0001-intent-objects.md)
- [RFC-0003: Agent Leasing](./0003-agent-leasing.md)
- [RFC-0004: Governance & Arbitration](./0004-governance-arbitration.md)
- [RFC-0009: Cost & Resource Tracking](./0009-cost-tracking.md)
- [RFC-0011: Access-Aware Coordination](./0011-access-control.md)
- [RFC-0012: Task Decomposition & Planning](./0012-task-decomposition-planning.md)
- [Temporal Workflow Determinism](https://docs.temporal.io/workflows#deterministic-constraints)
- [Kubernetes Controller Pattern](https://kubernetes.io/docs/concepts/architecture/controller/)
