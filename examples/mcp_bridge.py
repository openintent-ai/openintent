#!/usr/bin/env python3
"""
MCP Bridge Example
==================

Demonstrates how OpenIntent agents consume external MCP tool servers.
The bridge connects to MCP servers via stdio transport, lists their tools,
and invokes them as part of an OpenIntent workflow.

Prerequisites:
    pip install openintent mcp
    npm install -g @modelcontextprotocol/server-filesystem

Usage:
    python mcp_bridge.py
"""

import asyncio

import yaml

from openintent.mcp import MCPBridge, MCPSecurityConfig, MCPServerConfig


async def basic_bridge():
    """Connect to a filesystem MCP server and invoke tools."""
    config = MCPServerConfig(
        name="filesystem",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
        allowed_tools=["read_file", "list_directory"],
        security=MCPSecurityConfig(audit=True),
    )

    bridge = MCPBridge()
    bridge.add_server(config)

    await bridge.connect_all()

    all_tools = await bridge.list_all_tools()
    print("Connected MCP servers and tools:")
    for server_name, tools in all_tools.items():
        for tool in tools:
            print(f"  {server_name}/{tool['name']}: {tool['description']}")

    result = await bridge.invoke(
        "filesystem",
        "list_directory",
        {"path": "/tmp"},
    )
    print("\nDirectory listing result:")
    for content in result["content"]:
        print(f"  {content['text'][:200]}")

    await bridge.disconnect_all()


async def from_yaml_config():
    """Create a bridge from a YAML mcp: block."""
    yaml_content = """
mcp:
  servers:
    filesystem:
      command: "npx"
      args: ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
      allowed_tools: ["read_file", "list_directory"]
      security:
        audit: true
        credential_isolation: true
"""
    config = yaml.safe_load(yaml_content)
    bridge = MCPBridge.from_yaml(config["mcp"])

    await bridge.connect_all()

    tools = await bridge.list_all_tools()
    print("\nTools from YAML-configured bridge:")
    for server_name, server_tools in tools.items():
        print(f"  {server_name}: {[t['name'] for t in server_tools]}")

    await bridge.disconnect_all()


async def multi_server_bridge():
    """Connect to multiple MCP servers simultaneously."""
    filesystem_config = MCPServerConfig(
        name="filesystem",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
        allowed_tools=["read_file", "list_directory"],
        security=MCPSecurityConfig(audit=True),
    )

    openintent_config = MCPServerConfig(
        name="openintent-remote",
        command="npx",
        args=["-y", "@openintent/mcp-server"],
        env={
            "OPENINTENT_SERVER_URL": "http://localhost:8000",
            "OPENINTENT_API_KEY": "${OPENINTENT_API_KEY}",
        },
        security=MCPSecurityConfig(
            credential_isolation=True,
            audit=True,
        ),
    )

    bridge = MCPBridge()
    bridge.add_server(filesystem_config)
    bridge.add_server(openintent_config)

    await bridge.connect_all()

    all_tools = await bridge.list_all_tools()
    total = sum(len(tools) for tools in all_tools.values())
    print(f"\nConnected to {len(all_tools)} servers with {total} total tools")

    for server_name, tools in all_tools.items():
        print(f"\n  {server_name}:")
        for tool in tools:
            print(f"    - {tool['name']}")

    await bridge.disconnect_all()


async def main():
    print("=" * 60)
    print("MCP Bridge Example")
    print("=" * 60)

    print("\n--- Basic Bridge ---")
    await basic_bridge()

    print("\n--- YAML Configuration ---")
    await from_yaml_config()

    print("\n--- Multi-Server Bridge ---")
    await multi_server_bridge()

    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
