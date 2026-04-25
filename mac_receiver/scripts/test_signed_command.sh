#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
PY="python3"
if [ -x .venv/bin/python ]; then
  PY=.venv/bin/python
fi
exec "$PY" scripts/test_signed_command.py "$@"
