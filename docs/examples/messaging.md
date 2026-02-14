# Agent-to-Agent Messaging

Build agents that communicate directly through channels.

## Ask / Reply (Two Agents)

A data agent answers questions, and a researcher asks them:

```python
from openintent.agents import Agent, on_assignment, on_message

@Agent("data-agent")
class DataAgent:
    @on_assignment
    async def handle(self, intent):
        return {"status": "ready"}

    @on_message(channel="questions")
    async def answer(self, message):
        if message.message_type == "request":
            return {"answer": "v2.3", "confidence": 0.95}

DataAgent.run()
```

The researcher opens a channel and asks questions:

```python
@Agent("researcher")
class ResearchAgent:
    @on_assignment
    async def handle(self, intent):
        ch = await self.channels.open("questions", intent_id=intent.id)
        
        response = await ch.ask("data-agent", {
            "dataset": "q1_financials"
        }, timeout=30)
        
        schema = response.payload["answer"]
        return {"findings": f"Dataset uses schema {schema}"}

ResearchAgent.run()
```

## Broadcast Notifications

An agent broadcasts progress to all channel members:

```python
@Agent("pipeline-runner")
class PipelineAgent:
    @on_assignment
    async def handle(self, intent):
        ch = await self.channels.open("progress", intent_id=intent.id)
        
        for batch_num in range(1, 4):
            await process_batch(batch_num)
            await ch.broadcast({"batch": batch_num, "status": "complete"})
        
        return {"total_batches": 3}
```

## Catch-All Message Handler

Receive all messages on any channel:

```python
@Agent("logger")
class LoggerAgent:
    @on_message()
    async def log_all(self, message):
        print(f"[{message.sender}] {message.message_type}: {message.payload}")
```

## YAML Workflow with Channels

Define channels and their members declaratively:

```yaml
openintent: "1.0"
info:
  name: "Research Pipeline"

channels:
  questions:
    members: [researcher, data-agent]
    member_policy: explicit
    audit: true
  progress:
    member_policy: intent

workflow:
  research:
    assign: researcher
  process:
    assign: data-agent
    depends_on: [research]
```

## Client-Level Messaging

Use the client directly to create channels and send messages:

```python
from openintent import OpenIntentClient

client = OpenIntentClient(base_url="http://localhost:8000", api_key="dev-key")

channel = client.create_channel(
    intent_id="intent_01",
    name="coordination",
    members=["agent-a", "agent-b"]
)

response = client.ask(
    channel_id=channel["id"],
    sender="agent-a",
    to="agent-b",
    payload={"question": "Ready?"},
    timeout=15
)
```

## Message Types

Channels support four message types:

- **request**: Expect a response (sender waits for an answer)
- **response**: Reply to a request (linked by correlation_id)
- **notify**: Fire-and-forget (no response expected)
- **broadcast**: Send to all channel members

Choose the message type based on whether you need a synchronous answer or just want to send information.
