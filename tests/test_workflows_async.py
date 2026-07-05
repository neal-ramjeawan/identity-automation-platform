"""Async workflow engine tests."""

import asyncio

from identity_automation_platform.workflows import (
    WorkflowDefinition,
    WorkflowStep,
)
from identity_automation_platform.workflows.async_engine import AsyncWorkflowEngine


def test_async_execute_simple_workflow():
    engine = AsyncWorkflowEngine(emit_events=False)

    # Use a tiny workflow
    workflow = WorkflowDefinition(
        workflow_type="ASYNC_TEST",
        name="Async Test Workflow",
        description="Simple async workflow",
        steps=[WorkflowStep(name="one", handler=lambda ctx: True, retry_max=0)],
    )

    instance = engine.create_instance(workflow, {})
    res = asyncio.run(engine.execute(instance))
    assert res
    assert instance.is_successful()


def test_async_retry_logic():
    engine = AsyncWorkflowEngine(emit_events=False)

    attempt = {"n": 0}

    def flaky(ctx):
        attempt["n"] += 1
        return attempt["n"] >= 2

    workflow = WorkflowDefinition(
        workflow_type="ASYNC_RETRY",
        name="Async Retry Workflow",
        description="Retry logic",
        steps=[WorkflowStep(name="flaky", handler=flaky, retry_max=2)],
    )

    instance = engine.create_instance(workflow, {})
    res = asyncio.run(engine.execute(instance))
    assert res
    assert instance.get_step_retry_count("flaky") == 1


def test_async_timeout():
    engine = AsyncWorkflowEngine(emit_events=False)

    async def slow(ctx):
        await asyncio.sleep(0.1)
        return True

    # Set timeout very small to trigger
    workflow = WorkflowDefinition(
        workflow_type="ASYNC_TIMEOUT",
        name="Async Timeout",
        description="Timeout handling",
        steps=[WorkflowStep(name="slow", handler=slow, retry_max=0, timeout_seconds=0)],
    )

    instance = engine.create_instance(workflow, {})
    res = asyncio.run(engine.execute(instance))
    assert not res
    assert instance.is_failed()
