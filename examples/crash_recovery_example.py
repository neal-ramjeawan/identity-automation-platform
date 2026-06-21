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
    print(f"  ➜ Processing {context.get('target_user')}")
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
    print(f"✓ Created workflow instance: {instance.id}")
    print(f"  Storage: {storage_dir}/{instance.id}.json")

    # Validate
    print("\n[PHASE 1] Validating input...")
    engine.validate(instance)
    print(f"✓ Validation passed, state: {instance.state.value}")

    # Start execution but "crash" mid-way
    print("\n[PHASE 1] Starting execution (will crash after 2 steps)...")
    instance.transition_to(WorkflowState.EXECUTING, "EXECUTING")
    if store:
        store.save(instance)

    # Execute first step
    step1 = instance.definition.get_step("validate_input")
    instance.record_step_started("validate_input")
    instance.record_step_succeeded("validate_input")
    print(f"✓ Step 1 succeeded: validate_input")
    if store:
        store.save(instance)

    # Execute second step
    step2 = instance.definition.get_step("provision_ad_account")
    instance.record_step_started("provision_ad_account")
    instance.record_step_succeeded("provision_ad_account")
    print(f"✓ Step 2 succeeded: provision_ad_account")
    if store:
        store.save(instance)

    # CRASH HAPPENS HERE (in real scenario, process would exit)
    print("\n⚠️  CRASH SIMULATION: Process exits here")
    print(f"   Incomplete workflow saved to: {storage_dir}/{instance.id}.json")
    print(f"   Current state: {instance.state.value}")
    print(f"   Completed steps: {len(instance.step_executions)}")

    crashed_instance_id = str(instance.id)

    # --- PHASE 2: Crash recovery ---
    print("\n" + "-" * 70)
    print("\n[PHASE 2] System restarted, loading incomplete workflows...")

# Simulate process restart: create fresh store
    recovered_store = WorkflowStore(storage_dir)

    # Load all incomplete workflows
    definition_map = {"CREATE_USER": CREATE_USER_WORKFLOW}
    incomplete = recovered_store.load_incomplete(definition_map)

    print(f"✓ Found {len(incomplete)} incomplete workflow(s)")

    if not incomplete:
        print("ERROR: No incomplete workflows found!")
        return

    # Get the first incomplete workflow
    recovered = incomplete[0]
    print(f"\n[PHASE 2] Recovering workflow: {recovered.id}")
    print(f"  State: {recovered.state.value}")
    print(f"  Completed steps: {len(recovered.step_executions)}")
    for exec in recovered.step_executions:
        print(f"    • {exec.step_name}: {exec.status.value}")

    # --- PHASE 3: Resume execution ---
    print("\n[PHASE 3] Resuming execution from step 3...")

    # Continue execution from where we left off
    # The engine would normally skip completed steps, but for this example
    # we'll manually execute the remaining steps
    remaining_steps = ["create_email_account", "add_to_groups"]

    for step_name in remaining_steps:

        print(f"\n  ➜ Executing: {step_name}")

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

    print(f"\n✓ Workflow recovery complete!")
    print(f"  Final state: {recovered.state.value}")
    print(f"  Total steps: {len(recovered.step_executions)}")
    print(f"  Workflow file deleted (cleanup for completed workflows)")


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

    print(f"\n[Step 1] Created workflow: {instance.id}")

    # Simulate partial execution
    instance.transition_to(WorkflowState.VALIDATION_PENDING)
    instance.transition_to(WorkflowState.VALIDATED)
    instance.transition_to(WorkflowState.EXECUTING)
    instance.record_step_started("validate_input")
    instance.record_step_succeeded("validate_input")

    store.save(instance)
    print(f"[Step 2] Persisted workflow state")
    print(f"  State: {instance.state.value}")
    print(f"  Executed steps: {len(instance.step_executions)}")

    # "Restart" - load the instance back
    loaded = store.load(instance.id, CREATE_USER_WORKFLOW)
    print("\n[Step 3] Loaded workflow after 'restart'")
    print("  Verified state matches:")
    exp_state = "EXECUTING"
    print(f"    • State: {loaded.state.value} (expected: {exp_state})")
    print(f"    • Context: {loaded.context}")
    print(f"    • Step history: {len(loaded.step_executions)} steps")

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
    print(f"  • Workflow 1: {inst1.id} (state: EXECUTING - INCOMPLETE)")

    # Workflow 2: COMPLETED (should not be loaded)
    ctx2 = {"target_user": "user2@company.com"}
    inst2 = engine.create_instance(CREATE_USER_WORKFLOW, ctx2)
    inst2.transition_to(WorkflowState.VALIDATION_PENDING)
    inst2.transition_to(WorkflowState.VALIDATED)
    inst2.transition_to(WorkflowState.EXECUTING)
    inst2.transition_to(WorkflowState.COMPLETED)
    store.save(inst2)
    print(f"  • Workflow 2: {inst2.id} (state: COMPLETED - will skip)")

    # Workflow 3: VALIDATION_PENDING (incomplete)
    ctx3 = {"target_user": "user3@company.com"}
    inst3 = engine.create_instance(CREATE_USER_WORKFLOW, ctx3)
    inst3.transition_to(WorkflowState.VALIDATION_PENDING)
    store.save(inst3)
    print(f"  • Workflow 3: {inst3.id} (state: VALIDATION_PENDING - INCOMPLETE)")

    # Load only incomplete
    definition_map = {"CREATE_USER": CREATE_USER_WORKFLOW}
    incomplete = store.load_incomplete(definition_map)

    print(f"\n✓ Found {len(incomplete)} incomplete workflows (out of 3)")
    for inst in incomplete:
        print(f"  • {inst.id[:8]}... state: {inst.state.value}")

    assert len(incomplete) == 2, "Should find exactly 2 incomplete workflows"
    assert inst1.id in [i.id for i in incomplete], "Should find workflow 1"
    assert inst3.id in [i.id for i in incomplete], "Should find workflow 3"

    print(f"\n✓ Incomplete workflow detection verified")


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
