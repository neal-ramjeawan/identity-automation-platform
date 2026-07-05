#!/usr/bin/env python3
"""Async workflow engine example."""

import asyncio
from identity_automation_platform.workflows import WorkflowStep, WorkflowDefinition
from identity_automation_platform.workflows.async_engine import AsyncWorkflowEngine


async def async_handler(ctx):
    print(f"  → async handling {ctx.get('target_user')}")
    await asyncio.sleep(0.05)
    return True


def run_example():
    engine = AsyncWorkflowEngine(emit_events=False)

    workflow = WorkflowDefinition(
        workflow_type="ASYNC_EXAMPLE",
        name="Async Example",
        description="Example async workflow",
        steps=[
            WorkflowStep(
                name="step1", handler=async_handler, retry_max=1, timeout_seconds=5
            ),
        ],
    )

    instance = engine.create_instance(
        workflow, {"target_user": "async.user@company.com"}
    )
    res = asyncio.run(engine.execute(instance))
    print("Result:", res)


if __name__ == "__main__":
    run_example()
