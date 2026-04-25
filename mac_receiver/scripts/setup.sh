#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON_BIN="${PYTHON_BIN:-python3}"
"$PYTHON_BIN" - <<'PY'
import sys
if sys.version_info < (3, 10):
    raise SystemExit('DexTilt Mac Receiver requires Python 3.10 or newer.')
print('Python OK:', sys.version.split()[0])
PY
if [ ! -d .venv ]; then
  "$PYTHON_BIN" -m venv .venv
fi
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
mkdir -p "$HOME/.dextilt/logs"
if [ ! -f "$HOME/.dextilt/config.json" ]; then
  cp config.example.json "$HOME/.dextilt/config.json"
  echo "Created $HOME/.dextilt/config.json"
else
  echo "Using existing $HOME/.dextilt/config.json"
fi
echo "DexTilt Mac Receiver setup complete. Run ./scripts/run.sh"
