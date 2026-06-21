"""Tests for audit logging system."""

import json
import os
import tempfile
import pytest
from identity_automation_platform.audit import (
    AuditEvent,
    EventType,
    AuditLogger,
    get_logger,
    log_event,
)


class TestAuditEvent:
    """Tests for AuditEvent class."""

    def test_create_user_success_event(self):
        """Test creating a successful user creation event."""
        event = AuditEvent.create(
            event_type=EventType.CREATE_USER,
            actor="admin@company.com",
            target="john.doe@company.com",
            result="SUCCESS",
            reason="User account created for new employee",
            metadata={"department": "Engineering", "manager": "jane.smith@company.com"},
        )

        assert event.event_type == "CREATE_USER"
        assert event.actor == "admin@company.com"
        assert event.target == "john.doe@company.com"
        assert event.result == "SUCCESS"
        assert event.metadata["department"] == "Engineering"
        assert event.timestamp  # Should have ISO timestamp

    def test_create_validation_failed_event(self):
        """Test creating a validation failure event."""
        event = AuditEvent.create(
            event_type=EventType.VALIDATION_FAILED,
            actor="api-client",
            target="invalid.user@",
            result="FAILURE",
            reason="Invalid email format",
        )

        assert event.event_type == "VALIDATION_FAILED"
        assert event.result == "FAILURE"
        assert event.metadata == {}

    def test_event_to_dict(self):
        """Test converting event to dictionary."""
        event = AuditEvent.create(
            event_type=EventType.RESET_PASSWORD,
            actor="user@company.com",
            target="user@company.com",
            result="SUCCESS",
            reason="User requested password reset",
        )

        event_dict = event.to_dict()

        assert isinstance(event_dict, dict)
        assert event_dict["event_type"] == "RESET_PASSWORD"
        assert event_dict["actor"] == "user@company.com"
        assert event_dict["result"] == "SUCCESS"
        assert "timestamp" in event_dict


class TestAuditLogger:
    """Tests for AuditLogger class."""

    def test_log_event_creates_file(self):
        """Test that logging creates the audit file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "audit.log")
            logger = AuditLogger(log_file)

            event = AuditEvent.create(
                event_type=EventType.CREATE_USER,
                actor="admin",
                target="user@company.com",
                result="SUCCESS",
                reason="Test event",
            )

            logger.log_event(event)

            assert os.path.exists(log_file)

    def test_log_event_ndjson_format(self):
        """Test that events are logged in NDJSON (one JSON per line) format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "audit.log")
            logger = AuditLogger(log_file)

            events = [
                AuditEvent.create(
                    event_type=EventType.CREATE_USER,
                    actor="admin",
                    target=f"user{i}@company.com",
                    result="SUCCESS",
                    reason="Test event",
                )
                for i in range(3)
            ]

            for event in events:
                logger.log_event(event)

            # Verify NDJSON format: one valid JSON per line
            with open(log_file) as f:
                lines = f.readlines()

            assert len(lines) == 3
            for line in lines:
                data = json.loads(line)  # Should not raise
                assert "event_type" in data
                assert "timestamp" in data

    def test_read_events(self):
        """Test reading events back from log file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "audit.log")
            logger = AuditLogger(log_file)

            original_events = [
                AuditEvent.create(
                    event_type=EventType.CREATE_USER,
                    actor="admin",
                    target=f"user{i}@company.com",
                    result="SUCCESS",
                    reason=f"Created user {i}",
                )
                for i in range(3)
            ]

            for event in original_events:
                logger.log_event(event)

            # Read back
            read_events = logger.read_events()

            assert len(read_events) == 3
            assert read_events[0].target == "user0@company.com"
            assert read_events[2].target == "user2@company.com"
            assert all(isinstance(e, AuditEvent) for e in read_events)

    def test_read_events_with_limit(self):
        """Test reading limited number of events."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "audit.log")
            logger = AuditLogger(log_file)

            for i in range(5):
                event = AuditEvent.create(
                    event_type=EventType.CREATE_USER,
                    actor="admin",
                    target=f"user{i}@company.com",
                    result="SUCCESS",
                    reason="Test",
                )
                logger.log_event(event)

            # Read only 2 events
            events = logger.read_events(limit=2)
            assert len(events) == 2

    def test_read_events_nonexistent_file(self):
        """Test reading from non-existent log file returns empty list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "nonexistent.log")
            logger = AuditLogger(log_file)
            events = logger.read_events()
            assert events == []

    def test_malformed_json_line_skipped(self):
        """Test that malformed JSON lines are skipped gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "audit.log")
            logger = AuditLogger(log_file)

            # Write valid event
            event1 = AuditEvent.create(
                event_type=EventType.CREATE_USER,
                actor="admin",
                target="user1@company.com",
                result="SUCCESS",
                reason="Test",
            )
            logger.log_event(event1)

            # Write malformed JSON directly
            with open(log_file, "a") as f:
                f.write("this is not valid json\n")

            # Write another valid event
            event2 = AuditEvent.create(
                event_type=EventType.CREATE_USER,
                actor="admin",
                target="user2@company.com",
                result="SUCCESS",
                reason="Test",
            )
            logger.log_event(event2)

            # Should skip malformed line and read valid ones
            events = logger.read_events()
            assert len(events) == 2
            assert events[0].target == "user1@company.com"
            assert events[1].target == "user2@company.com"


class TestEventTypes:
    """Tests for EventType enum."""

    def test_all_event_types_exist(self):
        """Test that all expected event types are defined."""
        expected = {
            "CREATE_USER",
            "CREATE_USER_FAILED",
            "DISABLE_USER",
            "DISABLE_USER_FAILED",
            "RESET_PASSWORD",
            "RESET_PASSWORD_FAILED",
            "SUSPEND_ACCOUNT",
            "SUSPEND_ACCOUNT_FAILED",
            "VALIDATION_PASSED",
            "VALIDATION_FAILED",
        }

        actual = {e.value for e in EventType}
        assert actual == expected

    def test_event_type_values(self):
        """Test that event type values are properly formatted."""
        for event_type in EventType:
            # All uppercase, no spaces
            assert event_type.value == event_type.value.upper()
            assert " " not in event_type.value


class TestGlobalLogger:
    """Tests for global logger convenience functions."""

    def test_get_logger_singleton(self):
        """Test that get_logger returns same instance."""
        # Reset for testing
        import identity_automation_platform.audit.logger as logger_module

        logger_module._default_logger = None

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.log")

            logger1 = get_logger(log_file)
            logger2 = get_logger()

            # Should be same instance
            assert logger1 is logger2

    def test_log_event_convenience_function(self):
        """Test log_event convenience function."""
        import identity_automation_platform.audit.logger as logger_module

        logger_module._default_logger = None

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.log")
            get_logger(log_file)

            event = AuditEvent.create(
                event_type=EventType.CREATE_USER,
                actor="admin",
                target="test@company.com",
                result="SUCCESS",
                reason="Test",
            )

            log_event(event)

            logger = get_logger()
            events = logger.read_events()

            assert len(events) == 1
            assert events[0].target == "test@company.com"
