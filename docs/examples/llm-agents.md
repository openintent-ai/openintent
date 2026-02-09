---
title: LLM-Powered Agents
---

# LLM-Powered Agent Examples

Practical examples of agents and coordinators with `model=` parameter.

---

## Minimal LLM Agent

The simplest LLM-powered agent --- one decorator, one handler:

```python
from openintent import Agent, on_assignment

@Agent("helper", model="gpt-4o")
class Helper:
    @on_assignment
    async def work(self, intent):
        return await self.think(intent.description)

Helper.run()
```

---

## Agent with Memory

Store and recall information across tasks:

```python
@Agent("researcher", model="gpt-4o", memory="episodic")
class Researcher:
    @on_assignment
    async def work(self, intent):
        result = await self.think(
            "Research this topic. Use the remember tool to store "
            "key findings as you go, and recall tool to check if "
            f"you've seen related topics before. Topic: {intent.description}"
        )
        return {"research": result}
```

The LLM will autonomously call `remember` and `recall` tools, which map to RFC-0015 memory operations.

---

## Streaming Responses

### Async Generator

```python
@Agent("narrator", model="gpt-4o")
class Narrator:
    @on_assignment
    async def work(self, intent):
        full_response = []
        async for token in await self.think_stream(intent.description):
            full_response.append(token)
            print(token, end="", flush=True)
        return {"narration": "".join(full_response)}
```

### Callback Style

```python
@Agent("narrator", model="gpt-4o")
class Narrator:
    @on_assignment
    async def work(self, intent):
        result = await self.think(
            intent.description,
            stream=True,
            on_token=lambda t: print(t, end=""),
        )
        return {"narration": result}
```

---

## Human-in-the-Loop

The `clarify` tool creates an arbitration request and pauses the intent:

```python
@Agent("careful-agent", model="gpt-4o")
class CarefulAgent:
    @on_assignment
    async def work(self, intent):
        result = await self.think(
            "Review this request carefully. If the requirements are "
            "ambiguous or you need more information, use the clarify "
            f"tool to ask. Request: {intent.description}"
        )
        return {"result": result}
```

When the LLM calls `clarify`:

1. An arbitration request is created (RFC-0004)
2. The intent pauses, waiting for human input
3. `think()` returns `{"status": "awaiting_response", "question": "..."}`
4. When the human responds, the conversation resumes

---

## Multi-Provider Setup

```python
@Agent("openai-agent", model="gpt-4o")
class OpenAIAgent:
    @on_assignment
    async def work(self, intent):
        return await self.think(intent.description)

@Agent("anthropic-agent", model="claude-sonnet-4-20250514")
class AnthropicAgent:
    @on_assignment
    async def work(self, intent):
        return await self.think(intent.description)

@Agent("gemini-agent", model="gemini-1.5-pro")
class GeminiAgent:
    @on_assignment
    async def work(self, intent):
        return await self.think(intent.description)
```

Providers are auto-detected from model names. Set the matching environment variable for each provider.

---

## LLM-Powered Coordinator

Coordinators get delegation and planning tools:

```python
from openintent import Coordinator, on_assignment, on_all_complete

@Coordinator(
    "project-lead",
    model="gpt-4o",
    agents=["researcher", "writer", "reviewer"],
    memory="episodic",
)
class ProjectLead:
    @on_assignment
    async def plan(self, intent):
        return await self.think(
            "You are leading a research project. Break down the work "
            "and delegate to your team (researcher, writer, reviewer). "
            f"Project: {intent.description}"
        )

    @on_all_complete
    async def finalize(self, portfolio):
        return await self.think(
            "All agents have completed their work. Review the results "
            "and provide a final summary with quality assessment."
        )
```

The LLM can call:

- `delegate(agent_id, task_description)` --- assign work to a managed agent
- `create_plan(title, steps)` --- decompose work into sub-tasks
- `record_decision(decision_type, summary)` --- log governance decisions

---

## Agent with Custom Tools

Define tools with rich descriptions and local handlers using `ToolDef` or `@define_tool`:

```python
from openintent import Agent, ToolDef, define_tool, on_assignment

@define_tool(description="Search the web and return relevant results.", parameters={
    "type": "object",
    "properties": {
        "query": {"type": "string", "description": "Search query."},
        "max_results": {"type": "integer", "description": "Max results to return."},
    },
    "required": ["query"],
})
async def web_search(query: str, max_results: int = 5) -> dict:
    # Your search implementation
    return {"results": ["result1", "result2"]}

calculator = ToolDef(
    name="calculator",
    description="Evaluate a mathematical expression.",
    parameters={
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": "A math expression like '2 + 3 * 4'.",
            },
        },
        "required": ["expression"],
    },
    handler=lambda expression: {"result": eval(expression)},
)

@Agent("research-analyst", model="gpt-4o", memory="episodic",
       tools=[web_search, calculator])
class ResearchAnalyst:
    @on_assignment
    async def work(self, intent):
        return await self.think(
            "Research this topic and compute any numbers: "
            + intent.description
        )
```

The LLM sees full descriptions and parameter schemas for each tool, and calls them with structured arguments.

---

## Hybrid Agent (LLM + Manual Logic)

Mix `self.think()` with direct protocol operations:

```python
@Agent("analyst", model="gpt-4o", memory="episodic")
class Analyst:
    @on_assignment
    async def work(self, intent):
        analysis = await self.think(
            f"Analyze this data: {intent.description}"
        )

        await self.patch_state(intent.id, {
            "analysis_complete": True,
            "summary": analysis[:200],
        })

        recommendations = await self.think(
            "Based on your analysis, provide actionable recommendations."
        )

        return {
            "analysis": analysis,
            "recommendations": recommendations,
        }
```

Conversation history carries across `think()` calls, so the second call has context from the first.

---

## Custom System Prompt

Override the auto-generated system prompt:

```python
@Agent(
    "specialist",
    model="gpt-4o",
    system_prompt=(
        "You are a financial analyst specializing in risk assessment. "
        "Always quantify risks on a 1-10 scale. Use the remember tool "
        "to track identified risks across tasks."
    ),
    temperature=0.3,
    max_tokens=2048,
)
class RiskAnalyst:
    @on_assignment
    async def work(self, intent):
        return await self.think(intent.description)
```

---

## Error Handling

```python
@Agent("resilient", model="gpt-4o")
class ResilientAgent:
    @on_assignment
    async def work(self, intent):
        try:
            return await self.think(intent.description)
        except Exception as e:
            await self.escalate(
                intent.id,
                f"LLM processing failed: {e}"
            )
            return {"error": str(e), "escalated": True}
```
