"""
Tests for OpenIntent SDK models — RFC 0012-0017.
"""

from datetime import datetime

from openintent.models import (
    AgentCapacity,
    AgentRecord,
    AgentStatus,
    AuthType,
    Checkpoint,
    CheckpointTimeoutAction,
    CoordinatorLease,
    CoordinatorScope,
    CoordinatorStatus,
    CoordinatorType,
    Credential,
    CredentialStatus,
    CredentialVault,
    DecisionRecord,
    DecisionType,
    DeduplicationMode,
    EventType,
    GrantConstraints,
    GrantSource,
    GrantStatus,
    Guardrails,
    GuardrailExceedAction,
    Heartbeat,
    HeartbeatConfig,
    IntentTemplate,
    InvocationStatus,
    MemoryEntry,
    MemoryPolicy,
    MemoryPriority,
    MemoryScope,
    MemorySensitivity,
    MemoryType,
    Plan,
    PlanCondition,
    PlanFailureAction,
    PlanState,
    Task,
    TaskStatus,
    ToolGrant,
    ToolInvocation,
    ToolRequirement,
    Trigger,
    TriggerCondition,
    TriggerLineage,
    TriggerType,
)


class TestRFC0012Enums:
    """Tests for RFC-0012 enum values."""

    def test_task_status_values(self):
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.READY.value == "ready"
        assert TaskStatus.CLAIMED.value == "claimed"
        assert TaskStatus.RUNNING.value == "running"
        assert TaskStatus.BLOCKED.value == "blocked"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.FAILED.value == "failed"
        assert TaskStatus.CANCELLED.value == "cancelled"
        assert TaskStatus.SKIPPED.value == "skipped"

    def test_plan_state_values(self):
        assert PlanState.DRAFT.value == "draft"
        assert PlanState.ACTIVE.value == "active"
        assert PlanState.PAUSED.value == "paused"
        assert PlanState.COMPLETED.value == "completed"
        assert PlanState.FAILED.value == "failed"
        assert PlanState.CANCELLED.value == "cancelled"

    def test_checkpoint_timeout_action_values(self):
        assert CheckpointTimeoutAction.ESCALATE.value == "escalate"
        assert CheckpointTimeoutAction.AUTO_APPROVE.value == "auto_approve"
        assert CheckpointTimeoutAction.FAIL.value == "fail"

    def test_plan_failure_action_values(self):
        assert PlanFailureAction.PAUSE_AND_ESCALATE.value == "pause_and_escalate"
        assert PlanFailureAction.NOTIFY.value == "notify"
        assert PlanFailureAction.FAIL.value == "fail"
        assert PlanFailureAction.RETRY.value == "retry"


class TestRFC0013Enums:
    """Tests for RFC-0013 enum values."""

    def test_coordinator_type_values(self):
        assert CoordinatorType.LLM.value == "llm"
        assert CoordinatorType.HUMAN.value == "human"
        assert CoordinatorType.COMPOSITE.value == "composite"
        assert CoordinatorType.SYSTEM.value == "system"

    def test_coordinator_status_values(self):
        assert CoordinatorStatus.REGISTERING.value == "registering"
        assert CoordinatorStatus.ACTIVE.value == "active"
        assert CoordinatorStatus.PAUSED.value == "paused"
        assert CoordinatorStatus.UNRESPONSIVE.value == "unresponsive"
        assert CoordinatorStatus.FAILED_OVER.value == "failed_over"
        assert CoordinatorStatus.COMPLETING.value == "completing"
        assert CoordinatorStatus.COMPLETED.value == "completed"

    def test_coordinator_scope_values(self):
        assert CoordinatorScope.INTENT.value == "intent"
        assert CoordinatorScope.PORTFOLIO.value == "portfolio"

    def test_decision_type_values(self):
        assert DecisionType.PLAN_CREATED.value == "plan_created"
        assert DecisionType.PLAN_MODIFIED.value == "plan_modified"
        assert DecisionType.TASK_ASSIGNED.value == "task_assigned"
        assert DecisionType.TASK_DELEGATED.value == "task_delegated"
        assert DecisionType.ESCALATION_INITIATED.value == "escalation_initiated"
        assert DecisionType.ESCALATION_RESOLVED.value == "escalation_resolved"
        assert DecisionType.CHECKPOINT_EVALUATED.value == "checkpoint_evaluated"
        assert DecisionType.FAILURE_HANDLED.value == "failure_handled"
        assert DecisionType.GUARDRAIL_APPROACHED.value == "guardrail_approached"
        assert DecisionType.COORDINATOR_HANDOFF.value == "coordinator_handoff"

    def test_guardrail_exceed_action_values(self):
        assert GuardrailExceedAction.PAUSE.value == "pause"
        assert GuardrailExceedAction.ESCALATE.value == "escalate"
        assert GuardrailExceedAction.PAUSE_AND_ESCALATE.value == "pause_and_escalate"
        assert GuardrailExceedAction.FAIL.value == "fail"


class TestRFC0014Enums:
    """Tests for RFC-0014 enum values."""

    def test_auth_type_values(self):
        assert AuthType.API_KEY.value == "api_key"
        assert AuthType.OAUTH2_TOKEN.value == "oauth2_token"
        assert AuthType.BEARER_TOKEN.value == "bearer_token"
        assert AuthType.BASIC_AUTH.value == "basic_auth"
        assert AuthType.CONNECTION_STRING.value == "connection_string"
        assert AuthType.CUSTOM.value == "custom"

    def test_credential_status_values(self):
        assert CredentialStatus.ACTIVE.value == "active"
        assert CredentialStatus.EXPIRED.value == "expired"
        assert CredentialStatus.REVOKED.value == "revoked"

    def test_grant_status_values(self):
        assert GrantStatus.ACTIVE.value == "active"
        assert GrantStatus.EXPIRED.value == "expired"
        assert GrantStatus.REVOKED.value == "revoked"
        assert GrantStatus.SUSPENDED.value == "suspended"

    def test_grant_source_values(self):
        assert GrantSource.DIRECT.value == "direct"
        assert GrantSource.DELEGATED.value == "delegated"

    def test_invocation_status_values(self):
        assert InvocationStatus.SUCCESS.value == "success"
        assert InvocationStatus.DENIED.value == "denied"
        assert InvocationStatus.ERROR.value == "error"


class TestRFC0015Enums:
    """Tests for RFC-0015 enum values."""

    def test_memory_type_values(self):
        assert MemoryType.WORKING.value == "working"
        assert MemoryType.EPISODIC.value == "episodic"
        assert MemoryType.SEMANTIC.value == "semantic"

    def test_memory_priority_values(self):
        assert MemoryPriority.LOW.value == "low"
        assert MemoryPriority.NORMAL.value == "normal"
        assert MemoryPriority.HIGH.value == "high"

    def test_memory_sensitivity_values(self):
        assert MemorySensitivity.PUBLIC.value == "public"
        assert MemorySensitivity.INTERNAL.value == "internal"
        assert MemorySensitivity.CONFIDENTIAL.value == "confidential"
        assert MemorySensitivity.RESTRICTED.value == "restricted"


class TestRFC0016Enums:
    """Tests for RFC-0016 enum values."""

    def test_agent_status_values(self):
        assert AgentStatus.REGISTERING.value == "registering"
        assert AgentStatus.ACTIVE.value == "active"
        assert AgentStatus.DRAINING.value == "draining"
        assert AgentStatus.UNHEALTHY.value == "unhealthy"
        assert AgentStatus.DEAD.value == "dead"
        assert AgentStatus.DEREGISTERED.value == "deregistered"


class TestRFC0017Enums:
    """Tests for RFC-0017 enum values."""

    def test_trigger_type_values(self):
        assert TriggerType.SCHEDULE.value == "schedule"
        assert TriggerType.EVENT.value == "event"
        assert TriggerType.WEBHOOK.value == "webhook"

    def test_deduplication_mode_values(self):
        assert DeduplicationMode.ALLOW.value == "allow"
        assert DeduplicationMode.SKIP.value == "skip"
        assert DeduplicationMode.QUEUE.value == "queue"


class TestNewEventTypes:
    """Tests for new EventType entries from RFC 0012-0017."""

    def test_task_event_types(self):
        assert EventType.TASK_CREATED.value == "task.created"
        assert EventType.TASK_READY.value == "task.ready"
        assert EventType.TASK_CLAIMED.value == "task.claimed"
        assert EventType.TASK_STARTED.value == "task.started"
        assert EventType.TASK_PROGRESS.value == "task.progress"
        assert EventType.TASK_COMPLETED.value == "task.completed"
        assert EventType.TASK_FAILED.value == "task.failed"
        assert EventType.TASK_RETRYING.value == "task.retrying"
        assert EventType.TASK_BLOCKED.value == "task.blocked"
        assert EventType.TASK_UNBLOCKED.value == "task.unblocked"
        assert EventType.TASK_DELEGATED.value == "task.delegated"
        assert EventType.TASK_ESCALATED.value == "task.escalated"
        assert EventType.TASK_CANCELLED.value == "task.cancelled"
        assert EventType.TASK_SKIPPED.value == "task.skipped"

    def test_plan_event_types(self):
        assert EventType.PLAN_CREATED.value == "plan.created"
        assert EventType.PLAN_ACTIVATED.value == "plan.activated"
        assert EventType.PLAN_PAUSED.value == "plan.paused"
        assert EventType.PLAN_RESUMED.value == "plan.resumed"
        assert EventType.PLAN_COMPLETED.value == "plan.completed"
        assert EventType.PLAN_FAILED.value == "plan.failed"
        assert EventType.PLAN_CHECKPOINT_REACHED.value == "plan.checkpoint_reached"
        assert EventType.PLAN_CHECKPOINT_APPROVED.value == "plan.checkpoint_approved"
        assert EventType.PLAN_CHECKPOINT_REJECTED.value == "plan.checkpoint_rejected"

    def test_coordinator_event_types(self):
        assert EventType.COORDINATOR_DECISION.value == "coordinator.decision"
        assert EventType.COORDINATOR_HEARTBEAT.value == "coordinator.heartbeat"
        assert EventType.COORDINATOR_PAUSED.value == "coordinator.paused"
        assert EventType.COORDINATOR_RESUMED.value == "coordinator.resumed"
        assert EventType.COORDINATOR_REPLACED.value == "coordinator.replaced"
        assert EventType.COORDINATOR_UNRESPONSIVE.value == "coordinator.unresponsive"
        assert EventType.COORDINATOR_FAILED_OVER.value == "coordinator.failed_over"
        assert EventType.COORDINATOR_HANDOFF.value == "coordinator.handoff"
        assert EventType.COORDINATOR_PLAN_OVERRIDDEN.value == "coordinator.plan_overridden"
        assert EventType.COORDINATOR_GUARDRAILS_UPDATED.value == "coordinator.guardrails_updated"
        assert EventType.COORDINATOR_STALLED.value == "coordinator.stalled"
        assert EventType.COORDINATOR_ESCALATION_RESOLVED.value == "coordinator.escalation_resolved"

    def test_tool_and_grant_event_types(self):
        assert EventType.TOOL_INVOKED.value == "tool.invoked"
        assert EventType.TOOL_DENIED.value == "tool.denied"
        assert EventType.GRANT_CREATED.value == "grant.created"
        assert EventType.GRANT_DELEGATED.value == "grant.delegated"
        assert EventType.GRANT_REVOKED.value == "grant.revoked"
        assert EventType.GRANT_EXPIRED.value == "grant.expired"
        assert EventType.GRANT_SUSPENDED.value == "grant.suspended"
        assert EventType.GRANT_RESUMED.value == "grant.resumed"
        assert EventType.CREDENTIAL_CREATED.value == "credential.created"
        assert EventType.CREDENTIAL_ROTATED.value == "credential.rotated"
        assert EventType.CREDENTIAL_EXPIRED.value == "credential.expired"
        assert EventType.CREDENTIAL_REVOKED.value == "credential.revoked"

    def test_memory_event_types(self):
        assert EventType.MEMORY_CREATED.value == "memory.created"
        assert EventType.MEMORY_UPDATED.value == "memory.updated"
        assert EventType.MEMORY_DELETED.value == "memory.deleted"
        assert EventType.MEMORY_ARCHIVED.value == "memory.archived"
        assert EventType.MEMORY_EVICTED.value == "memory.evicted"
        assert EventType.MEMORY_EXPIRED.value == "memory.expired"

    def test_agent_lifecycle_event_types(self):
        assert EventType.AGENT_LIFECYCLE.value == "agent.lifecycle"
        assert EventType.AGENT_REGISTERED.value == "agent.registered"
        assert EventType.AGENT_STATUS_CHANGED.value == "agent.status_changed"
        assert EventType.AGENT_DEAD.value == "agent.dead"

    def test_trigger_event_types(self):
        assert EventType.TRIGGER_FIRED.value == "trigger.fired"
        assert EventType.TRIGGER_SKIPPED.value == "trigger.skipped"
        assert EventType.TRIGGER_CASCADE_LIMIT.value == "trigger.cascade_limit"
        assert EventType.TRIGGER_NAMESPACE_BLOCKED.value == "trigger.namespace_blocked"


class TestTask:
    """Tests for Task model (RFC-0012)."""

    def test_create_minimal(self):
        task = Task(id="task-1", intent_id="intent-1", name="Research")
        assert task.id == "task-1"
        assert task.intent_id == "intent-1"
        assert task.name == "Research"
        assert task.status == TaskStatus.PENDING
        assert task.version == 1
        assert task.priority == "normal"
        assert task.input == {}
        assert task.output is None
        assert task.artifacts == []
        assert task.assigned_agent is None
        assert task.lease_id is None
        assert task.capabilities_required == []
        assert task.depends_on == []
        assert task.blocks == []
        assert task.parent_task_id is None
        assert task.plan_id is None
        assert task.retry_policy is None
        assert task.timeout_seconds is None
        assert task.attempt == 1
        assert task.max_attempts == 3
        assert task.permissions == "inherit"
        assert task.memory_policy is None
        assert task.requires_tools == []
        assert task.blocked_reason is None
        assert task.error is None
        assert task.metadata == {}
        assert task.created_at is None

    def test_create_full(self):
        now = datetime.now()
        mp = MemoryPolicy(archive_on_completion=True, inherit_from_parent=True)
        tr = ToolRequirement(service="github", scopes=["read"], required=True)
        task = Task(
            id="task-2",
            intent_id="intent-2",
            name="Deploy",
            version=2,
            status=TaskStatus.RUNNING,
            plan_id="plan-1",
            description="Deploy the app",
            priority="high",
            input={"env": "production"},
            output={"url": "https://example.com"},
            artifacts=["build.zip"],
            assigned_agent="agent-1",
            lease_id="lease-1",
            capabilities_required=["deploy"],
            depends_on=["task-1"],
            blocks=["task-3"],
            parent_task_id="task-0",
            retry_policy="exponential",
            timeout_seconds=300,
            attempt=2,
            max_attempts=5,
            permissions="explicit",
            memory_policy=mp,
            requires_tools=[tr],
            blocked_reason=None,
            error=None,
            metadata={"team": "platform"},
            created_at=now,
            started_at=now,
            completed_at=None,
        )
        assert task.status == TaskStatus.RUNNING
        assert task.priority == "high"
        assert task.memory_policy.archive_on_completion is True
        assert len(task.requires_tools) == 1
        assert task.requires_tools[0].service == "github"

    def test_to_dict(self):
        now = datetime.now()
        mp = MemoryPolicy(archive_on_completion=False)
        tr = ToolRequirement(service="slack", scopes=["chat:write"])
        task = Task(
            id="task-3",
            intent_id="intent-3",
            name="Notify",
            version=1,
            status=TaskStatus.COMPLETED,
            description="Send notification",
            assigned_agent="agent-2",
            memory_policy=mp,
            requires_tools=[tr],
            error="timeout",
            created_at=now,
            started_at=now,
            completed_at=now,
        )
        d = task.to_dict()
        assert d["id"] == "task-3"
        assert d["status"] == "completed"
        assert d["description"] == "Send notification"
        assert d["assigned_agent"] == "agent-2"
        assert d["memory_policy"]["archive_on_completion"] is False
        assert d["requires_tools"][0]["service"] == "slack"
        assert d["error"] == "timeout"
        assert d["created_at"] == now.isoformat()
        assert d["started_at"] == now.isoformat()
        assert d["completed_at"] == now.isoformat()

    def test_from_dict_round_trip(self):
        now = datetime.now()
        task = Task(
            id="task-rt",
            intent_id="intent-rt",
            name="Round Trip",
            version=3,
            status=TaskStatus.BLOCKED,
            plan_id="plan-rt",
            description="Testing round trip",
            priority="low",
            input={"data": 42},
            output={"result": "ok"},
            assigned_agent="agent-rt",
            capabilities_required=["cap1"],
            depends_on=["dep1"],
            blocks=["blk1"],
            parent_task_id="parent-1",
            retry_policy="fixed",
            timeout_seconds=60,
            attempt=2,
            max_attempts=4,
            permissions="explicit",
            memory_policy=MemoryPolicy(max_entries=100),
            requires_tools=[ToolRequirement(service="s3", scopes=["read", "write"])],
            blocked_reason="waiting on dep",
            error=None,
            metadata={"key": "val"},
            created_at=now,
            started_at=now,
        )
        d = task.to_dict()
        restored = Task.from_dict(d)
        assert restored.id == task.id
        assert restored.intent_id == task.intent_id
        assert restored.name == task.name
        assert restored.version == task.version
        assert restored.status == task.status
        assert restored.plan_id == task.plan_id
        assert restored.description == task.description
        assert restored.priority == task.priority
        assert restored.input == task.input
        assert restored.output == task.output
        assert restored.assigned_agent == task.assigned_agent
        assert restored.capabilities_required == task.capabilities_required
        assert restored.depends_on == task.depends_on
        assert restored.blocks == task.blocks
        assert restored.parent_task_id == task.parent_task_id
        assert restored.retry_policy == task.retry_policy
        assert restored.timeout_seconds == task.timeout_seconds
        assert restored.attempt == task.attempt
        assert restored.max_attempts == task.max_attempts
        assert restored.permissions == task.permissions
        assert restored.memory_policy.max_entries == 100
        assert restored.requires_tools[0].service == "s3"
        assert restored.blocked_reason == task.blocked_reason
        assert restored.metadata == task.metadata

    def test_from_dict_minimal(self):
        task = Task.from_dict({"id": "t-min"})
        assert task.id == "t-min"
        assert task.intent_id == ""
        assert task.name == ""
        assert task.status == TaskStatus.PENDING
        assert task.version == 1
        assert task.memory_policy is None
        assert task.requires_tools == []


class TestPlan:
    """Tests for Plan model (RFC-0012)."""

    def test_create_minimal(self):
        plan = Plan(id="plan-1", intent_id="intent-1")
        assert plan.id == "plan-1"
        assert plan.intent_id == "intent-1"
        assert plan.version == 1
        assert plan.state == PlanState.DRAFT
        assert plan.tasks == []
        assert plan.checkpoints == []
        assert plan.conditions == []
        assert plan.on_failure == PlanFailureAction.PAUSE_AND_ESCALATE
        assert plan.on_complete == "notify"
        assert plan.metadata == {}

    def test_to_dict(self):
        now = datetime.now()
        cp = Checkpoint(id="cp-1", name="Review", after_task="task-1")
        cond = PlanCondition(id="cond-1", task_id="task-2", when="output.score > 0.8")
        plan = Plan(
            id="plan-2",
            intent_id="intent-2",
            version=2,
            state=PlanState.ACTIVE,
            tasks=["task-1", "task-2"],
            checkpoints=[cp],
            conditions=[cond],
            on_failure=PlanFailureAction.NOTIFY,
            on_complete="archive",
            metadata={"source": "auto"},
            created_at=now,
            updated_at=now,
        )
        d = plan.to_dict()
        assert d["id"] == "plan-2"
        assert d["state"] == "active"
        assert d["tasks"] == ["task-1", "task-2"]
        assert len(d["checkpoints"]) == 1
        assert d["checkpoints"][0]["name"] == "Review"
        assert len(d["conditions"]) == 1
        assert d["on_failure"] == "notify"
        assert d["on_complete"] == "archive"
        assert d["created_at"] == now.isoformat()
        assert d["updated_at"] == now.isoformat()

    def test_from_dict_round_trip(self):
        now = datetime.now()
        plan = Plan(
            id="plan-rt",
            intent_id="intent-rt",
            version=3,
            state=PlanState.COMPLETED,
            tasks=["t1", "t2"],
            checkpoints=[Checkpoint(id="cp-rt", name="Gate", after_task="t1")],
            conditions=[PlanCondition(id="c-rt", task_id="t2", when="true")],
            on_failure=PlanFailureAction.FAIL,
            on_complete="close",
            metadata={"k": "v"},
            created_at=now,
            updated_at=now,
        )
        d = plan.to_dict()
        restored = Plan.from_dict(d)
        assert restored.id == plan.id
        assert restored.state == plan.state
        assert restored.tasks == plan.tasks
        assert len(restored.checkpoints) == 1
        assert restored.checkpoints[0].name == "Gate"
        assert len(restored.conditions) == 1
        assert restored.on_failure == PlanFailureAction.FAIL

    def test_from_dict_minimal(self):
        plan = Plan.from_dict({"id": "p-min"})
        assert plan.id == "p-min"
        assert plan.state == PlanState.DRAFT
        assert plan.tasks == []


class TestCheckpoint:
    """Tests for Checkpoint model (RFC-0012)."""

    def test_create_minimal(self):
        cp = Checkpoint(id="cp-1", name="Review Gate", after_task="task-1")
        assert cp.id == "cp-1"
        assert cp.name == "Review Gate"
        assert cp.after_task == "task-1"
        assert cp.requires_approval is True
        assert cp.approvers == []
        assert cp.timeout_hours is None
        assert cp.on_timeout == CheckpointTimeoutAction.ESCALATE
        assert cp.status == "pending"

    def test_to_dict(self):
        now = datetime.now()
        cp = Checkpoint(
            id="cp-2",
            name="Final Check",
            after_task="task-5",
            requires_approval=True,
            approvers=["admin-1"],
            timeout_hours=48,
            on_timeout=CheckpointTimeoutAction.AUTO_APPROVE,
            status="approved",
            approved_by="admin-1",
            approved_at=now,
        )
        d = cp.to_dict()
        assert d["id"] == "cp-2"
        assert d["name"] == "Final Check"
        assert d["after_task"] == "task-5"
        assert d["requires_approval"] is True
        assert d["approvers"] == ["admin-1"]
        assert d["timeout_hours"] == 48
        assert d["on_timeout"] == "auto_approve"
        assert d["status"] == "approved"
        assert d["approved_by"] == "admin-1"
        assert d["approved_at"] == now.isoformat()

    def test_from_dict_round_trip(self):
        now = datetime.now()
        cp = Checkpoint(
            id="cp-rt",
            name="Gate",
            after_task="t-1",
            timeout_hours=24,
            on_timeout=CheckpointTimeoutAction.FAIL,
            approved_by="user-1",
            approved_at=now,
        )
        d = cp.to_dict()
        restored = Checkpoint.from_dict(d)
        assert restored.id == cp.id
        assert restored.name == cp.name
        assert restored.after_task == cp.after_task
        assert restored.timeout_hours == 24
        assert restored.on_timeout == CheckpointTimeoutAction.FAIL

    def test_from_dict_minimal(self):
        cp = Checkpoint.from_dict({})
        assert cp.id == ""
        assert cp.name == ""
        assert cp.after_task == ""
        assert cp.on_timeout == CheckpointTimeoutAction.ESCALATE


class TestPlanCondition:
    """Tests for PlanCondition model (RFC-0012)."""

    def test_create(self):
        cond = PlanCondition(id="cond-1", task_id="t-1", when="output.ok == true")
        assert cond.id == "cond-1"
        assert cond.task_id == "t-1"
        assert cond.when == "output.ok == true"
        assert cond.otherwise == "skip"

    def test_to_dict(self):
        cond = PlanCondition(id="c-1", task_id="t-2", when="score > 0.5", otherwise="fail")
        d = cond.to_dict()
        assert d["id"] == "c-1"
        assert d["task_id"] == "t-2"
        assert d["when"] == "score > 0.5"
        assert d["otherwise"] == "fail"

    def test_from_dict_round_trip(self):
        cond = PlanCondition(id="c-rt", task_id="t-rt", when="x > 1", otherwise="retry")
        d = cond.to_dict()
        restored = PlanCondition.from_dict(d)
        assert restored.id == cond.id
        assert restored.task_id == cond.task_id
        assert restored.when == cond.when
        assert restored.otherwise == cond.otherwise

    def test_from_dict_minimal(self):
        cond = PlanCondition.from_dict({})
        assert cond.id == ""
        assert cond.task_id == ""
        assert cond.when == ""
        assert cond.otherwise == "skip"


class TestMemoryPolicy:
    """Tests for MemoryPolicy model (RFC-0012/0015)."""

    def test_create_defaults(self):
        mp = MemoryPolicy()
        assert mp.archive_on_completion is True
        assert mp.inherit_from_parent is False
        assert mp.max_entries is None
        assert mp.max_total_size_kb is None

    def test_to_dict(self):
        mp = MemoryPolicy(
            archive_on_completion=False,
            inherit_from_parent=True,
            max_entries=50,
            max_total_size_kb=1024,
        )
        d = mp.to_dict()
        assert d["archive_on_completion"] is False
        assert d["inherit_from_parent"] is True
        assert d["max_entries"] == 50
        assert d["max_total_size_kb"] == 1024

    def test_to_dict_minimal(self):
        mp = MemoryPolicy()
        d = mp.to_dict()
        assert d["archive_on_completion"] is True
        assert d["inherit_from_parent"] is False
        assert "max_entries" not in d
        assert "max_total_size_kb" not in d

    def test_from_dict_round_trip(self):
        mp = MemoryPolicy(max_entries=200, max_total_size_kb=2048)
        d = mp.to_dict()
        restored = MemoryPolicy.from_dict(d)
        assert restored.archive_on_completion == mp.archive_on_completion
        assert restored.max_entries == mp.max_entries
        assert restored.max_total_size_kb == mp.max_total_size_kb

    def test_from_dict_minimal(self):
        mp = MemoryPolicy.from_dict({})
        assert mp.archive_on_completion is True
        assert mp.inherit_from_parent is False


class TestToolRequirement:
    """Tests for ToolRequirement model (RFC-0012/0014)."""

    def test_create_minimal(self):
        tr = ToolRequirement(service="github")
        assert tr.service == "github"
        assert tr.scopes == []
        assert tr.required is True

    def test_to_dict(self):
        tr = ToolRequirement(service="slack", scopes=["chat:write", "chat:read"], required=False)
        d = tr.to_dict()
        assert d["service"] == "slack"
        assert d["scopes"] == ["chat:write", "chat:read"]
        assert d["required"] is False

    def test_from_dict_round_trip(self):
        tr = ToolRequirement(service="aws-s3", scopes=["s3:GetObject"], required=True)
        d = tr.to_dict()
        restored = ToolRequirement.from_dict(d)
        assert restored.service == tr.service
        assert restored.scopes == tr.scopes
        assert restored.required == tr.required

    def test_from_dict_minimal(self):
        tr = ToolRequirement.from_dict({"service": "redis"})
        assert tr.service == "redis"
        assert tr.scopes == []
        assert tr.required is True


class TestGuardrails:
    """Tests for Guardrails model (RFC-0013)."""

    def test_create_defaults(self):
        g = Guardrails()
        assert g.max_budget_usd is None
        assert g.warn_at_percentage == 80
        assert g.on_exceed == GuardrailExceedAction.PAUSE_AND_ESCALATE
        assert g.max_tasks_per_plan == 20
        assert g.max_delegation_depth == 3
        assert g.max_concurrent_tasks == 10
        assert g.max_plan_versions == 5
        assert g.allowed_capabilities is None
        assert g.max_plan_duration_hours is None
        assert g.checkpoint_timeout_hours == 24
        assert g.requires_plan_review is False
        assert g.auto_escalate_after_failures == 3
        assert g.memory_archive_required is True

    def test_to_dict(self):
        g = Guardrails(
            max_budget_usd=100.0,
            max_concurrent_tasks=5,
            allowed_capabilities=["deploy", "test"],
            max_plan_duration_hours=72,
            require_progress_every_minutes=30,
        )
        d = g.to_dict()
        assert d["max_budget_usd"] == 100.0
        assert d["max_concurrent_tasks"] == 5
        assert d["allowed_capabilities"] == ["deploy", "test"]
        assert d["max_plan_duration_hours"] == 72
        assert d["require_progress_every_minutes"] == 30
        assert d["on_exceed"] == "pause_and_escalate"

    def test_from_dict_round_trip(self):
        g = Guardrails(
            max_budget_usd=50.0,
            on_exceed=GuardrailExceedAction.FAIL,
            max_tasks_per_plan=10,
            requires_plan_review=True,
            max_working_memory_per_task=500,
        )
        d = g.to_dict()
        restored = Guardrails.from_dict(d)
        assert restored.max_budget_usd == g.max_budget_usd
        assert restored.on_exceed == g.on_exceed
        assert restored.max_tasks_per_plan == g.max_tasks_per_plan
        assert restored.requires_plan_review is True
        assert restored.max_working_memory_per_task == 500

    def test_from_dict_minimal(self):
        g = Guardrails.from_dict({})
        assert g.max_budget_usd is None
        assert g.warn_at_percentage == 80
        assert g.max_concurrent_tasks == 10


class TestCoordinatorLease:
    """Tests for CoordinatorLease model (RFC-0013)."""

    def test_create_minimal(self):
        cl = CoordinatorLease(id="cl-1")
        assert cl.id == "cl-1"
        assert cl.intent_id is None
        assert cl.portfolio_id is None
        assert cl.agent_id == ""
        assert cl.role == "coordinator"
        assert cl.supervisor_id is None
        assert cl.coordinator_type == CoordinatorType.LLM
        assert cl.scope == CoordinatorScope.INTENT
        assert cl.status == CoordinatorStatus.ACTIVE
        assert cl.guardrails is None
        assert cl.heartbeat_interval_seconds == 60
        assert cl.version == 1
        assert cl.metadata == {}

    def test_create_full(self):
        now = datetime.now()
        g = Guardrails(max_budget_usd=200.0)
        cl = CoordinatorLease(
            id="cl-2",
            intent_id="intent-1",
            portfolio_id="port-1",
            agent_id="agent-coord",
            role="lead",
            supervisor_id="super-1",
            coordinator_type=CoordinatorType.HUMAN,
            scope=CoordinatorScope.PORTFOLIO,
            status=CoordinatorStatus.PAUSED,
            guardrails=g,
            heartbeat_interval_seconds=30,
            last_heartbeat=now,
            granted_at=now,
            expires_at=now,
            version=3,
            metadata={"region": "us-east"},
        )
        assert cl.coordinator_type == CoordinatorType.HUMAN
        assert cl.scope == CoordinatorScope.PORTFOLIO
        assert cl.guardrails.max_budget_usd == 200.0

    def test_to_dict(self):
        now = datetime.now()
        cl = CoordinatorLease(
            id="cl-3",
            intent_id="i-1",
            agent_id="a-1",
            coordinator_type=CoordinatorType.COMPOSITE,
            status=CoordinatorStatus.COMPLETED,
            granted_at=now,
            expires_at=now,
        )
        d = cl.to_dict()
        assert d["id"] == "cl-3"
        assert d["intent_id"] == "i-1"
        assert d["coordinator_type"] == "composite"
        assert d["status"] == "completed"
        assert d["scope"] == "intent"
        assert d["granted_at"] == now.isoformat()

    def test_from_dict_round_trip(self):
        now = datetime.now()
        cl = CoordinatorLease(
            id="cl-rt",
            intent_id="i-rt",
            agent_id="a-rt",
            role="orchestrator",
            coordinator_type=CoordinatorType.SYSTEM,
            scope=CoordinatorScope.PORTFOLIO,
            status=CoordinatorStatus.UNRESPONSIVE,
            guardrails=Guardrails(max_concurrent_tasks=3),
            heartbeat_interval_seconds=15,
            last_heartbeat=now,
            granted_at=now,
            expires_at=now,
            version=5,
            metadata={"env": "prod"},
        )
        d = cl.to_dict()
        restored = CoordinatorLease.from_dict(d)
        assert restored.id == cl.id
        assert restored.coordinator_type == CoordinatorType.SYSTEM
        assert restored.scope == CoordinatorScope.PORTFOLIO
        assert restored.status == CoordinatorStatus.UNRESPONSIVE
        assert restored.guardrails.max_concurrent_tasks == 3
        assert restored.heartbeat_interval_seconds == 15
        assert restored.version == 5
        assert restored.metadata == {"env": "prod"}

    def test_from_dict_minimal(self):
        cl = CoordinatorLease.from_dict({"id": "cl-min"})
        assert cl.id == "cl-min"
        assert cl.coordinator_type == CoordinatorType.LLM
        assert cl.status == CoordinatorStatus.ACTIVE
        assert cl.guardrails is None


class TestDecisionRecord:
    """Tests for DecisionRecord model (RFC-0013)."""

    def test_create_minimal(self):
        dr = DecisionRecord(
            id="dr-1",
            coordinator_id="coord-1",
            intent_id="intent-1",
            decision_type=DecisionType.PLAN_CREATED,
            summary="Created initial plan",
            rationale="Based on intent requirements",
        )
        assert dr.id == "dr-1"
        assert dr.decision_type == DecisionType.PLAN_CREATED
        assert dr.alternatives_considered == []
        assert dr.confidence is None
        assert dr.timestamp is None

    def test_to_dict(self):
        now = datetime.now()
        dr = DecisionRecord(
            id="dr-2",
            coordinator_id="coord-2",
            intent_id="intent-2",
            decision_type=DecisionType.TASK_ASSIGNED,
            summary="Assigned task to agent-3",
            rationale="Best capability match",
            alternatives_considered=[{"agent": "agent-4", "reason": "lower capacity"}],
            confidence=0.85,
            timestamp=now,
        )
        d = dr.to_dict()
        assert d["id"] == "dr-2"
        assert d["type"] == "coordinator.decision"
        assert d["decision_type"] == "task_assigned"
        assert d["summary"] == "Assigned task to agent-3"
        assert d["confidence"] == 0.85
        assert d["timestamp"] == now.isoformat()
        assert len(d["alternatives_considered"]) == 1

    def test_from_dict_round_trip(self):
        now = datetime.now()
        dr = DecisionRecord(
            id="dr-rt",
            coordinator_id="c-rt",
            intent_id="i-rt",
            decision_type=DecisionType.ESCALATION_INITIATED,
            summary="Escalated due to failure",
            rationale="Max retries exceeded",
            alternatives_considered=[],
            confidence=0.95,
            timestamp=now,
        )
        d = dr.to_dict()
        restored = DecisionRecord.from_dict(d)
        assert restored.id == dr.id
        assert restored.decision_type == DecisionType.ESCALATION_INITIATED
        assert restored.summary == dr.summary
        assert restored.confidence == 0.95

    def test_from_dict_minimal(self):
        dr = DecisionRecord.from_dict({"id": "dr-min"})
        assert dr.id == "dr-min"
        assert dr.decision_type == DecisionType.PLAN_CREATED
        assert dr.summary == ""
        assert dr.confidence is None


class TestCredentialVault:
    """Tests for CredentialVault model (RFC-0014)."""

    def test_create_minimal(self):
        vault = CredentialVault(id="vault-1", owner_id="user-1", name="My Vault")
        assert vault.id == "vault-1"
        assert vault.owner_id == "user-1"
        assert vault.name == "My Vault"
        assert vault.credentials == []
        assert vault.created_at is None

    def test_to_dict(self):
        now = datetime.now()
        vault = CredentialVault(
            id="vault-2",
            owner_id="user-2",
            name="Production",
            credentials=["cred-1", "cred-2"],
            created_at=now,
        )
        d = vault.to_dict()
        assert d["id"] == "vault-2"
        assert d["owner_id"] == "user-2"
        assert d["name"] == "Production"
        assert d["credentials"] == ["cred-1", "cred-2"]
        assert d["created_at"] == now.isoformat()

    def test_from_dict_round_trip(self):
        now = datetime.now()
        vault = CredentialVault(
            id="vault-rt",
            owner_id="user-rt",
            name="Test Vault",
            credentials=["c1"],
            created_at=now,
        )
        d = vault.to_dict()
        restored = CredentialVault.from_dict(d)
        assert restored.id == vault.id
        assert restored.owner_id == vault.owner_id
        assert restored.name == vault.name
        assert restored.credentials == vault.credentials

    def test_from_dict_minimal(self):
        vault = CredentialVault.from_dict({"id": "v-min"})
        assert vault.id == "v-min"
        assert vault.owner_id == ""
        assert vault.name == ""
        assert vault.credentials == []


class TestCredential:
    """Tests for Credential model (RFC-0014)."""

    def test_create_minimal(self):
        cred = Credential(
            id="cred-1",
            vault_id="vault-1",
            service="github",
            label="GitHub Token",
            auth_type=AuthType.BEARER_TOKEN,
        )
        assert cred.id == "cred-1"
        assert cred.auth_type == AuthType.BEARER_TOKEN
        assert cred.scopes_available == []
        assert cred.status == CredentialStatus.ACTIVE
        assert cred.metadata == {}

    def test_to_dict(self):
        now = datetime.now()
        cred = Credential(
            id="cred-2",
            vault_id="vault-2",
            service="aws",
            label="AWS Key",
            auth_type=AuthType.API_KEY,
            scopes_available=["s3:read", "s3:write"],
            status=CredentialStatus.ACTIVE,
            metadata={"region": "us-west-2"},
            created_at=now,
            rotated_at=now,
            expires_at=now,
        )
        d = cred.to_dict()
        assert d["id"] == "cred-2"
        assert d["auth_type"] == "api_key"
        assert d["scopes_available"] == ["s3:read", "s3:write"]
        assert d["status"] == "active"
        assert d["created_at"] == now.isoformat()
        assert d["rotated_at"] == now.isoformat()
        assert d["expires_at"] == now.isoformat()

    def test_from_dict_round_trip(self):
        now = datetime.now()
        cred = Credential(
            id="cred-rt",
            vault_id="v-rt",
            service="stripe",
            label="Stripe Key",
            auth_type=AuthType.API_KEY,
            scopes_available=["charges:read"],
            status=CredentialStatus.EXPIRED,
            metadata={"env": "test"},
            created_at=now,
        )
        d = cred.to_dict()
        restored = Credential.from_dict(d)
        assert restored.id == cred.id
        assert restored.auth_type == AuthType.API_KEY
        assert restored.status == CredentialStatus.EXPIRED
        assert restored.scopes_available == ["charges:read"]

    def test_from_dict_minimal(self):
        cred = Credential.from_dict({"id": "c-min"})
        assert cred.id == "c-min"
        assert cred.auth_type == AuthType.API_KEY
        assert cred.status == CredentialStatus.ACTIVE


class TestGrantConstraints:
    """Tests for GrantConstraints model (RFC-0014)."""

    def test_create_defaults(self):
        gc = GrantConstraints()
        assert gc.max_invocations_per_hour is None
        assert gc.max_cost_per_invocation is None
        assert gc.allowed_parameters is None
        assert gc.denied_parameters is None
        assert gc.ip_allowlist is None

    def test_to_dict(self):
        gc = GrantConstraints(
            max_invocations_per_hour=100,
            max_cost_per_invocation=0.50,
            allowed_parameters={"model": ["gpt-4"]},
            ip_allowlist=["10.0.0.0/8"],
        )
        d = gc.to_dict()
        assert d["max_invocations_per_hour"] == 100
        assert d["max_cost_per_invocation"] == 0.50
        assert d["allowed_parameters"] == {"model": ["gpt-4"]}
        assert d["ip_allowlist"] == ["10.0.0.0/8"]

    def test_to_dict_empty(self):
        gc = GrantConstraints()
        d = gc.to_dict()
        assert d == {}

    def test_from_dict_round_trip(self):
        gc = GrantConstraints(
            max_invocations_per_hour=50,
            denied_parameters={"action": ["delete"]},
        )
        d = gc.to_dict()
        restored = GrantConstraints.from_dict(d)
        assert restored.max_invocations_per_hour == 50
        assert restored.denied_parameters == {"action": ["delete"]}

    def test_from_dict_minimal(self):
        gc = GrantConstraints.from_dict({})
        assert gc.max_invocations_per_hour is None
        assert gc.ip_allowlist is None


class TestToolGrant:
    """Tests for ToolGrant model (RFC-0014)."""

    def test_create_minimal(self):
        tg = ToolGrant(
            id="grant-1",
            credential_id="cred-1",
            agent_id="agent-1",
            granted_by="admin-1",
        )
        assert tg.id == "grant-1"
        assert tg.scopes == []
        assert tg.constraints is None
        assert tg.source == GrantSource.DIRECT
        assert tg.delegatable is False
        assert tg.delegation_depth == 0
        assert tg.delegated_from is None
        assert tg.context == {}
        assert tg.status == GrantStatus.ACTIVE

    def test_to_dict(self):
        now = datetime.now()
        tg = ToolGrant(
            id="grant-2",
            credential_id="cred-2",
            agent_id="agent-2",
            granted_by="admin-2",
            scopes=["read", "write"],
            constraints=GrantConstraints(max_invocations_per_hour=10),
            source=GrantSource.DELEGATED,
            delegatable=True,
            delegation_depth=2,
            delegated_from="grant-1",
            context={"intent_id": "i-1"},
            status=GrantStatus.ACTIVE,
            expires_at=now,
            created_at=now,
            revoked_at=None,
        )
        d = tg.to_dict()
        assert d["id"] == "grant-2"
        assert d["scopes"] == ["read", "write"]
        assert d["source"] == "delegated"
        assert d["delegatable"] is True
        assert d["delegation_depth"] == 2
        assert d["delegated_from"] == "grant-1"
        assert d["constraints"]["max_invocations_per_hour"] == 10
        assert d["status"] == "active"
        assert d["expires_at"] == now.isoformat()

    def test_from_dict_round_trip(self):
        now = datetime.now()
        tg = ToolGrant(
            id="grant-rt",
            credential_id="cred-rt",
            agent_id="agent-rt",
            granted_by="admin-rt",
            scopes=["execute"],
            constraints=GrantConstraints(max_cost_per_invocation=1.0),
            source=GrantSource.DIRECT,
            delegatable=True,
            status=GrantStatus.SUSPENDED,
            created_at=now,
            revoked_at=now,
        )
        d = tg.to_dict()
        restored = ToolGrant.from_dict(d)
        assert restored.id == tg.id
        assert restored.scopes == ["execute"]
        assert restored.constraints.max_cost_per_invocation == 1.0
        assert restored.source == GrantSource.DIRECT
        assert restored.delegatable is True
        assert restored.status == GrantStatus.SUSPENDED

    def test_from_dict_minimal(self):
        tg = ToolGrant.from_dict({"id": "g-min"})
        assert tg.id == "g-min"
        assert tg.source == GrantSource.DIRECT
        assert tg.status == GrantStatus.ACTIVE
        assert tg.constraints is None


class TestToolInvocation:
    """Tests for ToolInvocation model (RFC-0014)."""

    def test_create_minimal(self):
        ti = ToolInvocation(
            invocation_id="inv-1",
            grant_id="grant-1",
            service="github",
            tool="create_issue",
            agent_id="agent-1",
        )
        assert ti.invocation_id == "inv-1"
        assert ti.grant_id == "grant-1"
        assert ti.service == "github"
        assert ti.tool == "create_issue"
        assert ti.parameters == {}
        assert ti.status == InvocationStatus.SUCCESS
        assert ti.result is None
        assert ti.error is None
        assert ti.cost is None
        assert ti.duration_ms is None
        assert ti.idempotency_key is None
        assert ti.context == {}

    def test_to_dict(self):
        now = datetime.now()
        ti = ToolInvocation(
            invocation_id="inv-2",
            grant_id="grant-2",
            service="slack",
            tool="send_message",
            agent_id="agent-2",
            parameters={"channel": "general", "text": "Hello"},
            status=InvocationStatus.SUCCESS,
            result={"ts": "123.456"},
            cost={"amount": 0.001, "currency": "USD"},
            duration_ms=150,
            idempotency_key="idem-123",
            context={"intent_id": "i-2"},
            timestamp=now,
        )
        d = ti.to_dict()
        assert d["invocation_id"] == "inv-2"
        assert d["service"] == "slack"
        assert d["tool"] == "send_message"
        assert d["status"] == "success"
        assert d["result"] == {"ts": "123.456"}
        assert d["cost"]["amount"] == 0.001
        assert d["duration_ms"] == 150
        assert d["idempotency_key"] == "idem-123"
        assert d["timestamp"] == now.isoformat()

    def test_from_dict_round_trip(self):
        now = datetime.now()
        ti = ToolInvocation(
            invocation_id="inv-rt",
            grant_id="g-rt",
            service="aws",
            tool="s3_upload",
            agent_id="a-rt",
            parameters={"bucket": "data"},
            status=InvocationStatus.ERROR,
            error={"code": "AccessDenied", "message": "Forbidden"},
            duration_ms=500,
            timestamp=now,
        )
        d = ti.to_dict()
        restored = ToolInvocation.from_dict(d)
        assert restored.invocation_id == ti.invocation_id
        assert restored.service == "aws"
        assert restored.tool == "s3_upload"
        assert restored.status == InvocationStatus.ERROR
        assert restored.error == {"code": "AccessDenied", "message": "Forbidden"}
        assert restored.duration_ms == 500

    def test_from_dict_minimal(self):
        ti = ToolInvocation.from_dict({})
        assert ti.invocation_id == ""
        assert ti.status == InvocationStatus.SUCCESS
        assert ti.parameters == {}


class TestMemoryScope:
    """Tests for MemoryScope model (RFC-0015)."""

    def test_create_defaults(self):
        ms = MemoryScope()
        assert ms.task_id is None
        assert ms.intent_id is None

    def test_to_dict(self):
        ms = MemoryScope(task_id="task-1", intent_id="intent-1")
        d = ms.to_dict()
        assert d["task_id"] == "task-1"
        assert d["intent_id"] == "intent-1"

    def test_to_dict_empty(self):
        ms = MemoryScope()
        d = ms.to_dict()
        assert d == {}

    def test_from_dict_round_trip(self):
        ms = MemoryScope(task_id="t-1", intent_id="i-1")
        d = ms.to_dict()
        restored = MemoryScope.from_dict(d)
        assert restored.task_id == "t-1"
        assert restored.intent_id == "i-1"

    def test_from_dict_minimal(self):
        ms = MemoryScope.from_dict({})
        assert ms.task_id is None
        assert ms.intent_id is None


class TestMemoryEntry:
    """Tests for MemoryEntry model (RFC-0015)."""

    def test_create_minimal(self):
        me = MemoryEntry(
            id="mem-1",
            agent_id="agent-1",
            namespace="tasks",
            key="current_step",
            value={"step": 3},
            memory_type=MemoryType.WORKING,
        )
        assert me.id == "mem-1"
        assert me.agent_id == "agent-1"
        assert me.namespace == "tasks"
        assert me.key == "current_step"
        assert me.value == {"step": 3}
        assert me.memory_type == MemoryType.WORKING
        assert me.version == 1
        assert me.scope is None
        assert me.tags == []
        assert me.ttl is None
        assert me.pinned is False
        assert me.priority == MemoryPriority.NORMAL
        assert me.sensitivity is None
        assert me.curated_by is None

    def test_to_dict(self):
        now = datetime.now()
        scope = MemoryScope(task_id="t-1", intent_id="i-1")
        me = MemoryEntry(
            id="mem-2",
            agent_id="agent-2",
            namespace="knowledge",
            key="api_docs",
            value={"content": "docs here"},
            memory_type=MemoryType.SEMANTIC,
            version=5,
            scope=scope,
            tags=["important", "api"],
            ttl="P7D",
            pinned=True,
            priority=MemoryPriority.HIGH,
            sensitivity=MemorySensitivity.CONFIDENTIAL,
            curated_by="admin",
            created_at=now,
            updated_at=now,
            expires_at=now,
        )
        d = me.to_dict()
        assert d["id"] == "mem-2"
        assert d["memory_type"] == "semantic"
        assert d["version"] == 5
        assert d["scope"]["task_id"] == "t-1"
        assert d["tags"] == ["important", "api"]
        assert d["ttl"] == "P7D"
        assert d["pinned"] is True
        assert d["priority"] == "high"
        assert d["sensitivity"] == "confidential"
        assert d["curated_by"] == "admin"
        assert d["created_at"] == now.isoformat()
        assert d["updated_at"] == now.isoformat()
        assert d["expires_at"] == now.isoformat()

    def test_from_dict_round_trip(self):
        now = datetime.now()
        me = MemoryEntry(
            id="mem-rt",
            agent_id="a-rt",
            namespace="ns",
            key="k",
            value={"data": True},
            memory_type=MemoryType.EPISODIC,
            version=2,
            scope=MemoryScope(task_id="t-rt"),
            tags=["tag1"],
            ttl="PT1H",
            pinned=True,
            priority=MemoryPriority.LOW,
            sensitivity=MemorySensitivity.INTERNAL,
            curated_by="curator",
            created_at=now,
            updated_at=now,
            expires_at=now,
        )
        d = me.to_dict()
        restored = MemoryEntry.from_dict(d)
        assert restored.id == me.id
        assert restored.memory_type == MemoryType.EPISODIC
        assert restored.version == 2
        assert restored.scope.task_id == "t-rt"
        assert restored.tags == ["tag1"]
        assert restored.ttl == "PT1H"
        assert restored.pinned is True
        assert restored.priority == MemoryPriority.LOW
        assert restored.sensitivity == MemorySensitivity.INTERNAL
        assert restored.curated_by == "curator"

    def test_from_dict_minimal(self):
        me = MemoryEntry.from_dict({"id": "m-min"})
        assert me.id == "m-min"
        assert me.memory_type == MemoryType.WORKING
        assert me.scope is None
        assert me.pinned is False
        assert me.priority == MemoryPriority.NORMAL
        assert me.sensitivity is None


class TestHeartbeatConfig:
    """Tests for HeartbeatConfig model (RFC-0016)."""

    def test_create_defaults(self):
        hc = HeartbeatConfig()
        assert hc.interval_seconds == 30
        assert hc.unhealthy_after_seconds == 90
        assert hc.dead_after_seconds == 300

    def test_to_dict(self):
        hc = HeartbeatConfig(
            interval_seconds=15,
            unhealthy_after_seconds=45,
            dead_after_seconds=120,
        )
        d = hc.to_dict()
        assert d["interval_seconds"] == 15
        assert d["unhealthy_after_seconds"] == 45
        assert d["dead_after_seconds"] == 120

    def test_from_dict_round_trip(self):
        hc = HeartbeatConfig(interval_seconds=10, unhealthy_after_seconds=30, dead_after_seconds=60)
        d = hc.to_dict()
        restored = HeartbeatConfig.from_dict(d)
        assert restored.interval_seconds == 10
        assert restored.unhealthy_after_seconds == 30
        assert restored.dead_after_seconds == 60

    def test_from_dict_minimal(self):
        hc = HeartbeatConfig.from_dict({})
        assert hc.interval_seconds == 30
        assert hc.unhealthy_after_seconds == 90
        assert hc.dead_after_seconds == 300


class TestAgentCapacity:
    """Tests for AgentCapacity model (RFC-0016)."""

    def test_create_defaults(self):
        ac = AgentCapacity()
        assert ac.max_concurrent_tasks == 5
        assert ac.current_load == 0

    def test_to_dict(self):
        ac = AgentCapacity(max_concurrent_tasks=10, current_load=3)
        d = ac.to_dict()
        assert d["max_concurrent_tasks"] == 10
        assert d["current_load"] == 3

    def test_from_dict_round_trip(self):
        ac = AgentCapacity(max_concurrent_tasks=8, current_load=5)
        d = ac.to_dict()
        restored = AgentCapacity.from_dict(d)
        assert restored.max_concurrent_tasks == 8
        assert restored.current_load == 5

    def test_from_dict_minimal(self):
        ac = AgentCapacity.from_dict({})
        assert ac.max_concurrent_tasks == 5
        assert ac.current_load == 0


class TestAgentRecord:
    """Tests for AgentRecord model (RFC-0016)."""

    def test_create_minimal(self):
        ar = AgentRecord(agent_id="agent-1")
        assert ar.agent_id == "agent-1"
        assert ar.status == AgentStatus.ACTIVE
        assert ar.role_id is None
        assert ar.name is None
        assert ar.capabilities == []
        assert ar.capacity is None
        assert ar.endpoint is None
        assert ar.heartbeat_config is None
        assert ar.metadata == {}
        assert ar.registered_at is None
        assert ar.last_heartbeat_at is None
        assert ar.drain_timeout_seconds is None
        assert ar.version == 1

    def test_create_full(self):
        now = datetime.now()
        cap = AgentCapacity(max_concurrent_tasks=3, current_load=1)
        hc = HeartbeatConfig(interval_seconds=10)
        ar = AgentRecord(
            agent_id="agent-2",
            status=AgentStatus.DRAINING,
            role_id="role-worker",
            name="Worker Agent",
            capabilities=["research", "summarize"],
            capacity=cap,
            endpoint="https://agent.example.com",
            heartbeat_config=hc,
            metadata={"version": "2.0"},
            registered_at=now,
            last_heartbeat_at=now,
            drain_timeout_seconds=120,
            version=3,
        )
        assert ar.status == AgentStatus.DRAINING
        assert ar.capacity.max_concurrent_tasks == 3
        assert ar.heartbeat_config.interval_seconds == 10
        assert ar.drain_timeout_seconds == 120

    def test_to_dict(self):
        now = datetime.now()
        ar = AgentRecord(
            agent_id="agent-3",
            status=AgentStatus.UNHEALTHY,
            role_id="role-1",
            name="Test Agent",
            capabilities=["deploy"],
            capacity=AgentCapacity(max_concurrent_tasks=2),
            endpoint="http://localhost:8080",
            heartbeat_config=HeartbeatConfig(interval_seconds=20),
            metadata={"env": "staging"},
            registered_at=now,
            last_heartbeat_at=now,
            drain_timeout_seconds=60,
            version=2,
        )
        d = ar.to_dict()
        assert d["agent_id"] == "agent-3"
        assert d["status"] == "unhealthy"
        assert d["role_id"] == "role-1"
        assert d["name"] == "Test Agent"
        assert d["capabilities"] == ["deploy"]
        assert d["capacity"]["max_concurrent_tasks"] == 2
        assert d["endpoint"] == "http://localhost:8080"
        assert d["heartbeat_config"]["interval_seconds"] == 20
        assert d["registered_at"] == now.isoformat()
        assert d["last_heartbeat_at"] == now.isoformat()
        assert d["drain_timeout_seconds"] == 60
        assert d["version"] == 2

    def test_from_dict_round_trip(self):
        now = datetime.now()
        ar = AgentRecord(
            agent_id="agent-rt",
            status=AgentStatus.DEAD,
            role_id="r-rt",
            name="Round Trip",
            capabilities=["cap1", "cap2"],
            capacity=AgentCapacity(max_concurrent_tasks=4, current_load=2),
            endpoint="https://rt.example.com",
            heartbeat_config=HeartbeatConfig(dead_after_seconds=600),
            metadata={"key": "val"},
            registered_at=now,
            last_heartbeat_at=now,
            drain_timeout_seconds=90,
            version=7,
        )
        d = ar.to_dict()
        restored = AgentRecord.from_dict(d)
        assert restored.agent_id == ar.agent_id
        assert restored.status == AgentStatus.DEAD
        assert restored.role_id == "r-rt"
        assert restored.name == "Round Trip"
        assert restored.capabilities == ["cap1", "cap2"]
        assert restored.capacity.max_concurrent_tasks == 4
        assert restored.capacity.current_load == 2
        assert restored.endpoint == "https://rt.example.com"
        assert restored.heartbeat_config.dead_after_seconds == 600
        assert restored.drain_timeout_seconds == 90
        assert restored.version == 7

    def test_from_dict_minimal(self):
        ar = AgentRecord.from_dict({})
        assert ar.agent_id == ""
        assert ar.status == AgentStatus.ACTIVE
        assert ar.capacity is None
        assert ar.heartbeat_config is None
        assert ar.version == 1


class TestHeartbeat:
    """Tests for Heartbeat model (RFC-0016)."""

    def test_create_minimal(self):
        hb = Heartbeat(agent_id="agent-1")
        assert hb.agent_id == "agent-1"
        assert hb.status == "active"
        assert hb.current_load == 0
        assert hb.tasks_in_progress == []
        assert hb.client_timestamp is None

    def test_to_dict(self):
        now = datetime.now()
        hb = Heartbeat(
            agent_id="agent-2",
            status="active",
            current_load=3,
            tasks_in_progress=["task-1", "task-2", "task-3"],
            client_timestamp=now,
        )
        d = hb.to_dict()
        assert d["agent_id"] == "agent-2"
        assert d["status"] == "active"
        assert d["current_load"] == 3
        assert d["tasks_in_progress"] == ["task-1", "task-2", "task-3"]
        assert d["client_timestamp"] == now.isoformat()

    def test_to_dict_no_timestamp(self):
        hb = Heartbeat(agent_id="agent-3")
        d = hb.to_dict()
        assert "client_timestamp" not in d

    def test_from_dict_round_trip(self):
        now = datetime.now()
        hb = Heartbeat(
            agent_id="agent-rt",
            status="draining",
            current_load=1,
            tasks_in_progress=["t-1"],
            client_timestamp=now,
        )
        d = hb.to_dict()
        restored = Heartbeat.from_dict(d)
        assert restored.agent_id == "agent-rt"
        assert restored.status == "draining"
        assert restored.current_load == 1
        assert restored.tasks_in_progress == ["t-1"]

    def test_from_dict_minimal(self):
        hb = Heartbeat.from_dict({})
        assert hb.agent_id == ""
        assert hb.status == "active"
        assert hb.current_load == 0
        assert hb.tasks_in_progress == []


class TestIntentTemplate:
    """Tests for IntentTemplate model (RFC-0017)."""

    def test_create_minimal(self):
        it = IntentTemplate(type="research", title="Research Task")
        assert it.type == "research"
        assert it.title == "Research Task"
        assert it.priority == "medium"
        assert it.assignee is None
        assert it.context == {}
        assert it.graph_id is None
        assert it.tags == []

    def test_to_dict(self):
        it = IntentTemplate(
            type="deploy",
            title="Deploy App",
            priority="high",
            assignee="agent-1",
            context={"env": "prod"},
            graph_id="graph-1",
            tags=["urgent", "deploy"],
        )
        d = it.to_dict()
        assert d["type"] == "deploy"
        assert d["title"] == "Deploy App"
        assert d["priority"] == "high"
        assert d["assignee"] == "agent-1"
        assert d["context"] == {"env": "prod"}
        assert d["graph_id"] == "graph-1"
        assert d["tags"] == ["urgent", "deploy"]

    def test_from_dict_round_trip(self):
        it = IntentTemplate(
            type="monitor",
            title="Monitor Service",
            priority="low",
            context={"service": "api"},
            tags=["monitoring"],
        )
        d = it.to_dict()
        restored = IntentTemplate.from_dict(d)
        assert restored.type == it.type
        assert restored.title == it.title
        assert restored.priority == it.priority
        assert restored.context == it.context
        assert restored.tags == it.tags

    def test_from_dict_minimal(self):
        it = IntentTemplate.from_dict({})
        assert it.type == ""
        assert it.title == ""
        assert it.priority == "medium"
        assert it.tags == []


class TestTriggerCondition:
    """Tests for TriggerCondition model (RFC-0017)."""

    def test_create_defaults(self):
        tc = TriggerCondition()
        assert tc.cron is None
        assert tc.timezone == "UTC"
        assert tc.starts_at is None
        assert tc.ends_at is None
        assert tc.at is None
        assert tc.event is None
        assert tc.filter is None
        assert tc.path is None
        assert tc.method == "POST"
        assert tc.secret is None
        assert tc.transform is None

    def test_to_dict_schedule(self):
        tc = TriggerCondition(cron="0 9 * * MON", timezone="US/Pacific")
        d = tc.to_dict()
        assert d["cron"] == "0 9 * * MON"
        assert d["timezone"] == "US/Pacific"

    def test_to_dict_event(self):
        tc = TriggerCondition(
            event="task.completed",
            filter={"status": "completed"},
        )
        d = tc.to_dict()
        assert d["event"] == "task.completed"
        assert d["filter"] == {"status": "completed"}

    def test_to_dict_webhook(self):
        tc = TriggerCondition(
            path="/hooks/deploy",
            method="POST",
            transform={"title": "$.body.repo"},
        )
        d = tc.to_dict()
        assert d["path"] == "/hooks/deploy"
        assert d["method"] == "POST"
        assert d["transform"] == {"title": "$.body.repo"}

    def test_from_dict_round_trip(self):
        now = datetime.now()
        tc = TriggerCondition(
            cron="*/5 * * * *",
            timezone="Europe/London",
            starts_at=now,
            ends_at=now,
        )
        d = tc.to_dict()
        restored = TriggerCondition.from_dict(d)
        assert restored.cron == "*/5 * * * *"
        assert restored.timezone == "Europe/London"
        assert restored.starts_at is not None
        assert restored.ends_at is not None

    def test_from_dict_minimal(self):
        tc = TriggerCondition.from_dict({})
        assert tc.cron is None
        assert tc.timezone == "UTC"
        assert tc.method == "POST"


class TestTriggerLineage:
    """Tests for TriggerLineage model (RFC-0017)."""

    def test_create_defaults(self):
        tl = TriggerLineage()
        assert tl.created_by == "trigger"
        assert tl.trigger_id == ""
        assert tl.trigger_type == ""
        assert tl.trigger_depth == 1
        assert tl.trigger_chain == []

    def test_to_dict(self):
        tl = TriggerLineage(
            created_by="trigger",
            trigger_id="trig-1",
            trigger_type="schedule",
            trigger_depth=2,
            trigger_chain=["trig-0", "trig-1"],
        )
        d = tl.to_dict()
        assert d["created_by"] == "trigger"
        assert d["trigger_id"] == "trig-1"
        assert d["trigger_type"] == "schedule"
        assert d["trigger_depth"] == 2
        assert d["trigger_chain"] == ["trig-0", "trig-1"]

    def test_from_dict_round_trip(self):
        tl = TriggerLineage(
            trigger_id="trig-rt",
            trigger_type="event",
            trigger_depth=3,
            trigger_chain=["a", "b", "c"],
        )
        d = tl.to_dict()
        restored = TriggerLineage.from_dict(d)
        assert restored.trigger_id == "trig-rt"
        assert restored.trigger_type == "event"
        assert restored.trigger_depth == 3
        assert restored.trigger_chain == ["a", "b", "c"]

    def test_from_dict_minimal(self):
        tl = TriggerLineage.from_dict({})
        assert tl.created_by == "trigger"
        assert tl.trigger_id == ""
        assert tl.trigger_depth == 1


class TestTrigger:
    """Tests for Trigger model (RFC-0017)."""

    def test_create_minimal(self):
        trig = Trigger(
            trigger_id="trig-1",
            name="Daily Report",
            type=TriggerType.SCHEDULE,
        )
        assert trig.trigger_id == "trig-1"
        assert trig.name == "Daily Report"
        assert trig.type == TriggerType.SCHEDULE
        assert trig.enabled is True
        assert trig.condition is None
        assert trig.intent_template is None
        assert trig.deduplication == DeduplicationMode.ALLOW
        assert trig.namespace is None
        assert trig.fire_count == 0
        assert trig.version == 1

    def test_create_full(self):
        now = datetime.now()
        cond = TriggerCondition(cron="0 8 * * *", timezone="US/Eastern")
        tmpl = IntentTemplate(type="report", title="Daily Summary")
        trig = Trigger(
            trigger_id="trig-2",
            name="Morning Report",
            type=TriggerType.SCHEDULE,
            enabled=True,
            condition=cond,
            intent_template=tmpl,
            deduplication=DeduplicationMode.SKIP,
            namespace="reports",
            fire_count=42,
            version=3,
            created_at=now,
            updated_at=now,
            last_fired_at=now,
        )
        assert trig.condition.cron == "0 8 * * *"
        assert trig.intent_template.title == "Daily Summary"
        assert trig.deduplication == DeduplicationMode.SKIP
        assert trig.fire_count == 42

    def test_to_dict(self):
        now = datetime.now()
        trig = Trigger(
            trigger_id="trig-3",
            name="Event Trigger",
            type=TriggerType.EVENT,
            enabled=False,
            condition=TriggerCondition(event="task.completed"),
            intent_template=IntentTemplate(type="follow_up", title="Follow Up"),
            deduplication=DeduplicationMode.QUEUE,
            namespace="ns-1",
            fire_count=10,
            version=2,
            created_at=now,
            updated_at=now,
            last_fired_at=now,
        )
        d = trig.to_dict()
        assert d["trigger_id"] == "trig-3"
        assert d["name"] == "Event Trigger"
        assert d["type"] == "event"
        assert d["enabled"] is False
        assert d["condition"]["event"] == "task.completed"
        assert d["intent_template"]["type"] == "follow_up"
        assert d["deduplication"] == "queue"
        assert d["namespace"] == "ns-1"
        assert d["fire_count"] == 10
        assert d["version"] == 2
        assert d["created_at"] == now.isoformat()
        assert d["updated_at"] == now.isoformat()
        assert d["last_fired_at"] == now.isoformat()

    def test_from_dict_round_trip(self):
        now = datetime.now()
        trig = Trigger(
            trigger_id="trig-rt",
            name="Webhook Trigger",
            type=TriggerType.WEBHOOK,
            enabled=True,
            condition=TriggerCondition(path="/hooks/build", method="POST"),
            intent_template=IntentTemplate(type="build", title="Build"),
            deduplication=DeduplicationMode.SKIP,
            namespace="ci",
            fire_count=100,
            version=5,
            created_at=now,
            updated_at=now,
            last_fired_at=now,
        )
        d = trig.to_dict()
        restored = Trigger.from_dict(d)
        assert restored.trigger_id == "trig-rt"
        assert restored.type == TriggerType.WEBHOOK
        assert restored.enabled is True
        assert restored.condition.path == "/hooks/build"
        assert restored.intent_template.type == "build"
        assert restored.deduplication == DeduplicationMode.SKIP
        assert restored.namespace == "ci"
        assert restored.fire_count == 100
        assert restored.version == 5

    def test_from_dict_minimal(self):
        trig = Trigger.from_dict({"trigger_id": "trig-min"})
        assert trig.trigger_id == "trig-min"
        assert trig.name == ""
        assert trig.type == TriggerType.SCHEDULE
        assert trig.enabled is True
        assert trig.condition is None
        assert trig.intent_template is None
        assert trig.deduplication == DeduplicationMode.ALLOW
        assert trig.fire_count == 0
