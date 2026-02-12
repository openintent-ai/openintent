# RFC-0014: Credential Vaults & Tool Scoping

**Status:** Proposed  
**Created:** 2026-02-08  
**Authors:** OpenIntent Contributors  
**Requires:** RFC-0001 (Intents), RFC-0003 (Leasing), RFC-0009 (Cost Tracking), RFC-0011 (Access Control), RFC-0012 (Task Decomposition & Planning), RFC-0013 (Coordinator Governance)

---

## Abstract

This RFC introduces **Credential Vaults** and **Tool Grants** as protocol-level constructs for managing agent access to external services. Agents never receive raw credentials. Instead, the protocol provides a secure proxy layer where users register their service credentials in encrypted vaults, define scoped grants specifying which agents can use which services with what permissions, and all external tool invocations are executed server-side, logged as auditable events, and constrained by the same guardrail system defined in RFC-0013.

## Motivation

The OpenIntent protocol governs how agents coordinate *with each other*. But agents don't just talk to each other — they interact with external services: payment processors, source control, databases, email providers, cloud infrastructure, and more. Today, this creates five critical gaps:

1. **Credential exposure.** Most agent frameworks pass raw API keys to the agent — either as environment variables, context window content, or tool configuration. Once an agent has a key, there is no protocol-level mechanism to prevent misuse, logging of the key itself, or lateral movement to other services.

2. **No isolation between agents.** If a billing agent and a code review agent both serve the same user, they typically share the same credential store or receive credentials through the same mechanism. There is no protocol-level boundary ensuring the billing agent cannot access the code review agent's GitHub token.

3. **No scope limitation within a service.** An agent that needs to *read* Stripe charges should not be able to *create* refunds. But most credential systems grant service-level access, not operation-level access. The protocol should express fine-grained scopes.

4. **No audit trail for external actions.** The protocol logs intent events and task state transitions, but when an agent calls an external API, that action is invisible to the audit trail. The user cannot see what the agent did in their Stripe account, GitHub repository, or database.

5. **No delegation of tool access.** When a coordinator delegates a task to a worker agent, there is no protocol mechanism for the coordinator to pass down a *subset* of its tool grants. The worker either inherits everything (too permissive) or nothing (non-functional).

Without these constructs, agents can coordinate within the protocol but cannot safely interact with external services on behalf of a user.

## Terminology

| Term | Definition |
|------|-----------|
| **Credential Vault** | A secure, encrypted store of external service credentials owned by a user or organization |
| **Credential** | An encrypted record containing the authentication material for an external service (API key, OAuth token, connection string, etc.) |
| **Tool** | A callable operation backed by an external service credential (e.g., `stripe.charges.create`, `github.issues.list`) |
| **Tool Grant** | A permission linking an agent to a specific set of tools with defined scopes, constraints, and an expiry |
| **Tool Proxy** | The server-side component that executes external service calls on behalf of an agent using stored credentials, without exposing credentials to the agent |
| **Grant Delegation** | The act of a coordinator passing a subset of its tool grants to a worker agent for the duration of a task |
| **Tool Invocation** | A single call to an external service, executed through the tool proxy, logged as an event |
| **Scope** | A granular permission within a service defining what operations are allowed (e.g., `read`, `write`, `admin`) |

## Design

### 1. Credential Vault

A Credential Vault is a user-owned encrypted store. It holds credentials for external services and metadata about those credentials. The vault itself is never accessible to agents — only the server's tool proxy reads from it.

#### 1.1 Vault Object

```json
{
  "id": "vault_01HXYZ",
  "owner_id": "user_01HABC",
  "name": "acme-corp-production",
  "created_at": "2026-02-08T10:00:00Z",
  "credentials": ["cred_01H001", "cred_01H002", "cred_01H003"]
}
```

#### 1.2 Credential Object

```json
{
  "id": "cred_01H001",
  "vault_id": "vault_01HXYZ",
  "service": "stripe",
  "label": "stripe-production",
  "auth_type": "api_key",
  "encrypted_material": "...",
  "scopes_available": [
    "charges.read",
    "charges.create",
    "refunds.create",
    "customers.read",
    "customers.write"
  ],
  "metadata": {
    "environment": "production",
    "account_id": "acct_1234"
  },
  "created_at": "2026-02-08T10:00:00Z",
  "rotated_at": "2026-02-08T10:00:00Z",
  "expires_at": null
}
```

Key properties:

- **`encrypted_material`** is never returned by any API endpoint. It exists only in the vault's encrypted storage and is read exclusively by the tool proxy at invocation time.
- **`scopes_available`** declares the full set of operations this credential supports. Grants (Section 2) select subsets of these scopes.
- **`auth_type`** supports `api_key`, `oauth2_token`, `oauth2_client_credentials`, `bearer_token`, `basic_auth`, `connection_string`, and `custom`.
- **`rotated_at`** tracks the last credential rotation. The protocol SHOULD support automated rotation where the service supports it.

#### 1.3 Credential Lifecycle

```
created → active → rotated → active (new material)
                  → expired → re-provisioned → active
                  → revoked (terminal)
```

Credential rotation replaces the encrypted material without changing the credential ID or invalidating existing grants. This is critical: agents and grants reference credential IDs, not raw keys, so rotation is transparent.

### 2. Tool Grants

A Tool Grant links an agent to a credential with scoped permissions. Grants are the authorization layer between "this credential exists" and "this agent can use it."

#### 2.1 Grant Object

```json
{
  "id": "grant_01HDEF",
  "credential_id": "cred_01H001",
  "agent_id": "agent_billing_01",
  "granted_by": "user_01HABC",
  "scopes": ["charges.read", "charges.create"],
  "constraints": {
    "max_invocations_per_hour": 100,
    "max_cost_per_invocation": null,
    "allowed_parameters": {
      "currency": ["usd", "eur"],
      "amount_max": 50000
    },
    "denied_parameters": {
      "metadata.test_mode": [true]
    },
    "ip_allowlist": null
  },
  "delegatable": true,
  "delegation_depth": 1,
  "context": {
    "intent_id": null,
    "plan_id": null,
    "task_id": null
  },
  "expires_at": "2026-03-08T10:00:00Z",
  "created_at": "2026-02-08T10:00:00Z",
  "revoked_at": null
}
```

Key properties:

- **`scopes`** is a subset of the credential's `scopes_available`. An agent can never exceed the credential's capabilities.
- **`constraints`** define operational limits: rate limits, cost caps, parameter restrictions, and network restrictions.
- **`delegatable`** controls whether this agent can pass this grant (or a subset) to another agent.
- **`delegation_depth`** limits how many levels deep a grant can be delegated. 0 = non-delegatable. 1 = can delegate once but the recipient cannot re-delegate. `null` = unlimited.
- **`context`** optionally binds the grant to a specific intent, plan, or task. A grant bound to a task is automatically revoked when the task completes or is cancelled.
- **`expires_at`** provides time-bounded access. Grants SHOULD have an expiry; indefinite grants MUST be explicitly opted into.

#### 2.2 Grant Models

The protocol supports two grant models, reflecting the two primary ways agents operate.

##### 2.2.1 Direct Grants (Standalone Agents)

A **direct grant** is created by a user and assigned to an agent with no coordinator or delegation chain involved. This is the simplest path and the default for single-purpose agents.

```
User (vault owner)
  ├─ Agent A (direct grant: stripe, [charges.read])
  ├─ Agent B (direct grant: github, [repo.read, issues.write])
  └─ Agent C (direct grant: postgres, [query.read])
```

Direct grants have:
- **`delegatable: false`** by default. A standalone agent has no reason to delegate.
- **`delegation_depth: 0`** by default. No delegation chain.
- **`context`** may optionally bind the grant to a specific intent, but is typically unbound (`null`) — the agent can use the tool for any work it performs.

A direct grant is the simplest object:

```json
{
  "id": "grant_01HXYZ",
  "credential_id": "cred_01H001",
  "agent_id": "agent_billing_01",
  "granted_by": "user_01HABC",
  "scopes": ["charges.read"],
  "constraints": {
    "max_invocations_per_hour": 100
  },
  "delegatable": false,
  "delegation_depth": 0,
  "context": {},
  "expires_at": "2026-03-08T10:00:00Z",
  "created_at": "2026-02-08T10:00:00Z",
  "revoked_at": null
}
```

For the standalone agent, the invocation flow is simple: the agent discovers its grants, selects the appropriate tool, and invokes through the proxy. No coordinator, no plan, no task context required. The `context` field in the invocation request is optional:

```json
{
  "grant_id": "grant_01HXYZ",
  "tool": "stripe.charges.read",
  "parameters": { "charge_id": "ch_abc" }
}
```

The proxy validates the grant and executes. The audit trail logs the invocation against the agent, even without an intent context. This ensures standalone agents are still fully auditable.

##### 2.2.2 Delegated Grants (Coordinated Agents)

A **delegated grant** flows through a coordination hierarchy. A coordinator receives a direct grant from the user, then delegates subsets to worker agents as tasks are assigned.

```
User (vault owner)
  └─ Coordinator (direct grant from user)
       ├─ Worker A (delegated by coordinator, scopes ⊆ coordinator's)
       │    └─ Sub-worker (delegated by Worker A, if delegation_depth allows)
       └─ Worker B (delegated by coordinator, different scope subset)
```

**Invariant:** A delegated grant can never exceed the grantor's grant. If a coordinator has `[charges.read, charges.create]`, it can delegate `[charges.read]` to a worker but never `[refunds.create]`.

**Invariant:** Delegation depth decrements at each level. If the coordinator's grant has `delegation_depth: 2`, the delegated grant has `delegation_depth: 1`, and the next level has `delegation_depth: 0` (non-delegatable).

##### 2.2.3 Mixed Model

A single agent can hold both direct grants and delegated grants simultaneously. For example, an agent might have a direct grant for a logging service (always available) and receive a delegated grant for Stripe (only during a specific task). The proxy resolves grants independently per invocation — it does not merge or combine grants.

#### 2.3 Grant Discovery

An agent SHOULD be able to discover its available tools without prior knowledge of vaults, credentials, or grant IDs. The protocol provides a discovery endpoint that returns the agent's effective tool surface:

```
GET /api/v1/tools/granted?agent_id=agent_billing_01
```

Response:

```json
{
  "agent_id": "agent_billing_01",
  "tools": [
    {
      "grant_id": "grant_01HXYZ",
      "service": "stripe",
      "tool": "charges.read",
      "constraints": {
        "max_invocations_per_hour": 100
      },
      "source": "direct",
      "expires_at": "2026-03-08T10:00:00Z"
    },
    {
      "grant_id": "grant_01HDEF",
      "service": "stripe",
      "tool": "charges.create",
      "constraints": {
        "max_invocations_per_hour": 50,
        "amount_max": 10000
      },
      "source": "delegated",
      "delegated_from": "coordinator_01",
      "context": { "task_id": "task_01HXYZ" },
      "expires_at": "2026-02-08T12:00:00Z"
    }
  ]
}
```

The `source` field distinguishes direct grants from delegated grants. This is informational — the invocation flow is identical for both. The agent simply picks the appropriate `grant_id` and invokes the tool.

#### 2.4 Grant Lifecycle

```
created → active → expired (terminal)
                  → revoked (terminal)
                  → suspended → active (resumable)
```

Revoking a grant cascades: all grants delegated from the revoked grant are also revoked. This ensures that removing a coordinator's access immediately removes all downstream access.

### 3. Tool Proxy

The Tool Proxy is the server-side component that executes external service calls. Agents never make external calls directly — they submit tool invocation requests to the proxy, which validates the request against grants and constraints, executes the call using stored credentials, and returns the result.

#### 3.1 Invocation Request

```json
{
  "grant_id": "grant_01HDEF",
  "tool": "stripe.charges.create",
  "parameters": {
    "amount": 2500,
    "currency": "usd",
    "customer": "cus_abc123",
    "description": "Q1 compliance report generation fee"
  },
  "idempotency_key": "inv_01HXYZ_attempt_1",
  "context": {
    "intent_id": "intent_01HABC",
    "task_id": "task_01HXYZ",
    "agent_id": "agent_billing_01"
  }
}
```

#### 3.2 Invocation Flow

```
Agent                    Tool Proxy                    External Service
  │                          │                              │
  │  invoke(grant, tool,     │                              │
  │         parameters)      │                              │
  │─────────────────────────>│                              │
  │                          │                              │
  │                          │  1. Validate grant is active  │
  │                          │  2. Check scopes include tool │
  │                          │  3. Validate constraints      │
  │                          │     (rate, cost, params)      │
  │                          │  4. Decrypt credential        │
  │                          │  5. Execute call ────────────>│
  │                          │                               │
  │                          │  6. Receive response <────────│
  │                          │  7. Log invocation event      │
  │                          │  8. Update rate counters      │
  │                          │  9. Redact credential from    │
  │                          │     response if present       │
  │                          │                               │
  │  result (no credential)  │                               │
  │<─────────────────────────│                               │
```

**Step 3 (constraint validation)** checks:
- Rate limit: Has this grant exceeded `max_invocations_per_hour`?
- Parameter restrictions: Are all parameters within `allowed_parameters`? Are any in `denied_parameters`?
- Context binding: If the grant is bound to a task, is that task in a `running` state?
- Guardrails (RFC-0013): If the coordinator has budget guardrails, does this invocation exceed them?

**Step 9 (redaction)** ensures that if the external service response accidentally includes credential material (e.g., in error messages or debug output), it is stripped before returning to the agent.

#### 3.3 Invocation Response

```json
{
  "invocation_id": "inv_01HXYZ",
  "status": "success",
  "result": {
    "id": "ch_1234",
    "amount": 2500,
    "currency": "usd",
    "status": "succeeded"
  },
  "cost": {
    "api_units": 1,
    "estimated_cost_usd": 0.02
  },
  "duration_ms": 342,
  "timestamp": "2026-02-08T10:30:00Z"
}
```

#### 3.4 Invocation Errors

```json
{
  "invocation_id": "inv_01HXYZ",
  "status": "denied",
  "error": {
    "code": "GRANT_SCOPE_INSUFFICIENT",
    "message": "Grant grant_01HDEF does not include scope 'refunds.create'",
    "grant_id": "grant_01HDEF",
    "requested_scope": "refunds.create",
    "available_scopes": ["charges.read", "charges.create"]
  }
}
```

Error codes:

| Code | Meaning |
|------|---------|
| `GRANT_NOT_FOUND` | The specified grant does not exist |
| `GRANT_EXPIRED` | The grant has passed its `expires_at` |
| `GRANT_REVOKED` | The grant has been revoked |
| `GRANT_SUSPENDED` | The grant is temporarily suspended |
| `GRANT_SCOPE_INSUFFICIENT` | The requested tool is not in the grant's scopes |
| `GRANT_RATE_LIMITED` | The grant has exceeded its rate limit |
| `GRANT_PARAMETER_DENIED` | A parameter violates the grant's constraints |
| `GRANT_CONTEXT_MISMATCH` | The grant is bound to a different intent/task than the invocation context |
| `CREDENTIAL_EXPIRED` | The underlying credential has expired |
| `CREDENTIAL_REVOKED` | The underlying credential has been revoked |
| `PROXY_ERROR` | The tool proxy failed to execute the call (network, timeout, etc.) |
| `SERVICE_ERROR` | The external service returned an error |

### 4. Tool Requirements on Tasks

RFC-0012 Tasks gain an optional `requires_tools` field that declares what external service access a task needs. This enables the server to match tasks to agents that have appropriate grants.

#### 4.1 Task Tool Requirements

```json
{
  "id": "task_01HXYZ",
  "name": "create_invoice",
  "requires_tools": [
    {
      "service": "stripe",
      "scopes": ["charges.create", "customers.read"],
      "required": true
    },
    {
      "service": "email",
      "scopes": ["send"],
      "required": false
    }
  ]
}
```

- **`required: true`** — The task cannot be claimed by an agent that lacks this grant. The lease acquisition (RFC-0003) is rejected.
- **`required: false`** — The task can proceed without this grant, but the agent may skip functionality that depends on it.

#### 4.2 Lease Validation

When an agent attempts to acquire a lease on a task with `requires_tools`, the server performs grant matching:

```
For each required tool in task.requires_tools:
  1. Find active grants for this agent matching the service
  2. Check that the grant's scopes include all required scopes
  3. Check that the grant is not expired, revoked, or suspended
  4. Check that the grant's context allows this intent/task
  5. If any required tool has no matching grant → reject lease with
     INSUFFICIENT_TOOL_ACCESS
```

This is evaluated at lease acquisition time, not at invocation time. The agent knows before starting work whether it has the necessary access.

### 5. Grant Delegation in Plans

When a coordinator creates a plan and assigns tasks, it can delegate subsets of its tool grants to worker agents. This is the mechanism by which tool access flows through the coordination hierarchy.

#### 5.1 Delegation Request

```json
{
  "action": "delegate_grant",
  "source_grant_id": "grant_01HDEF",
  "target_agent_id": "agent_worker_01",
  "scopes": ["charges.read"],
  "constraints": {
    "max_invocations_per_hour": 10
  },
  "context": {
    "task_id": "task_01HXYZ"
  },
  "expires_at": "2026-02-08T12:00:00Z"
}
```

Delegation rules:

1. The delegated scopes MUST be a subset of the source grant's scopes.
2. The delegated constraints MUST be equal to or more restrictive than the source grant's constraints.
3. The source grant's `delegatable` MUST be `true`.
4. The source grant's `delegation_depth` MUST be > 0. The delegated grant's depth is `source_depth - 1`.
5. If the source grant has a `context` binding, the delegated grant's context must be within that scope (same intent, or a child task of the same plan).
6. The delegated grant's `expires_at` MUST be ≤ the source grant's `expires_at`.

#### 5.2 Automatic Delegation

When a coordinator assigns a task, the server can automatically create delegated grants based on the task's `requires_tools` and the coordinator's grants. This reduces boilerplate:

```
Coordinator assigns task_01HXYZ to agent_worker_01
Task requires: stripe.charges.read

Server checks coordinator's grants:
  → grant_01HDEF includes stripe.charges.read
  → grant_01HDEF.delegatable = true

Server auto-creates:
  → delegated_grant for agent_worker_01
  → scopes: [charges.read] (minimum needed)
  → context: bound to task_01HXYZ
  → expires_at: min(grant.expires_at, task.deadline)
```

Automatic delegation follows the **principle of least privilege**: only the scopes required by the task are delegated, never the coordinator's full grant.

#### 5.3 Cascading Revocation

When a grant is revoked, all grants delegated from it are also revoked:

```
User revokes coordinator's grant_01HDEF
  → All grants delegated from grant_01HDEF are revoked
    → All grants delegated from those are revoked
      → ... recursively
```

This ensures that removing a coordinator's access immediately removes all downstream access, regardless of delegation depth.

### 6. Audit Trail

Every tool invocation and grant lifecycle event is logged as an intent event (RFC-0001), creating a complete audit trail of what agents did with external services.

#### 6.1 Tool Invocation Event

```json
{
  "type": "tool.invoked",
  "intent_id": "intent_01HABC",
  "task_id": "task_01HXYZ",
  "agent_id": "agent_billing_01",
  "data": {
    "invocation_id": "inv_01HXYZ",
    "grant_id": "grant_01HDEF",
    "service": "stripe",
    "tool": "charges.create",
    "parameters_summary": {
      "amount": 2500,
      "currency": "usd"
    },
    "status": "success",
    "duration_ms": 342,
    "cost": {
      "api_units": 1,
      "estimated_cost_usd": 0.02
    }
  },
  "timestamp": "2026-02-08T10:30:00Z"
}
```

Note: The `parameters_summary` MAY omit sensitive fields (e.g., customer PII). The tool proxy configuration determines which fields are logged and which are redacted.

#### 6.2 Grant Lifecycle Events

| Event Type | Trigger |
|------------|---------|
| `grant.created` | A new tool grant is created |
| `grant.delegated` | A grant is delegated to another agent |
| `grant.revoked` | A grant is revoked (includes cascade) |
| `grant.expired` | A grant reaches its expiry |
| `grant.suspended` | A grant is temporarily suspended |
| `grant.resumed` | A suspended grant is reactivated |

#### 6.3 Credential Lifecycle Events

| Event Type | Trigger |
|------------|---------|
| `credential.created` | A new credential is added to a vault |
| `credential.rotated` | A credential's material is replaced |
| `credential.expired` | A credential reaches its expiry |
| `credential.revoked` | A credential is permanently revoked |

### 7. Integration with Existing RFCs

#### 7.1 RFC-0009 (Cost Tracking)

Tool invocation costs are tracked as part of the intent's cost ledger. Each invocation's `cost` field contributes to the task and intent cost totals:

```json
{
  "cost_entry": {
    "category": "external_tool",
    "service": "stripe",
    "tool": "charges.create",
    "amount_usd": 0.02,
    "invocation_id": "inv_01HXYZ"
  }
}
```

Coordinator guardrails (RFC-0013) can set budget limits that include external tool costs, preventing agents from making expensive external calls beyond approved thresholds.

#### 7.2 RFC-0011 (Access Control)

Tool grants extend the RFC-0011 permission model with a new permission type:

| Permission | Meaning |
|------------|---------|
| `tools.invoke` | Agent can invoke tools via granted access |
| `tools.delegate` | Agent can delegate tool grants to other agents |
| `tools.manage` | Agent can create, revoke, and manage grants (typically user-only) |

These permissions are checked in addition to grant-level authorization. An agent must have both the `tools.invoke` protocol permission AND an active grant for the specific service and scope.

#### 7.3 RFC-0013 (Coordinator Governance)

Coordinator guardrails gain tool-related constraints:

```json
{
  "guardrails": {
    "max_tool_invocations": 500,
    "max_tool_cost_usd": 25.00,
    "allowed_services": ["stripe", "github"],
    "denied_services": ["aws"],
    "require_approval_for": ["stripe.refunds.create"],
    "auto_delegate": true
  }
}
```

- **`max_tool_invocations`** — Total external calls the coordinator and its delegated agents can make.
- **`max_tool_cost_usd`** — Budget cap for external service costs.
- **`allowed_services` / `denied_services`** — Whitelist or blacklist of services.
- **`require_approval_for`** — Specific tools that require supervisor approval before each invocation.
- **`auto_delegate`** — Whether the server should automatically delegate grants when the coordinator assigns tasks (Section 5.2).

### 8. Tool Registry

To enable `requires_tools` matching and grant validation, the protocol defines a tool registry — a catalog of available tools and their scopes for each service.

#### 8.1 Service Definition

```json
{
  "service": "stripe",
  "version": "2024-01",
  "tools": {
    "charges.create": {
      "description": "Create a new charge",
      "scope": "charges.create",
      "parameters": {
        "amount": { "type": "integer", "required": true },
        "currency": { "type": "string", "required": true },
        "customer": { "type": "string", "required": false },
        "description": { "type": "string", "required": false }
      },
      "returns": {
        "id": "string",
        "amount": "integer",
        "status": "string"
      },
      "idempotent": true,
      "estimated_cost_usd": 0.02
    },
    "charges.read": {
      "description": "Retrieve a charge by ID",
      "scope": "charges.read",
      "parameters": {
        "charge_id": { "type": "string", "required": true }
      },
      "returns": {
        "id": "string",
        "amount": "integer",
        "status": "string"
      },
      "idempotent": true,
      "estimated_cost_usd": 0.001
    }
  }
}
```

The tool registry enables:
- **Validation:** The proxy validates invocation parameters against the tool's schema before calling the external service.
- **Cost estimation:** Coordinators can estimate plan costs before execution.
- **Capability matching:** Tasks declare required tools, agents declare available grants, and the server matches them.
- **Discovery:** Agents can query the registry to understand what tools are available to them.

#### 8.2 Discovery Endpoint

```
GET /api/v1/tools
  → List all registered services and tools

GET /api/v1/tools/{service}
  → List tools for a specific service

GET /api/v1/tools/granted?agent_id={agent_id}
  → List tools the agent has active grants for
```

### 9. YAML Workflow Integration

The YAML workflow specification (RFC-0011 v2.0) gains a `tools` block for declaring tool requirements and grants:

```yaml
name: quarterly-compliance
version: "1.0"

tools:
  vault: acme-corp-production
  grants:
    billing-agent:
      - service: stripe
        scopes: [charges.read, charges.create]
        constraints:
          max_invocations_per_hour: 50
          amount_max: 10000
        delegatable: false
    data-agent:
      - service: postgres-analytics
        scopes: [query.read]
        delegatable: false
    report-agent:
      - service: email
        scopes: [send]
        constraints:
          max_invocations_per_hour: 10
        delegatable: false

agents:
  billing-agent:
    capabilities: [billing, invoicing]
    permissions: private
  data-agent:
    capabilities: [data-analysis, sql]
    permissions: private
  report-agent:
    capabilities: [document-generation, email]
    permissions: private

plan:
  - task: gather-financial-data
    agent: data-agent
    requires_tools:
      - service: postgres-analytics
        scopes: [query.read]
    outputs: [financial_summary]

  - task: process-billing
    agent: billing-agent
    depends_on: [gather-financial-data]
    requires_tools:
      - service: stripe
        scopes: [charges.read, charges.create]
    outputs: [billing_report]

  - task: send-report
    agent: report-agent
    depends_on: [process-billing]
    requires_tools:
      - service: email
        scopes: [send]
```

### 10. Security Considerations

#### 10.1 Credential Storage

- Credentials MUST be encrypted at rest using AES-256-GCM or equivalent.
- Encryption keys MUST be stored separately from encrypted credentials (e.g., in a hardware security module or key management service).
- Credential material MUST never appear in logs, events, error messages, or API responses.

#### 10.2 Grant Boundaries

- The system MUST reject any grant where scopes exceed the credential's `scopes_available`.
- The system MUST reject any delegation where the delegated grant exceeds the source grant.
- The system MUST enforce cascading revocation with zero delay.
- Expired grants MUST be rejected even if the underlying credential is still valid.

#### 10.3 Tool Proxy Isolation

- The tool proxy MUST execute external calls in an isolated context with no access to other credentials, grants, or vault data beyond what is needed for the current invocation.
- The tool proxy MUST sanitize responses to remove any credential material that may be present in error messages, headers, or response bodies.
- The tool proxy SHOULD implement request signing or HMAC to prevent replay attacks on idempotent operations.

#### 10.4 Audit Completeness

- Every tool invocation MUST produce an event, regardless of success or failure.
- Every grant lifecycle transition MUST produce an event.
- Invocation events MUST include sufficient detail for the user to understand what the agent did, without including raw credentials.

### 11. SDK Semantics for Standalone Agents

This section defines the expected developer experience for standalone agents using tool grants. While the protocol is language-agnostic, the semantics described here inform SDK implementations (including the Python reference SDK).

#### 11.1 Design Principles

1. **Tools are first-class.** A standalone agent should be able to discover and invoke tools without understanding vaults, credentials, or the grant model. The SDK abstracts these away.
2. **No coordinator required.** A developer building a single-purpose agent should never need to create a coordinator lease, a plan, or a task to use a tool. Direct grants are sufficient.
3. **Grant resolution is transparent.** When an agent invokes a tool, the SDK resolves the appropriate grant automatically. The developer specifies the tool name and parameters; the SDK finds the matching grant, validates scopes, and makes the proxy call.
4. **Audit is automatic.** Every invocation is logged as an event regardless of whether the agent is standalone or coordinated. The developer does not need to opt into auditing.

#### 11.2 Agent Tool Interface

The SDK provides a `tools` namespace on the client that handles discovery, resolution, and invocation:

```python
from openintent import Client

client = Client(server_url="...", api_key="...")

# Discover available tools
my_tools = client.tools.list()
# Returns: [GrantedTool(service="stripe", tool="charges.read", ...), ...]

# Invoke a tool by service and operation
result = client.tools.invoke(
    "stripe", "charges.read",
    parameters={"charge_id": "ch_abc123"}
)
# The SDK:
#   1. Finds the agent's grant for stripe/charges.read
#   2. Submits the invocation to the proxy
#   3. Returns the result (no credential exposure)
#   4. Event is logged automatically

# Check what you can do with a service
stripe_tools = client.tools.list(service="stripe")
# Returns only Stripe-related granted tools
```

#### 11.3 Async Support

```python
from openintent import AsyncClient

async_client = AsyncClient(server_url="...", api_key="...")

result = await async_client.tools.invoke(
    "stripe", "charges.create",
    parameters={"amount": 2500, "currency": "usd"}
)
```

#### 11.4 Error Handling

SDK errors map directly to protocol error codes:

```python
from openintent.exceptions import (
    GrantScopeError,      # GRANT_SCOPE_INSUFFICIENT
    GrantExpiredError,     # GRANT_EXPIRED
    GrantRateLimitError,   # GRANT_RATE_LIMITED
    GrantParameterError,   # GRANT_PARAMETER_DENIED
    ToolProxyError,        # PROXY_ERROR
    ServiceError,          # SERVICE_ERROR
)

try:
    result = client.tools.invoke("stripe", "refunds.create", ...)
except GrantScopeError as e:
    # Agent doesn't have the refunds.create scope
    # e.available_scopes shows what the agent CAN do
    print(f"Cannot create refund. Available: {e.available_scopes}")
except GrantRateLimitError as e:
    # Agent has exceeded its rate limit
    # e.retry_after_seconds suggests when to retry
    print(f"Rate limited. Retry after {e.retry_after_seconds}s")
```

#### 11.5 Worker Agent Pattern

For agents that operate within a coordination hierarchy (receiving delegated grants), the same interface works — the SDK resolves the delegated grant transparently:

```python
from openintent import Worker

@Worker(capabilities=["billing"])
def process_invoice(ctx):
    # ctx.tools is the same interface as client.tools
    # but scoped to grants delegated for this task
    charge = ctx.tools.invoke(
        "stripe", "charges.create",
        parameters={"amount": ctx.input["amount"], "currency": "usd"}
    )
    return {"charge_id": charge["id"]}
```

The key difference: `client.tools` resolves from all of the agent's grants (direct + delegated). `ctx.tools` in a Worker resolves only from grants delegated for the current task. This enforces the principle of least privilege without the developer needing to manage grant IDs.

#### 11.6 Grant Awareness (Optional)

For agents that need explicit control over which grant to use (e.g., an agent with multiple Stripe credentials for different environments):

```python
# List grants explicitly
grants = client.tools.grants()
prod_grant = next(g for g in grants if g.metadata.get("environment") == "production")

# Invoke with explicit grant
result = client.tools.invoke(
    "stripe", "charges.read",
    parameters={"charge_id": "ch_abc"},
    grant_id=prod_grant.id
)
```

This is the advanced path. Most standalone agents will never need it — the SDK's automatic grant resolution handles the common case.

## API Endpoints

### Vault Management

```
POST   /api/v1/vaults                    — Create a vault
GET    /api/v1/vaults                    — List user's vaults
GET    /api/v1/vaults/{vault_id}         — Get vault details
DELETE /api/v1/vaults/{vault_id}         — Delete vault (cascades to credentials and grants)
```

### Credential Management

```
POST   /api/v1/vaults/{vault_id}/credentials        — Add a credential
GET    /api/v1/vaults/{vault_id}/credentials        — List credentials (material redacted)
GET    /api/v1/credentials/{credential_id}          — Get credential details (material redacted)
PATCH  /api/v1/credentials/{credential_id}/rotate   — Rotate credential material
DELETE /api/v1/credentials/{credential_id}          — Revoke credential (cascades to grants)
```

### Grant Management

```
POST   /api/v1/grants                    — Create a grant
GET    /api/v1/grants                    — List grants (filterable by agent, service, credential)
GET    /api/v1/grants/{grant_id}         — Get grant details
DELETE /api/v1/grants/{grant_id}         — Revoke grant (cascades to delegated grants)
PATCH  /api/v1/grants/{grant_id}/suspend — Suspend grant
PATCH  /api/v1/grants/{grant_id}/resume  — Resume grant
POST   /api/v1/grants/{grant_id}/delegate — Delegate grant to another agent
```

### Tool Invocation

```
POST   /api/v1/tools/invoke              — Invoke a tool (through proxy)
GET    /api/v1/tools                     — List registered tools
GET    /api/v1/tools/{service}           — List tools for a service
GET    /api/v1/tools/granted             — List tools available to the authenticated agent
```

### Invocation History

```
GET    /api/v1/invocations                           — List invocations (filterable)
GET    /api/v1/invocations/{invocation_id}           — Get invocation details
GET    /api/v1/intents/{intent_id}/invocations       — List invocations for an intent
GET    /api/v1/tasks/{task_id}/invocations           — List invocations for a task
```

## Events

| Event Type | Data Fields |
|------------|-------------|
| `tool.invoked` | invocation_id, grant_id, service, tool, parameters_summary, status, duration_ms, cost |
| `tool.denied` | grant_id, service, tool, error_code, reason |
| `grant.created` | grant_id, credential_id, agent_id, scopes, expires_at |
| `grant.delegated` | grant_id, source_grant_id, target_agent_id, scopes, delegation_depth |
| `grant.revoked` | grant_id, reason, cascade_count |
| `grant.expired` | grant_id |
| `grant.suspended` | grant_id, reason |
| `grant.resumed` | grant_id |
| `credential.created` | credential_id, vault_id, service, auth_type |
| `credential.rotated` | credential_id, rotated_by |
| `credential.expired` | credential_id |
| `credential.revoked` | credential_id, reason, affected_grants_count |

## Relationship to MCP (Model Context Protocol)

The Tool Proxy model in this RFC is designed to complement MCP's tool-calling interface. An MCP server implementing OpenIntent would expose granted tools as MCP tools, with the proxy layer handling credential injection transparently:

```
LLM sees:     "stripe.charges.create" as an MCP tool
LLM calls:    tool with parameters
MCP server:   validates grant → invokes via tool proxy → returns result
LLM receives: result (no credential exposure)
```

The grant system provides what MCP does not: per-agent scoping, delegation hierarchies, rate limiting, audit trails, and cascading revocation. MCP provides the transport; OpenIntent provides the governance.

## Reference Implementation: Execution Adapters

The reference implementation provides a pluggable adapter system for real external API execution through the Tool Proxy. This section describes the implementation architecture.

### Adapter Interface

All adapters implement `ToolExecutionAdapter`, which provides:

- URL validation and SSRF protection
- Timeout enforcement (1–120 seconds)
- Response size limiting (1 MB)
- Secret sanitization in all outputs
- Request fingerprinting for audit correlation

```python
class ToolExecutionAdapter:
    async def execute(self, tool_name, parameters, credential_metadata, 
                      credential_secret, grant_constraints=None):
        # 1. Validate URL (blocks private IPs, metadata endpoints)
        # 2. Enforce timeout bounds
        # 3. Execute request
        # 4. Sanitize secrets from response
        # 5. Generate request fingerprint
        return ToolExecutionResult(status, result, duration_ms, request_fingerprint)
```

### Built-in Adapters

| Adapter | Auth Types | Resolution |
|---------|-----------|------------|
| `RestToolAdapter` | API key (header/query), Bearer token, Basic Auth | `auth_type` in `["api_key", "bearer_token", "basic_auth"]` |
| `OAuth2ToolAdapter` | OAuth2 with automatic token refresh on 401 | `auth_type == "oauth2_token"` |
| `WebhookToolAdapter` | HMAC-SHA256 signed dispatch | `adapter == "webhook"` or `auth_type == "webhook"` |

### Adapter Registry

The `AdapterRegistry` resolves adapters using credential metadata:

1. **Explicit selection**: `metadata.adapter` key selects adapter by name
2. **Auth-type mapping**: `metadata.auth_type` maps to the appropriate adapter
3. **Fallback**: No execution config → placeholder response (backward compatible)

### Security Controls

| Control | Implementation |
|---------|---------------|
| URL validation | `validate_url()` blocks RFC-1918 ranges, loopback, link-local, cloud metadata endpoints, non-HTTP schemes |
| Timeout clamping | `sanitize_timeout()` clamps to [1, 120] seconds |
| Response limiting | Responses truncated at 1 MB |
| Secret sanitization | `sanitize_secrets()` replaces API keys, tokens, passwords with `[REDACTED]` in all output paths |
| Request fingerprinting | SHA-256 hash of method + URL + sorted parameters stored per invocation |
| Redirect blocking | `allow_redirects=False` prevents SSRF via redirect chains |

### Open Questions (Execution)

The implementation resolves some of the open questions from this RFC:

1. **OAuth flow management** — The `OAuth2ToolAdapter` handles token refresh automatically using `refresh_token` + `token_url` stored in credential metadata. Initial authorization (consent screens) remains out of scope.
2. **Tool versioning** — Endpoint paths are stored in credential metadata, so different API versions can coexist by storing different `base_url` values per credential.

## Open Questions

1. **OAuth flow management.** For services using OAuth2, should the protocol define a standard flow for initial authorization (redirects, consent screens), or is that out of scope?

2. **Multi-tenant isolation.** When multiple users share a protocol server, vault isolation is critical. Should the protocol specify tenant isolation requirements, or leave this to deployment?

3. **Tool versioning.** External service APIs change. How should the tool registry handle breaking changes in external APIs?

4. **Credential sharing across vaults.** Should credentials be shareable across vaults (e.g., an organization-wide Stripe key used by multiple teams), or should each vault be fully independent?

## References

- RFC-0001: Intent Object Model
- RFC-0003: Lease-Based Coordination
- RFC-0009: Cost Tracking
- RFC-0011: Access-Aware Coordination
- RFC-0012: Task Decomposition & Planning
- RFC-0013: Coordinator Governance & Meta-Coordination
- Model Context Protocol (MCP) Specification
