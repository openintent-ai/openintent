import type { MCPConfig } from "./config.js";
import { enforceTransport, createAuditEntry } from "./security.js";

export class OpenIntentAPIError extends Error {
  constructor(
    message: string,
    public statusCode: number,
    public body?: unknown,
  ) {
    super(message);
    this.name = "OpenIntentAPIError";
  }
}

/**
 * Thin HTTP client that calls the OpenIntent REST API.
 * Uses the built-in `fetch` available in Node 18+.
 */
export class OpenIntentClient {
  private baseUrl: string;
  private headers: Record<string, string>;
  private timeoutMs: number;
  private retries: number;
  private retryDelay: number;
  private auditLogging: boolean;
  private config: MCPConfig;

  constructor(config: MCPConfig) {
    this.baseUrl = config.server.url.replace(/\/+$/, "");
    this.headers = {
      "Content-Type": "application/json",
      "X-API-Key": config.server.api_key,
      "X-Agent-ID": config.server.agent_id,
    };
    this.timeoutMs = config.network.timeout;
    this.retries = config.network.retries;
    this.retryDelay = config.network.retry_delay;
    this.auditLogging = config.security.audit_logging;
    this.config = config;
  }

  private async request(
    method: string,
    path: string,
    body?: unknown,
    extraHeaders?: Record<string, string>,
  ): Promise<unknown> {
    const url = `${this.baseUrl}${path}`;
    enforceTransport(url, this.config);

    const maxTimeout = this.config.security.max_timeout * 1000;
    const effectiveTimeout = Math.min(this.timeoutMs, maxTimeout);

    let lastError: Error | undefined;

    for (let attempt = 0; attempt <= this.retries; attempt++) {
      const start = Date.now();
      try {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), effectiveTimeout);

        const res = await fetch(url, {
          method,
          headers: { ...this.headers, ...extraHeaders },
          body: body !== undefined ? JSON.stringify(body) : undefined,
          signal: controller.signal,
        });

        clearTimeout(timer);

        const duration = Date.now() - start;
        const responseBody = res.headers.get("content-type")?.includes("application/json")
          ? await res.json()
          : await res.text();

        if (this.auditLogging) {
          const entry = createAuditEntry(
            `${method} ${path}`,
            { status: res.status },
            res.ok ? "success" : "error",
            duration,
            this.config.server.agent_id,
          );
          process.stderr.write(`[audit] ${JSON.stringify(entry)}\n`);
        }

        if (!res.ok) {
          const msg =
            typeof responseBody === "object" && responseBody !== null
              ? (responseBody as Record<string, unknown>).message ?? res.statusText
              : res.statusText;
          throw new OpenIntentAPIError(String(msg), res.status, responseBody);
        }

        return responseBody;
      } catch (err) {
        lastError = err as Error;
        if (err instanceof OpenIntentAPIError && err.statusCode < 500) {
          throw err;
        }
        if (attempt < this.retries) {
          await new Promise((r) => setTimeout(r, this.retryDelay * (attempt + 1)));
        }
      }
    }

    throw lastError ?? new Error("Request failed after retries");
  }

  // ── Intent CRUD ──────────────────────────────────────────────────────

  async createIntent(params: {
    title: string;
    description?: string;
    constraints?: string[];
    initial_state?: Record<string, unknown>;
  }): Promise<unknown> {
    return this.request("POST", "/api/v1/intents", {
      title: params.title,
      description: params.description ?? "",
      constraints: params.constraints ?? [],
      state: params.initial_state ?? {},
      created_by: this.config.server.agent_id,
    });
  }

  async getIntent(intentId: string): Promise<unknown> {
    return this.request("GET", `/api/v1/intents/${intentId}`);
  }

  async listIntents(params?: {
    status?: string;
    limit?: number;
    offset?: number;
  }): Promise<unknown> {
    const query = new URLSearchParams();
    if (params?.status) query.set("status", params.status);
    if (params?.limit !== undefined) query.set("limit", String(params.limit));
    if (params?.offset !== undefined) query.set("offset", String(params.offset));
    const qs = query.toString();
    return this.request("GET", `/api/v1/intents${qs ? `?${qs}` : ""}`);
  }

  async updateState(params: {
    intent_id: string;
    version: number;
    state_patch: Record<string, unknown>;
  }): Promise<unknown> {
    const patches = Object.entries(params.state_patch).map(([path, value]) => ({
      op: "set",
      path,
      value,
    }));
    return this.request(
      "POST",
      `/api/v1/intents/${params.intent_id}/state`,
      { patches },
      { "If-Match": String(params.version) },
    );
  }

  async setStatus(params: {
    intent_id: string;
    version: number;
    status: string;
  }): Promise<unknown> {
    return this.request(
      "POST",
      `/api/v1/intents/${params.intent_id}/status`,
      { status: params.status },
      { "If-Match": String(params.version) },
    );
  }

  // ── Events ───────────────────────────────────────────────────────────

  async logEvent(params: {
    intent_id: string;
    event_type: string;
    payload?: Record<string, unknown>;
  }): Promise<unknown> {
    return this.request("POST", `/api/v1/intents/${params.intent_id}/events`, {
      event_type: params.event_type,
      actor: this.config.server.agent_id,
      payload: params.payload ?? {},
    });
  }

  async getEvents(params: {
    intent_id: string;
    event_type?: string;
    limit?: number;
  }): Promise<unknown> {
    const query = new URLSearchParams();
    if (params.event_type) query.set("event_type", params.event_type);
    if (params.limit !== undefined) query.set("limit", String(params.limit));
    const qs = query.toString();
    return this.request(
      "GET",
      `/api/v1/intents/${params.intent_id}/events${qs ? `?${qs}` : ""}`,
    );
  }

  // ── Leasing ──────────────────────────────────────────────────────────

  async acquireLease(params: {
    intent_id: string;
    scope: string;
    duration_seconds?: number;
  }): Promise<unknown> {
    return this.request("POST", `/api/v1/intents/${params.intent_id}/leases`, {
      scope: params.scope,
      duration_seconds: params.duration_seconds ?? 300,
    });
  }

  async releaseLease(params: {
    intent_id: string;
    lease_id: string;
  }): Promise<unknown> {
    return this.request(
      "DELETE",
      `/api/v1/intents/${params.intent_id}/leases/${params.lease_id}`,
    );
  }

  // ── Agent Management ─────────────────────────────────────────────────

  async assignAgent(params: {
    intent_id: string;
    agent_id: string;
    role?: string;
  }): Promise<unknown> {
    return this.request("POST", `/api/v1/intents/${params.intent_id}/agents`, {
      agent_id: params.agent_id,
      role: params.role ?? "worker",
    });
  }

  async unassignAgent(params: {
    intent_id: string;
    agent_id: string;
  }): Promise<unknown> {
    return this.request(
      "DELETE",
      `/api/v1/intents/${params.intent_id}/agents/${params.agent_id}`,
    );
  }

  // ── Messaging (RFC-0021) ─────────────────────────────────────────────

  async createChannel(params: {
    intent_id: string;
    name: string;
    members?: string[];
    member_policy?: string;
    options?: Record<string, unknown>;
  }): Promise<unknown> {
    return this.request("POST", `/api/v1/intents/${params.intent_id}/channels`, {
      name: params.name,
      members: params.members ?? [this.config.server.agent_id],
      member_policy: params.member_policy ?? "explicit",
      options: params.options ?? {},
    });
  }

  async sendMessage(params: {
    channel_id: string;
    message_type?: string;
    payload: Record<string, unknown>;
    to?: string;
  }): Promise<unknown> {
    return this.request("POST", `/api/v1/channels/${params.channel_id}/messages`, {
      sender: this.config.server.agent_id,
      message_type: params.message_type ?? "message",
      payload: params.payload,
      to: params.to,
    });
  }

  async askOnChannel(params: {
    channel_id: string;
    to: string;
    payload: Record<string, unknown>;
    timeout?: number;
  }): Promise<unknown> {
    return this.request("POST", `/api/v1/channels/${params.channel_id}/ask`, {
      sender: this.config.server.agent_id,
      to: params.to,
      payload: params.payload,
      timeout: params.timeout ?? 30,
    });
  }

  async broadcastOnChannel(params: {
    channel_id: string;
    payload: Record<string, unknown>;
  }): Promise<unknown> {
    return this.request("POST", `/api/v1/channels/${params.channel_id}/messages`, {
      sender: this.config.server.agent_id,
      message_type: "broadcast",
      payload: params.payload,
    });
  }

  async getChannelMessages(params: {
    channel_id: string;
    limit?: number;
  }): Promise<unknown> {
    const query = new URLSearchParams();
    if (params.limit !== undefined) query.set("limit", String(params.limit));
    const qs = query.toString();
    return this.request(
      "GET",
      `/api/v1/channels/${params.channel_id}/messages${qs ? `?${qs}` : ""}`,
    );
  }

  // ── Workflows (RFC-0011) ──────────────────────────────────────────

  async createWorkflow(params: {
    name: string;
    yaml_spec: string;
    description?: string;
  }): Promise<unknown> {
    return this.request("POST", "/api/v1/workflows", {
      name: params.name,
      yaml_spec: params.yaml_spec,
      description: params.description ?? "",
      created_by: this.config.server.agent_id,
    });
  }

  async triggerWorkflow(params: {
    workflow_id: string;
    inputs?: Record<string, unknown>;
  }): Promise<unknown> {
    return this.request("POST", `/api/v1/workflows/${params.workflow_id}/trigger`, {
      inputs: params.inputs ?? {},
      triggered_by: this.config.server.agent_id,
    });
  }

  async getWorkflow(workflowId: string): Promise<unknown> {
    return this.request("GET", `/api/v1/workflows/${workflowId}`);
  }

  async listWorkflows(params?: {
    limit?: number;
    offset?: number;
  }): Promise<unknown> {
    const query = new URLSearchParams();
    if (params?.limit !== undefined) query.set("limit", String(params.limit));
    if (params?.offset !== undefined) query.set("offset", String(params.offset));
    const qs = query.toString();
    return this.request("GET", `/api/v1/workflows${qs ? `?${qs}` : ""}`);
  }

  // ── Plans (RFC-0012) ──────────────────────────────────────────────

  async createPlan(params: {
    intent_id: string;
    title: string;
    steps: Array<{ title: string; description?: string; depends_on?: string[] }>;
  }): Promise<unknown> {
    return this.request("POST", `/api/v1/intents/${params.intent_id}/plans`, {
      title: params.title,
      steps: params.steps,
      created_by: this.config.server.agent_id,
    });
  }

  async decomposeTask(params: {
    intent_id: string;
    task_description: string;
    max_depth?: number;
  }): Promise<unknown> {
    return this.request("POST", `/api/v1/intents/${params.intent_id}/plans/decompose`, {
      task_description: params.task_description,
      max_depth: params.max_depth ?? 3,
      requested_by: this.config.server.agent_id,
    });
  }

  async getPlan(params: {
    intent_id: string;
    plan_id: string;
  }): Promise<unknown> {
    return this.request("GET", `/api/v1/intents/${params.intent_id}/plans/${params.plan_id}`);
  }

  // ── Governance (RFC-0013) ─────────────────────────────────────────

  async setCoordinator(params: {
    intent_id: string;
    coordinator_id: string;
    governance_policy?: string;
  }): Promise<unknown> {
    return this.request("POST", `/api/v1/intents/${params.intent_id}/coordinator`, {
      coordinator_id: params.coordinator_id,
      governance_policy: params.governance_policy ?? "default",
      set_by: this.config.server.agent_id,
    });
  }

  async recordDecision(params: {
    intent_id: string;
    decision_type: string;
    rationale: string;
    outcome: Record<string, unknown>;
  }): Promise<unknown> {
    return this.request("POST", `/api/v1/intents/${params.intent_id}/decisions`, {
      decision_type: params.decision_type,
      rationale: params.rationale,
      outcome: params.outcome,
      decided_by: this.config.server.agent_id,
    });
  }

  async getArbitration(params: {
    intent_id: string;
  }): Promise<unknown> {
    return this.request("GET", `/api/v1/intents/${params.intent_id}/arbitration`);
  }

  // ── Human Escalation (RFC-0013) ────────────────────────────────────

  async escalateToHuman(params: {
    intent_id: string;
    reason: string;
    priority?: string;
    context?: Record<string, unknown>;
  }): Promise<unknown> {
    const mapped = this.mapPriority(params.priority ?? "normal");
    return this.request("POST", `/api/v1/intents/${params.intent_id}/escalations`, {
      reason: params.reason,
      priority: mapped,
      urgency: mapped,
      context: params.context ?? {},
      escalated_by: this.config.server.agent_id,
    });
  }

  private mapPriority(p: string): string {
    return p === "normal" ? "medium" : p;
  }

  async listEscalations(params: {
    intent_id?: string;
    status?: string;
    limit?: number;
    offset?: number;
  }): Promise<unknown> {
    const qs = new URLSearchParams();
    if (params.intent_id) qs.set("intent_id", params.intent_id);
    if (params.status) qs.set("status", params.status);
    if (params.limit !== undefined) qs.set("limit", String(params.limit));
    if (params.offset !== undefined) qs.set("offset", String(params.offset));
    const query = qs.toString();
    return this.request("GET", `/api/v1/escalations${query ? `?${query}` : ""}`);
  }

  async resolveEscalation(params: {
    escalation_id: string;
    resolution: string;
    decision: Record<string, unknown>;
  }): Promise<unknown> {
    return this.request("POST", `/api/v1/escalations/${params.escalation_id}/resolve`, {
      resolution: params.resolution,
      notes: JSON.stringify(params.decision),
      resolved_by: this.config.server.agent_id,
    });
  }

  async requestApproval(params: {
    intent_id: string;
    action_description: string;
    urgency?: string;
    metadata?: Record<string, unknown>;
  }): Promise<unknown> {
    const context: Record<string, unknown> = { ...(params.metadata ?? {}) };
    if (params.urgency) {
      context.urgency = this.mapPriority(params.urgency);
    }
    return this.request("POST", `/api/v1/intents/${params.intent_id}/approvals`, {
      action: params.action_description,
      reason: params.action_description,
      context,
      requested_by: this.config.server.agent_id,
    });
  }

  async getApprovalStatus(params: {
    intent_id: string;
    approval_id: string;
  }): Promise<unknown> {
    return this.request("GET", `/api/v1/intents/${params.intent_id}/approvals/${params.approval_id}`);
  }

  // ── Portfolios (RFC-0004) ─────────────────────────────────────────

  async createPortfolio(params: {
    name: string;
    description?: string;
  }): Promise<unknown> {
    return this.request("POST", "/api/v1/portfolios", {
      name: params.name,
      description: params.description ?? "",
      created_by: this.config.server.agent_id,
    });
  }

  async addToPortfolio(params: {
    portfolio_id: string;
    intent_id: string;
  }): Promise<unknown> {
    return this.request("POST", `/api/v1/portfolios/${params.portfolio_id}/intents`, {
      intent_id: params.intent_id,
    });
  }

  async getPortfolio(portfolioId: string): Promise<unknown> {
    return this.request("GET", `/api/v1/portfolios/${portfolioId}`);
  }

  // ── Access Control (RFC-0011) ─────────────────────────────────────

  async setPermissions(params: {
    intent_id: string;
    permissions: Record<string, unknown>;
    version: number;
  }): Promise<unknown> {
    return this.request(
      "PUT",
      `/api/v1/intents/${params.intent_id}/permissions`,
      { permissions: params.permissions },
      { "If-Match": String(params.version) },
    );
  }

  async getPermissions(params: {
    intent_id: string;
  }): Promise<unknown> {
    return this.request("GET", `/api/v1/intents/${params.intent_id}/permissions`);
  }

  async grantAccess(params: {
    intent_id: string;
    agent_id: string;
    level: string;
    scopes?: string[];
  }): Promise<unknown> {
    return this.request("POST", `/api/v1/intents/${params.intent_id}/permissions/grants`, {
      agent_id: params.agent_id,
      level: params.level,
      scopes: params.scopes ?? ["*"],
      granted_by: this.config.server.agent_id,
    });
  }

  // ── Credential Vaults (RFC-0014) ──────────────────────────────────

  async storeCredential(params: {
    vault_id: string;
    credential_name: string;
    credential_type: string;
    metadata?: Record<string, unknown>;
  }): Promise<unknown> {
    return this.request("POST", `/api/v1/vaults/${params.vault_id}/credentials`, {
      name: params.credential_name,
      credential_type: params.credential_type,
      metadata: params.metadata ?? {},
      stored_by: this.config.server.agent_id,
    });
  }

  async getCredential(params: {
    vault_id: string;
    credential_name: string;
  }): Promise<unknown> {
    return this.request("GET", `/api/v1/vaults/${params.vault_id}/credentials/${params.credential_name}`);
  }

  async grantTool(params: {
    intent_id: string;
    agent_id: string;
    tool_name: string;
    constraints?: Record<string, unknown>;
  }): Promise<unknown> {
    return this.request("POST", `/api/v1/intents/${params.intent_id}/tools/grants`, {
      agent_id: params.agent_id,
      tool_name: params.tool_name,
      constraints: params.constraints ?? {},
      granted_by: this.config.server.agent_id,
    });
  }

  // ── Agent Memory (RFC-0015) ───────────────────────────────────────

  async memorySet(params: {
    agent_id: string;
    namespace: string;
    key: string;
    value: unknown;
    ttl_seconds?: number;
  }): Promise<unknown> {
    return this.request("PUT", `/api/v1/agents/${params.agent_id}/memory/${params.namespace}/${params.key}`, {
      value: params.value,
      ttl_seconds: params.ttl_seconds,
    });
  }

  async memoryGet(params: {
    agent_id: string;
    namespace: string;
    key: string;
  }): Promise<unknown> {
    return this.request("GET", `/api/v1/agents/${params.agent_id}/memory/${params.namespace}/${params.key}`);
  }

  async memoryList(params: {
    agent_id: string;
    namespace?: string;
  }): Promise<unknown> {
    const path = params.namespace
      ? `/api/v1/agents/${params.agent_id}/memory/${params.namespace}`
      : `/api/v1/agents/${params.agent_id}/memory`;
    return this.request("GET", path);
  }

  // ── Agent Lifecycle (RFC-0016) ────────────────────────────────────

  async heartbeat(params: {
    agent_id: string;
    status?: string;
    metadata?: Record<string, unknown>;
  }): Promise<unknown> {
    return this.request("POST", `/api/v1/agents/${params.agent_id}/heartbeat`, {
      status: params.status ?? "healthy",
      metadata: params.metadata ?? {},
    });
  }

  async getHealth(params: {
    agent_id: string;
  }): Promise<unknown> {
    return this.request("GET", `/api/v1/agents/${params.agent_id}/health`);
  }

  async setAgentStatus(params: {
    agent_id: string;
    status: string;
    reason?: string;
  }): Promise<unknown> {
    return this.request("PUT", `/api/v1/agents/${params.agent_id}/status`, {
      status: params.status,
      reason: params.reason ?? "",
    });
  }

  // ── Triggers (RFC-0017) ───────────────────────────────────────────

  async createTrigger(params: {
    intent_id: string;
    trigger_type: string;
    condition: Record<string, unknown>;
    action: Record<string, unknown>;
    name?: string;
  }): Promise<unknown> {
    return this.request("POST", `/api/v1/intents/${params.intent_id}/triggers`, {
      name: params.name ?? "",
      trigger_type: params.trigger_type,
      condition: params.condition,
      action: params.action,
      created_by: this.config.server.agent_id,
    });
  }

  async listTriggers(params: {
    intent_id: string;
  }): Promise<unknown> {
    return this.request("GET", `/api/v1/intents/${params.intent_id}/triggers`);
  }

  async deleteTrigger(params: {
    intent_id: string;
    trigger_id: string;
  }): Promise<unknown> {
    return this.request("DELETE", `/api/v1/intents/${params.intent_id}/triggers/${params.trigger_id}`);
  }

  // ── Cryptographic Identity (RFC-0018) ─────────────────────────────

  async registerIdentity(params: {
    agent_id: string;
    public_key: string;
    key_type?: string;
  }): Promise<unknown> {
    return this.request("POST", "/api/v1/identity/register", {
      agent_id: params.agent_id,
      public_key: params.public_key,
      key_type: params.key_type ?? "ed25519",
    });
  }

  async verifyChallenge(params: {
    agent_id: string;
    challenge: string;
    signature: string;
  }): Promise<unknown> {
    return this.request("POST", "/api/v1/identity/verify", {
      agent_id: params.agent_id,
      challenge: params.challenge,
      signature: params.signature,
    });
  }

  async rotateKey(params: {
    agent_id: string;
    new_public_key: string;
    rotation_proof: string;
  }): Promise<unknown> {
    return this.request("POST", `/api/v1/identity/${params.agent_id}/rotate`, {
      new_public_key: params.new_public_key,
      rotation_proof: params.rotation_proof,
    });
  }

  // ── Verifiable Event Logs (RFC-0019) ──────────────────────────────

  async getHashChain(params: {
    intent_id: string;
    from_sequence?: number;
    to_sequence?: number;
  }): Promise<unknown> {
    const query = new URLSearchParams();
    if (params.from_sequence !== undefined) query.set("from", String(params.from_sequence));
    if (params.to_sequence !== undefined) query.set("to", String(params.to_sequence));
    const qs = query.toString();
    return this.request("GET", `/api/v1/intents/${params.intent_id}/events/hashchain${qs ? `?${qs}` : ""}`);
  }

  async verifyInclusion(params: {
    intent_id: string;
    event_id: string;
  }): Promise<unknown> {
    return this.request("GET", `/api/v1/intents/${params.intent_id}/events/${params.event_id}/proof`);
  }

  async getCheckpoint(params: {
    intent_id: string;
    checkpoint_id?: string;
  }): Promise<unknown> {
    const path = params.checkpoint_id
      ? `/api/v1/intents/${params.intent_id}/events/checkpoints/${params.checkpoint_id}`
      : `/api/v1/intents/${params.intent_id}/events/checkpoints/latest`;
    return this.request("GET", path);
  }

  // ── Distributed Tracing (RFC-0020) ────────────────────────────────

  async startTrace(params: {
    intent_id: string;
    trace_name: string;
    parent_trace_id?: string;
    metadata?: Record<string, unknown>;
  }): Promise<unknown> {
    return this.request("POST", `/api/v1/intents/${params.intent_id}/traces`, {
      trace_name: params.trace_name,
      parent_trace_id: params.parent_trace_id,
      metadata: params.metadata ?? {},
      started_by: this.config.server.agent_id,
    });
  }

  async getTrace(params: {
    intent_id: string;
    trace_id: string;
  }): Promise<unknown> {
    return this.request("GET", `/api/v1/intents/${params.intent_id}/traces/${params.trace_id}`);
  }

  async linkSpans(params: {
    trace_id: string;
    spans: Array<{ span_id: string; parent_span_id?: string; operation: string; status?: string }>;
  }): Promise<unknown> {
    return this.request("POST", `/api/v1/traces/${params.trace_id}/spans`, {
      spans: params.spans,
      linked_by: this.config.server.agent_id,
    });
  }
}
