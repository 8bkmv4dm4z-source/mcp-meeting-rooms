#!/bin/sh
set -e

mkdir -p "$(dirname "${MR_DB_PATH:-meeting_rooms.db}")"

echo "=== Starting seed ==="
python scripts/seed.py

echo "=== Starting server on port ${PORT:-8000} with transport ${MR_TRANSPORT:-stdio} ==="
exec python -u -m meeting_rooms.server
