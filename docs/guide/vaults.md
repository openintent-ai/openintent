---
title: Credential Vaults & Tools
---

# Credential Vaults & Tools

Credential Vaults provide encrypted storage for secrets and API keys with scoped tool grants. Agents receive only the credentials they need, with full audit trails and cascading revocation. Defined in [RFC-0014](../rfcs/0014-credential-vaults-tool-scoping.md).

## Vaults

### Storing Credentials

```python
# Store a credential in a vault
client.vault_store(
    vault_id="production-apis",
    key="openai_api_key",
    value="sk-...",
    metadata={"provider": "openai", "tier": "production"}
)
```

### Retrieving Credentials

```python
# Agents with grants can retrieve scoped credentials
cred = client.get_vault(vault_id="production-apis", key="openai_api_key")
print(f"Key: {cred.key}, Provider: {cred.metadata['provider']}")
```

### Declarative Vaults

Use the `@Vault` decorator for declarative vault configuration:

```python
from openintent.agents import Vault

@Vault("research-tools",
    rotate_keys=True  # Automatic key rotation
)
class ResearchVault:
    web_search = {"provider": "serp", "scopes": ["search"]}
    email = {"provider": "sendgrid", "scopes": ["send"]}
    database = {"provider": "postgres", "scopes": ["read"]}
```

---

## Tool Grants

Tool grants control which agents can use which tools. Grants are scoped and can be delegated with cascading revocation.

### Granting Tool Access

```python
# Grant an agent access to a specific tool
client.tools.grant(
    agent_id="researcher",
    tool="web_search",
    scopes=["search"],
    vault_id="research-tools"
)
```

### Listing Grants

```python
# List grants for an agent
grants = client.tools.list_grants(agent_id="researcher")

for g in grants:
    print(f"Tool: {g.tool}, Scopes: {g.scopes}")
```

### Grant Delegation

Grants can be delegated from one agent to another, with automatic cascading revocation:

```python
# Coordinator delegates tool access to a sub-agent
client.tools.delegate_grant(
    from_agent="coordinator",
    to_agent="worker",
    tool="web_search",
    scopes=["search"],
    max_depth=2  # Can be re-delegated once more
)

# Revoking the coordinator's grant also revokes the worker's
client.tools.revoke_grant(agent_id="coordinator", tool="web_search")
# → worker's grant is also revoked (cascading)
```

---

## Tool Invocation

### Direct Invocation

```python
# Invoke a tool (grant is checked automatically)
result = client.tools.invoke(
    tool="web_search",
    input={"query": "OpenIntent protocol documentation"},
    agent_id="researcher"
)

print(f"Results: {result.output}")
```

### Using Tools in Agents

The `@Agent` decorator provides a `self.tools` proxy:

```python
from openintent.agents import Agent, on_assignment

@Agent("smart-researcher",
    tools=["web_search", "sql_query"],  # Declare required tools
)
class SmartResearcher:

    @on_assignment
    async def handle(self, intent):
        # Tools are available via self.tools
        search_results = await self.tools.invoke(
            "web_search",
            {"query": intent.description}
        )

        db_results = await self.tools.invoke(
            "sql_query",
            {"sql": "SELECT * FROM reports WHERE topic = ?",
             "params": [intent.title]}
        )

        return {
            "web_results": search_results,
            "db_results": db_results
        }
```

### Tool Registry

The server maintains a registry of available tools:

```python
# List available tools
tools = client.tools.list()

for tool in tools:
    print(f"{tool.name}: {tool.description}")
    print(f"  Scopes: {tool.scopes}")
```

---

## Server-Side Tool Proxy

The built-in server can proxy tool invocations, keeping credentials server-side:

```
Agent → Server → Tool Provider
         ↑
    Credentials from vault
    (never exposed to agent)
```

This means agents never see raw API keys — the server handles authentication transparently.

## Tools in YAML Workflows

```yaml
tools:
  web_search:
    vault: research-tools
    scopes: [search]
    rate_limit: 100/hour

  email:
    vault: research-tools
    scopes: [send]
    require_approval: true

workflow:
  research:
    assign: researcher
    tools: [web_search]

  notify:
    assign: notifier
    tools: [email]
    depends_on: [research]
```

!!! tip "Direct grants"
    Standalone agents (not under a coordinator) can receive tool grants directly via `client.tools.grant()`. No coordinator required.

## Audit Trail

Every tool invocation is logged for compliance:

```python
# Query tool invocation audit log
audit = client.tools.audit_log(tool="web_search", limit=50)

for entry in audit:
    print(f"Agent: {entry.agent_id}, Time: {entry.timestamp}")
    print(f"  Input: {entry.input}")
    print(f"  Output: {entry.output}")
```

## Next Steps

- [Access Control](access-control.md) — Permission-based coordination
- [Agent Abstractions](agents.md) — `@Vault` decorator reference
- [Coordinator Patterns](coordinators.md) — Tool delegation in multi-agent systems
