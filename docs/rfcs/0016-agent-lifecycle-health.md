# RFC-0016: Agent Lifecycle & Health

- **Status:** Proposed
- **Created:** 2026-02-08
- **Authors:** OpenIntent Contributors
- **Depends on:** RFC-0001, RFC-0003, RFC-0011, RFC-0013, RFC-0014, RFC-0015

## Abstract

This RFC defines the protocol-level primitives for agent registration, health monitoring, graceful shutdown, and lifecycle management. It introduces a formal agent registry, a pull-based heartbeat protocol with jitter-tolerant thresholds, a status lifecycle state machine, and a graceful drain mechanism. The scope is coordination readiness — whether an agent can accept and execute work — not infrastructure management. Agent pools are defined as a concept; assignment logic is explicitly out of scope.

## Motivation

The protocol currently treats agents as implicit participants. An agent appears when it claims a lease (RFC-0003) or is referenced in an intent event (RFC-0001), but there is no formal record of the agent's existence, capabilities, health, or availability. This creates several coordination gaps:

1. **Ghost agents.** A coordinator delegates work to an agent that crashed. The task sits in "claimed" state until the lease expires. The coordinator has no mechanism to distinguish a slow agent from a dead one until the timeout fires — which may be minutes or hours.

2. **No capability discovery.** A coordinator that needs an agent with specific capabilities (e.g., billing, translation, code review) must know agent IDs in advance or rely on out-of-band configuration. There is no protocol-level registry to answer "which agents can do this work?"

3. **No graceful shutdown.** An agent that needs to restart — for updates, scaling, or maintenance — has no way to signal "stop sending me work, I'm going away." It simply disappears, and the system discovers this through lease timeouts.

4. **No capacity awareness.** A coordinator assigns 50 tasks to an agent that can handle 5 concurrently. The agent has no way to declare its capacity, and the coordinator has no way to query it.

5. **Replacement ambiguity.** When an agent is replaced (same role, new instance), the relationship between old and new instance is undefined. Working memory handoff (RFC-0015) handles state transfer, but there is no identity continuity at the protocol level.

### Scope Boundary

This RFC defines **coordination readiness**: can an agent accept work, is it healthy, is it going away? It does not define infrastructure concerns such as container orchestration, network topology, resource provisioning, or deployment strategy. Implementations may run agents as processes, containers, serverless functions, or browser tabs — the protocol is indifferent. The heartbeat protocol checks coordination availability, not system health metrics.

## Specification

### 1. Agent Record

An agent record is the protocol-level representation of a participating agent. It is created at registration and updated through heartbeats and status transitions.

```json
{
  "agent_id": "agent_billing_01",
  "role_id": "billing-processor",
  "name": "Billing Processor",
  "capabilities": ["billing", "invoicing", "stripe-integration"],
  "capacity": {
    "max_concurrent_tasks": 5,
    "current_load": 2
  },
  "status": "active",
  "endpoint": "https://billing-agent.example.com/webhook",
  "heartbeat_config": {
    "interval_seconds": 30,
    "unhealthy_after_seconds": 90,
    "dead_after_seconds": 300
  },
  "metadata": {},
  "registered_at": "2026-02-08T10:00:00Z",
  "last_heartbeat_at": "2026-02-08T10:29:45Z",
  "version": 14
}
```

#### 1.1 Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `agent_id` | string | Yes | Unique identifier for this agent instance (server-generated or client-provided). |
| `role_id` | string | No | Stable identifier for the agent's role. Multiple instances may share a role ID (see Section 7). |
| `name` | string | No | Human-readable name for display and logging. |
| `capabilities` | string[] | No | List of capability tags describing what work this agent can perform. Used for discovery queries. |
| `capacity.max_concurrent_tasks` | integer | No | Maximum number of tasks this agent can execute concurrently. Advisory (see Section 8.4). |
| `capacity.current_load` | integer | No | Number of tasks currently in progress. Updated via heartbeats. |
| `status` | string | Yes | Current lifecycle status (see Section 2). |
| `endpoint` | string | No | URL for push notifications (task assignments, drain requests). Not used by the heartbeat protocol. |
| `heartbeat_config.interval_seconds` | integer | No | How often the agent sends heartbeats. Default: 30. |
| `heartbeat_config.unhealthy_after_seconds` | integer | No | Seconds of silence before the server marks the agent unhealthy. Default: 90. |
| `heartbeat_config.dead_after_seconds` | integer | No | Seconds of silence before the server marks the agent dead. Default: 300. |
| `metadata` | object | No | Implementation-specific data (version, runtime, resource metrics). The protocol does not inspect this field. |
| `registered_at` | string (ISO 8601) | Yes | Timestamp of initial registration (server-generated). |
| `last_heartbeat_at` | string (ISO 8601) | Yes | Timestamp of the most recently received heartbeat (server-generated). |
| `version` | integer | Yes | Optimistic concurrency version, incremented on every state change. |

### 2. Status Lifecycle

An agent transitions through the following states:

```
                    ┌────────────────────────────────────────┐
                    │                                        │
  ┌─────────────┐   │  ┌──────────┐     ┌──────────────────┐ │
  │ registering │───┼─▸│  active   │────▸│    draining      │─┼──▸ deregistered
  └─────────────┘   │  └──────────┘     └──────────────────┘ │
                    │       │                    │            │
                    │       ▼                    │            │
                    │  ┌──────────┐              │            │
                    │  │unhealthy │──────────────┘            │
                    │  └──────────┘                           │
                    │       │                                 │
                    │       ▼                                 │
                    │  ┌──────────┐                           │
                    │  │   dead   │───────────────────────────┘
                    │  └──────────┘                           │
                    └────────────────────────────────────────┘
```

#### 2.1 State Definitions

| State | Description |
|-------|-------------|
| `registering` | Agent has sent a registration request. Transitions to `active` upon successful registration. This state is transient and exists only during the registration handshake. |
| `active` | Agent is healthy and accepting tasks. Heartbeats are arriving within the configured threshold. |
| `draining` | Agent has signaled intent to shut down. Not accepting new tasks. Finishing current work. Transitions to `deregistered` when all tasks complete or drain timeout expires. |
| `unhealthy` | Agent has missed heartbeats beyond `unhealthy_after_seconds`. The server emits a warning event but does not reassign tasks. If heartbeats resume, transitions back to `active`. If silence continues, transitions to `dead`. |
| `dead` | Agent has missed heartbeats beyond `dead_after_seconds`. All held leases are expired (Section 6). Tasks are eligible for reassignment. The agent record is retained for audit. |
| `deregistered` | Agent has completed a graceful drain or been explicitly deregistered. The agent record is retained for audit but the agent is no longer a participant. |

#### 2.2 Valid Transitions

| From | To | Trigger |
|------|----|---------|
| `registering` | `active` | Registration accepted by server. |
| `active` | `draining` | Agent sends drain request (Section 4). |
| `active` | `unhealthy` | No heartbeat received within `unhealthy_after_seconds`. |
| `unhealthy` | `active` | Heartbeat received (agent recovered). |
| `unhealthy` | `dead` | No heartbeat received within `dead_after_seconds`. |
| `unhealthy` | `draining` | Agent sends drain request while unhealthy (recovering and shutting down). |
| `draining` | `deregistered` | All current tasks completed, or drain timeout expired. |
| `draining` | `dead` | Drain timeout expired with tasks still in progress and no heartbeats. |
| `dead` | `active` | Agent re-registers with the same `agent_id` (restart scenario). Previous leases remain expired; agent starts fresh. |

#### 2.3 Status Events

Every status transition MUST produce an intent event of type `agent.lifecycle` appended to the system event log:

```json
{
  "type": "agent.lifecycle",
  "agent_id": "agent_billing_01",
  "previous_status": "active",
  "new_status": "unhealthy",
  "reason": "heartbeat_timeout",
  "timestamp": "2026-02-08T10:32:30Z"
}
```

Coordinators monitoring the event log can react to lifecycle changes — for example, by pre-emptively querying the registry for replacement agents when a worker becomes unhealthy.

### 3. Registration

#### 3.1 Registration Request

```
POST /api/v1/agents
Content-Type: application/json
X-API-Key: {api_key}

{
  "agent_id": "agent_billing_01",
  "role_id": "billing-processor",
  "name": "Billing Processor",
  "capabilities": ["billing", "invoicing", "stripe-integration"],
  "capacity": {
    "max_concurrent_tasks": 5
  },
  "endpoint": "https://billing-agent.example.com/webhook",
  "heartbeat_config": {
    "interval_seconds": 30,
    "unhealthy_after_seconds": 90,
    "dead_after_seconds": 300
  },
  "metadata": {
    "version": "1.2.0",
    "runtime": "python-3.11"
  }
}
```

#### 3.2 Registration Response

```
201 Created
Content-Type: application/json
ETag: "1"

{
  "agent_id": "agent_billing_01",
  "role_id": "billing-processor",
  "name": "Billing Processor",
  "capabilities": ["billing", "invoicing", "stripe-integration"],
  "capacity": {
    "max_concurrent_tasks": 5,
    "current_load": 0
  },
  "status": "active",
  "endpoint": "https://billing-agent.example.com/webhook",
  "heartbeat_config": {
    "interval_seconds": 30,
    "unhealthy_after_seconds": 90,
    "dead_after_seconds": 300
  },
  "metadata": {
    "version": "1.2.0",
    "runtime": "python-3.11"
  },
  "registered_at": "2026-02-08T10:00:00Z",
  "last_heartbeat_at": "2026-02-08T10:00:00Z",
  "version": 1
}
```

#### 3.3 Registration Semantics

- If `agent_id` is omitted, the server generates one (recommended format: `agent_{ulid}`).
- If `agent_id` is provided and already exists with status `dead` or `deregistered`, the server re-activates the record (new registration, same ID). Version is reset. This supports agent restart scenarios.
- If `agent_id` is provided and already exists with status `active`, `draining`, or `unhealthy`, the server returns `409 Conflict`. An agent must deregister or die before re-registering with the same ID.
- `heartbeat_config` values are validated: `unhealthy_after_seconds` MUST be ≥ 2× `interval_seconds`. `dead_after_seconds` MUST be ≥ 2× `unhealthy_after_seconds`.
- Registration is **optional for standalone agents.** An agent with direct grants (RFC-0014) that does not participate in coordinated workflows is not required to register. It can interact with intents and tools directly. Registration is for agents that need discoverability, health monitoring, or pool membership.

#### 3.4 Uniform Registration

Both the declarative path (`@Agent` decorator) and the imperative path (`client.agents.register(...)`) MUST produce identical protocol-level effects:

1. A `POST /api/v1/agents` request is sent.
2. An `agent.lifecycle` event with `new_status: "active"` is recorded.
3. The agent appears in registry queries.
4. Heartbeat monitoring begins.

The decorator provides syntactic convenience; the protocol operation is the same.

### 4. Heartbeat Protocol

#### 4.1 Heartbeat Request

Agents send heartbeats by posting to the server. This is a pull model: the agent initiates the request, not the server.

```
POST /api/v1/agents/{agent_id}/heartbeat
Content-Type: application/json
X-API-Key: {api_key}

{
  "status": "active",
  "current_load": 3,
  "tasks_in_progress": ["task_01H001", "task_01H002", "task_01H003"],
  "client_timestamp": "2026-02-08T10:30:00Z"
}
```

#### 4.2 Heartbeat Response

```
200 OK
Content-Type: application/json

{
  "acknowledged": true,
  "server_timestamp": "2026-02-08T10:30:00.123Z",
  "agent_status": "active",
  "pending_commands": []
}
```

#### 4.3 Heartbeat Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `status` | string | Yes | Agent's self-reported status. Must be `active` or `draining`. |
| `current_load` | integer | No | Number of tasks currently in progress. |
| `tasks_in_progress` | string[] | No | IDs of tasks the agent is currently executing. Enables the server to cross-reference with lease records. |
| `client_timestamp` | string (ISO 8601) | Yes | The agent's local timestamp when the heartbeat was generated. Used for drift detection (Section 4.5). |

#### 4.4 Heartbeat Semantics

- A successful heartbeat resets the agent's silence timer.
- If the agent's server-side status is `unhealthy` and a heartbeat arrives, the server transitions the agent back to `active` and emits an `agent.lifecycle` event with reason `heartbeat_resumed`.
- Heartbeats from agents in `dead` or `deregistered` status are rejected with `410 Gone`. The agent must re-register.
- The `pending_commands` field in the response allows the server to communicate directives to the agent (e.g., `drain_requested`). This enables server-initiated drain without requiring the server to reach the agent's endpoint.

#### 4.5 Jitter Tolerance and Drift Detection

Network latency, garbage collection pauses, and transient failures can delay heartbeats. The protocol uses **threshold-based detection**, not strict interval enforcement:

- **Unhealthy threshold:** The server marks an agent unhealthy when `now - last_heartbeat_at > unhealthy_after_seconds`. With default values (interval=30s, unhealthy_after=90s), the agent can miss 2 heartbeats entirely and deliver the third 30 seconds late before being marked unhealthy.

- **Dead threshold:** The server marks an agent dead when `now - last_heartbeat_at > dead_after_seconds`. With default values (dead_after=300s), the agent has 5 minutes of total silence before being declared dead.

- **Clock drift detection:** The server compares `client_timestamp` with its own receipt timestamp. If the difference exceeds `interval_seconds × 2`, the server SHOULD log a drift warning. The server MUST NOT use client timestamps for health decisions — only server-side receipt timestamps govern lifecycle transitions.

- **Latency-degraded networks:** Progressive latency (50ms → 1s → 10s → 30s) causes heartbeats to arrive later and later. The threshold model handles this naturally: as long as heartbeats arrive within `unhealthy_after_seconds` of the previous one, the agent remains active. The thresholds are deliberately generous (default 90s for unhealthy) to tolerate significant network degradation without false positives.

#### 4.6 Network Partition Behavior

During a complete network partition:

1. The agent's heartbeats cannot reach the server.
2. After `unhealthy_after_seconds`, the server marks the agent unhealthy.
3. After `dead_after_seconds`, the server marks the agent dead and expires all held leases (Section 6).
4. The coordinator assigns the dead agent's tasks to a replacement.
5. The network recovers. The original agent attempts a heartbeat.
6. The server rejects the heartbeat with `410 Gone` (agent is dead).
7. The original agent re-registers, discovers its leases have expired, and stops any in-progress work.
8. **Split-brain prevention:** Leases (RFC-0003) are the authoritative record of task ownership. Even if both agents are temporarily alive, only the one holding a valid lease may write results. The original agent's lease expired during the partition, so its writes will be rejected with `412 Precondition Failed`.

This interaction between heartbeats and leases is critical. The heartbeat protocol detects the problem; the leasing protocol prevents inconsistency.

### 5. Graceful Drain

#### 5.1 Initiating a Drain

An agent signals its intent to shut down by sending a drain request:

```
PATCH /api/v1/agents/{agent_id}/status
Content-Type: application/json
X-API-Key: {api_key}
If-Match: "14"

{
  "status": "draining",
  "drain_timeout_seconds": 120
}
```

#### 5.2 Drain Semantics

1. The server transitions the agent to `draining` status.
2. An `agent.lifecycle` event is emitted with reason `drain_initiated`.
3. The server stops including this agent in capability discovery results (Section 5).
4. The agent continues sending heartbeats during drain (to confirm it is still alive and working).
5. The agent completes its current tasks and releases leases normally.
6. When all leases held by the agent are released, the server transitions to `deregistered`.
7. If `drain_timeout_seconds` elapses and the agent still holds leases:
   - The server emits a warning event.
   - The server transitions the agent to `dead` and expires remaining leases.
   - Tasks are eligible for reassignment.

#### 5.3 Server-Initiated Drain

A coordinator or administrator may request an agent to drain via the `pending_commands` field in the heartbeat response:

```json
{
  "acknowledged": true,
  "server_timestamp": "2026-02-08T10:30:00.123Z",
  "agent_status": "active",
  "pending_commands": [
    {
      "command": "drain",
      "reason": "maintenance_window",
      "drain_timeout_seconds": 120
    }
  ]
}
```

The agent SHOULD honor drain commands by transitioning to `draining` status on its next heartbeat. If the agent ignores the command, the coordinator may escalate through RFC-0013 guardrails or by revoking the agent's grants (RFC-0014).

### 6. Agent Registry & Discovery

#### 6.1 Listing Agents

```
GET /api/v1/agents?capabilities=billing&status=active
```

Response:

```json
{
  "agents": [
    {
      "agent_id": "agent_billing_01",
      "role_id": "billing-processor",
      "name": "Billing Processor",
      "capabilities": ["billing", "invoicing", "stripe-integration"],
      "capacity": {
        "max_concurrent_tasks": 5,
        "current_load": 2
      },
      "status": "active",
      "last_heartbeat_at": "2026-02-08T10:29:45Z"
    },
    {
      "agent_id": "agent_billing_02",
      "role_id": "billing-processor",
      "name": "Billing Processor (Instance 2)",
      "capabilities": ["billing", "invoicing"],
      "capacity": {
        "max_concurrent_tasks": 5,
        "current_load": 4
      },
      "status": "active",
      "last_heartbeat_at": "2026-02-08T10:29:50Z"
    }
  ],
  "total": 2
}
```

#### 6.2 Query Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `capabilities` | string (comma-separated) | Filter by capability tags. Returns agents matching ANY of the specified capabilities. |
| `status` | string (comma-separated) | Filter by status. Default: `active`. |
| `role_id` | string | Filter by role ID. |
| `min_available_capacity` | integer | Filter to agents with `max_concurrent_tasks - current_load >= value`. |

#### 6.3 Single Agent Lookup

```
GET /api/v1/agents/{agent_id}
```

Returns the full agent record including `metadata`, `heartbeat_config`, and `endpoint`.

### 7. Agent Pools

#### 7.1 Concept

An **agent pool** is a set of agent instances that share a `role_id`. Pool members have the same capabilities and can perform the same work. The pool abstraction enables horizontal scaling: multiple instances of the same agent role can be registered, and coordinators can distribute work across them.

#### 7.2 Protocol Semantics

The protocol defines pool membership through `role_id`:

- All agents sharing a `role_id` are members of the same pool.
- Pool membership is queryable: `GET /api/v1/agents?role_id=billing-processor` returns all instances.
- Pool-level capacity is the sum of member capacities: `sum(max_concurrent_tasks) - sum(current_load)`.
- Each pool member has an independent lifecycle. One instance going unhealthy does not affect others.

#### 7.3 Assignment Logic (Out of Scope)

The protocol does **not** define how tasks are assigned to specific pool members. Coordinators decide. Possible strategies include:

- Round-robin across active members.
- Least-loaded member (lowest `current_load`).
- Capability-weighted selection (prefer members with more specific capabilities).
- Affinity-based (prefer the member that handled previous tasks in the same intent graph).

Assignment strategy is an implementation concern. The protocol provides the data (capabilities, capacity, status) that coordinators need to make informed decisions.

### 8. Instance Identity vs. Role Identity

#### 8.1 Definitions

- **`agent_id`** — Unique to a running instance. Two simultaneously running agents MUST NOT share an `agent_id`. When an agent restarts, it MAY re-register with the same `agent_id` (if the previous record is `dead` or `deregistered`) or register with a new one.

- **`role_id`** — Stable across restarts and instances. Identifies what the agent does, not who it is right now. Multiple running instances MAY share a `role_id` (pool members). A restarted agent SHOULD use the same `role_id` as its predecessor.

#### 8.2 Memory Continuity

When a replacement agent registers with the same `role_id`:

- **Episodic memory (RFC-0015):** Accessible to any agent with the same `role_id`. Learned patterns survive agent restarts. The episodic memory scope filter `agent_role_id` enables this.
- **Working memory (RFC-0015):** If the original agent's working memory was not archived (because the task is still in progress), a replacement agent with the same `role_id` can access it for task resumption. This requires explicit coordination — the coordinator assigns the task to the replacement and grants working memory access.
- **Semantic memory (RFC-0015):** Unaffected by agent lifecycle. Shared knowledge persists independently of any agent.

#### 8.3 Audit Trail

The event log always records `agent_id` (instance), not `role_id`. This ensures that the audit trail shows exactly which instance performed each action, even when multiple instances of the same role are active.

### 9. Integration with RFC-0003 (Leasing)

Agent lifecycle and leasing are complementary systems with explicit ordering:

#### 9.1 Lifecycle Death Triggers Lease Expiry

When the server transitions an agent to `dead`:

1. The server queries all active leases held by the agent.
2. Each lease is expired with reason `agent_dead`.
3. Lease expiry events are appended to the relevant intent event logs.
4. Tasks associated with expired leases become eligible for reassignment.
5. Coordinators observing the event log can assign tasks to healthy agents.

This ordering is mandatory: lifecycle death **causes** lease expiry, not the reverse. A lease expiring due to timeout (the agent held it too long) does not affect the agent's lifecycle status.

#### 9.2 Unhealthy Agents and Leases

When an agent becomes `unhealthy`:

- Existing leases are **not** expired. The agent may recover.
- New lease requests from the unhealthy agent are accepted (the agent may still be functioning, just with network issues).
- Coordinators MAY choose not to assign new tasks to unhealthy agents, but the protocol does not enforce this.

#### 9.3 Draining Agents and Leases

When an agent is `draining`:

- Existing leases remain valid. The agent is expected to complete them.
- New lease requests from the draining agent SHOULD be rejected by the server (the agent should be finishing work, not starting new work).
- When all leases are released, the agent transitions to `deregistered`.

### 10. Integration with Other RFCs

#### 10.1 RFC-0011 (Access Control)

Agent registration respects the same access control model. An agent's capabilities determine what it is permitted to do; access grants determine what it is authorized to do. Capabilities are self-declared at registration. Grants are assigned by coordinators or administrators through RFC-0011 permissions.

#### 10.2 RFC-0013 (Coordinator Governance)

Coordinators are agents with the `coordinator` capability. They register, send heartbeats, and follow the same lifecycle as worker agents. Coordinator-specific governance (supervisor hierarchies, guardrails, failover) is defined in RFC-0013 and operates on top of the lifecycle primitives defined here.

A coordinator transitioning to `dead` triggers the coordinator failover process defined in RFC-0013.

#### 10.3 RFC-0014 (Credential Vaults)

Tool grants are associated with `agent_id`. When an agent re-registers after death (same `agent_id`, new lifecycle), existing grants are preserved — the agent does not need to re-request tool access. Grants associated with an `agent_id` that has been `deregistered` are retained but dormant; they activate when the agent re-registers.

#### 10.4 RFC-0015 (Agent Memory)

See Section 8.2 for memory continuity semantics across agent lifecycle transitions.

### 11. API Summary

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/agents` | Register a new agent. |
| `GET` | `/api/v1/agents` | List/query agents (with filters). |
| `GET` | `/api/v1/agents/{agent_id}` | Get a single agent record. |
| `PATCH` | `/api/v1/agents/{agent_id}/status` | Update agent status (drain, deregister). |
| `POST` | `/api/v1/agents/{agent_id}/heartbeat` | Send a heartbeat. |
| `DELETE` | `/api/v1/agents/{agent_id}` | Deregister an agent (immediate, no drain). |

All endpoints require `X-API-Key` authentication. Status updates use `If-Match` for optimistic concurrency.

### 12. YAML Workflow Integration

Agent lifecycle configuration can be specified in YAML workflows:

```yaml
agents:
  billing-processor:
    role_id: billing-processor
    capabilities:
      - billing
      - invoicing
      - stripe-integration
    capacity:
      max_concurrent_tasks: 5
    heartbeat:
      interval_seconds: 30
      unhealthy_after_seconds: 90
      dead_after_seconds: 300
    drain_timeout_seconds: 120
    pool:
      min_instances: 1
      max_instances: 5

  code-reviewer:
    role_id: code-reviewer
    capabilities:
      - code-review
      - linting
    capacity:
      max_concurrent_tasks: 3
    heartbeat:
      interval_seconds: 60
      unhealthy_after_seconds: 180
      dead_after_seconds: 600
```

The `pool.min_instances` and `pool.max_instances` fields are advisory. The protocol does not enforce scaling; orchestration systems (if any) can read these values to inform scaling decisions.

## Security Considerations

- **Heartbeat spoofing:** An attacker sending heartbeats for another agent's ID could keep a dead agent appearing alive. Heartbeat endpoints MUST validate the `X-API-Key` and ensure it matches the agent's registration credentials.
- **Registry enumeration:** The agent listing endpoint exposes capability information. Implementations SHOULD restrict registry access to coordinators and administrators via RFC-0011 permissions.
- **Drain abuse:** An unauthorized drain request could take an agent offline. Status update endpoints MUST enforce authorization — only the agent itself, its coordinator, or an administrator can change an agent's status.

## Rationale

### Pull-Based Heartbeats

The agent sends heartbeats to the server, rather than the server polling agents. This design:
- Works across network boundaries (agents behind firewalls, NATs, load balancers).
- Does not require the server to manage outbound connections.
- Scales linearly: adding agents does not increase server-side polling work.
- Fails safely: if the network is down, heartbeats stop, and the server correctly infers the agent is unreachable.

### Two-Threshold Health Detection

The `unhealthy` → `dead` progression prevents premature task reassignment. A brief network glitch should not trigger a full failover cascade. The unhealthy state is a warning that gives the agent time to recover. Only sustained silence triggers the dead state and its consequences (lease expiry, task reassignment).

### Capacity as Advisory

The protocol reports capacity; it does not enforce it. A coordinator MAY send a task to an agent that reports zero available capacity — perhaps the task is urgent, or the coordinator knows the agent will finish current work soon. Guardrails (RFC-0013) can enforce hard limits if an implementation requires them.

### Registration as Optional

Standalone agents that interact with intents directly (using direct grants from RFC-0014) do not need registration, health monitoring, or discovery. Making registration mandatory would add overhead for simple use cases. The protocol accommodates both patterns: lightweight standalone agents and fully managed pool members.
