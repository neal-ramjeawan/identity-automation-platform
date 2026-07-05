#!/usr/bin/env bash
# Demo script: run tests, async example, and persistence demo
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_BIN="${ROOT_DIR}/.venv/bin"

echo "Running test suite..."
"${VENV_BIN}/pytest" -q

echo
echo "Running async example..."
"${VENV_BIN}/python3" examples/workflow_engine_async_example.py

echo
echo "Running persistence & audit demo (creates ./.workflows_demo and audit.log)..."
"${VENV_BIN}/python3" examples/demo_persist_and_audit.py

echo
echo "Artifacts created:"
ls -la .workflows_demo || true
echo "Recent audit lines:"
tail -n 5 audit.log || true
