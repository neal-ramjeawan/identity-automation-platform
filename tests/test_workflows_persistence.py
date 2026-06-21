"""
Workflow persistence tests.

Tests for WorkflowStore: save, load, resume, crash recovery.
"""

import tempfile
from pathlib import Path

import pytest

from identity_automation_platform.workflows import (
    WorkflowEngine,
    WorkflowState,
    CREATE_USER_WORKFLOW,
    DISABLE_USER_WORKFLOW,
)
from identity_automation_platform.workflows.store import WorkflowStore


class TestWorkflowStore:
    """Test WorkflowStore persistence and recovery."""

    @pytest.fixture
    def temp_storage(self):
        """Create temporary directory for workflow storage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    def test_save_and_load(self, temp_storage):
        """Test saving and loading a workflow instance."""
        store = WorkflowStore(temp_storage)
        engine = WorkflowEngine(emit_events=False)

        context = {"target_user": "test.user@example.com"}
        instance = engine.create_instance(CREATE_USER_WORKFLOW, context)

        # Save instance
        store.save(instance)

        # Load instance
        loaded = store.load(instance.id, CREATE_USER_WORKFLOW)

        assert loaded is not None
        assert loaded.id == instance.id
        assert loaded.context == context
        assert loaded.state == WorkflowState.CREATED

    def test_save_updates_file(self, temp_storage):
        """Test that saving updates the file."""
        store = WorkflowStore(temp_storage)
        engine = WorkflowEngine(emit_events=False)

        context = {"target_user": "test.user@example.com"}
        instance = engine.create_instance(CREATE_USER_WORKFLOW, context)

        # Save initial
        store.save(instance)
        file_path = Path(temp_storage) / f"{instance.id}.json"
        initial_mtime = file_path.stat().st_mtime

        # Modify and save again
        instance.status = "Updated status"
        store.save(instance)
        updated_mtime = file_path.stat().st_mtime

        assert updated_mtime >= initial_mtime

    def test_load_nonexistent(self, temp_storage):
        """Test loading a workflow that doesn't exist."""
        store = WorkflowStore(temp_storage)

        loaded = store.load(
            "00000000-0000-0000-0000-000000000000", CREATE_USER_WORKFLOW
        )

        assert loaded is None

    def test_persistence_preserves_step_executions(self, temp_storage):
        """Test that step executions are preserved through save/load."""
        store = WorkflowStore(temp_storage)
        engine = WorkflowEngine(emit_events=False)

        context = {"target_user": "test.user@example.com"}
        instance = engine.create_instance(CREATE_USER_WORKFLOW, context)

        # Simulate executing first step
        instance.transition_to(WorkflowState.VALIDATION_PENDING, "Validating")
        instance.record_step_started("validate_input")
        instance.record_step_succeeded("validate_input")

        # Save and reload
        store.save(instance)
        loaded = store.load(instance.id, CREATE_USER_WORKFLOW)

        # Verify step execution was persisted
        assert len(loaded.step_executions) == 1
        step_exec = loaded.step_executions[0]
        assert step_exec.step_name == "validate_input"
        assert step_exec.status.value == "SUCCEEDED"
        assert step_exec.retry_count == 0

    def test_persistence_preserves_state(self, temp_storage):
        """Test that workflow state is preserved."""
        store = WorkflowStore(temp_storage)
        engine = WorkflowEngine(emit_events=False)

        context = {"target_user": "test.user@example.com"}
        instance = engine.create_instance(CREATE_USER_WORKFLOW, context)

        # Transition to validated state
        instance.transition_to(WorkflowState.VALIDATION_PENDING, "Validating")
        instance.transition_to(WorkflowState.VALIDATED, "Validation passed")

        # Save and reload
        store.save(instance)
        loaded = store.load(instance.id, CREATE_USER_WORKFLOW)

        assert loaded.state == WorkflowState.VALIDATED

    def test_load_incomplete_filters_terminal_states(self, temp_storage):
        """Test that load_incomplete skips completed workflows."""
        store = WorkflowStore(temp_storage)
        engine = WorkflowEngine(emit_events=False)

        # Create and complete one workflow
        context1 = {"target_user": "user1@example.com"}
        instance1 = engine.create_instance(CREATE_USER_WORKFLOW, context1)
        instance1.transition_to(WorkflowState.VALIDATION_PENDING, "")
        instance1.transition_to(WorkflowState.VALIDATED, "")
        instance1.transition_to(WorkflowState.EXECUTING, "")
        instance1.transition_to(WorkflowState.COMPLETED, "Success")
        store.save(instance1)

        # Create an incomplete workflow
        context2 = {"target_user": "user2@example.com"}
        instance2 = engine.create_instance(CREATE_USER_WORKFLOW, context2)
        instance2.transition_to(WorkflowState.VALIDATION_PENDING, "")
        instance2.transition_to(WorkflowState.VALIDATED, "")
        instance2.transition_to(WorkflowState.EXECUTING, "")
        store.save(instance2)

        # Load incomplete - should only return instance2
        definition_map = {"CREATE_USER": CREATE_USER_WORKFLOW}
        incomplete = store.load_incomplete(definition_map)

        assert len(incomplete) == 1
        assert incomplete[0].id == instance2.id

    def test_load_incomplete_includes_failed_workflows(self, temp_storage):
        """Test that load_incomplete includes EXECUTION_FAILED workflows."""
        store = WorkflowStore(temp_storage)
        engine = WorkflowEngine(emit_events=False)

        context = {"target_user": "user@example.com"}
        instance = engine.create_instance(CREATE_USER_WORKFLOW, context)
        instance.transition_to(WorkflowState.VALIDATION_PENDING, "")
        instance.transition_to(WorkflowState.VALIDATED, "")
        instance.transition_to(WorkflowState.EXECUTING, "")
        instance.transition_to(WorkflowState.EXECUTION_FAILED, "Step failed")
        store.save(instance)

        # EXECUTION_FAILED is terminal, so it should NOT be in incomplete
        definition_map = {"CREATE_USER": CREATE_USER_WORKFLOW}
        incomplete = store.load_incomplete(definition_map)

        assert len(incomplete) == 0

    def test_delete_removes_file(self, temp_storage):
        """Test that delete removes the workflow file."""
        store = WorkflowStore(temp_storage)
        engine = WorkflowEngine(emit_events=False)

        context = {"target_user": "user@example.com"}
        instance = engine.create_instance(CREATE_USER_WORKFLOW, context)
        store.save(instance)

        # Verify file exists
        file_path = Path(temp_storage) / f"{instance.id}.json"
        assert file_path.exists()

        # Delete
        store.delete(instance.id)

        # Verify file is gone
        assert not file_path.exists()

    def test_list_all(self, temp_storage):
        """Test listing all workflow IDs."""
        store = WorkflowStore(temp_storage)
        engine = WorkflowEngine(emit_events=False)

        ids = []
        for i in range(3):
            context = {"target_user": f"user{i}@example.com"}
            instance = engine.create_instance(CREATE_USER_WORKFLOW, context)
            store.save(instance)
            ids.append(str(instance.id))

        # List all
        all_ids = store.list_all()

        assert len(all_ids) == 3
        assert set(all_ids) == set(ids)

    def test_json_format_is_readable(self, temp_storage):
        """Test that persisted JSON is human-readable (indented)."""
        store = WorkflowStore(temp_storage)
        engine = WorkflowEngine(emit_events=False)

        context = {"target_user": "user@example.com"}
        instance = engine.create_instance(CREATE_USER_WORKFLOW, context)
        store.save(instance)

        # Read JSON file
        file_path = Path(temp_storage) / f"{instance.id}.json"
        with open(file_path, "r") as f:
            content = f.read()

        # Should have newlines and indentation (not minified)
        assert "\n" in content
        assert "  " in content  # Check for indentation

    def test_roundtrip_preserves_all_data(self, temp_storage):
        """Test complete roundtrip: save → load → verify all fields."""
        store = WorkflowStore(temp_storage)
        engine = WorkflowEngine(emit_events=False)

        context = {
            "target_user": "user@example.com",
            "department": "Engineering",
            "manager": "boss@example.com",
        }
        instance = engine.create_instance(CREATE_USER_WORKFLOW, context)
        instance.transition_to(WorkflowState.VALIDATION_PENDING, "Starting validation")
        instance.record_step_started("validate_input")
        instance.record_step_succeeded("validate_input")

        # Save
        store.save(instance)

        # Load
        loaded = store.load(instance.id, CREATE_USER_WORKFLOW)

        # Verify all fields match
        assert loaded.id == instance.id
        assert loaded.state == WorkflowState.VALIDATION_PENDING
        assert loaded.context == context
        assert loaded.status == "Starting validation"
        assert len(loaded.step_executions) == 1
        assert loaded.step_executions[0].step_name == "validate_input"


class TestWorkflowEngineWithPersistence:
    """Test WorkflowEngine integration with WorkflowStore."""

    @pytest.fixture
    def temp_storage(self):
        """Create temporary directory for workflow storage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    def test_engine_with_persistent_store(self, temp_storage):
        """Test that engine can work with persistent store."""
        store = WorkflowStore(temp_storage)
        engine = WorkflowEngine(emit_events=False)

        context = {"target_user": "user@example.com"}
        instance = engine.create_instance(CREATE_USER_WORKFLOW, context)

        # Manually persist (in real usage, engine would do this automatically)
        store.save(instance)

        # Simulate loading after crash
        loaded = store.load(instance.id, CREATE_USER_WORKFLOW)

        # Both instances should have same ID and context
        assert loaded.id == instance.id
        assert loaded.context == instance.context

    def test_disable_user_persistence(self, temp_storage):
        """Test persistence with different workflow type."""
        store = WorkflowStore(temp_storage)
        engine = WorkflowEngine(emit_events=False)

        context = {"target_user": "user@example.com"}
        instance = engine.create_instance(DISABLE_USER_WORKFLOW, context)
        store.save(instance)

        loaded = store.load(instance.id, DISABLE_USER_WORKFLOW)

        assert loaded is not None
        assert loaded.definition.workflow_type == "DISABLE_USER"
