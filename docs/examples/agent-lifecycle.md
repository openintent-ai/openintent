# Agent Lifecycle & Health

Agent registration, heartbeats, health monitoring, graceful drain, and agent pools.

## Agent Registration

```python
from openintent import OpenIntentClient

client = OpenIntentClient(
    base_url="http://localhost:8000",
    agent_id="worker-001"
)

# Register with capabilities and capacity
client.agents.register(
    agent_id="worker-001",
    role_id="data-processor",  # Shared role for pooling
    capabilities=["python", "data-analysis", "ml"],
    capacity=5,  # Max concurrent intents
    metadata={"version": "2.1", "region": "us-east"}
)
```

## Declarative Registration with @Agent

```python
from openintent.agents import Agent, on_assignment, on_drain

@Agent(
    "worker-001",
    role_id="data-processor",
    capabilities=["python", "data-analysis"],
    capacity=5,
    auto_heartbeat=True
)
class DataProcessor:

    @on_assignment
    async def handle(self, intent):
        return {"status": "processed"}

    @on_drain
    async def draining(self):
        # Graceful shutdown — finish current work, accept no new tasks
        print("Draining: finishing current tasks...")
        await self.finish_current_work()

DataProcessor.run()
```

## Heartbeats

```python
# Manual heartbeat (when not using auto_heartbeat)
client.agents.heartbeat(agent_id="worker-001")

# Heartbeat with status update
client.agents.heartbeat(
    agent_id="worker-001",
    status="active",
    current_load=3
)
```

## Agent Status Lifecycle

```
active -> unhealthy -> dead
active -> draining -> deregistered
```

```python
# Check agent health
agent = client.agents.get("worker-001")
print(f"Status: {agent.status}")        # active, unhealthy, dead, draining
print(f"Last heartbeat: {agent.last_heartbeat}")
print(f"Current load: {agent.current_load}/{agent.capacity}")

# Initiate graceful drain
client.agents.drain(
    agent_id="worker-001",
    timeout_seconds=300  # Finish work within 5 minutes
)

# Deregister
client.agents.deregister(agent_id="worker-001")
```

## Agent Pools

Multiple instances share a `role_id` for load distribution:

```python
from openintent.agents import Agent, on_assignment

# Three instances with the same role_id form a pool
@Agent("worker-001", role_id="processor", auto_heartbeat=True)
class Worker1:
    @on_assignment
    async def handle(self, intent):
        return {"handled_by": "worker-001"}

@Agent("worker-002", role_id="processor", auto_heartbeat=True)
class Worker2:
    @on_assignment
    async def handle(self, intent):
        return {"handled_by": "worker-002"}

# Assignment to role_id="processor" picks an available instance
```

## YAML Workflow with Agent Lifecycle

```yaml
openintent: "1.0"
info:
  name: "Pool-Based Processing"

agents:
  - id: processor-pool
    role_id: processor
    capacity: 10
    auto_heartbeat: true
    heartbeat_interval_seconds: 30
    drain_timeout_seconds: 300

workflow:
  ingest:
    title: "Ingest Data"
    assign: processor  # Assigned to pool by role_id

  transform:
    title: "Transform Data"
    assign: processor
    depends_on: [ingest]

  load:
    title: "Load Results"
    assign: processor
    depends_on: [transform]
```

```python
from openintent.workflow import load_workflow

wf = load_workflow("pool_processing.yaml")
wf.run()
```
