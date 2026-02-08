---
title: Triggers & Reactive Scheduling
---

# Triggers & Reactive Scheduling

Triggers are standing declarations that automatically create intents when conditions are met. They enable reactive, event-driven coordination without polling. Three trigger types — schedule, event, and webhook — cover time-based, protocol-reactive, and external activation patterns. Defined in [RFC-0017](../rfcs/0017-triggers-reactive-scheduling.md).

## Trigger Types

| Type | Activation | Example |
|------|-----------|---------|
| `schedule` | Cron expression | Daily report at 9am |
| `event` | Protocol event | Run analysis when data arrives |
| `webhook` | External HTTP call | Deploy when CI passes |

## Creating Triggers

### Schedule Triggers

```python
# Create a daily trigger
trigger = client.triggers.create(
    name="daily-report",
    type="schedule",
    cron="0 9 * * *",  # Every day at 9:00 AM
    intent_template={
        "title": "Generate daily report",
        "assign": "report-agent",
        "initial_state": {"report_date": "{{ today }}"}
    }
)
```

### Event Triggers

```python
# Trigger when a specific event occurs
trigger = client.triggers.create(
    name="on-data-ready",
    type="event",
    event_type="state_patched",
    condition={"key": "data_status", "value": "ready"},
    intent_template={
        "title": "Analyze new data",
        "assign": "analyst",
        "initial_state": {"source_intent": "{{ source_intent_id }}"}
    }
)
```

#### Standard Event Types

| Event Type | Description |
|------------|-------------|
| `intent_created` | A new intent was created |
| `status_changed` | Intent status transitioned |
| `state_patched` | Intent state was updated |
| `intent_completed` | Intent reached completed status |
| `intent_abandoned` | Intent was abandoned |
| `agent_assigned` | Agent was assigned to an intent |
| `lease_acquired` | A lease was acquired |
| `lease_released` | A lease was released |
| `task_completed` | A task finished |
| `task_failed` | A task failed |
| `cost_threshold` | Cost exceeded threshold |

### Webhook Triggers

```python
# Trigger from external HTTP calls
trigger = client.triggers.create(
    name="deploy-trigger",
    type="webhook",
    webhook_secret="whsec_...",
    payload_transform={
        "title": "Deploy {{ payload.repo }}",
        "assign": "deploy-agent",
        "initial_state": {
            "repo": "{{ payload.repo }}",
            "commit": "{{ payload.commit_sha }}"
        }
    }
)

# External systems POST to:
# POST /api/v1/triggers/{trigger_id}/fire
```

## Using Triggers in Agents

### Declarative Triggers

```python
from openintent.agents import Trigger

@Trigger(
    name="daily-report",
    type="schedule",
    cron="0 9 * * *",
    dedup="skip"        # Skip if previous instance still running
)
class DailyReport:
    title = "Generate daily report"
    assign = "report-agent"

@Trigger(
    name="failure-handler",
    type="event",
    condition={"event_type": "task_failed"}
)
class FailureHandler:
    title = "Handle failed task"
    assign = "recovery-agent"

@Trigger(
    name="deploy-hook",
    type="webhook"
)
class DeployTrigger:
    title = "Deploy {{ payload.repo }}"
    assign = "deploy-agent"
```

### Responding to Trigger-Created Intents

```python
from openintent.agents import Agent, on_trigger

@Agent("report-agent")
class ReportAgent:

    @on_trigger("daily-report")
    async def handle_daily(self, intent):
        """Called when the daily-report trigger fires."""
        report = await generate_report(intent.state["report_date"])
        return {"report": report}
```

## Deduplication

Control what happens when a trigger fires while a previous intent is still active:

| Mode | Behavior |
|------|----------|
| `allow` | Create a new intent every time |
| `skip` | Skip if a previous intent is still active |
| `queue` | Queue and create when the previous one completes |

```python
trigger = client.triggers.create(
    name="hourly-check",
    type="schedule",
    cron="0 * * * *",
    dedup="skip",  # Don't pile up if check is slow
    intent_template={"title": "Hourly health check", "assign": "monitor"}
)
```

## Trigger Lineage

Every intent created by a trigger carries lineage metadata:

```python
intent = client.get_intent(intent_id)

print(f"Created by trigger: {intent.trigger_id}")
print(f"Trigger chain: {intent.trigger_chain}")  # Full ancestry
print(f"Trigger depth: {intent.trigger_depth}")   # Nesting level
```

### Cascade Depth Limit

To prevent infinite trigger loops, the protocol enforces a cascade depth limit. A trigger-created intent that fires another trigger increments the depth counter:

```
Trigger A → Intent → Trigger B → Intent → Trigger C → Intent (depth=3)
```

Default max depth: 10. Configurable per namespace.

## Namespace Governance

Triggers respect namespace-level governance policies:

```yaml
triggers:
  daily_report:
    type: schedule
    cron: "0 9 * * *"
    dedup: skip
    template:
      title: "Daily Report"
      assign: report-agent

  on_failure:
    type: event
    event_type: task_failed
    dedup: allow
    template:
      title: "Handle failure"
      assign: recovery-agent

  deploy:
    type: webhook
    dedup: queue
    template:
      title: "Deploy {{ payload.repo }}"
      assign: deploy-agent
```

## Listing and Managing Triggers

```python
# List all triggers
triggers = client.triggers.list()

for t in triggers:
    print(f"{t.name} ({t.type}): {t.status}")

# Disable a trigger
client.triggers.disable(trigger_id=trigger.id)

# Re-enable
client.triggers.enable(trigger_id=trigger.id)

# Delete
client.triggers.delete(trigger_id=trigger.id)
```

## Firing a Trigger Manually

```python
# Manually fire a trigger (useful for testing)
intent = client.triggers.fire(
    trigger_id=trigger.id,
    payload={"repo": "openintent", "commit_sha": "abc123"}
)

print(f"Created intent: {intent.id}")
```

!!! warning "Webhook security"
    Always validate webhook signatures using `webhook_secret` to prevent unauthorized trigger firing.

## Next Steps

- [Agent Lifecycle](lifecycle.md) — Death triggers and health monitoring
- [Agent Abstractions](agents.md) — `@Trigger` and `@on_trigger` decorators
- [YAML Workflows](workflows.md) — Declarative trigger configuration
