# Workflow API Reference

Python API for loading, validating, and executing YAML workflows.

## WorkflowSpec

The main class for working with workflow YAML files.

::: openintent.workflow.WorkflowSpec
    options:
      show_source: false
      members:
        - from_yaml
        - from_string
        - to_portfolio_spec
        - run

### Example Usage

```python
from openintent.workflow import WorkflowSpec

# Load from file
spec = WorkflowSpec.from_yaml("workflow.yaml")

# Access metadata
print(f"Workflow: {spec.name}")
print(f"Version: {spec.workflow_version}")
print(f"Phases: {len(spec.phases)}")

# List phases
for phase in spec.phases:
    print(f"  - {phase.title} -> {phase.assign}")

# Execute
result = await spec.run(
    server_url="http://localhost:8000",
    api_key="dev-user-key"
)
```

### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `version` | `str` | Protocol version (e.g., `"1.0"`) |
| `name` | `str` | Workflow name |
| `description` | `str` | Workflow description |
| `workflow_version` | `str` | Semantic version |
| `agents` | `dict[str, dict]` | Declared agents |
| `phases` | `list[PhaseConfig]` | Workflow phases |
| `governance` | `GovernanceConfig | None` | Governance settings |
| `llm` | `LLMConfig | None` | LLM configuration |
| `types` | `dict[str, Any]` | Type definitions |
| `source_path` | `Path | None` | Source file path |

## PhaseConfig

Configuration for a single workflow phase.

::: openintent.workflow.PhaseConfig
    options:
      show_source: false

### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `name` | `str` | Internal phase name (from YAML key) |
| `title` | `str` | Display title |
| `assign` | `str` | Agent ID to assign |
| `description` | `str` | Phase description |
| `depends_on` | `list[str]` | Dependency phase names |
| `constraints` | `list[str]` | Constraints for the agent |
| `initial_state` | `dict[str, Any]` | Initial state values |
| `retry` | `dict | None` | Retry policy (RFC-0010) |
| `leasing` | `dict | None` | Leasing config (RFC-0003) |
| `cost_tracking` | `dict | None` | Cost tracking (RFC-0009) |
| `attachments` | `list[dict] | None` | Attachments (RFC-0005) |
| `inputs` | `dict[str, str]` | Input mappings |
| `outputs` | `list[str]` | Output state keys |
| `skip_when` | `str | None` | Skip condition |

### Example

```python
for phase in spec.phases:
    print(f"Phase: {phase.title}")
    print(f"  Assigned to: {phase.assign}")
    print(f"  Depends on: {phase.depends_on}")
    print(f"  Constraints: {phase.constraints}")
    
    if phase.retry:
        print(f"  Retry: {phase.retry.get('max_attempts')} attempts")
```

## LLMConfig

LLM provider configuration.

::: openintent.workflow.LLMConfig
    options:
      show_source: false

### Attributes

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `provider` | `str` | `"openai"` | Provider name |
| `model` | `str` | `""` | Model identifier |
| `temperature` | `float` | `0.7` | Sampling temperature |
| `max_tokens` | `int` | `4096` | Maximum tokens |
| `system_prompt` | `str` | `""` | System prompt |

### Methods

#### `get_env_key()`

Returns the environment variable name for the API key.

```python
config = spec.llm
print(config.get_env_key())  # "OPENAI_API_KEY"
```

#### `get_default_model()`

Returns the default model for the provider.

```python
config = LLMConfig(provider="anthropic")
print(config.get_default_model())  # "claude-sonnet-4-20250514"
```

## GovernanceConfig

Governance settings for approval gates and budgets.

::: openintent.workflow.GovernanceConfig
    options:
      show_source: false

### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `require_approval` | `dict | None` | Approval gate configuration |
| `max_cost_usd` | `float | None` | Maximum workflow cost |
| `timeout_hours` | `float | None` | Maximum duration |
| `escalation` | `dict[str, str] | None` | Escalation contacts |

### Example

```python
if spec.governance:
    if spec.governance.max_cost_usd:
        print(f"Budget: ${spec.governance.max_cost_usd}")
    if spec.governance.timeout_hours:
        print(f"Timeout: {spec.governance.timeout_hours}h")
```

## Validation Functions

### validate_workflow()

Validate a workflow file and return warnings.

::: openintent.workflow.validate_workflow
    options:
      show_source: false

```python
from openintent.workflow import validate_workflow, WorkflowValidationError

try:
    warnings = validate_workflow("workflow.yaml")
    for warning in warnings:
        print(f"Warning: {warning}")
    print("Workflow is valid!")
except WorkflowValidationError as e:
    print(f"Validation failed: {e}")
```

### list_sample_workflows()

List available sample workflows.

::: openintent.workflow.list_sample_workflows
    options:
      show_source: false

```python
from openintent.workflow import list_sample_workflows

for workflow in list_sample_workflows():
    print(f"{workflow['name']}: {workflow['description']}")
    print(f"  Path: {workflow['path']}")
    print(f"  Phases: {workflow['phases']}")
```

## Exceptions

### WorkflowError

Base exception for workflow errors.

::: openintent.workflow.WorkflowError
    options:
      show_source: false

### WorkflowValidationError

Raised when workflow YAML is invalid.

::: openintent.workflow.WorkflowValidationError
    options:
      show_source: false

```python
from openintent.workflow import WorkflowSpec, WorkflowValidationError

try:
    spec = WorkflowSpec.from_yaml("invalid.yaml")
except WorkflowValidationError as e:
    print(f"Path: {e.path}")
    print(f"Error: {e}")
    print(f"Suggestion: {e.suggestion}")
```

### WorkflowNotFoundError

Raised when workflow file is not found.

::: openintent.workflow.WorkflowNotFoundError
    options:
      show_source: false

## Integration with Agents

### Converting to PortfolioSpec

For manual execution with a Coordinator:

```python
from openintent.workflow import WorkflowSpec
from openintent import Coordinator

# Load workflow
spec = WorkflowSpec.from_yaml("workflow.yaml")

# Convert to PortfolioSpec
portfolio_spec = spec.to_portfolio_spec()

# Execute with Coordinator
coordinator = Coordinator(
    agent_id="orchestrator",
    base_url="http://localhost:8000",
    api_key="dev-user-key"
)

result = await coordinator.execute(portfolio_spec)
```

### Direct Execution

For simpler use cases:

```python
spec = WorkflowSpec.from_yaml("workflow.yaml")

result = await spec.run(
    server_url="http://localhost:8000",
    api_key="dev-user-key",
    timeout=300,
    verbose=True
)
```

## CLI Reference

The workflow module provides CLI commands via the `openintent` command:

```bash
# Run a workflow
openintent run workflow.yaml [OPTIONS]

Options:
  --server URL      Server URL (default: http://localhost:8000)
  --api-key KEY     API key
  --timeout SEC     Timeout in seconds (default: 300)
  --output FILE     Save results to file
  --dry-run         Validate only
  --verbose         Show progress

# Validate a workflow
openintent validate workflow.yaml

# List sample workflows
openintent list

# Create from template
openintent new "Workflow Name"
```

## See Also

- [Workflow YAML Specification](../spec/workflow-yaml.md) - Complete schema
- [Workflows Guide](../guide/workflows.md) - Usage guide
- [Agent Abstractions](agents.md) - Building agents
