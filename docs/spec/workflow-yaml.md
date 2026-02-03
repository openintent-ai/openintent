# Workflow YAML Specification

**Version:** 1.0  
**Status:** Stable

The OpenIntent Workflow YAML format provides a declarative way to define multi-agent coordination workflows. This specification describes the complete schema, validation rules, and execution semantics.

## Overview

A workflow YAML file describes:

- **Metadata** - Name, version, description
- **Agents** - Declared agent capabilities
- **Phases** - Sequential or parallel work units assigned to agents
- **Governance** - Approval gates, budgets, timeouts
- **LLM Configuration** - Provider settings for AI-powered agents

## Document Structure

```yaml
openintent: "1.0"           # Required: Protocol version

info:                       # Required: Workflow metadata
  name: "..."               # Required: Workflow name
  version: "1.0.0"          # Optional: Semantic version
  description: "..."        # Optional: Description

governance:                 # Optional: Governance rules
  require_approval: {...}
  max_cost_usd: 10.00
  timeout_hours: 24

agents:                     # Optional: Agent declarations
  agent-id:
    description: "..."
    capabilities: [...]

llm:                        # Optional: LLM provider config
  provider: "openai"
  model: "gpt-4o"

workflow:                   # Required: Workflow phases
  phase_name:
    title: "..."
    assign: "agent-id"
    ...

types:                      # Optional: Type definitions
  TypeName:
    field: type
```

## Required Fields

### `openintent`

Protocol version identifier. Currently `"1.0"`.

```yaml
openintent: "1.0"
```

### `info`

Workflow metadata object.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Human-readable workflow name |
| `version` | string | No | Semantic version (default: `"1.0.0"`) |
| `description` | string | No | Detailed description |

```yaml
info:
  name: "Research Pipeline"
  version: "2.1.0"
  description: "Research a topic and create a summary report"
```

### `workflow`

Map of phase definitions. Each key is the phase name (internal identifier).

```yaml
workflow:
  research:
    title: "Gather Research"
    description: "Research the topic thoroughly"
    assign: researcher
    
  summarize:
    title: "Create Summary"
    assign: summarizer
    depends_on: [research]
```

## Phase Configuration

Each phase in the `workflow` section supports these fields:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `title` | string | No | Display title (defaults to phase name) |
| `description` | string | No | What this phase should accomplish |
| `assign` | string | **Yes** | Agent ID to assign this phase to |
| `depends_on` | list[string] | No | Phase names that must complete first |
| `constraints` | list[string] | No | Rules/parameters for the agent |
| `initial_state` | object | No | Initial state values |
| `inputs` | object | No | Input mappings from dependencies |
| `outputs` | list[string] | No | State keys to expose to dependents |
| `skip_when` | string | No | Condition expression to skip phase |

### RFC-Specific Phase Fields

| Field | Type | RFC | Description |
|-------|------|-----|-------------|
| `retry` | object | RFC-0010 | Retry policy configuration |
| `leasing` | object | RFC-0003 | Scope leasing configuration |
| `cost_tracking` | object | RFC-0009 | Cost budget and tracking |
| `attachments` | list[object] | RFC-0005 | File attachments |

### Phase Example

```yaml
workflow:
  analysis:
    title: "Analyze Document"
    description: "Extract key information from the document"
    assign: analyzer-agent
    depends_on:
      - extraction
    constraints:
      - "Be thorough but concise"
      - "Focus on actionable items"
    initial_state:
      phase: "analysis"
      depth: "comprehensive"
    retry:
      max_attempts: 3
      backoff: exponential
      initial_delay_ms: 1000
    outputs:
      - findings
      - recommendations
```

## Agents Section

Declare agents referenced in the workflow. While optional, it provides documentation and validation.

```yaml
agents:
  researcher:
    description: "Gathers and analyzes information from sources"
    capabilities:
      - web-search
      - document-analysis
      - summarization
      
  summarizer:
    description: "Creates concise summaries from research"
    capabilities:
      - text-generation
      - formatting
```

| Field | Type | Description |
|-------|------|-------------|
| `description` | string | What this agent does |
| `capabilities` | list[string] | Agent capabilities for validation |

## Governance Section

Configure approval gates, budgets, and timeouts.

```yaml
governance:
  require_approval:
    when: "risk.category == 'HIGH'"
    approvers:
      - "legal-team"
      - "compliance-officer"
    timeout_hours: 24
    on_timeout: "escalate"
  max_cost_usd: 10.00
  timeout_hours: 48
  escalation:
    contact: "admin@company.com"
    after_hours: 4
```

| Field | Type | Description |
|-------|------|-------------|
| `require_approval` | object | Conditional approval configuration |
| `max_cost_usd` | number | Maximum workflow cost budget |
| `timeout_hours` | number | Maximum workflow duration |
| `escalation` | object | Escalation contact info |

### Approval Configuration

| Field | Type | Description |
|-------|------|-------------|
| `when` | string | Condition expression for requiring approval |
| `approvers` | list[string] | List of approver IDs |
| `timeout_hours` | number | Time to wait for approval |
| `on_timeout` | string | Action on timeout: `"escalate"`, `"abort"`, `"proceed"` |

## LLM Configuration

Configure the LLM provider for AI-powered agents.

```yaml
llm:
  provider: "openai"      # openai, anthropic, or env
  model: "gpt-4o"         # Model name (optional)
  temperature: 0.7        # Sampling temperature
  max_tokens: 4096        # Max response tokens
  system_prompt: "..."    # Global system prompt
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `provider` | string | `"openai"` | LLM provider |
| `model` | string | Provider default | Model identifier |
| `temperature` | number | `0.7` | Sampling temperature |
| `max_tokens` | integer | `4096` | Maximum tokens |
| `system_prompt` | string | `""` | System prompt |

### Provider Defaults

| Provider | Default Model | Environment Variable |
|----------|---------------|---------------------|
| `openai` | `gpt-4o` | `OPENAI_API_KEY` |
| `anthropic` | `claude-sonnet-4-20250514` | `ANTHROPIC_API_KEY` |
| `env` | `gpt-4o` | Auto-detect from env |

## Retry Configuration

Configure retry behavior for failed phases (RFC-0010).

```yaml
retry:
  max_attempts: 5
  backoff: exponential           # constant, linear, exponential
  initial_delay_ms: 1000
  max_delay_ms: 60000
  retryable_errors:
    - "TIMEOUT"
    - "RATE_LIMIT"
  fallback_agent: "backup-agent"
```

| Field | Type | Description |
|-------|------|-------------|
| `max_attempts` | integer | Maximum retry attempts |
| `backoff` | string | Backoff strategy |
| `initial_delay_ms` | integer | Initial delay in milliseconds |
| `max_delay_ms` | integer | Maximum delay cap |
| `retryable_errors` | list[string] | Error types to retry |
| `fallback_agent` | string | Agent to use after max attempts |

## Leasing Configuration

Configure scope leasing for exclusive access (RFC-0003).

```yaml
leasing:
  strategy: per_section          # global, per_section, custom
  scope: "section:{{section.id}}"
  ttl_seconds: 60
  wait_for_lock: true
```

| Field | Type | Description |
|-------|------|-------------|
| `strategy` | string | Leasing strategy |
| `scope` | string | Scope pattern (supports interpolation) |
| `ttl_seconds` | integer | Lease time-to-live |
| `wait_for_lock` | boolean | Wait for lock or fail immediately |

## Cost Tracking Configuration

Configure budget and cost tracking (RFC-0009).

```yaml
cost_tracking:
  enabled: true
  budget_usd: 5.00
  alert_at_percent: 80
```

| Field | Type | Description |
|-------|------|-------------|
| `enabled` | boolean | Enable cost tracking |
| `budget_usd` | number | Phase budget in USD |
| `alert_at_percent` | integer | Alert threshold percentage |

## Attachments Configuration

Declare expected attachments (RFC-0005).

```yaml
attachments:
  - filename: "report.pdf"
    content_type: "application/pdf"
  - filename: "data.json"
    content_type: "application/json"
```

| Field | Type | Description |
|-------|------|-------------|
| `filename` | string | Attachment filename |
| `content_type` | string | MIME type |

## Types Section

Define types for validation and documentation.

```yaml
types:
  Finding:
    source: string
    content: string
    confidence: number
    
  RiskLevel:
    enum: ["low", "medium", "high", "critical"]
```

## Dependency Resolution

Dependencies are resolved using topological sort:

1. Phases with no `depends_on` run immediately (can be parallel)
2. A phase starts only when ALL dependencies are `completed`
3. Circular dependencies are detected and rejected at validation time

```yaml
workflow:
  # These two run in parallel (no dependencies)
  research:
    assign: researcher
  competitor_analysis:
    assign: analyst
    
  # This waits for both above to complete
  synthesis:
    assign: synthesizer
    depends_on: [research, competitor_analysis]
    
  # This waits for synthesis
  report:
    assign: reporter
    depends_on: [synthesis]
```

## Validation Rules

The parser validates:

1. **Required fields** - `openintent`, `info.name`, `workflow`, phase `assign`
2. **Dependency references** - All `depends_on` must reference valid phase names
3. **Circular dependencies** - No cycles allowed in dependency graph
4. **Agent references** - Warns if `assign` references undeclared agent

### Example Validation Errors

```
WorkflowValidationError: Missing 'openintent' version field
  Hint: Add 'openintent: "1.0"' at the top of your file

WorkflowValidationError: Phase 'synthesis' depends on unknown phase 'resarch'
  Hint: Available phases: research, analysis, report

WorkflowValidationError: Circular dependency detected: a -> b -> c -> a
  Hint: Remove one of the dependencies to break the cycle
```

## Execution

### CLI Execution

```bash
# Run a workflow
openintent run workflow.yaml

# With options
openintent run workflow.yaml --server http://localhost:8000
openintent run workflow.yaml --api-key my-key
openintent run workflow.yaml --timeout 600
openintent run workflow.yaml --output result.json

# Validate without running
openintent validate workflow.yaml

# List sample workflows
openintent list

# Create from template
openintent new "My Workflow"
```

### Programmatic Execution

```python
from openintent.workflow import WorkflowSpec

# Load from file
spec = WorkflowSpec.from_yaml("workflow.yaml")

# Or from string
spec = WorkflowSpec.from_string(yaml_content)

# Convert to PortfolioSpec for manual execution
portfolio = spec.to_portfolio_spec()

# Or execute directly
result = await spec.run(
    server_url="http://localhost:8000",
    api_key="dev-user-key",
    timeout=300,
    verbose=True
)
```

## Complete Example

```yaml
openintent: "1.0"

info:
  name: "Research Pipeline"
  version: "1.0.0"
  description: "Research a topic and create a comprehensive report"

governance:
  max_cost_usd: 5.00
  timeout_hours: 2

agents:
  researcher:
    description: "Gathers information from various sources"
    capabilities: [web-search, summarization]
    
  analyst:
    description: "Analyzes and synthesizes information"
    capabilities: [analysis, reasoning]
    
  writer:
    description: "Creates polished written output"
    capabilities: [writing, formatting]

llm:
  provider: openai
  model: gpt-4o
  temperature: 0.7

workflow:
  research:
    title: "Gather Research"
    description: "Research the topic from multiple sources"
    assign: researcher
    constraints:
      - "Use at least 3 sources"
      - "Focus on recent information"
    initial_state:
      phase: "research"
    retry:
      max_attempts: 3
      backoff: exponential
    outputs:
      - sources
      - findings
      
  analysis:
    title: "Analyze Findings"
    description: "Synthesize research into key insights"
    assign: analyst
    depends_on: [research]
    cost_tracking:
      enabled: true
      budget_usd: 2.00
    outputs:
      - insights
      - recommendations
      
  report:
    title: "Write Report"
    description: "Create a comprehensive written report"
    assign: writer
    depends_on: [analysis]
    attachments:
      - filename: "report.md"
        content_type: "text/markdown"
```

## See Also

- [Workflows User Guide](../guide/workflows.md) - Step-by-step usage guide
- [Workflow API Reference](../api/workflow.md) - Python API documentation
- [Sample Workflows](https://github.com/openintent-ai/openintent/tree/main/examples/workflows) - Example workflows
