import type { MCPConfig, MCPRole } from "./config.js";
import { VALID_ROLES } from "./config.js";

export interface AuditEntry {
  timestamp: string;
  operation: string;
  params: Record<string, unknown>;
  result: "success" | "error";
  duration_ms: number;
  agent_id: string;
}

const SENSITIVE_KEYS = new Set(["api_key", "password", "secret", "token", "authorization"]);

/**
 * Tool permission tiers.
 *
 * Each tool belongs to exactly one tier. Tiers are cumulative — higher roles
 * inherit all tools from lower tiers.
 *
 *   read   — Observe protocol state without side effects.
 *   write  — Progress work within an intent (create content, send messages).
 *   admin  — Lifecycle control, coordination primitives, structural changes.
 */
export type ToolTier = "read" | "write" | "admin";

export const TOOL_TIERS: Record<string, ToolTier> = {
  // ── Participation Tools (16) ──────────────────────────────────────
  openintent_get_intent:    "read",
  openintent_list_intents:  "read",
  openintent_get_events:    "read",
  openintent_get_messages:  "read",

  openintent_create_intent: "write",
  openintent_update_state:  "write",
  openintent_log_event:     "write",
  openintent_send_message:  "write",
  openintent_ask:           "write",
  openintent_broadcast:     "write",

  openintent_set_status:      "admin",
  openintent_acquire_lease:   "admin",
  openintent_release_lease:   "admin",
  openintent_assign_agent:    "admin",
  openintent_unassign_agent:  "admin",
  openintent_create_channel:  "admin",

  // ── Advanced Tools (37) ───────────────────────────────────────────

  // Workflows (RFC-0011)
  openintent_get_workflow:     "read",
  openintent_list_workflows:   "read",
  openintent_create_workflow:  "write",
  openintent_trigger_workflow: "admin",

  // Plans & Task Decomposition (RFC-0012)
  openintent_get_plan:         "read",
  openintent_create_plan:      "write",
  openintent_decompose_task:   "write",

  // Coordinator Governance (RFC-0013)
  openintent_get_arbitration:  "read",
  openintent_set_coordinator:  "admin",
  openintent_record_decision:  "admin",

  // Human Escalation (RFC-0013)
  openintent_escalate_to_human:  "write",
  openintent_list_escalations:   "read",
  openintent_resolve_escalation: "admin",
  openintent_request_approval:   "write",
  openintent_get_approval_status: "read",

  // Portfolios (RFC-0004)
  openintent_get_portfolio:      "read",
  openintent_create_portfolio:   "write",
  openintent_add_to_portfolio:   "write",

  // Access Control (RFC-0011)
  openintent_get_permissions:  "read",
  openintent_set_permissions:  "admin",
  openintent_grant_access:     "admin",

  // Credential Vaults (RFC-0014)
  openintent_store_credential: "admin",
  openintent_get_credential:   "admin",
  openintent_grant_tool:       "admin",

  // Agent Memory (RFC-0015)
  openintent_memory_get:  "read",
  openintent_memory_list: "read",
  openintent_memory_set:  "write",

  // Agent Lifecycle (RFC-0016)
  openintent_get_health:        "read",
  openintent_heartbeat:         "write",
  openintent_set_agent_status:  "admin",

  // Triggers (RFC-0017)
  openintent_list_triggers:   "read",
  openintent_create_trigger:  "admin",
  openintent_delete_trigger:  "admin",

  // Cryptographic Identity (RFC-0018)
  openintent_register_identity:  "admin",
  openintent_verify_challenge:   "admin",
  openintent_rotate_key:         "admin",

  // Verifiable Event Logs (RFC-0019)
  openintent_get_hash_chain:     "read",
  openintent_verify_inclusion:   "read",
  openintent_get_checkpoint:     "read",

  // Distributed Tracing (RFC-0020)
  openintent_get_trace:    "read",
  openintent_start_trace:  "write",
  openintent_link_spans:   "write",
};

const TIER_ORDER: ToolTier[] = ["read", "write", "admin"];

/**
 * Map each role to the set of tiers it grants access to.
 *
 *   reader   → read
 *   operator → read + write
 *   admin    → read + write + admin
 */
export const ROLE_TIERS: Record<MCPRole, Set<ToolTier>> = {
  reader:   new Set(["read"]),
  operator: new Set(["read", "write"]),
  admin:    new Set(["read", "write", "admin"]),
};

export function getToolTier(toolName: string): ToolTier | undefined {
  return TOOL_TIERS[toolName];
}

export function getTiersForRole(role: MCPRole): Set<ToolTier> {
  return ROLE_TIERS[role] ?? ROLE_TIERS["reader"];
}

export function getToolsForRole(role: MCPRole): string[] {
  const allowedTiers = getTiersForRole(role);
  return Object.entries(TOOL_TIERS)
    .filter(([, tier]) => allowedTiers.has(tier))
    .map(([name]) => name);
}

/**
 * Check whether a tool is permitted by the configured role.
 * Returns `true` if the tool's tier is within the role's granted tiers.
 * Unknown tools are denied by default.
 */
export function checkToolAllowedByRole(toolName: string, config: MCPConfig): boolean {
  const tier = getToolTier(toolName);
  if (!tier) return false;
  const allowedTiers = getTiersForRole(config.security.role);
  return allowedTiers.has(tier);
}

/**
 * Check whether a tool name is permitted by the explicit allowlist.
 * Returns `true` if the tool is allowed, `false` otherwise.
 */
export function checkToolAllowed(toolName: string, config: MCPConfig): boolean {
  if (config.security.allowed_tools === null) {
    return true;
  }
  return config.security.allowed_tools.includes(toolName);
}

/**
 * Combined check: a tool must pass BOTH the role gate AND the allowlist.
 * Returns an object with allowed status and a reason string for denials.
 */
export function isToolPermitted(
  toolName: string,
  config: MCPConfig,
): { allowed: boolean; reason?: string } {
  if (!checkToolAllowedByRole(toolName, config)) {
    const tier = getToolTier(toolName) ?? "unknown";
    return {
      allowed: false,
      reason:
        `Tool "${toolName}" requires "${tier}" permission but the current role ` +
        `"${config.security.role}" does not grant it. ` +
        `Upgrade to a role that includes the "${tier}" tier ` +
        `(${TIER_ORDER.filter((t) => TIER_ORDER.indexOf(t) >= TIER_ORDER.indexOf(tier as ToolTier)).join(", ")}).`,
    };
  }
  if (!checkToolAllowed(toolName, config)) {
    return {
      allowed: false,
      reason: `Tool "${toolName}" is not in the allowed_tools list.`,
    };
  }
  return { allowed: true };
}

/**
 * Return the list of tool names visible to the current configuration.
 * A tool is visible only if it passes both the role gate and the allowlist.
 */
export function getVisibleTools(config: MCPConfig): Set<string> {
  const roleTools = getToolsForRole(config.security.role);
  if (config.security.allowed_tools === null) {
    return new Set(roleTools);
  }
  const allowSet = new Set(config.security.allowed_tools);
  return new Set(roleTools.filter((t) => allowSet.has(t)));
}

/**
 * Validate the loaded configuration, emitting warnings to stderr for
 * potentially dangerous settings (e.g. TLS not required on a non-localhost URL).
 */
export function validateConfig(config: MCPConfig): string[] {
  const warnings: string[] = [];

  if (!config.server.api_key) {
    warnings.push("OPENINTENT_API_KEY is not set – requests will fail authentication.");
  }

  const url = config.server.url;
  const isLocal = url.includes("localhost") || url.includes("127.0.0.1");
  if (!config.security.tls_required && !isLocal) {
    warnings.push(
      `TLS is not required but server URL "${url}" is not localhost. ` +
        "Set security.tls_required = true for production deployments.",
    );
  }

  if (config.security.max_timeout > 300) {
    warnings.push(
      `max_timeout is ${config.security.max_timeout}s which exceeds the recommended 300s limit.`,
    );
  }

  if (!VALID_ROLES.includes(config.security.role)) {
    warnings.push(
      `Unknown role "${config.security.role}". Valid roles: ${VALID_ROLES.join(", ")}. Falling back to "reader".`,
    );
    config.security.role = "reader";
  }

  if (config.security.role === "admin") {
    warnings.push(
      'Role is set to "admin" which grants access to all tools including lifecycle ' +
        "and coordination primitives. Use this only for trusted orchestrators.",
    );
  }

  return warnings;
}

/**
 * Remove sensitive fields from a params object before writing to audit logs.
 */
export function sanitizeForAudit(
  operation: string,
  params: Record<string, unknown>,
): Record<string, unknown> {
  const sanitized: Record<string, unknown> = { _operation: operation };
  for (const [key, value] of Object.entries(params)) {
    if (SENSITIVE_KEYS.has(key.toLowerCase())) {
      sanitized[key] = "[REDACTED]";
    } else if (typeof value === "object" && value !== null && !Array.isArray(value)) {
      sanitized[key] = sanitizeForAudit("", value as Record<string, unknown>);
    } else {
      sanitized[key] = value;
    }
  }
  return sanitized;
}

/**
 * Enforce TLS transport requirements. Throws if a non-HTTPS URL is used
 * when `tls_required` is enabled.
 */
export function enforceTransport(url: string, config: MCPConfig): void {
  if (config.security.tls_required && !url.startsWith("https://")) {
    throw new Error(
      `TLS is required but the server URL "${url}" does not use HTTPS. ` +
        "Set security.tls_required to false or use an HTTPS endpoint.",
    );
  }
}

/**
 * Build a structured audit log entry.
 */
export function createAuditEntry(
  operation: string,
  params: Record<string, unknown>,
  result: "success" | "error",
  duration: number,
  agentId: string,
): AuditEntry {
  return {
    timestamp: new Date().toISOString(),
    operation,
    params: sanitizeForAudit(operation, params),
    result,
    duration_ms: Math.round(duration),
    agent_id: agentId,
  };
}
