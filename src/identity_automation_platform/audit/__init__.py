"""
Audit logging module for identity automation events.

Provides structured, SIEM-ready event logging for compliance and security monitoring.
"""

from .events import AuditEvent, EventType  # noqa: E501
from .logger import AuditLogger, get_logger, log_event

__all__ = [
    "AuditEvent",
    "EventType",
    "AuditLogger",
    "get_logger",
    "log_event",
]
