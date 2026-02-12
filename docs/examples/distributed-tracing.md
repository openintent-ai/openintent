# Distributed Tracing

End-to-end tracing for multi-agent workflows with automatic context propagation.

## Start a New Trace

```python
from openintent import TracingContext

# Create a root tracing context
ctx = TracingContext.new_root()
print(f"Trace ID: {ctx.trace_id}")  # 128-bit hex
```

## Log Events with Trace Context

```python
from openintent import OpenIntentClient

client = OpenIntentClient(
    base_url="http://localhost:8000",
    agent_id="coordinator"
)

# Log an event with tracing fields
event = client.log_event(
    intent_id="intent-123",
    event_type="tool_invocation",
    payload={
        "tool_name": "web_search",
        "arguments": {"query": "latest data"},
        "result": {"urls": ["..."]},
        "duration_ms": 342.5
    },
    trace_id=ctx.trace_id,
    parent_event_id=None,  # Root span
)
```

## Propagate Context Through Tool Handlers

```python
from openintent import Agent, TracingContext, on_assignment, ToolDef

# Define a tool that accepts tracing context
async def delegate_to_researcher(query: str, tracing: TracingContext = None):
    """This tool delegates work to another agent, passing trace context."""
    researcher = ResearchAgent(tracing_context=tracing)
    return await researcher.run(query)

# Normal tools work without changes
def calculator(expression: str):
    return {"result": eval(expression)}

@Agent("coordinator", tools=[
    ToolDef(
        name="delegate_research",
        description="Delegate research to specialist",
        parameters={"query": {"type": "string"}},
        handler=delegate_to_researcher,
    ),
    ToolDef(
        name="calculate",
        description="Evaluate expression",
        parameters={"expression": {"type": "string"}},
        handler=calculator,
    ),
])
class CoordinatorAgent:
    @on_assignment
    async def handle(self, intent):
        return await self.think("Research and calculate results")
```

## Query a Complete Trace

```python
# Retrieve all events across all intents sharing a trace ID
events = client.list_events(
    trace_id="4bf92f3577b34da6a3ce929d0e0e4736"
)

# Build the call tree
roots = [e for e in events if e.parent_event_id is None]

def print_tree(event, indent=0):
    children = [e for e in events if e.parent_event_id == event.id]
    prefix = "  " * indent
    print(f"{prefix}{event.event_type}: {event.payload.get('tool_name', '?')}")
    for child in children:
        print_tree(child, indent + 1)

for root in roots:
    print_tree(root)
```

## Trace Tree Visualization

```text
Trace: 4bf92f3577b34da6a3ce929d0e0e4736

User Request
└── Coordinator Agent
    ├── tool_invocation: web_search          (evt_001, parent: null)
    ├── tool_invocation: delegate_research   (evt_002, parent: evt_001)
    │   └── Research Agent
    │       ├── tool_invocation: fetch_data  (evt_003, parent: evt_002)
    │       └── tool_invocation: summarize   (evt_004, parent: evt_003)
    └── tool_invocation: format_response     (evt_005, parent: evt_004)
```

## TracingContext API

```python
from openintent import TracingContext

# Create new root trace
ctx = TracingContext.new_root()

# Create child context after emitting an event
child = ctx.child(event_id="evt_001")

# Serialize for transport
data = ctx.to_dict()  # {"trace_id": "...", "parent_event_id": "..."}

# Deserialize (returns None if trace_id missing)
restored = TracingContext.from_dict(data)
```
