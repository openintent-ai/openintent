# RFC-0011: Access-Aware Coordination v2.0

| Field       | Value                                |
|-------------|--------------------------------------|
| RFC         | 0011                                 |
| Title       | Access-Aware Coordination            |
| Status      | Proposed                             |
| Created     | 2026-02-07                           |
| Authors     | OpenIntent Contributors              |
| Requires    | RFC-0001, RFC-0002, RFC-0003         |

## Abstract

This RFC defines **access-aware coordination** for the OpenIntent protocol. Beyond controlling which principals (humans and agents) may read, write, or administer an intent, it introduces **automatic context injection** — when an agent gains access to an intent, it immediately receives a rich `IntentContext` object describing its role, its peers, upstream results, and the broader coordination landscape. The result is a system where access control is not merely a gate but a coordination primitive: granting access *is* onboarding.

Every access grant is attributed to the principal who authorized it, creating a clear chain of responsibility. The design integrates with RFC-0003 Governance so that access requests flow through the same arbitration and decision-record infrastructure already in place, and exposes a Pythonic SDK that makes the common case elegant and the complex case possible.

## Motivation

The current protocol assumes any authenticated principal can interact with any intent. In production multi-agent systems this creates problems:

- **Confidentiality**: Sensitive intents (legal, financial, HR) should not be visible to all agents.
- **Blast radius**: A misbehaving agent can modify intents it has no business touching.
- **Regulatory compliance**: Audit requirements demand proof of who authorized agent access.
- **Principle of least privilege**: Agents should only access the intents they need for their assigned work.
- **Context gap**: Even when agents *are* granted access, they arrive without understanding — they don't know who else is working, what upstream work produced, what their specific role is, or who delegated the task. This forces every agent to make expensive API calls to reconstruct context that the system already knows.
- **Coordination blindness**: Agents cannot see their peers, cannot understand the dependency graph, and cannot make informed decisions about escalation or delegation without custom integration work.

Without access-aware coordination, organizations must rely on network-level isolation or custom middleware, which fragments the protocol and defeats interoperability. And without context injection, even properly permissioned agents operate in the dark.

## Design Principles

1. **Simple over complex**: Three permission levels, not a full RBAC/ABAC system.
2. **Attribution first**: Every grant records who authorized it.
3. **Governance integration**: Access requests reuse the arbitration/decision pipeline from RFC-0003.
4. **Pythonic SDK design**: The SDK should make the common case a one-liner. Policy-as-code via decorators, context via `intent.ctx`, delegation via method calls. Invisible complexity — the hard parts (token refresh, context filtering, lease cleanup) happen automatically.
5. **Invisible complexity**: Developers interact with clean abstractions; the protocol handles filtering, lifecycle, and cleanup behind the scenes.
6. **Deny by default**: When an ACL exists, unlisted principals have no access.

## Permission Model

### Permission Levels

| Level   | Capabilities |
|---------|-------------|
| `read`  | View intent metadata, state, events, attachments, and cost summaries. Subscribe to events (RFC-0006). |
| `write` | All of `read`, plus: patch state, emit events, acquire leases (RFC-0003), add attachments (RFC-0005), record costs (RFC-0009). |
| `admin` | All of `write`, plus: change intent status, modify the ACL (grant/revoke access), configure retry policies (RFC-0010), create child intents (RFC-0002), request arbitration, record decisions. |

Permission levels are cumulative: `admin` includes `write`, which includes `read`.

## Access Control List (ACL)

Each intent carries an optional Access Control List. When present, it restricts access to listed principals. When absent, the intent uses the server's default policy (typically open access for backward compatibility).

```json
{
  "intent_id": "uuid",
  "default_policy": "open | closed",
  "entries": [
    {
      "id": "uuid",
      "principal_id": "string",
      "principal_type": "user | agent | group",
      "permission": "read | write | admin",
      "granted_by": "string",
      "granted_at": "ISO 8601",
      "expires_at": "ISO 8601 | null",
      "reason": "string | null"
    }
  ]
}
```

### Field Definitions

| Field            | Type     | Required | Description |
|------------------|----------|----------|-------------|
| `intent_id`      | UUID     | Yes      | The intent this ACL belongs to. |
| `default_policy` | enum     | Yes      | `open` allows any authenticated principal when no ACL entry matches. `closed` denies access to unlisted principals. |
| `entries`         | array    | Yes      | List of ACL entries (may be empty). |
| `entries[].id`   | UUID     | Yes      | Unique identifier for this entry. |
| `entries[].principal_id` | string | Yes | Identifier of the user, agent, or group. |
| `entries[].principal_type` | enum | Yes | One of `user`, `agent`, or `group`. |
| `entries[].permission` | enum | Yes | One of `read`, `write`, or `admin`. |
| `entries[].granted_by` | string | Yes | Principal ID of whoever authorized this entry. |
| `entries[].granted_at` | ISO 8601 | Yes | Timestamp of when access was granted. |
| `entries[].expires_at` | ISO 8601 | No | Optional expiration. Null means no expiry. |
| `entries[].reason` | string | No | Human-readable justification for the grant. |

### Default Behavior

- **No ACL on intent**: The server's global default policy applies. Servers SHOULD default to `open` for backward compatibility with pre-0011 deployments.
- **ACL with `default_policy: open`**: Listed entries take precedence; unlisted principals get `read` access.
- **ACL with `default_policy: closed`**: Only listed principals have access. All others receive `403 Forbidden`.

### Creator Privileges

The principal identified in `created_by` on the intent object automatically receives `admin` permission. This is implicit and does not require an explicit ACL entry.

## IntentContext — Automatic Context Injection

The core innovation of access-aware coordination is the `IntentContext` object. When an agent accesses an intent through the SDK, the context is **automatically populated** and available as `intent.ctx`. The agent never needs to make separate API calls to understand its environment.

### Context Fields

| Field | Type | Description |
|-------|------|-------------|
| `intent.ctx.parent` | `IntentSummary \| None` | The parent intent (if this is a child intent per RFC-0002). |
| `intent.ctx.dependencies` | `dict[str, DependencyState]` | Results from upstream intents in the dependency graph, keyed by intent title. |
| `intent.ctx.events` | `list[Event]` | Recent event history for this intent. |
| `intent.ctx.acl` | `ACL \| None` | The access control list — who else is working on this intent. |
| `intent.ctx.my_permission` | `str` | The current agent's permission level: `"read"`, `"write"`, or `"admin"`. |
| `intent.ctx.attachments` | `list[Attachment]` | Files and data attached to the intent (RFC-0005). |
| `intent.ctx.peers` | `list[PeerInfo]` | Other agents currently working on this intent, with their permissions. |
| `intent.ctx.delegated_by` | `DelegationInfo \| None` | Set when this work was delegated from another agent. Contains the delegating agent's ID, the original intent, and any payload. |

### Context Filtering by Permission Level

The context object is **filtered based on the agent's permission level**. This ensures agents only see what they're authorized to see, without requiring the developer to implement filtering logic.

| Field | `read` sees | `write` sees | `admin` sees |
|-------|-------------|--------------|--------------|
| `parent` | title, status | title, status, state | everything |
| `dependencies` | final results only | results + working state | everything |
| `events` | public events | public + state events | all events |
| `acl` | not visible | own entry only | full ACL |
| `peers` | agent IDs only | IDs + permissions | full details |
| `attachments` | public attachments | all attachments | all + metadata |

### Context Population

The server populates `IntentContext` at access time. The SDK caches the context and refreshes it when:

1. The agent receives a real-time event (RFC-0006) indicating a relevant change.
2. The agent explicitly calls `intent.refresh_ctx()`.
3. A configurable TTL expires (default: 30 seconds).

### Example: Using Context in an Agent

```python
from openintent import Agent, on_assignment

@Agent("research-bot", capabilities=["web-search", "summarization"])
class ResearchAgent:

    @on_assignment
    async def handle(self, intent):
        # Context is already populated — no extra API calls needed
        print(f"My permission: {intent.ctx.my_permission}")
        print(f"Peers working on this: {[p.agent_id for p in intent.ctx.peers]}")

        if intent.ctx.delegated_by:
            print(f"Delegated by: {intent.ctx.delegated_by.agent_id}")
            print(f"Delegation payload: {intent.ctx.delegated_by.payload}")

        # Check upstream results
        for title, dep in intent.ctx.dependencies.items():
            print(f"Upstream '{title}': {dep.status} — {dep.result}")

        # Check parent intent
        if intent.ctx.parent:
            print(f"Part of: {intent.ctx.parent.title} ({intent.ctx.parent.status})")

        # Do the actual work...
        findings = await self.research(intent.state.get("query"))

        # Update state (requires write permission)
        await intent.patch({"findings": findings})
```

## Capability Declaration

Agents declare their capabilities as a list of strings. This enables the system (and other agents) to make informed decisions about delegation and assignment.

```python
from openintent import Agent

@Agent("ocr-bot", capabilities=["ocr", "pdf-extraction", "image-analysis"])
class OCRAgent:
    pass

@Agent("legal-reviewer", capabilities=["legal-review", "compliance-check", "risk-assessment"])
class LegalReviewer:
    pass
```

Capabilities are advisory — they describe what an agent *can* do, not what it's *allowed* to do. Permission to act on a specific intent is still governed by the ACL. Capabilities are exposed via the agent registry and can be queried when deciding which agent to delegate work to.

### Capability Matching

When delegating work, agents can query available capabilities:

```python
# Find an agent that can do legal review
candidates = await intent.find_agents(capability="legal-review")
await intent.delegate(candidates[0].agent_id, payload={"document": doc})
```

## Pythonic SDK Design

The SDK is designed so that the common case is a one-liner and complex cases compose cleanly. The principle is **invisible complexity** — developers interact with clean abstractions while the SDK handles filtering, lifecycle, token management, and cleanup behind the scenes.

### Policy-as-Code with Decorators

```python
from openintent import Agent, on_access_requested, on_assignment

@Agent("orchestrator", capabilities=["coordination", "delegation"])
class Orchestrator:

    @on_access_requested
    async def handle_access_request(self, request, intent):
        """Automatically evaluate access requests. Return 'approve', 'deny', or 'defer'."""
        # Auto-approve research agents for research intents
        if "research" in request.principal_id and intent.title.startswith("Research:"):
            return "approve"

        # Auto-approve agents with required capabilities
        agent_info = await self.lookup_agent(request.principal_id)
        if agent_info and "summarization" in agent_info.capabilities:
            return "approve"

        # Defer everything else to human admin
        return "defer"

    @on_assignment
    async def handle(self, intent):
        # Orchestrator logic here
        pass
```

### Escalation

```python
@on_assignment
async def handle(self, intent):
    findings = await self.analyze(intent.state)

    if findings.risk_level == "critical":
        # Escalate to an admin — SDK handles the governance flow
        await intent.escalate(
            reason="Critical risk findings require human review",
            data={"risk_level": "critical", "findings": findings.summary}
        )
```

### Delegation

```python
@on_assignment
async def handle(self, intent):
    findings = await self.research(intent.state.get("query"))

    if findings.contains_legal_risk:
        # Delegate to legal reviewer — SDK grants access, sends context
        await intent.delegate(
            agent_id="legal-reviewer",
            payload={
                "flagged_content": findings.flagged_items,
                "risk_category": "regulatory",
                "urgency": "high"
            }
        )
```

When `legal-reviewer` receives this delegation, its `intent.ctx.delegated_by` is automatically populated:

```python
@Agent("legal-reviewer", capabilities=["legal-review", "compliance-check"])
class LegalReviewer:

    @on_assignment
    async def handle(self, intent):
        # Context tells us who delegated and why
        delegation = intent.ctx.delegated_by
        print(f"Delegated by: {delegation.agent_id}")
        print(f"Payload: {delegation.payload}")
        # delegation.payload == {"flagged_content": [...], "risk_category": "regulatory", "urgency": "high"}

        # We also get full context about the intent itself
        print(f"My permission: {intent.ctx.my_permission}")
        print(f"Parent intent: {intent.ctx.parent.title if intent.ctx.parent else 'None'}")
```

### Scoped Temporary Access

```python
@on_assignment
async def handle(self, intent):
    # Grant temporary access that is automatically revoked when the block exits
    async with intent.temp_access("auditor-agent", permission="read") as grant:
        # auditor-agent can read for the duration of this block
        await self.wait_for_audit_completion()
    # Access automatically revoked here — SDK handles cleanup
```

### Auto-Request Access on 403

```python
from openintent import Client

client = Client(
    base_url="http://localhost:8000",
    agent_id="research-bot",
    auto_request_access=True  # SDK automatically requests access on 403
)

# If the agent doesn't have access, the SDK will:
# 1. Catch the 403
# 2. Submit an access request with the agent's identity
# 3. Wait for approval (with configurable timeout)
# 4. Retry the original request
intent = await client.get_intent("intent-uuid")
```

## Access Grants and Revocation

### Granting Access

Access is granted by a principal with `admin` permission on the intent. Every grant produces:

1. A new ACL entry with the `granted_by` field set to the granting principal.
2. An event of type `access_granted` appended to the intent's event log.
3. The `IntentContext` for the newly granted principal is immediately populated.

```json
{
  "type": "access_granted",
  "actor": "admin-user-1",
  "payload": {
    "principal_id": "agent-research",
    "principal_type": "agent",
    "permission": "write",
    "reason": "Assigned to research phase",
    "expires_at": "2026-02-08T00:00:00Z"
  }
}
```

### Revoking Access

Revocation removes an ACL entry. Only `admin` principals can revoke. Revocation produces:

1. Removal of the ACL entry.
2. An event of type `access_revoked` appended to the intent's event log.
3. If the revoked principal holds any active leases (RFC-0003) on this intent, those leases are automatically revoked.
4. The SDK automatically handles cleanup — any active connections, subscriptions, or cached context for the revoked principal are invalidated.

```json
{
  "type": "access_revoked",
  "actor": "admin-user-1",
  "payload": {
    "principal_id": "agent-research",
    "previous_permission": "write",
    "reason": "Research phase completed"
  }
}
```

### Time-Limited Access

Grants may include `expires_at`. When a grant expires:

- The ACL entry is removed (or marked expired).
- An `access_expired` event is logged.
- Active leases held by that principal on this intent are revoked.
- The SDK detects the expiration and cleans up local state automatically.

Servers SHOULD run periodic expiration checks or evaluate expiry at request time.

## Access Requests (Governance Integration)

When an agent needs access to an intent it cannot currently reach, it submits an **access request**. This integrates directly with RFC-0003 Governance:

### Request Flow

```
Agent (no access)
  |
  +---> POST /v1/intents/{id}/access-requests
  |       { "principal_id": "agent-research",
  |         "permission": "write",
  |         "reason": "Need to contribute research findings" }
  |
  v
AccessRequest created (status: pending)
  |
  +---> @on_access_requested handler evaluated (if policy-as-code is configured)
  |       |
  |       +---> "approve"  --> ACL entry created immediately
  |       +---> "deny"     --> Request denied, agent notified
  |       +---> "defer"    --> Notification sent to intent admins (via RFC-0006)
  |
  v
Admin reviews request (if deferred)
  |
  +---> POST /v1/intents/{id}/access-requests/{requestId}/approve
  |       { "decided_by": "admin-user-1",
  |         "permission": "write",
  |         "expires_at": "2026-02-08T00:00:00Z",
  |         "reason": "Approved for research phase" }
  |
  v
ACL entry created + DecisionRecord logged (RFC-0003) + IntentContext populated
```

### AccessRequest Object

```json
{
  "id": "uuid",
  "intent_id": "uuid",
  "principal_id": "string",
  "principal_type": "user | agent | group",
  "requested_permission": "read | write | admin",
  "reason": "string",
  "status": "pending | approved | denied",
  "decided_by": "string | null",
  "decided_at": "ISO 8601 | null",
  "decision_reason": "string | null",
  "created_at": "ISO 8601"
}
```

### Relationship to RFC-0003 Governance

Access requests are a specific category of governance action. When an access request is approved or denied:

1. A **DecisionRecord** (RFC-0003) is created, linking the access decision to the intent's governance trail.
2. The `decided_by` field provides clear attribution.
3. If the request was escalated via arbitration, the ArbitrationRequest resolution references the access grant.

This means access decisions appear in the same governance audit trail as all other consequential decisions, providing a unified view of who authorized what.

## Inheritance

### Parent-Child Inheritance (RFC-0002)

When creating a child intent, the creator may specify `inherit_access: true`:

```json
{
  "title": "Sub-task",
  "parent_intent_id": "uuid",
  "inherit_access": true
}
```

When `inherit_access` is true:

- The child intent copies the parent's ACL entries at creation time.
- Subsequent changes to the parent ACL do NOT propagate (snapshot, not live reference).
- The child's creator still receives implicit `admin`.

When `inherit_access` is false (default):

- The child starts with no ACL (server default policy applies).
- The creator has implicit `admin`.

### Portfolio-Level Access

Portfolios (RFC-0004) may define a portfolio-level ACL. When a portfolio has an ACL:

- Adding an intent to a portfolio does NOT automatically grant portfolio-level principals access to the intent.
- Portfolio admins can batch-grant access to all member intents via a portfolio-level operation.
- This is a convenience operation; each intent still maintains its own ACL.

## Endpoints

### ACL Management

| Method | Path | Description |
|--------|------|-------------|
| `GET`    | `/v1/intents/{id}/acl` | Get the intent's ACL |
| `PUT`    | `/v1/intents/{id}/acl` | Set the intent's ACL (replace) |
| `POST`   | `/v1/intents/{id}/acl/entries` | Add an ACL entry (grant access) |
| `DELETE`  | `/v1/intents/{id}/acl/entries/{entryId}` | Remove an ACL entry (revoke access) |

### Access Requests

| Method | Path | Description |
|--------|------|-------------|
| `POST`   | `/v1/intents/{id}/access-requests` | Submit an access request |
| `GET`    | `/v1/intents/{id}/access-requests` | List access requests |
| `POST`   | `/v1/intents/{id}/access-requests/{requestId}/approve` | Approve a request |
| `POST`   | `/v1/intents/{id}/access-requests/{requestId}/deny` | Deny a request |

### Request Details

#### POST `/v1/intents/{id}/acl/entries`

Grant access to a principal. Requires `admin` permission on the intent.

**Request body:**

```json
{
  "principal_id": "agent-research",
  "principal_type": "agent",
  "permission": "write",
  "reason": "Assigned to research phase",
  "expires_at": "2026-02-08T00:00:00Z"
}
```

**Response (201 Created):**

```json
{
  "id": "entry-uuid",
  "principal_id": "agent-research",
  "principal_type": "agent",
  "permission": "write",
  "granted_by": "admin-user-1",
  "granted_at": "2026-02-07T12:00:00Z",
  "expires_at": "2026-02-08T00:00:00Z",
  "reason": "Assigned to research phase"
}
```

#### POST `/v1/intents/{id}/access-requests`

Submit a request for access. Any authenticated principal may call this, even without existing access to the intent. The server MUST allow this endpoint to be called without intent-level permissions (otherwise agents could never request access to closed intents).

**Request body:**

```json
{
  "principal_id": "agent-research",
  "principal_type": "agent",
  "requested_permission": "write",
  "reason": "Need to contribute research findings"
}
```

**Response (201 Created):**

```json
{
  "id": "request-uuid",
  "intent_id": "intent-uuid",
  "principal_id": "agent-research",
  "principal_type": "agent",
  "requested_permission": "write",
  "reason": "Need to contribute research findings",
  "status": "pending",
  "created_at": "2026-02-07T12:00:00Z"
}
```

#### POST `/v1/intents/{id}/access-requests/{requestId}/approve`

Approve an access request. Requires `admin` permission. Creates an ACL entry and a DecisionRecord.

**Request body:**

```json
{
  "decided_by": "admin-user-1",
  "permission": "write",
  "expires_at": "2026-02-08T00:00:00Z",
  "reason": "Approved for research phase"
}
```

The `permission` field in the approval MAY differ from the requested permission (e.g., downgrade from `write` to `read`).

## Error Responses

| Status | Condition |
|--------|-----------|
| `403 Forbidden` | Principal lacks required permission. Response body includes `required_permission` and a link to the access-request endpoint. |
| `404 Not Found` | Intent does not exist, OR principal has no `read` permission and the server chooses to hide the intent's existence. |
| `409 Conflict` | ACL entry already exists for this principal (use PUT to update). |
| `410 Gone` | Access request has already been resolved. |

### 403 Response Format

When a principal is denied access, the response SHOULD include enough information to request access:

```json
{
  "error": "forbidden",
  "message": "You do not have write access to this intent",
  "required_permission": "write",
  "current_permission": "read",
  "access_request_url": "/api/v1/intents/{id}/access-requests"
}
```

## Event Types

This RFC introduces the following event types appended to the intent's event log:

| Event Type | Description |
|-----------|-------------|
| `access_granted` | A principal was granted access |
| `access_revoked` | A principal's access was revoked |
| `access_expired` | A time-limited grant expired |
| `access_requested` | A principal requested access |
| `access_request_approved` | An access request was approved |
| `access_request_denied` | An access request was denied |

All events include the `actor` field identifying who performed the action, maintaining the protocol's append-only audit trail.

## YAML Workflow Integration

Workflow YAML files specify access control per phase using the unified `permissions` field, which supports shorthand forms and a full object form:

```yaml
openintent: "1.0"

info:
  name: "Confidential Review"

workflow:
  extraction:
    title: "Extract Data"
    assign: ocr-agent
    permissions:
      policy: restricted
      allow:
        - agent: "ocr-agent"
          level: write
        - agent: "legal-team"
          level: read

  review:
    title: "Legal Review"
    assign: legal-reviewer
    depends_on: [extraction]
    permissions:
      policy: private
      allow:
        - agent: "legal-reviewer"
          level: write
        - agent: "compliance-officer"
          level: admin
      context: [dependencies, acl, delegated_by]
```

Shorthand forms are also supported:

```yaml
  public_phase:
    permissions: open                      # Anyone can access

  private_phase:
    permissions: private                   # Only the assigned agent

  team_phase:
    permissions: [analyst, auditor]        # Only these agents
```

When the workflow engine creates intents for each phase, it sets the ACL accordingly and grants `admin` to the workflow orchestrator. Each assigned agent receives an `IntentContext` with the dependency results from prior phases automatically populated.

**Backward compatibility:** Legacy `access`, `delegation`, and `context` fields at the phase level are still parsed and auto-converted to the unified `permissions` format.

## Security Considerations

1. **Access request endpoint**: The access-request endpoint (`POST /v1/intents/{id}/access-requests`) MUST be accessible without intent-level permissions. Servers SHOULD rate-limit this endpoint to prevent enumeration attacks.

2. **Intent existence leakage**: When a principal has no access to a closed intent, servers MAY return `404 Not Found` instead of `403 Forbidden` to avoid revealing the intent's existence.

3. **Cascading revocation**: When revoking access, servers MUST also revoke any active leases (RFC-0003) held by that principal, to prevent continued modification via an existing lease.

4. **Context filtering**: The `IntentContext` MUST be filtered according to the permission-level table defined above. Servers MUST NOT leak information to lower-permission principals through the context object.

5. **Group resolution**: When using `principal_type: group`, the server is responsible for resolving group membership. Group membership resolution is implementation-specific and outside the scope of this RFC.

6. **Token/key mapping**: How API keys or OAuth tokens map to principal IDs is implementation-specific. The protocol operates on principal IDs, not raw credentials.

## Backward Compatibility

- Intents without an ACL continue to work as before (server default, typically open access).
- Existing endpoints do not change behavior for intents without ACLs.
- The new ACL and access-request endpoints are additive.
- Servers that do not implement RFC-0011 simply ignore ACL-related fields and continue to allow all authenticated access.
- `intent.ctx` is **always populated**, even for intents without ACLs. In that case, `intent.ctx.my_permission` defaults to `"admin"` (open access), and all context fields are fully visible. This means agents can always rely on `intent.ctx` being present — no feature-detection required.

## Example: Full Multi-Agent Access-Aware Coordination

This example demonstrates the complete flow: an orchestrator creates a confidential research intent, a research agent is auto-approved via policy, receives full context, discovers high-risk content, and delegates to a legal reviewer.

### Step 1: Orchestrator Creates a Confidential Intent

```bash
# Create an intent with a closed ACL
curl -X POST http://localhost:8000/api/v1/intents \
  -H "Content-Type: application/json" \
  -H "X-API-Key: orchestrator-key" \
  -d '{
    "title": "Confidential Research: Market Analysis Q3",
    "created_by": "orchestrator-agent",
    "state": {
      "query": "Analyze competitor patent filings for Q3 2026",
      "classification": "confidential",
      "deadline": "2026-02-14T00:00:00Z"
    },
    "acl": {
      "default_policy": "closed",
      "entries": [
        {
          "principal_id": "orchestrator-agent",
          "principal_type": "agent",
          "permission": "admin"
        }
      ]
    }
  }'
```

### Step 2: Research Agent Requests Access (Auto-Approved via Policy)

```bash
# Agent requests access (allowed even without intent access)
curl -X POST http://localhost:8000/api/v1/intents/{id}/access-requests \
  -H "Content-Type: application/json" \
  -H "X-API-Key: research-agent-key" \
  -d '{
    "principal_id": "research-bot",
    "principal_type": "agent",
    "requested_permission": "write",
    "reason": "Assigned to research phase by coordinator"
  }'

# The orchestrator's @on_access_requested handler auto-approves this.
# The response includes the created ACL entry:
# {
#   "id": "request-uuid",
#   "status": "approved",
#   "permission": "write",
#   "decided_by": "orchestrator-agent",
#   "reason": "Auto-approved: research agent for research intent"
# }
```

### Step 3: Research Agent Receives Full Context

```bash
# Research agent accesses the intent — context is included in response
curl http://localhost:8000/api/v1/intents/{id}?include=context \
  -H "X-API-Key: research-agent-key"

# Response includes intent.ctx:
# {
#   "intent": { "id": "...", "title": "Confidential Research: Market Analysis Q3", ... },
#   "context": {
#     "my_permission": "write",
#     "parent": null,
#     "dependencies": {},
#     "events": [...],
#     "acl": { "entries": [{ "principal_id": "research-bot", "permission": "write" }] },
#     "peers": [
#       { "agent_id": "orchestrator-agent", "permission": "admin" }
#     ],
#     "attachments": [],
#     "delegated_by": null
#   }
# }
```

### Step 4: Research Agent Delegates to Legal Reviewer

```bash
# Research agent finds high-risk content and delegates to legal
curl -X POST http://localhost:8000/api/v1/intents/{id}/delegate \
  -H "Content-Type: application/json" \
  -H "X-API-Key: research-agent-key" \
  -d '{
    "agent_id": "legal-reviewer",
    "permission": "write",
    "payload": {
      "flagged_content": ["Patent filing #12345 overlaps with our IP"],
      "risk_category": "intellectual-property",
      "urgency": "high"
    }
  }'

# This creates an ACL entry for legal-reviewer and sends them an assignment
# with intent.ctx.delegated_by populated.
```

### Step 5: Legal Reviewer Receives Delegation Context

```bash
# Legal reviewer accesses the intent — delegation context is included
curl http://localhost:8000/api/v1/intents/{id}?include=context \
  -H "X-API-Key: legal-reviewer-key"

# Response includes delegation info in context:
# {
#   "context": {
#     "my_permission": "write",
#     "delegated_by": {
#       "agent_id": "research-bot",
#       "payload": {
#         "flagged_content": ["Patent filing #12345 overlaps with our IP"],
#         "risk_category": "intellectual-property",
#         "urgency": "high"
#       }
#     },
#     "peers": [
#       { "agent_id": "orchestrator-agent", "permission": "admin" },
#       { "agent_id": "research-bot", "permission": "write" }
#     ],
#     ...
#   }
# }
```

### Step 6: Audit Trail

```bash
# Check the complete audit trail
curl http://localhost:8000/api/v1/intents/{id}/events \
  -H "X-API-Key: orchestrator-key"

# Events include:
# - access_requested (research-bot)
# - access_request_approved (orchestrator-agent auto-approved)
# - access_granted (research-bot, write)
# - state_patched (research-bot added findings)
# - access_granted (legal-reviewer, write, delegated by research-bot)
# - state_patched (legal-reviewer added legal assessment)
```

### Python SDK: All Three Agents

```python
from openintent import Agent, Client, on_access_requested, on_assignment

# ──────────────────────────────────────────────────────────────
# Agent 1: Orchestrator — creates intents and manages access policy
# ──────────────────────────────────────────────────────────────

@Agent("orchestrator", capabilities=["coordination", "delegation", "policy"])
class Orchestrator:

    @on_access_requested
    async def handle_access_request(self, request, intent):
        """Policy-as-code: auto-approve research agents for research intents."""
        if "research" in request.principal_id and "Research" in intent.title:
            return "approve"
        if "legal" in request.principal_id:
            return "approve"
        return "defer"  # Send to human admin

    @on_assignment
    async def handle(self, intent):
        # Create a confidential research intent
        child = await intent.create_child(
            title="Confidential Research: Market Analysis Q3",
            state={
                "query": "Analyze competitor patent filings for Q3 2026",
                "classification": "confidential",
                "deadline": "2026-02-14T00:00:00Z",
            },
            acl={
                "default_policy": "closed",
                "entries": []  # Orchestrator gets admin implicitly as creator
            }
        )
        print(f"Created confidential intent: {child.id}")


# ──────────────────────────────────────────────────────────────
# Agent 2: Research Bot — does research, delegates when risk found
# ──────────────────────────────────────────────────────────────

@Agent("research-bot", capabilities=["web-search", "summarization", "patent-analysis"])
class ResearchBot:

    @on_assignment
    async def handle(self, intent):
        # Context is already populated — we know everything we need
        print(f"Permission: {intent.ctx.my_permission}")  # "write"
        print(f"Peers: {[p.agent_id for p in intent.ctx.peers]}")

        if intent.ctx.delegated_by:
            print(f"This was delegated by {intent.ctx.delegated_by.agent_id}")

        # Check upstream dependencies (if any)
        for title, dep in intent.ctx.dependencies.items():
            print(f"Upstream '{title}': {dep.status}")

        # Do the research
        query = intent.state.get("query", "")
        findings = await self.analyze_patents(query)

        # Update state with findings
        await intent.patch({"findings": findings.summary, "risk_level": findings.risk})

        # If high-risk content found, delegate to legal
        if findings.risk == "high":
            await intent.delegate(
                agent_id="legal-reviewer",
                payload={
                    "flagged_content": findings.flagged_items,
                    "risk_category": "intellectual-property",
                    "urgency": "high",
                }
            )

    async def analyze_patents(self, query):
        # ... patent analysis logic ...
        pass


# ──────────────────────────────────────────────────────────────
# Agent 3: Legal Reviewer — reviews flagged content
# ──────────────────────────────────────────────────────────────

@Agent("legal-reviewer", capabilities=["legal-review", "compliance-check", "risk-assessment"])
class LegalReviewer:

    @on_assignment
    async def handle(self, intent):
        # We know exactly why we're here
        delegation = intent.ctx.delegated_by
        print(f"Delegated by: {delegation.agent_id}")  # "research-bot"
        print(f"Risk category: {delegation.payload['risk_category']}")
        print(f"Urgency: {delegation.payload['urgency']}")

        # We can see our peers
        for peer in intent.ctx.peers:
            print(f"Peer: {peer.agent_id} ({peer.permission})")
        # Output:
        #   Peer: orchestrator (admin)
        #   Peer: research-bot (write)

        # Review the flagged content
        flagged = delegation.payload["flagged_content"]
        assessment = await self.review(flagged, intent.state)

        # Update state with legal assessment
        await intent.patch({
            "legal_assessment": assessment.summary,
            "legal_risk": assessment.risk_level,
            "recommendations": assessment.recommendations,
        })

        # If critical, escalate to human admin
        if assessment.risk_level == "critical":
            await intent.escalate(
                reason="Critical IP risk requires human legal review",
                data={
                    "assessment": assessment.summary,
                    "affected_patents": assessment.affected_patents,
                }
            )

    async def review(self, flagged_content, state):
        # ... legal review logic ...
        pass
```

## References

- [RFC-0001: OpenIntent Coordination Protocol](./0001-core-protocol.md)
- [RFC-0002: Intent Graphs](./0002-intent-graphs.md)
- [RFC-0003: Arbitration, Governance & Agent Leasing](./0003-governance-leasing.md)
- [RFC-0004: Intent Portfolios](./0004-portfolios.md)
- [RFC-0005: Attachments](./0005-attachments.md)
- [RFC-0006: Real-time Subscriptions](./0006-subscriptions.md)
- [RFC-0009: Cost Tracking](./0009-cost-tracking.md)
- [RFC-0010: Retry Policies](./0010-retry-policies.md)
