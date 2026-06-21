"""
Workflow states and transition rules.

Defines the state machine model for identity automation workflows,
including valid state transitions for different workflow types.
"""

from enum import Enum
from typing import Set, Dict


class WorkflowState(Enum):
    """Possible states in an identity workflow."""

    # Initial states
    CREATED = "CREATED"
    VALIDATION_PENDING = "VALIDATION_PENDING"

    # Success path
    VALIDATED = "VALIDATED"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"

    # Failure path
    VALIDATION_FAILED = "VALIDATION_FAILED"
    EXECUTION_FAILED = "EXECUTION_FAILED"

    # Retry state
    RETRYING = "RETRYING"


class WorkflowType(Enum):
    """Types of identity workflows."""

    CREATE_USER = "CREATE_USER"
    DISABLE_USER = "DISABLE_USER"
    RESET_PASSWORD = "RESET_PASSWORD"
    SUSPEND_ACCOUNT = "SUSPEND_ACCOUNT"


# State transition rules: which states can transition to which
# Key: current state, Value: set of valid next states
VALID_TRANSITIONS: Dict[WorkflowState, Set[WorkflowState]] = {
    WorkflowState.CREATED: {
        WorkflowState.VALIDATION_PENDING,
    },
    WorkflowState.VALIDATION_PENDING: {
        WorkflowState.VALIDATED,
        WorkflowState.VALIDATION_FAILED,
    },
    WorkflowState.VALIDATED: {
        WorkflowState.EXECUTING,
    },
    WorkflowState.EXECUTING: {
        WorkflowState.COMPLETED,
        WorkflowState.EXECUTION_FAILED,
    },
    WorkflowState.EXECUTION_FAILED: {
        WorkflowState.RETRYING,
    },
    WorkflowState.RETRYING: {
        WorkflowState.EXECUTING,
        WorkflowState.EXECUTION_FAILED,
    },
    WorkflowState.VALIDATION_FAILED: {
        # Terminal state, no transitions
    },
    WorkflowState.COMPLETED: {
        # Terminal state, no transitions
    },
}


# Workflow type to initial state
INITIAL_STATES: Dict[WorkflowType, WorkflowState] = {
    WorkflowType.CREATE_USER: WorkflowState.CREATED,
    WorkflowType.DISABLE_USER: WorkflowState.CREATED,
    WorkflowType.RESET_PASSWORD: WorkflowState.CREATED,
    WorkflowType.SUSPEND_ACCOUNT: WorkflowState.CREATED,
}


def is_valid_transition(
    current_state: WorkflowState,
    next_state: WorkflowState,
) -> bool:
    """
    Check if a state transition is valid.

    Args:
        current_state: Current workflow state
        next_state: Desired next state

    Returns:
        True if transition is valid, False otherwise
    """
    if current_state not in VALID_TRANSITIONS:
        return False

    return next_state in VALID_TRANSITIONS[current_state]


def is_terminal_state(state: WorkflowState) -> bool:
    """
    Check if a state is terminal (no further transitions possible).

    Args:
        state: Workflow state

    Returns:
        True if state is terminal, False otherwise
    """
    return len(VALID_TRANSITIONS.get(state, set())) == 0


def is_success_state(state: WorkflowState) -> bool:
    """
    Check if a state represents successful completion.

    Args:
        state: Workflow state

    Returns:
        True if state is successful terminal state, False otherwise
    """
    return state == WorkflowState.COMPLETED


def is_failure_state(state: WorkflowState) -> bool:
    """
    Check if a state represents a failure.

    Args:
        state: Workflow state

    Returns:
        True if state is a failure state, False otherwise
    """
    return state in {
        WorkflowState.VALIDATION_FAILED,
        WorkflowState.EXECUTION_FAILED,
    }
