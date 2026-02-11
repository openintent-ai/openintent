# Agents API Reference

High-level agent abstractions for building OpenIntent agents.

!!! tip "Preferred pattern: LLM-Powered Agents"
    Adding `model=` to `@Agent` or `@Coordinator` is the recommended way to build agents. See the [LLM-Powered Agents guide](../guide/llm-agents.md) for details.

## Agent Decorator

::: openintent.agents.Agent
    options:
      show_source: false

### LLM Instance Properties (requires `model=`)

When `model=` is set on `@Agent`, the class gains these methods:

| Method | Description |
|--------|-------------|
| `self.think(prompt)` | Agentic tool loop — sends prompt to LLM, executes tool calls, returns final text |
| `self.think_stream(prompt)` | Same agentic loop but yields tokens as they arrive for real-time streaming |
| `self.reset_conversation()` | Clear the LLM conversation history to start fresh |

## Worker

::: openintent.agents.Worker
    options:
      show_source: false

## Coordinator

::: openintent.agents.Coordinator
    options:
      show_source: false

### Built-in Coordinator Guardrails

The `guardrails=` parameter on `@Coordinator` accepts these built-in policies:

| Policy | Description |
|--------|-------------|
| `"require_approval"` | Logs decision records before assignment |
| `"budget_limit"` | Rejects intents exceeding cost constraints |
| `"agent_allowlist"` | Rejects delegation to agents outside the managed list |

## Protocol Decorators

### Plan (RFC-0012)

::: openintent.agents.Plan
    options:
      show_source: false

### Vault (RFC-0014)

::: openintent.agents.Vault
    options:
      show_source: false

### Memory (RFC-0015)

::: openintent.agents.Memory
    options:
      show_source: false

### Trigger (RFC-0017)

::: openintent.agents.Trigger
    options:
      show_source: false

## Lifecycle Decorators

### on_assignment

::: openintent.agents.on_assignment
    options:
      show_source: false

### on_complete

::: openintent.agents.on_complete
    options:
      show_source: false

### on_state_change

::: openintent.agents.on_state_change
    options:
      show_source: false

### on_event

::: openintent.agents.on_event
    options:
      show_source: false

### on_lease_available

::: openintent.agents.on_lease_available
    options:
      show_source: false

### on_all_complete

::: openintent.agents.on_all_complete
    options:
      show_source: false

### on_access_requested (RFC-0011)

::: openintent.agents.on_access_requested
    options:
      show_source: false

### on_task (RFC-0012)

::: openintent.agents.on_task
    options:
      show_source: false

### on_trigger (RFC-0017)

::: openintent.agents.on_trigger
    options:
      show_source: false

### on_drain (RFC-0016)

::: openintent.agents.on_drain
    options:
      show_source: false

### on_handoff (RFC-0013)

Fires when an agent receives work delegated from another agent. The handler receives the intent and the delegating agent's ID.

::: openintent.agents.on_handoff
    options:
      show_source: false

### on_retry (RFC-0010)

Fires when an intent is reassigned after a previous failure. The handler receives the intent, attempt number, and last error.

::: openintent.agents.on_retry
    options:
      show_source: false

## Guardrail Decorators

### input_guardrail

::: openintent.agents.input_guardrail
    options:
      show_source: false

### output_guardrail

::: openintent.agents.output_guardrail
    options:
      show_source: false

### GuardrailError

::: openintent.agents.GuardrailError
    options:
      show_source: false

## Coordinator Lifecycle Decorators

### on_conflict

::: openintent.agents.on_conflict
    options:
      show_source: false

### on_escalation

::: openintent.agents.on_escalation
    options:
      show_source: false

### on_quorum

::: openintent.agents.on_quorum
    options:
      show_source: false

## Tool Definitions

### ToolDef

`ToolDef(name, description, parameters, handler)` — rich tool definition for LLM function calling with local execution. Pass `ToolDef` objects in the `tools=` parameter on `@Agent` or `@Coordinator`.

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Tool name (used in function calling) |
| `description` | `str` | What the tool does (shown to the LLM) |
| `parameters` | `dict` | JSON Schema for tool arguments |
| `handler` | `callable` | Local function called when the LLM invokes the tool |

### @define_tool

`@define_tool(description=, parameters=)` — decorator that turns a function into a `ToolDef` object.

```python
from openintent import define_tool

@define_tool(description="Search the web.", parameters={
    "type": "object",
    "properties": {"query": {"type": "string"}},
    "required": ["query"],
})
async def web_search(query: str) -> dict:
    return {"results": await fetch_results(query)}
```

!!! note "Backwards compatibility"
    `Tool` = `ToolDef`, `@tool` = `@define_tool`. The old names are kept as aliases.

### Tool Execution Priority

1. **Protocol tools** (remember, recall, clarify, escalate, update_status) — always first
2. **Local handlers** (`ToolDef` objects) — executed in-process
3. **Remote protocol grants** (string names via RFC-0014) — resolved via server proxy

## Proxy Classes

### _ToolsProxy

The `_ToolsProxy` class provides `self.tools` on agents. For string tool names (RFC-0014 grants), it delegates to `client.invoke_tool()` for server-side invocation. For `ToolDef` objects, it executes the local handler directly.

```python
# Server-side invocation (string tool name → server proxy)
result = await self.tools.invoke("web_search", {"query": "..."})

# Local invocation (ToolDef handler)
result = await self.tools.invoke(my_tooldef, {"param": "value"})
```

### _MemoryProxy

`self.memory` proxy for RFC-0015 agent memory operations.

### _TasksProxy

`self.tasks` proxy for RFC-0012 task creation and management.

## Internal Classes

### BaseAgent

::: openintent.agents.BaseAgent
    options:
      show_source: false

### AgentConfig

::: openintent.agents.AgentConfig
    options:
      show_source: false
