#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [[ -f .env ]]; then set -a; source .env; set +a; fi
export PYTHONPATH="${ROOT}/scripts"
PYTHON="${ROOT}/.venv/bin/python3"
if [[ ! -x "$PYTHON" ]]; then
  PYTHON=python3
fi
exec "$PYTHON" -m telegram_ops
