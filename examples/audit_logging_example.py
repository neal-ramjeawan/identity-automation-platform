#!/usr/bin/env python3
"""
Example: Using the audit logging system in the identity automation platform.

This demonstrates how to integrate structured audit logging into your workflows
and validation layers for compliance, security, and troubleshooting.
"""

from identity_automation_platform.audit import AuditEvent, EventType, log_event
from identity_automation_platform.validation.validator import validate_user_request


def example_create_user_workflow():
    """Example: Create user with audit logging."""

    # User request
    user_request = {
        "username": "jsmith",
        "firstname": "John",
        "lastname": "Smith",
        "department": "Engineering",
    }

    try:
        # Validate user
        validate_user_request(user_request)

        # Log validation success
        event = AuditEvent.create(
            event_type=EventType.VALIDATION_PASSED,
            actor="admin@company.com",
            target=user_request["username"],
            result="SUCCESS",
            reason="User validation passed all checks",
            metadata={
                "department": user_request.get("department"),
                "action": "create_user",
            },
        )
        log_event(event)

        # TODO: Create user in directory (LDAP, AD, etc.)
        # directory_service.create_user(user_request)

        # Log user creation
        event = AuditEvent.create(
            event_type=EventType.CREATE_USER,
            actor="admin@company.com",
            target=user_request["username"],
            result="SUCCESS",
            reason="User account created successfully",
            metadata={
                "department": user_request.get("department"),
                "firstname": user_request.get("firstname"),
                "lastname": user_request.get("lastname"),
            },
        )
        log_event(event)

        print(f"✓ User {user_request['username']} created successfully")

    except ValueError as e:
        # Log validation failure
        event = AuditEvent.create(
            event_type=EventType.VALIDATION_FAILED,
            actor="admin@company.com",
            target=user_request.get("username", "unknown"),
            result="FAILURE",
            reason=str(e),
            metadata={"action": "create_user"},
        )
        log_event(event)

        print(f"✗ User creation failed: {e}")


def example_reset_password_workflow():
    """Example: Reset password with audit logging."""

    actor = "jsmith@company.com"
    target = "msmith@company.com"

    try:
        # TODO: Perform password reset in directory
        # directory_service.reset_password(target)

        # Log successful password reset
        event = AuditEvent.create(
            event_type=EventType.RESET_PASSWORD,
            actor=actor,
            target=target,
            result="SUCCESS",
            reason="Password reset completed via self-service portal",
        )
        log_event(event)

        print(f"✓ Password reset for {target}")

    except Exception as e:
        # Log reset failure
        event = AuditEvent.create(
            event_type=EventType.RESET_PASSWORD_FAILED,
            actor=actor,
            target=target,
            result="FAILURE",
            reason=str(e),
        )
        log_event(event)

        print(f"✗ Password reset failed: {e}")


def example_suspend_account_workflow():
    """Example: Suspend account with audit logging."""

    actor = "security@company.com"
    target = "terminated.user@company.com"

    try:
        # TODO: Suspend account in directory
        # directory_service.suspend_account(target)

        event = AuditEvent.create(
            event_type=EventType.SUSPEND_ACCOUNT,
            actor=actor,
            target=target,
            result="SUCCESS",
            reason="Account suspended due to employee termination",
            metadata={
                "termination_reason": "end_of_employment",
                "ticket_id": "SEC-2024-001234",
            },
        )
        log_event(event)

        print(f"✓ Account {target} suspended")

    except Exception as e:
        event = AuditEvent.create(
            event_type=EventType.SUSPEND_ACCOUNT_FAILED,
            actor=actor,
            target=target,
            result="FAILURE",
            reason=str(e),
        )
        log_event(event)

        print(f"✗ Account suspension failed: {e}")


def example_read_audit_log():
    """Example: Read audit log entries."""

    from identity_automation_platform.audit import get_logger

    logger = get_logger(log_file="audit.log")

    print("\n=== Audit Log (last 5 events) ===\n")

    # Read all events
    events = logger.read_events()

    # Display last 5
    for event in events[-5:]:
        ts = event.timestamp
        et = event.event_type
        ac = event.actor
        tg = event.target
        res = event.result
        print(f"{ts} | {et:25s} | {ac:20s} | {tg:20s} | {res}")
        if event.reason:
            print(f"  → {event.reason}")
        if event.metadata:
            print(f"  → metadata: {event.metadata}")
        print()


if __name__ == "__main__":
    print("=== Identity Automation Platform - Audit Logging Examples ===\n")

    print("1. Create User Workflow")
    print("-" * 50)
    example_create_user_workflow()

    print("\n2. Reset Password Workflow")
    print("-" * 50)
    example_reset_password_workflow()

    print("\n3. Suspend Account Workflow")
    print("-" * 50)
    example_suspend_account_workflow()

    # Show audit log
    example_read_audit_log()
