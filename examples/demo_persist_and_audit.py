#!/usr/bin/env python3
"""Small demo to create a persisted workflow and emit an audit event.

Leaves artifacts in `./.workflows_demo/` and `audit.log` for inspection.
"""
from identity_automation_platform.workflows import (
    CREATE_USER_WORKFLOW,
    WorkflowEngine,
    WorkflowState,
)
from identity_automation_platform.workflows.store import WorkflowStore
from identity_automation_platform.audit.logger import get_logger
from identity_automation_platform.audit.events import AuditEvent, EventType


def run_demo():
    storage_dir = "./.workflows_demo"
    store = WorkflowStore(storage_dir)
    engine = WorkflowEngine(emit_events=True, store=store)

    ctx = {"target_user": "demo.user@company.com", "department": "IT"}
    instance = engine.create_instance(CREATE_USER_WORKFLOW, ctx)
    print("Created instance:", instance.id)
    print("Persisted to:", f"{storage_dir}/{instance.id}.json")

    # Simulate partial execution: mark first step succeeded and save
    instance.transition_to(WorkflowState.VALIDATION_PENDING)
    instance.transition_to(WorkflowState.VALIDATED)
    instance.transition_to(WorkflowState.EXECUTING)
    instance.record_step_started("validate_input")
    instance.record_step_succeeded("validate_input")
    store.save(instance)

    print("Saved partial execution (1 step completed).")

    # Emit an audit event directly
    event = AuditEvent.create(
        event_type=EventType.CREATE_USER,
        actor="demo-script",
        target=ctx["target_user"],
        result="IN_PROGRESS",
        reason="Demo persisted workflow created",
        metadata={"workflow_id": str(instance.id)},
    )
    get_logger().log_event(event)
    print("Wrote audit event to audit.log")

    print("Demo complete — artifacts left in ./.workflows_demo and audit.log")


if __name__ == "__main__":
    run_demo()
