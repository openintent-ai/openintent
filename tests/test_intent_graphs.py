"""
Tests for RFC-0002: Intent Graphs

Tests parent-child relationships, dependencies, DAG validation,
and dependency-aware status transitions.
"""

from openintent.models import Intent, IntentState, IntentStatus


class TestIntentModel:
    """Tests for Intent model with RFC-0002 fields."""

    def test_intent_with_parent_id(self):
        """Intent should support parent_intent_id field."""
        intent = Intent(
            id="child-1",
            title="Child Intent",
            description="A child intent",
            version=1,
            status=IntentStatus.ACTIVE,
            state=IntentState(),
            parent_intent_id="parent-1",
        )

        assert intent.parent_intent_id == "parent-1"
        assert intent.has_parent is True

    def test_intent_without_parent(self):
        """Intent without parent should have has_parent=False."""
        intent = Intent(
            id="root-1",
            title="Root Intent",
            description="A root intent",
            version=1,
            status=IntentStatus.ACTIVE,
            state=IntentState(),
        )

        assert intent.parent_intent_id is None
        assert intent.has_parent is False

    def test_intent_with_dependencies(self):
        """Intent should support depends_on field."""
        intent = Intent(
            id="task-3",
            title="Deploy Fix",
            description="Deploy the hotfix",
            version=1,
            status=IntentStatus.ACTIVE,
            state=IntentState(),
            depends_on=["task-1", "task-2"],
        )

        assert intent.depends_on == ["task-1", "task-2"]
        assert intent.has_dependencies is True

    def test_intent_without_dependencies(self):
        """Intent without dependencies should have has_dependencies=False."""
        intent = Intent(
            id="task-1",
            title="Diagnose",
            description="Diagnose the issue",
            version=1,
            status=IntentStatus.ACTIVE,
            state=IntentState(),
        )

        assert intent.depends_on == []
        assert intent.has_dependencies is False

    def test_intent_to_dict_includes_graph_fields(self):
        """to_dict should include parent_intent_id and depends_on."""
        intent = Intent(
            id="task-1",
            title="Test",
            description="Test intent",
            version=1,
            status=IntentStatus.ACTIVE,
            state=IntentState(),
            parent_intent_id="parent-1",
            depends_on=["dep-1", "dep-2"],
        )

        data = intent.to_dict()

        assert data["parent_intent_id"] == "parent-1"
        assert data["depends_on"] == ["dep-1", "dep-2"]

    def test_intent_from_dict_with_graph_fields(self):
        """from_dict should parse parent_intent_id and depends_on."""
        data = {
            "id": "task-1",
            "title": "Test",
            "description": "Test intent",
            "version": 1,
            "status": "active",
            "state": {},
            "parent_intent_id": "parent-1",
            "depends_on": ["dep-1", "dep-2"],
        }

        intent = Intent.from_dict(data)

        assert intent.parent_intent_id == "parent-1"
        assert intent.depends_on == ["dep-1", "dep-2"]

    def test_intent_from_dict_with_camel_case_fields(self):
        """from_dict should handle both snake_case and camelCase."""
        data = {
            "id": "task-1",
            "title": "Test",
            "status": "active",
            "parentIntentId": "parent-1",
            "dependsOn": ["dep-1"],
        }

        intent = Intent.from_dict(data)

        assert intent.parent_intent_id == "parent-1"
        assert intent.depends_on == ["dep-1"]


class TestIncidentResponseGraph:
    """Tests for incident response graph structure."""

    def create_incident_graph(self):
        """Create a sample incident response graph."""
        parent = Intent(
            id="incident-1",
            title="Resolve Outage",
            description="",
            version=1,
            status=IntentStatus.ACTIVE,
            state=IntentState(),
        )

        diagnose = Intent(
            id="diagnose-1",
            title="Diagnose Root Cause",
            description="",
            version=1,
            status=IntentStatus.ACTIVE,
            state=IntentState(),
            parent_intent_id="incident-1",
        )

        communicate = Intent(
            id="communicate-1",
            title="Customer Communication",
            description="",
            version=1,
            status=IntentStatus.ACTIVE,
            state=IntentState(),
            parent_intent_id="incident-1",
        )

        hotfix = Intent(
            id="hotfix-1",
            title="Implement Hotfix",
            description="",
            version=1,
            status=IntentStatus.BLOCKED,
            state=IntentState(),
            parent_intent_id="incident-1",
            depends_on=["diagnose-1"],
        )

        deploy = Intent(
            id="deploy-1",
            title="Deploy Fix",
            description="",
            version=1,
            status=IntentStatus.BLOCKED,
            state=IntentState(),
            parent_intent_id="incident-1",
            depends_on=["diagnose-1", "hotfix-1"],
        )

        return {
            "parent": parent,
            "diagnose": diagnose,
            "communicate": communicate,
            "hotfix": hotfix,
            "deploy": deploy,
        }

    def test_incident_graph_structure(self):
        """Verify incident response graph has correct structure."""
        graph = self.create_incident_graph()

        assert graph["parent"].has_parent is False
        assert graph["diagnose"].has_parent is True
        assert graph["diagnose"].parent_intent_id == "incident-1"

        assert graph["diagnose"].has_dependencies is False
        assert graph["communicate"].has_dependencies is False

        assert graph["hotfix"].has_dependencies is True
        assert "diagnose-1" in graph["hotfix"].depends_on

        assert graph["deploy"].has_dependencies is True
        assert len(graph["deploy"].depends_on) == 2

    def test_parallel_intents_have_no_dependencies(self):
        """Parallel intents should not have dependencies on each other."""
        graph = self.create_incident_graph()

        assert "communicate-1" not in graph["diagnose"].depends_on
        assert "diagnose-1" not in graph["communicate"].depends_on

    def test_multi_dependency_gate(self):
        """Deploy should depend on both diagnose AND hotfix."""
        graph = self.create_incident_graph()

        assert "diagnose-1" in graph["deploy"].depends_on
        assert "hotfix-1" in graph["deploy"].depends_on


class TestDAGValidation:
    """Tests for DAG (Directed Acyclic Graph) validation."""

    def test_valid_linear_dag(self):
        """Linear dependency chain is a valid DAG."""
        a = Intent(
            id="a",
            title="A",
            description="",
            version=1,
            status=IntentStatus.ACTIVE,
            state=IntentState(),
        )
        b = Intent(
            id="b",
            title="B",
            description="",
            version=1,
            status=IntentStatus.ACTIVE,
            state=IntentState(),
            depends_on=["a"],
        )
        c = Intent(
            id="c",
            title="C",
            description="",
            version=1,
            status=IntentStatus.ACTIVE,
            state=IntentState(),
            depends_on=["b"],
        )

        assert a.has_dependencies is False
        assert b.depends_on == ["a"]
        assert c.depends_on == ["b"]

    def test_valid_diamond_dag(self):
        """Diamond dependency pattern is a valid DAG."""
        Intent(
            id="start",
            title="Start",
            description="",
            version=1,
            status=IntentStatus.ACTIVE,
            state=IntentState(),
        )
        Intent(
            id="left",
            title="Left",
            description="",
            version=1,
            status=IntentStatus.ACTIVE,
            state=IntentState(),
            depends_on=["start"],
        )
        Intent(
            id="right",
            title="Right",
            description="",
            version=1,
            status=IntentStatus.ACTIVE,
            state=IntentState(),
            depends_on=["start"],
        )
        end = Intent(
            id="end",
            title="End",
            description="",
            version=1,
            status=IntentStatus.ACTIVE,
            state=IntentState(),
            depends_on=["left", "right"],
        )

        assert end.depends_on == ["left", "right"]


class TestIntentSerialization:
    """Tests for intent serialization with graph fields."""

    def test_roundtrip_with_graph_fields(self):
        """Intent should survive dict roundtrip with graph fields."""
        original = Intent(
            id="test-1",
            title="Test Intent",
            description="A test",
            version=5,
            status=IntentStatus.BLOCKED,
            state=IntentState(data={"progress": 50}),
            constraints=["budget < 1000"],
            parent_intent_id="parent-xyz",
            depends_on=["dep-a", "dep-b", "dep-c"],
        )

        data = original.to_dict()
        restored = Intent.from_dict(data)

        assert restored.id == original.id
        assert restored.title == original.title
        assert restored.parent_intent_id == original.parent_intent_id
        assert restored.depends_on == original.depends_on
        assert restored.status == original.status
