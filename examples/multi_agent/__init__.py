"""Multi-agent coordination example using OpenIntent high-level SDK.

This example demonstrates how to coordinate AI agents from different providers
(OpenAI GPT-4 and Anthropic Claude) using the OpenIntent SDK's high-level
abstractions.

Components:
- coordinator.py: Orchestrates workflow using Coordinator class with PortfolioSpec
- research_agent.py: Research agent using @Agent decorator with GPT-4
- writing_agent.py: Writing agent using @Agent decorator with Claude
- config.py: Simple configuration constants

The high-level SDK provides:
- @Agent decorator for minimal-boilerplate agent creation
- Coordinator class for declarative workflow orchestration
- Automatic SSE subscriptions for real-time event handling
- Auto-patching of intent state from handler return values
- LLM adapters for automatic request/response logging
"""
