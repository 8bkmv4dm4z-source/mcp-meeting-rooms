"""Simple CLI client to call MCP tools on the remote server."""

import asyncio
import json
import sys

from mcp.client.session import ClientSession
from mcp.client.sse import sse_client

SERVER_URL = "https://web-production-e9fc5.up.railway.app/sse"


async def call_tool(tool_name: str, arguments: dict):
    async with sse_client(SERVER_URL) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments)
            for content in result.content:
                print(content.text)


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/cli_client.py <tool_name> [json_args]")
        print()
        print("Examples:")
        print('  python scripts/cli_client.py list_rooms')
        print('  python scripts/cli_client.py list_rooms \'{"min_capacity": 7, "equipment": ["projector"]}\'')
        print('  python scripts/cli_client.py search_available_rooms \'{"date": "2026-08-28", "start_time": "14:00", "end_time": "15:00"}\'')
        print('  python scripts/cli_client.py book_room \'{"room_id": 5, "date": "2026-08-28", "start_time": "14:00", "end_time": "15:00", "booked_by": "nir@siemens.com", "title": "Demo"}\'')
        print('  python scripts/cli_client.py my_bookings \'{"booked_by": "nir@siemens.com"}\'')
        print('  python scripts/cli_client.py cancel_booking \'{"booking_id": 1}\'')
        sys.exit(1)

    tool_name = sys.argv[1]
    arguments = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}

    asyncio.run(call_tool(tool_name, arguments))


if __name__ == "__main__":
    main()
