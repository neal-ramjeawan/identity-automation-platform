"""
Workflow definition - the template/schema for workflows.

Defines what steps a workflow contains, their order, and how they're executed.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Callable, Optional
from enum import Enum


class StepStatus(Enum):
    """Status of a workflow step."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


@dataclass
class WorkflowStep:
    """
    Represents a single step in a workflow.

    Attributes:
        name: Unique name for this step
        handler: Callable that executes the step
        retry_max: Maximum number of retries on failure
        timeout_seconds: Step execution timeout
        description: Human-readable description
    """

    name: str
    handler: Callable
    retry_max: int = 2
    timeout_seconds: int = 300
    description: str = ""

    def __hash__(self):
        # Make it hashable despite being a dataclass with callable
        return hash(self.name)

    def __eq__(self, other):
        if not isinstance(other, WorkflowStep):
            return False
        return self.name == other.name


@dataclass
class WorkflowDefinition:
    """
    Definition of a workflow - its steps and execution order.

    Attributes:
        workflow_type: Type of workflow (CREATE_USER, etc.)
        name: Human-readable name
        description: What this workflow does
        steps: Ordered list of steps to execute
        validation_handler: Optional validation function before execution
    """

    workflow_type: str
    name: str
    description: str
    steps: List[WorkflowStep] = field(default_factory=list)
    validation_handler: Optional[Callable] = None

    def __post_init__(self):
        """Validate workflow definition."""
        if not self.steps:
            raise ValueError("Workflow must have at least one step")

        # Check for duplicate step names
        step_names = [step.name for step in self.steps]
        if len(step_names) != len(set(step_names)):
            raise ValueError("Workflow steps must have unique names")

    def get_step(self, step_name: str) -> Optional[WorkflowStep]:
        """
        Get a step by name.

        Args:
            step_name: Name of the step

        Returns:
            WorkflowStep if found, None otherwise
        """
        for step in self.steps:
            if step.name == step_name:
                return step
        return None

    def get_next_step(self, current_step_name: str) -> Optional[WorkflowStep]:
        """
        Get the next step after the given step.

        Args:
            current_step_name: Name of current step

        Returns:
            Next WorkflowStep if exists, None otherwise
        """
        try:
            current_index = next(
                i for i, step in enumerate(self.steps) if step.name == current_step_name
            )
            if current_index + 1 < len(self.steps):
                return self.steps[current_index + 1]
        except StopIteration:
            pass

        return None

    def get_first_step(self) -> WorkflowStep:
        """Get the first step in the workflow."""
        return self.steps[0]

    def is_last_step(self, step_name: str) -> bool:
        """Check if a step is the last step in the workflow."""
        if not self.steps:
            return False
        return self.steps[-1].name == step_name

    def validate_input(self, context: Dict[str, Any]) -> tuple[bool, str]:
        """
        Validate workflow input using validation handler.

        Args:
            context: Workflow context/input data

        Returns:
            Tuple of (is_valid, error_message)
        """
        if self.validation_handler is None:
            return True, ""

        try:
            result = self.validation_handler(context)
            if isinstance(result, bool):
                return result, "" if result else "Validation failed"
            elif isinstance(result, tuple):
                return result
            else:
                return bool(result), ""
        except Exception as e:
            return False, str(e)


# Standard workflow definitions

CREATE_USER_WORKFLOW = WorkflowDefinition(
    workflow_type="CREATE_USER",
    name="Create User Workflow",
    description="Provisions a new user in the identity system",
    steps=[
        WorkflowStep(
            name="validate_input",
            handler=lambda ctx: True,  # Will be overridden
            retry_max=0,
            description="Validate user input data",
        ),
        WorkflowStep(
            name="provision_ad_account",
            handler=lambda ctx: True,  # Will be overridden
            retry_max=2,
            timeout_seconds=60,
            description="Create account in Active Directory",
        ),
        WorkflowStep(
            name="create_email_account",
            handler=lambda ctx: True,  # Will be overridden
            retry_max=2,
            timeout_seconds=60,
            description="Create email account",
        ),
        WorkflowStep(
            name="add_to_groups",
            handler=lambda ctx: True,  # Will be overridden
            retry_max=1,
            timeout_seconds=30,
            description="Add user to required groups",
        ),
    ],
)

DISABLE_USER_WORKFLOW = WorkflowDefinition(
    workflow_type="DISABLE_USER",
    name="Disable User Workflow",
    description="Deactivates a user in the identity system",
    steps=[
        WorkflowStep(
            name="validate_input",
            handler=lambda ctx: True,
            retry_max=0,
            description="Validate user to disable",
        ),
        WorkflowStep(
            name="revoke_access",
            handler=lambda ctx: True,
            retry_max=2,
            description="Revoke all access tokens and sessions",
        ),
        WorkflowStep(
            name="disable_ad_account",
            handler=lambda ctx: True,
            retry_max=2,
            description="Disable Active Directory account",
        ),
        WorkflowStep(
            name="archive_data",
            handler=lambda ctx: True,
            retry_max=1,
            description="Archive user data",
        ),
    ],
)
