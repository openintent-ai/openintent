# RFC-0021: Agent-to-Agent Messaging

**Status:** Proposed  
**Created:** 2026-02-13  
**Authors:** OpenIntent Contributors  
**Requires:** RFC-0001 (Intents), RFC-0003 (Leasing), RFC-0011 (Access Control), RFC-0016 (Agent Lifecycle)

---

## Abstract

This RFC introduces **Channels** and **Messages** as protocol-level primitives for direct, structured communication between agents working on the same intent. Channels provide lightweight, scoped message streams that support request/response patterns, notifications, and broadcasts — replacing the current workaround of encoding inter-agent communication as intent state patches or event log entries.

## Motivation

The protocol currently offers three mechanisms for agents to exchange information:

1. **Intent state patches (RFC-0001).** Agents write key-value pairs to shared mutable state. This creates concurrency conflicts when multiple agents patch simultaneously, pollutes the state object with transient coordination data, and provides no conversation structure (no questions, no replies, no threading).

2. **Event log entries (RFC-0001).** Events are append-only and immutable, which is excellent for audit trails but wrong for coordination. Events are broadcast to all subscribers, cannot be targeted to a specific agent, and have no reply mechanism.

3. **New intents.** Creating a child intent for a simple question ("What format is this data in?") is heavyweight — it requires full intent lifecycle management, leasing, and status tracking for what should be a sub-second exchange.

None of these support the fundamental pattern of autonomous multi-agent coordination: **Agent A asks Agent B a question and gets an answer back.**

### Concrete Scenarios

**Handoff clarification.** A coordinator delegates a research task to Agent A, who discovers the data is in an unexpected format. Agent A needs to ask the data-processing agent (Agent B) what schema version to use — without creating a new intent, without polluting the parent intent's state, and without broadcasting to every agent on the intent.

**Incremental results.** A pipeline of three agents processes data sequentially. Agent 1 completes a batch and needs to notify Agent 2 that a new batch is ready, with metadata about the batch (size, format, location). This is not a state change on the intent — it's a coordination signal between two specific agents.

**Negotiation.** Two agents are assigned overlapping scopes on the same intent. Before one acquires a lease, it asks the other: "Are you still working on section X, or can I take it?" This requires targeted messaging with a response.

## Design Principles

1. **Agent-only.** Channels are for agent-to-agent coordination. Humans interact through intents (goals), arbitration (disputes), and checkpoints (approvals). Mixing human and agent communication in the same primitive creates mismatched cadence (milliseconds vs. minutes) and semantics (structured data vs. natural language).

2. **Intent-scoped.** Channels are always attached to an intent. This provides natural access control (intent permissions govern channel access), natural lifecycle (channels close when the intent resolves), and clear context (messages are always about the work at hand).

3. **Ephemeral by default.** Messages are coordination artifacts, not permanent records. They have optional TTLs and are cleaned up when the intent completes. Important messages can be promoted to the event log via `audit: true`.

4. **Async-first, sync-convenient.** The protocol defines asynchronous message delivery. The SDK provides a synchronous `ask()` helper that sends a request and awaits the correlated response with a timeout.

5. **Typed, not free-form.** Messages carry structured payloads, not chat text. This enables programmatic processing by receiving agents without LLM interpretation overhead.

## Specification

### 1. Channel

A Channel is a named, scoped communication context attached to an intent.

#### 1.1 Channel Object

```json
{
  "id": "chan_01HXYZ",
  "intent_id": "intent_01HABC",
  "task_id": null,
  "name": "data-clarification",
  "created_by": "research-agent-01",
  "members": ["research-agent-01", "data-agent-01"],
  "member_policy": "explicit",
  "options": {
    "audit": false,
    "ttl_seconds": 3600,
    "max_messages": 1000
  },
  "status": "open",
  "created_at": "2026-02-13T10:00:00Z",
  "closed_at": null,
  "message_count": 0,
  "last_message_at": null
}
```

#### 1.2 Channel Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Unique channel identifier (server-generated). |
| `intent_id` | string | Yes | The intent this channel is scoped to. |
| `task_id` | string | No | Optional task scope. If set, the channel is further scoped to a specific task within the intent. |
| `name` | string | Yes | Human-readable channel name. Must be unique within the intent. |
| `created_by` | string | Yes | Agent ID that created the channel. |
| `members` | string[] | Yes | List of agent IDs permitted to send and receive messages on this channel. |
| `member_policy` | enum | Yes | `"explicit"` (only listed members) or `"intent"` (any agent with access to the intent). Default: `"intent"`. |
| `options.audit` | boolean | No | If `true`, all messages are copied to the intent's event log as `channel_message` events. Default: `false`. |
| `options.ttl_seconds` | integer | No | Time-to-live for the channel after the last message. `null` means the channel lives until the intent resolves. |
| `options.max_messages` | integer | No | Maximum number of messages retained. Oldest messages are evicted when exceeded. Default: `1000`. |
| `status` | enum | Yes | `"open"` or `"closed"`. |
| `created_at` | string (ISO 8601) | Yes | Channel creation timestamp. |
| `closed_at` | string (ISO 8601) | No | Timestamp when the channel was closed. |
| `message_count` | integer | Yes | Total number of messages sent on this channel. |
| `last_message_at` | string (ISO 8601) | No | Timestamp of the most recent message. |

#### 1.3 Channel Lifecycle

```
created (open) → closed
                → closed (intent resolved — automatic)
                → closed (TTL expired — automatic)
```

Channels are lightweight and disposable. An agent creates a channel for a specific coordination need, uses it, and the channel closes when the need is met or the intent resolves.

#### 1.4 Implicit Channel Creation

Channels can be created implicitly by sending a message to a channel name that does not yet exist on the intent. The server creates the channel with `member_policy: "intent"` (open to all agents on the intent) and delivers the message. This reduces ceremony for common cases.

Explicit creation via `POST /channels` is available when agents need to set `member_policy: "explicit"`, configure `audit: true`, or set custom TTL/retention.

### 2. Message

A Message is a typed, structured communication between agents on a channel.

#### 2.1 Message Object

```json
{
  "id": "msg_01HXYZ",
  "channel_id": "chan_01HABC",
  "sender": "research-agent-01",
  "to": "data-agent-01",
  "message_type": "request",
  "correlation_id": null,
  "payload": {
    "question": "What schema version does the Q1 dataset use?",
    "context": { "task_id": "task_01HGHI", "dataset": "q1_financials" }
  },
  "metadata": {},
  "status": "delivered",
  "created_at": "2026-02-13T10:00:00Z",
  "expires_at": "2026-02-13T10:05:00Z",
  "read_at": null
}
```

#### 2.2 Message Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Unique message identifier (server-generated). |
| `channel_id` | string | Yes | The channel this message belongs to. |
| `sender` | string | Yes | Agent ID of the message sender. |
| `to` | string | No | Target agent ID, `"role:<role_id>"` for role-based addressing, or `"*"` for broadcast. `null` means broadcast to all channel members. |
| `message_type` | enum | Yes | One of: `"request"`, `"response"`, `"notify"`, `"broadcast"`. |
| `correlation_id` | string | No | For `"response"` messages: the `id` of the originating `"request"` message. Creates a request/response pair. |
| `payload` | object | Yes | Structured message content. Schema is application-defined. |
| `metadata` | object | No | Implementation-specific data (priority hints, routing tags, trace context). |
| `status` | enum | Yes | `"pending"`, `"delivered"`, `"read"`, `"expired"`. |
| `created_at` | string (ISO 8601) | Yes | Message creation timestamp. |
| `expires_at` | string (ISO 8601) | No | Message expiration. Expired messages transition to `"expired"` status and are not delivered. |
| `read_at` | string (ISO 8601) | No | Timestamp when the target agent acknowledged the message. |

#### 2.3 Message Types

| Type | Semantics | `correlation_id` | `to` |
|------|-----------|-------------------|------|
| `request` | Sender expects a response. Creates a pending request that the target should reply to. | Not set (this message *is* the request — its `id` becomes the correlation target). | Required (specific agent or role). |
| `response` | Reply to a previous request. Linked by `correlation_id`. | Required (must reference a `request` message `id`). | Auto-set to the original request's `sender`. |
| `notify` | Fire-and-forget information. No response expected. | Not set. | Optional (specific agent, role, or broadcast). |
| `broadcast` | Information sent to all channel members. | Not set. | Auto-set to `"*"`. |

#### 2.4 Message Delivery

Messages are delivered asynchronously. The server persists the message and makes it available for retrieval. Delivery mechanisms:

1. **Pull (base).** Agents poll `GET /channels/{id}/messages?since={cursor}` to retrieve new messages. The `since` parameter is an opaque cursor (message ID or timestamp) for efficient pagination.

2. **Push (SSE).** Agents subscribed to the intent via RFC-0006 receive `channel_message` events in their SSE stream. The event contains the full message object, enabling real-time processing without polling.

3. **Push (webhook).** If the target agent has a registered `endpoint` (RFC-0016), the server MAY deliver the message via HTTP POST to the agent's endpoint. This is implementation-optional.

#### 2.5 Message Status Transitions

```
pending → delivered (server confirmed persistence)
        → expired (expires_at reached before delivery)

delivered → read (target agent acknowledged)
          → expired (expires_at reached after delivery)
```

### 3. Request/Response Pattern

The request/response pattern is the primary coordination mechanism. It works as follows:

1. Agent A sends a `request` message to Agent B on a channel.
2. The server persists the message with `status: "pending"`, then `"delivered"`.
3. Agent B receives the message (via pull or push).
4. Agent B sends a `response` message with `correlation_id` set to the request's `id`.
5. Agent A receives the response (via pull or push), matched by `correlation_id`.

#### 3.1 Timeout Semantics

Requests have an optional `expires_at`. If no response arrives before expiration:

- The request message transitions to `"expired"` status.
- The requesting agent receives no response (the SDK `ask()` helper raises a `MessageTimeoutError`).
- No automatic retry — the requesting agent decides whether to retry, escalate, or proceed without the answer.

#### 3.2 Multiple Responses

A request may receive multiple responses (e.g., when sent to a role and multiple agents with that role respond). The protocol supports this — all responses share the same `correlation_id`. The SDK `ask()` helper returns the first response by default; `ask_all()` collects responses within the timeout window.

### 4. Addressing

#### 4.1 Direct Addressing

```json
{ "to": "data-agent-01" }
```

The message is delivered only to the specified agent. If the agent is not a member of the channel (and `member_policy` is `"explicit"`), the server returns `403 Forbidden`.

#### 4.2 Role-Based Addressing

```json
{ "to": "role:billing-processor" }
```

The message is delivered to any agent registered with `role_id: "billing-processor"` (RFC-0016) that is a member of the channel (or has access to the intent, if `member_policy` is `"intent"`). If multiple agents match, all receive the message. This is useful for addressing capabilities rather than specific instances.

#### 4.3 Broadcast Addressing

```json
{ "to": "*" }
```

All channel members receive the message. Used for `broadcast` message type or `notify` without a specific target.

### 5. Access Control

Channel access follows RFC-0011 intent permissions with optional further restriction:

1. **Intent-level access is required.** An agent must have access to the intent to interact with any of its channels. Agents without intent access cannot see, join, or message channels.

2. **Channel-level restriction is optional.** With `member_policy: "explicit"`, only agents listed in `members` can send and receive messages. With `member_policy: "intent"`, any agent with intent access can participate.

3. **Creator manages membership.** The agent that created the channel can add or remove members via `PATCH /channels/{id}`. The intent's coordinator (if any) can also manage membership.

4. **No cross-intent messaging.** An agent on Intent A cannot send a message to a channel on Intent B, even if the agent has access to both intents. Cross-intent coordination uses intent graphs (RFC-0002) and portfolios (RFC-0004).

### 6. Audit Integration

When `options.audit` is `true` on a channel, every message is also recorded as an intent event:

```json
{
  "event_type": "channel_message",
  "actor": "research-agent-01",
  "payload": {
    "channel_id": "chan_01HABC",
    "channel_name": "data-clarification",
    "message_id": "msg_01HXYZ",
    "message_type": "request",
    "to": "data-agent-01",
    "payload": { "question": "What schema version?" }
  }
}
```

This integrates with the existing event log, hash chains (RFC-0019), and distributed tracing (RFC-0020). The `trace_id` from the message's `metadata` (if present) is propagated to the event.

Non-audit channels do not emit events. This keeps the event log clean for coordination-heavy workflows where dozens of messages may be exchanged per minute.

### 7. Lifecycle Integration

#### 7.1 Intent Resolution

When an intent transitions to a terminal status (`completed`, `abandoned`), all open channels on that intent are automatically closed. Pending messages transition to `"expired"`. This prevents orphaned channels.

#### 7.2 Agent Deregistration

When an agent is deregistered (RFC-0016), it is removed from all channel member lists. Pending `request` messages addressed to the agent transition to `"expired"`, and a `notify` message is sent to the channel indicating the agent has departed.

#### 7.3 Task Completion

If a channel is scoped to a task (`task_id` is set), the channel closes when the task completes. Task-scoped channels are automatically cleaned up, keeping the coordination context tight.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/v1/intents/{intent_id}/channels` | Create a channel |
| `GET` | `/v1/intents/{intent_id}/channels` | List channels on an intent |
| `GET` | `/v1/channels/{channel_id}` | Get channel details |
| `PATCH` | `/v1/channels/{channel_id}` | Update channel (members, options, status) |
| `DELETE` | `/v1/channels/{channel_id}` | Close and delete a channel |
| `POST` | `/v1/channels/{channel_id}/messages` | Send a message |
| `GET` | `/v1/channels/{channel_id}/messages` | List messages (with `?since=` cursor, `?to=` filter) |
| `GET` | `/v1/channels/{channel_id}/messages/{message_id}` | Get a specific message |
| `POST` | `/v1/channels/{channel_id}/messages/{message_id}/reply` | Send a response (auto-sets `correlation_id` and `to`) |
| `PATCH` | `/v1/channels/{channel_id}/messages/{message_id}` | Update message status (mark as `read`) |

### Request/Response Examples

#### Create Channel

```http
POST /api/v1/intents/intent_01HABC/channels
Content-Type: application/json
X-API-Key: dev-key-001

{
  "name": "data-clarification",
  "members": ["research-agent-01", "data-agent-01"],
  "member_policy": "explicit",
  "options": {
    "audit": true,
    "ttl_seconds": 3600
  }
}
```

Response:

```json
{
  "id": "chan_01HXYZ",
  "intent_id": "intent_01HABC",
  "name": "data-clarification",
  "created_by": "research-agent-01",
  "members": ["research-agent-01", "data-agent-01"],
  "member_policy": "explicit",
  "options": { "audit": true, "ttl_seconds": 3600, "max_messages": 1000 },
  "status": "open",
  "created_at": "2026-02-13T10:00:00Z",
  "message_count": 0
}
```

#### Send Request Message

```http
POST /api/v1/channels/chan_01HXYZ/messages
Content-Type: application/json
X-API-Key: dev-key-001

{
  "sender": "research-agent-01",
  "to": "data-agent-01",
  "message_type": "request",
  "payload": {
    "question": "What schema version does the Q1 dataset use?"
  },
  "expires_at": "2026-02-13T10:05:00Z"
}
```

Response:

```json
{
  "id": "msg_01HXYZ",
  "channel_id": "chan_01HXYZ",
  "sender": "research-agent-01",
  "to": "data-agent-01",
  "message_type": "request",
  "correlation_id": null,
  "payload": { "question": "What schema version does the Q1 dataset use?" },
  "status": "delivered",
  "created_at": "2026-02-13T10:00:00Z",
  "expires_at": "2026-02-13T10:05:00Z"
}
```

#### Reply to Request

```http
POST /api/v1/channels/chan_01HXYZ/messages/msg_01HXYZ/reply
Content-Type: application/json
X-API-Key: dev-key-001

{
  "sender": "data-agent-01",
  "payload": {
    "answer": "v2.3",
    "confidence": 0.95,
    "schema_url": "https://schemas.example.com/financials/v2.3"
  }
}
```

Response:

```json
{
  "id": "msg_01HABC",
  "channel_id": "chan_01HXYZ",
  "sender": "data-agent-01",
  "to": "research-agent-01",
  "message_type": "response",
  "correlation_id": "msg_01HXYZ",
  "payload": {
    "answer": "v2.3",
    "confidence": 0.95,
    "schema_url": "https://schemas.example.com/financials/v2.3"
  },
  "status": "delivered",
  "created_at": "2026-02-13T10:00:05Z"
}
```

#### List Messages (with cursor)

```http
GET /api/v1/channels/chan_01HXYZ/messages?since=msg_01HXYZ&to=research-agent-01
X-API-Key: dev-key-001
```

Returns messages after the cursor, optionally filtered by recipient.

## SDK Integration

### Client Methods

Both `OpenIntentClient` (sync) and `AsyncOpenIntentClient` (async) expose:

```python
# Channel management
client.create_channel(intent_id, name, members=None, member_policy="intent", options=None)
client.list_channels(intent_id)
client.get_channel(channel_id)
client.close_channel(channel_id)

# Messaging
client.send_message(channel_id, sender, to=None, message_type="notify", payload={}, expires_at=None)
client.reply_to(channel_id, message_id, sender, payload={})
client.list_messages(channel_id, since=None, to=None)
client.get_message(channel_id, message_id)
client.mark_read(channel_id, message_id)

# Convenience
client.ask(channel_id, sender, to, payload, timeout=30)  # Send request + await response
client.ask_all(channel_id, sender, to, payload, timeout=30)  # Collect multiple responses
```

### Agent Decorators

```python
from openintent.agents import Agent, on_message, on_assignment

@Agent("data-agent-01")
class DataAgent:
    @on_assignment
    async def handle(self, intent):
        # Normal work...
        pass

    @on_message(channel="data-clarification")
    async def handle_clarification(self, message):
        """Called when a message arrives on the named channel."""
        if message.message_type == "request":
            # Return value is auto-sent as a response
            return {"answer": "v2.3", "confidence": 0.95}

    @on_message()  # No channel filter — receives all messages
    async def handle_any(self, message):
        """Called for messages on any channel."""
        logger.info(f"Got message from {message.sender}: {message.payload}")
```

### Channel Proxy on Agents

```python
@Agent("research-agent-01")
class ResearchAgent:
    @on_assignment
    async def handle(self, intent):
        # Open/get a channel (created implicitly if it doesn't exist)
        channel = await self.channels.open("data-clarification", intent_id=intent.id)

        # Ask a question and wait for the answer
        response = await channel.ask("data-agent-01", {
            "question": "What schema version?"
        }, timeout=30)

        schema_version = response.payload["answer"]

        # Notify everyone
        await channel.broadcast({"status": "starting analysis", "schema": schema_version})

        # Fire-and-forget
        await channel.notify("logger-agent", {"phase": "research", "started": True})
```

## YAML Workflow Integration

```yaml
version: "1.0"
intent:
  title: "Research Q1 Financials"

channels:
  data-clarification:
    members: [research-agent, data-agent]
    member_policy: explicit
    audit: true

  progress:
    member_policy: intent
    audit: false

agents:
  research-agent:
    on_message:
      - channel: progress
        handler: log_progress

  data-agent:
    on_message:
      - channel: data-clarification
        handler: answer_questions
```

## Relationship to Other RFCs

| RFC | Relationship |
|-----|-------------|
| RFC-0001 (Intents) | Channels are scoped to intents. Channel lifecycle follows intent lifecycle. |
| RFC-0002 (Intent Graphs) | Cross-intent communication uses intent graphs, not channels. Channels are intra-intent only. |
| RFC-0003 (Leasing) | Channel membership does not grant lease rights. An agent can message on a channel without holding a lease. |
| RFC-0006 (Subscriptions) | SSE subscriptions deliver `channel_message` events for real-time push. |
| RFC-0011 (Access Control) | Intent access is required for channel access. Channel `member_policy` adds optional further restriction. |
| RFC-0012 (Task Decomposition) | Channels can be scoped to tasks via `task_id`. Task completion auto-closes task-scoped channels. |
| RFC-0016 (Agent Lifecycle) | Agent deregistration triggers channel cleanup. Role-based addressing uses `role_id` from agent records. |
| RFC-0018 (Cryptographic Identity) | Agents with cryptographic identity can sign messages. The `metadata` field can carry a `proof` object following the EventProof format. |
| RFC-0019 (Verifiable Logs) | Audit-enabled channels emit events that participate in hash chains. |
| RFC-0020 (Distributed Tracing) | Message `metadata` can carry `trace_id` and `parent_event_id` for cross-agent trace propagation. |

## Security Considerations

1. **No credential exposure.** Messages carry structured data, not credentials. Tool grants (RFC-0014) are never communicated via channels.

2. **Intent-scoped isolation.** Agents cannot send messages to channels on intents they don't have access to. This is enforced at the API level.

3. **Member restriction.** Explicit member policies prevent eavesdropping by agents that have intent access but should not participate in specific conversations.

4. **Message expiration.** TTLs prevent stale messages from accumulating. Expired messages are not delivered.

5. **Audit trail.** Channels with `audit: true` produce immutable event log entries, integrating with hash chains and cryptographic signatures for non-repudiation.

6. **No arbitrary code execution.** Message payloads are structured data (JSON objects). The protocol does not define executable content in messages.

## Open Questions

1. **Message ordering guarantees.** Should the protocol guarantee strict ordering within a channel, or is best-effort ordering acceptable? Strict ordering simplifies agent logic but may limit throughput.

2. **Channel discovery.** Should agents be able to discover channels they're not members of (read channel names and metadata without seeing messages)? This could help with dynamic team formation but raises privacy concerns.

3. **Message persistence after intent resolution.** Should messages be retained after the intent resolves (for post-mortem analysis), or cleaned up immediately? The `audit: true` path preserves important messages in the event log regardless.

4. **Binary payloads.** Should messages support binary attachments (e.g., intermediate data files), or should agents use RFC-0005 (Attachments) for large data and reference attachment IDs in messages?

## References

- RFC-0001: Intent Object Model
- RFC-0003: Lease-Based Coordination
- RFC-0006: Real-time Subscriptions
- RFC-0011: Access-Aware Coordination
- RFC-0012: Task Decomposition & Planning
- RFC-0016: Agent Lifecycle & Health
- RFC-0018: Cryptographic Agent Identity
- RFC-0019: Verifiable Event Logs
- RFC-0020: Distributed Tracing
