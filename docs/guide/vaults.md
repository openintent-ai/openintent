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

## Server-Side Tool Invocation

The built-in server proxies tool invocations, keeping credentials server-side. Agents invoke tools via `POST /api/v1/tools/invoke` — the server resolves the grant, injects credentials from the vault, enforces rate limits, executes the tool through the appropriate adapter, and records the invocation.

```
Agent → POST /api/v1/tools/invoke → Server → Adapter → External API
                                       ↑         ↑
                                  Grant check   Credentials injected
                                  + rate limit  (never exposed to agent)
```

### Execution Adapters

The server uses a pluggable adapter system to execute real external API calls. Three adapters are provided:

| Adapter | Auth Types | Use Case |
|---------|-----------|----------|
| **RestToolAdapter** | API key, Bearer token, Basic Auth | REST APIs (most common) |
| **OAuth2ToolAdapter** | OAuth2 with token refresh | APIs requiring OAuth2 flows |
| **WebhookToolAdapter** | HMAC-signed dispatch | Webhook receivers |

When a credential includes execution config (`base_url`, `endpoints`), the server makes the real external API call. When no execution config is present, the endpoint falls back to a placeholder response for backward compatibility.

### Configuring Credentials for Real Execution

To enable real external API calls, store execution config in the credential's `metadata` field:

```python
# Store a credential with execution config
client.create_credential(
    vault_id="production-apis",
    service="serpapi",
    label="SerpAPI Production Key",
    auth_type="api_key",
    metadata={
        # Execution config
        "base_url": "https://serpapi.com",
        "endpoints": {
            "web_search": {
                "path": "/search",
                "method": "GET",
                "param_mapping": "query"
            }
        },
        "auth": {
            "location": "query",
            "query_param": "api_key"
        },
        # Secret material (extracted at execution time, never logged)
        "api_key": "your-serpapi-key"
    }
)
```

#### REST API Credential (Bearer Token)

```python
client.create_credential(
    vault_id="ai-services",
    service="openai",
    label="OpenAI GPT-4",
    auth_type="bearer_token",
    metadata={
        "base_url": "https://api.openai.com",
        "endpoints": {
            "chat": {
                "path": "/v1/chat/completions",
                "method": "POST",
                "param_mapping": "body"
            }
        },
        "auth": {
            "location": "header",
            "header_prefix": "Bearer"
        },
        "api_key": "sk-..."
    }
)
```

#### OAuth2 Credential (Auto Token Refresh)

```python
client.create_credential(
    vault_id="saas-integrations",
    service="salesforce",
    label="Salesforce CRM",
    auth_type="oauth2_token",
    metadata={
        "base_url": "https://yourinstance.salesforce.com",
        "endpoints": {
            "query": {
                "path": "/services/data/v58.0/query",
                "method": "GET",
                "param_mapping": "query"
            }
        },
        "token_url": "https://login.salesforce.com/services/oauth2/token",
        "token_grant_type": "refresh_token",
        # Secrets
        "access_token": "eyJ...",
        "refresh_token": "dGhp...",
        "client_id": "your-client-id",
        "client_secret": "your-client-secret"
    }
)
```

#### Webhook Credential (HMAC-Signed)

```python
client.create_credential(
    vault_id="integrations",
    service="slack-notify",
    label="Slack Webhook",
    auth_type="webhook",
    metadata={
        "base_url": "https://hooks.slack.com/services/T.../B.../xxx",
        "signing_secret": "whsec_..."
    }
)
```

### Security Controls

The execution layer enforces strict security boundaries:

| Control | Behavior |
|---------|----------|
| **URL Validation** | Blocks private IPs (`10.x`, `192.168.x`, `127.0.0.1`), cloud metadata endpoints (`169.254.169.254`), and non-HTTP schemes |
| **Timeout Bounds** | All calls clamped to 1–120 seconds (default 30s) |
| **Response Size** | Responses capped at 1 MB |
| **Secret Sanitization** | All results and errors are scrubbed — keys, tokens, and passwords are replaced with `[REDACTED]` before storage or return |
| **Request Fingerprinting** | SHA-256 fingerprint of each outbound request stored in the invocation audit trail for correlation |
| **No Redirects** | HTTP redirects are disabled to prevent SSRF via redirect chains |
| **Host Allowlist** | Optional per-grant `allowed_hosts` constraint restricts which domains the adapter can call |

### 3-Tier Grant Resolution

When an agent invokes a tool, the server finds the matching grant using three tiers:

1. **`grant.scopes`** — grant's scopes list contains the tool name
2. **`grant.context["tools"]`** — grant's context has a `tools` array containing the tool name
3. **`credential.service`** — the linked credential's service field matches the tool name

This resolves the common mismatch where tool names (e.g. `"web_search"`) differ from credential service names (e.g. `"serpapi"`).

### Adapter Resolution

The server resolves the adapter for each invocation:

1. **Explicit** — `metadata.adapter` key selects a specific adapter by name
2. **Auth-type** — If `metadata.base_url` is present, the credential's `auth_type` selects the adapter
3. **Fallback** — If no execution config exists, returns a placeholder response (backward compatible)

### Custom Adapters

Register custom adapters for services with non-standard protocols:

```python
from openintent.server.tool_adapters import ToolExecutionAdapter, ToolExecutionResult, register_adapter

class GraphQLAdapter(ToolExecutionAdapter):
    async def _do_execute(self, tool_name, parameters, credential_metadata, credential_secret, grant_constraints=None):
        # Custom execution logic
        return ToolExecutionResult(status="success", result={"data": ...})

register_adapter("graphql", GraphQLAdapter())
```

Then set `"adapter": "graphql"` in the credential metadata.

### Client API

```python
# Synchronous
result = client.invoke_tool(
    tool_name="web_search",
    agent_id="researcher",
    parameters={"query": "OpenIntent protocol"}
)

# Asynchronous
result = await async_client.invoke_tool(
    tool_name="web_search",
    agent_id="researcher",
    parameters={"query": "OpenIntent protocol"}
)
```

### Agent Proxy

Agents using string tool names in `tools=` automatically invoke via the server:

```python
@Agent("researcher", tools=["web_search"])
class Researcher:
    @on_assignment
    async def handle(self, intent):
        result = await self.tools.invoke("web_search", {"query": intent.title})
        return {"results": result}
```

### REST Endpoint

```bash
curl -X POST http://localhost:8000/api/v1/tools/invoke \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-user-key" \
  -d '{
    "tool_name": "web_search",
    "agent_id": "researcher",
    "parameters": {"query": "OpenIntent protocol"}
  }'
```

Response (with real execution):

```json
{
  "invocation_id": "inv-abc123",
  "tool_name": "web_search",
  "status": "success",
  "result": {"organic_results": [{"title": "OpenIntent Protocol", "link": "..."}]},
  "duration_ms": 342
}
```

Error responses map to standard HTTP codes:

| HTTP Status | Meaning |
|-------------|---------|
| `403` | Grant not found, expired, or security validation failed |
| `429` | Rate limit exceeded |
| `502` | Upstream service returned a 5xx error |
| `504` | Upstream service timed out |

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

## Integrating OAuth2 Services

The SDK handles OAuth2 token management (refresh, injection, sanitization) but does **not** implement the initial authorization code flow. That flow involves browser redirects and user consent screens, which belong in your application or platform layer.

Here's the recommended integration pattern:

### Step 1: Your Platform Handles the Consent Flow

Your application (dashboard, admin panel, CLI tool) runs the standard OAuth2 authorization code flow:

```
1. User clicks "Connect Salesforce" in your app
2. Your app redirects to: https://login.salesforce.com/services/oauth2/authorize
   ?client_id=YOUR_CLIENT_ID
   &redirect_uri=https://yourapp.com/oauth/callback
   &response_type=code
   &scope=api refresh_token
3. User logs in and grants consent
4. Salesforce redirects back to your app with ?code=AUTH_CODE
5. Your app exchanges the code for tokens:
   POST https://login.salesforce.com/services/oauth2/token
   grant_type=authorization_code&code=AUTH_CODE&client_id=...&client_secret=...
6. Your app receives: { access_token, refresh_token, instance_url, ... }
```

### Step 2: Store Tokens in the Credential Vault

Once your platform has the tokens, store them in the vault with the execution config:

```python
from openintent import OpenIntentClient

client = OpenIntentClient(base_url="http://localhost:8000", agent_id="admin")

client.create_credential(
    vault_id="saas-integrations",
    service="salesforce",
    label="Salesforce CRM",
    auth_type="oauth2_token",
    metadata={
        # Execution config — tells the adapter how to call the API
        "base_url": "https://yourinstance.salesforce.com",
        "endpoints": {
            "query": {
                "path": "/services/data/v58.0/query",
                "method": "GET",
                "param_mapping": "query"
            },
            "create_record": {
                "path": "/services/data/v58.0/sobjects/{sobject}",
                "method": "POST",
                "param_mapping": "body"
            }
        },
        # Token refresh config — the adapter uses these to refresh automatically
        "token_url": "https://login.salesforce.com/services/oauth2/token",
        "token_grant_type": "refresh_token",

        # Secrets — extracted at execution time, never logged or returned
        "access_token": "eyJ...",        # from the OAuth2 exchange
        "refresh_token": "dGhp...",      # from the OAuth2 exchange
        "client_id": "your-client-id",
        "client_secret": "your-client-secret"
    }
)
```

### Step 3: Agents Use the Service

From this point, agents interact with the service through the protocol. They never see tokens:

```python
@Agent("crm-agent", tools=["salesforce"])
class CRMAgent:
    @on_assignment
    async def handle(self, intent):
        # The server resolves the grant, injects the access token,
        # and calls the Salesforce API. If the token has expired,
        # the OAuth2ToolAdapter refreshes it automatically.
        accounts = await self.tools.invoke(
            "query",
            {"q": "SELECT Id, Name FROM Account LIMIT 10"}
        )
        return {"accounts": accounts}
```

### Required Metadata Fields for OAuth2

| Field | Required | Description |
|-------|----------|-------------|
| `base_url` | Yes | API base URL (e.g., `https://yourinstance.salesforce.com`) |
| `endpoints` | Yes | Map of tool names to path/method/param_mapping |
| `token_url` | Yes | Token endpoint for refresh (e.g., `https://login.salesforce.com/services/oauth2/token`) |
| `token_grant_type` | Yes | Usually `"refresh_token"` |
| `access_token` | Yes | Current access token (from your OAuth2 exchange) |
| `refresh_token` | Yes | Refresh token (from your OAuth2 exchange) |
| `client_id` | Yes | OAuth2 client ID |
| `client_secret` | Yes | OAuth2 client secret |

### Token Lifecycle

Once tokens are stored, the `OAuth2ToolAdapter` manages the lifecycle automatically:

```
Agent invokes tool
  → Adapter calls API with stored access_token
  → If 401 Unauthorized:
      → Adapter POSTs to token_url with refresh_token
      → Receives new access_token
      → Retries the original request with the new token
      → Stores the new access_token in credential metadata
  → Returns result (secrets sanitized)
```

### Common OAuth2 Services

Here are the key metadata fields for popular services:

**Google APIs (Gmail, Drive, Calendar)**
```python
metadata={
    "base_url": "https://www.googleapis.com",
    "token_url": "https://oauth2.googleapis.com/token",
    "token_grant_type": "refresh_token",
    # ... endpoints, tokens, client_id, client_secret
}
```

**Microsoft Graph (Office 365, OneDrive, Teams)**
```python
metadata={
    "base_url": "https://graph.microsoft.com",
    "token_url": "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
    "token_grant_type": "refresh_token",
    # ... endpoints, tokens, client_id, client_secret
}
```

**HubSpot CRM**
```python
metadata={
    "base_url": "https://api.hubapi.com",
    "token_url": "https://api.hubapi.com/oauth/v1/token",
    "token_grant_type": "refresh_token",
    # ... endpoints, tokens, client_id, client_secret
}
```

**GitHub (with fine-grained tokens, use bearer_token instead)**
```python
metadata={
    "base_url": "https://api.github.com",
    "auth": {"location": "header", "header_prefix": "Bearer"},
    "api_key": "ghp_..."  # Fine-grained PAT — no OAuth2 refresh needed
}
```

!!! info "Why not build the consent flow into the SDK?"
    The authorization code flow requires browser redirects, session management, CSRF protection, and UI — concerns that belong in your application layer, not a protocol library. The SDK's boundary is: "Give me tokens, I'll manage them." This keeps the protocol layer focused and deployment-agnostic.

---

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
