# identity-automation-platform

Enterprise-grade identity automation system with structured audit logging, state machine workflows, and persistence layer for crash recovery.

## Repository Structure

```
src/identity_automation_platform/
├── audit/              # Structured audit logging and event tracking
├── directory/          # Directory integration layer (LDAP, AD, etc.)
├── validation/         # User request validation and schema checking
└── workflows/          # State machine-based workflow orchestration
    ├── states.py       # State machine definition
    ├── definition.py   # Workflow templates and steps
    ├── instance.py     # Runtime workflow state
    ├── engine.py       # Orchestration engine
    └── store.py        # Persistence layer (Phase 2)
tests/
├── test_audit.py       # Audit logging tests
├── test_validation.py  # Validation tests
├── test_workflows.py   # Workflow engine tests
└── test_workflows_persistence.py  # Persistence tests
examples/
├── audit_logging_example.py        # Audit logging usage
├── workflow_engine_example.py       # Workflow execution
└── crash_recovery_example.py        # Crash recovery (Phase 2)
```

## Features

### 🔍 **Audit Logging System**

Structured, SIEM-ready event logging in NDJSON format:
- Event types: CREATE_USER, DISABLE_USER, RESET_PASSWORD, SUSPEND_ACCOUNT, etc.
- Automatic timestamp and metadata capture
- Integration with ELK, Splunk, and other SIEM platforms

### 🔄 **Workflow Engine (Phase 1)**

State machine-based workflow orchestration with:
- Explicit state transitions (CREATED → VALIDATED → EXECUTING → COMPLETED)
- Step-by-step execution with automatic retry logic
- Failure handling and recovery
- Audit event emission for compliance tracking
- Support for validation, provisioning, and deprovisioning workflows

### 💾 **Persistence Layer (Phase 2)**

Durable workflow storage for crash recovery:
- JSON-based persistence to `.workflows/` directory
- Automatic saves after state transitions and step completions
- Load incomplete workflows to find crashed instances
- Resume execution from last completed step
- Enable "what happened at 3am?" audit reconstruction

### ✅ **User Validation**

Structured input validation for identity operations:
- Required field validation
- Schema checking
- Error reporting

## Installation

```bash
pip install .
```

## Running Tests

```bash
pytest -v
```

## Running Examples

```bash
# Audit logging examples
python examples/audit_logging_example.py

# Workflow engine examples  
python examples/workflow_engine_example.py

# Crash recovery and persistence examples (Phase 2)
python examples/crash_recovery_example.py
```

## Quick Demo (for reviewers)

Run the bundled demo script which runs tests, the async example, and the
persistence/audit demo that leaves artifacts for inspection:

```bash
./demo.sh
```

Artifacts produced by the demo:
- `./.workflows_demo/` — persisted workflow JSON files
- `audit.log` — NDJSON audit events


## Development

```bash
# Install in development mode
pip install . --force-reinstall --no-deps

# Or for rapid iteration
PYTHONPATH=src pytest
```

## Architecture

The platform is organized around three core layers:

1. **Validation Layer** — Input validation and schema checking
2. **Workflow Engine** — State machine execution with step management
3. **Audit Layer** — Structured event emission for compliance and debugging

### Phase 1 (Complete)

- ✅ State machine workflow engine
- ✅ Step execution with automatic retry
- ✅ Event-driven audit logging (NDJSON format)
- ✅ In-memory workflow execution
- ✅ 55 tests passing

### Phase 2 (Complete)

- ✅ Persistence layer (WorkflowStore)
- ✅ Crash recovery capability
- ✅ Resume from incomplete workflows
- ✅ Load/save/delete operations
- ✅ 13 new tests (68 total)

### Phase 3+ (Future)

- Async/await support for concurrent execution
- Approval gates and manual intervention
- Workflow timeouts and cancellation
- Distributed execution across multiple nodes
- LDAP/AD directory integration
- FastAPI service layer

## Testing

### Phase 1: Workflow Engine
- 15 audit logging tests
- 2 validation tests
- 38 workflow engine tests
- **55 tests passing**

### Phase 2: Persistence Layer
- 13 persistence tests (save, load, resume, crash recovery)
- **68 tests total passing** in <0.05s

## Key Design Decisions

### Event-First Architecture
Events are first-class domain objects, not logging bolted on. The workflow engine automatically emits audit events on every state transition.

### Deterministic State Machine
Explicit state transitions prevent invalid state sequences. All state changes are validated before execution.

### Synchronous Execution (Phase 1)
Workflows run to completion in a single call to `engine.execute()`. Phase 3 will add async support.

### JSON Persistence
Workflows are persisted to `.workflows/{instance_id}.json` files for durability and crash recovery. Format is human-readable and compatible with log aggregation systems.

## Usage Example

```python
from identity_automation_platform.workflows import (
    WorkflowEngine,
    WorkflowStore,
    CREATE_USER_WORKFLOW,
)

# Enable persistence
store = WorkflowStore(".workflows")
engine = WorkflowEngine(emit_events=True, store=store)

# Create and execute
context = {"target_user": "john@company.com", "department": "Engineering"}
instance = engine.create_instance(CREATE_USER_WORKFLOW, context)
success = engine.execute(instance)

# After crash, recover incomplete workflows
definition_map = {"CREATE_USER": CREATE_USER_WORKFLOW}
incomplete = store.load_incomplete(definition_map)
for workflow in incomplete:
    # Resume execution
    engine.execute(workflow)
```
