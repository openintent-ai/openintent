# Credential Vaults & Tool Scoping

Securely manage API keys, grant tools to agents with scoped permissions, and maintain audit trails.

## Declarative Vault with @Agent

```python
from openintent.agents import Agent, on_assignment, Vault

@Vault
class MyVault:
    secrets = {
        "openai_key": {"env": "OPENAI_API_KEY"},
        "github_token": {"env": "GITHUB_TOKEN"},
    }
    auto_rotate = True
    rotation_interval_hours = 24

@Agent("secure-agent", tools=["web_search", "code_review"])
class SecureAgent:

    @on_assignment
    async def handle(self, intent):
        # Tools are automatically scoped — agent can only use granted tools
        results = await self.tools.invoke("web_search", query=intent.title)
        return {"results": results}
```

## Imperative Vault Management

```python
from openintent import OpenIntentClient

client = OpenIntentClient(
    base_url="http://localhost:8000",
    agent_id="vault-admin"
)

# Store a credential
client.vault_store(
    key="openai_api_key",
    value="sk-...",
    metadata={"provider": "openai", "tier": "production"}
)

# Grant tool access to an agent
client.grant_tool(
    agent_id="researcher",
    tool_name="web_search",
    scopes=["read"],
    expires_in_seconds=3600
)

# Grant with delegation rights
client.grant_tool(
    agent_id="coordinator",
    tool_name="code_review",
    scopes=["read", "execute"],
    can_delegate=True,
    max_delegation_depth=2
)

# Coordinator delegates to a sub-agent
client.delegate_grant(
    from_agent="coordinator",
    to_agent="dev-agent",
    tool_name="code_review",
    scopes=["read"]  # Can narrow scopes, never widen
)
```

## Tool Registry and Invocation

```python
# Register a custom tool
client.register_tool(
    name="sentiment_analysis",
    description="Analyze sentiment of text",
    parameters={
        "text": {"type": "string", "required": True},
        "language": {"type": "string", "default": "en"}
    },
    endpoint="https://api.example.com/sentiment"
)

# Invoke tool through the proxy (audit trail is automatic)
result = client.tools.invoke(
    "sentiment_analysis",
    text="This product is amazing!",
    language="en"
)

# Audit trail
audit = client.list_tool_invocations(agent_id="researcher")
for entry in audit:
    print(f"[{entry.timestamp}] {entry.tool_name}: {entry.status}")
```

## Server-Side Tool Invocation (v0.9.0)

Invoke tools through the server proxy — credentials stay server-side:

```python
from openintent import OpenIntentClient

client = OpenIntentClient(
    base_url="http://localhost:8000",
    agent_id="researcher"
)

# Invoke a tool via server proxy (grant is validated automatically)
result = client.invoke_tool(
    tool_name="web_search",
    agent_id="researcher",
    parameters={"query": "OpenIntent protocol documentation"}
)
print(f"Results: {result}")

# Async version
from openintent import AsyncOpenIntentClient

async_client = AsyncOpenIntentClient(
    base_url="http://localhost:8000",
    agent_id="researcher"
)
result = await async_client.invoke_tool(
    tool_name="web_search",
    agent_id="researcher",
    parameters={"query": "OpenIntent protocol documentation"}
)
```

### Via REST API

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

### Via Agent Self-Access

```python
from openintent.agents import Agent, on_assignment

@Agent("researcher", tools=["web_search", "summarize"])
class Researcher:

    @on_assignment
    async def handle(self, intent):
        # String tool names invoke via server proxy
        results = await self.tools.invoke(
            "web_search",
            {"query": intent.description}
        )

        summary = await self.tools.invoke(
            "summarize",
            {"text": str(results)}
        )

        return {"results": results, "summary": summary}
```

## Real External API Execution

When credentials include execution config, the server makes real API calls instead of returning placeholder responses.

### REST API with API Key (SerpAPI)

```python
from openintent import OpenIntentClient

client = OpenIntentClient(base_url="http://localhost:8000", agent_id="admin")

# 1. Create a vault
vault = client.create_vault(owner_id="admin", name="Search APIs")

# 2. Store credential with execution config
cred = client.create_credential(
    vault_id=vault["id"],
    service="serpapi",
    label="SerpAPI Production",
    auth_type="api_key",
    metadata={
        "base_url": "https://serpapi.com",
        "endpoints": {
            "web_search": {
                "path": "/search",
                "method": "GET",
                "param_mapping": "query"
            }
        },
        "auth": {"location": "query", "query_param": "api_key"},
        "api_key": "your-serpapi-key"
    }
)

# 3. Grant the tool to an agent
client.create_tool_grant(
    credential_id=cred["id"],
    agent_id="researcher",
    granted_by="admin",
    scopes=["web_search"]
)

# 4. Agent invokes — server calls SerpAPI directly
result = client.invoke_tool(
    tool_name="web_search",
    agent_id="researcher",
    parameters={"query": "OpenIntent protocol", "num": 5}
)
# result contains real search results from SerpAPI
```

### OAuth2 API (Salesforce)

```python
cred = client.create_credential(
    vault_id=vault["id"],
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
        "access_token": "eyJ...",
        "refresh_token": "dGhp...",
        "client_id": "your-client-id",
        "client_secret": "your-client-secret"
    }
)

# If the access token expires, the adapter automatically refreshes it
result = client.invoke_tool(
    tool_name="query",
    agent_id="researcher",
    parameters={"q": "SELECT Id, Name FROM Account LIMIT 10"}
)
```

### Webhook Dispatch (Slack)

```python
cred = client.create_credential(
    vault_id=vault["id"],
    service="slack-notify",
    label="Slack Alerts",
    auth_type="webhook",
    metadata={
        "base_url": "https://hooks.slack.com/services/T.../B.../xxx",
        "signing_secret": "whsec_..."
    }
)

# Dispatch sends HMAC-signed POST to the webhook URL
result = client.invoke_tool(
    tool_name="slack-notify",
    agent_id="notifier",
    parameters={"text": "Deployment complete", "channel": "#ops"}
)
```

### Security: What Gets Blocked

```python
# These URLs are automatically blocked by the execution layer:

# Private IPs
# "http://192.168.1.1/admin"     → SecurityError: private IP blocked
# "http://10.0.0.1/internal"     → SecurityError: private IP blocked

# Cloud metadata endpoints
# "http://169.254.169.254/latest" → SecurityError: metadata endpoint blocked

# Non-HTTP schemes
# "ftp://files.example.com"      → SecurityError: non-HTTP scheme blocked
```

## Revoking Grants

```python
# Revoke a specific grant
client.revoke_grant(agent_id="researcher", tool_name="web_search")

# Cascading revocation — revoking a delegator's grant
# also revokes all downstream delegations
client.revoke_grant(agent_id="coordinator", tool_name="code_review")
# This also revokes dev-agent's delegated grant
```

## YAML Workflow with Tools and Vaults

```yaml
openintent: "1.0"
info:
  name: "Secure Research Pipeline"

tools:
  - name: web_search
    description: "Search the web"
    endpoint: "https://api.search.example.com"
  - name: summarize
    description: "Summarize text with LLM"
    endpoint: "internal://llm/summarize"

workflow:
  research:
    title: "Gather Information"
    assign: researcher
    tools: [web_search, summarize]

  analyze:
    title: "Analyze Results"
    assign: analyst
    depends_on: [research]
    tools: [summarize]

  report:
    title: "Generate Report"
    assign: reporter
    depends_on: [analyze]
    tools: []  # No tool access needed
```

```python
from openintent.workflow import load_workflow

wf = load_workflow("secure_research.yaml")
wf.run()
```
