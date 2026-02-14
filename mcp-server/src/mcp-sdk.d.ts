declare module "@modelcontextprotocol/sdk/server/index.js" {
  export class Server {
    constructor(
      info: { name: string; version: string },
      options: { capabilities: { tools?: Record<string, unknown>; resources?: Record<string, unknown> } },
    );
    setRequestHandler<T = unknown>(schema: unknown, handler: (request: T) => Promise<unknown>): void;
    connect(transport: unknown): Promise<void>;
  }
}

declare module "@modelcontextprotocol/sdk/server/stdio.js" {
  export class StdioServerTransport {}
}

declare module "@modelcontextprotocol/sdk/types.js" {
  export const ListToolsRequestSchema: unknown;
  export const CallToolRequestSchema: unknown;
  export const ListResourceTemplatesRequestSchema: unknown;
  export const ReadResourceRequestSchema: unknown;
}
