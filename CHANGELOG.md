# Changelog

All notable changes to the OpenIntent SDK will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.13.5] - 2026-02-14

### Added

- **MCP Governance Tool Surface Complete** — 4 governance enforcement tools now fully wired in the MCP server TypeScript implementation:
  - `set_governance_policy` — Set or update governance policy on an intent (admin tier, uses `If-Match` for optimistic concurrency).
  - `get_governance_policy` — Retrieve effective governance policy for an intent (reader tier).
  - `approve_approval` — Approve a pending approval gate (admin tier).
  - `deny_approval` — Deny a pending approval gate with optional reason (admin tier).
- **Full MCP Implementation Chain** — Tool definitions, client methods, handler cases, and RBAC tier assignments all in sync for the complete 62-tool surface.

### Fixed

- **MCP Startup Tool Count** — Fixed tool count mismatch where RBAC security tiers listed 62 tools but only 58 tool definitions existed. Startup log now correctly reports `tools=62/62` for admin role.
- **RBAC Tier Correction** — `operator` role count corrected from 37 to 38 across changelog entries and documentation.

### Changed

- Version bumped to 0.13.5 (v0.13.3 and v0.13.4 were npm publish patch releases for the `@openintentai/mcp-server` package).
- All version references updated across Python SDK, MCP server package, and documentation.

---

## [0.13.2] - 2026-02-14

### Changed

- **npm Package Scope Rename** — MCP server npm package renamed from `@openintent/mcp-server` to `@openintentai/mcp-server` to match the secured npm organization name. All documentation, examples, YAML workflows, `mcp://` URI schemes, and Makefile targets updated accordingly.

---

## [0.13.1] - 2026-02-14

### Added

- **OpenAI Codex Model Support** — Automatic routing for codex-family models (`gpt-5.2-codex`, `o3-codex`, etc.) that use the `/v1/completions` endpoint instead of `/v1/chat/completions`.
  - New `codex_utils` module with `is_codex_model()`, `messages_to_prompt()`, and `chat_kwargs_to_completions_kwargs()` helpers.
  - `OpenAICompletions` wrapper class for completions-API responses (maps `choices[0].text` to the standard content interface).
  - LLM engine routing updated in `_call_llm`, `_stream_llm`, and raw provider paths to auto-detect and redirect codex models.

### Fixed

- **Anthropic Streaming Usage Reliability** — Fixed two bugs causing token usage data (input/output token counts) to be silently lost during streaming:
  - Wrapped event consumption loop in `try/finally` so usage is saved even when the stream consumer exits early (`GeneratorExit`).
  - Added `_resolve_usage()` fallback that calls the SDK's `get_final_message()` when event parsing misses usage data, ensuring accurate cost tracking for all Anthropic models including those with extended thinking.

---

## [0.13.0] - 2026-02-14

### Added

- **Server-Enforced Governance (RFC-0013)** — Declarative governance policies with server-side enforcement on all mutation endpoints. Returns 403 with structured error details when governance rules are violated.
  - `GovernancePolicy` model with `completion_mode` (`auto`, `require_approval`, `quorum`), `write_scope` (`any`, `assigned_only`), `max_cost`, `quorum_threshold`, `allowed_agents`, and `require_status_reason`.
  - `governance_policy` parameter on `@Agent` and `@Coordinator` decorators for declarative policy attachment at creation time.
  - Fully backward compatible — intents without a governance policy behave exactly as before.
- **Governance Policy Endpoints** — `PUT /api/v1/intents/{id}/governance` (set policy, requires `If-Match`), `GET .../governance` (read effective policy), `DELETE .../governance` (remove policy).
- **Governance Approval Resolution** — `POST .../approvals/{id}/approve` and `POST .../approvals/{id}/deny` to resolve pending approval gates created by the v0.12.1 `request_approval` endpoint.
- **SSE Resume-After-Approval** — `governance.approval_granted`, `governance.approval_denied`, `governance.policy_set`, and `governance.policy_removed` events broadcast via SSE, enabling agents to resume without polling.
- **Governance Lifecycle Decorators** — `@on_governance_blocked`, `@on_approval_granted`, `@on_approval_denied` for reactive agent behavior when governance gates fire.
- **`self.governance` Proxy** — `set_policy()`, `get_policy()`, `remove_policy()`, `request_approval()`, `approve()`, `deny()` convenience methods on agent instances.
- **MCP Governance Tools** — 4 new tools: `set_governance_policy`, `get_governance_policy`, `approve_approval`, `deny_approval` (62 total; reader=21, operator=38, admin=62).
- **`GOVERNANCE_APPROVAL_ENFORCED` Event Type** — Emitted when a governance gate is satisfied and the blocked action proceeds.

### Changed

- All documentation, READMEs, and examples updated from v0.12.1 to v0.13.0.
- MCP tool surface expanded from 58 to 62 tools with 4 governance enforcement tools.
- RBAC role counts updated: reader=21 (was 20), operator=38 (was 37), admin=62 (was 58).
- Governance guide and examples updated with server-enforced patterns, approval gate workflows, and SSE resume examples.

---

## [0.12.1] - 2026-02-13

### Added

- **Human Escalation Tools (RFC-0013)**
  - `escalate_to_human`: Agents escalate when blocked or uncertain, providing reason, priority, urgency, and context.
  - `list_escalations`: List pending escalations filtered by intent ID or status.
  - `resolve_escalation`: Humans resolve escalations with a recorded decision and optional notes.
  - `request_approval`: Agents request human approval before proceeding with specific actions.
  - `get_approval_status`: Check the current status of a pending approval request.
- **MCP Tool Surface Expansion**
  - MCP tool count expanded from 53 to 58 (16 participation + 42 advanced).
  - RBAC role counts updated: `reader` = 20, `operator` = 37, `admin` = 58.
  - Human escalation tools assigned to appropriate tiers: `list_escalations` and `get_approval_status` (read), `escalate_to_human` and `request_approval` (write), `resolve_escalation` (admin).

---

## [0.12.0] - 2026-02-13

### Added

- **MCP Integration (Model Context Protocol)**
  - `@openintentai/mcp-server`: TypeScript MCP server exposing the full protocol API as 16 MCP tools and 5 MCP resources.
  - `openintent.mcp` Python module: `MCPBridge`, `MCPToolProvider`, and `MCPToolExporter` for bidirectional MCP integration.
  - YAML `mcp:` block for declarative MCP server configuration in workflows.
  - Security controls: TLS enforcement, tool allowlists, credential isolation, and audit logging.
- **MCP Role-Based Access Control (RBAC)**
  - Three permission tiers: `read` (observe state), `write` (bounded mutations), `admin` (lifecycle and coordination).
  - Three named roles: `reader` (4 tools), `operator` (10 tools), `admin` (16 tools).
  - Default role is `reader` — unconfigured servers cannot modify protocol state.
  - Role gate enforced alongside existing tool allowlist (both must pass).
  - Tools hidden from MCP tool listing when not permitted by role or allowlist.
  - Configurable via `OPENINTENT_MCP_ROLE` env var or `security.role` in JSON config.
  - Startup warnings for `admin` role and unknown role values.
- **MCPTool — First-Class MCP Tools in @Agent/@Coordinator**
  - `MCPTool` dataclass for declaring MCP servers as tool sources in `tools=[...]`.
  - `mcp://` URI scheme for inline MCP tool references (e.g., `"mcp://npx/-y/@openintentai/mcp-server?role=operator"`).
  - Automatic MCP connection at agent startup, tool discovery, ToolDef registration, and clean disconnection on shutdown.
  - RBAC `role` field on `MCPTool` defaults to `"reader"` (least privilege) and is set explicitly on each child process, isolating agents from ambient `OPENINTENT_MCP_ROLE` in the parent env.
  - Role validation with fallback to `"reader"` on invalid values and startup warnings for `admin` role.
  - Mixed tool lists: local `ToolDef`, `MCPTool`, `mcp://` URIs, and plain strings all coexist.
  - `parse_mcp_uri()` and `resolve_mcp_tools()` helpers exported from `openintent.mcp`.

---

## [0.11.0] - 2026-02-13

### Added

- **Declarative Messaging (RFC-0021)**
  - YAML `channels:` block for declarative agent-to-agent messaging configuration.
  - `@on_message` decorator for zero-boilerplate, reactive message handling with auto-reply.
  - Channel proxy (`self.channels`) with `ask()`, `notify()`, and `broadcast()` convenience methods.
  - Three messaging patterns: request/response, fire-and-forget, and broadcast.

---

## [0.10.1] - 2026-02-13

### Added

- **Tool Execution Adapters** — Pluggable adapter system for real external API execution through the Tool Proxy (`POST /api/v1/tools/invoke`). Three built-in adapters:
  - `RestToolAdapter` — API key (header/query), Bearer token, and Basic Auth for standard REST APIs.
  - `OAuth2ToolAdapter` — OAuth2 with automatic token refresh on 401 responses using `refresh_token` + `token_url`.
  - `WebhookToolAdapter` — HMAC-SHA256 signed dispatch for webhook receivers.
- **Adapter Registry** — `AdapterRegistry` resolves the correct adapter from credential metadata: explicit `adapter` key, `auth_type` mapping, or placeholder fallback for backward compatibility.
- **Security Controls** — All outbound tool execution requests enforce:
  - URL validation blocking private IPs (RFC-1918, loopback, link-local), cloud metadata endpoints (`169.254.169.254`), and non-HTTP schemes.
  - Timeout bounds clamped to 1–120 seconds (default 30s).
  - Response size limit of 1 MB.
  - Secret sanitization replacing API keys, tokens, and passwords with `[REDACTED]` in all outputs.
  - Request fingerprinting via SHA-256 hash stored per invocation for audit correlation.
  - HTTP redirect blocking to prevent SSRF via redirect chains.
- **Custom Adapter Registration** — `register_adapter(name, adapter)` to add adapters for services with non-standard protocols (e.g., GraphQL).
- **OAuth2 Integration Guide** — Comprehensive documentation for integrating OAuth2 services: platform handles the authorization code flow, stores tokens in the vault, SDK manages refresh and execution. Includes ready-to-use metadata templates for Salesforce, Google APIs, Microsoft Graph, and HubSpot.

### Changed

- Credential `metadata` field now supports execution config (`base_url`, `endpoints`, `auth`) to enable real API calls. Credentials without execution config continue to return placeholder responses (backward compatible).
- 57 new tests covering security utilities, all three adapters, and the adapter registry.
- Documentation updated across guide, RFC-0014, examples, API reference, and website.

---

## [0.10.0] - 2026-02-12

### Added

- **RFC-0018: Cryptographic Agent Identity**
  - `AgentIdentity`, `IdentityChallenge`, `IdentityVerification` data models for key-based agent identity.
  - Ed25519 key pairs with `did:key:z6Mk...` decentralized identifiers.
  - Challenge-response identity registration via `register_identity()` and `complete_identity_challenge()`.
  - Key rotation with `rotate_key()` preserving previous key history.
  - Signature verification with `verify_signature()`.
  - `@Identity` decorator for zero-boilerplate identity setup on agents.
  - `@on_identity_registered` lifecycle hook.
  - `IdentityConfig` for YAML workflow configuration.
  - `AgentRecord` extended with `public_key`, `did`, `key_algorithm`, `key_registered_at`, `key_expires_at`, `previous_keys` fields (all optional for backward compatibility).
  - 5 new server endpoints: `POST /api/v1/agents/{id}/identity`, `POST .../identity/challenge`, `GET .../identity`, `POST .../identity/verify`, `POST .../identity/rotate`.

- **RFC-0019: Verifiable Event Logs**
  - `LogCheckpoint`, `MerkleProof`, `MerkleProofEntry`, `ChainVerification`, `ConsistencyProof`, `TimestampAnchor` data models.
  - SHA-256 hash chains linking each event to its predecessor.
  - Merkle tree checkpoints with `MerkleProof.verify()` for client-side inclusion verification.
  - `verify_event_chain()` to validate an intent's full hash chain integrity.
  - `list_checkpoints()`, `get_checkpoint()`, `get_merkle_proof()`, `verify_consistency()` client methods.
  - `VerificationConfig` for YAML workflow configuration.
  - `IntentEvent` extended with optional `proof`, `event_hash`, `previous_event_hash`, `sequence` fields.
  - 8 new server endpoints for checkpoints, Merkle proofs, chain verification, and optional external anchoring.

- **RFC-0020: Distributed Tracing**
  - `TracingContext` dataclass for propagating trace state through agent → tool → agent call chains.
  - `IntentEvent` extended with optional `trace_id` (128-bit hex) and `parent_event_id` fields.
  - `log_event()` on both sync and async clients accepts `trace_id` and `parent_event_id` parameters.
  - `_emit_tool_event()` automatically includes tracing context in tool invocation events.
  - `_execute_tool()` passes `tracing` keyword argument to local tool handlers that accept it.
  - `TracingContext.new_root()` generates fresh 128-bit trace IDs (W3C-aligned format).
  - `TracingContext.child()` creates child contexts with updated parent references.
  - Cross-intent tracing via `trace_id` in event payloads.

- **Sync & Async Client Parity** — All new RFC-0018/0019/0020 methods available on both `OpenIntentClient` and `AsyncOpenIntentClient`.

### Changed

- Version bumped to 0.10.0.
- `__all__` exports updated with all new public symbols including `TracingContext`.
- 690+ tests passing across all 20 RFCs (104 model tests + 26 server tests for RFC-0018/0019/0020).

---

## [0.9.1] - 2026-02-12

### Fixed

- **Streaming token usage capture** — All 7 LLM provider adapters (OpenAI, DeepSeek, Gemini, Anthropic, Azure OpenAI, OpenRouter, Grok) now capture actual `prompt_tokens`, `completion_tokens`, and `total_tokens` during streaming responses. Previously, `tokens_streamed` used character count instead of real token counts.
- **OpenAI-compatible adapters** — OpenAI, DeepSeek, Azure OpenAI, OpenRouter, and Grok adapters now inject `stream_options={"include_usage": True}` to receive usage data in the final stream chunk. Token counts are extracted and passed through to `complete_stream()` and `log_llm_request_completed()`.
- **Gemini adapter** — Captures `usage_metadata` from stream chunks (`prompt_token_count`, `candidates_token_count`, `total_token_count`) and maps to standard fields.
- **Anthropic adapter** — Extracts usage from the stream's internal message snapshot in `__exit__`, removing the need for a manual `get_final_message()` call.
- **`tokens_streamed` field** — Now reports actual completion token counts from provider APIs, falling back to character count only when usage data is unavailable.

---

## [0.9.0] - 2026-02-11

### Added

- **Server-Side Tool Invocation** — `POST /api/v1/tools/invoke` endpoint enables agents to invoke tools through the server proxy without ever accessing raw credentials. The server resolves the appropriate grant, injects credentials from the vault, enforces rate limits, and records the invocation for audit.
- **3-Tier Grant Resolution** — Tool invocations are matched to grants using a three-tier resolution strategy: (1) `grant.scopes` contains the tool name, (2) `grant.context["tools"]` contains the tool name, (3) `credential.service` matches the tool name. This resolves the common mismatch where tool names differ from credential service names.
- **Client `invoke_tool()` Methods** — `OpenIntentClient.invoke_tool(tool_name, agent_id, parameters)` (sync) and `AsyncOpenIntentClient.invoke_tool(tool_name, agent_id, parameters)` (async) for programmatic server-side tool invocation.
- **Agent `self.tools.invoke()` via Server Proxy** — `_ToolsProxy` on agents delegates string tool names to `client.invoke_tool()`, completing the chain: `self.tools.invoke("web_search", {...})` → server resolves grant → injects credentials → executes → returns result.
- **Invocation Audit Trail** — Every server-side tool invocation is recorded with agent ID, tool name, parameters, result, duration, and timestamp for compliance and debugging.

- **`@on_handoff` Decorator** — Lifecycle hook that fires when an agent receives work delegated from another agent. The handler receives the intent and the delegating agent's ID, allowing context-aware handoff processing distinct from fresh assignments.
- **`@on_retry` Decorator** — Lifecycle hook that fires when an intent is reassigned after a previous failure (RFC-0010). The handler receives the intent, attempt number, and last error, allowing agents to adapt retry strategy.
- **`@input_guardrail` / `@output_guardrail` Decorators** — Validation pipeline for agent processing. Input guardrails run before `@on_assignment` handlers and can reject intents. Output guardrails validate handler results before they are committed to state. Both support `GuardrailError` for rejection.
- **Built-in Coordinator Guardrails** — The `guardrails=` parameter on `@Coordinator` is now active. Supported policies: `"require_approval"` (logs decision records before assignment), `"budget_limit"` (rejects intents exceeding cost constraints), `"agent_allowlist"` (rejects delegation to agents outside the managed list).

### Fixed

- **`_ToolsProxy` duplicate class** — Removed duplicate `_ToolsProxy` definition that caused agent tool proxy to silently fail. Single definition at top of `agents.py`, constructor takes `agent` only.
- **Dead proxy code** — Removed shadowed `_MemoryProxy` and `_TasksProxy` definitions (originally at lines 47-79, shadowed by full implementations later in the file).
- **Grant matching for mismatched tool/service names** — `find_agent_grant_for_tool()` in Database class now correctly resolves grants where the tool name (e.g. `"web_search"`) differs from the credential service name (e.g. `"serpapi"`).
- **Inert `guardrails=` parameter** — The `guardrails=` parameter on `@Coordinator` was accepted but completely unused. Now wires into the input/output guardrail pipeline.

### Changed

- Tool execution priority clarified and enforced: protocol tools (remember, recall, clarify, escalate, update_status) > local `ToolDef` handlers > remote RFC-0014 server grants.
- 556+ tests passing across test_llm, test_agents, test_server suites.

---

## [0.8.1] - 2026-02-08

### Changed

- **Tool → ToolDef rename** — `Tool` is now `ToolDef`, `@tool` is now `@define_tool` for clarity. The old names remain as backwards-compatible aliases and will not be removed.
- **Type annotations** — `llm.py` is now fully type-annotated and passes mypy strict mode (previously suppressed via `# mypy: disable-error-code`).

### Added

- **LLM-Powered Agents** — Add `model=` to `@Agent` or `@Coordinator` to enable agentic tool loops with `self.think(prompt)`, streaming via `self.think_stream(prompt)`, conversation reset via `self.reset_conversation()`, and protocol-native tools (remember, recall, clarify, escalate, update_status, delegate, record_decision, create_plan).
- **Custom Tools with ToolDef** — `ToolDef(name, description, parameters, handler)` for rich tool definitions with local execution, and `@define_tool(description=, parameters=)` decorator to turn functions into `ToolDef` objects.
- **Mixed tool sources** — `tools=` on `@Agent`/`@Coordinator` accepts both `ToolDef` objects (local handlers with rich schemas) and plain strings (RFC-0014 protocol grants).
- **Automatic Tool Tracing** — Every local `ToolDef` handler invocation is automatically traced as a `tool_invocation` protocol event when the agent is connected to an OpenIntent server. Each event records tool name, arguments, result, and execution duration. Tracing is best-effort and never blocks tool execution.
- **Backwards-compatible aliases** — `Tool` = `ToolDef`, `@tool` = `@define_tool`.

### Fixed

- Unified tool execution model documentation to clarify the three-tier priority: protocol tools > local handlers (`ToolDef`) > remote protocol grants (RFC-0014 strings).

---

## [0.8.0] - 2026-02-08

### Added

- **Decorator-First Agent Abstractions**
  - `@Agent("id", memory="episodic", tools=["web_search"], auto_heartbeat=True)` — zero-boilerplate agent decorator with proxy access to `self.memory`, `self.tasks`, `self.tools`
  - `@Coordinator("id", agents=[...], strategy="parallel", guardrails=[...])` — mirrors `@Agent` with portfolio orchestration, `self.delegate()`, `self.record_decision()`, `self.decisions`
  - `Worker` for ultra-minimal single-handler agents

- **Agent Lifecycle Decorators**
  - `@on_assignment` — agent assigned to intent
  - `@on_complete` — intent completed
  - `@on_state_change(keys)` — specific state keys changed
  - `@on_event(event_type)` — specific event type received
  - `@on_task(status)` — task lifecycle event (RFC-0012)
  - `@on_trigger(name)` — named trigger fires (RFC-0017)
  - `@on_drain` — graceful shutdown signal (RFC-0016)
  - `@on_access_requested` — access request received (RFC-0011)
  - `@on_all_complete` — all portfolio intents complete

- **Coordinator Lifecycle Decorators**
  - `@on_conflict` — version conflict detected
  - `@on_escalation` — agent escalation received
  - `@on_quorum(threshold)` — voting threshold met

- **First-Class Protocol Decorators** (import from `openintent.agents`)
  - `@Plan(strategy, checkpoints)` — declarative task decomposition config (RFC-0012)
  - `@Vault(name, rotation_policy)` — credential vault declaration (RFC-0014)
  - `@Memory(tier, capacity, eviction)` — memory configuration (RFC-0015)
  - `@Trigger(type, cron)` — reactive scheduling declaration (RFC-0017)

- **Proxy Classes for Agent Self-Access**
  - `_MemoryProxy` — `self.memory.store()`, `self.memory.recall()`, `self.memory.pin()`
  - `_TasksProxy` — `self.tasks.create()`
  - `_ToolsProxy` — `self.tools.invoke()`

- **Server SDK Documentation**
  - `OpenIntentServer`, `ServerConfig`, `create_app()` programmatic usage
  - CLI entry point `openintent-server` with all options
  - `ServerConfig` reference with all configuration fields
  - Environment variable mapping

- **Built-in FastAPI Server** (`openintent.server`)
  - Implements all 17 RFCs
  - SQLAlchemy + SQLite/PostgreSQL persistence
  - API key authentication, CORS, OpenAPI docs

### Changed

- Handler discovery uses `__func__` deduplication to prevent double-invocation of bound methods
- Coordinator extends BaseAgent handler discovery with conflict/escalation/quorum types via `update()`
- Protocol decorators (`@Plan`, `@Vault`, `@Memory`, `@Trigger`) exported only from `openintent.agents` to avoid name collision with model classes in `openintent`
- All documentation updated to reflect 17 RFC coverage
- README rewritten for v0.8.0 with decorator-first examples

### Fixed

- Handler double-invocation bug in `BaseAgent._discover_handlers()` when using decorator on bound methods
- All ruff lint errors resolved (F821 undefined names, F401 unused imports, E501 line length)

## [0.7.0] - 2026-02-07

### Added

- **RFC-0011: Access-Aware Coordination v1.0** (unified permissions model)
  - Unified `permissions` field replaces separate access/delegation/context fields
  - Shorthand forms: `permissions: open`, `permissions: private`, `permissions: [agent-a, agent-b]`
  - Full object form: `policy`, `default`, `allow` (agent grants), `delegate` (delegation rules), `context` (injection config)
  - `PermissionsConfig`, `PermissionLevel`, `AllowEntry`, `DelegateConfig` typed SDK classes
  - `WorkflowAccessPolicy` export alias to avoid collision with `models.AccessPolicy`
  - Legacy field auto-conversion: old `access`/`delegation`/`context` fields parsed and converted
  - Governance-level `access_review` with approvers, timeout, on_request policy
  - Agent-level `default_permission` and `approval_required`

- **Access Control Server Endpoints**
  - ACL management: GET/PUT `/v1/intents/{id}/acl`, POST/DELETE ACL entries
  - Access requests: POST/GET `/v1/intents/{id}/access-requests`, approve/deny endpoints
  - IntentContext automatic population with permission-filtered fields
  - Capability declaration and matching for delegation

- **SDK Access Control Primitives**
  - `@on_access_requested` decorator for policy-as-code
  - `intent.ctx` automatic context injection (parent, dependencies, peers, delegated_by)
  - `intent.delegate()` for agent delegation with payload
  - `intent.temp_access()` context manager for scoped temporary access
  - `auto_request_access=True` client option for automatic 403 handling

- **Streaming Hooks Infrastructure**
  - `on_stream_start(stream_id, model, provider)` callback in `AdapterConfig`
  - `on_token(token, stream_id)` callback for real-time token processing
  - `on_stream_end(stream_id, content, chunks)` callback on completion
  - `on_stream_error(error, stream_id)` callback on failure
  - All hooks use fail-safe pattern (exceptions caught, never break main flow)
  - Helper methods on `BaseAdapter`: `_invoke_stream_start`, `_invoke_on_token`, `_invoke_stream_end`, `_invoke_stream_error`

- **Azure OpenAI Adapter** (`AzureOpenAIAdapter`)
  - Full support for Azure OpenAI deployments via `openai` package
  - Azure-specific endpoint, API version, and authentication configuration
  - Complete streaming, tool calling, and hooks support
  - Install: `pip install openintent[azure]`

- **OpenRouter Adapter** (`OpenRouterAdapter`)
  - Access 200+ models from multiple providers through unified API
  - OpenAI-compatible interface via OpenRouter's endpoint
  - Complete streaming, tool calling, and hooks support
  - Install: `pip install openintent[openrouter]`

- **RFC-0012: Task Decomposition & Planning** (Proposed)
  - Task as first-class protocol primitive with 9-state lifecycle
  - Plan as evolution of Intent Graph with checkpoints, conditions, and ordering
  - Portfolio clarified as organizational boundary (no execution semantics)
  - Task state machine: pending → ready → claimed → running → completed/failed/blocked
  - `@task` decorator, `.t()` task signatures, `.depends_on()` chaining
  - `TaskContext` with progress reporting, delegation, escalation
  - YAML workflow integration with `plan:` block

- **RFC-0013: Coordinator Governance & Meta-Coordination** (Proposed)
  - Coordinator formalized as governed agent with coordinator lease
  - Supervisor hierarchies terminating at human authority
  - Declarative guardrails: budget, scope, temporal, review constraints
  - Decision records with rationale and alternatives considered
  - Heartbeat-based failover and coordinator handoff
  - Composite coordination modes: propose-approve, act-notify, act-audit
  - `@coordinator` decorator, `CoordinatorContext` API
  - New permission grants: `coordinate`, `approve`, `supervise`

- **RFC-0014: Credential Vaults & Tool Scoping** (Proposed)
  - Credential Vaults for encrypted storage of external service credentials
  - Tool Grants with scoped permissions, constraints, and expiry
  - Server-side Tool Proxy — agents never see raw credentials
  - Grant delegation with depth limits and cascading revocation
  - Tool requirements on tasks with lease-time grant validation
  - Tool Registry for service/tool discovery and parameter validation
  - Full audit trail: every tool invocation and grant lifecycle event logged
  - Integration with RFC-0009 (cost tracking), RFC-0011 (access control), RFC-0013 (guardrails)
  - Standalone agent direct grants (no coordinator required)
  - YAML workflow `tools:` block for declaring grants and requirements
  - MCP compatibility: grants provide governance layer over MCP tool transport

- **RFC-0015: Agent Memory & Persistent State** (Proposed)
  - Three-tier memory model: working (task-scoped), episodic (agent-scoped), semantic (shared)
  - Structured key-value entries with namespace, tags, versioning, and TTL
  - Optimistic concurrency via version numbers and `If-Match` headers
  - Tag-based filter queries (AND/OR logic) with semantic search as extension point
  - Working memory auto-archival on task completion with event log snapshot
  - Episodic memory with configurable capacity, LRU eviction, and pinning
  - Semantic memory with namespace-level permissions following RFC-0011 model
  - Agent resumability: replacement agents read previous agent's working memory
  - Batch operations for atomic multi-entry updates
  - Memory lifecycle events: created, updated, deleted, archived, evicted, expired
  - Integration with RFC-0005 (attachments for large payloads), RFC-0008 (context packing), RFC-0012 (task memory policy), RFC-0013 (guardrails)
  - SDK `client.memory` namespace with automatic version tracking
  - YAML workflow `memory:` block for declaring namespaces, capacity, and eviction

- **RFC-0016: Agent Lifecycle & Health** (Proposed)
  - Formal agent registration with capabilities, capacity, and heartbeat configuration
  - Agent record as protocol-level primitive with role_id and agent_id distinction
  - Status lifecycle state machine: registering → active → draining → deregistered, active → unhealthy → dead
  - Pull-based heartbeat protocol with jitter-tolerant thresholds and drift detection
  - Two-threshold health detection: unhealthy (warning) then dead (action)
  - Network partition behavior: heartbeats detect problems, leases (RFC-0003) prevent split-brain
  - Graceful drain with configurable timeout and server-initiated drain via pending_commands
  - Agent registry with capability-based discovery and capacity-aware querying
  - Agent pools defined via shared role_id; assignment logic explicitly out of scope
  - Instance identity (agent_id) vs. role identity (role_id) with memory continuity (RFC-0015)
  - Lifecycle death explicitly triggers lease expiry (RFC-0003 integration)
  - Uniform registration: @Agent decorator and imperative path produce identical protocol effects
  - Registration optional for standalone agents with direct grants (RFC-0014)
  - Capacity advisory, not enforced; guardrails (RFC-0013) can add hard limits
  - YAML workflow `agents:` block for declaring lifecycle configuration and pool hints
  - API: POST/GET/DELETE /agents, PATCH /agents/{id}/status, POST /agents/{id}/heartbeat

- **RFC-0017: Triggers & Reactive Scheduling** (Proposed)
  - Trigger as intent factory: standing declarations that create intents when conditions are met
  - Three trigger types: schedule (cron-based), event (protocol-reactive), webhook (external HTTP)
  - Trigger record as first-class protocol object with version, fire_count, and lineage tracking
  - Schedule triggers with cron expressions, timezone support, time windows, and one-time schedules
  - Event triggers with 11 standard event types and glob-pattern filtering
  - Webhook triggers with signature verification, payload transformation, and secure secret handling
  - Intent templates with {{ }} expression syntax for dynamic value injection
  - Trigger-to-intent lineage: created_by, trigger_id, trigger_depth, trigger_chain
  - Deduplication semantics: allow, skip, queue — preventing the "fires faster than resolves" footgun
  - Cascading namespace governance: global triggers cascade down, namespaces retain local authority
  - Namespace trigger policies: allow/block global triggers, type whitelists, context injection
  - Cascade depth limit (default: 10) prevents infinite trigger chains
  - Trigger lifecycle: enabled, disabled, deleted (fire history retained for audit)
  - Manual fire endpoint for testing and debugging
  - YAML workflow `triggers:` block with creates shorthand
  - SDK `client.triggers` namespace with create, list, fire, update, history, delete
  - API: POST/GET/PATCH/DELETE /triggers, POST /triggers/{id}/fire, GET /triggers/{id}/history

### Changed

- Updated all YAML workflow examples to use unified `permissions` field
- Updated all documentation to RFC-0011 v1.0 format
- Version bump to 0.7.0

## [0.6.0] - 2026-02-05

### Added

- **Distributed Tracing & Full Observability**
  - Workflow tree structure showing orchestrator → intent flow
  - LLM operations summary with tokens, duration, and cost per call
  - Cost rollup totaling tokens and estimated cost across all operations
  - Event timeline for complete audit trail

- **LiteLLM Adapter**
  - Universal adapter supporting 100+ LLM providers via LiteLLM
  - Automatic event logging for all supported providers

### Changed

- Adapter events now include `prompt_tokens`, `completion_tokens`, `total_tokens`, `duration_ms`
- Version bump to 0.6.0

## [0.5.0] - 2026-02-03

### Added

- **YAML Workflow Specification**
  - Declarative multi-agent workflow definitions in YAML
  - `WorkflowSpec` class with `from_yaml()`, `from_string()`, `to_portfolio_spec()` methods
  - CLI commands: `openintent run`, `openintent validate`, `openintent list`, `openintent new`
  - Full feature support: dependencies, parallel execution, retry policies, cost tracking, governance
  - LLM configuration block for provider/model settings
  - Leasing and attachment declarations per phase

- **Workflow Validation**
  - `validate_workflow()` function with `WorkflowValidationError`
  - DAG cycle detection
  - Agent and dependency reference validation
  - Warning system for best practices

- **Example Workflows**
  - `hello_world.yaml` - Minimal single-phase workflow
  - `research_assistant.yaml` - Two-phase research pipeline
  - `data_pipeline.yaml` - Four-phase ETL processing
  - `content_pipeline.yaml` - Parallel content creation
  - `compliance_review.yaml` - Full RFC showcase with governance

### Changed

- Version bump to 0.5.0

## [0.4.5] - 2026-02-02

### Fixed

- **IntentStatus Enum**: Aligned SDK with protocol spec
  - Now uses: `draft`, `active`, `blocked`, `completed`, `abandoned`
  - Added missing `DRAFT` and `ABANDONED` statuses
  - Removed deprecated `CANCELLED` (use `ABANDONED` instead)
  - Fixes "ValueError: 'draft' is not a valid IntentStatus" when using SDK with servers

- **EventType Enum**: Aligned SDK with all server event types
  - Renamed `CREATED` → `INTENT_CREATED` (value: `intent_created`)
  - Renamed `STATE_UPDATED` → `STATE_PATCHED` (value: `state_patched`)
  - Added: `DEPENDENCY_ADDED`, `DEPENDENCY_REMOVED` (RFC-0002)
  - Added: `ATTACHMENT_ADDED` (RFC-0005)
  - Added: `PORTFOLIO_CREATED`, `ADDED_TO_PORTFOLIO`, `REMOVED_FROM_PORTFOLIO` (RFC-0004)
  - Added: `FAILURE_RECORDED` (RFC-0010)
  - Legacy aliases `CREATED` and `STATE_UPDATED` preserved for backward compatibility

- **LeaseStatus Enum**: Added missing `REVOKED` status

- **Intent Model**: 
  - Changed `constraints` from `list[str]` to `dict[str, Any]` to match server spec
  - Added `created_by` and `confidence` fields to match server response

## [0.4.4] - 2026-02-02

### Fixed

- **Intent Creation**: Client now sends `created_by` field (using `agent_id`) when creating intents
- **Server Compatibility**: Server now accepts optional `created_by` field, defaulting to API key
- **Demo Script**: Fixed 422 validation errors in `/try` demo by ensuring proper authentication

## [0.4.0] - 2026-02-01

### Added

- **Built-in OpenIntent Server** (`server/` module)
  - FastAPI-based server implementing all 17 RFCs
  - SQLite by default (zero-config), PostgreSQL support
  - CLI entry point: `openintent-server`
  - Module entry point: `python -m openintent.server`
  - Programmatic access via `OpenIntentServer` class

- **Server Features**
  - Complete Intent CRUD with optimistic concurrency
  - Append-only event log
  - Agent assignment and lease management
  - Portfolio management with memberships
  - Attachments, cost tracking, retry policies
  - SSE subscriptions for real-time updates
  - Governance (arbitration and decisions)
  - OpenAPI documentation at `/docs`
  - Protocol discovery at `/.well-known/openintent.json`

- **Server Configuration**
  - `ServerConfig` dataclass for all settings
  - Environment variable support
  - Configurable API keys, CORS, logging

- **New Installation Options**
  - `pip install openintent[server]` - Server dependencies
  - `pip install openintent[all]` - Everything included

### Changed

- Updated description to "Python SDK and Server for the OpenIntent Coordination Protocol"
- Development status upgraded to Beta
- Version bump to 0.4.0

## [0.3.0] - 2026-02-01

### Added

- **High-Level Agent Abstractions** (`agents.py` module)
  - `@Agent` decorator for minimal-boilerplate agent creation
  - `Coordinator` class for portfolio-based multi-agent orchestration
  - `Worker` class for ultra-minimal single-purpose agents
  - `BaseAgent` class for custom agent implementations

- **Declarative Event Handlers**
  - `@on_assignment` - Called when agent is assigned to an intent
  - `@on_complete` - Called when an intent completes
  - `@on_lease_available(scope)` - Called when a scope lease becomes available
  - `@on_state_change(keys)` - Called when intent state changes
  - `@on_event(type)` - Called for specific event types
  - `@on_all_complete` - Called when all portfolio intents complete

- **Portfolio DSL**
  - `PortfolioSpec` - Declarative portfolio definition
  - `IntentSpec` - Intent specification with `depends_on` for dependencies
  - Automatic topological sorting of intent dependencies
  - Automatic intent creation and agent assignment

- **Agent Configuration**
  - `AgentConfig` dataclass for configuration
  - Auto-subscribe to SSE events
  - Auto-patch state from handler return values
  - Auto-complete intents after successful processing

- **New Examples**
  - `examples/agents/research_agent.py` - Decorator-based agent
  - `examples/agents/coordinator.py` - Portfolio orchestration
  - `examples/agents/worker.py` - Minimal worker pattern
  - `examples/agents/README.md` - Comprehensive documentation

### Changed

- Version bump to 0.3.0

## [0.2.0] - 2026-02-01

### Added

- **Real-Time SSE Streaming** (`streaming.py` module)
  - `SSEStream` - Iterator-based SSE event streaming
  - `SSESubscription` - Background thread event processing
  - `EventQueue` - Queue-based non-blocking event consumption
  - `SSEEvent` and `SSEEventType` models
  - Three subscription levels: intent, portfolio, agent

- **Provider Adapters** (`adapters/` directory)
  - `OpenAIAdapter` - Wraps OpenAI clients with automatic event logging
  - `AnthropicAdapter` - Wraps Anthropic clients with automatic event logging
  - `AdapterConfig` - Configuration for adapter behavior
  - Automatic LLM request, tool call, and stream logging

- **LLM Integration Events**
  - `TOOL_CALL_STARTED`, `TOOL_CALL_COMPLETED`, `TOOL_CALL_FAILED`
  - `LLM_REQUEST_STARTED`, `LLM_REQUEST_COMPLETED`, `LLM_REQUEST_FAILED`
  - `STREAM_STARTED`, `STREAM_CHUNK`, `STREAM_COMPLETED`, `STREAM_CANCELLED`

- **New Models**
  - `ToolCallPayload` - Tool call event data
  - `LLMRequestPayload` - LLM request event data
  - `StreamState`, `StreamStatus` - Streaming state tracking

## [0.1.0] - 2026-02-01

### Added

- Initial release of OpenIntent SDK for Python
- Synchronous client (`OpenIntentClient`)
- Asynchronous client (`AsyncOpenIntentClient`) with full feature parity
- Full Intent CRUD operations (RFC-0001)
- State management with optimistic concurrency control via `If-Match` headers
- Append-only event logging for audit trails (RFC-0002)
- Lease-based scope ownership with acquire, renew, and release (RFC-0003)
- Governance endpoints: arbitration requests and decisions (RFC-0003)
- File attachments with base64 encoding (RFC-0005)
- Webhook subscriptions for real-time updates (RFC-0006)
- Cost tracking with summaries by agent and type (RFC-0009)
- Retry policies and failure recording (RFC-0010)
- Portfolio management for grouping related intents
- Agent assignment and management
- Protocol discovery via `.well-known/openintent.json`
- Context manager support for automatic lease cleanup
- Comprehensive input validation module (`validation.py`)
- Type-safe models using dataclasses
- OpenAI multi-agent coordination example
- Streaming with background intent updates example
- Authentication patterns example
- Basic usage example
- Unit tests for models and validation

### Models

- `Intent` - Core intent object with state, constraints, and versioning
- `IntentState` - Flexible key-value state container
- `IntentEvent` - Immutable audit log entry
- `IntentLease` - Scope ownership lease with expiration
- `ArbitrationRequest` - Governance arbitration request
- `Decision` - Governance decision record
- `Attachment` - File attachment with metadata
- `Subscription` - Webhook subscription configuration
- `CostRecord` - Cost tracking entry
- `CostSummary` - Aggregated cost statistics
- `RetryPolicy` - Retry configuration
- `Failure` - Failure record for retry tracking
- `Portfolio` - Intent grouping container
- `PortfolioIntent` - Portfolio membership with role and priority

### Validation Helpers

- `validate_required` - Check for required fields
- `validate_string_length` - Enforce string length limits
- `validate_positive_int` - Ensure positive integers
- `validate_non_negative` - Ensure non-negative numbers
- `validate_uuid` - UUID format validation
- `validate_url` - URL format validation
- `validate_scope` - Scope identifier validation
- `validate_agent_id` - Agent ID format validation
- `validate_intent_create` - Composite intent creation validator
- `validate_lease_acquire` - Composite lease acquisition validator
- `validate_cost_record` - Composite cost record validator
- `validate_subscription` - Composite subscription validator

### Exceptions

- `OpenIntentError` - Base exception for all SDK errors
- `ConflictError` - Version conflict (409)
- `NotFoundError` - Resource not found (404)
- `LeaseConflictError` - Lease collision (409)
- `ValidationError` - Request validation failure (400)
- `InputValidationError` - Client-side input validation (inherits from ValidationError)
