#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="$SCRIPT_DIR/.venv/bin/python"

if [ ! -f "$PYTHON" ]; then
  echo "Virtual environment not found. Run: pip install -e '.[dev]' first."
  exit 1
fi

export PYTHONPATH="$SCRIPT_DIR/src"

npx --yes @modelcontextprotocol/inspector "$PYTHON" -m meeting_rooms.server
