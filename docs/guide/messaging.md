---
title: Agent-to-Agent Messaging
---

# Agent-to-Agent Messaging

Channels let agents talk to each other directly within an intent scope. Instead of polluting shared state with coordination data or spinning up new intents for simple questions, agents open a channel and exchange structured messages. Three patterns cover the common cases: **ask/reply**, **notify**, and **broadcast**. Defined in [RFC-0021](../rfcs/0021-agent-to-agent-messaging.md).

---

## Quick Start

Two agents working a data pipeline. The researcher needs to ask the data agent which schema version to use — a sub-second exchange that doesn't belong in intent state.

### 1. Declare the Channel

```yaml
openintent: "1.0"
info:
  name: "Data Pipeline"

channels:
  data-sync:
    members: [researcher, data-agent]
    audit: true

workflow:
  research:
    assign: researcher
  process:
    assign: data-agent
    depends_on: [research]
```

### 2. Handle Incoming Messages

The data agent listens on the `data-sync` channel. When a `request` arrives, it returns a dict — the framework sends it back as a correlated `response` automatically.

```python
from openintent.agents import Agent, on_assignment, on_message

@Agent("data-agent")
class DataAgent:
    @on_assignment
    async def handle(self, intent):
        return {"status": "ready"}

    @on_message(channel="data-sync")
    async def on_question(self, message):
        if message.message_type == "request":
            return {"answer": "v2.3", "confidence": 0.95}
```

### 3. Ask a Question

The researcher opens the channel, asks a question, and uses the answer — all within a single handler.

```python
from openintent.agents import Agent, on_assignment

@Agent("researcher")
class ResearchAgent:
    @on_assignment
    async def handle(self, intent):
        ch = await self.channels.open("data-sync", intent_id=intent.id)
        response = await ch.ask("data-agent", {"question": "What schema?"}, timeout=30)
        schema = response.payload["answer"]
        return {"findings": f"Using schema {schema}"}
```

!!! tip "Zero ceremony"
    The channel was declared in YAML, so both agents can use it immediately. No explicit creation step, no connection handshake — just `open` and `ask`.

---

## Channels

A **Channel** is a named, scoped communication context attached to an intent. Think of it as a lightweight topic that two or more agents can post messages to.

**Key properties:**

- **Declarative or programmatic.** Define channels in YAML (recommended) or create them at runtime via `self.channels.open()`.
- **Intent-scoped.** A channel's lifecycle is tied to its parent intent. When the intent resolves, all its channels close automatically.
- **Membership policies.** Two options:
    - `explicit` — only agents listed in `members` can participate.
    - `intent` — any agent with access to the intent can join. This is the default.
- **Optional settings:** `audit` (copy messages to the event log), `ttl_seconds` (auto-close after inactivity), `max_messages` (evict oldest when full).

!!! info "Implicit creation"
    If an agent sends a message to a channel name that doesn't exist yet, the server creates it automatically with `member_policy: "intent"`. Explicit creation via YAML or the API is only needed when you want restricted membership, audit logging, or custom TTLs.

---

## Message Types

Every message carries a `message_type` that determines its semantics:

| Type | Description | Expects reply? |
|------|-------------|----------------|
| `request` | Ask a question or request data from a specific agent. | Yes |
| `response` | Reply to a previous `request`, linked by `correlation_id`. | No |
| `notify` | Fire-and-forget information to a specific agent. | No |
| `broadcast` | Information sent to all channel members. | No |

---

## Patterns

### Ask / Reply

The primary coordination pattern. `channel.ask()` sends a `request` message and awaits the correlated `response` — one call, one answer.

**Sending side:**

```python
response = await ch.ask(
    "data-agent",
    {"question": "What format is the Q1 dataset?"},
    timeout=30
)
print(response.payload["answer"])
```

**Receiving side:**

```python
@on_message(channel="data-sync")
async def on_question(self, message):
    if message.message_type == "request":
        return {"answer": "v2.3", "confidence": 0.95}
```

Returning a dict from an `@on_message` handler automatically sends it as a `response` with the correct `correlation_id`. No manual reply wiring needed.

!!! tip "Timeouts"
    Always set a `timeout` on `ask()`. If no response arrives in time, the SDK raises `MessageTimeoutError` so your agent can decide to retry, escalate, or proceed without the answer.

### Notify

Fire-and-forget. Send a message to a specific agent with no response expected.

```python
await ch.notify("logger-agent", {"event": "phase_complete", "phase": 1})
```

### Broadcast

Send a message to every member of the channel.

```python
await ch.broadcast({"status": "pipeline_ready", "batch_size": 500})
```

---

## Declarative Configuration

The `channels:` block in a workflow YAML defines channels with full configuration:

```yaml
channels:
  data-sync:
    members: [agent-a, agent-b]
    member_policy: explicit
    audit: true
    ttl_seconds: 3600
    max_messages: 500

  progress:
    member_policy: intent
    audit: false
```

You can also wire per-agent message handlers declaratively:

```yaml
agents:
  data-agent:
    on_message:
      - channel: data-sync
        handler: answer_questions

  logger-agent:
    on_message:
      - channel: progress
        handler: log_updates
```

This is equivalent to decorating methods with `@on_message(channel="data-sync")` in Python — choose whichever style fits your project.

---

## Channel Proxy

Every `@Agent` instance has a `self.channels` proxy for working with channels at runtime.

### Opening a Channel

```python
ch = await self.channels.open("data-sync", intent_id=intent.id)
```

If the channel exists, it returns a handle to it. If not, the server creates it with `member_policy: "intent"`.

### ChannelHandle Methods

The handle returned by `open()` provides four methods:

| Method | Description |
|--------|-------------|
| `await ch.ask(to, payload, timeout=30)` | Send a `request` and await the correlated `response`. |
| `await ch.notify(to, payload)` | Send a fire-and-forget `notify` message. |
| `await ch.broadcast(payload)` | Send a `broadcast` to all channel members. |
| `await ch.send(to, message_type, payload)` | Low-level send with explicit type. |

```python
@Agent("coordinator")
class CoordinatorAgent:
    @on_assignment
    async def handle(self, intent):
        ch = await self.channels.open("team", intent_id=intent.id)

        await ch.broadcast({"status": "starting", "phase": "init"})

        resp = await ch.ask("validator", {"data": intent.state}, timeout=15)

        if resp.payload.get("valid"):
            await ch.notify("worker", {"action": "begin_processing"})

        return {"status": "coordinated"}
```

---

## Real-Time Streaming

Channels support real-time delivery via Server-Sent Events:

```
GET /v1/subscribe/channels/{channel_id}
```

When subscribed, the agent receives messages the instant they're posted — no polling needed.

In practice, you rarely interact with this endpoint directly. The `@on_message` decorator handles SSE subscription automatically: when your agent starts, the framework subscribes to the relevant channels and routes incoming messages to your decorated handlers.

---

## Access Control

Channel access follows a simple layered model:

1. **Intent permissions are required.** An agent must have access to the parent intent before it can interact with any channel on that intent.
2. **Member policy adds restriction.** With `member_policy: "explicit"`, only listed members can send and receive. With `"intent"`, any agent on the intent can participate.
3. **No cross-intent messaging.** An agent on Intent A cannot message a channel on Intent B, even if the agent has access to both. Cross-intent coordination uses [intent graphs](../rfcs/0002-intent-graphs.md) and [portfolios](portfolios.md).

!!! info "Creator manages membership"
    The agent that created a channel (or the intent's coordinator) can add or remove members at any time via the API.

---

## Best Practices

**Use channels for coordination, not data transfer.** Channels are designed for structured signals — questions, status updates, handoff notifications. Keep payloads small. If you need to pass large datasets between agents, use intent state or attachments.

**Prefer declarative YAML channels.** Defining channels in your workflow YAML makes the communication topology visible and reviewable. Reserve programmatic creation for truly dynamic scenarios.

**Set timeouts on `ask()` calls.** An unanswered request should not block your agent indefinitely. Set a reasonable timeout and handle `MessageTimeoutError` gracefully.

**Enable `audit: true` for important channels.** Audit channels copy every message to the intent's event log, integrating with hash chains and distributed tracing. Use this for channels where you need a permanent record of coordination decisions.

**Use role-based addressing for flexible routing.** Instead of hardcoding agent IDs, address messages to roles:

```python
response = await ch.ask("role:processor", {"task": "validate"}, timeout=30)
```

This lets you swap agent implementations without changing coordination logic.

---

## Next Steps

<div class="oi-features" style="margin-top: 1em;">
  <div class="oi-feature">
    <div class="oi-feature__title">Agent Abstractions</div>
    <p class="oi-feature__desc">Build agents with lifecycle hooks, memory, and tools.</p>
    <a href="../agents/" class="oi-feature__link">Build agents</a>
  </div>
  <div class="oi-feature">
    <div class="oi-feature__title">Subscriptions & Streaming</div>
    <p class="oi-feature__desc">Real-time event delivery via SSE for intents, agents, and portfolios.</p>
    <a href="../subscriptions/" class="oi-feature__link">Stream events</a>
  </div>
  <div class="oi-feature">
    <div class="oi-feature__title">RFC-0021</div>
    <p class="oi-feature__desc">Full specification for channels, messages, and endpoints.</p>
    <a href="../../rfcs/0021-agent-to-agent-messaging/" class="oi-feature__link">Read the RFC</a>
  </div>
</div>
