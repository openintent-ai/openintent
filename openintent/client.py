"""
OpenIntent SDK - HTTP client for the OpenIntent Coordination Protocol.

Provides both synchronous and asynchronous clients with full protocol support.
"""

from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Generator, Optional

import httpx

if TYPE_CHECKING:
    from .streaming import EventQueue, SSEStream

from .exceptions import (
    ConflictError,
    LeaseConflictError,
    NotFoundError,
    OpenIntentError,
    ValidationError,
)
from .models import (
    AggregateStatus,
    ArbitrationRequest,
    CostSummary,
    Decision,
    EventType,
    Intent,
    IntentAttachment,
    IntentCost,
    IntentEvent,
    IntentFailure,
    IntentLease,
    IntentPortfolio,
    IntentStatus,
    IntentSubscription,
    LLMRequestPayload,
    MembershipRole,
    PortfolioMembership,
    PortfolioStatus,
    RetryPolicy,
    RetryStrategy,
    StreamState,
    StreamStatus,
    ToolCallPayload,
)


class OpenIntentClient:
    """
    Synchronous client for the OpenIntent Coordination Protocol.

    Example:
        ```python
        client = OpenIntentClient(
            base_url="https://api.openintent.ai",
            api_key="your-api-key",
            agent_id="my-agent"
        )

        # Create an intent
        intent = client.create_intent(
            title="Research market trends",
            description="Analyze Q4 market data and identify patterns"
        )

        # Update state with optimistic concurrency
        client.update_state(intent.id, intent.version, {"progress": 0.5})

        # Acquire a lease for exclusive scope access
        with client.lease(intent.id, "analysis") as lease:
            # Perform work within the leased scope
            client.log_event(intent.id, EventType.COMMENT, {"note": "Starting analysis"})
        ```
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        agent_id: str,
        timeout: float = 30.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.agent_id = agent_id
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={
                "X-API-Key": api_key,
                "X-Agent-ID": agent_id,
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )

    def _handle_response(self, response: httpx.Response) -> dict:
        """Handle HTTP response and raise appropriate exceptions."""
        if response.status_code == 404:
            raise NotFoundError(
                "Resource not found",
                status_code=404,
                response=response.json() if response.content else None,
            )
        elif response.status_code == 409:
            data = response.json() if response.content else {}
            if "lease" in str(data).lower():
                raise LeaseConflictError(
                    data.get("message", "Lease conflict"),
                    existing_lease=data.get("existing_lease"),
                    status_code=409,
                    response=data,
                )
            raise ConflictError(
                data.get("message", "Version conflict"),
                current_version=data.get("current_version"),
                status_code=409,
                response=data,
            )
        elif response.status_code == 400:
            data = response.json() if response.content else {}
            raise ValidationError(
                data.get("message", "Validation error"),
                errors=data.get("errors", []),
                status_code=400,
                response=data,
            )
        elif response.status_code >= 400:
            raise OpenIntentError(
                f"Request failed with status {response.status_code}",
                status_code=response.status_code,
                response=response.json() if response.content else None,
            )

        return response.json() if response.content else {}

    # ==================== Discovery ====================

    def discover(self) -> dict:
        """
        Discover protocol capabilities via .well-known endpoint.

        Returns:
            Protocol metadata including version, endpoints, and capabilities.
        """
        response = self._client.get("/.well-known/openintent.json")
        return self._handle_response(response)

    # ==================== Intent CRUD ====================

    def create_intent(
        self,
        title: str,
        description: str = "",
        constraints: Optional[list[str]] = None,
        initial_state: Optional[dict[str, Any]] = None,
        parent_intent_id: Optional[str] = None,
        depends_on: Optional[list[str]] = None,
    ) -> Intent:
        """
        Create a new intent.

        Args:
            title: Human-readable title for the intent.
            description: Detailed description of the goal.
            constraints: Optional list of constraints.
            initial_state: Optional initial state data.
            parent_intent_id: Optional parent intent ID for hierarchical graphs (RFC-0002).
            depends_on: Optional list of intent IDs this depends on (RFC-0002).

        Returns:
            The created Intent object.
        """
        payload: dict[str, Any] = {
            "title": title,
            "description": description,
            "constraints": constraints or [],
            "state": initial_state or {},
            "created_by": self.agent_id,
        }
        if parent_intent_id:
            payload["parent_intent_id"] = parent_intent_id
        if depends_on:
            payload["depends_on"] = depends_on
        response = self._client.post("/api/v1/intents", json=payload)
        data = self._handle_response(response)
        return Intent.from_dict(data)

    def get_intent(self, intent_id: str) -> Intent:
        """
        Retrieve an intent by ID.

        Args:
            intent_id: The unique identifier of the intent.

        Returns:
            The Intent object.
        """
        response = self._client.get(f"/api/v1/intents/{intent_id}")
        data = self._handle_response(response)
        return Intent.from_dict(data)

    def list_intents(
        self,
        status: Optional[IntentStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Intent]:
        """
        List intents with optional filtering.

        Args:
            status: Filter by intent status.
            limit: Maximum number of results.
            offset: Pagination offset.

        Returns:
            List of Intent objects.
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status.value

        response = self._client.get("/api/v1/intents", params=params)
        data = self._handle_response(response)
        return [Intent.from_dict(item) for item in data.get("intents", data)]

    # ==================== Intent Graphs (RFC-0002) ====================

    def create_child_intent(
        self,
        parent_id: str,
        title: str,
        description: str = "",
        constraints: Optional[list[str]] = None,
        initial_state: Optional[dict[str, Any]] = None,
        depends_on: Optional[list[str]] = None,
    ) -> Intent:
        """
        Create a child intent under a parent intent.

        Args:
            parent_id: The parent intent ID.
            title: Human-readable title for the child intent.
            description: Detailed description of the goal.
            constraints: Optional list of constraints.
            initial_state: Optional initial state data.
            depends_on: Optional list of intent IDs this depends on.

        Returns:
            The created child Intent object.
        """
        payload = {
            "title": title,
            "description": description,
            "constraints": constraints or [],
            "state": initial_state or {},
            "parent_intent_id": parent_id,
            "depends_on": depends_on or [],
        }
        response = self._client.post(
            f"/api/v1/intents/{parent_id}/children", json=payload
        )
        data = self._handle_response(response)
        return Intent.from_dict(data)

    def get_children(self, intent_id: str) -> list[Intent]:
        """
        Get immediate children of an intent.

        Args:
            intent_id: The parent intent ID.

        Returns:
            List of child Intent objects.
        """
        response = self._client.get(f"/api/v1/intents/{intent_id}/children")
        data = self._handle_response(response)
        return [Intent.from_dict(item) for item in data.get("children", data)]

    def get_descendants(self, intent_id: str) -> list[Intent]:
        """
        Get all descendants of an intent (recursive).

        Args:
            intent_id: The ancestor intent ID.

        Returns:
            List of all descendant Intent objects.
        """
        response = self._client.get(f"/api/v1/intents/{intent_id}/descendants")
        data = self._handle_response(response)
        return [Intent.from_dict(item) for item in data.get("descendants", data)]

    def get_ancestors(self, intent_id: str) -> list[Intent]:
        """
        Get all ancestors of an intent up to root.

        Args:
            intent_id: The descendant intent ID.

        Returns:
            List of ancestor Intent objects (nearest first).
        """
        response = self._client.get(f"/api/v1/intents/{intent_id}/ancestors")
        data = self._handle_response(response)
        return [Intent.from_dict(item) for item in data.get("ancestors", data)]

    def get_dependencies(self, intent_id: str) -> list[Intent]:
        """
        Get intents that this intent depends on.

        Args:
            intent_id: The dependent intent ID.

        Returns:
            List of dependency Intent objects.
        """
        response = self._client.get(f"/api/v1/intents/{intent_id}/dependencies")
        data = self._handle_response(response)
        return [Intent.from_dict(item) for item in data.get("dependencies", data)]

    def get_dependents(self, intent_id: str) -> list[Intent]:
        """
        Get intents that depend on this intent.

        Args:
            intent_id: The dependency intent ID.

        Returns:
            List of dependent Intent objects.
        """
        response = self._client.get(f"/api/v1/intents/{intent_id}/dependents")
        data = self._handle_response(response)
        return [Intent.from_dict(item) for item in data.get("dependents", data)]

    def add_dependency(
        self,
        intent_id: str,
        dependency_id: str,
        version: int,
    ) -> Intent:
        """
        Add a dependency to an intent.

        Args:
            intent_id: The intent to add dependency to.
            dependency_id: The intent that becomes a dependency.
            version: Expected current version (for conflict detection).

        Returns:
            The updated Intent object.

        Raises:
            ValidationError: If adding creates a cycle.
        """
        response = self._client.post(
            f"/api/v1/intents/{intent_id}/dependencies",
            json={"dependency_id": dependency_id},
            headers={"If-Match": str(version)},
        )
        data = self._handle_response(response)
        return Intent.from_dict(data)

    def remove_dependency(
        self,
        intent_id: str,
        dependency_id: str,
        version: int,
    ) -> Intent:
        """
        Remove a dependency from an intent.

        Args:
            intent_id: The intent to remove dependency from.
            dependency_id: The dependency to remove.
            version: Expected current version (for conflict detection).

        Returns:
            The updated Intent object.
        """
        response = self._client.delete(
            f"/api/v1/intents/{intent_id}/dependencies/{dependency_id}",
            headers={"If-Match": str(version)},
        )
        data = self._handle_response(response)
        return Intent.from_dict(data)

    def get_ready_intents(self, intent_id: str) -> list[Intent]:
        """
        Get child intents that are ready to work on (all dependencies satisfied).

        Args:
            intent_id: The parent intent ID.

        Returns:
            List of Intent objects that have no blocking dependencies.
        """
        response = self._client.get(f"/api/v1/intents/{intent_id}/ready")
        data = self._handle_response(response)
        return [Intent.from_dict(item) for item in data.get("ready", data)]

    def get_blocked_intents(self, intent_id: str) -> list[Intent]:
        """
        Get child intents that are blocked by unmet dependencies.

        Args:
            intent_id: The parent intent ID.

        Returns:
            List of Intent objects that have blocking dependencies.
        """
        response = self._client.get(f"/api/v1/intents/{intent_id}/blocked")
        data = self._handle_response(response)
        return [Intent.from_dict(item) for item in data.get("blocked", data)]

    def get_intent_graph(self, intent_id: str) -> dict[str, Any]:
        """
        Get the full intent graph from a node.

        Args:
            intent_id: The intent to get graph from.

        Returns:
            Graph structure with nodes, edges, and metadata.
        """
        response = self._client.get(f"/api/v1/intents/{intent_id}/graph")
        return self._handle_response(response)

    # ==================== State Management ====================

    def update_state(
        self,
        intent_id: str,
        version: int,
        state_patch: dict[str, Any],
    ) -> Intent:
        """
        Update intent state with optimistic concurrency control.

        Args:
            intent_id: The intent to update.
            version: Expected current version (for conflict detection).
            state_patch: Partial state update to merge.

        Returns:
            The updated Intent object.

        Raises:
            ConflictError: If version doesn't match (another update occurred).
        """
        # Convert state dict to RFC-compliant JSON Patch format
        patches = [{"op": "set", "path": k, "value": v} for k, v in state_patch.items()]
        response = self._client.post(
            f"/api/v1/intents/{intent_id}/state",
            json={"patches": patches},
            headers={"If-Match": str(version)},
        )
        data = self._handle_response(response)
        return Intent.from_dict(data)

    def set_status(
        self,
        intent_id: str,
        version: int,
        status: IntentStatus,
    ) -> Intent:
        """
        Change intent status.

        Args:
            intent_id: The intent to update.
            version: Expected current version.
            status: New status to set.

        Returns:
            The updated Intent object.
        """
        response = self._client.post(
            f"/api/v1/intents/{intent_id}/status",
            json={"status": status.value},
            headers={"If-Match": str(version)},
        )
        data = self._handle_response(response)
        return Intent.from_dict(data)

    # ==================== Event Log ====================

    def log_event(
        self,
        intent_id: str,
        event_type: EventType,
        payload: Optional[dict[str, Any]] = None,
    ) -> IntentEvent:
        """
        Append an event to the intent's audit log.

        Args:
            intent_id: The intent to log against.
            event_type: Type of event.
            payload: Event-specific data.

        Returns:
            The created IntentEvent object.
        """
        response = self._client.post(
            f"/api/v1/intents/{intent_id}/events",
            json={
                "event_type": event_type.value,
                "actor": self.agent_id,
                "payload": payload or {},
            },
        )
        data = self._handle_response(response)
        return IntentEvent.from_dict(data)

    def get_events(
        self,
        intent_id: str,
        event_type: Optional[EventType] = None,
        since: Optional[datetime] = None,
        limit: int = 100,
    ) -> list[IntentEvent]:
        """
        Retrieve events from the intent's audit log.

        Args:
            intent_id: The intent to query.
            event_type: Optional filter by event type.
            since: Optional filter for events after this time.
            limit: Maximum number of events.

        Returns:
            List of IntentEvent objects.
        """
        params: dict[str, Any] = {"limit": limit}
        if event_type:
            params["event_type"] = event_type.value
        if since:
            params["since"] = since.isoformat()

        response = self._client.get(
            f"/api/v1/intents/{intent_id}/events",
            params=params,
        )
        data = self._handle_response(response)
        # Handle both list response and dict with "events" key
        events = data if isinstance(data, list) else data.get("events", [])
        return [IntentEvent.from_dict(item) for item in events]

    # ==================== Lease Management ====================

    def acquire_lease(
        self,
        intent_id: str,
        scope: str,
        duration_seconds: int = 300,
    ) -> IntentLease:
        """
        Acquire a lease for exclusive access to a scope.

        Args:
            intent_id: The intent to lease within.
            scope: The scope to acquire (e.g., "research", "synthesis").
            duration_seconds: How long the lease should last.

        Returns:
            The acquired IntentLease object.

        Raises:
            LeaseConflictError: If scope is already leased by another agent.
        """
        response = self._client.post(
            f"/api/v1/intents/{intent_id}/leases",
            json={
                "scope": scope,
                "duration_seconds": duration_seconds,
            },
        )
        data = self._handle_response(response)
        return IntentLease.from_dict(data)

    def release_lease(self, intent_id: str, lease_id: str) -> None:
        """
        Release a previously acquired lease.

        Args:
            intent_id: The intent containing the lease.
            lease_id: The lease to release.
        """
        response = self._client.delete(f"/api/v1/intents/{intent_id}/leases/{lease_id}")
        self._handle_response(response)

    def get_leases(self, intent_id: str) -> list[IntentLease]:
        """
        List all active leases for an intent.

        Args:
            intent_id: The intent to query.

        Returns:
            List of IntentLease objects.
        """
        response = self._client.get(f"/api/v1/intents/{intent_id}/leases")
        data = self._handle_response(response)
        return [IntentLease.from_dict(item) for item in data.get("leases", data)]

    def renew_lease(
        self,
        intent_id: str,
        lease_id: str,
        duration_seconds: int = 300,
    ) -> IntentLease:
        """
        Renew an existing lease to extend its expiration.

        Args:
            intent_id: The intent the lease belongs to.
            lease_id: The lease to renew.
            duration_seconds: New duration from now.

        Returns:
            The renewed IntentLease object.
        """
        response = self._client.patch(
            f"/api/v1/intents/{intent_id}/leases/{lease_id}",
            json={"duration_seconds": duration_seconds},
        )
        data = self._handle_response(response)
        return IntentLease.from_dict(data)

    @contextmanager
    def lease(
        self, intent_id: str, scope: str, duration_seconds: int = 300
    ) -> Generator[IntentLease, None, None]:
        """
        Context manager for lease acquisition and release.

        Example:
            ```python
            with client.lease(intent_id, "analysis") as lease:
                # Perform exclusive work
                pass
            # Lease automatically released
            ```
        """
        acquired_lease = self.acquire_lease(intent_id, scope, duration_seconds)
        try:
            yield acquired_lease
        finally:
            try:
                self.release_lease(intent_id, acquired_lease.id)
            except Exception:
                pass  # Lease may have expired

    # ==================== Governance ====================

    def request_arbitration(
        self,
        intent_id: str,
        reason: str,
        context: Optional[dict[str, Any]] = None,
    ) -> ArbitrationRequest:
        """
        Request human arbitration for a conflict or decision.

        Args:
            intent_id: The intent requiring arbitration.
            reason: Explanation of why arbitration is needed.
            context: Additional context for the arbitrator.

        Returns:
            The created ArbitrationRequest object.
        """
        response = self._client.post(
            f"/api/v1/intents/{intent_id}/arbitrate",
            json={
                "reason": reason,
                "context": context or {},
            },
        )
        data = self._handle_response(response)
        return ArbitrationRequest.from_dict(data)

    def record_decision(
        self,
        intent_id: str,
        decision_type: str,
        outcome: str,
        reasoning: str,
    ) -> Decision:
        """
        Record a governance decision.

        Args:
            intent_id: The intent the decision applies to.
            decision_type: Type of decision (e.g., "arbitration", "escalation").
            outcome: The decision outcome.
            reasoning: Explanation of the decision.

        Returns:
            The created Decision object.
        """
        response = self._client.post(
            f"/api/v1/intents/{intent_id}/decisions",
            json={
                "decision_type": decision_type,
                "outcome": outcome,
                "reasoning": reasoning,
            },
        )
        data = self._handle_response(response)
        return Decision.from_dict(data)

    def get_decisions(self, intent_id: str) -> list[Decision]:
        """
        Retrieve all decisions for an intent.

        Args:
            intent_id: The intent to query.

        Returns:
            List of Decision objects.
        """
        response = self._client.get(f"/api/v1/intents/{intent_id}/decisions")
        data = self._handle_response(response)
        return [Decision.from_dict(item) for item in data.get("decisions", data)]

    # ==================== Agent Management ====================

    def assign_agent(self, intent_id: str, agent_id: Optional[str] = None) -> dict:
        """
        Assign an agent to work on an intent.

        Args:
            intent_id: The intent to assign to.
            agent_id: Agent to assign (defaults to current agent).

        Returns:
            Assignment confirmation.
        """
        response = self._client.post(
            f"/api/v1/intents/{intent_id}/agents",
            json={"agent_id": agent_id or self.agent_id},
        )
        return self._handle_response(response)

    def unassign_agent(self, intent_id: str, agent_id: Optional[str] = None) -> None:
        """
        Remove an agent from an intent.

        Args:
            intent_id: The intent to unassign from.
            agent_id: Agent to remove (defaults to current agent).
        """
        aid = agent_id or self.agent_id
        response = self._client.delete(f"/api/v1/intents/{intent_id}/agents/{aid}")
        self._handle_response(response)

    def create_portfolio(
        self,
        name: str,
        description: Optional[str] = None,
        governance_policy: Optional[dict[str, Any]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> IntentPortfolio:
        """
        Create a new intent portfolio for multi-intent coordination.

        Args:
            name: Portfolio name.
            description: Optional description.
            governance_policy: Optional governance rules (e.g., require_all_completed).
            metadata: Optional metadata.

        Returns:
            The created portfolio.
        """
        response = self._client.post(
            "/api/v1/portfolios",
            json={
                "name": name,
                "description": description,
                "createdBy": self.agent_id,
                "governancePolicy": governance_policy or {},
                "metadata": metadata or {},
            },
        )
        data = self._handle_response(response)
        return IntentPortfolio.from_dict(data)

    def get_portfolio(self, portfolio_id: str) -> IntentPortfolio:
        """
        Get a portfolio with its intents and aggregate status.

        Args:
            portfolio_id: The portfolio ID.

        Returns:
            Portfolio with intents and aggregate status.
        """
        response = self._client.get(f"/api/v1/portfolios/{portfolio_id}")
        data = self._handle_response(response)
        return IntentPortfolio.from_dict(data)

    def list_portfolios(
        self, created_by: Optional[str] = None
    ) -> list[IntentPortfolio]:
        """
        List portfolios, optionally filtered by creator.

        Args:
            created_by: Optional filter by creator.

        Returns:
            List of portfolios.
        """
        params = {}
        if created_by:
            params["created_by"] = created_by
        response = self._client.get("/api/v1/portfolios", params=params)
        data = self._handle_response(response)
        return [IntentPortfolio.from_dict(p) for p in data.get("portfolios", [])]

    def update_portfolio_status(
        self, portfolio_id: str, status: PortfolioStatus
    ) -> IntentPortfolio:
        """
        Update portfolio status.

        Args:
            portfolio_id: The portfolio ID.
            status: New status (active, completed, abandoned).

        Returns:
            Updated portfolio.
        """
        response = self._client.patch(
            f"/api/v1/portfolios/{portfolio_id}/status",
            json={"status": status.value},
        )
        data = self._handle_response(response)
        return IntentPortfolio.from_dict(data)

    def add_intent_to_portfolio(
        self,
        portfolio_id: str,
        intent_id: str,
        role: MembershipRole = MembershipRole.MEMBER,
        priority: int = 0,
    ) -> PortfolioMembership:
        """
        Add an intent to a portfolio.

        Args:
            portfolio_id: The portfolio ID.
            intent_id: The intent to add.
            role: Membership role (primary, member, dependency).
            priority: Priority (higher = more important).

        Returns:
            Membership record.
        """
        response = self._client.post(
            f"/api/v1/portfolios/{portfolio_id}/intents",
            json={
                "intent_id": intent_id,
                "role": role.value,
                "priority": priority,
            },
        )
        data = self._handle_response(response)
        return PortfolioMembership.from_dict(data)

    def remove_intent_from_portfolio(self, portfolio_id: str, intent_id: str) -> None:
        """
        Remove an intent from a portfolio.

        Args:
            portfolio_id: The portfolio ID.
            intent_id: The intent to remove.
        """
        response = self._client.delete(
            f"/api/v1/portfolios/{portfolio_id}/intents/{intent_id}"
        )
        if response.status_code != 204:
            self._handle_response(response)

    def get_portfolio_intents(
        self, portfolio_id: str
    ) -> tuple[list[Intent], AggregateStatus]:
        """
        Get all intents in a portfolio with aggregate status.

        Args:
            portfolio_id: The portfolio ID.

        Returns:
            Tuple of (intents list, aggregate status).
        """
        response = self._client.get(f"/api/v1/portfolios/{portfolio_id}/intents")
        data = self._handle_response(response)
        intents = [Intent.from_dict(i) for i in data.get("intents", [])]
        agg = AggregateStatus.from_dict(data.get("aggregate_status", {}))
        return intents, agg

    def get_intent_portfolios(self, intent_id: str) -> list[IntentPortfolio]:
        """
        Get all portfolios containing an intent.

        Args:
            intent_id: The intent ID.

        Returns:
            List of portfolios.
        """
        response = self._client.get(f"/api/v1/intents/{intent_id}/portfolios")
        data = self._handle_response(response)
        return [IntentPortfolio.from_dict(p) for p in data.get("portfolios", [])]

    # RFC-0005: Attachments
    def add_attachment(
        self,
        intent_id: str,
        filename: str,
        mime_type: str,
        size: int,
        storage_url: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> IntentAttachment:
        """
        Add a file attachment to an intent.

        Args:
            intent_id: The intent ID.
            filename: Name of the file.
            mime_type: MIME type (e.g., image/jpeg, application/pdf).
            size: File size in bytes.
            storage_url: URL where the file is stored.
            metadata: Optional metadata (dimensions, duration, etc.).

        Returns:
            The created attachment.
        """
        response = self._client.post(
            f"/api/v1/intents/{intent_id}/attachments",
            json={
                "filename": filename,
                "mime_type": mime_type,
                "size": size,
                "storage_url": storage_url,
                "metadata": metadata or {},
            },
        )
        data = self._handle_response(response)
        return IntentAttachment.from_dict(data)

    def get_attachments(self, intent_id: str) -> list[IntentAttachment]:
        """
        Get all attachments for an intent.

        Args:
            intent_id: The intent ID.

        Returns:
            List of attachments.
        """
        response = self._client.get(f"/api/v1/intents/{intent_id}/attachments")
        data = self._handle_response(response)
        return [IntentAttachment.from_dict(a) for a in data.get("attachments", [])]

    def delete_attachment(self, intent_id: str, attachment_id: str) -> None:
        """
        Delete an attachment from an intent.

        Args:
            intent_id: The intent ID.
            attachment_id: The attachment ID to delete.
        """
        response = self._client.delete(
            f"/api/v1/intents/{intent_id}/attachments/{attachment_id}"
        )
        if response.status_code != 204:
            self._handle_response(response)

    # RFC-0009: Cost Tracking
    def record_cost(
        self,
        intent_id: str,
        cost_type: str,
        amount: int,
        unit: str,
        provider: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> IntentCost:
        """
        Record a cost/resource usage for an intent.

        Args:
            intent_id: The intent ID.
            cost_type: Type of cost (tokens, api_call, compute, custom).
            amount: Amount of resources used.
            unit: Unit of measurement (tokens, cents, seconds).
            provider: Optional provider name (openai, anthropic, etc.).
            metadata: Optional additional info (model, prompt_tokens, etc.).

        Returns:
            The recorded cost.
        """
        response = self._client.post(
            f"/api/v1/intents/{intent_id}/costs",
            json={
                "agent_id": self.agent_id,
                "cost_type": cost_type,
                "amount": amount,
                "unit": unit,
                "provider": provider,
                "metadata": metadata or {},
            },
        )
        data = self._handle_response(response)
        return IntentCost.from_dict(data)

    def get_costs(self, intent_id: str) -> tuple[list[IntentCost], CostSummary]:
        """
        Get all costs for an intent with summary.

        Args:
            intent_id: The intent ID.

        Returns:
            Tuple of (costs list, cost summary).
        """
        response = self._client.get(f"/api/v1/intents/{intent_id}/costs")
        data = self._handle_response(response)
        costs = [IntentCost.from_dict(c) for c in data.get("costs", [])]
        summary = CostSummary.from_dict(data.get("summary", {}))
        return costs, summary

    # RFC-0010: Retry Policies
    def set_retry_policy(
        self,
        intent_id: str,
        strategy: RetryStrategy = RetryStrategy.EXPONENTIAL,
        max_retries: int = 3,
        base_delay_ms: int = 1000,
        max_delay_ms: int = 60000,
        fallback_agent_id: Optional[str] = None,
        failure_threshold: int = 3,
    ) -> RetryPolicy:
        """
        Set or update retry policy for an intent.

        Args:
            intent_id: The intent ID.
            strategy: Retry strategy (none, fixed, exponential, linear).
            max_retries: Maximum retry attempts.
            base_delay_ms: Initial delay between retries in milliseconds.
            max_delay_ms: Maximum delay between retries.
            fallback_agent_id: Agent to hand off to after max failures.
            failure_threshold: Failures before triggering fallback.

        Returns:
            The retry policy.
        """
        response = self._client.put(
            f"/api/v1/intents/{intent_id}/retry-policy",
            json={
                "strategy": strategy.value,
                "max_retries": max_retries,
                "base_delay_ms": base_delay_ms,
                "max_delay_ms": max_delay_ms,
                "fallback_agent_id": fallback_agent_id,
                "failure_threshold": failure_threshold,
            },
        )
        data = self._handle_response(response)
        return RetryPolicy.from_dict(data)

    def get_retry_policy(self, intent_id: str) -> Optional[RetryPolicy]:
        """
        Get retry policy for an intent.

        Args:
            intent_id: The intent ID.

        Returns:
            Retry policy or None if not configured.
        """
        response = self._client.get(f"/api/v1/intents/{intent_id}/retry-policy")
        if response.status_code == 404:
            return None
        data = self._handle_response(response)
        return RetryPolicy.from_dict(data)

    def record_failure(
        self,
        intent_id: str,
        attempt_number: int,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        retry_scheduled_at: Optional[datetime] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> IntentFailure:
        """
        Record a failure that occurred while processing an intent.

        Args:
            intent_id: The intent ID.
            attempt_number: Which attempt this was.
            error_code: Optional error code.
            error_message: Optional error description.
            retry_scheduled_at: When retry is scheduled (if any).
            metadata: Optional additional info.

        Returns:
            The recorded failure.
        """
        response = self._client.post(
            f"/api/v1/intents/{intent_id}/failures",
            json={
                "agent_id": self.agent_id,
                "attempt_number": attempt_number,
                "error_code": error_code,
                "error_message": error_message,
                "retry_scheduled_at": (
                    retry_scheduled_at.isoformat() if retry_scheduled_at else None
                ),
                "metadata": metadata or {},
            },
        )
        data = self._handle_response(response)
        return IntentFailure.from_dict(data)

    def get_failures(self, intent_id: str) -> list[IntentFailure]:
        """
        Get failure history for an intent.

        Args:
            intent_id: The intent ID.

        Returns:
            List of failures.
        """
        response = self._client.get(f"/api/v1/intents/{intent_id}/failures")
        data = self._handle_response(response)
        return [IntentFailure.from_dict(f) for f in data.get("failures", [])]

    # RFC-0006: Subscriptions
    def subscribe(
        self,
        intent_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        event_types: Optional[list[str]] = None,
        webhook_url: Optional[str] = None,
        expires_at: Optional[datetime] = None,
    ) -> IntentSubscription:
        """
        Subscribe to real-time notifications for an intent or portfolio.

        Args:
            intent_id: Intent to subscribe to (optional).
            portfolio_id: Portfolio to subscribe to (optional).
            event_types: Which events to receive (optional, all if not specified).
            webhook_url: URL to receive webhook notifications.
            expires_at: When subscription expires (optional).

        Returns:
            The created subscription.
        """
        response = self._client.post(
            "/api/v1/subscriptions",
            json={
                "intent_id": intent_id,
                "portfolio_id": portfolio_id,
                "subscriber_id": self.agent_id,
                "event_types": event_types or [],
                "webhook_url": webhook_url,
                "expires_at": expires_at.isoformat() if expires_at else None,
            },
        )
        data = self._handle_response(response)
        return IntentSubscription.from_dict(data)

    def get_subscriptions(
        self, intent_id: Optional[str] = None, portfolio_id: Optional[str] = None
    ) -> list[IntentSubscription]:
        """
        Get subscriptions, optionally filtered by intent or portfolio.

        Args:
            intent_id: Filter by intent (optional).
            portfolio_id: Filter by portfolio (optional).

        Returns:
            List of subscriptions.
        """
        params = {}
        if intent_id:
            params["intent_id"] = intent_id
        if portfolio_id:
            params["portfolio_id"] = portfolio_id
        response = self._client.get("/api/v1/subscriptions", params=params)
        data = self._handle_response(response)
        return [IntentSubscription.from_dict(s) for s in data.get("subscriptions", [])]

    def unsubscribe(self, subscription_id: str) -> None:
        """
        Remove a subscription.

        Args:
            subscription_id: The subscription ID to remove.
        """
        response = self._client.delete(f"/api/v1/subscriptions/{subscription_id}")
        if response.status_code != 204:
            self._handle_response(response)

    # ==================== Tool Call Logging ====================

    def log_tool_call_started(
        self,
        intent_id: str,
        tool_name: str,
        tool_id: str,
        arguments: dict[str, Any],
        provider: Optional[str] = None,
        model: Optional[str] = None,
        parent_request_id: Optional[str] = None,
    ) -> IntentEvent:
        """
        Log the start of a tool call initiated by an LLM.

        Args:
            intent_id: The intent this tool call is part of.
            tool_name: Name of the tool being called.
            tool_id: Unique identifier for this tool call.
            arguments: Arguments passed to the tool.
            provider: LLM provider (e.g., "openai", "anthropic").
            model: Model that initiated the call.
            parent_request_id: ID of the parent LLM request.

        Returns:
            The created event.
        """
        payload = ToolCallPayload(
            tool_name=tool_name,
            tool_id=tool_id,
            arguments=arguments,
            provider=provider,
            model=model,
            parent_request_id=parent_request_id,
        )
        return self.log_event(intent_id, EventType.TOOL_CALL_STARTED, payload.to_dict())

    def log_tool_call_completed(
        self,
        intent_id: str,
        tool_name: str,
        tool_id: str,
        arguments: dict[str, Any],
        result: Any,
        duration_ms: Optional[int] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ) -> IntentEvent:
        """
        Log the successful completion of a tool call.

        Args:
            intent_id: The intent this tool call is part of.
            tool_name: Name of the tool that was called.
            tool_id: Unique identifier for this tool call.
            arguments: Arguments that were passed to the tool.
            result: Result returned by the tool.
            duration_ms: How long the tool call took.
            provider: LLM provider.
            model: Model that initiated the call.

        Returns:
            The created event.
        """
        payload = ToolCallPayload(
            tool_name=tool_name,
            tool_id=tool_id,
            arguments=arguments,
            result=result,
            duration_ms=duration_ms,
            provider=provider,
            model=model,
        )
        return self.log_event(
            intent_id, EventType.TOOL_CALL_COMPLETED, payload.to_dict()
        )

    def log_tool_call_failed(
        self,
        intent_id: str,
        tool_name: str,
        tool_id: str,
        arguments: dict[str, Any],
        error: str,
        duration_ms: Optional[int] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ) -> IntentEvent:
        """
        Log a failed tool call.

        Args:
            intent_id: The intent this tool call is part of.
            tool_name: Name of the tool that failed.
            tool_id: Unique identifier for this tool call.
            arguments: Arguments that were passed to the tool.
            error: Error message or description.
            duration_ms: How long before the failure.
            provider: LLM provider.
            model: Model that initiated the call.

        Returns:
            The created event.
        """
        payload = ToolCallPayload(
            tool_name=tool_name,
            tool_id=tool_id,
            arguments=arguments,
            error=error,
            duration_ms=duration_ms,
            provider=provider,
            model=model,
        )
        return self.log_event(intent_id, EventType.TOOL_CALL_FAILED, payload.to_dict())

    # ==================== LLM Request Logging ====================

    def log_llm_request_started(
        self,
        intent_id: str,
        request_id: str,
        provider: str,
        model: str,
        messages_count: int,
        tools_available: Optional[list[str]] = None,
        stream: bool = False,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> IntentEvent:
        """
        Log the start of an LLM API request.

        Args:
            intent_id: The intent this request is part of.
            request_id: Unique identifier for this request.
            provider: LLM provider (e.g., "openai", "anthropic").
            model: Model being called.
            messages_count: Number of messages in the request.
            tools_available: List of tool names available to the model.
            stream: Whether this is a streaming request.
            temperature: Temperature setting.
            max_tokens: Max tokens setting.

        Returns:
            The created event.
        """
        payload = LLMRequestPayload(
            request_id=request_id,
            provider=provider,
            model=model,
            messages_count=messages_count,
            tools_available=tools_available or [],
            stream=stream,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return self.log_event(
            intent_id, EventType.LLM_REQUEST_STARTED, payload.to_dict()
        )

    def log_llm_request_completed(
        self,
        intent_id: str,
        request_id: str,
        provider: str,
        model: str,
        messages_count: int,
        response_content: Optional[str] = None,
        tool_calls: Optional[list[dict[str, Any]]] = None,
        finish_reason: Optional[str] = None,
        prompt_tokens: Optional[int] = None,
        completion_tokens: Optional[int] = None,
        total_tokens: Optional[int] = None,
        duration_ms: Optional[int] = None,
    ) -> IntentEvent:
        """
        Log the successful completion of an LLM API request.

        Args:
            intent_id: The intent this request is part of.
            request_id: Unique identifier for this request.
            provider: LLM provider.
            model: Model that was called.
            messages_count: Number of messages in the request.
            response_content: Text content of the response.
            tool_calls: Any tool calls in the response.
            finish_reason: Why the model stopped generating.
            prompt_tokens: Tokens used for the prompt.
            completion_tokens: Tokens used for the completion.
            total_tokens: Total tokens used.
            duration_ms: Request duration in milliseconds.

        Returns:
            The created event.
        """
        payload = LLMRequestPayload(
            request_id=request_id,
            provider=provider,
            model=model,
            messages_count=messages_count,
            response_content=response_content,
            tool_calls=tool_calls or [],
            finish_reason=finish_reason,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            duration_ms=duration_ms,
        )
        return self.log_event(
            intent_id, EventType.LLM_REQUEST_COMPLETED, payload.to_dict()
        )

    def log_llm_request_failed(
        self,
        intent_id: str,
        request_id: str,
        provider: str,
        model: str,
        messages_count: int,
        error: str,
        duration_ms: Optional[int] = None,
    ) -> IntentEvent:
        """
        Log a failed LLM API request.

        Args:
            intent_id: The intent this request is part of.
            request_id: Unique identifier for this request.
            provider: LLM provider.
            model: Model that was called.
            messages_count: Number of messages in the request.
            error: Error message or description.
            duration_ms: Time until failure.

        Returns:
            The created event.
        """
        payload = LLMRequestPayload(
            request_id=request_id,
            provider=provider,
            model=model,
            messages_count=messages_count,
            error=error,
            duration_ms=duration_ms,
        )
        return self.log_event(
            intent_id, EventType.LLM_REQUEST_FAILED, payload.to_dict()
        )

    # ==================== Stream Coordination ====================

    def start_stream(
        self,
        intent_id: str,
        stream_id: str,
        provider: str,
        model: str,
    ) -> IntentEvent:
        """
        Signal the start of a streaming LLM response.

        Args:
            intent_id: The intent this stream is part of.
            stream_id: Unique identifier for this stream.
            provider: LLM provider.
            model: Model being streamed from.

        Returns:
            The created event.
        """
        payload = StreamState(
            stream_id=stream_id,
            intent_id=intent_id,
            agent_id=self.agent_id,
            status=StreamStatus.ACTIVE,
            provider=provider,
            model=model,
            started_at=datetime.now(),
        )
        return self.log_event(intent_id, EventType.STREAM_STARTED, payload.to_dict())

    def log_stream_chunk(
        self,
        intent_id: str,
        stream_id: str,
        chunk_index: int,
        token_count: int = 1,
    ) -> IntentEvent:
        """
        Log a chunk received during streaming (use sparingly for performance).

        Args:
            intent_id: The intent this stream is part of.
            stream_id: The stream identifier.
            chunk_index: Index of this chunk.
            token_count: Number of tokens in this chunk.

        Returns:
            The created event.
        """
        return self.log_event(
            intent_id,
            EventType.STREAM_CHUNK,
            {
                "stream_id": stream_id,
                "chunk_index": chunk_index,
                "token_count": token_count,
            },
        )

    def complete_stream(
        self,
        intent_id: str,
        stream_id: str,
        provider: str,
        model: str,
        chunks_received: int,
        tokens_streamed: int,
    ) -> IntentEvent:
        """
        Signal successful completion of a stream.

        Args:
            intent_id: The intent this stream is part of.
            stream_id: The stream identifier.
            provider: LLM provider.
            model: Model that was streamed from.
            chunks_received: Total chunks received.
            tokens_streamed: Total tokens streamed.

        Returns:
            The created event.
        """
        payload = StreamState(
            stream_id=stream_id,
            intent_id=intent_id,
            agent_id=self.agent_id,
            status=StreamStatus.COMPLETED,
            provider=provider,
            model=model,
            chunks_received=chunks_received,
            tokens_streamed=tokens_streamed,
            completed_at=datetime.now(),
        )
        return self.log_event(intent_id, EventType.STREAM_COMPLETED, payload.to_dict())

    def cancel_stream(
        self,
        intent_id: str,
        stream_id: str,
        provider: str,
        model: str,
        reason: Optional[str] = None,
        chunks_received: int = 0,
        tokens_streamed: int = 0,
    ) -> IntentEvent:
        """
        Signal cancellation of an active stream.

        Args:
            intent_id: The intent this stream is part of.
            stream_id: The stream identifier.
            provider: LLM provider.
            model: Model that was being streamed from.
            reason: Why the stream was cancelled.
            chunks_received: Chunks received before cancellation.
            tokens_streamed: Tokens streamed before cancellation.

        Returns:
            The created event.
        """
        payload = StreamState(
            stream_id=stream_id,
            intent_id=intent_id,
            agent_id=self.agent_id,
            status=StreamStatus.CANCELLED,
            provider=provider,
            model=model,
            chunks_received=chunks_received,
            tokens_streamed=tokens_streamed,
            cancelled_at=datetime.now(),
            cancel_reason=reason,
        )
        return self.log_event(intent_id, EventType.STREAM_CANCELLED, payload.to_dict())

    # =========================================================================
    # SSE Streaming Subscriptions
    # =========================================================================

    def subscribe_sse(self, intent_id: str) -> "SSEStream":
        """
        Subscribe to real-time events for a specific intent via SSE.

        This returns an iterator that yields events as they occur, providing
        sub-second latency compared to polling.

        Args:
            intent_id: The intent ID to subscribe to.

        Returns:
            An SSEStream that yields SSEEvent objects.

        Example:
            ```python
            from openintent.streaming import SSEEventType

            for event in client.subscribe_sse(intent_id):
                if event.type == SSEEventType.STATE_CHANGED:
                    print(f"State updated: {event.data}")
                elif event.type == SSEEventType.STATUS_CHANGED:
                    print(f"Status: {event.data['status']}")
            ```
        """
        from .streaming import SSEStream

        url = f"{self.base_url}/api/v1/intents/{intent_id}/subscribe"
        headers = {
            "X-API-Key": self.api_key,
            "X-Agent-ID": self.agent_id,
        }
        return SSEStream(url, headers)

    def subscribe_portfolio(self, portfolio_id: str) -> "SSEStream":
        """
        Subscribe to real-time events for all intents in a portfolio.

        Coordinators should use this to monitor portfolio-wide progress
        instead of subscribing to each intent individually.

        Args:
            portfolio_id: The portfolio ID to subscribe to.

        Returns:
            An SSEStream that yields SSEEvent objects for all portfolio events.

        Example:
            ```python
            for event in client.subscribe_portfolio(portfolio_id):
                if event.type == "INTENT_COMPLETED":
                    intent_id = event.data["intent_id"]
                    print(f"Intent {intent_id} completed")
            ```
        """
        from .streaming import SSEStream

        url = f"{self.base_url}/api/v1/portfolios/{portfolio_id}/subscribe"
        headers = {
            "X-API-Key": self.api_key,
            "X-Agent-ID": self.agent_id,
        }
        return SSEStream(url, headers)

    def subscribe_agent(self, agent_id: Optional[str] = None) -> "SSEStream":
        """
        Subscribe to events for intents assigned to an agent.

        Agents should use this to receive notifications when new intents
        are assigned to them, without polling.

        Args:
            agent_id: The agent ID (defaults to this client's agent_id).

        Returns:
            An SSEStream that yields SSEEvent objects for agent assignments.

        Example:
            ```python
            for event in client.subscribe_agent():
                if event.type == "INTENT_ASSIGNED":
                    intent_id = event.data["intent_id"]
                    print(f"New assignment: {intent_id}")
                    process_intent(intent_id)
            ```
        """
        from .streaming import SSEStream

        aid = agent_id or self.agent_id
        url = f"{self.base_url}/api/v1/agents/{aid}/subscribe"
        headers = {
            "X-API-Key": self.api_key,
            "X-Agent-ID": self.agent_id,
        }
        return SSEStream(url, headers)

    def create_event_queue(
        self,
        intent_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> "EventQueue":
        """
        Create a queue-based event subscription for easier processing.

        Use this when you want to process events in a pull-based manner
        rather than an iterator-based manner.

        Args:
            intent_id: Subscribe to a specific intent.
            portfolio_id: Subscribe to a portfolio (mutually exclusive with intent_id).
            agent_id: Subscribe to agent assignments.

        Returns:
            An EventQueue that can be used to get events.

        Example:
            ```python
            with client.create_event_queue(portfolio_id=portfolio_id) as queue:
                while True:
                    event = queue.get(timeout=30)
                    if event:
                        handle_event(event)
            ```
        """
        from .streaming import EventQueue

        if intent_id:
            url = f"{self.base_url}/api/v1/intents/{intent_id}/subscribe"
        elif portfolio_id:
            url = f"{self.base_url}/api/v1/portfolios/{portfolio_id}/subscribe"
        elif agent_id:
            url = f"{self.base_url}/api/v1/agents/{agent_id}/subscribe"
        else:
            url = f"{self.base_url}/api/v1/agents/{self.agent_id}/subscribe"

        headers = {
            "X-API-Key": self.api_key,
            "X-Agent-ID": self.agent_id,
        }
        return EventQueue(url, headers)

    def close(self) -> None:
        """Close the HTTP client connection."""
        self._client.close()

    def __enter__(self) -> "OpenIntentClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


class AsyncOpenIntentClient:
    """
    Asynchronous client for the OpenIntent Coordination Protocol.

    Example:
        ```python
        async with AsyncOpenIntentClient(
            base_url="https://api.openintent.ai",
            api_key="your-api-key",
            agent_id="my-agent"
        ) as client:
            intent = await client.create_intent(
                title="Research task",
                description="Analyze data"
            )
        ```
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        agent_id: str,
        timeout: float = 30.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.agent_id = agent_id
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "X-API-Key": api_key,
                "X-Agent-ID": agent_id,
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )

    def _handle_response(self, response: httpx.Response) -> dict:
        """Handle HTTP response and raise appropriate exceptions."""
        if response.status_code == 404:
            raise NotFoundError(
                "Resource not found",
                status_code=404,
                response=response.json() if response.content else None,
            )
        elif response.status_code == 409:
            data = response.json() if response.content else {}
            if "lease" in str(data).lower():
                raise LeaseConflictError(
                    data.get("message", "Lease conflict"),
                    existing_lease=data.get("existing_lease"),
                    status_code=409,
                    response=data,
                )
            raise ConflictError(
                data.get("message", "Version conflict"),
                current_version=data.get("current_version"),
                status_code=409,
                response=data,
            )
        elif response.status_code == 400:
            data = response.json() if response.content else {}
            raise ValidationError(
                data.get("message", "Validation error"),
                errors=data.get("errors", []),
                status_code=400,
                response=data,
            )
        elif response.status_code >= 400:
            raise OpenIntentError(
                f"Request failed with status {response.status_code}",
                status_code=response.status_code,
                response=response.json() if response.content else None,
            )

        return response.json() if response.content else {}

    async def discover(self) -> dict:
        """Discover protocol capabilities."""
        response = await self._client.get("/.well-known/openintent.json")
        return self._handle_response(response)

    async def create_intent(
        self,
        title: str,
        description: str,
        constraints: Optional[list[str]] = None,
        initial_state: Optional[dict[str, Any]] = None,
    ) -> Intent:
        """Create a new intent."""
        payload = {
            "title": title,
            "description": description,
            "constraints": constraints or [],
            "state": initial_state or {},
            "created_by": self.agent_id,
        }
        response = await self._client.post("/api/v1/intents", json=payload)
        data = self._handle_response(response)
        return Intent.from_dict(data)

    async def get_intent(self, intent_id: str) -> Intent:
        """Retrieve an intent by ID."""
        response = await self._client.get(f"/api/v1/intents/{intent_id}")
        data = self._handle_response(response)
        return Intent.from_dict(data)

    async def list_intents(
        self,
        status: Optional[IntentStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Intent]:
        """List intents with optional filtering."""
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status.value

        response = await self._client.get("/api/v1/intents", params=params)
        data = self._handle_response(response)
        return [Intent.from_dict(item) for item in data.get("intents", data)]

    async def update_state(
        self,
        intent_id: str,
        version: int,
        state_patch: dict[str, Any],
    ) -> Intent:
        """Update intent state with optimistic concurrency control."""
        # Convert state dict to RFC-compliant JSON Patch format
        patches = [{"op": "set", "path": k, "value": v} for k, v in state_patch.items()]
        response = await self._client.post(
            f"/api/v1/intents/{intent_id}/state",
            json={"patches": patches},
            headers={"If-Match": str(version)},
        )
        data = self._handle_response(response)
        return Intent.from_dict(data)

    async def set_status(
        self,
        intent_id: str,
        version: int,
        status: IntentStatus,
    ) -> Intent:
        """Change intent status."""
        response = await self._client.post(
            f"/api/v1/intents/{intent_id}/status",
            json={"status": status.value},
            headers={"If-Match": str(version)},
        )
        data = self._handle_response(response)
        return Intent.from_dict(data)

    async def log_event(
        self,
        intent_id: str,
        event_type: EventType,
        payload: Optional[dict[str, Any]] = None,
    ) -> IntentEvent:
        """Append an event to the intent's audit log."""
        response = await self._client.post(
            f"/api/v1/intents/{intent_id}/events",
            json={
                "event_type": event_type.value,
                "actor": self.agent_id,
                "payload": payload or {},
            },
        )
        data = self._handle_response(response)
        return IntentEvent.from_dict(data)

    async def get_events(
        self,
        intent_id: str,
        event_type: Optional[EventType] = None,
        since: Optional[datetime] = None,
        limit: int = 100,
    ) -> list[IntentEvent]:
        """Retrieve events from the intent's audit log."""
        params: dict[str, Any] = {"limit": limit}
        if event_type:
            params["event_type"] = event_type.value
        if since:
            params["since"] = since.isoformat()

        response = await self._client.get(
            f"/api/v1/intents/{intent_id}/events",
            params=params,
        )
        data = self._handle_response(response)
        # Handle both list response and dict with "events" key
        events = data if isinstance(data, list) else data.get("events", [])
        return [IntentEvent.from_dict(item) for item in events]

    async def acquire_lease(
        self,
        intent_id: str,
        scope: str,
        duration_seconds: int = 300,
    ) -> IntentLease:
        """Acquire a lease for exclusive access to a scope."""
        response = await self._client.post(
            f"/api/v1/intents/{intent_id}/leases",
            json={
                "scope": scope,
                "duration_seconds": duration_seconds,
            },
        )
        data = self._handle_response(response)
        return IntentLease.from_dict(data)

    async def release_lease(self, intent_id: str, lease_id: str) -> None:
        """Release a previously acquired lease."""
        response = await self._client.delete(
            f"/api/v1/intents/{intent_id}/leases/{lease_id}"
        )
        self._handle_response(response)

    async def get_leases(self, intent_id: str) -> list[IntentLease]:
        """List all active leases for an intent."""
        response = await self._client.get(f"/api/v1/intents/{intent_id}/leases")
        data = self._handle_response(response)
        return [IntentLease.from_dict(item) for item in data.get("leases", data)]

    async def request_arbitration(
        self,
        intent_id: str,
        reason: str,
        context: Optional[dict[str, Any]] = None,
    ) -> ArbitrationRequest:
        """Request human arbitration for a conflict or decision."""
        response = await self._client.post(
            f"/api/v1/intents/{intent_id}/arbitrate",
            json={
                "reason": reason,
                "context": context or {},
            },
        )
        data = self._handle_response(response)
        return ArbitrationRequest.from_dict(data)

    async def record_decision(
        self,
        intent_id: str,
        decision_type: str,
        outcome: str,
        reasoning: str,
    ) -> Decision:
        """Record a governance decision."""
        response = await self._client.post(
            f"/api/v1/intents/{intent_id}/decisions",
            json={
                "decision_type": decision_type,
                "outcome": outcome,
                "reasoning": reasoning,
            },
        )
        data = self._handle_response(response)
        return Decision.from_dict(data)

    async def get_decisions(self, intent_id: str) -> list[Decision]:
        """Retrieve all decisions for an intent."""
        response = await self._client.get(f"/api/v1/intents/{intent_id}/decisions")
        data = self._handle_response(response)
        return [Decision.from_dict(item) for item in data.get("decisions", data)]

    async def assign_agent(
        self, intent_id: str, agent_id: Optional[str] = None
    ) -> dict:
        """Assign an agent to work on an intent."""
        response = await self._client.post(
            f"/api/v1/intents/{intent_id}/agents",
            json={"agent_id": agent_id or self.agent_id},
        )
        return self._handle_response(response)

    async def unassign_agent(
        self, intent_id: str, agent_id: Optional[str] = None
    ) -> None:
        """Remove an agent from an intent."""
        aid = agent_id or self.agent_id
        response = await self._client.delete(
            f"/api/v1/intents/{intent_id}/agents/{aid}"
        )
        self._handle_response(response)

    async def create_portfolio(
        self,
        name: str,
        description: Optional[str] = None,
        governance_policy: Optional[dict[str, Any]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> IntentPortfolio:
        """Create a new intent portfolio for multi-intent coordination."""
        response = await self._client.post(
            "/api/v1/portfolios",
            json={
                "name": name,
                "description": description,
                "createdBy": self.agent_id,
                "governancePolicy": governance_policy or {},
                "metadata": metadata or {},
            },
        )
        data = self._handle_response(response)
        return IntentPortfolio.from_dict(data)

    async def get_portfolio(self, portfolio_id: str) -> IntentPortfolio:
        """Get a portfolio with its intents and aggregate status."""
        response = await self._client.get(f"/api/v1/portfolios/{portfolio_id}")
        data = self._handle_response(response)
        return IntentPortfolio.from_dict(data)

    async def list_portfolios(
        self, created_by: Optional[str] = None
    ) -> list[IntentPortfolio]:
        """List portfolios, optionally filtered by creator."""
        params = {}
        if created_by:
            params["created_by"] = created_by
        response = await self._client.get("/api/v1/portfolios", params=params)
        data = self._handle_response(response)
        return [IntentPortfolio.from_dict(p) for p in data.get("portfolios", [])]

    async def update_portfolio_status(
        self, portfolio_id: str, status: PortfolioStatus
    ) -> IntentPortfolio:
        """Update portfolio status."""
        response = await self._client.patch(
            f"/api/v1/portfolios/{portfolio_id}/status",
            json={"status": status.value},
        )
        data = self._handle_response(response)
        return IntentPortfolio.from_dict(data)

    async def add_intent_to_portfolio(
        self,
        portfolio_id: str,
        intent_id: str,
        role: MembershipRole = MembershipRole.MEMBER,
        priority: int = 0,
    ) -> PortfolioMembership:
        """Add an intent to a portfolio."""
        response = await self._client.post(
            f"/api/v1/portfolios/{portfolio_id}/intents",
            json={
                "intent_id": intent_id,
                "role": role.value,
                "priority": priority,
            },
        )
        data = self._handle_response(response)
        return PortfolioMembership.from_dict(data)

    async def remove_intent_from_portfolio(
        self, portfolio_id: str, intent_id: str
    ) -> None:
        """Remove an intent from a portfolio."""
        response = await self._client.delete(
            f"/api/v1/portfolios/{portfolio_id}/intents/{intent_id}"
        )
        if response.status_code != 204:
            self._handle_response(response)

    async def get_portfolio_intents(
        self, portfolio_id: str
    ) -> tuple[list[Intent], AggregateStatus]:
        """Get all intents in a portfolio with aggregate status."""
        response = await self._client.get(f"/api/v1/portfolios/{portfolio_id}/intents")
        data = self._handle_response(response)
        intents = [Intent.from_dict(i) for i in data.get("intents", [])]
        agg = AggregateStatus.from_dict(data.get("aggregate_status", {}))
        return intents, agg

    async def get_intent_portfolios(self, intent_id: str) -> list[IntentPortfolio]:
        """Get all portfolios containing an intent."""
        response = await self._client.get(f"/api/v1/intents/{intent_id}/portfolios")
        data = self._handle_response(response)
        return [IntentPortfolio.from_dict(p) for p in data.get("portfolios", [])]

    # ==================== Attachments ====================

    async def add_attachment(
        self,
        intent_id: str,
        filename: str,
        content_type: str,
        url: str,
        size_bytes: int = 0,
    ) -> IntentAttachment:
        """Add an attachment to an intent."""
        response = await self._client.post(
            f"/api/v1/intents/{intent_id}/attachments",
            json={
                "filename": filename,
                "content_type": content_type,
                "url": url,
                "size_bytes": size_bytes,
            },
        )
        data = self._handle_response(response)
        return IntentAttachment.from_dict(data)

    async def get_attachments(self, intent_id: str) -> list[IntentAttachment]:
        """Get all attachments for an intent."""
        response = await self._client.get(f"/api/v1/intents/{intent_id}/attachments")
        data = self._handle_response(response)
        return [IntentAttachment.from_dict(a) for a in data.get("attachments", [])]

    async def delete_attachment(self, intent_id: str, attachment_id: str) -> None:
        """Delete an attachment."""
        response = await self._client.delete(
            f"/api/v1/intents/{intent_id}/attachments/{attachment_id}"
        )
        if response.status_code != 204:
            self._handle_response(response)

    # ==================== Cost Tracking ====================

    async def record_cost(
        self,
        intent_id: str,
        cost_type: str,
        amount: float,
        unit: str,
        provider: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> IntentCost:
        """Record a cost/resource usage for an intent."""
        response = await self._client.post(
            f"/api/v1/intents/{intent_id}/costs",
            json={
                "cost_type": cost_type,
                "amount": amount,
                "unit": unit,
                "provider": provider,
                "metadata": metadata or {},
            },
        )
        data = self._handle_response(response)
        return IntentCost.from_dict(data)

    async def get_costs(self, intent_id: str) -> tuple[list[IntentCost], CostSummary]:
        """Get all costs for an intent with summary."""
        response = await self._client.get(f"/api/v1/intents/{intent_id}/costs")
        data = self._handle_response(response)
        costs = [IntentCost.from_dict(c) for c in data.get("costs", [])]
        summary = CostSummary.from_dict(data.get("summary", {}))
        return costs, summary

    # ==================== Retry Policies ====================

    async def set_retry_policy(
        self,
        intent_id: str,
        strategy: RetryStrategy,
        max_retries: int = 3,
        base_delay_ms: int = 1000,
        max_delay_ms: int = 30000,
        fallback_agent_id: Optional[str] = None,
    ) -> RetryPolicy:
        """Set retry policy for an intent."""
        response = await self._client.put(
            f"/api/v1/intents/{intent_id}/retry-policy",
            json={
                "strategy": strategy.value,
                "max_retries": max_retries,
                "base_delay_ms": base_delay_ms,
                "max_delay_ms": max_delay_ms,
                "fallback_agent_id": fallback_agent_id,
            },
        )
        data = self._handle_response(response)
        return RetryPolicy.from_dict(data)

    async def get_retry_policy(self, intent_id: str) -> Optional[RetryPolicy]:
        """Get retry policy for an intent."""
        response = await self._client.get(f"/api/v1/intents/{intent_id}/retry-policy")
        if response.status_code == 404:
            return None
        data = self._handle_response(response)
        return RetryPolicy.from_dict(data)

    async def record_failure(
        self,
        intent_id: str,
        error_type: str,
        error_message: str,
        recoverable: bool = True,
        metadata: Optional[dict[str, Any]] = None,
    ) -> IntentFailure:
        """Record a failure for an intent."""
        response = await self._client.post(
            f"/api/v1/intents/{intent_id}/failures",
            json={
                "error_type": error_type,
                "error_message": error_message,
                "recoverable": recoverable,
                "metadata": metadata or {},
            },
        )
        data = self._handle_response(response)
        return IntentFailure.from_dict(data)

    async def get_failures(self, intent_id: str) -> list[IntentFailure]:
        """Get all failures for an intent."""
        response = await self._client.get(f"/api/v1/intents/{intent_id}/failures")
        data = self._handle_response(response)
        return [IntentFailure.from_dict(f) for f in data.get("failures", [])]

    # ==================== Subscriptions ====================

    async def subscribe(
        self,
        webhook_url: str,
        event_types: Optional[list[str]] = None,
        intent_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        expires_in_hours: int = 24,
    ) -> IntentSubscription:
        """Subscribe to events for an intent or portfolio."""
        response = await self._client.post(
            "/api/v1/subscriptions",
            json={
                "intent_id": intent_id,
                "portfolio_id": portfolio_id,
                "subscriber_id": self.agent_id,
                "webhook_url": webhook_url,
                "event_types": event_types or [],
                "expires_at": (
                    datetime.now() + timedelta(hours=expires_in_hours)
                ).isoformat(),
            },
        )
        data = self._handle_response(response)
        return IntentSubscription.from_dict(data)

    async def get_subscriptions(
        self,
        intent_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
    ) -> list[IntentSubscription]:
        """Get subscriptions, optionally filtered by intent or portfolio."""
        params = {}
        if intent_id:
            params["intent_id"] = intent_id
        if portfolio_id:
            params["portfolio_id"] = portfolio_id

        response = await self._client.get("/api/v1/subscriptions", params=params)
        data = self._handle_response(response)
        return [IntentSubscription.from_dict(s) for s in data.get("subscriptions", [])]

    async def unsubscribe(self, subscription_id: str) -> None:
        """Unsubscribe from events."""
        response = await self._client.delete(f"/api/v1/subscriptions/{subscription_id}")
        if response.status_code != 204:
            self._handle_response(response)

    # ==================== Lease Renewal ====================

    async def renew_lease(
        self,
        intent_id: str,
        lease_id: str,
        duration_seconds: int = 300,
    ) -> IntentLease:
        """Renew an existing lease to extend its expiration."""
        response = await self._client.patch(
            f"/api/v1/intents/{intent_id}/leases/{lease_id}",
            json={"duration_seconds": duration_seconds},
        )
        data = self._handle_response(response)
        return IntentLease.from_dict(data)

    # ==================== Tool Call Logging ====================

    async def log_tool_call_started(
        self,
        intent_id: str,
        tool_name: str,
        tool_id: str,
        arguments: dict[str, Any],
        provider: Optional[str] = None,
        model: Optional[str] = None,
        parent_request_id: Optional[str] = None,
    ) -> IntentEvent:
        """Log the start of a tool call initiated by an LLM."""
        payload = ToolCallPayload(
            tool_name=tool_name,
            tool_id=tool_id,
            arguments=arguments,
            provider=provider,
            model=model,
            parent_request_id=parent_request_id,
        )
        return await self.log_event(
            intent_id, EventType.TOOL_CALL_STARTED, payload.to_dict()
        )

    async def log_tool_call_completed(
        self,
        intent_id: str,
        tool_name: str,
        tool_id: str,
        arguments: dict[str, Any],
        result: Any,
        duration_ms: Optional[int] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ) -> IntentEvent:
        """Log the successful completion of a tool call."""
        payload = ToolCallPayload(
            tool_name=tool_name,
            tool_id=tool_id,
            arguments=arguments,
            result=result,
            duration_ms=duration_ms,
            provider=provider,
            model=model,
        )
        return await self.log_event(
            intent_id, EventType.TOOL_CALL_COMPLETED, payload.to_dict()
        )

    async def log_tool_call_failed(
        self,
        intent_id: str,
        tool_name: str,
        tool_id: str,
        arguments: dict[str, Any],
        error: str,
        duration_ms: Optional[int] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ) -> IntentEvent:
        """Log a failed tool call."""
        payload = ToolCallPayload(
            tool_name=tool_name,
            tool_id=tool_id,
            arguments=arguments,
            error=error,
            duration_ms=duration_ms,
            provider=provider,
            model=model,
        )
        return await self.log_event(
            intent_id, EventType.TOOL_CALL_FAILED, payload.to_dict()
        )

    # ==================== LLM Request Logging ====================

    async def log_llm_request_started(
        self,
        intent_id: str,
        request_id: str,
        provider: str,
        model: str,
        messages_count: int,
        tools_available: Optional[list[str]] = None,
        stream: bool = False,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> IntentEvent:
        """Log the start of an LLM API request."""
        payload = LLMRequestPayload(
            request_id=request_id,
            provider=provider,
            model=model,
            messages_count=messages_count,
            tools_available=tools_available or [],
            stream=stream,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return await self.log_event(
            intent_id, EventType.LLM_REQUEST_STARTED, payload.to_dict()
        )

    async def log_llm_request_completed(
        self,
        intent_id: str,
        request_id: str,
        provider: str,
        model: str,
        messages_count: int,
        response_content: Optional[str] = None,
        tool_calls: Optional[list[dict[str, Any]]] = None,
        finish_reason: Optional[str] = None,
        prompt_tokens: Optional[int] = None,
        completion_tokens: Optional[int] = None,
        total_tokens: Optional[int] = None,
        duration_ms: Optional[int] = None,
    ) -> IntentEvent:
        """Log the successful completion of an LLM API request."""
        payload = LLMRequestPayload(
            request_id=request_id,
            provider=provider,
            model=model,
            messages_count=messages_count,
            response_content=response_content,
            tool_calls=tool_calls or [],
            finish_reason=finish_reason,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            duration_ms=duration_ms,
        )
        return await self.log_event(
            intent_id, EventType.LLM_REQUEST_COMPLETED, payload.to_dict()
        )

    async def log_llm_request_failed(
        self,
        intent_id: str,
        request_id: str,
        provider: str,
        model: str,
        messages_count: int,
        error: str,
        duration_ms: Optional[int] = None,
    ) -> IntentEvent:
        """Log a failed LLM API request."""
        payload = LLMRequestPayload(
            request_id=request_id,
            provider=provider,
            model=model,
            messages_count=messages_count,
            error=error,
            duration_ms=duration_ms,
        )
        return await self.log_event(
            intent_id, EventType.LLM_REQUEST_FAILED, payload.to_dict()
        )

    # ==================== Stream Coordination ====================

    async def start_stream(
        self,
        intent_id: str,
        stream_id: str,
        provider: str,
        model: str,
    ) -> IntentEvent:
        """Signal the start of a streaming LLM response."""
        payload = StreamState(
            stream_id=stream_id,
            intent_id=intent_id,
            agent_id=self.agent_id,
            status=StreamStatus.ACTIVE,
            provider=provider,
            model=model,
            started_at=datetime.now(),
        )
        return await self.log_event(
            intent_id, EventType.STREAM_STARTED, payload.to_dict()
        )

    async def log_stream_chunk(
        self,
        intent_id: str,
        stream_id: str,
        chunk_index: int,
        token_count: int = 1,
    ) -> IntentEvent:
        """Log a chunk received during streaming (use sparingly)."""
        return await self.log_event(
            intent_id,
            EventType.STREAM_CHUNK,
            {
                "stream_id": stream_id,
                "chunk_index": chunk_index,
                "token_count": token_count,
            },
        )

    async def complete_stream(
        self,
        intent_id: str,
        stream_id: str,
        provider: str,
        model: str,
        chunks_received: int,
        tokens_streamed: int,
    ) -> IntentEvent:
        """Signal successful completion of a stream."""
        payload = StreamState(
            stream_id=stream_id,
            intent_id=intent_id,
            agent_id=self.agent_id,
            status=StreamStatus.COMPLETED,
            provider=provider,
            model=model,
            chunks_received=chunks_received,
            tokens_streamed=tokens_streamed,
            completed_at=datetime.now(),
        )
        return await self.log_event(
            intent_id, EventType.STREAM_COMPLETED, payload.to_dict()
        )

    async def cancel_stream(
        self,
        intent_id: str,
        stream_id: str,
        provider: str,
        model: str,
        reason: Optional[str] = None,
        chunks_received: int = 0,
        tokens_streamed: int = 0,
    ) -> IntentEvent:
        """Signal cancellation of an active stream."""
        payload = StreamState(
            stream_id=stream_id,
            intent_id=intent_id,
            agent_id=self.agent_id,
            status=StreamStatus.CANCELLED,
            provider=provider,
            model=model,
            chunks_received=chunks_received,
            tokens_streamed=tokens_streamed,
            cancelled_at=datetime.now(),
            cancel_reason=reason,
        )
        return await self.log_event(
            intent_id, EventType.STREAM_CANCELLED, payload.to_dict()
        )

    async def close(self) -> None:
        """Close the HTTP client connection."""
        await self._client.aclose()

    async def __aenter__(self) -> "AsyncOpenIntentClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()
