#!/usr/bin/env bash
set -euo pipefail
PORT="${DEXTILT_PORT:-47391}"
curl -fsS "http://127.0.0.1:${PORT}/health" | python3 -m json.tool
