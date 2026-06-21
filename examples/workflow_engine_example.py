#!/usr/bin/env python3
"""
Example: Workflow engine in action.

Demonstrates executing an identity workflow with state management,
step execution, retry logic, and audit integration.
"""

from identity_automation_platform.workflows import (
    WorkflowEngine,
    WorkflowDefinition,
    WorkflowStep,
)


def create_ad_account(context):
    """Simulate creating an AD account."""
    print(f"  → Creating AD account for {context.get('target_user')}")
    return True


def create_email_account(context):
    """Simulate creating an email account."""
    print(f"  → Creating email account for {context.get('target_user')}")
    return True


def add_to_groups(context):
    """Simulate adding user to groups."""
    print(f"  → Adding {context.get('target_user')} to groups")
    return True


def example_create_user():
    """Example: Execute CREATE_USER workflow."""
    print("\n" + "=" * 70)
    print("Example 1: Create User Workflow")
    print("=" * 70)

    # Create workflow engine
    engine = WorkflowEngine(emit_events=True)

    # Create a workflow instance
    context = {
        "target_user": "john.smith@company.com",
        "department": "Engineering",
        "manager": "jane.doe@company.com",
    }

    # Define the actual workflow steps
    create_user_workflow = WorkflowDefinition(
        workflow_type="CREATE_USER",
        name="Create User Workflow",
        description="Provisions a new user in the identity system",
        steps=[
            WorkflowStep(
                name="validate_input",
                handler=lambda ctx: True,
                retry_max=0,
                description="Validate user input",
            ),
            WorkflowStep(
                name="provision_ad_account",
                handler=create_ad_account,
                retry_max=2,
                description="Create AD account",
            ),
            WorkflowStep(
                name="create_email_account",
                handler=create_email_account,
                retry_max=2,
                description="Create email account",
            ),
            WorkflowStep(
                name="add_to_groups",
                handler=add_to_groups,
                retry_max=1,
                description="Add user to groups",
            ),
        ],
    )

    # Create and execute workflow instance
    instance = engine.create_instance(create_user_workflow, context)
    print(f"\nCreated workflow instance: {instance.id}")
    print(f"Initial state: {instance.state.value}")

    # Execute the workflow
    print("\nExecuting workflow steps:")
    success = engine.execute(instance)

    # Print results
    print(f"\n✓ Workflow execution: {'SUCCESS' if success else 'FAILED'}")
    print(f"Final state: {instance.state.value}")
    print(f"Step executions: {len(instance.step_executions)}")

    for execution in instance.step_executions:
        print(f"  • {execution.step_name}: {execution.status.value}")


def example_workflow_with_failure():
    """Example: Workflow with step failure and retry."""
    print("\n" + "=" * 70)
    print("Example 2: Workflow with Failure and Retry")
    print("=" * 70)

    attempt = [0]

    def flaky_handler(context):
        """Handler that fails twice then succeeds."""
        attempt[0] += 1
        print(f"  → Attempt {attempt[0]}")
        return attempt[0] >= 2  # Succeed on 2nd attempt

    engine = WorkflowEngine(emit_events=False)

    workflow = WorkflowDefinition(
        workflow_type="FLAKY_TEST",
        name="Flaky Test Workflow",
        description="Tests retry logic",
        steps=[
            WorkflowStep(
                name="validate", handler=lambda ctx: True, description="Validation"
            ),
            WorkflowStep(
                name="flaky_step",
                handler=flaky_handler,
                retry_max=2,
                description="Step that fails then succeeds",
            ),
        ],
    )

    instance = engine.create_instance(workflow, {})
    print(f"\nCreated workflow instance: {instance.id}")

    print("\nExecuting workflow with automatic retry:")
    success = engine.execute(instance)

    print(f"\n✓ Workflow execution: {'SUCCESS' if success else 'FAILED'}")
    print(f"Total step executions: {len(instance.step_executions)}")
    print(
        f"Retry count for 'flaky_step': {instance.get_step_retry_count('flaky_step')}"
    )


def example_workflow_with_validation_failure():
    """Example: Workflow with validation failure."""
    print("\n" + "=" * 70)
    print("Example 3: Workflow with Validation Failure")
    print("=" * 70)

    def validate_email(context):
        """Validate email format."""
        email = context.get("target_user", "")
        is_valid = "@" in email
        error_msg = "" if is_valid else "Invalid email format"
        return is_valid, error_msg

    engine = WorkflowEngine(emit_events=False)

    workflow = WorkflowDefinition(
        workflow_type="EMAIL_TEST",
        name="Email Validation Workflow",
        description="Tests validation failure",
        steps=[
            WorkflowStep(
                name="check_email", handler=lambda ctx: True, description="Check email"
            ),
        ],
        validation_handler=validate_email,
    )

    # Test with invalid email
    instance = engine.create_instance(workflow, {"target_user": "invalid-email"})
    print(f"\nCreated workflow instance: {instance.id}")
    print(f"Input: {instance.context}")

    print("\nExecuting workflow with invalid input:")
    success = engine.execute(instance)

    print(f"\n✗ Workflow execution: {'SUCCESS' if success else 'FAILED'}")
    print(f"Final state: {instance.state.value}")


def example_disable_user_workflow():
    """Example: DISABLE_USER workflow."""
    print("\n" + "=" * 70)
    print("Example 4: Disable User Workflow")
    print("=" * 70)

    def revoke_access(ctx):
        print(f"  → Revoking access for {ctx.get('target_user')}")
        return True

    def disable_ad_account(ctx):
        print(f"  → Disabling AD account for {ctx.get('target_user')}")
        return True

    def archive_data(ctx):
        print(f"  → Archiving data for {ctx.get('target_user')}")
        return True

    engine = WorkflowEngine(emit_events=False)

    # Create disable workflow with custom handlers
    disable_workflow = WorkflowDefinition(
        workflow_type="DISABLE_USER",
        name="Disable User Workflow",
        description="Deactivates a user",
        steps=[
            WorkflowStep(
                name="validate_input",
                handler=lambda ctx: True,
                description="Validate user",
            ),
            WorkflowStep(
                name="revoke_access",
                handler=revoke_access,
                retry_max=2,
                description="Revoke access",
            ),
            WorkflowStep(
                name="disable_ad_account",
                handler=disable_ad_account,
                retry_max=2,
                description="Disable AD",
            ),
            WorkflowStep(
                name="archive_data",
                handler=archive_data,
                retry_max=1,
                description="Archive data",
            ),
        ],
    )

    context = {
        "target_user": "terminated.employee@company.com",
        "termination_reason": "voluntary",
        "offboarding_ticket": "SEC-2024-001234",
    }

    instance = engine.create_instance(disable_workflow, context)
    print(f"\nCreated workflow instance: {instance.id}")
    print(f"User: {context['target_user']}")

    print("\nExecuting disable user workflow:")
    success = engine.execute(instance)

    print(f"\n✓ Workflow execution: {'SUCCESS' if success else 'FAILED'}")
    print(f"Steps executed: {len(instance.step_executions)}")


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("IDENTITY WORKFLOW ENGINE - EXAMPLES")
    print("=" * 70)

    # Run examples
    example_create_user()
    example_workflow_with_failure()
    example_workflow_with_validation_failure()
    example_disable_user_workflow()

    print("\n" + "=" * 70)
    print("All examples completed!")
    print("=" * 70 + "\n")
