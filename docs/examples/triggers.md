# Triggers & Reactive Scheduling

Triggers are standing declarations that automatically create intents when conditions are met — schedule (cron), event (protocol-reactive), or webhook (external HTTP).

## Schedule Trigger (Cron)

```python
from openintent import OpenIntentClient

client = OpenIntentClient(
    base_url="http://localhost:8000",
    agent_id="scheduler"
)

# Create a cron-based trigger
client.triggers.create(
    name="daily_report",
    type="schedule",
    schedule="0 9 * * *",  # Every day at 9 AM
    intent_template={
        "title": "Daily Status Report",
        "assign": "reporter",
        "initial_state": {"report_type": "daily"}
    }
)
```

## Event Trigger (Protocol-Reactive)

React to protocol events and create new intents automatically:

```python
# Trigger when any intent completes
client.triggers.create(
    name="post_completion_review",
    type="event",
    event_type="intent_completed",
    filter={"namespace": "production"},
    intent_template={
        "title": "Review: {{ source_intent.title }}",
        "assign": "reviewer",
        "initial_state": {
            "source_intent_id": "{{ source_intent.id }}",
            "completed_at": "{{ event.timestamp }}"
        }
    }
)

# Trigger on agent health change
client.triggers.create(
    name="agent_failure_alert",
    type="event",
    event_type="agent_status_changed",
    filter={"new_status": "dead"},
    intent_template={
        "title": "Alert: Agent {{ agent.id }} is dead",
        "assign": "ops-agent",
        "initial_state": {
            "failed_agent": "{{ agent.id }}",
            "last_heartbeat": "{{ agent.last_heartbeat }}"
        }
    }
)
```

## Webhook Trigger (External HTTP)

Accept external events via HTTP and create intents:

```python
# Create a webhook trigger
webhook = client.triggers.create(
    name="github_push",
    type="webhook",
    payload_transform={
        "title": "Build: {{ payload.repository.name }}",
        "assign": "ci-agent",
        "initial_state": {
            "repo": "{{ payload.repository.full_name }}",
            "branch": "{{ payload.ref }}",
            "commit": "{{ payload.head_commit.id }}"
        }
    }
)

print(f"Webhook URL: {webhook.url}")
# Configure this URL in GitHub webhook settings
```

## Declarative Triggers with @Trigger

```python
from openintent.agents import Agent, on_assignment, Trigger

@Trigger
class DailyCleanup:
    type = "schedule"
    schedule = "0 2 * * *"  # 2 AM daily
    intent_template = {
        "title": "Nightly Cleanup",
        "assign": "janitor"
    }

@Trigger
class OnFailure:
    type = "event"
    event_type = "intent_failed"
    intent_template = {
        "title": "Retry: {{ source_intent.title }}",
        "assign": "{{ source_intent.assign }}"
    }
    deduplication = "skip"  # Don't create duplicate retry intents

@Agent("janitor", auto_heartbeat=True)
class JanitorAgent:

    @on_assignment
    async def handle(self, intent):
        await self.cleanup_old_data()
        return {"status": "cleaned"}
```

## Deduplication

Control how triggers handle repeated firings:

```python
client.triggers.create(
    name="rate_limited_alert",
    type="event",
    event_type="budget_exceeded",
    deduplication="skip",  # "allow", "skip", or "queue"
    intent_template={
        "title": "Budget Alert",
        "assign": "finance-agent"
    }
)
```

## Trigger Chains and Depth Limits

Triggers can cascade (trigger A creates an intent that fires trigger B), with depth limits to prevent infinite loops:

```python
# This trigger creates an intent that might fire another trigger
client.triggers.create(
    name="cascading_review",
    type="event",
    event_type="intent_completed",
    max_cascade_depth=3,  # Prevent infinite loops
    intent_template={
        "title": "Review: {{ source_intent.title }}",
        "assign": "reviewer"
    }
)
```

## YAML Workflow with Triggers

```yaml
openintent: "1.0"
info:
  name: "Event-Driven Pipeline"

triggers:
  - name: new_data_trigger
    type: webhook
    payload_transform:
      title: "Process: {{ payload.dataset_name }}"
      assign: processor
      initial_state:
        dataset_id: "{{ payload.dataset_id }}"

  - name: nightly_report
    type: schedule
    schedule: "0 22 * * *"
    intent_template:
      title: "Nightly Summary"
      assign: reporter

  - name: failure_retry
    type: event
    event_type: intent_failed
    deduplication: skip
    max_cascade_depth: 2
    intent_template:
      title: "Retry: {{ source_intent.title }}"
      assign: "{{ source_intent.assign }}"

workflow:
  process:
    title: "Process Dataset"
    assign: processor

  summarize:
    title: "Generate Summary"
    assign: reporter
    depends_on: [process]
```

```python
from openintent.workflow import load_workflow

wf = load_workflow("event_driven.yaml")
wf.run()
```
