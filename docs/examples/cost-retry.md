# Cost Tracking & Retry Policies

Monitor spend across agents and LLM calls, and configure resilient retry strategies.

## Cost Tracking (Imperative)

```python
from openintent import OpenIntentClient

client = OpenIntentClient(
    base_url="http://localhost:8000",
    agent_id="cost-monitor"
)

# Costs are tracked automatically when using LLM adapters
# Query cost for a single intent
cost = client.get_intent_cost(intent_id)
print(f"Intent cost: ${cost.total_usd:.4f}")
print(f"  Input tokens: {cost.input_tokens}")
print(f"  Output tokens: {cost.output_tokens}")
print(f"  LLM calls: {cost.call_count}")

# Aggregate cost across a portfolio
portfolio_cost = client.get_portfolio_cost(portfolio_id)
print(f"Portfolio total: ${portfolio_cost.total_usd:.2f}")

for agent_cost in portfolio_cost.by_agent:
    print(f"  {agent_cost.agent_id}: ${agent_cost.total_usd:.4f}")
```

## Budget Guardrails

```python
from openintent.agents import Coordinator

@Coordinator(
    "budget-coordinator",
    guardrails=[
        {"type": "budget", "max_cost_usd": 10.0},
    ]
)
class BudgetCoordinator:

    async def check_budget(self, portfolio):
        cost = await self.get_portfolio_cost(portfolio.id)
        if cost.total_usd > 8.0:
            print("Warning: approaching budget limit")

        if cost.total_usd >= 10.0:
            await self.pause_portfolio(portfolio.id)
            print("Budget exceeded — portfolio paused")
```

## Retry Policies (Imperative)

```python
# Configure retry on intent creation
intent = client.create_intent(
    title="Flaky API Call",
    retry_policy={
        "max_attempts": 5,
        "backoff": "exponential",
        "base_delay_seconds": 1,
        "max_delay_seconds": 30,
        "retry_on": ["timeout", "server_error"]
    }
)
```

## Retry with Fallback Agents

```python
intent = client.create_intent(
    title="Critical Task",
    assign="primary-agent",
    retry_policy={
        "max_attempts": 3,
        "backoff": "exponential",
        "base_delay_seconds": 2,
        "fallback_agents": ["backup-agent-1", "backup-agent-2"]
    }
)
# If primary-agent fails 3 times, tries backup-agent-1,
# then backup-agent-2
```

## YAML Workflow with Cost and Retry

```yaml
openintent: "1.0"
info:
  name: "Resilient Data Pipeline"

coordinator:
  id: pipeline-lead
  guardrails:
    - type: budget
      max_cost_usd: 25.0
    - type: timeout
      max_seconds: 1800

workflow:
  fetch:
    title: "Fetch External Data"
    assign: fetcher
    retry:
      max_attempts: 5
      backoff: exponential
      base_delay_seconds: 2
      max_delay_seconds: 60
      retry_on: [timeout, server_error]

  process:
    title: "Process Data"
    assign: processor
    depends_on: [fetch]
    retry:
      max_attempts: 3
      backoff: linear
      base_delay_seconds: 5
      fallback_agents: [backup-processor]

  validate:
    title: "Validate Output"
    assign: validator
    depends_on: [process]
    cost:
      budget_usd: 2.0
      alert_threshold: 0.8

  deliver:
    title: "Deliver Results"
    assign: deliverer
    depends_on: [validate]
```

```python
from openintent.workflow import load_workflow

wf = load_workflow("resilient_pipeline.yaml")
wf.run()
```
