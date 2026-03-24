"""Tests for RFC-0024: Workflow I/O Contracts.

Covers:
- Error types (MissingOutputError, OutputTypeMismatchError, UnresolvableInputError,
  InputWiringError) — construction, attributes, str representation.
- YAML parsing of ``outputs`` and ``inputs`` on PhaseConfig.
- Parse-time I/O wiring validation (_validate_io_wiring) including invalid
  references, missing depends_on, and unknown upstream output keys.
- resolve_task_inputs — upstream phase refs, $trigger.*, $initial_state.*,
  and UnresolvableInputError when keys are absent.
- validate_task_outputs — MissingOutputError for absent required keys,
  OutputTypeMismatchError for all primitive types and named/enum types,
  optional fields, and no-op when outputs schema is absent.
- validate_claim_inputs — delegates to resolve_task_inputs; raises on
  unresolvable refs.
- _check_value_type — all six primitive types, named struct type (top-level
  key presence), enum type (value membership), unknown named type (accepted).
- Incremental adoption — phases without outputs/inputs are unaffected.
- Package exports — all RFC-0024 symbols exported from openintent top-level.
"""

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_spec(yaml_text: str, tmp_path):
    """Write *yaml_text* to a temp file, parse, and return WorkflowSpec."""
    from openintent.workflow import WorkflowSpec

    f = tmp_path / "wf.yaml"
    f.write_text(yaml_text)
    return WorkflowSpec.from_yaml(str(f))


_BASE = """\
openintent: "1.0"
info:
  name: "IO Test Workflow"
"""


# ---------------------------------------------------------------------------
# Error type construction
# ---------------------------------------------------------------------------


class TestMissingOutputError:
    def test_construction(self):
        from openintent.workflow import MissingOutputError

        e = MissingOutputError(
            task_id="t1", phase_name="fetch", missing_keys=["revenue"]
        )
        assert e.task_id == "t1"
        assert e.phase_name == "fetch"
        assert e.missing_keys == ["revenue"]

    def test_multiple_missing_keys(self):
        from openintent.workflow import MissingOutputError

        e = MissingOutputError(
            task_id="t2", phase_name="analyze", missing_keys=["a", "b", "c"]
        )
        assert len(e.missing_keys) == 3
        assert "b" in e.missing_keys

    def test_is_workflow_error(self):
        from openintent.workflow import MissingOutputError, WorkflowError

        e = MissingOutputError(task_id="", phase_name="p", missing_keys=["x"])
        assert isinstance(e, WorkflowError)

    def test_message_contains_keys(self):
        from openintent.workflow import MissingOutputError

        e = MissingOutputError(task_id="t", phase_name="p", missing_keys=["revenue"])
        assert "revenue" in str(e)

    def test_empty_task_id(self):
        from openintent.workflow import MissingOutputError

        e = MissingOutputError(task_id="", phase_name="p", missing_keys=["k"])
        assert e.task_id == ""

    def test_export_from_package(self):
        import openintent

        assert hasattr(openintent, "MissingOutputError")


class TestOutputTypeMismatchError:
    def test_construction(self):
        from openintent.workflow import OutputTypeMismatchError

        e = OutputTypeMismatchError(
            task_id="t1",
            phase_name="fetch",
            key="revenue",
            expected_type="number",
            actual_type="str",
        )
        assert e.task_id == "t1"
        assert e.phase_name == "fetch"
        assert e.key == "revenue"
        assert e.expected_type == "number"
        assert e.actual_type == "str"

    def test_is_workflow_error(self):
        from openintent.workflow import OutputTypeMismatchError, WorkflowError

        e = OutputTypeMismatchError(
            task_id="",
            phase_name="p",
            key="k",
            expected_type="string",
            actual_type="int",
        )
        assert isinstance(e, WorkflowError)

    def test_message_contains_key_and_types(self):
        from openintent.workflow import OutputTypeMismatchError

        e = OutputTypeMismatchError(
            task_id="",
            phase_name="p",
            key="revenue",
            expected_type="number",
            actual_type="str",
        )
        msg = str(e)
        assert "revenue" in msg

    def test_export_from_package(self):
        import openintent

        assert hasattr(openintent, "OutputTypeMismatchError")


class TestUnresolvableInputError:
    def test_construction(self):
        from openintent.workflow import UnresolvableInputError

        e = UnresolvableInputError(
            task_id="t1",
            phase_name="analyze",
            unresolvable_refs=["fetch.revenue"],
        )
        assert e.task_id == "t1"
        assert e.phase_name == "analyze"
        assert e.unresolvable_refs == ["fetch.revenue"]

    def test_multiple_refs(self):
        from openintent.workflow import UnresolvableInputError

        e = UnresolvableInputError(
            task_id="", phase_name="p", unresolvable_refs=["a.x", "b.y"]
        )
        assert len(e.unresolvable_refs) == 2

    def test_is_workflow_error(self):
        from openintent.workflow import UnresolvableInputError, WorkflowError

        e = UnresolvableInputError(task_id="", phase_name="p", unresolvable_refs=[])
        assert isinstance(e, WorkflowError)

    def test_export_from_package(self):
        import openintent

        assert hasattr(openintent, "UnresolvableInputError")


class TestInputWiringError:
    def test_construction(self):
        from openintent.workflow import InputWiringError

        e = InputWiringError(phase_name="analyze", invalid_refs=["revenue: bad_ref"])
        assert e.phase_name == "analyze"
        assert e.invalid_refs == ["revenue: bad_ref"]

    def test_is_workflow_validation_error(self):
        from openintent.workflow import InputWiringError, WorkflowValidationError

        e = InputWiringError(phase_name="p", invalid_refs=[])
        assert isinstance(e, WorkflowValidationError)

    def test_suggestion_optional(self):
        from openintent.workflow import InputWiringError

        e = InputWiringError(phase_name="p", invalid_refs=[], suggestion="Fix it")
        assert e.suggestion == "Fix it"

    def test_export_from_package(self):
        import openintent

        assert hasattr(openintent, "InputWiringError")


# ---------------------------------------------------------------------------
# YAML parsing of outputs and inputs
# ---------------------------------------------------------------------------


class TestWorkflowIOParsing:
    def test_outputs_dict_form(self, tmp_path):
        spec = _make_spec(
            _BASE
            + """
workflow:
  fetch:
    title: "Fetch"
    assign: agent
    outputs:
      revenue: number
      label: string
""",
            tmp_path,
        )
        phase = spec.phases[0]
        assert phase.outputs == {"revenue": "number", "label": "string"}

    def test_outputs_legacy_list_form(self, tmp_path):
        spec = _make_spec(
            _BASE
            + """
workflow:
  fetch:
    title: "Fetch"
    assign: agent
    outputs:
      - revenue
      - label
""",
            tmp_path,
        )
        phase = spec.phases[0]
        assert phase.outputs == {"revenue": "any", "label": "any"}

    def test_outputs_optional_flag(self, tmp_path):
        spec = _make_spec(
            _BASE
            + """
workflow:
  fetch:
    title: "Fetch"
    assign: agent
    outputs:
      revenue: number
      notes:
        type: string
        required: false
""",
            tmp_path,
        )
        phase = spec.phases[0]
        assert phase.outputs["revenue"] == "number"
        assert phase.outputs["notes"] == {"type": "string", "required": False}

    def test_inputs_dict_form(self, tmp_path):
        spec = _make_spec(
            _BASE
            + """
workflow:
  fetch:
    title: "Fetch"
    assign: agent
    outputs:
      revenue: number

  analyze:
    title: "Analyze"
    assign: agent
    depends_on: [fetch]
    inputs:
      rev: fetch.revenue
""",
            tmp_path,
        )
        phase = next(p for p in spec.phases if p.name == "analyze")
        assert phase.inputs == {"rev": "fetch.revenue"}

    def test_trigger_input_reference(self, tmp_path):
        spec = _make_spec(
            _BASE
            + """
workflow:
  fetch:
    title: "Fetch"
    assign: agent
    inputs:
      quarter: $trigger.quarter
""",
            tmp_path,
        )
        phase = spec.phases[0]
        assert phase.inputs == {"quarter": "$trigger.quarter"}

    def test_initial_state_input_reference(self, tmp_path):
        spec = _make_spec(
            _BASE
            + """
workflow:
  fetch:
    title: "Fetch"
    assign: agent
    inputs:
      config: $initial_state.config
""",
            tmp_path,
        )
        phase = spec.phases[0]
        assert phase.inputs == {"config": "$initial_state.config"}

    def test_types_block_stored(self, tmp_path):
        spec = _make_spec(
            _BASE
            + """
types:
  FinancialSummary:
    revenue: number
    expenses: number

workflow:
  fetch:
    title: "Fetch"
    assign: agent
    outputs:
      summary: FinancialSummary
""",
            tmp_path,
        )
        assert "FinancialSummary" in spec.types
        assert spec.phases[0].outputs == {"summary": "FinancialSummary"}

    def test_no_outputs_defaults_empty(self, tmp_path):
        spec = _make_spec(
            _BASE
            + """
workflow:
  simple:
    title: "Simple"
    assign: agent
""",
            tmp_path,
        )
        assert spec.phases[0].outputs == {}

    def test_no_inputs_defaults_empty(self, tmp_path):
        spec = _make_spec(
            _BASE
            + """
workflow:
  simple:
    title: "Simple"
    assign: agent
""",
            tmp_path,
        )
        assert spec.phases[0].inputs == {}


# ---------------------------------------------------------------------------
# Parse-time I/O wiring validation (_validate_io_wiring)
# ---------------------------------------------------------------------------


class TestValidateIOWiring:
    def test_valid_wiring_passes(self, tmp_path):
        _make_spec(
            _BASE
            + """
workflow:
  fetch:
    title: "Fetch"
    assign: agent
    outputs:
      revenue: number

  analyze:
    title: "Analyze"
    assign: agent
    depends_on: [fetch]
    inputs:
      rev: fetch.revenue
""",
            tmp_path,
        )

    def test_reference_to_nonexistent_phase_raises(self, tmp_path):
        from openintent.workflow import InputWiringError

        with pytest.raises(InputWiringError):
            _make_spec(
                _BASE
                + """
workflow:
  analyze:
    title: "Analyze"
    assign: agent
    inputs:
      rev: ghost.revenue
""",
                tmp_path,
            )

    def test_reference_to_non_dependency_raises(self, tmp_path):
        from openintent.workflow import InputWiringError

        with pytest.raises(InputWiringError):
            _make_spec(
                _BASE
                + """
workflow:
  fetch:
    title: "Fetch"
    assign: agent
    outputs:
      revenue: number

  analyze:
    title: "Analyze"
    assign: agent
    inputs:
      rev: fetch.revenue
""",
                tmp_path,
            )

    def test_reference_to_undeclared_output_key_raises(self, tmp_path):
        from openintent.workflow import InputWiringError

        with pytest.raises(InputWiringError):
            _make_spec(
                _BASE
                + """
workflow:
  fetch:
    title: "Fetch"
    assign: agent
    outputs:
      revenue: number

  analyze:
    title: "Analyze"
    assign: agent
    depends_on: [fetch]
    inputs:
      x: fetch.nonexistent_key
""",
                tmp_path,
            )

    def test_trigger_reference_skips_validation(self, tmp_path):
        _make_spec(
            _BASE
            + """
workflow:
  fetch:
    title: "Fetch"
    assign: agent
    inputs:
      quarter: $trigger.quarter
""",
            tmp_path,
        )

    def test_initial_state_reference_skips_validation(self, tmp_path):
        _make_spec(
            _BASE
            + """
workflow:
  fetch:
    title: "Fetch"
    assign: agent
    inputs:
      config: $initial_state.config
""",
            tmp_path,
        )

    def test_upstream_without_outputs_declared_skips_key_check(self, tmp_path):
        """If upstream has no outputs block, skip key validation (incremental adoption)."""
        _make_spec(
            _BASE
            + """
workflow:
  fetch:
    title: "Fetch"
    assign: agent

  analyze:
    title: "Analyze"
    assign: agent
    depends_on: [fetch]
    inputs:
      rev: fetch.any_key_is_ok
""",
            tmp_path,
        )

    def test_invalid_syntax_no_dot_raises(self, tmp_path):
        from openintent.workflow import InputWiringError

        with pytest.raises(InputWiringError):
            _make_spec(
                _BASE
                + """
workflow:
  analyze:
    title: "Analyze"
    assign: agent
    inputs:
      rev: just_a_bare_string
""",
                tmp_path,
            )

    def test_multiple_inputs_one_bad_raises(self, tmp_path):
        from openintent.workflow import InputWiringError

        with pytest.raises(InputWiringError):
            _make_spec(
                _BASE
                + """
workflow:
  fetch:
    title: "Fetch"
    assign: agent
    outputs:
      revenue: number
      expenses: number

  analyze:
    title: "Analyze"
    assign: agent
    depends_on: [fetch]
    inputs:
      rev: fetch.revenue
      bad: ghost.whatever
""",
                tmp_path,
            )


# ---------------------------------------------------------------------------
# resolve_task_inputs
# ---------------------------------------------------------------------------


class TestResolveTaskInputs:
    def _spec_with_io(self, tmp_path):
        return _make_spec(
            _BASE
            + """
workflow:
  fetch:
    title: "Fetch"
    assign: agent
    outputs:
      revenue: number
      expenses: number

  analyze:
    title: "Analyze"
    assign: agent
    depends_on: [fetch]
    inputs:
      rev: fetch.revenue
      exp: fetch.expenses
""",
            tmp_path,
        )

    def test_resolves_from_upstream(self, tmp_path):
        spec = self._spec_with_io(tmp_path)
        result = spec.resolve_task_inputs(
            phase_name="analyze",
            upstream_outputs={"fetch": {"revenue": 1000, "expenses": 200}},
        )
        assert result == {"rev": 1000, "exp": 200}

    def test_no_inputs_returns_empty(self, tmp_path):
        spec = self._spec_with_io(tmp_path)
        result = spec.resolve_task_inputs(
            phase_name="fetch",
            upstream_outputs={},
        )
        assert result == {}

    def test_trigger_reference_resolved(self, tmp_path):
        spec = _make_spec(
            _BASE
            + """
workflow:
  fetch:
    title: "Fetch"
    assign: agent
    inputs:
      quarter: $trigger.quarter
""",
            tmp_path,
        )
        result = spec.resolve_task_inputs(
            phase_name="fetch",
            upstream_outputs={},
            trigger_payload={"quarter": "Q1-2026"},
        )
        assert result == {"quarter": "Q1-2026"}

    def test_initial_state_reference_resolved(self, tmp_path):
        spec = _make_spec(
            _BASE
            + """
workflow:
  fetch:
    title: "Fetch"
    assign: agent
    inputs:
      cfg: $initial_state.config
""",
            tmp_path,
        )
        result = spec.resolve_task_inputs(
            phase_name="fetch",
            upstream_outputs={},
            initial_state={"config": {"timeout": 30}},
        )
        assert result == {"cfg": {"timeout": 30}}

    def test_missing_upstream_output_raises(self, tmp_path):
        from openintent.workflow import UnresolvableInputError

        spec = self._spec_with_io(tmp_path)
        with pytest.raises(UnresolvableInputError) as exc_info:
            spec.resolve_task_inputs(
                phase_name="analyze",
                upstream_outputs={"fetch": {"revenue": 1000}},
            )
        err = exc_info.value
        assert err.phase_name == "analyze"
        assert any("expenses" in r for r in err.unresolvable_refs)

    def test_missing_trigger_key_raises(self, tmp_path):
        from openintent.workflow import UnresolvableInputError

        spec = _make_spec(
            _BASE
            + """
workflow:
  fetch:
    title: "Fetch"
    assign: agent
    inputs:
      quarter: $trigger.quarter
""",
            tmp_path,
        )
        with pytest.raises(UnresolvableInputError):
            spec.resolve_task_inputs(
                phase_name="fetch",
                upstream_outputs={},
                trigger_payload={},
            )

    def test_missing_initial_state_key_raises(self, tmp_path):
        from openintent.workflow import UnresolvableInputError

        spec = _make_spec(
            _BASE
            + """
workflow:
  fetch:
    title: "Fetch"
    assign: agent
    inputs:
      cfg: $initial_state.config
""",
            tmp_path,
        )
        with pytest.raises(UnresolvableInputError):
            spec.resolve_task_inputs(
                phase_name="fetch",
                upstream_outputs={},
                initial_state={},
            )

    def test_unknown_phase_raises_key_error(self, tmp_path):
        spec = self._spec_with_io(tmp_path)
        with pytest.raises(KeyError):
            spec.resolve_task_inputs(
                phase_name="nonexistent",
                upstream_outputs={},
            )

    def test_task_id_propagated_to_error(self, tmp_path):
        from openintent.workflow import UnresolvableInputError

        spec = self._spec_with_io(tmp_path)
        with pytest.raises(UnresolvableInputError) as exc_info:
            spec.resolve_task_inputs(
                phase_name="analyze",
                upstream_outputs={},
                task_id="task-abc-123",
            )
        assert exc_info.value.task_id == "task-abc-123"

    def test_multiple_unresolvable_collected(self, tmp_path):
        from openintent.workflow import UnresolvableInputError

        spec = self._spec_with_io(tmp_path)
        with pytest.raises(UnresolvableInputError) as exc_info:
            spec.resolve_task_inputs(
                phase_name="analyze",
                upstream_outputs={},
            )
        assert len(exc_info.value.unresolvable_refs) == 2


# ---------------------------------------------------------------------------
# validate_task_outputs
# ---------------------------------------------------------------------------


class TestValidateTaskOutputs:
    def _spec_with_outputs(self, tmp_path, outputs_yaml: str):
        return _make_spec(
            _BASE
            + f"""
workflow:
  fetch:
    title: "Fetch"
    assign: agent
    outputs:
      {outputs_yaml}
""",
            tmp_path,
        )

    def test_valid_output_passes(self, tmp_path):
        spec = self._spec_with_outputs(tmp_path, "revenue: number")
        spec.validate_task_outputs("fetch", {"revenue": 1000})

    def test_missing_required_key_raises(self, tmp_path):
        from openintent.workflow import MissingOutputError

        spec = self._spec_with_outputs(tmp_path, "revenue: number")
        with pytest.raises(MissingOutputError) as exc_info:
            spec.validate_task_outputs("fetch", {})
        assert "revenue" in exc_info.value.missing_keys

    def test_multiple_missing_keys_raises(self, tmp_path):
        from openintent.workflow import MissingOutputError

        spec = _make_spec(
            _BASE
            + """
workflow:
  fetch:
    title: "Fetch"
    assign: agent
    outputs:
      revenue: number
      expenses: number
""",
            tmp_path,
        )
        with pytest.raises(MissingOutputError) as exc_info:
            spec.validate_task_outputs("fetch", {})
        assert len(exc_info.value.missing_keys) == 2

    def test_wrong_type_raises(self, tmp_path):
        from openintent.workflow import OutputTypeMismatchError

        spec = self._spec_with_outputs(tmp_path, "revenue: number")
        with pytest.raises(OutputTypeMismatchError) as exc_info:
            spec.validate_task_outputs("fetch", {"revenue": "not-a-number"})
        assert exc_info.value.key == "revenue"
        assert exc_info.value.expected_type == "number"

    def test_optional_field_absent_passes(self, tmp_path):
        spec = _make_spec(
            _BASE
            + """
workflow:
  fetch:
    title: "Fetch"
    assign: agent
    outputs:
      revenue: number
      notes:
        type: string
        required: false
""",
            tmp_path,
        )
        spec.validate_task_outputs("fetch", {"revenue": 100})

    def test_optional_field_present_wrong_type_raises(self, tmp_path):
        from openintent.workflow import OutputTypeMismatchError

        spec = _make_spec(
            _BASE
            + """
workflow:
  fetch:
    title: "Fetch"
    assign: agent
    outputs:
      revenue: number
      notes:
        type: string
        required: false
""",
            tmp_path,
        )
        with pytest.raises(OutputTypeMismatchError):
            spec.validate_task_outputs("fetch", {"revenue": 100, "notes": 42})

    def test_no_outputs_schema_is_noop(self, tmp_path):
        spec = _make_spec(
            _BASE
            + """
workflow:
  simple:
    title: "Simple"
    assign: agent
""",
            tmp_path,
        )
        spec.validate_task_outputs("simple", {})
        spec.validate_task_outputs("simple", {"anything": "is fine"})

    def test_extra_keys_ignored(self, tmp_path):
        spec = self._spec_with_outputs(tmp_path, "revenue: number")
        spec.validate_task_outputs("fetch", {"revenue": 500, "bonus": "extra"})

    def test_unknown_phase_raises_key_error(self, tmp_path):
        spec = self._spec_with_outputs(tmp_path, "revenue: number")
        with pytest.raises(KeyError):
            spec.validate_task_outputs("nonexistent", {"revenue": 1})

    def test_task_id_in_error(self, tmp_path):
        from openintent.workflow import MissingOutputError

        spec = self._spec_with_outputs(tmp_path, "revenue: number")
        with pytest.raises(MissingOutputError) as exc_info:
            spec.validate_task_outputs("fetch", {}, task_id="task-xyz")
        assert exc_info.value.task_id == "task-xyz"


# ---------------------------------------------------------------------------
# _check_value_type — primitive types
# ---------------------------------------------------------------------------


class TestCheckValueType:
    def _spec(self, tmp_path):
        return _make_spec(
            _BASE
            + """
workflow:
  p:
    title: "P"
    assign: a
""",
            tmp_path,
        )

    def _check(self, spec, expected_type, value, tmp_path):
        from openintent.workflow import OutputTypeMismatchError

        spec.validate_task_outputs.__func__  # just to confirm it's on the class
        try:
            spec._check_value_type(
                task_id="",
                phase_name="p",
                key="k",
                expected_type=expected_type,
                value=value,
            )
        except OutputTypeMismatchError:
            raise

    def test_string_accepts_str(self, tmp_path):
        spec = self._spec(tmp_path)
        spec._check_value_type("", "p", "k", "string", "hello")

    def test_string_rejects_int(self, tmp_path):
        from openintent.workflow import OutputTypeMismatchError

        spec = self._spec(tmp_path)
        with pytest.raises(OutputTypeMismatchError):
            spec._check_value_type("", "p", "k", "string", 42)

    def test_number_accepts_int(self, tmp_path):
        spec = self._spec(tmp_path)
        spec._check_value_type("", "p", "k", "number", 42)

    def test_number_accepts_float(self, tmp_path):
        spec = self._spec(tmp_path)
        spec._check_value_type("", "p", "k", "number", 3.14)

    def test_number_rejects_string(self, tmp_path):
        from openintent.workflow import OutputTypeMismatchError

        spec = self._spec(tmp_path)
        with pytest.raises(OutputTypeMismatchError):
            spec._check_value_type("", "p", "k", "number", "42")

    def test_boolean_accepts_true(self, tmp_path):
        spec = self._spec(tmp_path)
        spec._check_value_type("", "p", "k", "boolean", True)

    def test_boolean_rejects_int_one(self, tmp_path):
        from openintent.workflow import OutputTypeMismatchError

        spec = self._spec(tmp_path)
        with pytest.raises(OutputTypeMismatchError):
            spec._check_value_type("", "p", "k", "boolean", 1)

    def test_object_accepts_dict(self, tmp_path):
        spec = self._spec(tmp_path)
        spec._check_value_type("", "p", "k", "object", {"a": 1})

    def test_object_rejects_list(self, tmp_path):
        from openintent.workflow import OutputTypeMismatchError

        spec = self._spec(tmp_path)
        with pytest.raises(OutputTypeMismatchError):
            spec._check_value_type("", "p", "k", "object", [])

    def test_array_accepts_list(self, tmp_path):
        spec = self._spec(tmp_path)
        spec._check_value_type("", "p", "k", "array", [1, 2, 3])

    def test_array_rejects_dict(self, tmp_path):
        from openintent.workflow import OutputTypeMismatchError

        spec = self._spec(tmp_path)
        with pytest.raises(OutputTypeMismatchError):
            spec._check_value_type("", "p", "k", "array", {"a": 1})

    def test_any_accepts_anything(self, tmp_path):
        spec = self._spec(tmp_path)
        spec._check_value_type("", "p", "k", "any", "anything")
        spec._check_value_type("", "p", "k", "any", 42)
        spec._check_value_type("", "p", "k", "any", None)

    def test_unknown_named_type_accepts_without_validation(self, tmp_path):
        """Named type not in types block is silently accepted (incremental adoption)."""
        spec = self._spec(tmp_path)
        spec._check_value_type("", "p", "k", "UnknownType", {"anything": True})

    def test_named_struct_type_accepts_valid_keys(self, tmp_path):
        spec = _make_spec(
            _BASE
            + """
types:
  Summary:
    revenue: number
    expenses: number

workflow:
  p:
    title: "P"
    assign: a
    outputs:
      result: Summary
""",
            tmp_path,
        )
        spec._check_value_type(
            "", "p", "k", "Summary", {"revenue": 100, "expenses": 50}
        )

    def test_named_struct_type_rejects_non_dict(self, tmp_path):
        from openintent.workflow import OutputTypeMismatchError

        spec = _make_spec(
            _BASE
            + """
types:
  Summary:
    revenue: number

workflow:
  p:
    title: "P"
    assign: a
""",
            tmp_path,
        )
        with pytest.raises(OutputTypeMismatchError):
            spec._check_value_type("", "p", "k", "Summary", "not-a-dict")

    def test_named_struct_missing_key_raises(self, tmp_path):
        from openintent.workflow import OutputTypeMismatchError

        spec = _make_spec(
            _BASE
            + """
types:
  Summary:
    revenue: number
    expenses: number

workflow:
  p:
    title: "P"
    assign: a
""",
            tmp_path,
        )
        with pytest.raises(OutputTypeMismatchError):
            spec._check_value_type("", "p", "k", "Summary", {"revenue": 100})

    def test_enum_type_accepts_valid_value(self, tmp_path):
        spec = _make_spec(
            _BASE
            + """
types:
  RiskLevel:
    enum: [low, medium, high]

workflow:
  p:
    title: "P"
    assign: a
""",
            tmp_path,
        )
        spec._check_value_type("", "p", "k", "RiskLevel", "medium")

    def test_enum_type_rejects_invalid_value(self, tmp_path):
        from openintent.workflow import OutputTypeMismatchError

        spec = _make_spec(
            _BASE
            + """
types:
  RiskLevel:
    enum: [low, medium, high]

workflow:
  p:
    title: "P"
    assign: a
""",
            tmp_path,
        )
        with pytest.raises(OutputTypeMismatchError):
            spec._check_value_type("", "p", "k", "RiskLevel", "critical")


# ---------------------------------------------------------------------------
# validate_claim_inputs
# ---------------------------------------------------------------------------


class TestValidateClaimInputs:
    def test_valid_claim_passes(self, tmp_path):
        spec = _make_spec(
            _BASE
            + """
workflow:
  fetch:
    title: "Fetch"
    assign: agent
    outputs:
      revenue: number

  analyze:
    title: "Analyze"
    assign: agent
    depends_on: [fetch]
    inputs:
      rev: fetch.revenue
""",
            tmp_path,
        )
        spec.validate_claim_inputs(
            phase_name="analyze",
            upstream_outputs={"fetch": {"revenue": 999}},
        )

    def test_unresolvable_raises(self, tmp_path):
        from openintent.workflow import UnresolvableInputError

        spec = _make_spec(
            _BASE
            + """
workflow:
  fetch:
    title: "Fetch"
    assign: agent
    outputs:
      revenue: number

  analyze:
    title: "Analyze"
    assign: agent
    depends_on: [fetch]
    inputs:
      rev: fetch.revenue
""",
            tmp_path,
        )
        with pytest.raises(UnresolvableInputError):
            spec.validate_claim_inputs(
                phase_name="analyze",
                upstream_outputs={},
            )

    def test_phase_without_inputs_always_valid(self, tmp_path):
        spec = _make_spec(
            _BASE
            + """
workflow:
  simple:
    title: "Simple"
    assign: agent
""",
            tmp_path,
        )
        spec.validate_claim_inputs(phase_name="simple", upstream_outputs={})


# ---------------------------------------------------------------------------
# End-to-end output validation via validate_task_outputs with types block
# ---------------------------------------------------------------------------


class TestOutputValidationWithTypesBlock:
    def test_named_type_valid(self, tmp_path):
        spec = _make_spec(
            _BASE
            + """
types:
  FinancialSummary:
    revenue: number
    expenses: number

workflow:
  fetch:
    title: "Fetch"
    assign: agent
    outputs:
      summary: FinancialSummary
""",
            tmp_path,
        )
        spec.validate_task_outputs(
            "fetch", {"summary": {"revenue": 1000, "expenses": 200}}
        )

    def test_named_type_missing_field_raises(self, tmp_path):
        from openintent.workflow import OutputTypeMismatchError

        spec = _make_spec(
            _BASE
            + """
types:
  FinancialSummary:
    revenue: number
    expenses: number

workflow:
  fetch:
    title: "Fetch"
    assign: agent
    outputs:
      summary: FinancialSummary
""",
            tmp_path,
        )
        with pytest.raises(OutputTypeMismatchError):
            spec.validate_task_outputs("fetch", {"summary": {"revenue": 1000}})

    def test_enum_output_valid(self, tmp_path):
        spec = _make_spec(
            _BASE
            + """
types:
  Status:
    enum: [pending, approved, rejected]

workflow:
  review:
    title: "Review"
    assign: agent
    outputs:
      status: Status
""",
            tmp_path,
        )
        spec.validate_task_outputs("review", {"status": "approved"})

    def test_enum_output_invalid_raises(self, tmp_path):
        from openintent.workflow import OutputTypeMismatchError

        spec = _make_spec(
            _BASE
            + """
types:
  Status:
    enum: [pending, approved, rejected]

workflow:
  review:
    title: "Review"
    assign: agent
    outputs:
      status: Status
""",
            tmp_path,
        )
        with pytest.raises(OutputTypeMismatchError):
            spec.validate_task_outputs("review", {"status": "unknown"})

    def test_mixed_required_and_optional(self, tmp_path):
        spec = _make_spec(
            _BASE
            + """
workflow:
  fetch:
    title: "Fetch"
    assign: agent
    outputs:
      revenue: number
      expenses: number
      notes:
        type: string
        required: false
      confidence:
        type: number
        required: false
""",
            tmp_path,
        )
        spec.validate_task_outputs("fetch", {"revenue": 1000, "expenses": 200})
        spec.validate_task_outputs(
            "fetch",
            {"revenue": 1000, "expenses": 200, "notes": "good", "confidence": 0.95},
        )


# ---------------------------------------------------------------------------
# Incremental adoption — workflows without I/O contracts are unaffected
# ---------------------------------------------------------------------------


class TestIncrementalAdoption:
    def test_workflow_without_io_still_valid(self, tmp_path):
        spec = _make_spec(
            _BASE
            + """
workflow:
  research:
    title: "Research"
    assign: researcher

  summarize:
    title: "Summarize"
    assign: summarizer
    depends_on: [research]
""",
            tmp_path,
        )
        assert len(spec.phases) == 2
        for phase in spec.phases:
            assert phase.inputs == {}
            assert phase.outputs == {}

    def test_partial_io_contract_still_validates(self, tmp_path):
        """Only phases that declare outputs need to satisfy them."""
        spec = _make_spec(
            _BASE
            + """
workflow:
  raw:
    title: "Raw"
    assign: agent

  typed:
    title: "Typed"
    assign: agent
    depends_on: [raw]
    outputs:
      result: string
""",
            tmp_path,
        )
        spec.validate_task_outputs("raw", {})
        spec.validate_task_outputs("typed", {"result": "done"})

    def test_upstream_without_outputs_unblocks_downstream(self, tmp_path):
        """Upstream with no declared outputs can still be referenced in inputs."""
        spec = _make_spec(
            _BASE
            + """
workflow:
  fetch:
    title: "Fetch"
    assign: agent

  analyze:
    title: "Analyze"
    assign: agent
    depends_on: [fetch]
    inputs:
      data: fetch.anything
""",
            tmp_path,
        )
        result = spec.resolve_task_inputs(
            "analyze", upstream_outputs={"fetch": {"anything": [1, 2, 3]}}
        )
        assert result == {"data": [1, 2, 3]}


# ---------------------------------------------------------------------------
# Package export surface
# ---------------------------------------------------------------------------


class TestRFC0024Exports:
    def test_missing_output_error_exported(self):
        import openintent

        assert hasattr(openintent, "MissingOutputError")

    def test_output_type_mismatch_error_exported(self):
        import openintent

        assert hasattr(openintent, "OutputTypeMismatchError")

    def test_unresolvable_input_error_exported(self):
        import openintent

        assert hasattr(openintent, "UnresolvableInputError")

    def test_input_wiring_error_exported(self):
        import openintent

        assert hasattr(openintent, "InputWiringError")

    def test_errors_are_instantiable_from_package(self):
        import openintent

        e = openintent.MissingOutputError(
            task_id="t", phase_name="p", missing_keys=["k"]
        )
        assert isinstance(e, openintent.WorkflowError)

    def test_unresolvable_is_instantiable_from_package(self):
        import openintent

        e = openintent.UnresolvableInputError(
            task_id="t", phase_name="p", unresolvable_refs=[]
        )
        assert isinstance(e, openintent.WorkflowError)

    def test_workflow_spec_still_exported(self):
        import openintent

        assert hasattr(openintent, "WorkflowSpec")

    def test_phase_config_still_exported(self):
        import openintent

        assert hasattr(openintent, "PhaseConfig")
