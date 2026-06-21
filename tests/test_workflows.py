"""Tests for workflow engine and state management."""

import pytest
from identity_automation_platform.workflows import (
    WorkflowState,
    is_valid_transition,
    is_terminal_state,
    is_success_state,
    is_failure_state,
    WorkflowDefinition,
    WorkflowStep,
    StepStatus,
    CREATE_USER_WORKFLOW,
    DISABLE_USER_WORKFLOW,
    WorkflowInstance,
    WorkflowEngine,
)


class TestWorkflowStates:
    """Tests for workflow state machine."""

    def test_valid_transition_created_to_validation(self):
        """Test valid transition from CREATED to VALIDATION_PENDING."""
        assert is_valid_transition(
            WorkflowState.CREATED, WorkflowState.VALIDATION_PENDING
        )

    def test_invalid_transition_created_to_completed(self):
        """Test invalid transition from CREATED directly to COMPLETED."""
        assert not is_valid_transition(WorkflowState.CREATED, WorkflowState.COMPLETED)

    def test_validation_to_validated_success(self):
        """Test transition from VALIDATION_PENDING to VALIDATED."""
        assert is_valid_transition(
            WorkflowState.VALIDATION_PENDING, WorkflowState.VALIDATED
        )

    def test_validation_to_failed(self):
        """Test transition from VALIDATION_PENDING to VALIDATION_FAILED."""
        assert is_valid_transition(
            WorkflowState.VALIDATION_PENDING, WorkflowState.VALIDATION_FAILED
        )

    def test_is_terminal_state_completed(self):
        """Test that COMPLETED is a terminal state."""
        assert is_terminal_state(WorkflowState.COMPLETED)

    def test_is_terminal_state_validation_failed(self):
        """Test that VALIDATION_FAILED is a terminal state."""
        assert is_terminal_state(WorkflowState.VALIDATION_FAILED)

    def test_is_terminal_state_created(self):
        """Test that CREATED is not a terminal state."""
        assert not is_terminal_state(WorkflowState.CREATED)

    def test_is_success_state(self):
        """Test success state detection."""
        assert is_success_state(WorkflowState.COMPLETED)
        assert not is_success_state(WorkflowState.CREATED)

    def test_is_failure_state(self):
        """Test failure state detection."""
        assert is_failure_state(WorkflowState.VALIDATION_FAILED)
        assert is_failure_state(WorkflowState.EXECUTION_FAILED)
        assert not is_failure_state(WorkflowState.COMPLETED)


class TestWorkflowDefinition:
    """Tests for workflow definitions."""

    def test_create_user_workflow_exists(self):
        """Test that CREATE_USER_WORKFLOW is properly defined."""
        assert CREATE_USER_WORKFLOW.workflow_type == "CREATE_USER"
        assert len(CREATE_USER_WORKFLOW.steps) > 0

    def test_workflow_step_names_unique(self):
        """Test that workflow steps have unique names."""
        step_names = [s.name for s in CREATE_USER_WORKFLOW.steps]
        assert len(step_names) == len(set(step_names))

    def test_get_step(self):
        """Test retrieving a step by name."""
        step = CREATE_USER_WORKFLOW.get_step("validate_input")
        assert step is not None
        assert step.name == "validate_input"

    def test_get_step_not_found(self):
        """Test retrieving non-existent step returns None."""
        step = CREATE_USER_WORKFLOW.get_step("nonexistent")
        assert step is None

    def test_get_next_step(self):
        """Test getting next step in workflow."""
        next_step = CREATE_USER_WORKFLOW.get_next_step("validate_input")
        assert next_step is not None
        assert next_step.name == "provision_ad_account"

    def test_get_next_step_last(self):
        """Test getting next step after last step returns None."""
        last_step = CREATE_USER_WORKFLOW.steps[-1]
        next_step = CREATE_USER_WORKFLOW.get_next_step(last_step.name)
        assert next_step is None

    def test_get_first_step(self):
        """Test getting the first step."""
        first = CREATE_USER_WORKFLOW.get_first_step()
        assert first.name == "validate_input"

    def test_is_last_step(self):
        """Test checking if a step is the last step."""
        last_step = CREATE_USER_WORKFLOW.steps[-1]
        assert CREATE_USER_WORKFLOW.is_last_step(last_step.name)

        first_step = CREATE_USER_WORKFLOW.get_first_step()
        assert not CREATE_USER_WORKFLOW.is_last_step(first_step.name)

    def test_workflow_without_steps_raises_error(self):
        """Test that workflow without steps raises ValueError."""
        with pytest.raises(ValueError):
            WorkflowDefinition(
                workflow_type="BAD",
                name="Bad Workflow",
                description="No steps",
                steps=[],
            )

    def test_workflow_with_duplicate_step_names_raises_error(self):
        """Test that duplicate step names raise ValueError."""
        with pytest.raises(ValueError):
            WorkflowDefinition(
                workflow_type="BAD",
                name="Bad Workflow",
                description="Duplicate steps",
                steps=[
                    WorkflowStep(name="step1", handler=lambda ctx: True),
                    WorkflowStep(name="step1", handler=lambda ctx: True),
                ],
            )

    def test_validate_input_no_handler(self):
        """Test validation with no handler returns True."""
        is_valid, msg = CREATE_USER_WORKFLOW.validate_input({"test": "data"})
        assert is_valid
        assert msg == ""


class TestWorkflowInstance:
    """Tests for workflow instances."""

    def test_create_instance(self):
        """Test creating a workflow instance."""
        context = {"target_user": "john.doe@company.com"}
        instance = WorkflowInstance.create(CREATE_USER_WORKFLOW, context)

        assert instance.id
        assert instance.state == WorkflowState.CREATED
        assert instance.context == context
        assert instance.definition == CREATE_USER_WORKFLOW

    def test_transition_to_valid_state(self):
        """Test valid state transition."""
        instance = WorkflowInstance.create(CREATE_USER_WORKFLOW, {})

        success = instance.transition_to(WorkflowState.VALIDATION_PENDING)
        assert success
        assert instance.state == WorkflowState.VALIDATION_PENDING

    def test_transition_to_invalid_state(self):
        """Test invalid state transition returns False."""
        instance = WorkflowInstance.create(CREATE_USER_WORKFLOW, {})

        success = instance.transition_to(WorkflowState.COMPLETED)
        assert not success
        assert instance.state == WorkflowState.CREATED

    def test_record_step_succeeded(self):
        """Test recording successful step execution."""
        instance = WorkflowInstance.create(CREATE_USER_WORKFLOW, {})

        instance.record_step_succeeded("step1")

        assert len(instance.step_executions) == 1
        assert instance.step_executions[0].step_name == "step1"
        assert instance.step_executions[0].status == StepStatus.SUCCEEDED

    def test_record_step_failed(self):
        """Test recording failed step execution."""
        instance = WorkflowInstance.create(CREATE_USER_WORKFLOW, {})

        instance.record_step_failed("step1", "Connection timeout", retry_count=1)

        assert len(instance.step_executions) == 1
        assert instance.step_executions[0].step_name == "step1"
        assert instance.step_executions[0].status == StepStatus.FAILED
        assert instance.step_executions[0].error == "Connection timeout"
        assert instance.step_executions[0].retry_count == 1

    def test_get_step_execution(self):
        """Test retrieving step execution."""
        instance = WorkflowInstance.create(CREATE_USER_WORKFLOW, {})
        instance.record_step_succeeded("step1")

        execution = instance.get_step_execution("step1")
        assert execution is not None
        assert execution.step_name == "step1"

    def test_get_step_retry_count(self):
        """Test counting step retries."""
        instance = WorkflowInstance.create(CREATE_USER_WORKFLOW, {})

        instance.record_step_failed("step1", "Error 1", 1)
        instance.record_step_failed("step1", "Error 2", 2)

        retry_count = instance.get_step_retry_count("step1")
        assert retry_count == 2

    def test_is_complete_true(self):
        """Test is_complete returns True for completed workflow."""
        instance = WorkflowInstance.create(CREATE_USER_WORKFLOW, {})

        # Follow valid state transitions
        instance.transition_to(WorkflowState.VALIDATION_PENDING)
        instance.transition_to(WorkflowState.VALIDATED)
        instance.transition_to(WorkflowState.EXECUTING)
        instance.transition_to(WorkflowState.COMPLETED)

        assert instance.is_complete()

    def test_is_complete_false(self):
        """Test is_complete returns False for running workflow."""
        instance = WorkflowInstance.create(CREATE_USER_WORKFLOW, {})

        assert not instance.is_complete()

    def test_is_successful(self):
        """Test is_successful for completed workflow."""
        instance = WorkflowInstance.create(CREATE_USER_WORKFLOW, {})

        # Follow valid state transitions
        instance.transition_to(WorkflowState.VALIDATION_PENDING)
        instance.transition_to(WorkflowState.VALIDATED)
        instance.transition_to(WorkflowState.EXECUTING)
        instance.transition_to(WorkflowState.COMPLETED)

        assert instance.is_successful()

    def test_is_failed(self):
        """Test is_failed for failed workflow."""
        instance = WorkflowInstance.create(CREATE_USER_WORKFLOW, {})
        instance.transition_to(WorkflowState.VALIDATION_PENDING)
        instance.transition_to(WorkflowState.VALIDATION_FAILED)

        assert instance.is_failed()

    def test_to_dict(self):
        """Test converting instance to dictionary."""
        instance = WorkflowInstance.create(CREATE_USER_WORKFLOW, {"user": "test"})
        data = instance.to_dict()

        assert data["id"] == instance.id
        assert data["workflow_type"] == "CREATE_USER"
        assert data["state"] == "CREATED"
        assert data["context"] == {"user": "test"}


class TestWorkflowEngine:
    """Tests for workflow execution engine."""

    def test_create_instance(self):
        """Test engine creating a workflow instance."""
        engine = WorkflowEngine(emit_events=False)
        context = {"target_user": "john@company.com"}

        instance = engine.create_instance(CREATE_USER_WORKFLOW, context)

        assert instance.id
        assert instance.definition == CREATE_USER_WORKFLOW

    def test_validate_passes(self):
        """Test successful validation."""
        engine = WorkflowEngine(emit_events=False)
        instance = WorkflowInstance.create(CREATE_USER_WORKFLOW, {"user": "test"})

        is_valid, msg = engine.validate(instance)

        assert is_valid
        assert instance.state == WorkflowState.VALIDATED

    def test_validate_fails(self):
        """Test validation failure."""

        # Create workflow with failing validator
        def fail_validator(ctx):
            return False, "Invalid data"

        workflow = WorkflowDefinition(
            workflow_type="TEST",
            name="Test",
            description="Test",
            steps=[WorkflowStep(name="step1", handler=lambda ctx: True)],
            validation_handler=fail_validator,
        )

        engine = WorkflowEngine(emit_events=False)
        instance = WorkflowInstance.create(workflow, {})

        is_valid, msg = engine.validate(instance)

        assert not is_valid
        assert instance.state == WorkflowState.VALIDATION_FAILED

    def test_execute_simple_workflow(self):
        """Test executing a simple workflow."""
        workflow = WorkflowDefinition(
            workflow_type="SIMPLE",
            name="Simple Workflow",
            description="Test",
            steps=[
                WorkflowStep(name="step1", handler=lambda ctx: True),
                WorkflowStep(name="step2", handler=lambda ctx: True),
            ],
        )

        engine = WorkflowEngine(emit_events=False)
        instance = engine.create_instance(workflow, {})

        success = engine.execute(instance)

        assert success
        assert instance.is_successful()
        assert instance.state == WorkflowState.COMPLETED

    def test_execute_workflow_with_failing_step(self):
        """Test workflow execution fails when step fails."""
        workflow = WorkflowDefinition(
            workflow_type="FAILING",
            name="Failing Workflow",
            description="Test",
            steps=[
                WorkflowStep(name="step1", handler=lambda ctx: True),
                WorkflowStep(name="step2", handler=lambda ctx: False, retry_max=0),
                WorkflowStep(name="step3", handler=lambda ctx: True),
            ],
        )

        engine = WorkflowEngine(emit_events=False)
        instance = engine.create_instance(workflow, {})

        success = engine.execute(instance)

        assert not success
        assert instance.is_failed()
        assert instance.state == WorkflowState.EXECUTION_FAILED

    def test_execute_workflow_with_retry(self):
        """Test workflow step retry on failure."""
        attempt_count = [0]

        def failing_handler(ctx):
            attempt_count[0] += 1
            return attempt_count[0] >= 2  # Succeed on 2nd attempt

        workflow = WorkflowDefinition(
            workflow_type="RETRY",
            name="Retry Workflow",
            description="Test",
            steps=[
                WorkflowStep(name="step1", handler=lambda ctx: True),
                WorkflowStep(
                    name="step2",
                    handler=failing_handler,
                    retry_max=2,
                ),
            ],
        )

        engine = WorkflowEngine(emit_events=False)
        instance = engine.create_instance(workflow, {})

        success = engine.execute(instance)

        assert success
        assert instance.is_successful()
        assert attempt_count[0] == 2  # Called twice due to retry

    def test_execute_workflow_retry_exhausted(self):
        """Test workflow fails after retries exhausted."""
        workflow = WorkflowDefinition(
            workflow_type="RETRY_FAIL",
            name="Retry Fail Workflow",
            description="Test",
            steps=[
                WorkflowStep(
                    name="step1",
                    handler=lambda ctx: False,
                    retry_max=1,
                ),
            ],
        )

        engine = WorkflowEngine(emit_events=False)
        instance = engine.create_instance(workflow, {})

        success = engine.execute(instance)

        assert not success
        assert instance.is_failed()
        # Should have 2 failed attempts (initial + 1 retry)
        assert instance.get_step_retry_count("step1") == 1

    def test_disable_user_workflow(self):
        """Test DISABLE_USER workflow structure."""
        assert DISABLE_USER_WORKFLOW.workflow_type == "DISABLE_USER"
        assert len(DISABLE_USER_WORKFLOW.steps) > 0

        # Check expected steps exist
        step_names = [s.name for s in DISABLE_USER_WORKFLOW.steps]
        assert "validate_input" in step_names
        assert "revoke_access" in step_names
        assert "disable_ad_account" in step_names
