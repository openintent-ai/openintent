# Task Decomposition & Planning

Tasks are first-class primitives that break complex intents into smaller, trackable units of work.

## Declarative Planning with @Agent

```python
from openintent.agents import Agent, on_assignment, Plan

@Plan
class ResearchPlan:
    strategy = "hierarchical"
    max_depth = 3
    auto_decompose = True

@Agent("planner", auto_heartbeat=True)
class PlanningAgent:

    @on_assignment
    async def handle(self, intent):
        # Decompose intent into tasks
        plan = await self.tasks.create_plan(
            intent_id=intent.id,
            tasks=[
                {"title": "Literature review", "assign": "researcher"},
                {"title": "Data collection", "assign": "collector", "depends_on": ["Literature review"]},
                {"title": "Analysis", "assign": "analyst", "depends_on": ["Data collection"]},
                {"title": "Write report", "assign": "writer", "depends_on": ["Analysis"]},
            ]
        )
        return {"plan_id": plan.id, "task_count": len(plan.tasks)}
```

## Imperative Task Management

```python
from openintent import OpenIntentClient

client = OpenIntentClient(
    base_url="http://localhost:8000",
    agent_id="task-manager"
)

intent = client.get_intent(intent_id)

# Create tasks under an intent
task_a = client.create_task(
    intent_id=intent.id,
    title="Gather requirements",
    description="Interview stakeholders and document needs"
)

task_b = client.create_task(
    intent_id=intent.id,
    title="Design solution",
    depends_on=[task_a.id]
)

task_c = client.create_task(
    intent_id=intent.id,
    title="Implement prototype",
    depends_on=[task_b.id]
)

# Update task status
client.update_task(task_a.id, status="in_progress")
client.update_task(task_a.id, status="completed", result={"requirements": [...]})

# Query task tree
tasks = client.list_tasks(intent_id=intent.id)
for t in tasks:
    print(f"  [{t.status}] {t.title}")
```

## Nested Task Decomposition

Tasks can be recursively decomposed:

```python
# Top-level task
parent_task = client.create_task(
    intent_id=intent.id,
    title="Build authentication system"
)

# Sub-tasks
client.create_task(
    intent_id=intent.id,
    parent_task_id=parent_task.id,
    title="Implement login endpoint"
)

client.create_task(
    intent_id=intent.id,
    parent_task_id=parent_task.id,
    title="Implement registration endpoint"
)

client.create_task(
    intent_id=intent.id,
    parent_task_id=parent_task.id,
    title="Add JWT token generation"
)
```

## YAML Workflow with Planning

```yaml
openintent: "1.0"
info:
  name: "Product Launch"

plan:
  strategy: hierarchical
  max_depth: 3
  auto_decompose: true

workflow:
  research:
    title: "Market Research"
    assign: market-analyst
    plan:
      tasks:
        - title: "Competitor analysis"
        - title: "Customer interviews"
          depends_on: ["Competitor analysis"]
        - title: "Market sizing"

  design:
    title: "Product Design"
    assign: designer
    depends_on: [research]

  develop:
    title: "Development Sprint"
    assign: dev-team
    depends_on: [design]
    plan:
      tasks:
        - title: "Backend API"
        - title: "Frontend UI"
        - title: "Integration tests"
          depends_on: ["Backend API", "Frontend UI"]

  launch:
    title: "Go to Market"
    assign: marketing
    depends_on: [develop]
```

```python
from openintent.workflow import load_workflow

wf = load_workflow("product_launch.yaml")

# Plan is automatically created with tasks
wf.run()
```
