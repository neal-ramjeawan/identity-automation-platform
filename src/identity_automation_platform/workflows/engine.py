"""
Workflow engine - orchestrates workflow execution.

Executes workflows step-by-step, managing state transitions,
retries, and audit event emission.
"""

from typing import Dict, Any, Optional

from .definition import WorkflowDefinition
from .instance import WorkflowInstance
from .states import WorkflowState
from .store import WorkflowStore

from identity_automation_platform.audit import AuditEvent, EventType, log_event


class WorkflowEngine:
    """Orchestrates execution of identity workflows.

    persistence, and integration with the audit logging system.
    """

def __init__(
        self, emit_events: bool = True, store: Optional[WorkflowStore] = None
    ):
        """Initialize the workflow engine.

        Args:
            emit_events: Whether to emit audit events (default: True)
            store: Optional WorkflowStore for persistence and crash recovery
        """
        self.emit_events = emit_events
        self.store = store

    def create_instance(
        self,
        definition: WorkflowDefinition,
        context: Dict[str, Any],
    ) -> WorkflowInstance:
        """
        Create a workflow instance.

        Args:
            definition: Workflow definition
            context: Input context

        Returns:
            WorkflowInstance
        """
        instance = WorkflowInstance.create(definition, context)

        # Persist if store is available
        if self.store:
            self.store.save(instance)

        if self.emit_events:
            event = AuditEvent.create(
                event_type=EventType.VALIDATION_PASSED,
                actor="workflow-engine",
                target=context.get("target_user", "unknown"),
                result="SUCCESS",
                reason=f"Workflow instance created: {definition.name}",
                metadata={
                    "workflow_id": instance.id,
                    "workflow_type": definition.workflow_type,
                },
            )
            log_event(event)

        return instance

    def validate(
        self,
        instance: WorkflowInstance,
    ) -> tuple[bool, str]:
        """
        Validate workflow input.

        Args:
            instance: Workflow instance

        Returns:
            Tuple of (is_valid, error_message)
        """
        is_valid, error_msg = instance.definition.validate_input(instance.context)

        if is_valid:
            instance.transition_to(WorkflowState.VALIDATION_PENDING)
            instance.transition_to(WorkflowState.VALIDATED)

            if self.store:
                self.store.save(instance)

            if self.emit_events:
                event = AuditEvent.create(
                    event_type=EventType.VALIDATION_PASSED,
                    actor="workflow-engine",
                    target=instance.context.get("target_user", "unknown"),
                    result="SUCCESS",
                    reason="Workflow input validation passed",
                    metadata={
                        "workflow_id": instance.id,
                        "workflow_type": instance.definition.workflow_type,
                    },
                )
                log_event(event)
        else:
            instance.transition_to(WorkflowState.VALIDATION_PENDING)
            instance.transition_to(WorkflowState.VALIDATION_FAILED, "VALIDATION_FAILED")

            if self.store:
                self.store.save(instance)

            if self.emit_events:
                event = AuditEvent.create(
                    event_type=EventType.VALIDATION_FAILED,
                    actor="workflow-engine",
                    target=instance.context.get("target_user", "unknown"),
                    result="FAILURE",
                    reason=f"Workflow validation failed: {error_msg}",
                    metadata={
                        "workflow_id": instance.id,
                        "workflow_type": instance.definition.workflow_type,
                    },
                )
                log_event(event)

        return is_valid, error_msg

    def execute(self, instance: WorkflowInstance) -> bool:
        """
        Execute a workflow to completion.

        Args:
            instance: Workflow instance

        Returns:
            True if workflow succeeded, False otherwise
        """
        # Validate first
        is_valid, _ = self.validate(instance)
        if not is_valid:
            return False

        # Transition to executing
        instance.transition_to(WorkflowState.EXECUTING, "EXECUTING")
        if self.store:
            self.store.save(instance)

        # Execute steps
        for step in instance.definition.steps:
            success = self._execute_step(instance, step.name)

            # Save after each step for crash recovery
            if self.store:
                self.store.save(instance)

            if not success:
                # Step failed - check if we should retry
                retry_count = instance.get_step_retry_count(step.name)
                step_def = instance.definition.get_step(step.name)

                if retry_count < step_def.retry_max:
                    # Retry the step
                    instance.transition_to(WorkflowState.RETRYING, "RETRYING")
                    if self.store:
                        self.store.save(instance)
                    success = self._execute_step(instance, step.name)
                    if self.store:
                        self.store.save(instance)

                if not success:
                    # Still failed after retries
                    instance.transition_to(
                        WorkflowState.EXECUTION_FAILED, "EXECUTION_FAILED"
                    )
                    if self.store:
                        self.store.save(instance)

                    if self.emit_events:
                        event = AuditEvent.create(
                            event_type=EventType.CREATE_USER_FAILED,
                            actor="workflow-engine",
                            target=instance.context.get("target_user", "unknown"),
                            result="FAILURE",
                            reason=f"Workflow failed at step: {step.name}",
                            metadata={
                                "workflow_id": instance.id,
                                "workflow_type": instance.definition.workflow_type,
                                "failed_step": step.name,
                                "retry_count": retry_count,
                            },
                        )
                        log_event(event)

                    return False

        # All steps succeeded
        instance.transition_to(WorkflowState.COMPLETED, "COMPLETED")
        if self.store:
            self.store.delete(instance.id)  # Clean up completed workflow

        if self.emit_events:
            event = AuditEvent.create(
                event_type=EventType.CREATE_USER,
                actor="workflow-engine",
                target=instance.context.get("target_user", "unknown"),
                result="SUCCESS",
                reason="Workflow completed successfully",
                metadata={
                    "workflow_id": instance.id,
                    "workflow_type": instance.definition.workflow_type,
                    "total_steps": len(instance.definition.steps),
                },
            )
            log_event(event)

        return True

    def _execute_step(self, instance: WorkflowInstance, step_name: str) -> bool:
        """Execute a single step.

        Args:
            instance: Workflow instance
            step_name: Name of step to execute

        Returns:
            True if step succeeded, False otherwise
        """
        step_def = instance.definition.get_step(step_name)
        if not step_def:
            return False

        instance.record_step_started(step_name)

        try:
            # Execute the step handler
            result = step_def.handler(instance.context)

            # Handler should return True for success
            if result:
                instance.record_step_succeeded(step_name)
                return True
            else:
                msg = "Step handler returned False"
                instance.record_step_failed(step_name, msg)
                return False

            error_msg = str(e)
            retry_count = instance.get_step_retry_count(step_name)
            instance.record_step_failed(step_name, error_msg, retry_count)
            return False

    def resume(self, instance: WorkflowInstance) -> bool:
        """
        Resume a failed workflow from the failed step.

        Args:
            instance: Workflow instance

        Returns:
            True if resumed workflow succeeds, False otherwise
        """
        if not instance.is_failed():
            return False

        # Reset to executing state
        instance.transition_to(WorkflowState.EXECUTING, "EXECUTING")

        # Find the failed step and resume from there
        failed_step = None
        for step in instance.definition.steps:
            execution = instance.get_step_execution(step.name)
            if execution and execution.status.value == "FAILED":
                failed_step = step.name
                break

        if not failed_step:
            return False

        # Resume from failed step
        current_index = next(
            i
            for i, step in enumerate(instance.definition.steps)
            if step.name == failed_step
        )

        for step in instance.definition.steps[current_index:]:
            success = self._execute_step(instance, step.name)

            if not success:
                retry_count = instance.get_step_retry_count(step.name)
                step_def = instance.definition.get_step(step.name)

                if retry_count < step_def.retry_max:
                    instance.transition_to(WorkflowState.RETRYING)
                    success = self._execute_step(instance, step.name)

                if not success:
                    instance.transition_to(WorkflowState.EXECUTION_FAILED)
                    return False

        # All remaining steps succeeded
        instance.transition_to(WorkflowState.COMPLETED, "COMPLETED")
        return True
