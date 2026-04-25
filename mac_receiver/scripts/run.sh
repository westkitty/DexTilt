#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [ ! -d .venv ]; then
  echo "Missing .venv. Run ./scripts/setup.sh first." >&2
  exit 1
fi
. .venv/bin/activate
exec python -m dextilt_receiver "$@"
