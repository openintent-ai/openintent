# Multi-Agent Workflow Example

This example demonstrates coordinating multiple agents using the OpenIntent protocol.

## Scenario

A research workflow with three agents:

1. **Research Agent** - Gathers information
2. **Analysis Agent** - Analyzes findings
3. **Report Agent** - Generates final report

## Setup

```python
from openintent import OpenIntentClient
from openintent.agents import Agent, on_assignment, Coordinator, IntentSpec, PortfolioSpec

# Each agent connects to the same server
OPENINTENT_URL = "http://localhost:8000"
```

## Research Agent

```python
@Agent("research-agent")
class ResearchAgent:
    
    @on_assignment
    async def handle(self, intent):
        # Simulate research
        findings = self.do_research(intent.description)
        
        return {
            "status": "researched",
            "findings": findings,
            "sources": 5
        }
    
    def do_research(self, topic):
        return f"Research findings about {topic}"
```

## Analysis Agent

```python
@Agent("analysis-agent")
class AnalysisAgent:
    
    @on_assignment
    async def handle(self, intent):
        # Get research findings from state
        findings = intent.state.get("findings", "")
        
        # Analyze
        analysis = self.analyze(findings)
        
        return {
            "status": "analyzed",
            "analysis": analysis
        }
    
    def analyze(self, findings):
        return f"Analysis of: {findings}"
```

## Report Agent

```python
@Agent("report-agent")
class ReportAgent:
    
    @on_assignment
    async def handle(self, intent):
        analysis = intent.state.get("analysis", "")
        
        report = f"# Report\n\n{analysis}"
        
        return {
            "status": "complete",
            "report": report
        }
```

## Coordinator

```python
# Define the workflow
workflow = PortfolioSpec(
    name="Research Pipeline",
    intents=[
        IntentSpec(
            title="Gather Research",
            assign="research-agent"
        ),
        IntentSpec(
            title="Analyze Findings",
            assign="analysis-agent",
            depends_on=["Gather Research"]
        ),
        IntentSpec(
            title="Generate Report",
            assign="report-agent",
            depends_on=["Analyze Findings"]
        )
    ]
)

@Coordinator("coordinator")
class PipelineCoordinator:
    
    @on_all_complete
    async def finished(self, portfolio):
        print("Pipeline complete!")
        print(f"Report: {portfolio.intents[-1].state.get('report')}")
```

## Running the Example

```python
import asyncio

async def main():
    # Start agents (in separate processes or threads)
    research = ResearchAgent()
    analysis = AnalysisAgent()
    report = ReportAgent()
    coordinator = PipelineCoordinator()
    
    # Run coordinator with workflow
    await coordinator.run_portfolio(workflow)

asyncio.run(main())
```

## Using the Demo

The SDK includes a working demo:

```bash
# Run with mock LLM responses
openintent demo

# Run with real LLM
OPENAI_API_KEY=sk-... openintent demo
```
