#!/usr/bin/env node

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  ListToolsRequestSchema,
  CallToolRequestSchema,
  ListResourceTemplatesRequestSchema,
  ReadResourceRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";

import { loadConfig } from "./config.js";
import { validateConfig, getVisibleTools } from "./security.js";
import { OpenIntentClient } from "./client.js";
import { TOOL_DEFINITIONS, handleToolCall } from "./tools.js";
import { RESOURCE_TEMPLATES, handleReadResource } from "./resources.js";

async function main() {
  const config = loadConfig();

  const warnings = validateConfig(config);
  for (const w of warnings) {
    process.stderr.write(`[openintent-mcp] WARNING: ${w}\n`);
  }

  const visibleTools = getVisibleTools(config);

  const apiClient = new OpenIntentClient(config);

  const server = new Server(
    {
      name: "openintent-mcp",
      version: "0.14.0",
    },
    {
      capabilities: {
        tools: {},
        resources: {},
      },
    },
  );

  server.setRequestHandler(ListToolsRequestSchema, async () => ({
    tools: TOOL_DEFINITIONS
      .filter((t) => visibleTools.has(t.name))
      .map((t) => ({
        name: t.name,
        description: t.description,
        inputSchema: t.inputSchema,
      })),
  }));

  server.setRequestHandler(CallToolRequestSchema, async (request: { params: { name: string; arguments?: Record<string, unknown> } }) => {
    const { name, arguments: args } = request.params;
    return handleToolCall(name, (args ?? {}) as Record<string, unknown>, apiClient, config);
  });

  server.setRequestHandler(ListResourceTemplatesRequestSchema, async () => ({
    resourceTemplates: RESOURCE_TEMPLATES.map((r) => ({
      uriTemplate: r.uriTemplate,
      name: r.name,
      description: r.description,
      mimeType: r.mimeType,
    })),
  }));

  server.setRequestHandler(ReadResourceRequestSchema, async (request: { params: { uri: string } }) => {
    return handleReadResource(request.params.uri, apiClient);
  });

  const transport = new StdioServerTransport();
  await server.connect(transport);

  const toolCount = visibleTools.size;
  const totalCount = TOOL_DEFINITIONS.length;
  process.stderr.write(
    `[openintent-mcp] Server started – role="${config.security.role}", ` +
    `tools=${toolCount}/${totalCount}, connected to ${config.server.url}\n`,
  );
}

main().catch((err) => {
  process.stderr.write(`[openintent-mcp] Fatal error: ${err}\n`);
  process.exit(1);
});
