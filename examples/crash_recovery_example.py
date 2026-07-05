#!/usr/bin/env python3
"""
Example: Crash recovery with workflow persistence.

Demonstrates the durability and recovery capabilities of the workflow engine
with the persistence layer. Shows:

1. Persisting workflows to disk as they execute
2. Simulating a crash (process exit)
3. Recovering incomplete workflows from disk
4. Resuming execution from where it crashed
"""

import time
from pathlib import Path

from identity_automation_platform.workflows import (
    WorkflowEngine,
    WorkflowState,
    CREATE_USER_WORKFLOW,
)
from identity_automation_platform.workflows.store import WorkflowStore


def simulate_slow_step(context):
    """Simulate a slow/flaky step that might fail mid-execution."""
    print("  ➜ Processing {}".format(context.get("target_user")))
    time.sleep(0.5)  # Simulate work
    return True


def example_crash_recovery():
    """
    Example: Simulating a crash and recovery.

    This demonstrates the persistence layer's crash recovery capability.
    """
    print("\n" + "=" * 70)
    print("Example: Crash Recovery with Persistence")
    print("=" * 70)

    # Storage directory for workflows
    storage_dir = "./.workflows_recovery_example"
    store = WorkflowStore(storage_dir)

    # Create engine with persistence enabled
    engine = WorkflowEngine(emit_events=False, store=store)

    # --- PHASE 1: Initial execution (with simulated crash) ---
    print("\n[PHASE 1] Starting workflow execution...")

    context = {
        "target_user": "john.doe@company.com",
        "department": "Engineering",
    }

    instance = engine.create_instance(CREATE_USER_WORKFLOW, context)
    print("✓ Created workflow instance: {}".format(instance.id))
    print("  Storage: {}/{}.json".format(storage_dir, instance.id))

    # Validate
    print("\n[PHASE 1] Validating input...")
    engine.validate(instance)
    print("✓ Validation passed, state: {}".format(instance.state.value))

    # Start execution but "crash" mid-way
    print("\n[PHASE 1] Starting execution (will crash after 2 steps)...")
    instance.transition_to(WorkflowState.EXECUTING, "EXECUTING")
    if store:
        store.save(instance)

    # Execute first step
    instance.record_step_started("validate_input")
    instance.record_step_succeeded("validate_input")
    print("✓ Step 1 succeeded: validate_input")
    if store:
        store.save(instance)

    # Execute second step
    instance.record_step_started("provision_ad_account")
    instance.record_step_succeeded("provision_ad_account")
    print("✓ Step 2 succeeded: provision_ad_account")
    if store:
        store.save(instance)

    # CRASH HAPPENS HERE (in real scenario, process would exit)
    print("\n⚠️  CRASH SIMULATION: Process exits here")
    # Keep the printed line under 88 characters by splitting path
    _wf_path = "{}/{}.json".format(storage_dir, instance.id)
    print("   Incomplete workflow saved to: {}".format(_wf_path))
    print("   Current state: {}".format(instance.state.value))
    print("   Completed steps: {}".format(len(instance.step_executions)))

    # --- PHASE 2: Crash recovery ---
    print("\n" + "-" * 70)
    print("\n[PHASE 2] System restarted, loading incomplete workflows...")

    # Simulate process restart: create fresh store
    recovered_store = WorkflowStore(storage_dir)

    # Load all incomplete workflows
    definition_map = {"CREATE_USER": CREATE_USER_WORKFLOW}
    incomplete = recovered_store.load_incomplete(definition_map)

    print("✓ Found {} incomplete workflow(s)".format(len(incomplete)))

    if not incomplete:
        print("ERROR: No incomplete workflows found!")
        return

    # Get the first incomplete workflow
    recovered = incomplete[0]
    print("\n[PHASE 2] Recovering workflow: {}".format(recovered.id))
    print("  State: {}".format(recovered.state.value))
    print("  Completed steps: {}".format(len(recovered.step_executions)))
    for exec in recovered.step_executions:
        print("    • {}: {}".format(exec.step_name, exec.status.value))

    # --- PHASE 3: Resume execution ---
    print("\n[PHASE 3] Resuming execution from step 3...")

    # Continue execution from where we left off
    # The engine would normally skip completed steps, but for this example
    # we'll manually execute the remaining steps
    remaining_steps = ["create_email_account", "add_to_groups"]

    for step_name in remaining_steps:

        print("\n  ➜ Executing: {}".format(step_name))

        recovered.record_step_started(step_name)
        # Simulate step execution
        simulate_slow_step(recovered.context)
        recovered.record_step_succeeded(step_name)

        # Save after each step
        recovered_store.save(recovered)
        print("  ✓ Step succeeded, state saved")

    # Mark as complete
    recovered.transition_to(WorkflowState.COMPLETED, "COMPLETED")
    recovered_store.delete(recovered.id)  # Clean up completed workflow

    print("\n✓ Workflow recovery complete!")
    print("  Final state: {}".format(recovered.state.value))
    print("  Total steps: {}".format(len(recovered.step_executions)))
    print("  Workflow file deleted (cleanup for completed workflows)")


def example_persistence_durability():
    """
    Example: Persistence and durability guarantees.

    Shows that workflow state is persisted and survives restarts.
    """
    print("\n" + "=" * 70)
    print("Example: Persistence Durability")
    print("=" * 70)

    storage_dir = "./.workflows_durability_example"
    store = WorkflowStore(storage_dir)
    engine = WorkflowEngine(emit_events=False, store=store)

    # Create and partially execute a workflow
    context = {"target_user": "alice.smith@company.com", "department": "HR"}
    instance = engine.create_instance(CREATE_USER_WORKFLOW, context)

    print("\n[Step 1] Created workflow: {}".format(instance.id))

    # Simulate partial execution
    instance.transition_to(WorkflowState.VALIDATION_PENDING)
    instance.transition_to(WorkflowState.VALIDATED)
    instance.transition_to(WorkflowState.EXECUTING)
    instance.record_step_started("validate_input")
    instance.record_step_succeeded("validate_input")

    store.save(instance)
    print("[Step 2] Persisted workflow state")
    print("  State: {}".format(instance.state.value))
    print("  Executed steps: {}".format(len(instance.step_executions)))

    # "Restart" - load the instance back
    loaded = store.load(instance.id, CREATE_USER_WORKFLOW)
    print("\n[Step 3] Loaded workflow after 'restart'")
    print("  Verified state matches:")
    exp_state = "EXECUTING"
    print("    • State: {} (expected: {})".format(loaded.state.value, exp_state))
    print("    • Context: {}".format(loaded.context))
    print("    • Step history: {} steps".format(len(loaded.step_executions)))

    assert loaded.state == instance.state, "State should match"
    assert loaded.context == instance.context, "Context should match"
    assert len(loaded.step_executions) == len(
        instance.step_executions
    ), "Step history should match"

    print("\n✓ Durability verified: state survived restart")


def example_load_incomplete_workflows():
    """
    Example: Loading incomplete workflows for recovery.

    Shows how to find all workflows that need recovery after a crash.
    """
    print("\n" + "=" * 70)
    print("Example: Loading Incomplete Workflows")
    print("=" * 70)

    storage_dir = "./.workflows_incomplete_example"
    store = WorkflowStore(storage_dir)
    engine = WorkflowEngine(emit_events=False, store=store)

    # Create several workflows in different states
    print("\n[Setup] Creating workflows in various states...")

    # Workflow 1: EXECUTING (incomplete)
    ctx1 = {"target_user": "user1@company.com"}
    inst1 = engine.create_instance(CREATE_USER_WORKFLOW, ctx1)
    inst1.transition_to(WorkflowState.EXECUTING)
    store.save(inst1)
    _msg = "  • Workflow 1: {} (state: EXECUTING - INCOMPLETE)".format(inst1.id)
    print(_msg)

    # Workflow 2: COMPLETED (should not be loaded)
    ctx2 = {"target_user": "user2@company.com"}
    inst2 = engine.create_instance(CREATE_USER_WORKFLOW, ctx2)
    inst2.transition_to(WorkflowState.VALIDATION_PENDING)
    inst2.transition_to(WorkflowState.VALIDATED)
    inst2.transition_to(WorkflowState.EXECUTING)
    inst2.transition_to(WorkflowState.COMPLETED)
    store.save(inst2)
    _msg = "  • Workflow 2: {} (state: COMPLETED - will skip)".format(inst2.id)
    print(_msg)

    # Workflow 3: VALIDATION_PENDING (incomplete)
    ctx3 = {"target_user": "user3@company.com"}
    inst3 = engine.create_instance(CREATE_USER_WORKFLOW, ctx3)
    inst3.transition_to(WorkflowState.VALIDATION_PENDING)
    store.save(inst3)
    _msg = "  • Workflow 3: {} (state: VALIDATION_PENDING - INCOMPLETE)".format(
        inst3.id
    )
    print(_msg)

    # Load only incomplete
    definition_map = {"CREATE_USER": CREATE_USER_WORKFLOW}
    incomplete = store.load_incomplete(definition_map)

    print("\n✓ Found {} incomplete workflows (out of 3)".format(len(incomplete)))
    for inst in incomplete:
        print("  • {}... state: {}".format(inst.id[:8], inst.state.value))

    assert len(incomplete) == 2, "Should find exactly 2 incomplete workflows"
    assert inst1.id in [i.id for i in incomplete], "Should find workflow 1"
    assert inst3.id in [i.id for i in incomplete], "Should find workflow 3"

    print("\n✓ Incomplete workflow detection verified")


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("WORKFLOW PERSISTENCE - CRASH RECOVERY EXAMPLES")
    print("=" * 70)

    try:
        # Run examples
        example_crash_recovery()
        example_persistence_durability()
        example_load_incomplete_workflows()

        print("\n" + "=" * 70)
        print("All examples completed successfully!")
        print("=" * 70 + "\n")

    finally:
        # Cleanup
        for storage_dir in [
            "./.workflows_recovery_example",
            "./.workflows_durability_example",
            "./.workflows_incomplete_example",
        ]:
            if Path(storage_dir).exists():
                import shutil

                shutil.rmtree(storage_dir)
