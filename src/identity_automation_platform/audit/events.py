"""
Audit event types and event definition for identity automation.

These events represent identity operations that require audit trail tracking
for compliance, security, and troubleshooting purposes.
"""

from enum import Enum
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional, Dict, Any


class EventType(Enum):
    """Identity automation event types."""

    # User creation events
    CREATE_USER = "CREATE_USER"
    CREATE_USER_FAILED = "CREATE_USER_FAILED"

    # User deletion/deactivation events
    DISABLE_USER = "DISABLE_USER"
    DISABLE_USER_FAILED = "DISABLE_USER_FAILED"

    # Password management events
    RESET_PASSWORD = "RESET_PASSWORD"
    RESET_PASSWORD_FAILED = "RESET_PASSWORD_FAILED"

    # Account status events
    SUSPEND_ACCOUNT = "SUSPEND_ACCOUNT"
    SUSPEND_ACCOUNT_FAILED = "SUSPEND_ACCOUNT_FAILED"

    # Validation events
    VALIDATION_PASSED = "VALIDATION_PASSED"
    VALIDATION_FAILED = "VALIDATION_FAILED"


@dataclass
class AuditEvent:
    """
    Represents a single audit event in the identity automation system.

    Attributes:
        timestamp: ISO 8601 formatted timestamp when event occurred
        event_type: Type of identity event (see EventType enum)
        actor: User/system that triggered the event
        target: User/resource affected by the event
        result: "SUCCESS" or "FAILURE"
        reason: Brief explanation of what happened or why it failed
        metadata: Additional context (optional)
    """

    timestamp: str
    event_type: str
    actor: str
    target: str
    result: str
    reason: str
    metadata: Optional[Dict[str, Any]] = None

    @classmethod
    def create(
        cls,
        event_type: EventType,
        actor: str,
        target: str,
        result: str,
        reason: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "AuditEvent":
        """
        Create an audit event with automatic timestamp.

        Args:
            event_type: EventType enum value
            actor: User/system that triggered the event
            target: User/resource affected
            result: "SUCCESS" or "FAILURE"
            reason: Description of the event
            metadata: Optional additional context

        Returns:
            AuditEvent instance
        """
        return cls(
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type=event_type.value,
            actor=actor,
            target=target,
            result=result,
            reason=reason,
            metadata=metadata or {},
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for JSON serialization."""
        return asdict(self)
