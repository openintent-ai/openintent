"""
OpenIntent Workflow Specification - YAML workflow definitions.

This module enables declarative workflow definitions using YAML,
providing a no-code path to multi-agent coordination.

Example:
    from openintent.workflow import WorkflowSpec

    spec = WorkflowSpec.from_yaml("my_workflow.yaml")
    result = await spec.run()
"""

# mypy: disable-error-code="assignment, return-value"

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional, Union

if TYPE_CHECKING:
    from .agents import PortfolioSpec

try:
    import yaml  # type: ignore[import-untyped]
except ImportError:
    yaml = None  # type: ignore[assignment]


class WorkflowError(Exception):
    """Base exception for workflow errors."""

    pass


class WorkflowValidationError(WorkflowError):
    """Raised when workflow YAML is invalid."""

    def __init__(self, message: str, path: str = "", suggestion: str = ""):
        self.path = path
        self.suggestion = suggestion
        full_message = message
        if path:
            full_message = f"{path}: {message}"
        if suggestion:
            full_message = f"{full_message}\n  Hint: {suggestion}"
        super().__init__(full_message)


class WorkflowNotFoundError(WorkflowError):
    """Raised when workflow file is not found."""

    pass


class PermissionLevel(str, Enum):
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"


class AccessPolicy(str, Enum):
    OPEN = "open"
    RESTRICTED = "restricted"
    PRIVATE = "private"


@dataclass
class AllowEntry:
    """An explicit access grant for an agent."""

    agent: str
    level: PermissionLevel = PermissionLevel.READ
    expires: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AllowEntry:
        return cls(
            agent=data["agent"],
            level=PermissionLevel(data.get("level", "read")),
            expires=data.get("expires"),
        )


@dataclass
class DelegateConfig:
    """Delegation configuration for a phase."""

    to: list[str] = field(default_factory=list)
    level: PermissionLevel = PermissionLevel.READ

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DelegateConfig:
        return cls(
            to=data.get("to", []),
            level=PermissionLevel(data.get("level", "read")),
        )


@dataclass
class PermissionsConfig:
    """Unified permissions configuration for a phase (RFC-0011).

    Supports shorthand forms:
        permissions: "open"              -> open access
        permissions: "private"           -> assigned agent only
        permissions: ["agent-a", "b"]    -> listed agents get write

    And full form:
        permissions:
          policy: restricted
          default: read
          allow: [{ agent: "a", level: "write" }]
          delegate: { to: ["b"], level: "read" }
          context: [dependencies, peers]
    """

    policy: AccessPolicy = AccessPolicy.OPEN
    default: PermissionLevel = PermissionLevel.READ
    allow: list[AllowEntry] = field(default_factory=list)
    delegate: Optional[DelegateConfig] = None
    context: Union[str, list[str]] = "auto"

    @classmethod
    def from_yaml(cls, data: Any) -> PermissionsConfig:
        if data is None:
            return cls()

        if isinstance(data, str):
            if data == "open":
                return cls(policy=AccessPolicy.OPEN)
            elif data == "private":
                return cls(policy=AccessPolicy.PRIVATE)
            else:
                return cls(policy=AccessPolicy(data))

        if isinstance(data, list):
            return cls(
                policy=AccessPolicy.RESTRICTED,
                allow=[AllowEntry(agent=a, level=PermissionLevel.WRITE) for a in data],
            )

        if isinstance(data, dict):
            allow = [AllowEntry.from_dict(e) for e in data.get("allow", [])]
            delegate = None
            if "delegate" in data:
                delegate = DelegateConfig.from_dict(data["delegate"])
            context = data.get("context", "auto")

            return cls(
                policy=AccessPolicy(data.get("policy", "open")),
                default=PermissionLevel(data.get("default", "read")),
                allow=allow,
                delegate=delegate,
                context=context,
            )

        return cls()


@dataclass
class PhaseConfig:
    """Configuration for a workflow phase (intent)."""

    name: str  # Internal name (from YAML key)
    title: str
    assign: str
    description: str = ""
    depends_on: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    initial_state: dict[str, Any] = field(default_factory=dict)

    # RFC-specific configs
    retry: Optional[dict[str, Any]] = None
    leasing: Optional[dict[str, Any]] = None
    cost_tracking: Optional[dict[str, Any]] = None
    attachments: Optional[list[dict[str, Any]]] = None

    # RFC-0011: Unified permissions
    permissions: Optional[PermissionsConfig] = None

    # Inputs/outputs for interpolation
    inputs: dict[str, str] = field(default_factory=dict)
    outputs: list[str] = field(default_factory=list)

    # Conditional
    skip_when: Optional[str] = None


@dataclass
class LLMConfig:
    """LLM provider configuration for the workflow."""

    provider: str = "openai"  # openai, anthropic, or env (auto-detect from env vars)
    model: str = ""  # Empty = use provider default
    temperature: float = 0.7
    max_tokens: int = 4096
    system_prompt: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LLMConfig":
        return cls(
            provider=data.get("provider", "openai"),
            model=data.get("model", ""),
            temperature=data.get("temperature", 0.7),
            max_tokens=data.get("max_tokens", 4096),
            system_prompt=data.get("system_prompt", ""),
        )

    def get_env_key(self) -> str:
        """Get the environment variable key for this provider."""
        provider_keys = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "env": "OPENAI_API_KEY",  # Default fallback
        }
        return provider_keys.get(self.provider, "OPENAI_API_KEY")

    def get_default_model(self) -> str:
        """Get the default model for this provider."""
        if self.model:
            return self.model
        defaults = {
            "openai": "gpt-4o",
            "anthropic": "claude-sonnet-4-20250514",
            "env": "gpt-4o",
        }
        return defaults.get(self.provider, "gpt-4o")


@dataclass
class GovernanceConfig:
    """Governance configuration for the workflow."""

    require_approval: Optional[dict[str, Any]] = None
    max_cost_usd: Optional[float] = None
    timeout_hours: Optional[float] = None
    escalation: Optional[dict[str, str]] = None
    access_review: Optional[dict[str, Any]] = None
    audit_access_events: bool = True


@dataclass
class WorkflowSpec:
    """
    Parsed and validated workflow specification.

    Load from YAML:
        spec = WorkflowSpec.from_yaml("workflow.yaml")

    Convert to PortfolioSpec:
        portfolio = spec.to_portfolio_spec()

    Run directly:
        result = await spec.run(server_url="http://localhost:8000")
    """

    # Metadata
    version: str
    name: str
    description: str = ""
    workflow_version: str = "1.0.0"

    # Agents declaration
    agents: dict[str, dict[str, Any]] = field(default_factory=dict)

    # Workflow phases
    phases: list[PhaseConfig] = field(default_factory=list)

    # Governance
    governance: Optional[GovernanceConfig] = None

    # LLM configuration
    llm: Optional[LLMConfig] = None

    # Types (for validation)
    types: dict[str, Any] = field(default_factory=dict)

    # Source file
    source_path: Optional[Path] = None

    @classmethod
    def from_yaml(cls, path: str | Path) -> "WorkflowSpec":
        """
        Load and validate a workflow from a YAML file.

        Args:
            path: Path to the YAML file

        Returns:
            Validated WorkflowSpec

        Raises:
            WorkflowNotFoundError: File not found
            WorkflowValidationError: Invalid YAML structure
        """
        if yaml is None:
            raise WorkflowError(
                "PyYAML is required for YAML workflows.\n"
                "Install with: pip install pyyaml"
            )

        path = Path(path)
        if not path.exists():
            raise WorkflowNotFoundError(f"Workflow file not found: {path}")

        try:
            with open(path, "r") as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise WorkflowValidationError(
                f"Invalid YAML syntax: {e}",
                suggestion="Check your YAML indentation and syntax",
            )

        if not isinstance(data, dict):
            raise WorkflowValidationError(
                "Workflow must be a YAML object",
                suggestion="Your YAML file should start with 'openintent: \"1.0\"'",
            )

        spec = cls._parse(data, path)
        spec._validate()
        return spec

    @classmethod
    def from_string(
        cls, yaml_content: str, source_name: str = "<string>"
    ) -> "WorkflowSpec":
        """
        Load and validate a workflow from a YAML string.

        Args:
            yaml_content: YAML content as a string
            source_name: Name for error messages

        Returns:
            Validated WorkflowSpec
        """
        if yaml is None:
            raise WorkflowError(
                "PyYAML is required for YAML workflows.\n"
                "Install with: pip install pyyaml"
            )

        try:
            data = yaml.safe_load(yaml_content)
        except yaml.YAMLError as e:
            raise WorkflowValidationError(
                f"Invalid YAML syntax: {e}",
                suggestion="Check your YAML indentation and syntax",
            )

        if not isinstance(data, dict):
            raise WorkflowValidationError(
                "Workflow must be a YAML object",
                suggestion="Your YAML file should start with 'openintent: \"1.0\"'",
            )

        spec = cls._parse(data, Path(source_name))
        spec._validate()
        return spec

    @classmethod
    def _parse(cls, data: dict, source_path: Path) -> "WorkflowSpec":
        """Parse raw YAML data into a WorkflowSpec."""

        # Version check
        version = data.get("openintent")
        if not version:
            raise WorkflowValidationError(
                "Missing 'openintent' version field",
                path="openintent",
                suggestion="Add 'openintent: \"1.0\"' at the top of your file",
            )

        # Info section
        info = data.get("info", {})
        if not isinstance(info, dict):
            raise WorkflowValidationError(
                "'info' must be an object",
                path="info",
                suggestion='info:\n  name: "My Workflow"\n  description: "..."',
            )

        name = info.get("name")
        if not name:
            raise WorkflowValidationError(
                "Missing workflow name",
                path="info.name",
                suggestion="Add 'name: \"My Workflow\"' under 'info:'",
            )

        # Workflow phases
        workflow = data.get("workflow", {})
        if not workflow:
            raise WorkflowValidationError(
                "Missing 'workflow' section",
                path="workflow",
                suggestion="Add a 'workflow:' section with your phases",
            )

        phases = []
        for phase_name, phase_data in workflow.items():
            if not isinstance(phase_data, dict):
                raise WorkflowValidationError(
                    f"Phase '{phase_name}' must be an object",
                    path=f"workflow.{phase_name}",
                )

            # Required fields
            title = phase_data.get("title", phase_name.replace("_", " ").title())
            assign = phase_data.get("assign")

            if not assign:
                raise WorkflowValidationError(
                    f"Phase '{phase_name}' missing 'assign' field",
                    path=f"workflow.{phase_name}.assign",
                    suggestion="Add 'assign: agent-id' to specify which agent handles this phase",
                )

            permissions_data = phase_data.get("permissions")
            if permissions_data is None:
                legacy_access = phase_data.get("access")
                legacy_delegation = phase_data.get("delegation")
                legacy_context = phase_data.get("context")
                if legacy_access or legacy_delegation or legacy_context:
                    merged: dict[str, Any] = {}
                    if legacy_access:
                        merged["policy"] = legacy_access.get("policy", "open")
                        merged["default"] = legacy_access.get("default_permission", "read")
                        acl = legacy_access.get("acl", [])
                        merged["allow"] = [
                            {"agent": e.get("principal_id", e.get("agent", "")), "level": e.get("permission", e.get("level", "read"))}  # noqa: E501
                            for e in acl
                        ]
                    if legacy_delegation:
                        merged["delegate"] = {
                            "to": legacy_delegation.get("targets", legacy_delegation.get("to", [])),  # noqa: E501
                            "level": legacy_delegation.get("default_permission", legacy_delegation.get("level", "read")),  # noqa: E501
                        }
                    if legacy_context:
                        merged["context"] = legacy_context.get("inject", legacy_context) if isinstance(legacy_context, dict) else legacy_context  # noqa: E501
                    permissions_data = merged

            permissions = PermissionsConfig.from_yaml(permissions_data) if permissions_data is not None else None  # noqa: E501

            phase = PhaseConfig(
                name=phase_name,
                title=title,
                assign=assign,
                description=phase_data.get("description", ""),
                depends_on=phase_data.get("depends_on", []),
                constraints=phase_data.get("constraints", []),
                initial_state=phase_data.get("initial_state", {}),
                retry=phase_data.get("retry"),
                leasing=phase_data.get("leasing"),
                cost_tracking=phase_data.get("cost_tracking"),
                attachments=phase_data.get("attachments"),
                permissions=permissions,
                inputs=phase_data.get("inputs", {}),
                outputs=phase_data.get("outputs", []),
                skip_when=phase_data.get("skip_when"),
            )
            phases.append(phase)

        # Governance
        governance = None
        gov_data = data.get("governance")
        if gov_data:
            governance = GovernanceConfig(
                require_approval=gov_data.get("require_approval"),
                max_cost_usd=gov_data.get("max_cost_usd"),
                timeout_hours=gov_data.get("timeout_hours"),
                escalation=gov_data.get("escalation"),
                access_review=gov_data.get("access_review"),
                audit_access_events=gov_data.get("audit_access_events", True),
            )

        # LLM configuration
        llm = None
        llm_data = data.get("llm")
        if llm_data:
            llm = LLMConfig.from_dict(llm_data)

        return cls(
            version=str(version),
            name=name,
            description=info.get("description", ""),
            workflow_version=info.get("version", "1.0.0"),
            agents=data.get("agents", {}),
            phases=phases,
            governance=governance,
            llm=llm,
            types=data.get("types", {}),
            source_path=source_path,
        )

    def _validate(self) -> None:
        """Validate the workflow for consistency."""

        # Check phase dependencies reference valid phases
        phase_names = {p.name for p in self.phases}

        for phase in self.phases:
            for dep in phase.depends_on:
                if dep not in phase_names:
                    # Try matching by title
                    title_match = next(
                        (p.name for p in self.phases if p.title == dep), None
                    )
                    if title_match:
                        # Allow title references
                        continue

                    raise WorkflowValidationError(
                        f"Phase '{phase.name}' depends on unknown phase '{dep}'",
                        path=f"workflow.{phase.name}.depends_on",
                        suggestion=f"Available phases: {', '.join(phase_names)}",
                    )

        # Check for circular dependencies
        self._check_circular_deps()

    def _check_circular_deps(self) -> None:
        """Check for circular dependencies in the workflow."""
        # Build dependency graph
        graph = {p.name: set(p.depends_on) for p in self.phases}

        # Add title aliases
        title_to_name = {p.title: p.name for p in self.phases}
        for phase in self.phases:
            resolved_deps = set()
            for dep in phase.depends_on:
                if dep in graph:
                    resolved_deps.add(dep)
                elif dep in title_to_name:
                    resolved_deps.add(title_to_name[dep])
            graph[phase.name] = resolved_deps

        # DFS for cycles
        visited = set()
        rec_stack = set()

        def dfs(node: str, path: list[str]) -> None:
            visited.add(node)
            rec_stack.add(node)

            for neighbor in graph.get(node, []):
                if neighbor in rec_stack:
                    cycle = " -> ".join(path + [node, neighbor])
                    raise WorkflowValidationError(
                        f"Circular dependency detected: {cycle}",
                        suggestion="Remove one of the dependencies to break the cycle",
                    )
                if neighbor not in visited:
                    dfs(neighbor, path + [node])

            rec_stack.remove(node)

        for phase in self.phases:
            if phase.name not in visited:
                dfs(phase.name, [])

    def to_portfolio_spec(self) -> "PortfolioSpec":
        """
        Convert this workflow to a PortfolioSpec for execution.

        Returns:
            PortfolioSpec ready for execution
        """
        from .agents import IntentSpec, PortfolioSpec

        intents = []
        for phase in self.phases:
            # Build initial state with RFC configs
            initial_state = dict(phase.initial_state)

            if phase.retry:
                initial_state["retry_policy"] = phase.retry

            if phase.leasing:
                initial_state["leasing_config"] = phase.leasing

            if phase.cost_tracking:
                initial_state["cost_tracking"] = phase.cost_tracking

            if phase.permissions:
                perm = phase.permissions
                perm_state: dict[str, Any] = {"policy": perm.policy.value, "default": perm.default.value}  # noqa: E501
                if perm.allow:
                    perm_state["allow"] = [{"agent": e.agent, "level": e.level.value} for e in perm.allow]  # noqa: E501
                if perm.delegate:
                    perm_state["delegate"] = {"to": perm.delegate.to, "level": perm.delegate.level.value}  # noqa: E501
                if perm.context != "auto":
                    perm_state["context"] = perm.context
                initial_state["permissions"] = perm_state

            # Resolve depends_on to titles (PortfolioSpec uses titles)
            title_to_name = {p.name: p.title for p in self.phases}
            depends_on = []
            for dep in phase.depends_on:
                if dep in title_to_name:
                    depends_on.append(title_to_name[dep])
                else:
                    # Assume it's already a title
                    depends_on.append(dep)

            intent = IntentSpec(
                title=phase.title,
                description=phase.description,
                assign=phase.assign,
                depends_on=depends_on,
                constraints=phase.constraints,
                initial_state=initial_state,
            )
            intents.append(intent)

        # Build governance policy
        governance_policy = {}
        if self.governance:
            if self.governance.max_cost_usd:
                governance_policy["max_cost_usd"] = self.governance.max_cost_usd
            if self.governance.timeout_hours:
                governance_policy["timeout_hours"] = self.governance.timeout_hours
            if self.governance.require_approval:
                governance_policy["require_approval"] = self.governance.require_approval
            if self.governance.escalation:
                governance_policy["escalation"] = self.governance.escalation
            if self.governance.access_review:
                governance_policy["access_review"] = self.governance.access_review
            if self.governance.audit_access_events is not True:
                governance_policy["audit_access_events"] = self.governance.audit_access_events

        return PortfolioSpec(
            name=self.name,
            description=self.description,
            governance_policy=governance_policy or {},
            intents=intents,
        )

    async def run(
        self,
        server_url: str = "http://localhost:8000",
        api_key: str = "dev-user-key",
        timeout: int = 300,
        verbose: bool = True,
    ) -> dict:
        """
        Execute this workflow against an OpenIntent server.

        Args:
            server_url: OpenIntent server URL
            api_key: API key for authentication
            timeout: Execution timeout in seconds
            verbose: Print progress messages

        Returns:
            Workflow execution result
        """
        from .agents import Coordinator

        if verbose:
            print(f"Running workflow: {self.name}")
            print(f"Server: {server_url}")
            print(f"Phases: {len(self.phases)}")
            for i, phase in enumerate(self.phases, 1):
                deps = (
                    f" (after: {', '.join(phase.depends_on)})"
                    if phase.depends_on
                    else ""
                )
                print(f"  {i}. {phase.title} -> {phase.assign}{deps}")
            print()

        # Create coordinator
        coordinator = Coordinator(
            agent_id="workflow-coordinator",
            base_url=server_url,
            api_key=api_key,
        )

        # Execute (timeout is managed internally by Coordinator)
        portfolio_spec = self.to_portfolio_spec()
        result = await coordinator.execute(portfolio_spec)

        if verbose:
            print(f"\nWorkflow complete: {self.name}")

        return result

    def __repr__(self) -> str:
        return f"WorkflowSpec(name={self.name!r}, phases={len(self.phases)})"


def validate_workflow(path: str | Path) -> list[str]:
    """
    Validate a workflow file and return any warnings.

    Args:
        path: Path to workflow YAML

    Returns:
        List of warning messages (empty if valid)

    Raises:
        WorkflowValidationError: If workflow is invalid
    """
    spec = WorkflowSpec.from_yaml(path)

    warnings = []

    # Check for agents without description
    for agent_id, agent_config in spec.agents.items():
        if not agent_config.get("description"):
            warnings.append(f"Agent '{agent_id}' has no description")

    # Check for phases without description
    for phase in spec.phases:
        if not phase.description:
            warnings.append(f"Phase '{phase.name}' has no description")

    return warnings


def list_sample_workflows() -> list[dict[str, str]]:
    """
    List available sample workflows.

    Returns:
        List of workflow info dicts with name, description, path
    """
    samples_dir = Path(__file__).parent.parent / "examples" / "workflows"

    if not samples_dir.exists():
        return []

    workflows = []
    for yaml_file in samples_dir.glob("*.yaml"):
        try:
            spec = WorkflowSpec.from_yaml(yaml_file)
            workflows.append(
                {
                    "name": spec.name,
                    "description": spec.description,
                    "path": str(yaml_file),
                    "phases": len(spec.phases),
                }
            )
        except Exception:
            pass  # Skip invalid files

    return workflows
