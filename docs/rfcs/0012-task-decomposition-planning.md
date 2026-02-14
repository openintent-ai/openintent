# RFC-0012: Task Decomposition & Planning

**Status:** Proposed  
**Created:** 2026-02-07  
**Authors:** OpenIntent Contributors  
**Requires:** RFC-0001 (Intents), RFC-0003 (Leasing & Governance), RFC-0004 (Portfolios), RFC-0011 (Access Control)

---

## Abstract

This RFC introduces **Task** as a first-class protocol primitive and evolves **Intent Graph** into **Plan** — a structured execution strategy for achieving intents. Together, these constructs bridge the gap between high-level intent declarations and concrete agent work, enabling LLM coordinators to autonomously decompose, schedule, monitor, and adapt multi-agent workflows with clear human escalation paths and full auditability.

## Motivation

The current OpenIntent protocol defines Intents (desired outcomes), Intent Graphs (dependency DAGs), and Portfolios (collections of intents). However, there is a semantic gap between declaring "I want X" and an agent actually doing concrete work:

1. **Intents are aspirational.** An intent declares a desired outcome but says nothing about *how* to achieve it. When an LLM coordinator decomposes an intent, the resulting work units need their own lifecycle, state tracking, and audit trail — distinct from the parent intent.

2. **Intent Graphs are structural, not strategic.** A graph captures "A depends on B" but not "if B fails, try C instead" or "pause here for human approval before continuing." Execution strategy — ordering, conditionals, checkpoints, rollback — needs a home.

3. **The LLM-as-Coordinator pattern demands it.** When an LLM accesses OpenIntent via MCP (Model Context Protocol) or native tool integration, it needs protocol-level constructs for planning and task management. Without them, the LLM must hold execution state in its context window — making it fragile, non-auditable, and non-portable.

4. **Agent interoperability requires concrete work units.** Different agents (potentially from different vendors, written in different languages) need a shared, typed contract for what they're being asked to do. Tasks provide this contract.

## Terminology

| Term | Definition |
|------|-----------|
| **Intent** | A declaration of desired outcome (unchanged from RFC-0001) |
| **Task** | A concrete, bounded, measurable unit of work derived from an intent |
| **Plan** | An execution strategy for achieving an intent, containing ordered tasks, decision points, and checkpoints. Evolves from Intent Graph. |
| **Portfolio** | An organizational boundary grouping related intents with shared ownership, budget, and access policies (clarified from RFC-0004) |
| **Coordinator** | An agent (human or LLM) responsible for creating plans, assigning tasks, monitoring progress, and handling escalation |
| **Checkpoint** | A named point in a plan where execution pauses for review, approval, or decision |

## Design

### 1. Task

A Task is the atomic unit of work in OpenIntent. It has clear inputs, expected outputs, bounded scope, and a well-defined lifecycle.

#### 1.1 Task Object

```json
{
  "id": "task_01HXYZ",
  "intent_id": "intent_01HABC",
  "plan_id": "plan_01HDEF",
  "name": "fetch_financials",
  "description": "Retrieve Q1 financial data from accounting system",
  "version": 3,
  "state": "running",
  "priority": "normal",

  "input": {
    "quarter": "Q1-2026",
    "source": "accounting_api"
  },
  "output": null,
  "artifacts": [],

  "assigned_agent": "data-agent-01",
  "lease_id": "lease_01HGHI",
  "capabilities_required": ["data_access", "finance"],

  "depends_on": ["task_01HWXY"],
  "blocks": ["task_01HZAB"],

  "retry_policy": "default",
  "timeout_seconds": 300,
  "attempt": 1,
  "max_attempts": 3,

  "permissions": "inherit",

  "created_at": "2026-02-07T10:00:00Z",
  "started_at": "2026-02-07T10:01:00Z",
  "completed_at": null,

  "metadata": {}
}
```

#### 1.2 Task State Machine

```
                    ┌──────────────────────────────────┐
                    │          (any state)              │
                    │              │                    │
                    │              ▼                    │
                    │         ┌─────────┐              │
                    │         │cancelled│              │
                    │         └─────────┘              │
                    │                                   │
  ┌───────┐    ┌───▼──┐    ┌───────┐    ┌───────┐     │
  │pending├───►│ready ├───►│claimed├───►│running│     │
  └───────┘    └──────┘    └───────┘    └─┬─┬─┬─┘     │
                                          │ │ │        │
                  ┌───────────────────────┘ │ └────┐   │
                  │                         │      │   │
                  ▼                         ▼      ▼   │
            ┌─────────┐              ┌──────┐  ┌───────┐
            │completed│              │failed│  │blocked│
            └─────────┘              └──┬───┘  └───┬───┘
                                        │          │
                                        ▼          ▼
                                    ┌──────┐  ┌───────┐
                                    │ready │  │running│
                                    │(retry)│ │(unblock)
                                    └──────┘  └───────┘
```

**States:**

| State | Description | Entered When |
|-------|-------------|-------------|
| `pending` | Created but dependencies not yet satisfied | Task created with unresolved `depends_on` |
| `ready` | All dependencies met, available for claiming | All `depends_on` tasks reach `completed` |
| `claimed` | An agent holds a lease | Agent successfully acquires lease (RFC-0003) |
| `running` | Actively executing | Agent begins work |
| `blocked` | Paused, waiting on external input | Task needs human approval, sub-task completion, or external event |
| `completed` | Successfully finished, outputs recorded | Agent submits results passing validation |
| `failed` | Execution failed | Agent reports error or timeout exceeded |
| `cancelled` | Explicitly terminated | Coordinator or human cancels |
| `skipped` | Bypassed by conditional plan logic | Plan condition evaluated to false |

**Transitions:**

| From | To | Trigger | Event Logged |
|------|----|---------|-------------|
| `pending` | `ready` | All dependencies completed | `task.ready` |
| `ready` | `claimed` | Agent acquires lease | `task.claimed` |
| `claimed` | `running` | Agent starts execution | `task.started` |
| `running` | `completed` | Agent submits successful result | `task.completed` |
| `running` | `failed` | Error or timeout | `task.failed` |
| `running` | `blocked` | Awaiting input/approval/sub-task | `task.blocked` |
| `blocked` | `running` | Input received / approval granted | `task.unblocked` |
| `failed` | `ready` | Retry triggered (RFC-0010) | `task.retrying` |
| `*` | `cancelled` | Explicit cancellation | `task.cancelled` |
| `pending` | `skipped` | Plan condition is false | `task.skipped` |

All state transitions produce append-only events on the parent intent's event log, ensuring full auditability.

#### 1.3 Task vs. Intent

| Aspect | Intent | Task |
|--------|--------|------|
| Scope | Open-ended desired outcome | Bounded, concrete work unit |
| Created by | Human or coordinator | Coordinator decomposing an intent |
| Executed by | Not directly executed | Executed by an agent |
| Completion | Achieved when all tasks in plan succeed | Achieved when work is done and output produced |
| Lifecycle | Long-lived, high-level | Short-lived, operational |
| Has a Plan | Yes | No (but can spawn sub-tasks) |

### 2. Plan (Evolution of Intent Graph)

A Plan is the execution strategy for achieving an intent. It replaces and extends Intent Graph (from RFC-0001) with ordering, conditionals, checkpoints, and rollback semantics.

#### 2.1 Plan Object

```json
{
  "id": "plan_01HDEF",
  "intent_id": "intent_01HABC",
  "version": 2,
  "state": "active",

  "tasks": ["task_01HXYZ", "task_01HWXY", "task_01HZAB"],

  "checkpoints": [
    {
      "id": "cp_01",
      "name": "compliance_review",
      "after_task": "task_01HWXY",
      "requires_approval": true,
      "approvers": ["compliance-officer"],
      "timeout_hours": 24,
      "on_timeout": "escalate"
    }
  ],

  "conditions": [
    {
      "id": "cond_01",
      "task_id": "task_01HZAB",
      "when": "tasks['task_01HWXY'].output.violations_found == true",
      "otherwise": "skip"
    }
  ],

  "on_failure": "pause_and_escalate",
  "on_complete": "notify",

  "created_at": "2026-02-07T10:00:00Z",
  "updated_at": "2026-02-07T10:30:00Z",

  "metadata": {}
}
```

#### 2.2 Plan States

| State | Description |
|-------|-------------|
| `draft` | Plan created but not yet activated |
| `active` | Plan is being executed, tasks are being scheduled |
| `paused` | Execution halted (checkpoint, failure, or manual pause) |
| `completed` | All tasks completed (or skipped), intent achieved |
| `failed` | Plan failed and no recovery path available |
| `cancelled` | Explicitly cancelled |

#### 2.3 Checkpoints

Checkpoints model human-in-the-loop gates within a plan:

- **Approval gates**: Execution pauses, a designated approver reviews, then approves or rejects
- **Review points**: Coordinator presents intermediate results for inspection
- **Decision points**: Human or LLM evaluates conditions and chooses a path

When a checkpoint is reached, the plan transitions to `paused` and a `plan.checkpoint_reached` event is logged. The checkpoint can be resolved by:
- An approver granting approval → plan resumes
- An approver rejecting → plan fails or follows `on_reject` path
- Timeout → follows `on_timeout` policy (escalate, auto-approve, fail)

#### 2.4 Conditions

Conditions enable branching logic within plans:

```json
{
  "task_id": "remediation_task",
  "when": "tasks['audit_task'].output.issues_found > 0",
  "otherwise": "skip"
}
```

The `when` expression is evaluated after the referenced task completes. If false, the task is transitioned to `skipped`.

### 3. Portfolio (Clarified)

With Plan now handling execution strategy, Portfolio (RFC-0004) is clarified as a purely **organizational** construct:

| Concern | Handled By |
|---------|-----------|
| "What are we trying to achieve?" | Intent |
| "How do we achieve it?" | Plan (tasks, ordering, checkpoints) |
| "Who owns this work? What's the budget? Who can see it?" | Portfolio |
| "What depends on what across intents?" | Plan (cross-intent task dependencies) |

A Portfolio provides:
- **Ownership boundary**: Who is responsible for this group of intents
- **Budget scope**: Cost tracking (RFC-0009) aggregated across all intents in the portfolio
- **Access boundary**: Default permissions (RFC-0011) for all intents in the portfolio
- **Organizational grouping**: Reporting, filtering, archival

Portfolios do **not** contain execution logic. They do not specify ordering, conditions, or checkpoints. That is the Plan's responsibility.

#### 3.1 Multi-Intent Coordination

Multiple intents within a portfolio can have cross-intent dependencies. These are expressed at the plan level:

```json
{
  "intent_id": "intent_report",
  "tasks": [
    {
      "name": "generate_summary",
      "depends_on": [
        "intent_audit/task_complete_audit"
      ]
    }
  ]
}
```

Cross-intent task references use the format `{intent_name}/{task_name}`. The coordinator ensures these dependencies are resolved before scheduling the task.

### 4. Permissions & Delegation for Tasks

Tasks inherit permissions from their parent intent (RFC-0011) by default. Task-level overrides support:

#### 4.1 Permission Inheritance

```
Portfolio (default_permission: "restricted")
  └── Intent A (permissions: { allow: [agent-a, agent-b] })
        └── Plan
              ├── Task 1 (permissions: "inherit")     → uses Intent A's permissions
              ├── Task 2 (permissions: { allow: [agent-c] })  → override
              └── Task 3 (permissions: "inherit")     → uses Intent A's permissions
```

#### 4.2 Delegation via Tasks

When a running task requires capabilities the assigned agent doesn't have:

1. Agent calls `task.delegate(capability="legal_review")` 
2. Protocol creates a **sub-task** with:
   - `parent_task_id` pointing to the delegating task
   - Scoped permissions granting the delegatee access to relevant context
   - The delegating task transitions to `blocked`
3. A qualified agent claims the sub-task
4. On sub-task completion, the parent task is unblocked with the sub-task's output

#### 4.3 Escalation

Any task can be escalated to a human:

1. Agent or coordinator calls `task.escalate(reason="Ambiguous compliance requirement")`
2. Task transitions to `blocked` with `blocked_reason: "escalation"`
3. An `task.escalated` event is logged with full context
4. Human reviews via dashboard or API, makes a decision
5. Decision is recorded as an event, task is unblocked

### 5. Python SDK

The SDK should feel familiar to developers who have used Celery, Prefect, or Temporal, while surfacing OpenIntent-specific constructs naturally.

#### 5.1 Defining Tasks

```python
from openintent import task, TaskContext, TaskResult

@task(
    name="fetch_financials",
    capabilities=["data_access", "finance"],
    timeout=300,
    retry={"max_attempts": 3, "backoff": "exponential"},
)
async def fetch_financials(ctx: TaskContext) -> TaskResult:
    quarter = ctx.input["quarter"]
    
    # Do the actual work
    data = await accounting_api.get_financials(quarter)
    
    # Report progress (logged as events)
    await ctx.progress(50, "Retrieved raw data, processing...")
    
    processed = transform(data)
    
    return TaskResult(
        output={"revenue": processed.revenue, "expenses": processed.expenses},
        artifacts=["report.csv"],
    )
```

**Key design choices:**
- `@task` registers a callable with metadata (capabilities, timeout, retry)
- `TaskContext` provides access to inputs, progress reporting, delegation, and escalation
- `TaskResult` is a typed container for outputs and artifacts
- Progress reporting creates events on the audit trail

#### 5.2 Defining Agents

```python
from openintent import agent

@agent(
    name="data-agent",
    tasks=[fetch_financials, fetch_hr_data, run_analysis],
    capabilities=["data_access", "finance", "analytics"],
)
class DataAgent:
    """Agent that handles data retrieval and analysis tasks."""
    
    async def on_task_claimed(self, ctx: TaskContext):
        """Optional hook: called when a task is claimed."""
        pass
    
    async def on_task_failed(self, ctx: TaskContext, error: Exception):
        """Optional hook: called when a task fails."""
        pass
```

**Key design choices:**
- `@agent` binds a set of tasks to an identity with declared capabilities
- Agents can define lifecycle hooks (optional)
- Capability matching is used for automatic task routing

#### 5.3 Creating Plans

Plans can be created declaratively or dynamically:

**Declarative (in code):**

```python
from openintent import intent, Plan, Checkpoint, IntentContext

@intent(name="quarterly_compliance_report")
async def compliance_report(ctx: IntentContext) -> Plan:
    return Plan(
        tasks=[
            fetch_financials.t(quarter=ctx.input["quarter"]),
            fetch_hr_data.t(quarter=ctx.input["quarter"]),
            run_analysis.t()
                .depends_on(fetch_financials, fetch_hr_data),
            generate_report.t()
                .depends_on(run_analysis),
        ],
        checkpoints=[
            Checkpoint(
                after=run_analysis,
                requires_approval=True,
                approvers=["compliance-officer"],
                timeout_hours=24,
            ),
        ],
    )
```

**Dynamic (LLM coordinator):**

```python
async with oi.coordinate("Generate Q1 compliance report") as coord:
    # LLM creates and validates plan
    plan = await coord.plan()
    
    # Human can review before execution
    await coord.review(plan)
    
    # Execute with automatic monitoring, retry, escalation
    result = await coord.execute(plan)
```

**Key design choices:**
- `.t()` creates a task invocation with bound parameters (inspired by Celery's `.s()` signature)
- `.depends_on()` is chainable and accepts task references
- `Checkpoint` is a declarative construct within Plan
- `coordinate()` is the high-level entry point for LLM-as-coordinator

#### 5.4 Task Context API

```python
class TaskContext:
    input: dict                    # Task inputs
    intent: Intent                 # Parent intent
    plan: Plan                     # Parent plan
    
    async def progress(self, pct: int, message: str) -> None:
        """Report progress (creates audit event)."""
    
    async def delegate(self, capability: str, payload: dict) -> TaskResult:
        """Delegate to another agent, blocks until sub-task completes."""
    
    async def escalate(self, reason: str, context: dict = None) -> Decision:
        """Escalate to human, blocks until decision is made."""
    
    async def log(self, message: str, data: dict = None) -> None:
        """Log an event to the audit trail."""
    
    async def get_sibling_output(self, task_name: str) -> dict:
        """Access output from a completed sibling task in the same plan."""
```

#### 5.5 YAML Workflow Integration

Tasks and plans integrate with the existing YAML workflow spec:

```yaml
name: quarterly_compliance
version: "1.0"
intents:
  compliance_report:
    description: "Generate quarterly compliance report"
    permissions:
      policy: restricted
      allow:
        - agent: data-agent
          grant: [read, execute]
        - agent: compliance-officer
          grant: [read, approve]
    
    plan:
      tasks:
        - name: fetch_financials
          capabilities: [data_access, finance]
          input:
            quarter: "{{ trigger.quarter }}"
          timeout: 300
          retry:
            max_attempts: 3

        - name: fetch_hr_data
          capabilities: [data_access, hr]
          input:
            quarter: "{{ trigger.quarter }}"
        
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
          timeout_hours: 24
          on_timeout: escalate

      on_failure: pause_and_escalate
```

### 6. API Endpoints

New endpoints for task and plan management:

#### Tasks

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/v1/intents/{id}/tasks` | Create a task for an intent |
| `GET` | `/v1/intents/{id}/tasks` | List tasks for an intent |
| `GET` | `/v1/tasks/{id}` | Get task by ID |
| `PATCH` | `/v1/tasks/{id}` | Update task (state transitions) |
| `POST` | `/v1/tasks/{id}/claim` | Claim a task (acquire lease) |
| `POST` | `/v1/tasks/{id}/complete` | Mark task completed with output |
| `POST` | `/v1/tasks/{id}/fail` | Mark task failed with error |
| `POST` | `/v1/tasks/{id}/delegate` | Delegate to another agent |
| `POST` | `/v1/tasks/{id}/escalate` | Escalate to human |
| `POST` | `/v1/tasks/{id}/progress` | Report progress |

#### Plans

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/v1/intents/{id}/plan` | Create or update plan for an intent |
| `GET` | `/v1/intents/{id}/plan` | Get current plan |
| `PATCH` | `/v1/plans/{id}` | Update plan (add tasks, modify checkpoints) |
| `POST` | `/v1/plans/{id}/activate` | Activate a draft plan |
| `POST` | `/v1/plans/{id}/pause` | Pause plan execution |
| `POST` | `/v1/plans/{id}/resume` | Resume paused plan |
| `POST` | `/v1/plans/{id}/cancel` | Cancel plan |

#### Checkpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/v1/plans/{id}/checkpoints` | List checkpoints and their status |
| `POST` | `/v1/checkpoints/{id}/approve` | Approve a checkpoint |
| `POST` | `/v1/checkpoints/{id}/reject` | Reject a checkpoint |

All endpoints support optimistic concurrency via `If-Match` headers (consistent with existing protocol design).

### 7. Event Types

New event types added to the intent event log:

| Event | Data |
|-------|------|
| `task.created` | task_id, name, capabilities_required |
| `task.ready` | task_id, resolved_dependencies |
| `task.claimed` | task_id, agent_id, lease_id |
| `task.started` | task_id, agent_id |
| `task.progress` | task_id, percentage, message |
| `task.completed` | task_id, output, artifacts, duration_ms |
| `task.failed` | task_id, error, attempt, will_retry |
| `task.retrying` | task_id, attempt, next_attempt_at |
| `task.blocked` | task_id, reason, blocked_by |
| `task.unblocked` | task_id, resolution |
| `task.delegated` | task_id, sub_task_id, capability, delegated_to |
| `task.escalated` | task_id, reason, escalated_to |
| `task.cancelled` | task_id, reason |
| `task.skipped` | task_id, condition_id, reason |
| `plan.created` | plan_id, task_count |
| `plan.activated` | plan_id |
| `plan.paused` | plan_id, reason |
| `plan.resumed` | plan_id |
| `plan.completed` | plan_id, duration_ms, tasks_completed, tasks_skipped |
| `plan.failed` | plan_id, failed_task_id, error |
| `plan.checkpoint_reached` | plan_id, checkpoint_id, requires_approval |
| `plan.checkpoint_approved` | plan_id, checkpoint_id, approved_by |
| `plan.checkpoint_rejected` | plan_id, checkpoint_id, rejected_by, reason |

### 8. Interaction with Existing RFCs

| RFC | Interaction |
|-----|-------------|
| RFC-0001 (Intents) | Tasks belong to intents. Intent state reflects plan/task progress. |
| RFC-0003 (Leasing) | Task claiming uses the existing lease mechanism. One lease per task. |
| RFC-0003 (Governance) | Plan checkpoints extend governance with task-level approval gates. |
| RFC-0006 (Subscriptions) | Clients can subscribe to task and plan events. |
| RFC-0004 (Portfolios) | Clarified as organizational boundary. No execution semantics. |
| RFC-0008 (LLM Integration) | LLM adapters can be used within task execution. Events include token/cost data. |
| RFC-0009 (Cost Tracking) | Task-level cost tracking. Plan aggregates costs across tasks. |
| RFC-0010 (Retry Policies) | Task retry uses existing retry policy definitions. |
| RFC-0011 (Access Control) | Tasks inherit permissions from intents. Task-level overrides supported. |

## Open Questions

1. **Sub-task depth limit**: Should there be a maximum nesting depth for delegated sub-tasks to prevent infinite recursion?

2. **Plan versioning**: When a coordinator modifies a plan mid-execution (adaptive re-planning), how do we handle tasks that are already running under the old plan version?

3. **Cross-portfolio task dependencies**: Should tasks be allowed to depend on tasks from intents in different portfolios, or should portfolio boundaries be strict?

4. **Task output schema**: Should task definitions include expected output schemas for validation, or is this left to the agent?

## References

- [RFC-0001: Intent Objects](./0001-intent-objects.md)
- [RFC-0003: Agent Leasing](./0003-agent-leasing.md)
- [RFC-0003: Governance & Arbitration](./0003-agent-leasing.md)
- [RFC-0004: Intent Portfolios](./0004-governance-arbitration.md)
- [RFC-0010: Retry Policies](./0010-retry-policies.md)
- [RFC-0011: Access-Aware Coordination](./0011-access-control.md)
- [Celery Task Documentation](https://docs.celeryq.dev/)
- [Prefect Task & Flow Concepts](https://docs.prefect.io/)
- [Temporal Workflow & Activity Model](https://docs.temporal.io/)
