#!/usr/bin/env bash
# Simple CLI for calling meeting-rooms MCP tools over SSE.
# Requires: python3 + httpx (pip install httpx)
#
# Usage:
#   ./cli.sh <tool_name> [json_arguments]
#
# Examples:
#   ./cli.sh list_rooms
#   ./cli.sh list_rooms '{"building": "R&D Center"}'
#   ./cli.sh search_available_rooms '{"date": "2026-04-25", "start_time": "09:00", "end_time": "10:00"}'
#   ./cli.sh book_room '{"room_id": 3, "date": "2026-04-25", "start_time": "14:00", "end_time": "15:00", "booked_by": "nir@example.com", "title": "Standup"}'
#   ./cli.sh get_room_availability '{"room_id": 5, "date": "2026-04-25"}'
#   ./cli.sh my_bookings '{"booked_by": "nir@example.com"}'
#   ./cli.sh cancel_booking '{"booking_id": 12}'
#
# Environment:
#   MCP_URL  — override the server base URL (default: Railway hosted instance)

set -euo pipefail

BASE_URL="${MCP_URL:-https://web-production-e9fc5.up.railway.app}"
TOOL="${1:?Usage: ./cli.sh <tool_name> [json_arguments]}"
ARGS="${2:-\{\}}"

exec python3 -c "
import asyncio, json, sys
try:
    import httpx
except ImportError:
    print('Error: httpx required. Install with: pip install httpx', file=sys.stderr)
    sys.exit(1)

BASE = '$BASE_URL'
TOOL = '$TOOL'
ARGS = json.loads('''$ARGS''')

async def read_sse(resp, q):
    event = None
    async for line in resp.aiter_lines():
        line = line.strip()
        if line.startswith('event: '): event = line[7:]
        elif line.startswith('data: '):
            if event == 'endpoint': await q.put(('e', line[6:]))
            elif event == 'message': await q.put(('m', json.loads(line[6:])))
            event = None

async def main():
    async with httpx.AsyncClient(timeout=30) as c:
        q = asyncio.Queue()
        async with c.stream('GET', f'{BASE}/sse') as sse:
            reader = asyncio.create_task(read_sse(sse, q))
            _, path = await asyncio.wait_for(q.get(), timeout=10)
            url = f'{BASE}{path}'

            await c.post(url, json={'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2024-11-05','capabilities':{},'clientInfo':{'name':'cli','version':'1.0'}}})
            await asyncio.wait_for(q.get(), timeout=10)
            await c.post(url, json={'jsonrpc':'2.0','method':'notifications/initialized'})

            await c.post(url, json={'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':TOOL,'arguments':ARGS}})
            _, resp = await asyncio.wait_for(q.get(), timeout=10)

            if 'error' in resp:
                print(json.dumps(resp['error'], indent=2))
                sys.exit(1)

            for block in resp.get('result',{}).get('content',[]):
                text = block.get('text','')
                try:
                    print(json.dumps(json.loads(text), indent=2))
                except (json.JSONDecodeError, TypeError):
                    print(text)

            reader.cancel()

asyncio.run(main())
"
