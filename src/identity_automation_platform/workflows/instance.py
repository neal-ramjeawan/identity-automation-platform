"""
Workflow instance - a running instance of a workflow.

Tracks the execution state, context, and history of a workflow execution.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from uuid import uuid4

from .states import WorkflowState, is_valid_transition
from .definition import WorkflowDefinition, StepStatus


@dataclass
class StepExecution:
    """Record of a step execution."""

    step_name: str
    status: StepStatus
    started_at: str
    completed_at: Optional[str] = None
    error: Optional[str] = None
    retry_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class WorkflowInstance:
    """
    A running instance of a workflow.

    Attributes:
        id: Unique workflow instance ID
        definition: The workflow definition
        state: Current workflow state
        context: Workflow input/execution context
        status: Current execution status
        created_at: When instance was created
        updated_at: When instance was last updated
        step_executions: History of step executions
    """

    id: str
    definition: WorkflowDefinition
    state: WorkflowState
    context: Dict[str, Any]
    status: str = "PENDING"
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    step_executions: List[StepExecution] = field(default_factory=list)
    current_step: Optional[str] = None
    retry_count: int = 0

    @classmethod
    def create(
        cls,
        definition: WorkflowDefinition,
        context: Dict[str, Any],
    ) -> "WorkflowInstance":
        """
        Create a new workflow instance.

        Args:
            definition: Workflow definition
            context: Input context for the workflow

        Returns:
            New WorkflowInstance
        """
        return cls(
            id=str(uuid4()),
            definition=definition,
            state=WorkflowState.CREATED,
            context=context,
            status="CREATED",
        )

    def transition_to(
        self, new_state: WorkflowState, status: Optional[str] = None
    ) -> bool:
        """
        Transition workflow to a new state.

        Args:
            new_state: Target state
            status: Optional status message

        Returns:
            True if transition succeeded, False otherwise
        """
        if not is_valid_transition(self.state, new_state):
            return False

        self.state = new_state
        self.updated_at = datetime.now(timezone.utc).isoformat()

        if status:
            self.status = status

        return True

    def record_step_started(self, step_name: str) -> None:
        """Record that a step has started."""
        self.current_step = step_name
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def record_step_succeeded(self, step_name: str) -> None:
        """Record that a step succeeded."""
        execution = StepExecution(
            step_name=step_name,
            status=StepStatus.SUCCEEDED,
            started_at=self.updated_at,
            completed_at=datetime.now(timezone.utc).isoformat(),
        )
        self.step_executions.append(execution)
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def record_step_failed(
        self, step_name: str, error: str, retry_count: int = 0
    ) -> None:
        """Record that a step failed."""
        execution = StepExecution(
            step_name=step_name,
            status=StepStatus.FAILED,
            started_at=self.updated_at,
            completed_at=datetime.now(timezone.utc).isoformat(),
            error=error,
            retry_count=retry_count,
        )
        self.step_executions.append(execution)
        self.updated_at = datetime.now(timezone.utc).isoformat()
        self.retry_count = max(self.retry_count, retry_count)

    def get_step_execution(self, step_name: str) -> Optional[StepExecution]:
        """Get the latest execution of a step."""
        for execution in reversed(self.step_executions):
            if execution.step_name == step_name:
                return execution
        return None

    def get_step_retry_count(self, step_name: str) -> int:
        """Get how many times a step has been retried."""
        count = 0
        for execution in self.step_executions:
            if (
                execution.step_name == step_name
                and execution.status == StepStatus.FAILED
            ):
                count += 1
        return count

    def is_complete(self) -> bool:
        """Check if workflow execution is complete."""
        return self.state in {
            WorkflowState.COMPLETED,
            WorkflowState.VALIDATION_FAILED,
            WorkflowState.EXECUTION_FAILED,
        }

    def is_successful(self) -> bool:
        """Check if workflow executed successfully."""
        return self.state == WorkflowState.COMPLETED

    def is_failed(self) -> bool:
        """Check if workflow failed."""
        return self.state in {
            WorkflowState.VALIDATION_FAILED,
            WorkflowState.EXECUTION_FAILED,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert workflow instance to dictionary for persistence."""
        return {
            "id": self.id,
            "workflow_type": self.definition.workflow_type,
            "state": self.state.value,
            "status": self.status,
            "context": self.context,
            "current_step": self.current_step,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "retry_count": self.retry_count,
            "step_executions": [e.to_dict() for e in self.step_executions],
        }
