# OpenIntent Workflow Examples

This directory contains YAML workflow definitions showcasing different complexity levels and patterns.

## Quick Start

```bash
# 1. Start the OpenIntent server
openintent-server

# 2. Run a workflow
openintent run examples/workflows/hello_world.yaml
```

## Workflows

### Beginner

| Workflow | Description | Phases | Features |
|----------|-------------|--------|----------|
| [hello_world.yaml](hello_world.yaml) | Simplest possible workflow | 1 | Basic structure |

### Intermediate

| Workflow | Description | Phases | Features |
|----------|-------------|--------|----------|
| [research_assistant.yaml](research_assistant.yaml) | Research and synthesis | 2 | Dependencies, retry |
| [data_pipeline.yaml](data_pipeline.yaml) | ETL data processing | 4 | Sequential deps, retry, costs |

### Advanced

| Workflow | Description | Phases | Features |
|----------|-------------|--------|----------|
| [content_pipeline.yaml](content_pipeline.yaml) | Content creation with parallel phases | 4 | Parallel execution, costs, attachments |
| [compliance_review.yaml](compliance_review.yaml) | Document compliance review | 4 | All 21 RFCs, unified permissions, delegation, context injection |

## Workflow Structure

Every workflow YAML file follows this structure:

```yaml
openintent: "1.0"  # Required version

info:
  name: "My Workflow"  # Required
  version: "1.0.0"
  description: "What this workflow does"

governance:  # Optional
  max_cost_usd: 10.00
  timeout_hours: 24
  require_approval:
    when: "condition"

agents:  # Optional but recommended
  my-agent:
    description: "What this agent does"
    capabilities: ["list", "of", "capabilities"]
    default_permission: read  # RFC-0011

workflow:  # Required
  phase_name:
    title: "Human Readable Title"
    description: "What this phase does"
    assign: my-agent  # Required
    depends_on: []    # Optional list of phase names
    constraints: []   # Optional constraints
    initial_state: {} # Optional initial state
    permissions: open # RFC-0011: Unified access control (string | list | object)
```

## Running Workflows

### Basic Run

```bash
openintent run workflow.yaml
```

### With Options

```bash
# Different server
openintent run workflow.yaml --server http://localhost:9000

# Custom API key
openintent run workflow.yaml --api-key my-secret-key

# Longer timeout
openintent run workflow.yaml --timeout 600

# Save output
openintent run workflow.yaml --output result.json

# Dry run (validate only)
openintent run workflow.yaml --dry-run
```

### Validate Without Running

```bash
openintent validate workflow.yaml
```

### Create New Workflow

```bash
openintent new "My New Workflow"
```

## Implementing Agents

For each agent in your workflow, you need a corresponding agent implementation:

```python
from openintent import Agent, on_assignment, on_access_requested

@Agent("my-agent")
class MyAgent:
    @on_assignment
    async def process(self, intent):
        # Context auto-populated based on your permission
        if intent.ctx.delegated_by:
            print(f"Delegated by: {intent.ctx.delegated_by}")
        
        if needs_help(intent):
            await self.delegate(intent.id, "helper-agent")
        
        return {"result": "done"}
    
    @on_access_requested
    async def policy(self, intent, request):
        # Approve, deny, or defer access requests
        return "approve" if request.permission == "read" else "defer"

if __name__ == "__main__":
    MyAgent.run()
```

See [examples/agents/](../agents/) for complete agent examples.

## Creating Your Own Workflows

1. Start with `hello_world.yaml` as a template
2. Add phases for each step of your process
3. Define dependencies between phases
4. Add agents for each phase
5. Run and iterate!

```bash
# Create from template
openintent new "Customer Onboarding"

# Edit the generated file
vim customer_onboarding.yaml

# Validate
openintent validate customer_onboarding.yaml

# Run
openintent run customer_onboarding.yaml
```
