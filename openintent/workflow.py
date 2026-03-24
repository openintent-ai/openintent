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


# ---------------------------------------------------------------------------
# RFC-0024: Workflow I/O Contract Errors
# ---------------------------------------------------------------------------


class MissingOutputError(WorkflowError):
    """Raised when a task completion is rejected because one or more declared
    output keys are absent from the agent's returned dict.

    Attributes:
        task_id: The ID of the task whose completion was rejected.
        phase_name: The name of the phase definition.
        missing_keys: The declared output keys that were not returned.
    """

    def __init__(self, task_id: str, phase_name: str, missing_keys: list[str]):
        self.task_id = task_id
        self.phase_name = phase_name
        self.missing_keys = missing_keys
        keys = ", ".join(repr(k) for k in missing_keys)
        super().__init__(
            f"Task completion rejected for task '{task_id}' (phase '{phase_name}'): "
            f"declared output key(s) {keys} were not present in agent return value"
        )


class OutputTypeMismatchError(WorkflowError):
    """Raised when a returned output key's value does not match the declared type.

    No type coercion is performed — the executor validates and rejects only.

    Attributes:
        task_id: The ID of the task whose completion was rejected.
        phase_name: The name of the phase definition.
        key: The output key with the type mismatch.
        expected_type: The type declared in the workflow definition.
        actual_type: The Python type name of the value returned by the agent.
    """

    def __init__(
        self,
        task_id: str,
        phase_name: str,
        key: str,
        expected_type: str,
        actual_type: str,
    ):
        self.task_id = task_id
        self.phase_name = phase_name
        self.key = key
        self.expected_type = expected_type
        self.actual_type = actual_type
        super().__init__(
            f"Task completion rejected for task '{task_id}' (phase '{phase_name}'): "
            f"output key '{key}' expected type '{expected_type}' "
            f"but got '{actual_type}'"
        )


class UnresolvableInputError(WorkflowError):
    """Raised at claim time when one or more declared inputs cannot be resolved
    from completed upstream task outputs.

    Attributes:
        task_id: The ID of the task whose claim was rejected.
        phase_name: The name of the phase definition.
        unresolvable_refs: Input mapping expressions that could not be resolved
            (e.g. ["research.findings"]).
    """

    def __init__(self, task_id: str, phase_name: str, unresolvable_refs: list[str]):
        self.task_id = task_id
        self.phase_name = phase_name
        self.unresolvable_refs = unresolvable_refs
        refs = ", ".join(repr(r) for r in unresolvable_refs)
        super().__init__(
            f"Task claim rejected for task '{task_id}' (phase '{phase_name}'): "
            f"input reference(s) {refs} could not be resolved from upstream outputs"
        )


class InputWiringError(WorkflowValidationError):
    """Raised at workflow validation time when an inputs declaration is
    structurally invalid — e.g. referencing a phase not in depends_on,
    referencing a non-existent phase, or using malformed mapping syntax.

    Attributes:
        phase_name: The phase with the invalid inputs declaration.
        invalid_refs: The malformed or invalid mapping expressions.
    """

    def __init__(self, phase_name: str, invalid_refs: list[str], suggestion: str = ""):
        self.phase_name = phase_name
        self.invalid_refs = invalid_refs
        refs = ", ".join(repr(r) for r in invalid_refs)
        super().__init__(
            f"Phase '{phase_name}' has invalid input wiring: {refs}",
            path=f"workflow.{phase_name}.inputs",
            suggestion=suggestion,
        )


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

    # RFC-0024: I/O contracts
    # inputs: mapping from local key name -> upstream reference
    #   e.g. {"revenue": "fetch_financials.revenue", "q": "$trigger.quarter"}
    # outputs: mapping from output key name -> type declaration
    #   e.g. {"revenue": "number", "findings": "Finding",
    #          "warnings": {"type": "array", "required": False}}
    inputs: dict[str, str] = field(default_factory=dict)
    outputs: dict[str, Any] = field(default_factory=dict)

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
            "openai": "gpt-5.2",
            "anthropic": "claude-sonnet-4-20250514",
            "env": "gpt-5.2",
        }
        return defaults.get(self.provider, "gpt-5.2")


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
class IdentityConfig:
    """Cryptographic identity configuration for YAML workflows (RFC-0018)."""

    enabled: bool = False
    key_path: Optional[str] = None
    auto_register: bool = True
    auto_sign: bool = True
    key_algorithm: str = "Ed25519"
    key_expires: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> IdentityConfig:
        if isinstance(data, bool):
            return cls(enabled=data)
        return cls(
            enabled=data.get("enabled", True),
            key_path=data.get("key_path"),
            auto_register=data.get("auto_register", True),
            auto_sign=data.get("auto_sign", True),
            key_algorithm=data.get("key_algorithm", "Ed25519"),
            key_expires=data.get("key_expires"),
        )


@dataclass
class VerificationConfig:
    """Verifiable event log configuration for YAML workflows (RFC-0019)."""

    enabled: bool = False
    require_signed_events: bool = False
    verify_chain: bool = True
    checkpoint_interval: int = 100
    checkpoint_time_minutes: int = 5
    anchor_provider: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VerificationConfig:
        if isinstance(data, bool):
            return cls(enabled=data)
        return cls(
            enabled=data.get("enabled", True),
            require_signed_events=data.get("require_signed_events", False),
            verify_chain=data.get("verify_chain", True),
            checkpoint_interval=data.get("checkpoint_interval", 100),
            checkpoint_time_minutes=data.get("checkpoint_time_minutes", 5),
            anchor_provider=data.get("anchor_provider"),
        )


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

    # Identity and verification (RFC-0018, RFC-0019)
    identity: Optional[IdentityConfig] = None
    verification: Optional[VerificationConfig] = None

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
                "PyYAML is required for YAML workflows.\nInstall with: pip install pyyaml"
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
                "PyYAML is required for YAML workflows.\nInstall with: pip install pyyaml"
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
                        merged["default"] = legacy_access.get(
                            "default_permission", "read"
                        )
                        acl = legacy_access.get("acl", [])
                        merged["allow"] = [
                            {
                                "agent": e.get("principal_id", e.get("agent", "")),
                                "level": e.get("permission", e.get("level", "read")),
                            }  # noqa: E501
                            for e in acl
                        ]
                    if legacy_delegation:
                        merged["delegate"] = {
                            "to": legacy_delegation.get(
                                "targets", legacy_delegation.get("to", [])
                            ),  # noqa: E501
                            "level": legacy_delegation.get(
                                "default_permission",
                                legacy_delegation.get("level", "read"),
                            ),  # noqa: E501
                        }
                    if legacy_context:
                        merged["context"] = (
                            legacy_context.get("inject", legacy_context)
                            if isinstance(legacy_context, dict)
                            else legacy_context
                        )  # noqa: E501
                    permissions_data = merged

            permissions = (
                PermissionsConfig.from_yaml(permissions_data)
                if permissions_data is not None
                else None
            )  # noqa: E501

            # RFC-0024: outputs may be a legacy list[str] or new dict form.
            # Normalise to dict[str, Any] so the rest of the code is uniform.
            raw_outputs = phase_data.get("outputs", {})
            if isinstance(raw_outputs, list):
                # Legacy form: ["key1", "key2"] -> {"key1": "any", "key2": "any"}
                raw_outputs = {k: "any" for k in raw_outputs}
            elif not isinstance(raw_outputs, dict):
                raw_outputs = {}

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
                outputs=raw_outputs,
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

        # Identity and verification (RFC-0018, RFC-0019)
        identity = None
        if data.get("identity"):
            identity = IdentityConfig.from_dict(data["identity"])
        verification = None
        if data.get("verification"):
            verification = VerificationConfig.from_dict(data["verification"])

        return cls(
            version=str(version),
            name=name,
            description=info.get("description", ""),
            workflow_version=info.get("version", "1.0.0"),
            agents=data.get("agents", {}),
            phases=phases,
            governance=governance,
            llm=llm,
            identity=identity,
            verification=verification,
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

        # RFC-0024: Validate input wiring declarations
        self._validate_io_wiring()

    def _validate_io_wiring(self) -> None:
        """Validate RFC-0024 input/output wiring declarations at parse time.

        Checks performed:
        1. Every phase reference in an input mapping (``phase.key``) names a
           phase that exists in the workflow.
        2. Every such reference names a phase that appears in this phase's
           ``depends_on`` list.
        3. If the referenced upstream phase declares ``outputs``, the key must
           appear there (incremental adoption: skip if upstream has no outputs).
        4. Input mapping syntax is valid (``phase.key``, ``$trigger.key``, or
           ``$initial_state.key``).
        """
        phase_map: dict[str, PhaseConfig] = {p.name: p for p in self.phases}
        # Also build a title -> name map for depends_on that use titles
        title_to_name: dict[str, str] = {p.title: p.name for p in self.phases}

        for phase in self.phases:
            if not phase.inputs:
                continue

            # Resolve depends_on to canonical phase names
            resolved_deps: set[str] = set()
            for dep in phase.depends_on:
                if dep in phase_map:
                    resolved_deps.add(dep)
                elif dep in title_to_name:
                    resolved_deps.add(title_to_name[dep])

            invalid_refs: list[str] = []

            for local_key, mapping_expr in phase.inputs.items():
                if not isinstance(mapping_expr, str):
                    invalid_refs.append(
                        f"{local_key}: {mapping_expr!r} (must be a string)"
                    )
                    continue

                # Static references are valid by definition at parse time
                if mapping_expr.startswith("$trigger.") or mapping_expr.startswith(
                    "$initial_state."
                ):
                    continue

                # Must be "phase_name.key"
                parts = mapping_expr.split(".", 1)
                if len(parts) != 2 or not parts[0] or not parts[1]:
                    invalid_refs.append(
                        f"{local_key}: {mapping_expr!r} "
                        f"(invalid syntax; expected 'phase_name.key' or "
                        f"'$trigger.key' or '$initial_state.key')"
                    )
                    continue

                ref_phase_name, ref_key = parts[0], parts[1]

                # Check phase exists
                if ref_phase_name not in phase_map:
                    invalid_refs.append(
                        f"{local_key}: {mapping_expr!r} "
                        f"(phase '{ref_phase_name}' does not exist)"
                    )
                    continue

                # Check phase is in depends_on
                if ref_phase_name not in resolved_deps:
                    invalid_refs.append(
                        f"{local_key}: {mapping_expr!r} "
                        f"(phase '{ref_phase_name}' is not in depends_on)"
                    )
                    continue

                # Check upstream output key exists if upstream declares outputs
                upstream = phase_map[ref_phase_name]
                if upstream.outputs and ref_key not in upstream.outputs:
                    invalid_refs.append(
                        f"{local_key}: {mapping_expr!r} "
                        f"(upstream phase '{ref_phase_name}' does not declare "
                        f"output key '{ref_key}')"
                    )

            if invalid_refs:
                raise InputWiringError(
                    phase_name=phase.name,
                    invalid_refs=invalid_refs,
                    suggestion=(
                        "Input mappings must use the form 'phase_name.key' "
                        "where phase_name appears in depends_on, or "
                        "'$trigger.key' / '$initial_state.key' for static values."
                    ),
                )

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

            # RFC-0024: persist I/O contract declarations in the intent's
            # initial_state so that the running agent can resolve ctx.input
            # and validate outputs at completion time without needing a
            # direct reference to the WorkflowSpec.
            if phase.inputs:
                initial_state["_io_inputs"] = phase.inputs
            if phase.outputs:
                initial_state["_io_outputs"] = phase.outputs
            # Persist the workflow-level types block so that agent-side
            # _validate_io_outputs can do named-type (struct/enum) checks
            # without needing a reference to the WorkflowSpec at runtime.
            if self.types:
                initial_state["_io_types"] = self.types
            # Store a mapping from dependency title -> phase name so that
            # _build_context can resolve upstream outputs by phase name
            # (as used in input mapping expressions) rather than by title.
            # This is essential because titles and names can differ.
            if phase.depends_on:
                name_to_title = {p.name: p.title for p in self.phases}
                dep_title_to_name: dict[str, str] = {}
                for dep_name in phase.depends_on:
                    dep_title = name_to_title.get(dep_name, dep_name)
                    dep_title_to_name[dep_title] = dep_name
                initial_state["_io_dep_title_to_name"] = dep_title_to_name

            if phase.permissions:
                perm = phase.permissions
                perm_state: dict[str, Any] = {
                    "policy": perm.policy.value,
                    "default": perm.default.value,
                }  # noqa: E501
                if perm.allow:
                    perm_state["allow"] = [
                        {"agent": e.agent, "level": e.level.value} for e in perm.allow
                    ]  # noqa: E501
                if perm.delegate:
                    perm_state["delegate"] = {
                        "to": perm.delegate.to,
                        "level": perm.delegate.level.value,
                    }  # noqa: E501
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
                # RFC-0024: preserve I/O contracts for executor wiring
                inputs=phase.inputs,
                outputs=phase.outputs,
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
                governance_policy["audit_access_events"] = (
                    self.governance.audit_access_events
                )

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

        # Execute with RFC-0024 I/O contract enforcement — pass self so the
        # Coordinator can call validate_claim_inputs/validate_task_outputs.
        portfolio_spec = self.to_portfolio_spec()
        result = await coordinator.execute(portfolio_spec, workflow_spec=self)

        if verbose:
            print(f"\nWorkflow complete: {self.name}")

        return result

    # ------------------------------------------------------------------
    # RFC-0024: Executor I/O wiring helpers
    # ------------------------------------------------------------------

    def resolve_task_inputs(
        self,
        phase_name: str,
        upstream_outputs: dict[str, dict[str, Any]],
        trigger_payload: Optional[dict[str, Any]] = None,
        initial_state: Optional[dict[str, Any]] = None,
        task_id: str = "",
    ) -> dict[str, Any]:
        """Pre-populate ctx.input for a task from its declared inputs mapping.

        This is the executor's pre-handoff step (RFC-0024 §3.2).  Call this
        before dispatching a task to an agent handler.  The returned dict
        should be placed in ``ctx.input``.

        Args:
            phase_name: The name of the phase being started.
            upstream_outputs: Map of ``{phase_name: {key: value}}`` for all
                phases that have already completed.  Keys are canonical phase
                names (not titles).
            trigger_payload: Optional trigger payload for ``$trigger.*`` refs.
            initial_state: Optional initial state for ``$initial_state.*`` refs.
            task_id: Optional task ID for error messages.

        Returns:
            Resolved ``ctx.input`` dict guaranteed to contain all declared
            input keys.

        Raises:
            UnresolvableInputError: If any declared input cannot be resolved.
            KeyError: If ``phase_name`` is not found in this workflow.
        """
        phase = next((p for p in self.phases if p.name == phase_name), None)
        if phase is None:
            raise KeyError(f"Phase '{phase_name}' not found in workflow '{self.name}'")

        if not phase.inputs:
            return {}

        trigger_payload = trigger_payload or {}
        initial_state = initial_state or {}
        resolved: dict[str, Any] = {}
        unresolvable: list[str] = []

        for local_key, mapping_expr in phase.inputs.items():
            if not isinstance(mapping_expr, str):
                unresolvable.append(f"{local_key}: {mapping_expr!r}")
                continue

            if mapping_expr.startswith("$trigger."):
                key = mapping_expr[len("$trigger.") :]
                if key in trigger_payload:
                    resolved[local_key] = trigger_payload[key]
                else:
                    unresolvable.append(mapping_expr)
            elif mapping_expr.startswith("$initial_state."):
                key = mapping_expr[len("$initial_state.") :]
                if key in initial_state:
                    resolved[local_key] = initial_state[key]
                else:
                    unresolvable.append(mapping_expr)
            else:
                parts = mapping_expr.split(".", 1)
                if len(parts) != 2:
                    unresolvable.append(mapping_expr)
                    continue
                ref_phase, ref_key = parts[0], parts[1]
                phase_output = upstream_outputs.get(ref_phase, {})
                if ref_key in phase_output:
                    resolved[local_key] = phase_output[ref_key]
                else:
                    unresolvable.append(mapping_expr)

        if unresolvable:
            raise UnresolvableInputError(
                task_id=task_id,
                phase_name=phase_name,
                unresolvable_refs=unresolvable,
            )

        return resolved

    def validate_claim_inputs(
        self,
        phase_name: str,
        upstream_outputs: dict[str, dict[str, Any]],
        trigger_payload: Optional[dict[str, Any]] = None,
        initial_state: Optional[dict[str, Any]] = None,
        task_id: str = "",
    ) -> None:
        """Validate that all declared inputs are resolvable at claim time.

        This is the executor's claim-time check (RFC-0024 §3.1).  Call this
        when an agent attempts to claim a task.  Raises ``UnresolvableInputError``
        if the claim should be rejected; returns ``None`` if the claim is safe.

        Args:
            phase_name: The name of the phase being claimed.
            upstream_outputs: Map of ``{phase_name: {key: value}}`` for all
                completed upstream phases.
            trigger_payload: Optional trigger payload for ``$trigger.*`` refs.
            initial_state: Optional initial state for ``$initial_state.*`` refs.
            task_id: Optional task ID for error messages.

        Raises:
            UnresolvableInputError: If any declared input cannot be resolved.
        """
        self.resolve_task_inputs(
            phase_name=phase_name,
            upstream_outputs=upstream_outputs,
            trigger_payload=trigger_payload,
            initial_state=initial_state,
            task_id=task_id,
        )

    def validate_task_outputs(
        self,
        phase_name: str,
        agent_output: dict[str, Any],
        task_id: str = "",
    ) -> None:
        """Validate an agent's output dict against the phase's declared outputs.

        This is the executor's completion-time validation (RFC-0024 §3.3).
        Call this when an agent submits a completion result.  Raises a typed
        error if validation fails; returns ``None`` if the output is acceptable.

        Args:
            phase_name: The name of the phase that completed.
            agent_output: The dict returned by the agent handler.
            task_id: Optional task ID for error messages.

        Raises:
            MissingOutputError: If any required declared output key is absent.
            OutputTypeMismatchError: If a value does not match its declared type.
            KeyError: If ``phase_name`` is not found in this workflow.
        """
        phase = next((p for p in self.phases if p.name == phase_name), None)
        if phase is None:
            raise KeyError(f"Phase '{phase_name}' not found in workflow '{self.name}'")

        if not phase.outputs:
            return

        missing: list[str] = []

        for output_key, type_decl in phase.outputs.items():
            # Determine whether this output is required
            required = True
            expected_type: str = "any"

            if isinstance(type_decl, dict):
                required = type_decl.get("required", True)
                expected_type = str(type_decl.get("type", "any"))
            elif isinstance(type_decl, str):
                expected_type = type_decl

            if output_key not in agent_output:
                if required:
                    missing.append(output_key)
                continue

            # Type validation (structural, no coercion)
            value = agent_output[output_key]
            if expected_type not in ("any", ""):
                self._check_value_type(
                    task_id=task_id,
                    phase_name=phase_name,
                    key=output_key,
                    expected_type=expected_type,
                    value=value,
                )

        if missing:
            raise MissingOutputError(
                task_id=task_id,
                phase_name=phase_name,
                missing_keys=missing,
            )

    def _check_value_type(
        self,
        task_id: str,
        phase_name: str,
        key: str,
        expected_type: str,
        value: Any,
    ) -> None:
        """Validate a single output value against a declared type string.

        Primitive type strings are mapped to Python types.  Named types from
        the ``types`` block are validated structurally (top-level key presence).
        Raises ``OutputTypeMismatchError`` on mismatch.
        """
        primitive_type_map: dict[str, type] = {
            "string": str,
            "number": (int, float),  # type: ignore[dict-item]
            "boolean": bool,
            "object": dict,
            "array": list,
        }

        if expected_type in primitive_type_map:
            expected_python_type = primitive_type_map[expected_type]
            if not isinstance(value, expected_python_type):
                raise OutputTypeMismatchError(
                    task_id=task_id,
                    phase_name=phase_name,
                    key=key,
                    expected_type=expected_type,
                    actual_type=type(value).__name__,
                )
            return

        # Named type from the types block — validate structurally
        type_schema = self.types.get(expected_type)
        if type_schema is None:
            # Unknown named type: accept without validation (incremental adoption)
            return

        # Enum type: schema is {"enum": [...]}.  Validate value membership
        # before any isinstance check — enum values are scalars, not dicts.
        if isinstance(type_schema, dict) and "enum" in type_schema:
            enum_values = type_schema["enum"]
            if isinstance(enum_values, list) and value not in enum_values:
                raise OutputTypeMismatchError(
                    task_id=task_id,
                    phase_name=phase_name,
                    key=key,
                    expected_type=f"{expected_type}(enum:{enum_values})",
                    actual_type=repr(value),
                )
            return

        if not isinstance(value, dict):
            raise OutputTypeMismatchError(
                task_id=task_id,
                phase_name=phase_name,
                key=key,
                expected_type=expected_type,
                actual_type=type(value).__name__,
            )

        # Validate that all keys declared in the type schema are present
        if isinstance(type_schema, dict):
            for schema_key in type_schema:
                if schema_key not in value:
                    raise OutputTypeMismatchError(
                        task_id=task_id,
                        phase_name=phase_name,
                        key=key,
                        expected_type=expected_type,
                        actual_type=(f"dict missing required field '{schema_key}'"),
                    )

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
