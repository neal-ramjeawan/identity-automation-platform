"""
Workflow persistence layer.

Handles reading and writing workflow instances to durable storage (JSON files).
Enables crash recovery and replay capability.
"""

import json
from pathlib import Path
from typing import Optional, List
from uuid import UUID

from .instance import WorkflowInstance, StepExecution
from .states import WorkflowState
from .definition import WorkflowDefinition, StepStatus


class WorkflowStore:
    """Persists workflow instances to JSON files.

    Enables durability and crash recovery.
    """

    def __init__(self, storage_dir: str | Path = ".workflows"):
        """
        Initialize workflow store.

        Args:
            storage_dir: Directory where workflow JSON files are stored.
                        Created if it doesn't exist.
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def save(self, instance: WorkflowInstance) -> None:
        """Save workflow instance to JSON file.

        Creates or updates the file: .workflows/{instance_id}.json

        Args:
            instance: WorkflowInstance to persist.
        """
        file_path = self.storage_dir / f"{instance.id}.json"

        # Serialize instance to dict
        # Note: created_at/updated_at and started_at are already ISO strings
        data = {
            "id": str(instance.id),
            "workflow_type": instance.definition.workflow_type,
            "state": instance.state.value,
            "context": instance.context,
            "created_at": instance.created_at,
            "updated_at": instance.updated_at,
            "current_step": instance.current_step,
            "retry_count": instance.retry_count,
            "status": instance.status,
            "step_executions": [
                {
                    "step_name": exec.step_name,
                    "status": exec.status.value,
                    "started_at": exec.started_at,
                    "completed_at": exec.completed_at,
                    "error": exec.error,
                    "retry_count": exec.retry_count,
                }
                for exec in instance.step_executions
            ],
        }

        # Write with indentation for readability
        with open(file_path, "w") as f:
            json.dump(data, f, indent=2)

    def load(
        self, instance_id: str | UUID, definition: WorkflowDefinition
    ) -> Optional[WorkflowInstance]:
        """
        Load workflow instance from JSON file.

        Args:
            instance_id: UUID of the workflow instance.
            definition: WorkflowDefinition (needed to restore instance).

        Returns:
            WorkflowInstance if found, None otherwise.
        """
        file_path = self.storage_dir / f"{instance_id}.json"

        if not file_path.exists():
            return None

        with open(file_path, "r") as f:
            data = json.load(f)

        # Reconstruct WorkflowInstance from persisted data
        # Note: created_at and updated_at are already ISO strings
        instance = WorkflowInstance(
            id=data["id"],
            definition=definition,
            state=WorkflowState(data["state"]),
            context=data["context"],
            status=data["status"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            step_executions=[],
            current_step=data["current_step"],
            retry_count=data["retry_count"],
        )

        # Reconstruct step executions
        # Note: started_at and completed_at are already ISO strings
        for exec_data in data["step_executions"]:
            exec = StepExecution(
                step_name=exec_data["step_name"],
                status=StepStatus(exec_data["status"]),
                started_at=exec_data["started_at"],
                completed_at=exec_data["completed_at"],
                error=exec_data["error"],
                retry_count=exec_data["retry_count"],
            )
            instance.step_executions.append(exec)

        return instance

    def load_incomplete(self, definition_map: dict) -> List[WorkflowInstance]:
        """Load all incomplete (crashed) workflow instances.

        Used for crash recovery—returns all workflows that haven't reached
        a terminal state (COMPLETED, VALIDATION_FAILED, EXECUTION_FAILED).

        Args:
            definition_map: Dict mapping workflow_type to WorkflowDefinition.
                           Example: {"CREATE_USER": CREATE_USER_WORKFLOW, ...}

        Returns:
            List of incomplete WorkflowInstance objects ready for resumption.
        """
        incomplete = []

        for file_path in self.storage_dir.glob("*.json"):
            with open(file_path, "r") as f:
                data = json.load(f)

            # Check if workflow is in a terminal state
            state = WorkflowState(data["state"])
            terminal = ["COMPLETED", "VALIDATION_FAILED", "EXECUTION_FAILED"]
            if state.value in terminal:
                continue  # Already finished, skip

            # Workflow is incomplete - load it
            workflow_type = data["workflow_type"]
            if workflow_type not in definition_map:
                # Definition not available, skip
                continue

            definition = definition_map[workflow_type]
            instance = self.load(data["id"], definition)

            if instance:
                incomplete.append(instance)

        return incomplete

    def delete(self, instance_id: str | UUID) -> None:
        """
        Delete persisted workflow file (e.g., after successful completion).

        Args:
            instance_id: UUID of the workflow instance.
        """
        file_path = self.storage_dir / f"{instance_id}.json"
        if file_path.exists():
            file_path.unlink()

    def list_all(self) -> List[str]:
        """
        List all workflow instance IDs in storage.

        Returns:
            List of instance IDs (as strings).
        """
        return [f.stem for f in self.storage_dir.glob("*.json")]

    def clear(self) -> None:
        """Delete all workflow files. Use with caution."""
        for file_path in self.storage_dir.glob("*.json"):
            file_path.unlink()
