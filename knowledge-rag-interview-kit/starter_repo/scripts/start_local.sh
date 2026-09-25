#!/bin/sh
set -eu

PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PYTHON="$PROJECT_DIR/.venv/bin/python"
if [ ! -x "$PYTHON" ]; then
  echo "Missing virtual environment. In $PROJECT_DIR run: python -m venv .venv && .venv/bin/python -m pip install -e ." >&2
  exit 1
fi

cd "$PROJECT_DIR"
exec "$PYTHON" scripts/local_control.py
