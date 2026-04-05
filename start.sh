#!/bin/sh
set -e

echo "=== Starting seed ==="
python scripts/seed.py --schema-only

echo "=== Starting server on port ${PORT:-8000} with transport ${MR_TRANSPORT:-stdio} ==="
exec python -m meeting_rooms.server
