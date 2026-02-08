"""
Built-in demo agents for quick-start workflows.

These agents auto-configure from environment variables and provide
ready-to-use functionality for common tasks. They work out-of-box
with sample workflows.

Usage:
    # Run all demo agents
    from openintent.demo_agents import start_demo_agents
    start_demo_agents()

    # Or run individual agents
    from openintent.demo_agents import ResearcherAgent, SummarizerAgent
    ResearcherAgent.run()

Note: Requires LLM provider SDK. Install with:
    pip install openintent[openai]     # For OpenAI
    pip install openintent[anthropic]  # For Anthropic
"""

import os
from typing import Any, Optional


def get_llm_client(provider: str = "auto") -> tuple[Any, str, str]:
    """
    Get an LLM client based on provider or auto-detect from env vars.

    Supports: openai, anthropic, auto (detect from env)
    Returns tuple of (client, model_name, provider_name)
    """
    if provider == "auto":
        if os.getenv("ANTHROPIC_API_KEY"):
            provider = "anthropic"
        elif os.getenv("OPENAI_API_KEY"):
            provider = "openai"
        else:
            raise EnvironmentError(
                "No LLM API key found. Set OPENAI_API_KEY or ANTHROPIC_API_KEY"
            )

    if provider == "anthropic":
        try:
            import anthropic

            client = anthropic.Anthropic()
            return client, "claude-sonnet-4-20250514", "anthropic"
        except ImportError:
            raise ImportError("Install anthropic: pip install anthropic")

    elif provider == "openai":
        try:
            from openai import OpenAI

            client = OpenAI()
            return client, "gpt-4o", "openai"
        except ImportError:
            raise ImportError("Install openai: pip install openai")

    else:
        raise ValueError(f"Unknown provider: {provider}")


def call_llm(
    client: Any,
    model: str,
    provider: str,
    messages: list[dict[str, Any]],
    **kwargs: Any,
) -> str:
    """Call the LLM with the appropriate API."""
    if provider == "anthropic":
        system = next((m["content"] for m in messages if m["role"] == "system"), "")
        user_messages = [m for m in messages if m["role"] != "system"]
        response = client.messages.create(
            model=model,
            max_tokens=kwargs.get("max_tokens", 4096),
            system=system,
            messages=user_messages,
        )
        return str(response.content[0].text)

    else:  # openai
        response = client.chat.completions.create(
            model=model, messages=messages, **kwargs
        )
        return str(response.choices[0].message.content)


class DemoAgent:
    """Base class for demo agents with LLM integration."""

    agent_id: str = "demo-agent"
    system_prompt: str = "You are a helpful assistant."

    def __init__(self, provider: str = "auto") -> None:
        self.client, self.model, self.provider = get_llm_client(provider)
        self.base_url = os.getenv("OPENINTENT_URL", "http://localhost:8000")
        self.api_key = os.getenv("OPENINTENT_API_KEY", "demo-agent-key")

    def call(self, user_prompt: str, **kwargs: Any) -> str:
        """Call the LLM with the system prompt and user prompt."""
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        return call_llm(self.client, self.model, self.provider, messages, **kwargs)

    async def handle_intent(self, intent: Any) -> dict[str, Any]:
        """Override this to handle assigned intents."""
        raise NotImplementedError

    @classmethod
    def run(cls, provider: str = "auto", base_url: Optional[str] = None) -> None:
        """Run this agent, subscribing to intents."""
        from openintent.agents import Agent, on_assignment

        instance = cls(provider=provider)

        @Agent(cls.agent_id)
        class WrappedAgent:
            @on_assignment
            async def work(self, intent: Any) -> dict[str, Any]:
                return await instance.handle_intent(intent)

        WrappedAgent.run(  # type: ignore[attr-defined]
            base_url=base_url or instance.base_url,
            api_key=instance.api_key,
        )


class ResearcherAgent(DemoAgent):
    """
    A research agent that gathers information on a topic.

    Handles intents assigned to: researcher, research-agent
    """

    agent_id = "researcher"
    system_prompt = """You are a thorough research assistant. When given a topic:
1. Identify key aspects and subtopics
2. Provide factual, well-organized information
3. Note any important caveats or areas of uncertainty
4. Structure your response with clear sections

Be concise but comprehensive. Focus on accuracy and clarity."""

    async def handle_intent(self, intent: Any) -> dict[str, Any]:
        topic = intent.description or intent.title
        constraints = "\n".join(intent.constraints) if intent.constraints else ""

        prompt = f"Research the following topic:\n\n{topic}"
        if constraints:
            prompt += f"\n\nConstraints:\n{constraints}"

        findings = self.call(prompt)

        return {
            "status": "complete",
            "findings": findings,
            "source": self.agent_id,
            "model": self.model,
        }


class SummarizerAgent(DemoAgent):
    """
    A summarizer agent that synthesizes information.

    Handles intents assigned to: summarizer, synthesis-agent
    """

    agent_id = "summarizer"
    system_prompt = """You are an expert at synthesizing information. When given research or data:
1. Identify the key themes and insights
2. Create a clear, actionable summary
3. Highlight the most important points
4. Organize information logically

Be concise. Focus on the essential takeaways."""

    async def handle_intent(self, intent: Any) -> dict[str, Any]:
        state = intent.state or {}
        findings = state.get("findings", intent.description or intent.title)

        prompt = f"Summarize the following:\n\n{findings}"

        summary = self.call(prompt)

        return {
            "status": "complete",
            "summary": summary,
            "source": self.agent_id,
            "model": self.model,
        }


class WriterAgent(DemoAgent):
    """
    A writer agent that creates content.

    Handles intents assigned to: writer, content-agent
    """

    agent_id = "writer"
    system_prompt = """You are a skilled content writer. When given a writing task:
1. Understand the purpose and audience
2. Create clear, engaging content
3. Use appropriate tone and style
4. Structure content for readability

Focus on quality and clarity."""

    async def handle_intent(self, intent: Any) -> dict[str, Any]:
        task = intent.description or intent.title
        state = intent.state or {}
        context = state.get("research", state.get("findings", ""))

        prompt = f"Write content for: {task}"
        if context:
            prompt += f"\n\nBackground information:\n{context}"

        content = self.call(prompt)

        return {
            "status": "complete",
            "content": content,
            "source": self.agent_id,
            "model": self.model,
        }


class AnalyzerAgent(DemoAgent):
    """
    An analyzer agent that examines data and provides insights.

    Handles intents assigned to: analyzer, analysis-agent
    """

    agent_id = "analyzer"
    system_prompt = """You are a data analyst. When given data or information:
1. Identify patterns and trends
2. Provide actionable insights
3. Note any anomalies or concerns
4. Make data-driven recommendations

Be analytical and precise."""

    async def handle_intent(self, intent: Any) -> dict[str, Any]:
        data = (
            intent.state.get("data", intent.description)
            if intent.state
            else intent.description
        )

        prompt = f"Analyze the following:\n\n{data}"

        analysis = self.call(prompt)

        return {
            "status": "complete",
            "analysis": analysis,
            "source": self.agent_id,
            "model": self.model,
        }


DEMO_AGENTS = {
    "researcher": ResearcherAgent,
    "research-agent": ResearcherAgent,
    "summarizer": SummarizerAgent,
    "synthesis-agent": SummarizerAgent,
    "writer": WriterAgent,
    "content-agent": WriterAgent,
    "analyzer": AnalyzerAgent,
    "analysis-agent": AnalyzerAgent,
}


def start_demo_agents(
    agent_ids: Optional[list[str]] = None,
    provider: str = "auto",
    base_url: Optional[str] = None,
) -> None:
    """
    Start demo agents in the background.

    Args:
        agent_ids: List of agent IDs to start (None = all)
        provider: LLM provider (openai, anthropic, auto)
        base_url: OpenIntent server URL
    """
    import threading

    if agent_ids is None:
        agent_ids = ["researcher", "summarizer", "writer", "analyzer"]

    for agent_id in agent_ids:
        agent_cls = DEMO_AGENTS.get(agent_id)
        if agent_cls:
            thread = threading.Thread(
                target=agent_cls.run,
                kwargs={"provider": provider, "base_url": base_url},
                daemon=True,
            )
            thread.start()
            print(f"Started {agent_id} agent")


def get_required_agents(workflow_path: str) -> list[str]:
    """Get list of agent IDs required by a workflow."""
    from openintent.workflow import WorkflowSpec

    spec = WorkflowSpec.from_yaml(workflow_path)
    return list(set(phase.assign for phase in spec.phases))
