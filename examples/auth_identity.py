#!/usr/bin/env python3
"""
OpenIntent Auth and Agent Identity Example

This example demonstrates authentication and agent identity management
in the OpenIntent protocol. Key concepts:

1. **API Key Authentication**: Simple bearer-style auth for development
2. **Agent Identity**: Unique agent IDs for tracking and auditing
3. **Agent Registration**: Optional agent metadata for richer coordination
4. **Multi-Tenant Considerations**: Namespace isolation patterns

Security Model:
- API keys authenticate the request
- Agent ID identifies WHO is acting (for audit trail)
- Both are required for proper protocol conformance
- Events and state changes are attributed to agent_id

Run:
    export OPENINTENT_API_URL=http://localhost:5000
    python auth_identity.py
"""

import asyncio
import hashlib
import os
import secrets
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from openintent import (
    AsyncOpenIntentClient,
    EventType,
    IntentStatus,
)


OPENINTENT_API_URL = os.getenv("OPENINTENT_API_URL", "http://localhost:5000")


class AgentRole(Enum):
    """Common agent roles for access control patterns."""
    ORCHESTRATOR = "orchestrator"  # Can create intents, assign agents
    WORKER = "worker"              # Can work on assigned intents
    OBSERVER = "observer"          # Read-only access
    GOVERNOR = "governor"          # Can make decisions, arbitrate


@dataclass
class AgentCredentials:
    """
    Agent credentials bundle.
    
    In production, this would be:
    - Generated during agent registration
    - Stored securely (vault, secrets manager)
    - Rotated periodically
    """
    agent_id: str
    api_key: str
    role: AgentRole
    created_at: datetime
    expires_at: Optional[datetime] = None
    
    @classmethod
    def generate(
        cls,
        agent_id: str,
        role: AgentRole = AgentRole.WORKER,
        ttl_hours: int = 24,
    ) -> "AgentCredentials":
        """Generate new credentials for an agent."""
        return cls(
            agent_id=agent_id,
            api_key=f"oi_{secrets.token_urlsafe(32)}",
            role=role,
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=ttl_hours),
        )
    
    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at
    
    def to_client(self) -> AsyncOpenIntentClient:
        """Create a client configured with these credentials."""
        return AsyncOpenIntentClient(
            base_url=OPENINTENT_API_URL,
            api_key=self.api_key,
            agent_id=self.agent_id,
        )


class AgentRegistry:
    """
    In-memory agent registry for demonstration.
    
    In production, this would be:
    - Backed by database
    - Integrated with identity provider (Auth0, Okta, etc.)
    - Support for API key rotation
    - Rate limiting per agent
    """
    
    def __init__(self):
        self._agents: dict[str, AgentCredentials] = {}
        self._by_key: dict[str, str] = {}  # api_key -> agent_id
    
    def register(
        self,
        agent_id: str,
        role: AgentRole = AgentRole.WORKER,
    ) -> AgentCredentials:
        """Register a new agent and generate credentials."""
        if agent_id in self._agents:
            raise ValueError(f"Agent {agent_id} already registered")
        
        creds = AgentCredentials.generate(agent_id, role)
        self._agents[agent_id] = creds
        self._by_key[creds.api_key] = agent_id
        
        return creds
    
    def authenticate(self, api_key: str) -> Optional[AgentCredentials]:
        """Authenticate an API key and return agent credentials."""
        agent_id = self._by_key.get(api_key)
        if not agent_id:
            return None
        
        creds = self._agents.get(agent_id)
        if not creds or creds.is_expired:
            return None
        
        return creds
    
    def get(self, agent_id: str) -> Optional[AgentCredentials]:
        """Get credentials for an agent."""
        return self._agents.get(agent_id)
    
    def rotate_key(self, agent_id: str) -> AgentCredentials:
        """Rotate API key for an agent."""
        old_creds = self._agents.get(agent_id)
        if not old_creds:
            raise ValueError(f"Agent {agent_id} not found")
        
        # Remove old key mapping
        del self._by_key[old_creds.api_key]
        
        # Generate new key
        new_creds = AgentCredentials(
            agent_id=agent_id,
            api_key=f"oi_{secrets.token_urlsafe(32)}",
            role=old_creds.role,
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=24),
        )
        
        self._agents[agent_id] = new_creds
        self._by_key[new_creds.api_key] = agent_id
        
        return new_creds


class AuthenticatedAgent:
    """
    Agent with authentication and identity management.
    
    Demonstrates proper auth patterns:
    - Credentials are validated before operations
    - Agent ID is consistently used for attribution
    - Role-based access control pattern
    """
    
    def __init__(self, credentials: AgentCredentials):
        self.credentials = credentials
        self.client: AsyncOpenIntentClient = None
    
    @property
    def agent_id(self) -> str:
        return self.credentials.agent_id
    
    @property
    def role(self) -> AgentRole:
        return self.credentials.role
    
    async def connect(self):
        """Connect with credentials."""
        if self.credentials.is_expired:
            raise ValueError("Credentials expired")
        
        self.client = self.credentials.to_client()
    
    async def disconnect(self):
        if self.client:
            await self.client.close()
    
    async def create_intent(self, title: str, description: str = "") -> str:
        """Create intent (orchestrators only in strict mode)."""
        intent = await self.client.create_intent(
            title=title,
            description=description,
            initial_state={
                "created_by": self.agent_id,
                "created_by_role": self.role.value,
            }
        )
        
        # Log creation with identity
        await self.client.log_event(
            intent.id,
            EventType.COMMENT,
            {
                "message": f"Intent created by {self.agent_id}",
                "agent_role": self.role.value,
            }
        )
        
        return intent.id
    
    async def work_on_intent(self, intent_id: str, work_description: str):
        """Perform work and log with identity attribution."""
        intent = await self.client.get_intent(intent_id)
        
        # Update state with worker identity
        await self.client.update_state(
            intent_id,
            intent.version,
            {
                "last_worked_by": self.agent_id,
                "last_work_at": datetime.now().isoformat(),
                "work_description": work_description,
            }
        )
        
        # Log work with full identity context
        await self.client.log_event(
            intent_id,
            EventType.COMMENT,
            {
                "message": work_description,
                "agent_id": self.agent_id,
                "agent_role": self.role.value,
            }
        )


async def demo_basic_auth():
    """Demonstrate basic API key authentication."""
    
    print("=" * 60)
    print("Basic API Key Authentication")
    print("=" * 60)
    
    # Using development keys (predefined in server)
    dev_keys = {
        "dev-user-key": "user",
        "agent-research-key": "research-agent",
        "agent-synth-key": "synthesis-agent",
    }
    
    for api_key, agent_id in dev_keys.items():
        client = AsyncOpenIntentClient(
            base_url=OPENINTENT_API_URL,
            api_key=api_key,
            agent_id=agent_id,
        )
        
        try:
            # Test authentication by making a request
            intents = await client.list_intents(limit=1)
            print(f"[OK] {agent_id}: Authenticated with {api_key[:15]}...")
        except Exception as e:
            print(f"[FAIL] {agent_id}: {e}")
        finally:
            await client.close()


async def demo_agent_registry():
    """Demonstrate agent registration and credential management."""
    
    print("\n" + "=" * 60)
    print("Agent Registry and Credential Management")
    print("=" * 60)
    
    registry = AgentRegistry()
    
    # Register different agent types
    orchestrator = registry.register("orch-001", AgentRole.ORCHESTRATOR)
    worker1 = registry.register("worker-001", AgentRole.WORKER)
    worker2 = registry.register("worker-002", AgentRole.WORKER)
    observer = registry.register("observer-001", AgentRole.OBSERVER)
    
    print(f"\nRegistered agents:")
    print(f"  - {orchestrator.agent_id} ({orchestrator.role.value})")
    print(f"  - {worker1.agent_id} ({worker1.role.value})")
    print(f"  - {worker2.agent_id} ({worker2.role.value})")
    print(f"  - {observer.agent_id} ({observer.role.value})")
    
    # Authenticate by API key
    print(f"\nAuthentication test:")
    auth_result = registry.authenticate(worker1.api_key)
    if auth_result:
        print(f"  API key {worker1.api_key[:20]}... -> {auth_result.agent_id}")
    
    # Key rotation
    print(f"\nKey rotation for {worker1.agent_id}:")
    old_key = worker1.api_key[:20]
    new_creds = registry.rotate_key(worker1.agent_id)
    print(f"  Old key: {old_key}...")
    print(f"  New key: {new_creds.api_key[:20]}...")
    
    # Old key no longer works
    old_auth = registry.authenticate(worker1.api_key)
    new_auth = registry.authenticate(new_creds.api_key)
    print(f"  Old key valid: {old_auth is not None}")
    print(f"  New key valid: {new_auth is not None}")


async def demo_multi_agent_identity():
    """Demonstrate multiple agents with distinct identities."""
    
    print("\n" + "=" * 60)
    print("Multi-Agent Identity Tracking")
    print("=" * 60)
    
    registry = AgentRegistry()
    
    # Register agents with different roles
    orchestrator_creds = registry.register("coordinator", AgentRole.ORCHESTRATOR)
    research_creds = registry.register("research-agent", AgentRole.WORKER)
    synth_creds = registry.register("synthesis-agent", AgentRole.WORKER)
    
    # For demo, we'll use dev keys since our server recognizes them
    # In production, the registered keys would be stored in the server
    
    orchestrator = AuthenticatedAgent(AgentCredentials(
        agent_id="coordinator",
        api_key="dev-user-key",  # Using dev key for demo
        role=AgentRole.ORCHESTRATOR,
        created_at=datetime.now(),
    ))
    
    research = AuthenticatedAgent(AgentCredentials(
        agent_id="research-agent",
        api_key="agent-research-key",
        role=AgentRole.WORKER,
        created_at=datetime.now(),
    ))
    
    synth = AuthenticatedAgent(AgentCredentials(
        agent_id="synthesis-agent",
        api_key="agent-synth-key",
        role=AgentRole.WORKER,
        created_at=datetime.now(),
    ))
    
    await orchestrator.connect()
    await research.connect()
    await synth.connect()
    
    try:
        # Orchestrator creates intent
        print("\n1. Orchestrator creates intent...")
        intent_id = await orchestrator.create_intent(
            title="Multi-Agent Identity Demo",
            description="Demonstrates identity tracking across agents",
        )
        print(f"   Intent: {intent_id}")
        
        # Research agent works
        print("\n2. Research agent works on intent...")
        await research.work_on_intent(
            intent_id,
            "Conducted research on AI coordination protocols",
        )
        print(f"   Work logged by: {research.agent_id}")
        
        # Synthesis agent works
        print("\n3. Synthesis agent works on intent...")
        await synth.work_on_intent(
            intent_id,
            "Synthesized research findings into report",
        )
        print(f"   Work logged by: {synth.agent_id}")
        
        # Check event trail
        print("\n4. Event audit trail:")
        events = await orchestrator.client.get_events(intent_id)
        for event in events:
            payload = event.payload
            agent = payload.get("agent_id", payload.get("message", "N/A"))
            msg = payload.get("message", "")[:50]
            print(f"   [{event.event_type.value}] {msg}")
        
        # Check final state shows all contributors
        print("\n5. Final state shows identity trail:")
        intent = await orchestrator.client.get_intent(intent_id)
        state = intent.state.to_dict()
        print(f"   Created by: {state.get('created_by')}")
        print(f"   Last worked by: {state.get('last_worked_by')}")
        
    finally:
        await orchestrator.disconnect()
        await research.disconnect()
        await synth.disconnect()


async def demo_namespace_isolation():
    """
    Demonstrate namespace patterns for multi-tenant isolation.
    
    Pattern: Prefix agent_id and intent metadata with tenant namespace.
    This allows logical isolation without separate database instances.
    """
    
    print("\n" + "=" * 60)
    print("Namespace Isolation Pattern")
    print("=" * 60)
    
    def namespaced_agent_id(tenant: str, agent: str) -> str:
        """Create namespaced agent ID."""
        return f"{tenant}/{agent}"
    
    def namespaced_intent_id(tenant: str) -> dict:
        """Create namespace metadata for intent."""
        return {"namespace": tenant, "tenant_id": tenant}
    
    # Tenant A agents
    tenant_a_agent = namespaced_agent_id("acme-corp", "research-bot")
    tenant_a_client = AsyncOpenIntentClient(
        base_url=OPENINTENT_API_URL,
        api_key="dev-user-key",
        agent_id=tenant_a_agent,
    )
    
    # Tenant B agents
    tenant_b_agent = namespaced_agent_id("globex-inc", "research-bot")
    tenant_b_client = AsyncOpenIntentClient(
        base_url=OPENINTENT_API_URL,
        api_key="dev-user-key",
        agent_id=tenant_b_agent,
    )
    
    try:
        # Each tenant creates intent in their namespace
        intent_a = await tenant_a_client.create_intent(
            title="Acme Research Task",
            description="Research for Acme Corp",
            initial_state=namespaced_intent_id("acme-corp"),
        )
        
        intent_b = await tenant_b_client.create_intent(
            title="Globex Research Task",
            description="Research for Globex Inc",
            initial_state=namespaced_intent_id("globex-inc"),
        )
        
        print(f"\nTenant A ({tenant_a_agent}):")
        print(f"  Created intent: {intent_a.id}")
        print(f"  Namespace: acme-corp")
        
        print(f"\nTenant B ({tenant_b_agent}):")
        print(f"  Created intent: {intent_b.id}")
        print(f"  Namespace: globex-inc")
        
        print("\nIn production, queries would filter by namespace metadata")
        print("to ensure tenant isolation at the application layer.")
        
    finally:
        await tenant_a_client.close()
        await tenant_b_client.close()


if __name__ == "__main__":
    asyncio.run(demo_basic_auth())
    asyncio.run(demo_agent_registry())
    asyncio.run(demo_multi_agent_identity())
    asyncio.run(demo_namespace_isolation())
