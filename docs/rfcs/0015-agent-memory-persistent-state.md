# RFC-0015: Agent Memory & Persistent State

- **Status:** Proposed
- **Created:** 2026-02-08
- **Authors:** OpenIntent Contributors
- **Depends on:** RFC-0001, RFC-0005, RFC-0008, RFC-0011, RFC-0012, RFC-0013

## Abstract

This RFC defines a structured memory model for agents participating in the OpenIntent Protocol. It introduces three memory tiers — working, episodic, and semantic — each with distinct lifecycle, access control, and eviction semantics. Memory entries are protocol-level primitives stored server-side, queryable through tag-based filters, and governed by the same access control model as the rest of the protocol. The goal is to provide stable semantics that implementations can build on, without prescribing how agents internally reason over their memories.

## Motivation

Agents executing multi-step work need to persist state between invocations. The protocol currently offers two places to store state, neither of which is designed for this purpose:

1. **Intent event log (RFC-0001):** Append-only and immutable. Suitable for history and audit, but not for mutable working state. An agent cannot update a previous entry, and scanning the full log to reconstruct current state is inefficient.

2. **Intent metadata:** Mutable via PATCH, but semantically belongs to the intent, not the agent. Multiple agents participating in the same intent would collide on metadata keys. There is no namespace isolation, no lifecycle management, and no access control beyond intent-level permissions.

Without a first-class memory primitive, agents resort to encoding state into event payloads, intent metadata, or external storage — all of which break interoperability. A coordinator cannot inspect a worker's progress. A replacement agent cannot resume a failed agent's work. Learned patterns cannot be retained across tasks.

This RFC provides the missing primitive: structured, server-managed memory with clear tiers, lifecycle rules, and access semantics. The protocol specifies *what* memory looks like and *how* it behaves, not *how* agents decide what to remember — that is an implementation concern that will vary across agent architectures, LLM providers, and use cases.

## Specification

### 1. Memory Entry

A memory entry is the fundamental unit of agent state. It is a structured key-value record with metadata governing its lifecycle and accessibility.

```json
{
  "id": "mem_01HXYZ",
  "agent_id": "agent_billing_01",
  "namespace": "invoice_processing",
  "key": "batch_progress",
  "value": {
    "total": 47,
    "completed": 23,
    "last_id": "inv_789",
    "errors": []
  },
  "memory_type": "working",
  "scope": {
    "task_id": "task_01HXYZ",
    "intent_id": "intent_01HABC"
  },
  "tags": ["batch", "invoices", "in-progress"],
  "ttl": "task_lifetime",
  "version": 1,
  "created_at": "2026-02-08T10:00:00Z",
  "updated_at": "2026-02-08T10:30:00Z",
  "expires_at": null
}
```

#### 1.1 Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Unique identifier (server-generated). |
| `agent_id` | string | Yes | The agent that owns this memory entry. |
| `namespace` | string | Yes | Logical grouping for related entries. Free-form string, dot-separated by convention (e.g., `billing.invoices`). |
| `key` | string | Yes | Unique key within the namespace for this agent. |
| `value` | object | Yes | Structured JSON payload. The protocol does not interpret the value — it is opaque to the server. |
| `memory_type` | enum | Yes | One of: `working`, `episodic`, `semantic`. Determines lifecycle and access rules. |
| `scope` | object | No | Binds the entry to a context. For working memory, typically contains `task_id` and/or `intent_id`. For episodic and semantic, may be empty. |
| `tags` | string[] | No | Free-form labels for filtering and querying. |
| `ttl` | string | No | Time-to-live policy. Values: `task_lifetime` (auto-expire on task completion), `duration:<ISO8601>` (e.g., `duration:PT24H`), or `null` (no automatic expiry). |
| `version` | integer | Yes | Monotonically increasing version for optimistic concurrency. |
| `created_at` | timestamp | Yes | When the entry was first created. |
| `updated_at` | timestamp | Yes | When the entry was last modified. |
| `expires_at` | timestamp | No | Absolute expiry. Takes precedence over `ttl` if both are set. |

#### 1.2 Uniqueness

The tuple `(agent_id, namespace, key)` is unique for working and episodic memory. For semantic memory, the tuple `(namespace, key)` is unique (semantic memory is not agent-scoped).

#### 1.3 Value Size

The `value` field SHOULD NOT exceed 64 KB. Memory entries are designed for structured state, not bulk data. For larger payloads, agents SHOULD use attachments (RFC-0005) and store a reference in the memory entry:

```json
{
  "namespace": "data_processing",
  "key": "large_dataset_ref",
  "value": {
    "attachment_id": "att_01HXYZ",
    "summary": "47,000 row customer export",
    "row_count": 47000
  },
  "memory_type": "working",
  "tags": ["dataset", "reference"]
}
```

### 2. Memory Tiers

The protocol defines three memory tiers. Each tier has distinct lifecycle, access, and eviction semantics. The tiers reflect how agents naturally organize state — not as an implementation prescription, but as a semantic contract that enables interoperability.

#### 2.1 Working Memory

Working memory holds mutable state for in-progress work. It is task-scoped and short-lived.

**Lifecycle:**
- Created when an agent begins work on a task (or at any point during task execution).
- Updated as work progresses.
- **Automatically archived and cleared** when the task completes, fails, or is cancelled.

**Archival:** On task completion, working memory entries are snapshotted as a `memory.archived` event in the intent event log (RFC-0001). This preserves the final state for audit without retaining mutable entries indefinitely.

```json
{
  "type": "memory.archived",
  "intent_id": "intent_01HABC",
  "task_id": "task_01HXYZ",
  "agent_id": "agent_billing_01",
  "data": {
    "entries_archived": 3,
    "snapshot": [
      {
        "namespace": "invoice_processing",
        "key": "batch_progress",
        "value": { "total": 47, "completed": 47, "last_id": "inv_832" },
        "tags": ["batch", "invoices", "completed"]
      }
    ]
  },
  "timestamp": "2026-02-08T11:00:00Z"
}
```

**Access control:**
- **Read/write:** The owning agent.
- **Read-only:** The coordinator managing the task (for progress monitoring during task lifetime).
- **No access:** Other agents, unless explicitly granted via RFC-0011 permissions.
- **After archival:** Working memory entries are deleted. The archived snapshot in the event log (Section 5) is accessible to any agent with read access to the intent's event log. Coordinators access post-completion state through the event log, not through the memory API.

**Use cases:**
- Checkpointing progress through a batch operation.
- Storing intermediate computation results.
- Tracking retry state for an in-progress action.
- Recording decisions made during task execution.

#### 2.2 Episodic Memory

Episodic memory holds patterns, observations, and learned behaviors that an agent accumulates over time. It is agent-scoped and medium-lived.

**Lifecycle:**
- Created by the agent at any time (typically after completing a task or encountering a notable event).
- Persists across tasks and intents.
- Subject to capacity limits and eviction.

**Capacity and eviction:**
- Each agent has a configurable capacity for episodic memory (default: 1,000 entries).
- When capacity is reached, the server evicts entries using the configured eviction policy.
- Default eviction policy: **LRU** (least recently accessed).
- Agents can **pin** entries to exempt them from eviction: `"pinned": true`. Pinned entries count against capacity but are never evicted.
- Agents can set **priority** on entries (`low`, `normal`, `high`). Eviction prefers lower-priority entries first within the LRU ordering.

```json
{
  "namespace": "learned_patterns",
  "key": "stripe_thursdays",
  "value": {
    "observation": "Stripe API returns elevated 500 rates on Thursdays between 14:00-16:00 UTC",
    "confidence": 0.85,
    "sample_size": 12,
    "first_observed": "2026-01-15",
    "last_observed": "2026-02-06",
    "recommended_action": "schedule_retry_with_backoff"
  },
  "memory_type": "episodic",
  "tags": ["stripe", "reliability", "temporal-pattern"],
  "pinned": false,
  "priority": "normal"
}
```

**Access control:**
- **Read/write:** The owning agent.
- **Read-only:** Coordinators managing tasks assigned to this agent.
- **No access:** Other agents. Episodic memory is personal to the agent.

**Note:** The protocol does not specify *how* an agent decides what to remember. Whether an agent uses heuristics, LLM reflection, or explicit rules to create episodic memories is an implementation concern. The protocol only specifies the storage semantics and access model.

#### 2.3 Semantic Memory

Semantic memory holds shared knowledge — facts, policies, domain rules, and reference data that multiple agents need access to. It is namespace-scoped and long-lived.

**Lifecycle:**
- Created by users, coordinators, or designated curator agents.
- Persists indefinitely unless explicitly deleted or expired.
- Not subject to automatic eviction.

**Ownership:** Semantic memory is not owned by a single agent. It belongs to a namespace, and access is controlled via namespace permissions.

```json
{
  "namespace": "company_policies",
  "key": "charge_approval_threshold",
  "value": {
    "rule": "Charges exceeding $10,000 require manager approval",
    "threshold_usd": 10000,
    "approval_role": "manager",
    "effective_date": "2025-06-01",
    "source": "finance_policy_v3.2"
  },
  "memory_type": "semantic",
  "tags": ["policy", "billing", "approval", "threshold"],
  "curated_by": "user_01HABC",
  "version": 3
}
```

**Access control:**
- **Read:** Any agent with `memory.read` permission for the namespace.
- **Write:** Users and agents with `memory.write` permission for the namespace (typically restricted to curators or coordinators).
- **Admin:** Users with `memory.admin` permission can manage namespace permissions.

**Namespace permissions** follow the RFC-0011 model:

```json
{
  "namespace": "company_policies",
  "permissions": {
    "default": "read",
    "allow": [
      { "agent": "agent_policy_curator", "access": "write" },
      { "agent": "coordinator_01", "access": "write" }
    ]
  }
}
```

### 3. Concurrency Control

Memory entries use optimistic concurrency, consistent with the protocol's concurrency model for intents (RFC-0001).

#### 3.1 Version Numbers

Every memory entry has a `version` field that increments on each update. The server MUST reject updates that do not include the correct current version.

#### 3.2 Conditional Updates

Updates use the `If-Match` header with the entry's current version:

```
PATCH /api/v1/memory/{entry_id}
If-Match: 3
Content-Type: application/json

{
  "value": { "total": 47, "completed": 24, "last_id": "inv_790" },
  "tags": ["batch", "invoices", "in-progress"]
}
```

If the current version is not 3, the server returns `409 Conflict` with the current entry state, allowing the agent to resolve the conflict and retry.

#### 3.3 Conflict Resolution

The protocol does not prescribe a conflict resolution strategy — agents handle conflicts based on their domain logic. Common patterns:

- **Last-writer-wins:** The agent reads the current state, merges, and retries the update.
- **Append-merge:** For entries where the value contains a list or set, the agent unions the current and proposed values.
- **Abort:** The agent abandons its update and works with the current state.

### 4. Querying Memory

The protocol defines a tag-based filter model for querying memory. This keeps the query interface deterministic and implementable without specialized infrastructure.

#### 4.1 Query Parameters

```
GET /api/v1/memory?agent_id=agent_billing_01&namespace=invoice_processing&tags=batch,in-progress&memory_type=working
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `agent_id` | string | Filter by owning agent. Required for working and episodic queries. |
| `namespace` | string | Filter by namespace (exact match or prefix with `*`). |
| `key` | string | Filter by key (exact match). |
| `memory_type` | enum | Filter by tier: `working`, `episodic`, `semantic`. |
| `tags` | string | Comma-separated tags. Returns entries matching ALL specified tags (AND logic). |
| `tags_any` | string | Comma-separated tags. Returns entries matching ANY specified tag (OR logic). |
| `scope.task_id` | string | Filter by task context. |
| `scope.intent_id` | string | Filter by intent context. |
| `pinned` | boolean | Filter pinned entries (episodic only). |
| `updated_after` | timestamp | Entries updated after this time. |
| `updated_before` | timestamp | Entries updated before this time. |
| `limit` | integer | Maximum entries to return (default: 100, max: 1000). |
| `offset` | integer | Pagination offset. |

#### 4.2 Query Response

```json
{
  "entries": [
    {
      "id": "mem_01HXYZ",
      "agent_id": "agent_billing_01",
      "namespace": "invoice_processing",
      "key": "batch_progress",
      "value": { "total": 47, "completed": 23 },
      "memory_type": "working",
      "tags": ["batch", "invoices", "in-progress"],
      "version": 5,
      "updated_at": "2026-02-08T10:30:00Z"
    }
  ],
  "total": 1,
  "limit": 100,
  "offset": 0
}
```

#### 4.3 Semantic Search (Extension Point)

The protocol does not specify semantic or fuzzy search. Implementations MAY provide additional query capabilities (e.g., vector similarity search over memory values) as non-standard extensions. Such extensions SHOULD be discoverable through the server's capabilities endpoint and MUST NOT replace the tag-based filter interface — they are additive.

### 5. Memory Lifecycle Events

All memory mutations produce events in the intent event log (when a task/intent context exists) or in a dedicated agent event stream (for context-free episodic memory operations).

#### 5.1 Event Types

| Event Type | Trigger |
|------------|---------|
| `memory.created` | A new memory entry is created. |
| `memory.updated` | An existing memory entry's value or tags are modified. |
| `memory.deleted` | A memory entry is explicitly deleted by the agent or curator. |
| `memory.archived` | Working memory is archived on task completion (batch event). |
| `memory.evicted` | An episodic memory entry is evicted due to capacity limits. |
| `memory.expired` | A memory entry reaches its TTL or `expires_at`. |

#### 5.2 Event Structure

```json
{
  "type": "memory.updated",
  "agent_id": "agent_billing_01",
  "intent_id": "intent_01HABC",
  "task_id": "task_01HXYZ",
  "data": {
    "entry_id": "mem_01HXYZ",
    "namespace": "invoice_processing",
    "key": "batch_progress",
    "memory_type": "working",
    "version": 6,
    "previous_version": 5,
    "tags": ["batch", "invoices", "in-progress"]
  },
  "timestamp": "2026-02-08T10:35:00Z"
}
```

Note: The `value` field is intentionally excluded from lifecycle events to avoid logging potentially large or sensitive data. The event references the entry by ID — the current value can be retrieved through the memory API if needed.

### 6. Integration with Existing RFCs

#### 6.1 RFC-0001 (Intents and Events)

Memory lifecycle events are logged as intent events when a task/intent context exists. Working memory archival events provide a snapshot of agent state at task completion, complementing the append-only event log with structured state capture.

#### 6.2 RFC-0005 (Attachments)

Memory entries exceeding 64 KB SHOULD store their bulk content as an attachment and reference it by `attachment_id` in the memory value. This keeps memory entries lightweight and queryable while supporting large payloads.

#### 6.3 RFC-0008 (LLM Integration)

The LLM adapter layer (RFC-0008) is responsible for selecting which memory entries to include in an agent's context window for a given invocation. The protocol provides the query interface; the adapter manages context packing strategy. Common patterns:

- **Working memory:** Load all entries for the current task.
- **Episodic memory:** Query by tags relevant to the current task type, load the top-N most recent.
- **Semantic memory:** Query by namespace relevant to the domain, load applicable policies/rules.

The protocol does not prescribe these patterns — they are implementation guidance.

#### 6.4 RFC-0011 (Access Control)

Memory access control introduces three new permission types:

| Permission | Meaning |
|------------|---------|
| `memory.read` | Agent can read memory entries (within access rules for the tier). |
| `memory.write` | Agent can create and update memory entries (within access rules for the tier). |
| `memory.admin` | Agent can manage namespace permissions for semantic memory. |

These permissions are orthogonal to memory tier access rules — an agent needs both the permission AND to satisfy the tier's access rules (e.g., ownership for episodic memory).

#### 6.5 RFC-0012 (Task Decomposition)

Tasks gain an optional `memory_policy` field that governs how working memory behaves for the task:

```json
{
  "task_id": "task_01HXYZ",
  "memory_policy": {
    "archive_on_completion": true,
    "inherit_from_parent": false,
    "max_entries": 100,
    "max_total_size_kb": 1024
  }
}
```

- **`archive_on_completion`** — Whether to archive working memory when the task completes (default: `true`).
- **`inherit_from_parent`** — Whether sub-tasks inherit the parent task's working memory as read-only context (default: `false`).
- **`max_entries`** — Maximum working memory entries for this task.
- **`max_total_size_kb`** — Maximum total size of working memory values for this task.

#### 6.6 RFC-0013 (Coordinator Governance)

Coordinator guardrails gain memory-related constraints:

```json
{
  "guardrails": {
    "max_working_memory_per_task": 100,
    "max_episodic_memory_per_agent": 1000,
    "allowed_semantic_namespaces": ["company_policies", "domain_knowledge"],
    "denied_semantic_namespaces": ["internal_config"],
    "memory_archive_required": true
  }
}
```

### 7. YAML Workflow Integration

The YAML workflow specification gains a `memory` block for declaring memory configuration and pre-loading semantic memory:

```yaml
name: quarterly-compliance
version: "1.0"

memory:
  semantic_namespaces:
    - company_policies
    - compliance_rules
    - billing_domain
  working_memory:
    archive_on_completion: true
    max_entries_per_task: 50
  episodic_memory:
    capacity_per_agent: 500
    eviction_policy: lru

agents:
  billing-agent:
    capabilities: [billing, invoicing]
    permissions: private
    episodic_memory:
      capacity: 200
      pinned_namespaces: [learned_patterns]
  data-agent:
    capabilities: [data-analysis, sql]
    permissions: private

plan:
  - task: gather-financial-data
    agent: data-agent
    memory_policy:
      archive_on_completion: true
      inherit_from_parent: false
    outputs: [financial_summary]

  - task: process-billing
    agent: billing-agent
    depends_on: [gather-financial-data]
    memory_policy:
      archive_on_completion: true
      max_entries: 100
    outputs: [billing_report]
```

### 8. Resumability

One of the primary benefits of protocol-managed memory is enabling agent resumability. When an agent fails or is replaced mid-task, the replacement agent can read the previous agent's working memory and continue from the last recorded state.

#### 8.1 Resumption Flow

1. Agent A is assigned to `task_01HXYZ` and creates working memory entries tracking progress.
2. Agent A fails (crash, timeout, lease expiry).
3. The coordinator assigns Agent B to the same task.
4. Agent B queries working memory for `task_01HXYZ`:
   ```
   GET /api/v1/memory?scope.task_id=task_01HXYZ&memory_type=working
   ```
5. Agent B reads the previous agent's state and resumes from the last checkpoint.

**Access:** The server MUST allow the newly assigned agent to read working memory entries created by the previous agent for the same task. This is an exception to the "owning agent only" rule for working memory, scoped specifically to task reassignment.

#### 8.2 Ownership Transfer

When a task is reassigned, working memory entries created by the previous agent become read-only to the new agent. The new agent creates its own entries in the same namespace. This preserves the audit trail (who wrote what) while enabling continuity.

```json
{
  "namespace": "invoice_processing",
  "key": "batch_progress",
  "value": { "total": 47, "completed": 24, "last_id": "inv_790", "resumed_from": "mem_01HXYZ" },
  "memory_type": "working",
  "scope": { "task_id": "task_01HXYZ" },
  "tags": ["batch", "invoices", "in-progress", "resumed"],
  "created_by": "agent_billing_02"
}
```

### 9. Security Considerations

#### 9.1 Memory Isolation

- Working and episodic memory entries MUST NOT be accessible to agents other than the owner (with the exception of coordinator read access and task reassignment per Section 8).
- Semantic memory namespace permissions MUST be enforced on every read and write operation.
- The server MUST NOT return memory entries in API responses to agents that lack access.

#### 9.2 Sensitive Data

- Memory entries MAY contain sensitive information (customer data, financial figures, API responses).
- Implementations SHOULD provide an optional `sensitivity` field on entries (`public`, `internal`, `confidential`, `restricted`) to support data classification.
- Entries marked `confidential` or `restricted` SHOULD be encrypted at rest beyond the default storage encryption.
- Memory archival events (Section 5) exclude entry values to prevent sensitive data from appearing in the event log.

#### 9.3 Eviction and Deletion

- Evicted episodic memory entries MUST be fully deleted from storage, not soft-deleted.
- Expired entries (TTL or `expires_at`) MUST be removed within a reasonable timeframe (implementation-defined, RECOMMENDED within 1 hour).
- Explicit deletion via the API MUST be immediate and irreversible.

#### 9.4 Capacity Enforcement

- The server MUST enforce working memory limits per task and episodic memory limits per agent.
- When a limit is reached, the server MUST reject new entries with a `429 Memory Capacity Exceeded` error (for working memory) or trigger eviction (for episodic memory).
- Semantic memory does not have automatic capacity limits but implementations MAY enforce storage quotas.

## API Endpoints

### Memory CRUD

```
POST   /api/v1/memory                         — Create a memory entry
GET    /api/v1/memory                         — Query memory entries (with filters)
GET    /api/v1/memory/{entry_id}              — Get a specific entry
PATCH  /api/v1/memory/{entry_id}              — Update an entry (requires If-Match)
DELETE /api/v1/memory/{entry_id}              — Delete an entry
```

### Batch Operations

```
POST   /api/v1/memory/batch                   — Create or update multiple entries atomically
DELETE /api/v1/memory/batch                   — Delete multiple entries by filter
```

### Namespace Management (Semantic Memory)

```
GET    /api/v1/memory/namespaces              — List namespaces the agent has access to
GET    /api/v1/memory/namespaces/{namespace}  — Get namespace details and permissions
PATCH  /api/v1/memory/namespaces/{namespace}  — Update namespace permissions (admin only)
```

### Agent Memory Summary

```
GET    /api/v1/agents/{agent_id}/memory/summary — Get memory usage summary (counts, capacity, etc.)
```

Response:

```json
{
  "agent_id": "agent_billing_01",
  "working": {
    "entry_count": 3,
    "total_size_kb": 12,
    "tasks_with_memory": ["task_01HXYZ"]
  },
  "episodic": {
    "entry_count": 142,
    "capacity": 1000,
    "pinned_count": 5,
    "total_size_kb": 890,
    "oldest_entry": "2026-01-15T08:00:00Z",
    "newest_entry": "2026-02-08T10:30:00Z"
  },
  "semantic_namespaces_accessible": ["company_policies", "domain_knowledge"]
}
```

## SDK Semantics

### Client Interface

The SDK provides a `memory` namespace on the client:

```python
from openintent import Client

client = Client(server_url="...", api_key="...")

# Write working memory (task context inferred from current execution)
client.memory.set(
    namespace="invoice_processing",
    key="batch_progress",
    value={"total": 47, "completed": 23, "last_id": "inv_789"},
    memory_type="working",
    tags=["batch", "invoices"]
)

# Read a specific entry
progress = client.memory.get(
    namespace="invoice_processing",
    key="batch_progress"
)

# Query by tags
entries = client.memory.query(
    namespace="invoice_processing",
    tags=["in-progress"],
    memory_type="working"
)

# Update with optimistic concurrency (version auto-tracked)
client.memory.set(
    namespace="invoice_processing",
    key="batch_progress",
    value={"total": 47, "completed": 24, "last_id": "inv_790"},
    tags=["batch", "invoices", "in-progress"]
)
# The SDK tracks the version from the last get/set and sends If-Match automatically.
# On conflict, raises MemoryConflictError with the current server state.

# Read semantic memory
policy = client.memory.get(
    namespace="company_policies",
    key="charge_approval_threshold"
)
```

### Worker Context

Inside a Worker (RFC-0014 Section 11.5), the `ctx.memory` interface is automatically scoped to the current task for working memory:

```python
from openintent import Worker

@Worker(capabilities=["billing"])
def process_invoices(ctx):
    # Working memory is scoped to this task
    progress = ctx.memory.get("invoice_processing", "batch_progress")

    if progress:
        start_from = progress["last_id"]
    else:
        start_from = None

    for invoice in fetch_invoices(start_from):
        process(invoice)
        ctx.memory.set(
            "invoice_processing", "batch_progress",
            value={"completed": invoice.index, "last_id": invoice.id},
            tags=["batch", "in-progress"]
        )

    # Record a learned pattern in episodic memory
    ctx.memory.set(
        "learned_patterns", "invoice_batch_size",
        value={"optimal_batch_size": 50, "reason": "API rate limits"},
        memory_type="episodic",
        tags=["performance", "optimization"]
    )
```

### Error Handling

```python
from openintent.exceptions import (
    MemoryConflictError,     # VERSION_MISMATCH (409)
    MemoryCapacityError,     # CAPACITY_EXCEEDED (429)
    MemoryAccessError,       # ACCESS_DENIED (403)
    MemoryNotFoundError,     # ENTRY_NOT_FOUND (404)
)

try:
    client.memory.set("ns", "key", value={"data": "..."})
except MemoryConflictError as e:
    # e.current_value has the server's current state
    # e.current_version has the current version number
    merged = merge(e.current_value, my_value)
    client.memory.set("ns", "key", value=merged, version=e.current_version)
except MemoryCapacityError as e:
    # e.current_count and e.max_capacity available
    # Agent should evict or consolidate entries
    pass
```
