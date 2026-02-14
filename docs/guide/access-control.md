---
title: Access Control
---

# Access Control

Access control governs which agents can read, write, or delegate on intents and namespaces. The unified permissions model supports shorthand and full-object forms for flexible coordination. Defined in [RFC-0011](../rfcs/0011-access-control.md).

## Permission Levels

| Level | Description |
|-------|-------------|
| `read` | Can view intent state and events |
| `write` | Can patch state, log events |
| `admin` | Full control including governance actions |
| `delegate` | Can assign the intent to other agents |

## Granting Access

```python
# Grant read access to an agent
client.grant_access(
    intent_id=intent.id,
    agent_id="analyst",
    permission="read"
)

# Grant write access
client.grant_access(
    intent_id=intent.id,
    agent_id="worker",
    permission="write"
)
```

## Checking Access

```python
# Get the access control list
acl = client.get_acl(intent.id)

for entry in acl:
    print(f"Agent: {entry.agent_id}, Permission: {entry.permission}")
```

## Revoking Access

```python
client.revoke_access(
    intent_id=intent.id,
    agent_id="analyst"
)
```

## Requesting Access

Agents can request access to intents they don't currently have permission for:

```python
# Agent requests access
request = client.request_access(
    intent_id=intent.id,
    requested_permission="write",
    reason="Need to update analysis results"
)
```

### Handling Access Requests in Agents

```python
from openintent.agents import Agent, on_access_requested

@Agent("gatekeeper")
class GatekeeperAgent:

    @on_access_requested
    async def handle_request(self, intent, request):
        """Evaluate and approve/deny access requests."""
        if request.agent_id in self.trusted_agents:
            return "approve"
        elif request.requested_permission == "read":
            return "approve"  # Read access is generally safe
        else:
            return "deny"
```

## Unified Permissions in YAML

RFC-0011 v1.0 provides a unified `permissions` field with shorthand and full forms:

=== "Shorthand — Open"

    ```yaml
    workflow:
      research:
        assign: researcher
        permissions: open  # All agents can access
    ```

=== "Shorthand — Private"

    ```yaml
    workflow:
      sensitive_analysis:
        assign: analyst
        permissions: private  # Only assigned agent
    ```

=== "Shorthand — Agent List"

    ```yaml
    workflow:
      review:
        assign: reviewer
        permissions: [reviewer, lead, auditor]
    ```

=== "Full Object"

    ```yaml
    workflow:
      research:
        assign: researcher
        permissions:
          policy: scoped
          default: read
          allow:
            - agent: analyst
              grants: [read, write]
            - agent: auditor
              grants: [read]
          delegate:
            allow: true
            max_depth: 2
          context:
            inject: [project_name, deadline]
    ```

## Governance-Level Access Review

```yaml
governance:
  access_review:
    on_request: approve  # approve | deny | defer
    approvers: [security-team, admin]
    timeout_hours: 4
```

## Agent-Level Defaults

```yaml
agents:
  researcher:
    default_permission: read
    approval_required: false

  data_handler:
    default_permission: write
    approval_required: true  # Requires governance approval
```

!!! tip "Legacy compatibility"
    The older `access`, `delegation`, and `context` YAML fields are still parsed and automatically converted to the unified `permissions` format.

## Next Steps

- [Governance & Arbitration](governance.md) — Approval workflows and escalation
- [Credential Vaults & Tools](vaults.md) — Scoped tool access and credential management
- [YAML Workflows](workflows.md) — Declarative workflow permissions
