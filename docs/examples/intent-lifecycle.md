# Intent Lifecycle

Intents are the core primitive — typed objects with versioned state, optimistic concurrency, and append-only event logs.

## Creating and Managing Intents (Imperative)

```python
from openintent import OpenIntentClient

client = OpenIntentClient(
    base_url="http://localhost:8000",
    agent_id="my-agent"
)

# Create an intent
intent = client.create_intent(
    title="Analyze customer feedback",
    description="Process Q4 feedback forms and extract themes",
    initial_state={"source": "feedback_forms", "quarter": "Q4"}
)

print(f"Intent ID: {intent.id}")
print(f"Version: {intent.version}")
```

## Versioned State Updates

Every state patch increments the version. Use `If-Match` for safe concurrent updates.

```python
# Patch state — version auto-increments
client.patch_state(
    intent.id,
    {"status": "processing", "themes_found": 0},
    expected_version=intent.version  # Optimistic concurrency
)

# If another agent patched first, you get a 409 Conflict
try:
    client.patch_state(
        intent.id,
        {"themes_found": 5},
        expected_version=1  # Stale version
    )
except ConflictError:
    # Re-fetch and retry
    intent = client.get_intent(intent.id)
    client.patch_state(
        intent.id,
        {"themes_found": 5},
        expected_version=intent.version
    )
```

## Event Logs

Every action is recorded in an append-only log.

```python
# Log a custom event
client.log_event(
    intent_id=intent.id,
    event_type="analysis_started",
    payload={"method": "NLP", "model": "gpt-4"}
)

# Read events
events = client.list_events(intent.id)
for event in events:
    print(f"[{event.timestamp}] {event.event_type}: {event.payload}")
```

## Intent Graphs

Link intents into dependency graphs for complex workflows.

```python
# Create a graph of related intents
parent = client.create_intent(title="Q4 Review")

child_a = client.create_intent(
    title="Feedback Analysis",
    parent_id=parent.id
)

child_b = client.create_intent(
    title="Metrics Summary",
    parent_id=parent.id,
    depends_on=[child_a.id]
)

# Query the graph
graph = client.get_intent_graph(parent.id)
for node in graph.nodes:
    print(f"  {node.title} (depends on: {node.depends_on})")
```

## Attachments

Attach files and structured data to intents.

```python
# Attach a file
client.add_attachment(
    intent_id=intent.id,
    filename="report.pdf",
    content_type="application/pdf",
    data=open("report.pdf", "rb").read()
)

# Attach structured data
client.add_attachment(
    intent_id=intent.id,
    filename="themes.json",
    content_type="application/json",
    data=b'{"themes": ["quality", "pricing", "support"]}'
)

# List attachments
attachments = client.list_attachments(intent.id)
for att in attachments:
    print(f"  {att.filename} ({att.content_type}, {att.size} bytes)")
```

## YAML Workflow

```yaml
openintent: "1.0"
info:
  name: "Feedback Analysis"
  description: "Analyze Q4 customer feedback"

workflow:
  collect:
    title: "Collect Feedback"
    assign: collector
    initial_state:
      source: feedback_forms
      quarter: Q4

  analyze:
    title: "Analyze Themes"
    assign: analyzer
    depends_on: [collect]
    constraints:
      - "Use NLP for theme extraction"
      - "Identify top 5 themes"

  report:
    title: "Generate Report"
    assign: reporter
    depends_on: [analyze]
    attachments:
      - filename: template.md
        content_type: text/markdown
```

```python
from openintent.workflow import load_workflow

wf = load_workflow("feedback_analysis.yaml")
wf.run()
```
