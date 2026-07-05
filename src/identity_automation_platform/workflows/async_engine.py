"""
Asynchronous Workflow Engine (Phase 3 groundwork).

Provides an async-compatible WorkflowEngine that supports coroutine handlers,
per-step timeouts, and the same persistence/audit integration hooks as the
synchronous engine. This is intentionally minimal: it mirrors the sync engine's
semantics but exposes async APIs to enable future concurrency and approval
mechanisms.
"""

import asyncio
import inspect
from typing import Any, Dict, Optional

from .definition import WorkflowDefinition
from .instance import WorkflowInstance
from .states import WorkflowState
from .store import WorkflowStore

from identity_automation_platform.audit import AuditEvent, EventType, log_event


class AsyncWorkflowEngine:
    """Async workflow engine.

    Methods mirror the synchronous `WorkflowEngine` but are coroutines.
    """

    def __init__(self, emit_events: bool = True, store: Optional[WorkflowStore] = None):
        self.emit_events = emit_events
        self.store = store

    async def _call_handler(
        self, handler, context, timeout: Optional[int] = None
    ) -> Any:
        """Call a handler that may be sync or async; support timeout."""

        # Wrap sync call into coroutine
        async def _wrap():
            if inspect.iscoroutinefunction(handler):
                return await handler(context)
            else:
                result = handler(context)
                if inspect.isawaitable(result):
                    return await result
                return result

        if timeout is not None:
            return await asyncio.wait_for(_wrap(), timeout=timeout)
        return await _wrap()

    def create_instance(
        self, definition: WorkflowDefinition, context: Dict[str, Any]
    ) -> WorkflowInstance:
        instance = WorkflowInstance.create(definition, context)
        if self.store:
            self.store.save(instance)

        if self.emit_events:
            event = AuditEvent.create(
                event_type=EventType.VALIDATION_PASSED,
                actor="async-workflow-engine",
                target=context.get("target_user", "unknown"),
                result="SUCCESS",
                reason=f"Async workflow instance created: {definition.name}",
                metadata={
                    "workflow_id": instance.id,
                    "workflow_type": definition.workflow_type,
                },
            )
            log_event(event)

        return instance

    async def validate(self, instance: WorkflowInstance) -> tuple[bool, str]:
        # Support async or sync validation handler
        is_valid, error_msg = instance.definition.validate_input(instance.context)

        if is_valid:
            instance.transition_to(WorkflowState.VALIDATION_PENDING)
            instance.transition_to(WorkflowState.VALIDATED)
            if self.store:
                self.store.save(instance)
            if self.emit_events:
                event = AuditEvent.create(
                    event_type=EventType.VALIDATION_PASSED,
                    actor="async-workflow-engine",
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
                    actor="async-workflow-engine",
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

    async def _execute_step(self, instance: WorkflowInstance, step_name: str) -> bool:
        step_def = instance.definition.get_step(step_name)
        if not step_def:
            return False

        instance.record_step_started(step_name)

        try:
            result = await self._call_handler(
                step_def.handler, instance.context, timeout=step_def.timeout_seconds
            )
            if result:
                instance.record_step_succeeded(step_name)
                if self.store:
                    self.store.save(instance)
                return True
            else:
                instance.record_step_failed(step_name, "Step handler returned False")
                if self.store:
                    self.store.save(instance)
                return False

        except asyncio.TimeoutError:
            msg = f"Step '{step_name}' timed out after {step_def.timeout_seconds}s"
            instance.record_step_failed(step_name, msg)
            if self.store:
                self.store.save(instance)
            return False

        except Exception as e:
            err = str(e)
            retry_count = instance.get_step_retry_count(step_name)
            instance.record_step_failed(step_name, err, retry_count)
            if self.store:
                self.store.save(instance)
            return False

    async def execute(self, instance: WorkflowInstance) -> bool:
        is_valid, _ = await self.validate(instance)
        if not is_valid:
            return False

        instance.transition_to(WorkflowState.EXECUTING, "EXECUTING")
        if self.store:
            self.store.save(instance)

        for step in instance.definition.steps:
            success = await self._execute_step(instance, step.name)

            if not success:
                retry_count = instance.get_step_retry_count(step.name)
                step_def = instance.definition.get_step(step.name)

                if retry_count < step_def.retry_max:
                    instance.transition_to(WorkflowState.RETRYING, "RETRYING")
                    if self.store:
                        self.store.save(instance)
                    success = await self._execute_step(instance, step.name)

                if not success:
                    instance.transition_to(
                        WorkflowState.EXECUTION_FAILED, "EXECUTION_FAILED"
                    )
                    if self.store:
                        self.store.save(instance)
                    if self.emit_events:
                        event = AuditEvent.create(
                            event_type=EventType.CREATE_USER_FAILED,
                            actor="async-workflow-engine",
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

        instance.transition_to(WorkflowState.COMPLETED, "COMPLETED")
        if self.store:
            self.store.delete(instance.id)
        if self.emit_events:
            event = AuditEvent.create(
                event_type=EventType.CREATE_USER,
                actor="async-workflow-engine",
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

    async def resume(self, instance: WorkflowInstance) -> bool:
        if not instance.is_failed():
            return False

        instance.transition_to(WorkflowState.EXECUTING, "EXECUTING")
        if self.store:
            self.store.save(instance)

        failed_step = None
        for step in instance.definition.steps:
            execution = instance.get_step_execution(step.name)
            if execution and execution.status.value == "FAILED":
                failed_step = step.name
                break

        if not failed_step:
            # Nothing to resume
            return False

        # Execute from failed step onwards
        start_index = next(
            i for i, s in enumerate(instance.definition.steps) if s.name == failed_step
        )
        for step in instance.definition.steps[start_index:]:
            success = await self._execute_step(instance, step.name)
            if not success:
                return False

        instance.transition_to(WorkflowState.COMPLETED, "COMPLETED")
        if self.store:
            self.store.delete(instance.id)
        return True
