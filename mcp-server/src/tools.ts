import type { OpenIntentClient } from "./client.js";
import type { MCPConfig } from "./config.js";
import type { ToolTier } from "./security.js";
import { isToolPermitted, TOOL_TIERS } from "./security.js";

export interface ToolDefinition {
  name: string;
  description: string;
  inputSchema: Record<string, unknown>;
  tier: ToolTier;
}

function textResult(data: unknown) {
  return {
    content: [{ type: "text" as const, text: JSON.stringify(data, null, 2) }],
  };
}

function errorResult(message: string) {
  return {
    content: [{ type: "text" as const, text: JSON.stringify({ error: message }, null, 2) }],
    isError: true,
  };
}

export const TOOL_DEFINITIONS: ToolDefinition[] = [
  // ── Intent Management ────────────────────────────────────────────────
  {
    name: "openintent_create_intent",
    description:
      "Create a new intent representing a goal to be coordinated across agents. " +
      "Use this when you need to start a new task, project, or coordination workflow.",
    inputSchema: {
      type: "object",
      properties: {
        title: { type: "string", description: "Human-readable title for the intent" },
        description: { type: "string", description: "Detailed description of the goal" },
        constraints: {
          type: "array",
          items: { type: "string" },
          description: "Optional constraints or rules the intent must satisfy",
        },
        initial_state: {
          type: "object",
          description: "Optional initial key-value state data",
          additionalProperties: true,
        },
      },
      required: ["title"],
    },
    tier: "write",
  },
  {
    name: "openintent_get_intent",
    description:
      "Retrieve an intent by its unique ID. Returns the full intent including " +
      "status, state, version, constraints, and metadata.",
    inputSchema: {
      type: "object",
      properties: {
        intent_id: { type: "string", description: "The unique identifier of the intent" },
      },
      required: ["intent_id"],
    },
    tier: "read",
  },
  {
    name: "openintent_list_intents",
    description:
      "List intents with optional filtering by status. Useful for discovering " +
      "active work, reviewing completed tasks, or finding blocked intents.",
    inputSchema: {
      type: "object",
      properties: {
        status: {
          type: "string",
          enum: ["draft", "active", "blocked", "completed", "abandoned"],
          description: "Filter intents by status",
        },
        limit: { type: "number", description: "Maximum number of results (default 50)" },
        offset: { type: "number", description: "Pagination offset (default 0)" },
      },
    },
    tier: "read",
  },
  {
    name: "openintent_update_state",
    description:
      "Patch the intent's state with new key-value data. Uses optimistic concurrency " +
      "control via version numbers to prevent conflicting updates. You must provide " +
      "the current version obtained from get_intent.",
    inputSchema: {
      type: "object",
      properties: {
        intent_id: { type: "string", description: "The intent to update" },
        version: {
          type: "number",
          description: "Current version of the intent (for conflict detection)",
        },
        state_patch: {
          type: "object",
          description: "Key-value pairs to merge into the intent state",
          additionalProperties: true,
        },
      },
      required: ["intent_id", "version", "state_patch"],
    },
    tier: "write",
  },
  {
    name: "openintent_set_status",
    description:
      "Change the lifecycle status of an intent. Valid transitions: " +
      "draft\u2192active, active\u2192blocked/completed/abandoned, blocked\u2192active.",
    inputSchema: {
      type: "object",
      properties: {
        intent_id: { type: "string", description: "The intent to update" },
        version: { type: "number", description: "Current version for conflict detection" },
        status: {
          type: "string",
          enum: ["draft", "active", "blocked", "completed", "abandoned"],
          description: "New status to set",
        },
      },
      required: ["intent_id", "version", "status"],
    },
    tier: "admin",
  },

  // ── Event Logging ────────────────────────────────────────────────────
  {
    name: "openintent_log_event",
    description:
      "Append an immutable event to an intent's audit log. Events are the " +
      "primary record of all activity and can never be deleted.",
    inputSchema: {
      type: "object",
      properties: {
        intent_id: { type: "string", description: "The intent to log against" },
        event_type: {
          type: "string",
          description:
            "Type of event (e.g. 'comment', 'state_patched', 'agent_assigned')",
        },
        payload: {
          type: "object",
          description: "Event-specific data",
          additionalProperties: true,
        },
      },
      required: ["intent_id", "event_type"],
    },
    tier: "write",
  },
  {
    name: "openintent_get_events",
    description:
      "Retrieve the event history for an intent. The event log is immutable " +
      "and provides a full audit trail of all changes and activities.",
    inputSchema: {
      type: "object",
      properties: {
        intent_id: { type: "string", description: "The intent to query" },
        event_type: { type: "string", description: "Filter by event type" },
        limit: { type: "number", description: "Maximum number of events (default 100)" },
      },
      required: ["intent_id"],
    },
    tier: "read",
  },

  // ── Leasing ──────────────────────────────────────────────────────────
  {
    name: "openintent_acquire_lease",
    description:
      "Acquire an exclusive lease on a scope within an intent. Leases prevent " +
      "concurrent modifications to the same scope by different agents. " +
      "Returns the lease object with its ID and expiration.",
    inputSchema: {
      type: "object",
      properties: {
        intent_id: { type: "string", description: "The intent to lease within" },
        scope: {
          type: "string",
          description: "The scope to acquire (e.g. 'research', 'analysis')",
        },
        duration_seconds: {
          type: "number",
          description: "Lease duration in seconds (default 300)",
        },
      },
      required: ["intent_id", "scope"],
    },
    tier: "admin",
  },
  {
    name: "openintent_release_lease",
    description:
      "Release a previously acquired lease, allowing other agents to acquire it.",
    inputSchema: {
      type: "object",
      properties: {
        intent_id: { type: "string", description: "The intent containing the lease" },
        lease_id: { type: "string", description: "The lease ID to release" },
      },
      required: ["intent_id", "lease_id"],
    },
    tier: "admin",
  },

  // ── Agent Management ─────────────────────────────────────────────────
  {
    name: "openintent_assign_agent",
    description:
      "Assign an agent to work on an intent. Agents can be assigned with " +
      "a role such as 'worker', 'reviewer', or 'coordinator'.",
    inputSchema: {
      type: "object",
      properties: {
        intent_id: { type: "string", description: "The intent to assign to" },
        agent_id: { type: "string", description: "The agent identifier to assign" },
        role: {
          type: "string",
          description: "Agent role (default 'worker')",
        },
      },
      required: ["intent_id", "agent_id"],
    },
    tier: "admin",
  },
  {
    name: "openintent_unassign_agent",
    description: "Remove an agent from an intent assignment.",
    inputSchema: {
      type: "object",
      properties: {
        intent_id: { type: "string", description: "The intent to unassign from" },
        agent_id: { type: "string", description: "The agent identifier to remove" },
      },
      required: ["intent_id", "agent_id"],
    },
    tier: "admin",
  },

  // ── Messaging (RFC-0021) ─────────────────────────────────────────────
  {
    name: "openintent_create_channel",
    description:
      "Create a messaging channel for direct agent-to-agent communication. " +
      "Channels are scoped to an intent and support request/reply, broadcast, " +
      "and point-to-point messaging patterns.",
    inputSchema: {
      type: "object",
      properties: {
        intent_id: { type: "string", description: "The intent to scope the channel to" },
        name: { type: "string", description: "Channel name (e.g. 'data-sync', 'progress')" },
        members: {
          type: "array",
          items: { type: "string" },
          description: "Agent IDs to include in the channel",
        },
        member_policy: {
          type: "string",
          enum: ["explicit", "open"],
          description: "Membership policy (default 'explicit')",
        },
      },
      required: ["intent_id", "name"],
    },
    tier: "admin",
  },
  {
    name: "openintent_send_message",
    description:
      "Send a message on a channel. Messages can be directed to a specific " +
      "agent (point-to-point) or sent without a target for general consumption.",
    inputSchema: {
      type: "object",
      properties: {
        channel_id: { type: "string", description: "The channel to send on" },
        payload: {
          type: "object",
          description: "Message content",
          additionalProperties: true,
        },
        to: { type: "string", description: "Target agent ID for directed messages" },
        message_type: {
          type: "string",
          description: "Message type (default 'message')",
        },
      },
      required: ["channel_id", "payload"],
    },
    tier: "write",
  },
  {
    name: "openintent_ask",
    description:
      "Send a request on a channel and await a correlated response. This implements " +
      "the ask/reply pattern where you send a question to a specific agent and " +
      "wait for their response.",
    inputSchema: {
      type: "object",
      properties: {
        channel_id: { type: "string", description: "The channel to ask on" },
        to: { type: "string", description: "Target agent ID to ask" },
        payload: {
          type: "object",
          description: "Request content",
          additionalProperties: true,
        },
        timeout: {
          type: "number",
          description: "Timeout in seconds to wait for response (default 30)",
        },
      },
      required: ["channel_id", "to", "payload"],
    },
    tier: "write",
  },
  {
    name: "openintent_broadcast",
    description:
      "Broadcast a message to all members of a channel. Useful for status " +
      "updates, progress notifications, or coordination signals.",
    inputSchema: {
      type: "object",
      properties: {
        channel_id: { type: "string", description: "The channel to broadcast on" },
        payload: {
          type: "object",
          description: "Broadcast content",
          additionalProperties: true,
        },
      },
      required: ["channel_id", "payload"],
    },
    tier: "write",
  },
  {
    name: "openintent_get_messages",
    description: "Retrieve messages from a channel, ordered by creation time.",
    inputSchema: {
      type: "object",
      properties: {
        channel_id: { type: "string", description: "The channel to read from" },
        limit: { type: "number", description: "Maximum number of messages to return" },
      },
      required: ["channel_id"],
    },
    tier: "read",
  },

  // ── Workflows (RFC-0011) ──────────────────────────────────────────
  {
    name: "openintent_create_workflow",
    description:
      "Create a new workflow from a YAML specification. Workflows define " +
      "multi-step coordination patterns with agent assignments and dependencies.",
    inputSchema: {
      type: "object",
      properties: {
        name: { type: "string", description: "Human-readable workflow name" },
        yaml_spec: { type: "string", description: "YAML workflow specification" },
        description: { type: "string", description: "Optional workflow description" },
      },
      required: ["name", "yaml_spec"],
    },
    tier: "write" as ToolTier,
  },
  {
    name: "openintent_trigger_workflow",
    description:
      "Trigger execution of a registered workflow. Optionally provide input " +
      "data that will be available to the workflow's agents.",
    inputSchema: {
      type: "object",
      properties: {
        workflow_id: { type: "string", description: "The workflow to trigger" },
        inputs: {
          type: "object",
          description: "Optional input data for the workflow",
          additionalProperties: true,
        },
      },
      required: ["workflow_id"],
    },
    tier: "admin" as ToolTier,
  },
  {
    name: "openintent_get_workflow",
    description: "Retrieve a workflow definition by its ID, including its YAML spec and metadata.",
    inputSchema: {
      type: "object",
      properties: {
        workflow_id: { type: "string", description: "The workflow identifier" },
      },
      required: ["workflow_id"],
    },
    tier: "read" as ToolTier,
  },
  {
    name: "openintent_list_workflows",
    description: "List all registered workflows with optional pagination.",
    inputSchema: {
      type: "object",
      properties: {
        limit: { type: "number", description: "Maximum number of results (default 50)" },
        offset: { type: "number", description: "Pagination offset (default 0)" },
      },
    },
    tier: "read" as ToolTier,
  },

  // ── Plans & Task Decomposition (RFC-0012) ─────────────────────────
  {
    name: "openintent_create_plan",
    description:
      "Create a structured execution plan for an intent. Plans define ordered " +
      "steps with dependencies that agents follow to complete complex tasks.",
    inputSchema: {
      type: "object",
      properties: {
        intent_id: { type: "string", description: "The intent this plan belongs to" },
        title: { type: "string", description: "Plan title" },
        steps: {
          type: "array",
          items: {
            type: "object",
            properties: {
              title: { type: "string" },
              description: { type: "string" },
              depends_on: { type: "array", items: { type: "string" } },
            },
            required: ["title"],
          },
          description: "Ordered list of plan steps with optional dependencies",
        },
      },
      required: ["intent_id", "title", "steps"],
    },
    tier: "write" as ToolTier,
  },
  {
    name: "openintent_decompose_task",
    description:
      "Automatically decompose a high-level task description into a structured " +
      "plan with subtasks and dependencies.",
    inputSchema: {
      type: "object",
      properties: {
        intent_id: { type: "string", description: "The intent context for decomposition" },
        task_description: { type: "string", description: "High-level task to decompose" },
        max_depth: { type: "number", description: "Maximum decomposition depth (default 3)" },
      },
      required: ["intent_id", "task_description"],
    },
    tier: "write" as ToolTier,
  },
  {
    name: "openintent_get_plan",
    description: "Retrieve a plan by ID including all steps and their current status.",
    inputSchema: {
      type: "object",
      properties: {
        intent_id: { type: "string", description: "The intent containing the plan" },
        plan_id: { type: "string", description: "The plan identifier" },
      },
      required: ["intent_id", "plan_id"],
    },
    tier: "read" as ToolTier,
  },

  // ── Coordinator Governance (RFC-0013) ─────────────────────────────
  {
    name: "openintent_set_coordinator",
    description:
      "Assign a coordinator to an intent with an optional governance policy. " +
      "The coordinator oversees agent work and makes arbitration decisions.",
    inputSchema: {
      type: "object",
      properties: {
        intent_id: { type: "string", description: "The intent to coordinate" },
        coordinator_id: { type: "string", description: "Agent ID of the coordinator" },
        governance_policy: {
          type: "string",
          description: "Governance policy name (default 'default')",
        },
      },
      required: ["intent_id", "coordinator_id"],
    },
    tier: "admin" as ToolTier,
  },
  {
    name: "openintent_record_decision",
    description:
      "Record a governance decision made by a coordinator. Decisions are " +
      "immutable and include rationale for auditability.",
    inputSchema: {
      type: "object",
      properties: {
        intent_id: { type: "string", description: "The intent this decision applies to" },
        decision_type: { type: "string", description: "Type of decision (e.g. 'approval', 'rejection', 'escalation')" },
        rationale: { type: "string", description: "Explanation for the decision" },
        outcome: {
          type: "object",
          description: "Structured outcome data",
          additionalProperties: true,
        },
      },
      required: ["intent_id", "decision_type", "rationale", "outcome"],
    },
    tier: "admin" as ToolTier,
  },
  {
    name: "openintent_get_arbitration",
    description: "Retrieve the arbitration history and governance state for an intent.",
    inputSchema: {
      type: "object",
      properties: {
        intent_id: { type: "string", description: "The intent to query" },
      },
      required: ["intent_id"],
    },
    tier: "read" as ToolTier,
  },

  // ── Human Escalation (RFC-0013) ────────────────────────────────────
  {
    name: "openintent_escalate_to_human",
    description:
      "Escalate an intent to a human reviewer when an agent is blocked, " +
      "uncertain, or a decision exceeds its authority. Supports priority " +
      "levels and structured context for the human reviewer.",
    inputSchema: {
      type: "object",
      properties: {
        intent_id: { type: "string", description: "The intent requiring human attention" },
        reason: { type: "string", description: "Why this needs human intervention" },
        priority: {
          type: "string",
          enum: ["low", "normal", "high", "critical"],
          description: "Escalation priority (default: normal)",
        },
        context: {
          type: "object",
          description: "Structured context to help the human reviewer (e.g. options considered, constraints)",
          additionalProperties: true,
        },
      },
      required: ["intent_id", "reason"],
    },
    tier: "write" as ToolTier,
  },
  {
    name: "openintent_list_escalations",
    description:
      "List escalations awaiting human action. Filter by intent or status " +
      "(pending, acknowledged, resolved).",
    inputSchema: {
      type: "object",
      properties: {
        intent_id: { type: "string", description: "Filter to a specific intent" },
        status: {
          type: "string",
          enum: ["pending", "acknowledged", "resolved"],
          description: "Filter by escalation status",
        },
        limit: { type: "number", description: "Max results to return" },
        offset: { type: "number", description: "Pagination offset" },
      },
      required: [],
    },
    tier: "read" as ToolTier,
  },
  {
    name: "openintent_resolve_escalation",
    description:
      "Resolve a pending escalation with a human decision. The resolution " +
      "is recorded immutably for audit and the originating agent is notified.",
    inputSchema: {
      type: "object",
      properties: {
        escalation_id: { type: "string", description: "The escalation to resolve" },
        resolution: {
          type: "string",
          enum: ["approved", "denied", "deferred", "overridden"],
          description: "Resolution outcome",
        },
        decision: {
          type: "object",
          description: "Structured decision data (instructions, constraints, rationale)",
          additionalProperties: true,
        },
      },
      required: ["escalation_id", "resolution", "decision"],
    },
    tier: "admin" as ToolTier,
  },
  {
    name: "openintent_request_approval",
    description:
      "Request explicit human approval before an agent proceeds with an " +
      "action. The agent should poll get_approval_status or wait for a " +
      "notification before continuing.",
    inputSchema: {
      type: "object",
      properties: {
        intent_id: { type: "string", description: "The intent this approval is scoped to" },
        action_description: { type: "string", description: "What the agent wants to do and why approval is needed" },
        urgency: {
          type: "string",
          enum: ["low", "normal", "high", "critical"],
          description: "How urgently approval is needed (default: normal)",
        },
        metadata: {
          type: "object",
          description: "Additional context (estimated cost, risk level, affected resources)",
          additionalProperties: true,
        },
      },
      required: ["intent_id", "action_description"],
    },
    tier: "write" as ToolTier,
  },
  {
    name: "openintent_get_approval_status",
    description:
      "Check the status of a previously submitted approval request. " +
      "Returns pending, approved, or denied with optional reviewer notes.",
    inputSchema: {
      type: "object",
      properties: {
        intent_id: { type: "string", description: "The intent the approval belongs to" },
        approval_id: { type: "string", description: "The approval request ID to check" },
      },
      required: ["intent_id", "approval_id"],
    },
    tier: "read" as ToolTier,
  },

  // ── Portfolios (RFC-0004) ─────────────────────────────────────────
  {
    name: "openintent_create_portfolio",
    description:
      "Create a portfolio to group related intents together. Portfolios " +
      "provide a higher-level view of coordinated work.",
    inputSchema: {
      type: "object",
      properties: {
        name: { type: "string", description: "Portfolio name" },
        description: { type: "string", description: "Optional portfolio description" },
      },
      required: ["name"],
    },
    tier: "write" as ToolTier,
  },
  {
    name: "openintent_add_to_portfolio",
    description: "Add an intent to an existing portfolio.",
    inputSchema: {
      type: "object",
      properties: {
        portfolio_id: { type: "string", description: "The portfolio to add to" },
        intent_id: { type: "string", description: "The intent to include" },
      },
      required: ["portfolio_id", "intent_id"],
    },
    tier: "write" as ToolTier,
  },
  {
    name: "openintent_get_portfolio",
    description: "Retrieve a portfolio and its constituent intents.",
    inputSchema: {
      type: "object",
      properties: {
        portfolio_id: { type: "string", description: "The portfolio identifier" },
      },
      required: ["portfolio_id"],
    },
    tier: "read" as ToolTier,
  },

  // ── Access Control (RFC-0011) ─────────────────────────────────────
  {
    name: "openintent_set_permissions",
    description:
      "Set the permissions configuration for an intent. Uses optimistic " +
      "concurrency control to prevent conflicting permission changes.",
    inputSchema: {
      type: "object",
      properties: {
        intent_id: { type: "string", description: "The intent to configure" },
        permissions: {
          type: "object",
          description: "Permissions configuration (policy, allow, delegate, context)",
          additionalProperties: true,
        },
        version: { type: "number", description: "Current version for conflict detection" },
      },
      required: ["intent_id", "permissions", "version"],
    },
    tier: "admin" as ToolTier,
  },
  {
    name: "openintent_get_permissions",
    description: "Retrieve the current permissions configuration for an intent.",
    inputSchema: {
      type: "object",
      properties: {
        intent_id: { type: "string", description: "The intent to query" },
      },
      required: ["intent_id"],
    },
    tier: "read" as ToolTier,
  },
  {
    name: "openintent_grant_access",
    description:
      "Grant an agent access to an intent with a specific permission level " +
      "and optional scope restrictions.",
    inputSchema: {
      type: "object",
      properties: {
        intent_id: { type: "string", description: "The intent to grant access to" },
        agent_id: { type: "string", description: "The agent to grant access" },
        level: {
          type: "string",
          enum: ["read", "write", "admin"],
          description: "Permission level to grant",
        },
        scopes: {
          type: "array",
          items: { type: "string" },
          description: "Optional scope restrictions (default ['*'] for all)",
        },
      },
      required: ["intent_id", "agent_id", "level"],
    },
    tier: "admin" as ToolTier,
  },

  // ── Credential Vaults (RFC-0014) ──────────────────────────────────
  {
    name: "openintent_store_credential",
    description:
      "Store a credential in a vault. Credentials are encrypted at rest " +
      "and never exposed in API responses or audit logs.",
    inputSchema: {
      type: "object",
      properties: {
        vault_id: { type: "string", description: "The vault to store in" },
        credential_name: { type: "string", description: "Unique name for this credential" },
        credential_type: {
          type: "string",
          description: "Credential type (e.g. 'api_key', 'oauth2', 'bearer')",
        },
        metadata: {
          type: "object",
          description: "Non-sensitive metadata (base_url, auth_type, etc.)",
          additionalProperties: true,
        },
      },
      required: ["vault_id", "credential_name", "credential_type"],
    },
    tier: "admin" as ToolTier,
  },
  {
    name: "openintent_get_credential",
    description:
      "Retrieve credential metadata from a vault. Returns metadata only — " +
      "secrets are never exposed through MCP.",
    inputSchema: {
      type: "object",
      properties: {
        vault_id: { type: "string", description: "The vault containing the credential" },
        credential_name: { type: "string", description: "The credential to retrieve" },
      },
      required: ["vault_id", "credential_name"],
    },
    tier: "admin" as ToolTier,
  },
  {
    name: "openintent_grant_tool",
    description:
      "Grant an agent access to use a specific tool with optional constraints. " +
      "The tool must be backed by a credential in the vault.",
    inputSchema: {
      type: "object",
      properties: {
        intent_id: { type: "string", description: "The intent scope for the grant" },
        agent_id: { type: "string", description: "The agent receiving tool access" },
        tool_name: { type: "string", description: "Name of the tool to grant" },
        constraints: {
          type: "object",
          description: "Optional usage constraints (rate limits, allowed methods, etc.)",
          additionalProperties: true,
        },
      },
      required: ["intent_id", "agent_id", "tool_name"],
    },
    tier: "admin" as ToolTier,
  },

  // ── Agent Memory (RFC-0015) ───────────────────────────────────────
  {
    name: "openintent_memory_set",
    description:
      "Store a value in an agent's persistent memory. Memory is organized " +
      "by namespace and key, with optional TTL for automatic expiration.",
    inputSchema: {
      type: "object",
      properties: {
        agent_id: { type: "string", description: "The agent whose memory to write" },
        namespace: { type: "string", description: "Memory namespace (e.g. 'preferences', 'context')" },
        key: { type: "string", description: "Memory key" },
        value: { description: "Value to store (any JSON-serializable data)" },
        ttl_seconds: { type: "number", description: "Optional time-to-live in seconds" },
      },
      required: ["agent_id", "namespace", "key", "value"],
    },
    tier: "write" as ToolTier,
  },
  {
    name: "openintent_memory_get",
    description: "Retrieve a value from an agent's persistent memory by namespace and key.",
    inputSchema: {
      type: "object",
      properties: {
        agent_id: { type: "string", description: "The agent whose memory to read" },
        namespace: { type: "string", description: "Memory namespace" },
        key: { type: "string", description: "Memory key" },
      },
      required: ["agent_id", "namespace", "key"],
    },
    tier: "read" as ToolTier,
  },
  {
    name: "openintent_memory_list",
    description:
      "List all memory keys for an agent, optionally filtered by namespace.",
    inputSchema: {
      type: "object",
      properties: {
        agent_id: { type: "string", description: "The agent whose memory to list" },
        namespace: { type: "string", description: "Optional namespace filter" },
      },
      required: ["agent_id"],
    },
    tier: "read" as ToolTier,
  },

  // ── Agent Lifecycle (RFC-0016) ────────────────────────────────────
  {
    name: "openintent_heartbeat",
    description:
      "Send a heartbeat signal to indicate an agent is alive and healthy. " +
      "Agents that miss heartbeats may be marked as unhealthy.",
    inputSchema: {
      type: "object",
      properties: {
        agent_id: { type: "string", description: "The agent sending the heartbeat" },
        status: {
          type: "string",
          enum: ["healthy", "degraded", "busy"],
          description: "Current agent status (default 'healthy')",
        },
        metadata: {
          type: "object",
          description: "Optional metadata (load, memory usage, etc.)",
          additionalProperties: true,
        },
      },
      required: ["agent_id"],
    },
    tier: "write" as ToolTier,
  },
  {
    name: "openintent_get_health",
    description:
      "Get the health status of an agent including last heartbeat time " +
      "and any reported issues.",
    inputSchema: {
      type: "object",
      properties: {
        agent_id: { type: "string", description: "The agent to check" },
      },
      required: ["agent_id"],
    },
    tier: "read" as ToolTier,
  },
  {
    name: "openintent_set_agent_status",
    description:
      "Set the lifecycle status of an agent (e.g. active, paused, terminated). " +
      "Used by coordinators to manage agent availability.",
    inputSchema: {
      type: "object",
      properties: {
        agent_id: { type: "string", description: "The agent to update" },
        status: {
          type: "string",
          enum: ["active", "paused", "draining", "terminated"],
          description: "New lifecycle status",
        },
        reason: { type: "string", description: "Optional reason for the status change" },
      },
      required: ["agent_id", "status"],
    },
    tier: "admin" as ToolTier,
  },

  // ── Triggers (RFC-0017) ───────────────────────────────────────────
  {
    name: "openintent_create_trigger",
    description:
      "Create a reactive trigger that fires an action when a condition is met. " +
      "Triggers enable event-driven coordination patterns.",
    inputSchema: {
      type: "object",
      properties: {
        intent_id: { type: "string", description: "The intent scope for this trigger" },
        name: { type: "string", description: "Optional trigger name" },
        trigger_type: {
          type: "string",
          enum: ["event", "schedule", "state_change", "webhook"],
          description: "Type of trigger",
        },
        condition: {
          type: "object",
          description: "Trigger condition (event pattern, cron expression, state predicate, etc.)",
          additionalProperties: true,
        },
        action: {
          type: "object",
          description: "Action to execute when triggered (notify, invoke tool, transition status, etc.)",
          additionalProperties: true,
        },
      },
      required: ["intent_id", "trigger_type", "condition", "action"],
    },
    tier: "admin" as ToolTier,
  },
  {
    name: "openintent_list_triggers",
    description: "List all triggers configured for an intent.",
    inputSchema: {
      type: "object",
      properties: {
        intent_id: { type: "string", description: "The intent to query" },
      },
      required: ["intent_id"],
    },
    tier: "read" as ToolTier,
  },
  {
    name: "openintent_delete_trigger",
    description: "Delete a trigger from an intent.",
    inputSchema: {
      type: "object",
      properties: {
        intent_id: { type: "string", description: "The intent containing the trigger" },
        trigger_id: { type: "string", description: "The trigger to delete" },
      },
      required: ["intent_id", "trigger_id"],
    },
    tier: "admin" as ToolTier,
  },

  // ── Cryptographic Agent Identity (RFC-0018) ───────────────────────
  {
    name: "openintent_register_identity",
    description:
      "Register a cryptographic identity for an agent using Ed25519 key pairs. " +
      "Creates a did:key identifier for the agent.",
    inputSchema: {
      type: "object",
      properties: {
        agent_id: { type: "string", description: "The agent to register" },
        public_key: { type: "string", description: "Base64-encoded Ed25519 public key" },
        key_type: {
          type: "string",
          enum: ["ed25519"],
          description: "Key type (default 'ed25519')",
        },
      },
      required: ["agent_id", "public_key"],
    },
    tier: "admin" as ToolTier,
  },
  {
    name: "openintent_verify_challenge",
    description:
      "Verify a challenge-response proof of identity. The agent must sign " +
      "the challenge with its private key to prove ownership.",
    inputSchema: {
      type: "object",
      properties: {
        agent_id: { type: "string", description: "The agent being verified" },
        challenge: { type: "string", description: "The challenge string to verify against" },
        signature: { type: "string", description: "Base64-encoded signature of the challenge" },
      },
      required: ["agent_id", "challenge", "signature"],
    },
    tier: "admin" as ToolTier,
  },
  {
    name: "openintent_rotate_key",
    description:
      "Rotate an agent's cryptographic key pair. Requires a rotation proof " +
      "signed by the current key to authorize the change.",
    inputSchema: {
      type: "object",
      properties: {
        agent_id: { type: "string", description: "The agent whose key to rotate" },
        new_public_key: { type: "string", description: "Base64-encoded new Ed25519 public key" },
        rotation_proof: { type: "string", description: "Signature proving ownership of the current key" },
      },
      required: ["agent_id", "new_public_key", "rotation_proof"],
    },
    tier: "admin" as ToolTier,
  },

  // ── Verifiable Event Logs (RFC-0019) ──────────────────────────────
  {
    name: "openintent_get_hash_chain",
    description:
      "Retrieve the SHA-256 hash chain for an intent's event log. Each event " +
      "is linked to the previous by its hash, forming a tamper-evident chain.",
    inputSchema: {
      type: "object",
      properties: {
        intent_id: { type: "string", description: "The intent to query" },
        from_sequence: { type: "number", description: "Start sequence number (optional)" },
        to_sequence: { type: "number", description: "End sequence number (optional)" },
      },
      required: ["intent_id"],
    },
    tier: "read" as ToolTier,
  },
  {
    name: "openintent_verify_inclusion",
    description:
      "Verify that a specific event is included in the Merkle tree checkpoint. " +
      "Returns an inclusion proof that can be independently verified.",
    inputSchema: {
      type: "object",
      properties: {
        intent_id: { type: "string", description: "The intent containing the event" },
        event_id: { type: "string", description: "The event to verify" },
      },
      required: ["intent_id", "event_id"],
    },
    tier: "read" as ToolTier,
  },
  {
    name: "openintent_get_checkpoint",
    description:
      "Retrieve a Merkle tree checkpoint for an intent's event log. " +
      "Checkpoints provide a compact, verifiable summary of the log state.",
    inputSchema: {
      type: "object",
      properties: {
        intent_id: { type: "string", description: "The intent to query" },
        checkpoint_id: { type: "string", description: "Specific checkpoint ID (default: latest)" },
      },
      required: ["intent_id"],
    },
    tier: "read" as ToolTier,
  },

  // ── Distributed Tracing (RFC-0020) ────────────────────────────────
  {
    name: "openintent_start_trace",
    description:
      "Start a new distributed trace for tracking operations across agents. " +
      "Traces correlate events and tool invocations across the protocol.",
    inputSchema: {
      type: "object",
      properties: {
        intent_id: { type: "string", description: "The intent to trace within" },
        trace_name: { type: "string", description: "Human-readable trace name" },
        parent_trace_id: { type: "string", description: "Parent trace ID for nested traces" },
        metadata: {
          type: "object",
          description: "Optional trace metadata",
          additionalProperties: true,
        },
      },
      required: ["intent_id", "trace_name"],
    },
    tier: "write" as ToolTier,
  },
  {
    name: "openintent_get_trace",
    description: "Retrieve a trace and its spans for analysis.",
    inputSchema: {
      type: "object",
      properties: {
        intent_id: { type: "string", description: "The intent containing the trace" },
        trace_id: { type: "string", description: "The trace identifier" },
      },
      required: ["intent_id", "trace_id"],
    },
    tier: "read" as ToolTier,
  },
  {
    name: "openintent_link_spans",
    description:
      "Link span entries to an existing trace. Spans represent individual " +
      "operations within a trace and can be nested via parent_span_id.",
    inputSchema: {
      type: "object",
      properties: {
        trace_id: { type: "string", description: "The trace to add spans to" },
        spans: {
          type: "array",
          items: {
            type: "object",
            properties: {
              span_id: { type: "string" },
              parent_span_id: { type: "string" },
              operation: { type: "string" },
              status: { type: "string" },
            },
            required: ["span_id", "operation"],
          },
          description: "Spans to link to the trace",
        },
      },
      required: ["trace_id", "spans"],
    },
    tier: "write" as ToolTier,
  },
];

/**
 * Route an incoming tool call to the appropriate client method.
 * The tool must pass both the role gate and the allowlist before execution.
 */
export async function handleToolCall(
  name: string,
  args: Record<string, unknown>,
  client: OpenIntentClient,
  config: MCPConfig,
) {
  const permission = isToolPermitted(name, config);
  if (!permission.allowed) {
    return errorResult(permission.reason ?? `Tool "${name}" is not permitted.`);
  }

  try {
    let result: unknown;

    switch (name) {
      case "openintent_create_intent":
        result = await client.createIntent({
          title: args.title as string,
          description: args.description as string | undefined,
          constraints: args.constraints as string[] | undefined,
          initial_state: args.initial_state as Record<string, unknown> | undefined,
        });
        break;

      case "openintent_get_intent":
        result = await client.getIntent(args.intent_id as string);
        break;

      case "openintent_list_intents":
        result = await client.listIntents({
          status: args.status as string | undefined,
          limit: args.limit as number | undefined,
          offset: args.offset as number | undefined,
        });
        break;

      case "openintent_update_state":
        result = await client.updateState({
          intent_id: args.intent_id as string,
          version: args.version as number,
          state_patch: args.state_patch as Record<string, unknown>,
        });
        break;

      case "openintent_set_status":
        result = await client.setStatus({
          intent_id: args.intent_id as string,
          version: args.version as number,
          status: args.status as string,
        });
        break;

      case "openintent_log_event":
        result = await client.logEvent({
          intent_id: args.intent_id as string,
          event_type: args.event_type as string,
          payload: args.payload as Record<string, unknown> | undefined,
        });
        break;

      case "openintent_get_events":
        result = await client.getEvents({
          intent_id: args.intent_id as string,
          event_type: args.event_type as string | undefined,
          limit: args.limit as number | undefined,
        });
        break;

      case "openintent_acquire_lease":
        result = await client.acquireLease({
          intent_id: args.intent_id as string,
          scope: args.scope as string,
          duration_seconds: args.duration_seconds as number | undefined,
        });
        break;

      case "openintent_release_lease":
        result = await client.releaseLease({
          intent_id: args.intent_id as string,
          lease_id: args.lease_id as string,
        });
        break;

      case "openintent_assign_agent":
        result = await client.assignAgent({
          intent_id: args.intent_id as string,
          agent_id: args.agent_id as string,
          role: args.role as string | undefined,
        });
        break;

      case "openintent_unassign_agent":
        result = await client.unassignAgent({
          intent_id: args.intent_id as string,
          agent_id: args.agent_id as string,
        });
        break;

      case "openintent_create_channel":
        result = await client.createChannel({
          intent_id: args.intent_id as string,
          name: args.name as string,
          members: args.members as string[] | undefined,
          member_policy: args.member_policy as string | undefined,
        });
        break;

      case "openintent_send_message":
        result = await client.sendMessage({
          channel_id: args.channel_id as string,
          payload: args.payload as Record<string, unknown>,
          to: args.to as string | undefined,
          message_type: args.message_type as string | undefined,
        });
        break;

      case "openintent_ask":
        result = await client.askOnChannel({
          channel_id: args.channel_id as string,
          to: args.to as string,
          payload: args.payload as Record<string, unknown>,
          timeout: args.timeout as number | undefined,
        });
        break;

      case "openintent_broadcast":
        result = await client.broadcastOnChannel({
          channel_id: args.channel_id as string,
          payload: args.payload as Record<string, unknown>,
        });
        break;

      case "openintent_get_messages":
        result = await client.getChannelMessages({
          channel_id: args.channel_id as string,
          limit: args.limit as number | undefined,
        });
        break;

      // ── Workflows (RFC-0011) ──────────────────────────────────────
      case "openintent_create_workflow":
        result = await client.createWorkflow({
          name: args.name as string,
          yaml_spec: args.yaml_spec as string,
          description: args.description as string | undefined,
        });
        break;

      case "openintent_trigger_workflow":
        result = await client.triggerWorkflow({
          workflow_id: args.workflow_id as string,
          inputs: args.inputs as Record<string, unknown> | undefined,
        });
        break;

      case "openintent_get_workflow":
        result = await client.getWorkflow(args.workflow_id as string);
        break;

      case "openintent_list_workflows":
        result = await client.listWorkflows({
          limit: args.limit as number | undefined,
          offset: args.offset as number | undefined,
        });
        break;

      // ── Plans (RFC-0012) ──────────────────────────────────────────
      case "openintent_create_plan":
        result = await client.createPlan({
          intent_id: args.intent_id as string,
          title: args.title as string,
          steps: args.steps as Array<{ title: string; description?: string; depends_on?: string[] }>,
        });
        break;

      case "openintent_decompose_task":
        result = await client.decomposeTask({
          intent_id: args.intent_id as string,
          task_description: args.task_description as string,
          max_depth: args.max_depth as number | undefined,
        });
        break;

      case "openintent_get_plan":
        result = await client.getPlan({
          intent_id: args.intent_id as string,
          plan_id: args.plan_id as string,
        });
        break;

      // ── Governance (RFC-0013) ─────────────────────────────────────
      case "openintent_set_coordinator":
        result = await client.setCoordinator({
          intent_id: args.intent_id as string,
          coordinator_id: args.coordinator_id as string,
          governance_policy: args.governance_policy as string | undefined,
        });
        break;

      case "openintent_record_decision":
        result = await client.recordDecision({
          intent_id: args.intent_id as string,
          decision_type: args.decision_type as string,
          rationale: args.rationale as string,
          outcome: args.outcome as Record<string, unknown>,
        });
        break;

      case "openintent_get_arbitration":
        result = await client.getArbitration({
          intent_id: args.intent_id as string,
        });
        break;

      // ── Human Escalation (RFC-0013) ───────────────────────────────
      case "openintent_escalate_to_human":
        result = await client.escalateToHuman({
          intent_id: args.intent_id as string,
          reason: args.reason as string,
          priority: args.priority as string | undefined,
          context: args.context as Record<string, unknown> | undefined,
        });
        break;

      case "openintent_list_escalations":
        result = await client.listEscalations({
          intent_id: args.intent_id as string | undefined,
          status: args.status as string | undefined,
          limit: args.limit as number | undefined,
          offset: args.offset as number | undefined,
        });
        break;

      case "openintent_resolve_escalation":
        result = await client.resolveEscalation({
          escalation_id: args.escalation_id as string,
          resolution: args.resolution as string,
          decision: args.decision as Record<string, unknown>,
        });
        break;

      case "openintent_request_approval":
        result = await client.requestApproval({
          intent_id: args.intent_id as string,
          action_description: args.action_description as string,
          urgency: args.urgency as string | undefined,
          metadata: args.metadata as Record<string, unknown> | undefined,
        });
        break;

      case "openintent_get_approval_status":
        result = await client.getApprovalStatus({
          intent_id: args.intent_id as string,
          approval_id: args.approval_id as string,
        });
        break;

      // ── Portfolios (RFC-0004) ─────────────────────────────────────
      case "openintent_create_portfolio":
        result = await client.createPortfolio({
          name: args.name as string,
          description: args.description as string | undefined,
        });
        break;

      case "openintent_add_to_portfolio":
        result = await client.addToPortfolio({
          portfolio_id: args.portfolio_id as string,
          intent_id: args.intent_id as string,
        });
        break;

      case "openintent_get_portfolio":
        result = await client.getPortfolio(args.portfolio_id as string);
        break;

      // ── Access Control (RFC-0011) ─────────────────────────────────
      case "openintent_set_permissions":
        result = await client.setPermissions({
          intent_id: args.intent_id as string,
          permissions: args.permissions as Record<string, unknown>,
          version: args.version as number,
        });
        break;

      case "openintent_get_permissions":
        result = await client.getPermissions({
          intent_id: args.intent_id as string,
        });
        break;

      case "openintent_grant_access":
        result = await client.grantAccess({
          intent_id: args.intent_id as string,
          agent_id: args.agent_id as string,
          level: args.level as string,
          scopes: args.scopes as string[] | undefined,
        });
        break;

      // ── Credential Vaults (RFC-0014) ──────────────────────────────
      case "openintent_store_credential":
        result = await client.storeCredential({
          vault_id: args.vault_id as string,
          credential_name: args.credential_name as string,
          credential_type: args.credential_type as string,
          metadata: args.metadata as Record<string, unknown> | undefined,
        });
        break;

      case "openintent_get_credential":
        result = await client.getCredential({
          vault_id: args.vault_id as string,
          credential_name: args.credential_name as string,
        });
        break;

      case "openintent_grant_tool":
        result = await client.grantTool({
          intent_id: args.intent_id as string,
          agent_id: args.agent_id as string,
          tool_name: args.tool_name as string,
          constraints: args.constraints as Record<string, unknown> | undefined,
        });
        break;

      // ── Agent Memory (RFC-0015) ───────────────────────────────────
      case "openintent_memory_set":
        result = await client.memorySet({
          agent_id: args.agent_id as string,
          namespace: args.namespace as string,
          key: args.key as string,
          value: args.value,
          ttl_seconds: args.ttl_seconds as number | undefined,
        });
        break;

      case "openintent_memory_get":
        result = await client.memoryGet({
          agent_id: args.agent_id as string,
          namespace: args.namespace as string,
          key: args.key as string,
        });
        break;

      case "openintent_memory_list":
        result = await client.memoryList({
          agent_id: args.agent_id as string,
          namespace: args.namespace as string | undefined,
        });
        break;

      // ── Agent Lifecycle (RFC-0016) ────────────────────────────────
      case "openintent_heartbeat":
        result = await client.heartbeat({
          agent_id: args.agent_id as string,
          status: args.status as string | undefined,
          metadata: args.metadata as Record<string, unknown> | undefined,
        });
        break;

      case "openintent_get_health":
        result = await client.getHealth({
          agent_id: args.agent_id as string,
        });
        break;

      case "openintent_set_agent_status":
        result = await client.setAgentStatus({
          agent_id: args.agent_id as string,
          status: args.status as string,
          reason: args.reason as string | undefined,
        });
        break;

      // ── Triggers (RFC-0017) ───────────────────────────────────────
      case "openintent_create_trigger":
        result = await client.createTrigger({
          intent_id: args.intent_id as string,
          trigger_type: args.trigger_type as string,
          condition: args.condition as Record<string, unknown>,
          action: args.action as Record<string, unknown>,
          name: args.name as string | undefined,
        });
        break;

      case "openintent_list_triggers":
        result = await client.listTriggers({
          intent_id: args.intent_id as string,
        });
        break;

      case "openintent_delete_trigger":
        result = await client.deleteTrigger({
          intent_id: args.intent_id as string,
          trigger_id: args.trigger_id as string,
        });
        break;

      // ── Cryptographic Identity (RFC-0018) ─────────────────────────
      case "openintent_register_identity":
        result = await client.registerIdentity({
          agent_id: args.agent_id as string,
          public_key: args.public_key as string,
          key_type: args.key_type as string | undefined,
        });
        break;

      case "openintent_verify_challenge":
        result = await client.verifyChallenge({
          agent_id: args.agent_id as string,
          challenge: args.challenge as string,
          signature: args.signature as string,
        });
        break;

      case "openintent_rotate_key":
        result = await client.rotateKey({
          agent_id: args.agent_id as string,
          new_public_key: args.new_public_key as string,
          rotation_proof: args.rotation_proof as string,
        });
        break;

      // ── Verifiable Event Logs (RFC-0019) ──────────────────────────
      case "openintent_get_hash_chain":
        result = await client.getHashChain({
          intent_id: args.intent_id as string,
          from_sequence: args.from_sequence as number | undefined,
          to_sequence: args.to_sequence as number | undefined,
        });
        break;

      case "openintent_verify_inclusion":
        result = await client.verifyInclusion({
          intent_id: args.intent_id as string,
          event_id: args.event_id as string,
        });
        break;

      case "openintent_get_checkpoint":
        result = await client.getCheckpoint({
          intent_id: args.intent_id as string,
          checkpoint_id: args.checkpoint_id as string | undefined,
        });
        break;

      // ── Distributed Tracing (RFC-0020) ────────────────────────────
      case "openintent_start_trace":
        result = await client.startTrace({
          intent_id: args.intent_id as string,
          trace_name: args.trace_name as string,
          parent_trace_id: args.parent_trace_id as string | undefined,
          metadata: args.metadata as Record<string, unknown> | undefined,
        });
        break;

      case "openintent_get_trace":
        result = await client.getTrace({
          intent_id: args.intent_id as string,
          trace_id: args.trace_id as string,
        });
        break;

      case "openintent_link_spans":
        result = await client.linkSpans({
          trace_id: args.trace_id as string,
          spans: args.spans as Array<{ span_id: string; parent_span_id?: string; operation: string; status?: string }>,
        });
        break;

      default:
        return errorResult(`Unknown tool: ${name}`);
    }

    return textResult(result);
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return errorResult(message);
  }
}
