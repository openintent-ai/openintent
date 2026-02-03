# Workflows Guide

YAML workflows provide a declarative way to define multi-agent coordination without writing code. This guide walks through creating, running, and customizing workflows.

## Quick Start

### 1. Create a Workflow File

Create `my_workflow.yaml`:

```yaml
openintent: "1.0"

info:
  name: "My First Workflow"
  description: "A simple two-phase workflow"

workflow:
  research:
    title: "Research Topic"
    description: "Gather information about the topic"
    assign: researcher
    
  summarize:
    title: "Create Summary"
    description: "Summarize the research findings"
    assign: summarizer
    depends_on: [research]
```

### 2. Start the Server

```bash
openintent-server
```

### 3. Run Your Agents

Each agent referenced in the workflow needs a running implementation:

```python
# researcher.py
from openintent import Agent, on_assignment

@Agent("researcher")
class ResearchAgent:
    @on_assignment
    async def handle(self, intent):
        return {"findings": "Research results here..."}

if __name__ == "__main__":
    ResearchAgent.run()
```

```python
# summarizer.py
from openintent import Agent, on_assignment

@Agent("summarizer")
class SummarizerAgent:
    @on_assignment
    async def handle(self, intent):
        findings = intent.state.get("findings", "")
        return {"summary": f"Summary of: {findings[:100]}..."}

if __name__ == "__main__":
    SummarizerAgent.run()
```

### 4. Execute the Workflow

```bash
openintent run my_workflow.yaml
```

## Workflow Structure

### Minimal Workflow

The smallest valid workflow:

```yaml
openintent: "1.0"

info:
  name: "Minimal"

workflow:
  task:
    assign: my-agent
```

### Full Workflow

A workflow using all features:

```yaml
openintent: "1.0"

info:
  name: "Full Example"
  version: "2.0.0"
  description: "Demonstrates all workflow features"

governance:
  max_cost_usd: 10.00
  timeout_hours: 24
  require_approval:
    when: "risk == 'high'"
    approvers: [admin]

agents:
  researcher:
    description: "Gathers information"
    capabilities: [search, analysis]

llm:
  provider: openai
  model: gpt-4o

workflow:
  research:
    title: "Research Phase"
    assign: researcher
    constraints:
      - "Be thorough"
    initial_state:
      depth: "comprehensive"
    retry:
      max_attempts: 3
      backoff: exponential
    outputs:
      - findings

  synthesis:
    title: "Synthesis Phase"
    assign: synthesizer
    depends_on: [research]
    cost_tracking:
      enabled: true
      budget_usd: 5.00
```

## Dependencies

### Sequential Dependencies

Phases run in order:

```yaml
workflow:
  step1:
    assign: agent-a
    
  step2:
    assign: agent-b
    depends_on: [step1]
    
  step3:
    assign: agent-c
    depends_on: [step2]
```

### Parallel Execution

Phases without dependencies run in parallel:

```yaml
workflow:
  # These three run simultaneously
  research_a:
    assign: researcher
  research_b:
    assign: researcher
  research_c:
    assign: researcher
    
  # This waits for all three
  merge:
    assign: synthesizer
    depends_on: [research_a, research_b, research_c]
```

### Diamond Dependencies

Multiple phases can depend on the same prerequisite:

```yaml
workflow:
  fetch_data:
    assign: fetcher
    
  analyze_trends:
    assign: analyst
    depends_on: [fetch_data]
    
  analyze_sentiment:
    assign: analyst
    depends_on: [fetch_data]
    
  report:
    assign: reporter
    depends_on: [analyze_trends, analyze_sentiment]
```

## Passing Data Between Phases

### Using State

Each phase can read state from previous phases:

```yaml
workflow:
  research:
    assign: researcher
    initial_state:
      topic: "AI trends"
    outputs:
      - findings

  summarize:
    assign: summarizer
    depends_on: [research]
    # Agent can access intent.state.findings
```

In your agent:

```python
@Agent("summarizer")
class SummarizerAgent:
    @on_assignment
    async def handle(self, intent):
        # Access state from previous phase
        findings = intent.state.get("findings", [])
        
        summary = create_summary(findings)
        return {"summary": summary}
```

### Using Constraints

Pass requirements to agents:

```yaml
workflow:
  research:
    assign: researcher
    constraints:
      - "Use at least 3 sources"
      - "Focus on peer-reviewed content"
      - "Include publication dates"
```

In your agent:

```python
@Agent("researcher")
class ResearchAgent:
    @on_assignment
    async def handle(self, intent):
        # Constraints available in intent.constraints
        for constraint in intent.constraints:
            print(f"Must satisfy: {constraint}")
```

## Governance

### Cost Budgets

Limit total workflow cost:

```yaml
governance:
  max_cost_usd: 10.00
```

Per-phase budgets:

```yaml
workflow:
  expensive_task:
    assign: my-agent
    cost_tracking:
      enabled: true
      budget_usd: 5.00
      alert_at_percent: 80
```

### Timeouts

Set workflow timeout:

```yaml
governance:
  timeout_hours: 24
```

### Approval Gates

Require human approval:

```yaml
governance:
  require_approval:
    when: "risk.level == 'high'"
    approvers:
      - "manager"
      - "compliance"
    timeout_hours: 4
    on_timeout: "escalate"
```

### Escalation

Configure escalation contacts:

```yaml
governance:
  escalation:
    contact: "admin@company.com"
    after_hours: 4
```

## Retry Policies

Handle transient failures:

```yaml
workflow:
  api_call:
    assign: api-agent
    retry:
      max_attempts: 5
      backoff: exponential       # constant, linear, exponential
      initial_delay_ms: 1000
      max_delay_ms: 60000
      retryable_errors:
        - "TIMEOUT"
        - "RATE_LIMIT"
        - "503"
      fallback_agent: "backup-agent"
```

## Leasing

Prevent concurrent access conflicts:

```yaml
workflow:
  update_database:
    assign: db-agent
    leasing:
      strategy: global           # global, per_section, custom
      scope: "database:users"
      ttl_seconds: 300
      wait_for_lock: true
```

## Attachments

Declare expected file outputs:

```yaml
workflow:
  generate_report:
    assign: reporter
    attachments:
      - filename: "report.pdf"
        content_type: "application/pdf"
      - filename: "data.json"
        content_type: "application/json"
```

## LLM Configuration

Configure the default LLM provider:

```yaml
llm:
  provider: openai              # openai, anthropic, env
  model: gpt-4o
  temperature: 0.7
  max_tokens: 4096
  system_prompt: "You are a helpful research assistant."
```

Use `provider: env` to auto-detect from environment variables:

```yaml
llm:
  provider: env                 # Uses OPENAI_API_KEY or ANTHROPIC_API_KEY
```

## CLI Commands

### Run a Workflow

```bash
openintent run workflow.yaml
```

Options:

```bash
--server URL        # OpenIntent server URL (default: http://localhost:8000)
--api-key KEY       # API key for authentication
--timeout SECONDS   # Execution timeout (default: 300)
--output FILE       # Save results to JSON file
--dry-run           # Validate without executing
--verbose           # Show detailed progress
```

### Validate a Workflow

```bash
openintent validate workflow.yaml
```

### List Sample Workflows

```bash
openintent list
```

### Create from Template

```bash
openintent new "My Workflow Name"
```

## Programmatic Usage

### Load and Execute

```python
from openintent.workflow import WorkflowSpec

# Load from file
spec = WorkflowSpec.from_yaml("workflow.yaml")

# Execute
result = await spec.run(
    server_url="http://localhost:8000",
    api_key="dev-user-key",
    timeout=300,
    verbose=True
)
```

### Load from String

```python
yaml_content = """
openintent: "1.0"
info:
  name: "Dynamic Workflow"
workflow:
  task:
    assign: my-agent
"""

spec = WorkflowSpec.from_string(yaml_content)
```

### Convert to PortfolioSpec

For manual execution with a Coordinator:

```python
from openintent.workflow import WorkflowSpec
from openintent import Coordinator

spec = WorkflowSpec.from_yaml("workflow.yaml")
portfolio_spec = spec.to_portfolio_spec()

coordinator = Coordinator("orchestrator", base_url, api_key)
result = await coordinator.execute(portfolio_spec)
```

### Validation

```python
from openintent.workflow import validate_workflow, WorkflowValidationError

try:
    warnings = validate_workflow("workflow.yaml")
    for warning in warnings:
        print(f"Warning: {warning}")
except WorkflowValidationError as e:
    print(f"Error: {e}")
```

## Best Practices

### 1. Start Simple

Begin with a minimal workflow and add complexity incrementally:

```yaml
openintent: "1.0"
info:
  name: "Simple Start"
workflow:
  main_task:
    assign: my-agent
```

### 2. Use Descriptive Names

Phase names become intent titles. Make them clear:

```yaml
workflow:
  # Good
  gather_customer_feedback:
    assign: feedback-agent
    
  # Less clear
  step1:
    assign: agent
```

### 3. Document Agents

Declare agents even though optional:

```yaml
agents:
  researcher:
    description: "Searches and analyzes web sources"
    capabilities: [search, summarization]
```

### 4. Set Reasonable Budgets

Always set cost limits for production:

```yaml
governance:
  max_cost_usd: 25.00
  
workflow:
  expensive_analysis:
    assign: analyst
    cost_tracking:
      enabled: true
      budget_usd: 10.00
```

### 5. Use Retry Policies

Handle transient failures gracefully:

```yaml
workflow:
  api_dependent_task:
    assign: api-agent
    retry:
      max_attempts: 3
      backoff: exponential
      retryable_errors: ["TIMEOUT", "RATE_LIMIT"]
```

### 6. Define Outputs

Explicitly declare what each phase produces:

```yaml
workflow:
  research:
    assign: researcher
    outputs:
      - sources
      - findings
      - confidence_score
```

## Troubleshooting

### "Missing 'openintent' version field"

Add the version at the top:

```yaml
openintent: "1.0"
```

### "Phase 'x' missing 'assign' field"

Every phase needs an agent:

```yaml
workflow:
  my_phase:
    assign: my-agent  # Required
```

### "Circular dependency detected"

Remove one dependency to break the cycle:

```yaml
# Invalid
workflow:
  a:
    depends_on: [c]
  b:
    depends_on: [a]
  c:
    depends_on: [b]  # Creates cycle: a -> c -> b -> a
```

### "Unknown phase referenced"

Check spelling in `depends_on`:

```yaml
workflow:
  research:
    assign: researcher
    
  synthesis:
    depends_on: [reserch]  # Typo! Should be 'research'
```

## See Also

- [Workflow YAML Specification](../spec/workflow-yaml.md) - Complete schema reference
- [Workflow API Reference](../api/workflow.md) - Python API documentation
- [Agent Abstractions](agents.md) - Building agents for workflows
