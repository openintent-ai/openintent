# Decorator-First Agents

Build agents with zero boilerplate using decorators.

## Basic Agent

```python
from openintent.agents import Agent, on_assignment, on_complete

@Agent("summarizer", auto_heartbeat=True)
class SummarizerAgent:

    @on_assignment
    async def handle(self, intent):
        text = intent.state.get("text", "")
        summary = text[:200] + "..."
        return {"summary": summary, "status": "summarized"}

    @on_complete
    async def done(self, intent):
        print(f"Finished: {intent.title}")

SummarizerAgent.run()
```

## Agent with Memory

```python
from openintent.agents import Agent, on_assignment, Memory

@Agent("learner", memory="episodic", auto_heartbeat=True)
class LearningAgent:

    @on_assignment
    async def handle(self, intent):
        # Store findings in episodic memory
        await self.memory.store(
            key="finding",
            value={"topic": intent.title, "result": "done"},
            tags=["research"]
        )

        # Recall past findings
        past = await self.memory.query(tags=["research"], limit=10)
        return {"past_findings": len(past), "status": "learned"}
```

## Agent with Tools

```python
from openintent.agents import Agent, on_assignment

@Agent("web-researcher", tools=["web_search", "summarize"])
class WebResearchAgent:

    @on_assignment
    async def handle(self, intent):
        query = intent.state.get("query", intent.title)

        # Tools are resolved from credential vault (RFC-0014)
        results = await self.tools.invoke("web_search", query=query)
        summary = await self.tools.invoke("summarize", text=results)

        return {"summary": summary, "sources": len(results)}
```

## Agent Lifecycle Hooks

```python
from openintent.agents import (
    Agent, on_assignment, on_complete,
    on_state_change, on_drain, on_event
)

@Agent("monitored-agent", auto_heartbeat=True)
class MonitoredAgent:

    @on_assignment
    async def handle(self, intent):
        return {"status": "processing"}

    @on_state_change
    async def state_changed(self, intent, old_state, new_state):
        print(f"State: {old_state} -> {new_state}")

    @on_drain
    async def draining(self):
        print("Agent draining, finishing current work...")

    @on_event("llm_request_completed")
    async def llm_done(self, event):
        tokens = event.payload.get("total_tokens", 0)
        print(f"LLM used {tokens} tokens")

    @on_complete
    async def finished(self, intent):
        print(f"Done: {intent.title}")
```

## Worker (Minimal Agent)

For single-handler agents that don't need a full class:

```python
from openintent.agents import Worker

async def process(intent):
    data = intent.state.get("data", [])
    return {"processed": len(data), "status": "done"}

worker = Worker("processor", handler=process)
worker.run()
```

## YAML Workflow

```yaml
openintent: "1.0"
info:
  name: "Content Pipeline"

workflow:
  draft:
    title: "Draft Article"
    assign: summarizer
    constraints: ["Keep under 500 words"]

  review:
    title: "Review Draft"
    assign: monitored-agent
    depends_on: [draft]

  publish:
    title: "Publish Article"
    assign: processor
    depends_on: [review]
```

```python
from openintent.workflow import load_workflow

workflow = load_workflow("content_pipeline.yaml")
workflow.run()
```
