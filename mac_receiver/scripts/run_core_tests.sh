#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
PY="python3"
if [ -x .venv/bin/python ]; then PY=.venv/bin/python; fi
PYTHONPATH="src${PYTHONPATH:+:$PYTHONPATH}" exec "$PY" tests/run_core_tests.py
