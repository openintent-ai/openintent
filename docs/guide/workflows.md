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
  model: gpt-5.2

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

channels:
  data-sync:
    members: [researcher, synthesizer]
    member_policy: explicit
    audit: true
```

## Channels

The `channels:` block defines named communication channels for direct agent-to-agent messaging (RFC-0021). Channels are created automatically when the workflow starts.

### Basic Channel

```yaml
channels:
  questions:
    members: [researcher, data-agent]
    audit: true
```

This creates a channel called `questions` that only `researcher` and `data-agent` can use. Messages are recorded in the event log.

### Channel Options

```yaml
channels:
  data-sync:
    members: [agent-a, agent-b]
    member_policy: explicit    # Only listed members (default: "intent")
    audit: true                # Copy messages to event log
    ttl_seconds: 3600          # Auto-close after 1 hour of inactivity
    max_messages: 500          # Retain last 500 messages

  progress:
    member_policy: intent      # Any agent on the intent can participate
    audit: false
```

| Field | Default | Description |
|-------|---------|-------------|
| `members` | `[]` | Agent IDs permitted on the channel |
| `member_policy` | `"intent"` | `"explicit"` (members only) or `"intent"` (any agent) |
| `audit` | `false` | Copy messages to the intent event log |
| `ttl_seconds` | `null` | Auto-close after inactivity (null = lives until intent resolves) |
| `max_messages` | `1000` | Max messages retained |

### Per-Agent Message Handlers

Declare which agents handle messages from which channels:

```yaml
agents:
  data-agent:
    on_message:
      - channel: data-sync
        handler: answer_questions
  
  researcher:
    on_message:
      - channel: progress
        handler: log_progress
```

This maps to the `@on_message` decorator in Python:

```python
@Agent("data-agent")
class DataAgent:
    @on_message(channel="data-sync")
    async def answer_questions(self, message):
        return {"answer": "v2.3"}
```

!!! tip "Channels + Workflows"
    Channels are ideal for coordination *within* a workflow phase — asking a peer agent a question, broadcasting progress, or negotiating work boundaries. For data passing *between* phases, use intent state and `depends_on`.

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

## Permissions (RFC-0011)

Control who can see and modify each phase's data using the unified `permissions` field.

### Quick Start

The simplest forms — a single string or a list of agents:

```yaml
workflow:
  public_step:
    assign: researcher
    permissions: open           # Anyone can access

  private_step:
    assign: analyst
    permissions: private        # Only the assigned agent

  team_step:
    assign: lead
    permissions: [analyst, auditor]  # Only these agents
```

### Full Permissions Object

For fine-grained control, use the full object form with `policy`, `allow`, `delegate`, and `context`:

```yaml
workflow:
  sensitive_analysis:
    assign: analyst
    permissions:
      policy: restricted
      default: read
      allow:
        - agent: "analyst"
          level: write
        - agent: "auditor"
          level: read
      delegate:
        to: ["specialist-bot", "backup-bot"]
        level: write
      context: [dependencies, peers, acl, delegated_by]
```

### Delegation

When `delegate` is specified, agents can hand off work:

```python
@Agent("triage-bot")
class TriageAgent:
    @on_assignment
    async def handle(self, intent):
        if needs_specialist(intent):
            await self.delegate(intent.id, "specialist-bot")
            return {"status": "delegated"}
        return {"result": process(intent)}
    
    @on_access_requested
    async def policy(self, intent, request):
        if "compliance" in (request.capabilities or []):
            return "approve"
        return "defer"
```

### Context Injection

The `context` field inside `permissions` controls what context the agent automatically receives. In your agent, context is available via `intent.ctx`:

```python
@Agent("analyst")
class AnalystAgent:
    @on_assignment
    async def handle(self, intent):
        ctx = intent.ctx
        if ctx.delegated_by:
            print(f"Delegated by: {ctx.delegated_by}")
        
        for dep_id, dep_state in ctx.dependencies.items():
            print(f"Dependency {dep_id}: {dep_state}")
        
        return {"analysis": "complete"}
```

### Governance Access Review

Set a workflow-level policy for access requests:

```yaml
governance:
  access_review:
    on_request: defer
    approvers: ["admin-agent", "compliance-officer"]
    timeout_hours: 4
```

### Backward Compatibility

Legacy `access`, `delegation`, and `context` fields at the phase level are still parsed and auto-converted to the unified `permissions` format. New workflows should always use `permissions`.

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
  model: gpt-5.2
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

### 3. Document Agents with Capabilities

Declare agents with capabilities for access decisions:

```yaml
agents:
  researcher:
    description: "Searches and analyzes web sources"
    capabilities: [search, summarization]
    default_permission: read
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
