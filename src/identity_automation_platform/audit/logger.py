"""
Audit logger for structured event logging.

Logs identity automation events to JSON format suitable for:
- Compliance audit trails
- SIEM integration (ELK, Splunk, etc.)
- Security monitoring
- Troubleshooting
"""

import json
import os
from pathlib import Path
from typing import Optional
from .events import AuditEvent


class AuditLogger:
    """
    Writes structured audit events to JSON file.

    SIEM-ready format: One JSON object per line (NDJSON/JSONL).
    """

    def __init__(self, log_file: Optional[str] = None):
        """
        Initialize audit logger.

        Args:
            log_file: Path to audit log file. Defaults to 'audit.log'
        """
        self.log_file = log_file or self._default_log_path()
        self._ensure_log_directory()

    def _default_log_path(self) -> str:
        """Get default audit log path."""
        return "audit.log"

    def _ensure_log_directory(self) -> None:
        """Create log directory if it doesn't exist."""
        log_dir = Path(self.log_file).parent
        if log_dir != Path("."):
            try:
                log_dir.mkdir(parents=True, exist_ok=True)
            except (OSError, PermissionError):
                # If we can't create the directory, log to current directory
                pass

    def log_event(self, event: AuditEvent) -> None:
        """
        Write audit event to log in NDJSON format.

        Args:
            event: AuditEvent instance to log
        """
        with open(self.log_file, "a") as f:
            f.write(json.dumps(event.to_dict()) + "\n")

    def read_events(self, limit: Optional[int] = None) -> list[AuditEvent]:
        """
        Read audit events from log file.

        Args:
            limit: Maximum number of events to read (None = all)

        Returns:
            List of AuditEvent instances
        """
        events = []

        if not os.path.exists(self.log_file):
            return events

        with open(self.log_file, "r") as f:
            for i, line in enumerate(f):
                if limit and i >= limit:
                    break

                if line.strip():
                    try:
                        data = json.loads(line)
                        # Reconstruct AuditEvent from dict
                        event = AuditEvent(
                            timestamp=data.get("timestamp"),
                            event_type=data.get("event_type"),
                            actor=data.get("actor"),
                            target=data.get("target"),
                            result=data.get("result"),
                            reason=data.get("reason"),
                            metadata=data.get("metadata"),
                        )
                        events.append(event)
                    except json.JSONDecodeError:
                        # Skip malformed lines
                        continue

        return events


# Global audit logger instance
_default_logger: Optional[AuditLogger] = None


def get_logger(log_file: Optional[str] = None) -> AuditLogger:
    """
    Get or create global audit logger instance.

    Args:
        log_file: Optional custom log file path

    Returns:
        AuditLogger instance
    """
    global _default_logger

    if _default_logger is None:
        _default_logger = AuditLogger(log_file)

    return _default_logger


def log_event(event: AuditEvent) -> None:
    """
    Log an audit event using the default logger.

    Convenience function for common usage pattern.

    Args:
        event: AuditEvent instance to log
    """
    logger = get_logger()
    logger.log_event(event)
