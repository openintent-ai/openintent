# RFC-0011: Access-Aware Coordination v1.0

**Status:** Proposed  
**Created:** 2026-02-01  
**Updated:** 2026-02-07  
**Authors:** OpenIntent Contributors  
**Requires:** [RFC-0001 (Intents)](./0001-intent-objects.md), [RFC-0003 (Leasing)](./0003-agent-leasing.md)

---

## Abstract

This RFC adds a unified `permissions` model to OpenIntent. One field on each workflow phase controls who can access it, what context agents receive, and whether work can be delegated. It replaces the previous three separate fields (`access`, `delegation`, `context`) with a single block that supports both shorthand strings for common cases and a full object form for fine-grained control.

## Quick Start

Most workflows only need a one-liner. The `permissions` field accepts a string, a list of agent IDs, or a full object.

```yaml
workflow:
  # No restrictions (default if omitted)
  research:
    assign: researcher
    permissions: open

  # Only the assigned agent can access
  extraction:
    assign: ocr-agent
    permissions: private

  # Specific agents get write, others get read
  analysis:
    assign: analyst
    permissions: [analyst, auditor]
```

In Python, permissions are typed with enums and dataclasses:

```python
from openintent.workflow import AccessPolicy
from openintent import PermissionsConfig, PermissionLevel

# Shorthand — parsed from YAML automatically
config = PermissionsConfig.from_yaml("private")
config = PermissionsConfig.from_yaml(["analyst", "auditor"])

# Or construct directly
config = PermissionsConfig(
    policy=AccessPolicy.RESTRICTED,
    default=PermissionLevel.READ,
)
```

## The Permissions Model

### Permission Levels

Three cumulative levels. Each includes all capabilities of the level below it.

| Level | Capabilities |
|-------|-------------|
| `read` | View intent metadata, state, events, attachments, cost summaries. Subscribe to events. |
| `write` | Patch state, emit events, acquire leases, add attachments, record costs. |
| `admin` | Change status, modify permissions, configure retry, create child intents, manage delegation. |

### Access Policies

| Policy | Description |
|--------|-------------|
| `open` | Any agent can access at the default permission level. This is the default. |
| `restricted` | Only agents declared in the workflow (or in the allow list) can access. |
| `private` | Only the assigned agent has access. Others must be explicitly granted via the allow list. |

## Full Permissions Object

When you need fine-grained control, the `permissions` field accepts an object with five optional subkeys:

```yaml
workflow:
  sensitive_analysis:
    title: "Analyze Sensitive Data"
    assign: analyst
    permissions:
      policy: restricted
      default: read
      allow:
        - agent: "analyst"
          level: write
        - agent: "auditor"
          level: read
          expires: "2026-12-31T00:00:00Z"
      delegate:
        to: ["specialist-bot"]
        level: read
      context: [dependencies, peers, acl]
```

### Context Injection

The `context` subkey controls what information the server auto-populates in `intent.ctx` when an agent receives work.

| Field | Description |
|-------|-------------|
| `dependencies` | Outputs from upstream phases (keyed by phase name) |
| `peers` | Sibling intents under the same parent |
| `parent` | Parent intent metadata |
| `events` | Recent event log entries |
| `acl` | Current access control list (admin only) |
| `delegated_by` | Which agent delegated this work |

Set `context: auto` (the default) and the server decides what to inject based on the agent's permission level. Set `context: none` to disable context injection entirely.

## Python SDK

### End-to-End Example

An agent declares capabilities, receives auto-populated context, analyzes data, and delegates or escalates based on results.

```python
@Agent("analyst", capabilities=["compliance", "risk-analysis"])
class AnalystAgent:
    @on_assignment
    async def work(self, intent):
        # Context is auto-populated based on permissions
        extraction = intent.ctx.dependencies.get("extraction", {})
        text = extraction.get("text", "")

        risk = await self.analyze(text)

        if risk > 0.8:
            # Escalate to a human when risk is high
            await intent.escalate(reason="High risk", data={"score": risk})

        if self.needs_specialist(text):
            # Delegate to another agent with scoped access
            await intent.delegate("specialist-bot")

        return {"status": "reviewed", "risk_score": risk}

    @on_access_requested
    async def policy(self, request):
        # Policy-as-code: approve read, defer everything else
        return "approve" if request.level == "read" else "defer"
```

### Scoped Temporary Access

Grant temporary access that is automatically revoked when the block exits, even on exceptions.

```python
async with self.temp_access(intent.id, "helper-agent", "write"):
    await self.client.assign_agent(intent.id, "helper-agent")
    # access is revoked automatically when the block exits
```

## Endpoints

### Permissions Management

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/v1/intents/{id}/acl` | Get the intent's access control list |
| `PUT` | `/v1/intents/{id}/acl` | Replace the intent's ACL |
| `POST` | `/v1/intents/{id}/acl/entries` | Grant access to an agent |
| `DELETE` | `/v1/intents/{id}/acl/entries/{entryId}` | Revoke an agent's access |

### Access Requests

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/v1/intents/{id}/access-requests` | Request access to an intent |
| `GET` | `/v1/intents/{id}/access-requests` | List pending access requests |
| `POST` | `/v1/intents/{id}/access-requests/{reqId}/approve` | Approve a request |
| `POST` | `/v1/intents/{id}/access-requests/{reqId}/deny` | Deny a request |

## Event Types

| Event Type | Description |
|-----------|-------------|
| `access_granted` | An agent was granted access to an intent |
| `access_revoked` | An agent's access was revoked |
| `access_expired` | A time-limited access grant expired |
| `access_requested` | An agent requested access to an intent |
| `access_request_approved` | An access request was approved |
| `access_request_denied` | An access request was denied |

All events include the `actor` field, maintaining the protocol's append-only audit trail.

## Backward Compatibility

Fully backward compatible with existing OpenIntent deployments:

- **No permissions = open access:** Intents without a permissions field work exactly as before.
- **Context is additive:** The `intent.ctx` object is new. Agents that don't use it are unaffected.
- **Legacy fields:** The old `access`, `delegation`, and `context` YAML fields are still parsed and automatically converted to the unified `permissions` format.
- **Decorators are opt-in:** `@on_access_requested` is optional. Without it, access requests flow through the governance pipeline (RFC-0003).
