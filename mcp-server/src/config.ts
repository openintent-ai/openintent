import { readFileSync } from "fs";

export type MCPRole = "reader" | "operator" | "admin";

export const VALID_ROLES: MCPRole[] = ["reader", "operator", "admin"];

export interface ServerConfig {
  url: string;
  api_key: string;
  agent_id: string;
}

export interface SecurityConfig {
  tls_required: boolean;
  allowed_tools: string[] | null;
  role: MCPRole;
  max_timeout: number;
  audit_logging: boolean;
}

export interface NetworkConfig {
  timeout: number;
  retries: number;
  retry_delay: number;
}

export interface MCPConfig {
  server: ServerConfig;
  security: SecurityConfig;
  network: NetworkConfig;
}

function loadFileConfig(path: string): Partial<MCPConfig> {
  try {
    const raw = readFileSync(path, "utf-8");
    return JSON.parse(raw) as Partial<MCPConfig>;
  } catch {
    return {};
  }
}

function deepMerge(base: MCPConfig, override: Partial<MCPConfig>): MCPConfig {
  const result: Record<string, unknown> = { ...base };
  for (const key of Object.keys(override)) {
    const val = (override as Record<string, unknown>)[key];
    if (val !== undefined && val !== null && typeof val === "object" && !Array.isArray(val)) {
      result[key] = {
        ...((result[key] as Record<string, unknown>) ?? {}),
        ...(val as Record<string, unknown>),
      };
    } else if (val !== undefined) {
      result[key] = val;
    }
  }
  return result as unknown as MCPConfig;
}

/**
 * Validate and normalise an MCP role string.  Returns a valid
 * {@link MCPRole} or falls back to ``"reader"`` (least privilege)
 * when the value is unrecognised.
 */
function validateRole(raw: string, source: string): MCPRole {
  const normalised = raw.trim().toLowerCase();
  if (VALID_ROLES.includes(normalised as MCPRole)) {
    if (normalised === "admin") {
      console.warn(
        `[openintent-mcp] WARNING: role "${normalised}" (from ${source}) ` +
        `grants full access — ensure this is intentional.`
      );
    }
    return normalised as MCPRole;
  }
  console.warn(
    `[openintent-mcp] WARNING: unknown role "${raw}" (from ${source}), ` +
    `falling back to "reader" (least privilege).`
  );
  return "reader";
}

/**
 * Load MCP server configuration.
 *
 * Precedence for the security role (highest → lowest):
 *   1. ``OPENINTENT_MCP_ROLE`` env var  — explicit per-process override
 *   2. ``security.role`` in config file — explicit file config
 *   3. Built-in default                 — ``"reader"`` (least privilege)
 *
 * The env var takes precedence because the SDK's {@link MCPTool} sets it
 * explicitly on each child process, giving every agent its own isolated
 * role without ambient env leaking upward.  When running standalone
 * (e.g. Claude Desktop) the env var is the primary configuration knob.
 *
 * Connection-related env vars (URL, API key, agent ID) always override
 * file config for convenience.
 */
export function loadConfig(): MCPConfig {
  const defaults: MCPConfig = {
    server: {
      url: "http://localhost:8000",
      api_key: "",
      agent_id: "mcp-agent",
    },
    security: {
      tls_required: false,
      allowed_tools: null,
      role: "reader",
      max_timeout: 120,
      audit_logging: true,
    },
    network: {
      timeout: 30_000,
      retries: 3,
      retry_delay: 1_000,
    },
  };

  const configPath = process.env.OPENINTENT_MCP_CONFIG;
  const fileConfig = configPath ? loadFileConfig(configPath) : {};

  const config = deepMerge(defaults, fileConfig);

  if (process.env.OPENINTENT_SERVER_URL) {
    config.server.url = process.env.OPENINTENT_SERVER_URL;
  }
  if (process.env.OPENINTENT_API_KEY) {
    config.server.api_key = process.env.OPENINTENT_API_KEY;
  }
  if (process.env.OPENINTENT_AGENT_ID) {
    config.server.agent_id = process.env.OPENINTENT_AGENT_ID;
  }

  if (process.env.OPENINTENT_MCP_ROLE) {
    config.security.role = validateRole(
      process.env.OPENINTENT_MCP_ROLE, "OPENINTENT_MCP_ROLE env var"
    );
  } else if (fileConfig.security?.role) {
    config.security.role = validateRole(
      fileConfig.security.role, "config file"
    );
  }

  return config;
}
