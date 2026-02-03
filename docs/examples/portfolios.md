# Portfolios Example

Portfolios group related intents for coordinated execution.

## Creating a Portfolio

```python
from openintent import OpenIntentClient

client = OpenIntentClient(
    base_url="http://localhost:8000",
    agent_id="coordinator"
)

# Create portfolio
portfolio = client.create_portfolio(
    name="Q1 Planning",
    description="Q1 2024 planning workflow"
)

# Add intents to portfolio
research = client.create_intent(
    title="Market Research",
    portfolio_id=portfolio.id
)

strategy = client.create_intent(
    title="Strategy Development",
    portfolio_id=portfolio.id,
    depends_on=[research.id]
)

roadmap = client.create_intent(
    title="Roadmap Creation",
    portfolio_id=portfolio.id,
    depends_on=[strategy.id]
)
```

## Using PortfolioSpec DSL

Declarative workflow definition:

```python
from openintent.agents import PortfolioSpec, IntentSpec

workflow = PortfolioSpec(
    name="Onboarding Workflow",
    intents=[
        IntentSpec(
            title="Collect User Info",
            assign="form-agent",
            initial_state={"step": 1}
        ),
        IntentSpec(
            title="Verify Identity",
            assign="verification-agent",
            depends_on=["Collect User Info"]
        ),
        IntentSpec(
            title="Setup Account",
            assign="provisioning-agent",
            depends_on=["Verify Identity"]
        ),
        IntentSpec(
            title="Send Welcome Email",
            assign="notification-agent",
            depends_on=["Setup Account"]
        )
    ],
    governance_policy={
        "require_approval": ["Verify Identity"]
    }
)
```

## Portfolio Status

```python
# Get portfolio with all intents
portfolio = client.get_portfolio(portfolio_id)

print(f"Name: {portfolio.name}")
print(f"Status: {portfolio.status}")
print(f"Progress: {portfolio.progress}%")

for intent in portfolio.intents:
    print(f"  - {intent.title}: {intent.status}")
```

## Monitoring Portfolio Progress

```python
# Subscribe to portfolio events
for event in client.subscribe_portfolio(portfolio_id):
    if event.event_type == "status_changed":
        intent = next(
            i for i in portfolio.intents 
            if i.id == event.intent_id
        )
        print(f"{intent.title} -> {event.payload.get('new')}")
```

## Coordinator Pattern

```python
from openintent.agents import Coordinator, on_all_complete

@Coordinator("workflow-coordinator")
class WorkflowCoordinator:
    
    async def start_workflow(self, spec: PortfolioSpec):
        """Execute a workflow specification."""
        await self.run_portfolio(spec)
    
    @on_all_complete
    async def handle_completion(self, portfolio):
        """Called when all intents complete."""
        print(f"Workflow {portfolio.name} completed!")
        
        # Aggregate results
        results = {}
        for intent in portfolio.intents:
            results[intent.title] = intent.state
        
        return results
```
