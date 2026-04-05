"""
Meeting Rooms MCP — End-to-End Demo
====================================
Spawns the MCP server as a subprocess and drives a realistic booking
scenario entirely through the MCP protocol (no HTTP, no direct imports).

Scenario
--------
1. List all rooms that fit 10+ people and have a projector
2. Check availability for one of them
3. Book it for alice@siemens.com
4. Try to book the same slot for bob@siemens.com → conflict
5. Inspect the cross-MCP context (ready-to-send Slack/email payloads)
6. Book one of the suggested alternative rooms for bob instead
7. Cancel alice's booking
8. Confirm it's gone via my_bookings

Run
---
    python demo.py

Requirements: the virtualenv must be active (or use .venv/bin/python demo.py).
The server seeds/creates the database automatically on first run.
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any, TypeVar

T = TypeVar("T")

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PYTHON = str(Path(sys.executable))          # same interpreter that runs this script
SERVER_MODULE = "meeting_rooms.server"
SRC_PATH = str(Path(__file__).parent / "src")

DEMO_DATE = (date.today() + timedelta(days=1)).isoformat()   # tomorrow
ALICE = "alice@siemens.com"
BOB = "bob@siemens.com"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def banner(title: str) -> None:
    width = 60
    print(f"\n{'=' * width}")
    print(f"  {title}")
    print(f"{'=' * width}")


async def call(session: ClientSession, tool: str, result_type: type[T], **kwargs: Any) -> T:
    """Call an MCP tool and return the parsed result cast to result_type."""
    from mcp.types import TextContent
    raw = await session.call_tool(tool, arguments=kwargs)
    content = raw.content[0]
    assert isinstance(content, TextContent), f"Expected TextContent, got {type(content)}"
    parsed = json.loads(content.text)
    return parsed  # type: ignore[return-value]  — JSON structure matches T by convention


# ---------------------------------------------------------------------------
# Demo steps
# ---------------------------------------------------------------------------

async def run_demo() -> None:
    server_params = StdioServerParameters(
        command=PYTHON,
        args=["-m", SERVER_MODULE],
        env={"PYTHONPATH": SRC_PATH},
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("Connected to MCP server.\n")

            # ------------------------------------------------------------------
            # Step 1 — Find rooms that fit 10+ people with a projector
            # ------------------------------------------------------------------
            banner("Step 1 — Find large rooms with a projector")

            rooms = await call(
                session, "list_rooms", list,
                min_capacity=10,
                equipment=["projector"],
            )
            print(f"Found {len(rooms)} room(s):")
            for r in rooms:
                print(f"  [{r['id']}] {r['name']} — capacity {r['capacity']}, "
                      f"equipment: {r['equipment']}")

            target_room = rooms[0]
            room_id = target_room["id"]
            print(f"\nPicking room [{room_id}] '{target_room['name']}' for the demo.")

            # ------------------------------------------------------------------
            # Step 2 — Check what's already booked in that room tomorrow
            # ------------------------------------------------------------------
            banner(f"Step 2 — Availability for room {room_id} on {DEMO_DATE}")

            availability = await call(
                session, "get_room_availability", dict,
                room_id=room_id,
                date=DEMO_DATE,
            )
            print(f"Existing bookings: {len(availability['bookings'])}")
            for b in availability["bookings"]:
                print(f"  {b['start_time']}–{b['end_time']}  '{b['title']}'  ({b['booked_by']})")
            print(f"Free slots:        {len(availability['free_slots'])}")
            for s in availability["free_slots"]:
                print(f"  {s['start_time']}–{s['end_time']}")

            # Pick a free slot (first available)
            free = availability["free_slots"]
            if not free:
                print("\nNo free slots tomorrow — adjust seed data and re-run.")
                return
            start_time = free[0]["start_time"]
            # Book a 1-hour slot
            end_hour = int(start_time.split(":")[0]) + 1
            end_time = f"{end_hour:02d}:00"
            print(f"\nUsing slot {start_time}–{end_time} for both bookings.")

            # ------------------------------------------------------------------
            # Step 3 — Alice books the room
            # ------------------------------------------------------------------
            banner(f"Step 3 — Alice books room {room_id}")

            alice_result = await call(
                session, "book_room", dict,
                room_id=room_id,
                date=DEMO_DATE,
                start_time=start_time,
                end_time=end_time,
                booked_by=ALICE,
                title="Alice's Planning Session",
            )
            if alice_result["success"]:
                alice_booking_id = alice_result["booking"]["id"]
                print(f"Booking confirmed. ID = {alice_booking_id}")
            else:
                print(f"Unexpected conflict: {alice_result['conflict']}")
                return

            # ------------------------------------------------------------------
            # Step 4 — Bob tries the same slot → conflict
            # ------------------------------------------------------------------
            banner(f"Step 4 — Bob tries to book the same slot → conflict")

            bob_result = await call(
                session, "book_room", dict,
                room_id=room_id,
                date=DEMO_DATE,
                start_time=start_time,
                end_time=end_time,
                booked_by=BOB,
                title="Bob's Sprint Review",
            )
            if bob_result["success"]:
                print("Booked (unexpected — no conflict?)")
            else:
                conflict = bob_result["conflict"]
                print(f"Conflict detected:")
                print(f"  Room    : {conflict['room_name']}")
                print(f"  Held by : {conflict['booked_by']}")
                print(f"  Slot    : {conflict['start_time']}–{conflict['end_time']}")
                print(f"  Title   : {conflict['title']}")

            # ------------------------------------------------------------------
            # Step 5 — Inspect the cross-MCP context
            # ------------------------------------------------------------------
            banner("Step 5 — Cross-MCP context (multi-agent actions)")

            cross = bob_result.get("cross_mcp_context")
            if cross:
                print("Suggested actions for other agents:")
                for action in cross["suggested_actions"]:
                    print(f"\n  action : {action['action']}")
                    print(f"  to     : {action['recipient_name']}")
                    print(f"  msg    : {action['message'][:120]}...")
            else:
                print("No cross-MCP context returned.")

            # ------------------------------------------------------------------
            # Step 6 — Bob books an alternative room instead
            # ------------------------------------------------------------------
            banner("Step 6 — Bob books an alternative room")

            alternatives = bob_result.get("alternatives", [])
            if not alternatives:
                print("No alternatives suggested.")
            else:
                alt = alternatives[0]
                print(f"Trying alternative: [{alt['id']}] '{alt['name']}'")
                bob_booking = await call(
                    session, "book_room", dict,
                    room_id=alt["id"],
                    date=DEMO_DATE,
                    start_time=start_time,
                    end_time=end_time,
                    booked_by=BOB,
                    title="Bob's Sprint Review",
                )
                if bob_booking["success"]:
                    print(f"Bob's booking confirmed. ID = {bob_booking['booking']['id']}")
                else:
                    print("Alternative also taken — all rooms busy.")

            # ------------------------------------------------------------------
            # Step 7 — Cancel Alice's booking
            # ------------------------------------------------------------------
            banner(f"Step 7 — Cancel Alice's booking (ID {alice_booking_id})")

            cancel = await call(session, "cancel_booking", dict, booking_id=alice_booking_id)
            print(f"Cancelled: {cancel['success']}")

            # ------------------------------------------------------------------
            # Step 8 — Confirm Alice has no bookings tomorrow
            # ------------------------------------------------------------------
            banner(f"Step 8 — Verify Alice has no bookings on {DEMO_DATE}")

            alice_bookings = await call(
                session, "my_bookings", list,
                booked_by=ALICE,
                date=DEMO_DATE,
            )
            if alice_bookings:
                print(f"Still has {len(alice_bookings)} booking(s) — unexpected.")
            else:
                print("No bookings found for Alice tomorrow. All clean.")

            print(f"\n{'=' * 60}")
            print("  Demo complete.")
            print(f"{'=' * 60}\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    asyncio.run(run_demo())
