#!/usr/bin/env python3
"""
Agent that uses MCPTool to automatically discover and invoke
OpenIntent tools through the MCP server.

Prerequisites:
    pip install openintent[openai] mcp
    npm install -g @openintentai/mcp-server

Usage:
    # Terminal 1: Start the OpenIntent server
    openintent-server

    # Terminal 2: Run this agent
    export OPENAI_API_KEY=sk-...
    python examples/mcp_agent.py
"""

from openintent import Agent, MCPTool, on_assignment


@Agent(
    "mcp-analyst",
    model="gpt-4o",
    tools=[
        MCPTool(
            server="npx",
            args=["-y", "@openintentai/mcp-server"],
            role="operator",
            env={"OPENINTENT_SERVER_URL": "http://localhost:8000"},
        ),
    ],
)
class MCPAnalyst:
    """An agent that can read and write OpenIntent data via MCP tools.

    At startup the SDK connects to the MCP server, discovers the tools
    the 'operator' role permits (10 tools), and registers them so the
    LLM can call them during self.think().
    """

    @on_assignment
    async def work(self, intent):
        return await self.think(
            f"You have access to OpenIntent tools via MCP. "
            f"Use them to analyze and update the intent: {intent.description}"
        )


if __name__ == "__main__":
    MCPAnalyst.run()
