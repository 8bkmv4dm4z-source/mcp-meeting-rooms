"""MCP server — registers tools, handles transport, optional auth."""

from __future__ import annotations

import json
import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from meeting_rooms.db import get_connection, init_db
from meeting_rooms.repository import Repository
from meeting_rooms import tools as tool_funcs

DB_PATH = Path(os.getenv("MR_DB_PATH", "meeting_rooms.db"))
TRANSPORT = os.getenv("MR_TRANSPORT", "stdio")   # "stdio" | "sse" | "streamable-http"
HOST = os.getenv("MR_HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))             # Railway injects PORT automatically

mcp = FastMCP("meeting-rooms", host=HOST, port=PORT)


@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})

# Lazy-init connection and repository
_repo: Repository | None = None


def _get_repo() -> Repository:
    global _repo
    if _repo is None:
        conn = get_connection(DB_PATH)
        init_db(conn)
        _repo = Repository(conn)
    return _repo


@mcp.tool()
def list_rooms(
    building: str | None = None,
    floor: int | None = None,
    min_capacity: int | None = None,
    equipment: list[str] | None = None,
) -> str:
    """List meeting rooms. Filter by building name, floor, minimum capacity, or required equipment (e.g. ["projector", "video_conf"])."""
    result = tool_funcs.list_rooms(
        _get_repo(), building=building, floor=floor,
        min_capacity=min_capacity, equipment=equipment,
    )
    return json.dumps(result, default=str)


@mcp.tool()
def search_available_rooms(
    date: str,
    start_time: str,
    end_time: str,
    building: str | None = None,
    min_capacity: int | None = None,
    equipment: list[str] | None = None,
) -> str:
    """Find rooms available for a specific time slot. Date as YYYY-MM-DD, times as HH:MM."""
    result = tool_funcs.search_available_rooms(
        _get_repo(), date=date, start_time=start_time, end_time=end_time,
        building=building, min_capacity=min_capacity, equipment=equipment,
    )
    return json.dumps(result, default=str)


@mcp.tool()
def get_room_availability(room_id: int, date: str) -> str:
    """Get all bookings and free time slots for a room on a specific date. Date as YYYY-MM-DD."""
    result = tool_funcs.get_room_availability(_get_repo(), room_id=room_id, date=date)
    return json.dumps(result, default=str)


@mcp.tool()
def book_room(
    room_id: int,
    date: str,
    start_time: str,
    end_time: str,
    booked_by: str,
    title: str,
) -> str:
    """Book a meeting room. Returns confirmation or conflict detail with alternatives hint. Date as YYYY-MM-DD, times as HH:MM."""
    result = tool_funcs.book_room(
        _get_repo(), room_id=room_id, date=date,
        start_time=start_time, end_time=end_time,
        booked_by=booked_by, title=title,
    )
    return json.dumps(result, default=str)


@mcp.tool()
def cancel_booking(booking_id: int) -> str:
    """Cancel an existing booking by its ID."""
    result = tool_funcs.cancel_booking(_get_repo(), booking_id=booking_id)
    return json.dumps(result, default=str)


@mcp.tool()
def my_bookings(booked_by: str, date: str | None = None) -> str:
    """List bookings for a specific person. Optionally filter by date (YYYY-MM-DD)."""
    result = tool_funcs.my_bookings(_get_repo(), booked_by=booked_by, date=date)
    return json.dumps(result, default=str)


def main():
    mcp.run(transport=TRANSPORT)  # type: ignore[arg-type]


if __name__ == "__main__":
    main()