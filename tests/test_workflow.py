"""Tests for the workflow module."""

import pytest

from openintent.workflow import (
    LLMConfig,
    WorkflowNotFoundError,
    WorkflowSpec,
    WorkflowValidationError,
    list_sample_workflows,
    validate_workflow,
)


class TestWorkflowSpec:
    """Tests for WorkflowSpec parsing and validation."""

    def test_from_yaml_valid(self, tmp_path):
        """Test loading a valid workflow YAML."""
        yaml_content = """
openintent: "1.0"

info:
  name: "Test Workflow"
  version: "1.0.0"
  description: "A test workflow"

workflow:
  phase1:
    title: "Phase One"
    description: "First phase"
    assign: agent-1
    constraints:
      - "Be thorough"
"""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text(yaml_content)

        spec = WorkflowSpec.from_yaml(str(yaml_file))

        assert spec.name == "Test Workflow"
        assert spec.workflow_version == "1.0.0"
        assert spec.description == "A test workflow"
        assert len(spec.phases) == 1
        assert spec.phases[0].name == "phase1"
        assert spec.phases[0].title == "Phase One"
        assert spec.phases[0].assign == "agent-1"

    def test_from_yaml_with_dependencies(self, tmp_path):
        """Test loading workflow with phase dependencies."""
        yaml_content = """
openintent: "1.0"

info:
  name: "Multi-Phase Workflow"

workflow:
  research:
    title: "Research"
    assign: researcher

  analyze:
    title: "Analyze"
    assign: analyst
    depends_on: [research]

  summarize:
    title: "Summarize"
    assign: summarizer
    depends_on: [analyze]
"""
        yaml_file = tmp_path / "multi.yaml"
        yaml_file.write_text(yaml_content)

        spec = WorkflowSpec.from_yaml(str(yaml_file))

        assert len(spec.phases) == 3
        assert spec.phases[1].depends_on == ["research"]
        assert spec.phases[2].depends_on == ["analyze"]

    def test_from_yaml_file_not_found(self):
        """Test error when file doesn't exist."""
        with pytest.raises(WorkflowNotFoundError):
            WorkflowSpec.from_yaml("/nonexistent/path.yaml")

    def test_from_yaml_missing_name(self, tmp_path):
        """Test error when workflow name is missing."""
        yaml_content = """
openintent: "1.0"

info:
  version: "1.0.0"

workflow:
  phase1:
    title: "Phase"
    assign: agent
"""
        yaml_file = tmp_path / "no_name.yaml"
        yaml_file.write_text(yaml_content)

        with pytest.raises(WorkflowValidationError, match="Missing workflow name"):
            WorkflowSpec.from_yaml(str(yaml_file))

    def test_from_yaml_missing_workflow(self, tmp_path):
        """Test error when workflow section is missing."""
        yaml_content = """
openintent: "1.0"

info:
  name: "Test"
"""
        yaml_file = tmp_path / "no_workflow.yaml"
        yaml_file.write_text(yaml_content)

        with pytest.raises(WorkflowValidationError, match="Missing 'workflow' section"):
            WorkflowSpec.from_yaml(str(yaml_file))

    def test_from_yaml_circular_dependency(self, tmp_path):
        """Test error on circular dependencies."""
        yaml_content = """
openintent: "1.0"

info:
  name: "Circular"

workflow:
  a:
    title: "A"
    assign: agent
    depends_on: [b]

  b:
    title: "B"
    assign: agent
    depends_on: [a]
"""
        yaml_file = tmp_path / "circular.yaml"
        yaml_file.write_text(yaml_content)

        with pytest.raises(WorkflowValidationError, match="[Cc]ircular"):
            WorkflowSpec.from_yaml(str(yaml_file))

    def test_from_yaml_invalid_dependency(self, tmp_path):
        """Test error on reference to non-existent phase."""
        yaml_content = """
openintent: "1.0"

info:
  name: "Invalid Dep"

workflow:
  a:
    title: "A"
    assign: agent
    depends_on: [nonexistent]
"""
        yaml_file = tmp_path / "invalid_dep.yaml"
        yaml_file.write_text(yaml_content)

        with pytest.raises(WorkflowValidationError, match="[Uu]nknown|[Ii]nvalid"):
            WorkflowSpec.from_yaml(str(yaml_file))

    def test_from_yaml_with_llm_config(self, tmp_path):
        """Test parsing LLM configuration."""
        yaml_content = """
openintent: "1.0"

info:
  name: "LLM Workflow"

llm:
  provider: openai
  model: gpt-5.2
  temperature: 0.5

workflow:
  task:
    title: "Task"
    assign: agent
"""
        yaml_file = tmp_path / "llm.yaml"
        yaml_file.write_text(yaml_content)

        spec = WorkflowSpec.from_yaml(str(yaml_file))

        assert spec.llm is not None
        assert spec.llm.provider == "openai"
        assert spec.llm.model == "gpt-5.2"
        assert spec.llm.temperature == 0.5

    def test_agents_from_phases(self, tmp_path):
        """Test getting agents from workflow phases."""
        yaml_content = """
openintent: "1.0"

info:
  name: "Multi-Agent"

agents:
  agent-a:
    description: "Agent A"
  agent-b:
    description: "Agent B"

workflow:
  phase1:
    title: "Phase 1"
    assign: agent-a

  phase2:
    title: "Phase 2"
    assign: agent-b

  phase3:
    title: "Phase 3"
    assign: agent-a
"""
        yaml_file = tmp_path / "multi_agent.yaml"
        yaml_file.write_text(yaml_content)

        spec = WorkflowSpec.from_yaml(str(yaml_file))

        # agents is a dict of agent configs from YAML
        assert "agent-a" in spec.agents
        assert "agent-b" in spec.agents
        # phases assign to agents
        assigned_agents = {p.assign for p in spec.phases}
        assert assigned_agents == {"agent-a", "agent-b"}

    def test_to_portfolio_spec(self, tmp_path):
        """Test converting to PortfolioSpec."""
        yaml_content = """
openintent: "1.0"

info:
  name: "Portfolio Test"
  description: "Test portfolio conversion"

workflow:
  research:
    title: "Research"
    description: "Do research"
    assign: researcher
    constraints:
      - "Be thorough"

  summarize:
    title: "Summarize"
    assign: summarizer
    depends_on: [research]
"""
        yaml_file = tmp_path / "portfolio.yaml"
        yaml_file.write_text(yaml_content)

        spec = WorkflowSpec.from_yaml(str(yaml_file))
        portfolio = spec.to_portfolio_spec()

        assert portfolio.name == "Portfolio Test"
        assert len(portfolio.intents) == 2
        assert portfolio.intents[0].title == "Research"
        assert portfolio.intents[0].assign == "researcher"
        assert portfolio.intents[1].depends_on == ["Research"]


class TestLLMConfig:
    """Tests for LLM configuration."""

    def test_get_default_model_openai(self):
        """Test default model for OpenAI."""
        config = LLMConfig(provider="openai")
        assert config.get_default_model() == "gpt-5.2"

    def test_get_default_model_anthropic(self):
        """Test default model for Anthropic."""
        config = LLMConfig(provider="anthropic")
        assert config.get_default_model() == "claude-sonnet-4-20250514"

    def test_get_default_model_auto_with_openai_key(self, monkeypatch):
        """Test auto-detection with OpenAI key."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        config = LLMConfig(provider="auto")
        assert config.get_default_model() == "gpt-5.2"

    def test_get_default_model_explicit_anthropic(self):
        """Test explicit Anthropic model default."""
        config = LLMConfig(provider="anthropic")
        assert config.get_default_model() == "claude-sonnet-4-20250514"

    def test_get_env_key_openai(self):
        """Test env key for OpenAI."""
        config = LLMConfig(provider="openai")
        assert config.get_env_key() == "OPENAI_API_KEY"

    def test_get_env_key_anthropic(self):
        """Test env key for Anthropic."""
        config = LLMConfig(provider="anthropic")
        assert config.get_env_key() == "ANTHROPIC_API_KEY"


class TestValidateWorkflow:
    """Tests for workflow validation function."""

    def test_validate_valid_workflow(self, tmp_path):
        """Test validating a valid workflow returns no errors."""
        yaml_content = """
openintent: "1.0"

info:
  name: "Valid"

workflow:
  task:
    title: "Task"
    assign: agent
"""
        yaml_file = tmp_path / "valid.yaml"
        yaml_file.write_text(yaml_content)

        warnings = validate_workflow(str(yaml_file))
        assert isinstance(warnings, list)

    def test_validate_missing_description_warning(self, tmp_path):
        """Test warning for missing phase description."""
        yaml_content = """
openintent: "1.0"

info:
  name: "No Description"

workflow:
  task:
    title: "Task"
    assign: agent
"""
        yaml_file = tmp_path / "no_desc.yaml"
        yaml_file.write_text(yaml_content)

        warnings = validate_workflow(str(yaml_file))
        assert any("description" in w.lower() for w in warnings)


class TestListSampleWorkflows:
    """Tests for listing sample workflows."""

    def test_returns_list(self):
        """Test that list_sample_workflows returns a list."""
        samples = list_sample_workflows()
        assert isinstance(samples, list)

    def test_sample_structure(self):
        """Test structure of sample workflow entries."""
        samples = list_sample_workflows()
        if samples:  # Only test if samples exist
            sample = samples[0]
            assert "name" in sample
            assert "path" in sample
            assert "phases" in sample
