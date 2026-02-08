---
title: Task Planning
---

# Task Planning

Task Planning introduces **Task** as a first-class work unit and **Plan** as an execution strategy. Tasks bridge the gap between high-level intents ("I want X") and concrete agent work. Defined in [RFC-0012](../rfcs/0012-task-decomposition-planning.md).

## Concepts

| Term | Description |
|------|-------------|
| **Intent** | A desired outcome (unchanged) |
| **Task** | A concrete, bounded, measurable unit of work derived from an intent |
| **Plan** | An execution strategy containing ordered tasks, decision points, and checkpoints |
| **Checkpoint** | A named point where execution pauses for review or approval |

## Creating Tasks

```python
# Create a task under an intent
task = client.tasks.create(
    intent_id=intent.id,
    name="fetch_financials",
    description="Retrieve Q1 financial data from accounting system",
    input={"quarter": "Q1-2026", "source": "accounting_api"},
    priority="normal",
    assign="data-agent"
)

print(f"Task: {task.name} ({task.state})")
```

### Task Lifecycle

```
pending → running → completed
                  ↘ failed → pending (retry)
       ↘ skipped
```

| State | Description |
|-------|-------------|
| `pending` | Task created, awaiting assignment |
| `running` | Agent is actively working on the task |
| `completed` | Task finished successfully |
| `failed` | Task encountered an error |
| `skipped` | Task was bypassed (conditional logic) |

## Completing Tasks

```python
# Mark task as completed with output
completed = client.tasks.complete(
    intent_id=intent.id,
    task_id=task.id,
    output={"revenue": 1500000, "expenses": 980000}
)

# Mark task as failed
client.tasks.fail(
    intent_id=intent.id,
    task_id=task.id,
    error="API returned 503 — service unavailable"
)
```

## Using Tasks in Agents

The `@Agent` decorator provides a `self.tasks` proxy for task operations:

```python
from openintent.agents import Agent, on_assignment, on_task

@Agent("analyst")
class AnalystAgent:

    @on_assignment
    async def handle(self, intent):
        # Create subtasks for the intent
        await self.tasks.create(
            intent_id=intent.id,
            name="gather_data",
            input={"source": "database"}
        )
        await self.tasks.create(
            intent_id=intent.id,
            name="analyze_data",
            input={"method": "regression"},
            depends_on=["gather_data"]
        )

    @on_task(status="completed")
    async def on_subtask_done(self, intent, task):
        """Called when any subtask completes."""
        if task.name == "gather_data":
            return {"data_ready": True}
        elif task.name == "analyze_data":
            return {"analysis_complete": True, "result": task.output}
```

## Plans

Plans define execution strategy beyond simple dependency ordering:

```python
from openintent.agents import Plan

@Plan(
    name="research-plan",
    strategy="sequential",       # sequential | parallel | adaptive
    max_concurrent=3,
    failure_policy="retry_then_skip"  # fail_fast | retry | skip | retry_then_skip
)
class ResearchPlan:
    gather = {"assign": "researcher", "priority": "high"}
    analyze = {"assign": "analyst", "depends_on": ["gather"]}
    synthesize = {"assign": "writer", "depends_on": ["analyze"]}
```

### Execution Strategies

| Strategy | Behavior |
|----------|----------|
| `sequential` | Tasks execute one at a time in dependency order |
| `parallel` | Independent tasks run simultaneously |
| `adaptive` | Coordinator adjusts based on results and conditions |

### Failure Policies

| Policy | Behavior |
|--------|----------|
| `fail_fast` | Stop the plan on first failure |
| `retry` | Retry failed tasks per retry policy |
| `skip` | Skip failed tasks and continue |
| `retry_then_skip` | Retry first, then skip if still failing |

## Plans in YAML Workflows

```yaml
workflow:
  research:
    title: "Research Phase"
    assign: researcher

  analysis:
    title: "Analysis Phase"
    assign: analyst
    depends_on: [research]

plan:
  strategy: adaptive
  max_concurrent: 2
  failure_policy: retry_then_skip
  checkpoints:
    - after: research
      require_approval: true
      approvers: [lead]
```

## Checkpoints

Checkpoints pause execution for review or approval:

```python
# In a coordinator
@Coordinator("project-manager", agents=["researcher", "analyst"])
class ProjectManager:

    @on_assignment
    async def plan(self, intent):
        # Create a plan with checkpoints
        await self.tasks.create(
            intent_id=intent.id,
            name="research",
            assign="researcher"
        )
        await self.tasks.create(
            intent_id=intent.id,
            name="checkpoint_review",
            type="checkpoint",
            description="Review research before proceeding",
            depends_on=["research"]
        )
        await self.tasks.create(
            intent_id=intent.id,
            name="analysis",
            assign="analyst",
            depends_on=["checkpoint_review"]
        )
```

!!! info "Tasks vs Intents"
    An intent declares *what* you want to achieve. A task specifies *one concrete step* toward that goal. Multiple tasks compose into a plan that fulfills the intent.

## Next Steps

- [Coordinator Patterns](coordinators.md) — Orchestrating multi-agent plans
- [Portfolios](portfolios.md) — Organizing intents with shared governance
- [Agent Abstractions](agents.md) — `@on_task` lifecycle decorators
