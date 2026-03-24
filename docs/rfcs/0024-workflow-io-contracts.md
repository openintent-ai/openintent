# RFC-0024: Workflow I/O Contracts

**Status:** Proposed  
**Created:** 2026-03-19  
**Authors:** OpenIntent Contributors  
**Requires:** RFC-0012 (Task Decomposition & Planning), RFC-0001 (Intents), RFC-0004 (Portfolios)  
**Addendum to:** RFC-0012

---

## Abstract

This RFC establishes typed input/output contracts at the task and phase level and assigns responsibility for wiring those contracts to the **executor**, not the agent. An agent receives a pre-populated `ctx.input` dict and returns a plain dict. The executor resolves dependency graphs, maps declared outputs from completed upstream tasks into the consuming task's `ctx.input`, and validates outputs against declared schemas before marking a task complete. Agents are fully decoupled from workflow topology and from each other's internal naming conventions.

This RFC directly answers **Open Question #4** from RFC-0012: _"Should task definitions include expected output schemas for validation, or is this left to the agent?"_ The answer is: output schemas are declared in the workflow definition, and validation is owned by the executor — not the agent.

---

## Motivation

RFC-0012 introduced Task as a first-class primitive and established that a task receives `input` and produces `output`. However, it left the responsibility of wiring those values across tasks ambiguous. In practice, agents working within a plan must reach into raw intent state using magic key names, relying on upstream agents to have written the right values in the right places. This creates three concrete problems:

1. **Implicit coupling.** Agent B cannot be written or tested without knowing exactly what key Agent A wrote to `intent.state`. Any rename in Agent A breaks Agent B silently.

2. **No executor-level guarantee.** Nothing in the protocol ensures that `ctx.input["quarter"]` is actually present when the task starts. Absence errors are only discovered at runtime, deep inside the agent's execution.

3. **Validation gap.** An agent can return any dict and call itself done. Downstream tasks that depend on specific output keys discover the missing data only when they attempt to read it.

### The Executor Must Own the Wiring

The solution is a clean inversion: the executor — not the agent — is responsible for:

- Reading declared `inputs`/`outputs` from the workflow definition
- Resolving the dependency graph to identify which upstream task produced each declared output
- Pre-populating `ctx.input` with exactly the keyed values the workflow declared, before the agent handler is invoked
- Validating the agent's return dict against declared `outputs` before accepting task completion
- Rejecting a task claim if the declared inputs cannot yet be resolved from upstream outputs

The agent's contract becomes simple and self-contained:

```python
async def handle(ctx: TaskContext) -> dict:
    # ctx.input is guaranteed to be pre-populated by the executor
    quarter = ctx.input["quarter"]
    revenue = await fetch(quarter)
    # return must satisfy the declared outputs schema
    return {"revenue": revenue, "expenses": 0}
```

The agent does not know about workflow topology. It does not call `get_sibling_output`. It reads from `ctx.input`, does work, and returns a dict.

---

## Design

### 1. Output Schema Declaration

Output schemas are declared inline in the phase definition, referencing types from the workflow's `types` block. A phase's `outputs` field is a mapping from output key names to type references.

#### 1.1 Simple Output Declaration

```yaml
types:
  FinancialSummary:
    revenue: number
    expenses: number
    net_profit: number

workflow:
  fetch_financials:
    title: "Fetch Financials"
    assign: data-agent
    outputs:
      revenue: number
      expenses: number
```

Each key in `outputs` is a name that the executor will require in the agent's return dict. The value is a type name (from `types`) or a primitive type string (`string`, `number`, `boolean`, `object`, `array`).

#### 1.2 Output Declaration with Type References

```yaml
types:
  Finding:
    source: string
    content: string
    confidence: number

workflow:
  research:
    title: "Research Phase"
    assign: researcher
    outputs:
      sources: array
      findings: Finding
```

When a type name from `types` is used, the executor validates that the returned value matches the declared shape.

#### 1.3 Optional Outputs

Individual output keys may be marked optional:

```yaml
outputs:
  summary: string
  citations: array
  warnings:
    type: array
    required: false
```

The `required` modifier (default: `true`) lets a phase declare outputs it may or may not produce, without causing a validation failure when absent.

---

### 2. Input Wiring

The `inputs` field on a phase declares which upstream outputs should be mapped into `ctx.input` before the agent runs. The executor resolves these mappings automatically.

#### 2.1 Input Mapping Syntax

```yaml
workflow:
  analysis:
    title: "Analyze Findings"
    assign: analyst
    depends_on: [research]
    inputs:
      research_findings: research.findings
      sources_list: research.sources
    outputs:
      insights: string
      recommendations: array
```

The format for input mapping values is `{phase_name}.{output_key}`. The executor reads the named key from the completed upstream phase's recorded output and places it at the declared `inputs` key name in `ctx.input`.

In the example above, before the `analysis` agent handler is called, the executor ensures:

```python
ctx.input == {
    "research_findings": <value of research.findings>,
    "sources_list": <value of research.sources>,
}
```

The agent reads `ctx.input["research_findings"]` directly and never touches raw intent state.

#### 2.2 Multi-Phase Input Wiring

A phase may draw inputs from multiple upstream phases:

```yaml
workflow:
  generate_report:
    title: "Generate Report"
    assign: reporter
    depends_on: [analysis, compliance_check]
    inputs:
      insights: analysis.insights
      recommendations: analysis.recommendations
      compliance_status: compliance_check.status
      violations: compliance_check.violations
    outputs:
      report_url: string
      report_summary: string
```

All declared input mappings must be resolvable from completed upstream phases. If any referenced key is missing from the upstream phase's recorded output, the executor raises `UnresolvableInputError` at claim time.

#### 2.3 Static Inputs

A phase may also declare static inputs that come from the workflow trigger or initial state, not from upstream phases. Static values use the `$` prefix to distinguish from phase references:

```yaml
workflow:
  fetch_data:
    title: "Fetch Data"
    assign: data-agent
    inputs:
      quarter: $trigger.quarter
      source: $initial_state.source
    outputs:
      data: object
```

Static input expressions are resolved at task creation time. The executor injects these alongside any dynamic (upstream phase) mappings.

**Implementation note:** `$trigger.*` and `$initial_state.*` values are projected into the intent's `initial_state` at portfolio creation time. At runtime, both the server-side and agent-side input resolution logic resolve these references from the intent's stored state. Trigger payloads that are not projected into `initial_state` will cause `UnresolvableInputError` at claim time.

---

### 3. Executor Wiring Semantics

This section is normative. Implementations conforming to this RFC must exhibit the following behavior.

#### 3.1 Claim-Time Validation

When an agent attempts to claim a task, the executor checks that all declared `inputs` can be resolved before granting the claim. A task is only claimable when:

1. All tasks in `depends_on` are in `completed` state.
2. All keys declared in `inputs` that reference upstream phase outputs exist in the recorded output of the referenced upstream phase.
3. All static input expressions (`$trigger.*`, `$initial_state.*`) resolve to non-null values.

If any check fails, the executor rejects the claim with `UnresolvableInputError` and the task remains in `ready` state.

#### 3.2 Pre-Handoff Population

Before dispatching a task to an agent handler, the executor:

1. Resolves each entry in the phase's `inputs` mapping.
2. Constructs a `ctx.input` dict containing the fully resolved key-value pairs.
3. Passes this dict to the agent as the `input` field of `TaskContext`.

The agent handler is never called with a partially populated or empty `ctx.input` when inputs are declared. The executor guarantees presence before handoff.

#### 3.3 Completion-Time Validation

When an agent calls the task completion endpoint (or returns from its handler), the executor:

1. Receives the agent's output dict.
2. Checks that every key declared as `required: true` (the default) in the phase's `outputs` is present in the output dict.
3. If type information is available, validates that each key's value matches the declared type.
4. If all checks pass, records the output against the completed task and transitions the task to `completed`.
5. If any check fails, rejects the completion with `MissingOutputError` or `OutputTypeMismatchError`, and the task remains in `running` state. The agent may retry the completion with a corrected output.

#### 3.4 Downstream Unblocking

After a task is marked `completed` and its outputs are recorded, the executor:

1. Identifies all downstream tasks whose `depends_on` includes the completed task.
2. For each downstream task: checks whether all of its other dependencies are also complete.
3. If all dependencies are complete, transitions the downstream task from `pending` to `ready`.
4. For each `ready` downstream task: pre-evaluates whether its `inputs` can now be fully resolved (claim-time validation). If any input remains unresolvable, the task stays in `ready` but will fail the claim check if an agent attempts to claim it.

---

### 4. Named Error Types

All executor I/O errors are named types that appear in task event logs and API error responses.

#### 4.1 `MissingOutputError`

**When raised:** Completion-time validation finds that a required output key is absent from the agent's returned dict.

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `task_id` | string | The task whose completion was rejected |
| `phase_name` | string | The phase definition name |
| `missing_keys` | list[string] | Output keys that were declared but not returned |

**Example event payload:**

```json
{
  "error": "MissingOutputError",
  "task_id": "task_01HXYZ",
  "phase_name": "fetch_financials",
  "missing_keys": ["expenses"],
  "message": "Task completion rejected: declared output key 'expenses' was not present in agent return value"
}
```

#### 4.2 `OutputTypeMismatchError`

**When raised:** Completion-time validation finds that a returned output key's value does not match the declared type.

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `task_id` | string | The task whose completion was rejected |
| `phase_name` | string | The phase definition name |
| `key` | string | The output key with the type mismatch |
| `expected_type` | string | Declared type |
| `actual_type` | string | Runtime type of the returned value |

**Note:** Type validation is structural, not coercive. The executor validates and rejects; it never casts values.

#### 4.3 `UnresolvableInputError`

**When raised:** Claim-time validation finds that one or more declared inputs cannot be resolved from completed upstream outputs.

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `task_id` | string | The task whose claim was rejected |
| `phase_name` | string | The phase definition name |
| `unresolvable_refs` | list[string] | Input mapping expressions that could not be resolved |

**Example event payload:**

```json
{
  "error": "UnresolvableInputError",
  "task_id": "task_01HABC",
  "phase_name": "analysis",
  "unresolvable_refs": ["research.findings"],
  "message": "Task claim rejected: upstream phase 'research' did not record output key 'findings'"
}
```

#### 4.4 `InputWiringError`

**When raised:** A structural problem with the `inputs` declaration is detected at workflow validation time (not at runtime). Examples: referencing a phase not in `depends_on`, referencing a non-existent phase, or using malformed mapping syntax.

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `phase_name` | string | The phase with the invalid inputs declaration |
| `invalid_refs` | list[string] | The malformed or invalid mapping expressions |
| `suggestion` | string | Human-readable fix hint |

---

### 5. `TaskContext` API

The `TaskContext` object passed to agent handlers is updated to reflect executor-managed input.

#### 5.1 `ctx.input`

`ctx.input` is a `dict` that is pre-populated by the executor before the agent handler is called. Its contents are determined by the phase's `inputs` declaration — not by raw intent state.

**Before RFC-0024:** `ctx.input` reflected whatever was stored in `intent.state` under certain keys, requiring agents to know upstream state naming conventions.

**After RFC-0024:** `ctx.input` contains exactly and only the keys declared in the phase's `inputs` mapping, populated from resolved upstream outputs. An agent that declares no `inputs` receives an empty dict (or the initial static inputs, if any are declared).

```python
@task(name="analysis")
async def run_analysis(ctx: TaskContext) -> dict:
    # ctx.input is guaranteed to contain exactly what the workflow declared
    # No reaching into intent.state, no magic key names
    findings = ctx.input["research_findings"]
    sources = ctx.input["sources_list"]

    result = analyze(findings, sources)

    return {
        "insights": result.insights,
        "recommendations": result.recommendations,
    }
```

#### 5.2 `ctx.get_sibling_output()` — Escape Hatch Only

`TaskContext.get_sibling_output(task_name: str) -> dict` remains available as a low-level escape hatch for exceptional circumstances, but is **not** the primary interface for passing data between tasks. It bypasses the executor's wiring guarantees and should be treated like `eval()` in Python: available when you need it, not the expected approach for normal use.

Use `ctx.get_sibling_output()` only when:

- You are integrating with a legacy workflow definition that has no `inputs`/`outputs` declarations.
- You need to inspect all sibling outputs for diagnostic purposes.
- You are in a dynamic context where the upstream key name cannot be known at workflow-definition time.

In all other cases, declare `inputs` in the workflow YAML and read from `ctx.input`.

---

### 6. Python SDK — Error Types

The SDK raises the named error types from Section 4 as Python exceptions.

```python
from openintent.workflow import (
    MissingOutputError,
    OutputTypeMismatchError,
    UnresolvableInputError,
    InputWiringError,
)
```

#### 6.1 `MissingOutputError`

```python
class MissingOutputError(WorkflowError):
    """
    Raised when a task completion is rejected because one or more
    declared output keys are absent from the agent's returned dict.

    Attributes:
        task_id: The ID of the task whose completion was rejected.
        phase_name: The name of the phase definition.
        missing_keys: The declared output keys that were not returned.
    """
    task_id: str
    phase_name: str
    missing_keys: list[str]
```

#### 6.2 `OutputTypeMismatchError`

```python
class OutputTypeMismatchError(WorkflowError):
    """
    Raised when a returned output key's value does not match the
    declared type. No coercion is attempted.

    Attributes:
        task_id: The ID of the task whose completion was rejected.
        phase_name: The name of the phase definition.
        key: The output key with the type mismatch.
        expected_type: The type declared in the workflow definition.
        actual_type: The Python type of the value returned by the agent.
    """
    task_id: str
    phase_name: str
    key: str
    expected_type: str
    actual_type: str
```

#### 6.3 `UnresolvableInputError`

```python
class UnresolvableInputError(WorkflowError):
    """
    Raised at claim time when one or more declared inputs cannot be
    resolved from completed upstream task outputs.

    Attributes:
        task_id: The ID of the task whose claim was rejected.
        phase_name: The name of the phase definition.
        unresolvable_refs: The input mapping expressions that could not
            be resolved (e.g. ["research.findings"]).
    """
    task_id: str
    phase_name: str
    unresolvable_refs: list[str]
```

#### 6.4 `InputWiringError`

```python
class InputWiringError(WorkflowValidationError):
    """
    Raised at workflow validation time when an inputs declaration is
    structurally invalid — for example, referencing a phase that is not
    in depends_on, referencing a non-existent phase, or using malformed
    mapping syntax.

    Attributes:
        phase_name: The phase with the invalid inputs declaration.
        invalid_refs: The malformed or invalid mapping expressions.
    """
    phase_name: str
    invalid_refs: list[str]
```

---

### 7. `to_portfolio_spec()` Wiring

When a `WorkflowSpec` is converted to a `PortfolioSpec` via `to_portfolio_spec()`, the `inputs` and `outputs` declarations from each phase must be preserved and threaded through so that the executor can perform wiring at runtime.

The `IntentSpec` dataclass gains two new fields:

```python
@dataclass
class IntentSpec:
    title: str
    description: str = ""
    assign: Optional[str] = None
    depends_on: Optional[list[str]] = None
    constraints: dict[str, Any] = field(default_factory=dict)
    initial_state: dict[str, Any] = field(default_factory=dict)
    # RFC-0024: I/O contracts
    inputs: dict[str, str] = field(default_factory=dict)
    outputs: dict[str, Any] = field(default_factory=dict)
```

`to_portfolio_spec()` maps each `PhaseConfig`'s `inputs` and `outputs` directly onto the corresponding `IntentSpec`. The executor accesses these fields when constructing `ctx.input` and when running completion-time validation.

---

### 8. Validation at Workflow Parse Time

In addition to runtime validation, the parser performs structural checks on `inputs`/`outputs` at workflow load time. These checks raise `InputWiringError` immediately, before any task runs.

**Checks performed:**

1. **Phase reference exists:** Every `phase_name` in an input mapping expression (`phase_name.key`) must name a phase that exists in the `workflow` section.

2. **Reference is a declared dependency:** Every phase referenced in an input mapping must appear in the consuming phase's `depends_on` list. A phase cannot wire inputs from a phase it does not depend on.

3. **Output key is declared:** If the upstream phase declares an `outputs` block, then the referenced key must appear in that block. (If the upstream phase has no `outputs` block, this check is skipped to allow incremental adoption.)

4. **Mapping syntax is valid:** Each input mapping value must match the pattern `{phase_name}.{key}` or `$trigger.{key}` or `$initial_state.{key}`. Other formats raise `InputWiringError`.

---

### 9. Incremental Adoption

Not all phases need to declare `inputs`/`outputs` immediately. The contract is opt-in per phase:

- A phase with **no `inputs` declaration**: `ctx.input` is empty (or contains only static workflow-level inputs). The agent is responsible for obtaining any data it needs from `ctx.get_sibling_output()` or other mechanisms.

- A phase with **no `outputs` declaration**: The executor skips completion-time output validation. The agent may return any dict (or nothing).

- A phase with **partial declarations**: Only the declared keys are validated. Additional keys returned by the agent beyond those declared are accepted and recorded.

This allows gradual adoption: start by declaring outputs on the most critical phases, then progressively add `inputs` declarations to their consumers.

---

### 10. Complete Example

```yaml
openintent: "1.0"

info:
  name: "Quarterly Compliance Report"
  version: "1.0.0"

types:
  FinancialData:
    revenue: number
    expenses: number
    quarter: string

  HRData:
    headcount: number
    attrition_rate: number

  AnalysisResult:
    findings: array
    risk_level: string
    violations_found: boolean

workflow:
  fetch_financials:
    title: "Fetch Financial Data"
    assign: data-agent
    inputs:
      quarter: $trigger.quarter
      source: $initial_state.source
    outputs:
      revenue: number
      expenses: number

  fetch_hr_data:
    title: "Fetch HR Data"
    assign: data-agent
    inputs:
      quarter: $trigger.quarter
    outputs:
      headcount: number
      attrition_rate: number

  run_analysis:
    title: "Run Compliance Analysis"
    assign: analytics-agent
    depends_on: [fetch_financials, fetch_hr_data]
    inputs:
      fin_revenue: fetch_financials.revenue
      fin_expenses: fetch_financials.expenses
      hr_headcount: fetch_hr_data.headcount
      hr_attrition: fetch_hr_data.attrition_rate
    outputs:
      findings: array
      risk_level: string
      violations_found: boolean

  generate_report:
    title: "Generate Report"
    assign: reporting-agent
    depends_on: [run_analysis]
    inputs:
      analysis_findings: run_analysis.findings
      risk_level: run_analysis.risk_level
      has_violations: run_analysis.violations_found
    outputs:
      report_url: string
      report_summary: string
```

The agent for `run_analysis` looks like:

```python
@task(name="run_analysis")
async def run_compliance_analysis(ctx: TaskContext) -> dict:
    # All inputs are guaranteed present by the executor
    revenue = ctx.input["fin_revenue"]
    expenses = ctx.input["fin_expenses"]
    headcount = ctx.input["hr_headcount"]
    attrition = ctx.input["hr_attrition"]

    result = await compliance_engine.analyze(
        revenue=revenue,
        expenses=expenses,
        headcount=headcount,
        attrition=attrition,
    )

    # Return must include all declared outputs
    return {
        "findings": result.findings,
        "risk_level": result.risk_level,
        "violations_found": result.violations_found,
    }
```

---

## Relationship to RFC-0012

RFC-0012 introduced Task as a protocol primitive and established that tasks have `input` and `output` fields. It left **Open Question #4** — _whether task definitions should include expected output schemas for validation, or leave that to the agent_ — explicitly unresolved.

**RFC-0024 resolves Open Question #4** with the following answer:

> Output schemas are declared in the workflow definition (in the phase's `outputs` field), and all validation responsibility belongs to the executor — not the agent. An agent receives a pre-populated `ctx.input` (wired by the executor from upstream phase outputs) and returns a plain dict. The executor validates that dict against declared outputs before recording task completion. Agents are decoupled from each other and from workflow topology.

This RFC does not modify:
- The Task state machine (RFC-0012 §1.2)
- The Plan object or plan states (RFC-0012 §2)
- The `get_sibling_output()` method signature (remains as an escape hatch)
- Any other RFC-0012 design choices

---

## Out of Scope

- **Channel I/O (RFC-0021):** Channel semantics are unchanged. This RFC only governs task-level `ctx.input`/`outputs`.
- **Intent-level state:** Only task-level input/output is in scope. `intent.state` continues to exist and function as defined in RFC-0001.
- **Runtime type coercion:** The executor validates types and rejects mismatches. It never casts or coerces values. An `int` returned for a declared `number` field passes; a `str` returned for a declared `number` field raises `OutputTypeMismatchError`.
- **Cross-portfolio task I/O wiring:** Input mappings may only reference phases within the same workflow. Cross-portfolio data passing is a separate concern.

---

## Open Questions

1. **Schema versioning:** When a workflow version is bumped and an output key is renamed, how are in-flight tasks (running under the old version) handled? Task outputs should be validated against the schema version active at task creation time.

2. **Array item typing:** The current proposal allows `outputs: findings: array` but does not specify array element types. A future extension could allow `array<Finding>` syntax for element-level validation.

3. **Nested object validation depth:** For `object` types, should validation be shallow (key presence only) or deep (recursive against the `types` block)? This RFC leaves it implementation-defined; a future RFC may standardize.

---

## RFC-0026 Patch: Upstream Suspension Rejection

When an agent attempts to claim a task whose declared inputs reference an upstream phase that is currently `suspended_awaiting_input`, `validate_claim_inputs()` MUST reject with `UpstreamIntentSuspendedError`:

```python
from openintent.workflow import UpstreamIntentSuspendedError

try:
    spec.validate_claim_inputs(phase_name, upstream_outputs, task_id=task_id)
except UpstreamIntentSuspendedError as e:
    # e.suspended_intent_id — the upstream intent that is suspended
    # e.expected_resume_at  — ISO-8601 estimate or None
    logger.info(f"Claim deferred: upstream intent {e.suspended_intent_id} is suspended")
```

**Workflow progress gains `suspended_phases`:**

```json
{
  "suspended_phases": [
    {
      "phase_name": "compliance_review",
      "intent_id": "intent_01ABC",
      "suspended_since": "2026-03-24T10:00:00Z",
      "expires_at": "2026-03-24T13:00:00Z"
    }
  ]
}
```

## Cross-RFC Interactions

| RFC | Interaction |
|-----|------------|
| RFC-0012 (Planning) | Addendum to RFC-0012; resolves Open Question #4 |
| RFC-0001 (Intents) | Intent state holds _io_inputs/_io_outputs for executor wiring |
| RFC-0004 (Portfolios) | Portfolios scope workflows |
| RFC-0025 (HITL) | Agents calling request_input() affect claim-time validation |
| RFC-0026 (Suspension Containers) | `upstream_intent_suspended` rejection reason; `suspended_phases` in workflow progress |

## References

- [RFC-0012: Task Decomposition & Planning](./0012-task-decomposition-planning.md) — parent RFC; defines Task, Plan, TaskContext
- [RFC-0001: Intent Objects](./0001-intent-objects.md) — intent state model
- [RFC-0004: Intent Portfolios](./0004-governance-arbitration.md) — portfolio boundaries
- [RFC-0021: Agent-to-Agent Messaging](./0021-agent-to-agent-messaging.md) — channel messaging (out of scope for this RFC)
- [RFC-0026: Suspension Propagation & Retry](./0026-suspension-container-interaction.md) — upstream suspension rejection
- [Temporal Activity Input/Output](https://docs.temporal.io/activities) — reference design for typed activity I/O
- [Prefect Task Parameters](https://docs.prefect.io/concepts/tasks/) — reference for task input contracts
