"""
OpenIntent SDK - HTTP client for the OpenIntent Coordination Protocol.

Provides both synchronous and asynchronous clients with full protocol support.
"""

from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any, Optional

import httpx

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
    MembershipRole,
    PortfolioMembership,
    PortfolioStatus,
    RetryPolicy,
    RetryStrategy,
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
        description: str,
        constraints: list[str] = None,
        initial_state: dict[str, Any] = None,
    ) -> Intent:
        """
        Create a new intent.

        Args:
            title: Human-readable title for the intent.
            description: Detailed description of the goal.
            constraints: Optional list of constraints.
            initial_state: Optional initial state data.

        Returns:
            The created Intent object.
        """
        payload = {
            "title": title,
            "description": description,
            "constraints": constraints or [],
            "state": initial_state or {},
        }
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
        status: IntentStatus = None,
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
        params = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status.value

        response = self._client.get("/api/v1/intents", params=params)
        data = self._handle_response(response)
        return [Intent.from_dict(item) for item in data.get("intents", data)]

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
        response = self._client.patch(
            f"/api/v1/intents/{intent_id}/state",
            json={"state": state_patch},
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
        response = self._client.patch(
            f"/api/v1/intents/{intent_id}/state",
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
        payload: dict[str, Any] = None,
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
                "payload": payload or {},
            },
        )
        data = self._handle_response(response)
        return IntentEvent.from_dict(data)

    def get_events(
        self,
        intent_id: str,
        event_type: EventType = None,
        since: datetime = None,
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
        params = {"limit": limit}
        if event_type:
            params["event_type"] = event_type.value
        if since:
            params["since"] = since.isoformat()

        response = self._client.get(
            f"/api/v1/intents/{intent_id}/events",
            params=params,
        )
        data = self._handle_response(response)
        return [IntentEvent.from_dict(item) for item in data.get("events", data)]

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
    def lease(self, intent_id: str, scope: str, duration_seconds: int = 300):
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
        lease = self.acquire_lease(intent_id, scope, duration_seconds)
        try:
            yield lease
        finally:
            try:
                self.release_lease(intent_id, lease.id)
            except Exception:
                pass  # Lease may have expired

    # ==================== Governance ====================

    def request_arbitration(
        self,
        intent_id: str,
        reason: str,
        context: dict[str, Any] = None,
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

    def assign_agent(self, intent_id: str, agent_id: str = None) -> dict:
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

    def unassign_agent(self, intent_id: str, agent_id: str = None) -> None:
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
        description: str = None,
        governance_policy: dict = None,
        metadata: dict = None,
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

    def list_portfolios(self, created_by: str = None) -> list[IntentPortfolio]:
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
        metadata: dict = None,
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
        provider: str = None,
        metadata: dict = None,
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
        fallback_agent_id: str = None,
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
        error_code: str = None,
        error_message: str = None,
        retry_scheduled_at: datetime = None,
        metadata: dict = None,
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
        intent_id: str = None,
        portfolio_id: str = None,
        event_types: list[str] = None,
        webhook_url: str = None,
        expires_at: datetime = None,
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
        self, intent_id: str = None, portfolio_id: str = None
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

    def close(self) -> None:
        """Close the HTTP client connection."""
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
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
        constraints: list[str] = None,
        initial_state: dict[str, Any] = None,
    ) -> Intent:
        """Create a new intent."""
        payload = {
            "title": title,
            "description": description,
            "constraints": constraints or [],
            "state": initial_state or {},
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
        status: IntentStatus = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Intent]:
        """List intents with optional filtering."""
        params = {"limit": limit, "offset": offset}
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
        response = await self._client.patch(
            f"/api/v1/intents/{intent_id}/state",
            json={"state": state_patch},
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
        response = await self._client.patch(
            f"/api/v1/intents/{intent_id}/state",
            json={"status": status.value},
            headers={"If-Match": str(version)},
        )
        data = self._handle_response(response)
        return Intent.from_dict(data)

    async def log_event(
        self,
        intent_id: str,
        event_type: EventType,
        payload: dict[str, Any] = None,
    ) -> IntentEvent:
        """Append an event to the intent's audit log."""
        response = await self._client.post(
            f"/api/v1/intents/{intent_id}/events",
            json={
                "event_type": event_type.value,
                "payload": payload or {},
            },
        )
        data = self._handle_response(response)
        return IntentEvent.from_dict(data)

    async def get_events(
        self,
        intent_id: str,
        event_type: EventType = None,
        since: datetime = None,
        limit: int = 100,
    ) -> list[IntentEvent]:
        """Retrieve events from the intent's audit log."""
        params = {"limit": limit}
        if event_type:
            params["event_type"] = event_type.value
        if since:
            params["since"] = since.isoformat()

        response = await self._client.get(
            f"/api/v1/intents/{intent_id}/events",
            params=params,
        )
        data = self._handle_response(response)
        return [IntentEvent.from_dict(item) for item in data.get("events", data)]

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
        context: dict[str, Any] = None,
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

    async def assign_agent(self, intent_id: str, agent_id: str = None) -> dict:
        """Assign an agent to work on an intent."""
        response = await self._client.post(
            f"/api/v1/intents/{intent_id}/agents",
            json={"agent_id": agent_id or self.agent_id},
        )
        return self._handle_response(response)

    async def unassign_agent(self, intent_id: str, agent_id: str = None) -> None:
        """Remove an agent from an intent."""
        aid = agent_id or self.agent_id
        response = await self._client.delete(
            f"/api/v1/intents/{intent_id}/agents/{aid}"
        )
        self._handle_response(response)

    async def create_portfolio(
        self,
        name: str,
        description: str = None,
        governance_policy: dict = None,
        metadata: dict = None,
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

    async def list_portfolios(self, created_by: str = None) -> list[IntentPortfolio]:
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
        provider: str = None,
        metadata: dict[str, Any] = None,
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
        fallback_agent_id: str = None,
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
        metadata: dict[str, Any] = None,
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
        event_types: list[str] = None,
        intent_id: str = None,
        portfolio_id: str = None,
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
        intent_id: str = None,
        portfolio_id: str = None,
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

    async def close(self) -> None:
        """Close the HTTP client connection."""
        await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()
