
"""Populate a Siemens-flavored campus with demo data."""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import date, timedelta
from pathlib import Path

from meeting_rooms.db import get_connection, init_db

BUILDINGS = [
    ("Innovation Tower", "Airport City, Building A"),
    ("Manufacturing Hub", "Airport City, Building B"),
    ("R&D Center", "Airport City, Building C"),
]

ROOMS = [
    # Innovation Tower — floors 1-3
    ("Huddle 1A", 1, 1, 4, ["whiteboard"]),
    ("Huddle 1B", 1, 1, 4, ["whiteboard"]),
    ("Meeting Room 2A", 1, 2, 8, ["whiteboard", "projector"]),
    ("Meeting Room 2B", 1, 2, 10, ["whiteboard", "projector"]),
    ("Board Room 3A", 1, 3, 20, ["whiteboard", "projector", "video_conf"]),
    ("Focus Room 1C", 1, 1, 2, []),
    ("Meeting Room 3B", 1, 3, 12, ["whiteboard", "video_conf"]),
    # Manufacturing Hub — floors 1-2
    ("Huddle M1", 2, 1, 4, ["whiteboard"]),
    ("Meeting Room M2", 2, 1, 8, ["whiteboard", "projector"]),
    ("Lab Meeting Room", 2, 2, 6, ["whiteboard"]),
    ("Training Room", 2, 2, 30, ["whiteboard", "projector", "video_conf"]),
    ("Huddle M3", 2, 1, 4, []),
    # R&D Center — floors 1-4
    ("Huddle R1", 3, 1, 4, ["whiteboard"]),
    ("Meeting Room R2", 3, 2, 8, ["whiteboard", "projector"]),
    ("Meeting Room R3", 3, 2, 10, ["whiteboard", "projector", "video_conf"]),
    ("Board Room R4", 3, 3, 20, ["whiteboard", "projector", "video_conf"]),
    ("Collaboration Space", 3, 1, 15, ["whiteboard", "projector"]),
    ("Quiet Room R5", 3, 4, 2, []),
    ("Workshop R6", 3, 3, 12, ["whiteboard", "video_conf"]),
    ("Huddle R7", 3, 4, 4, ["whiteboard"]),
    ("Meeting Room R8", 3, 2, 8, ["whiteboard", "projector"]),
    ("Design Lab", 3, 1, 6, ["whiteboard", "projector"]),
    ("Innovation Room", 3, 3, 16, ["whiteboard", "projector", "video_conf"]),
    ("Sprint Room R9", 3, 4, 10, ["whiteboard"]),
    ("Executive Suite", 3, 4, 8, ["whiteboard", "projector", "video_conf"]),
]

# Pre-existing bookings (relative to today)
SAMPLE_BOOKINGS = [
    (1, "alice@siemens.com", "Sprint Planning", 0, "09:00", "10:00"),
    (3, "bob@siemens.com", "Design Review", 0, "14:00", "15:30"),
    (5, "carol@siemens.com", "All-Hands", 1, "10:00", "11:00"),
    (8, "dana@siemens.com", "1:1 Sync", 0, "11:00", "11:30"),
    (10, "eve@siemens.com", "Lab Standup", 1, "09:00", "09:30"),
    (11, "frank@siemens.com", "Training Session", 2, "13:00", "16:00"),
    (14, "alice@siemens.com", "R&D Sync", 1, "10:00", "11:00"),
    (16, "bob@siemens.com", "Quarterly Review", 2, "09:00", "12:00"),
    (5, "carol@siemens.com", "Team Retro", 3, "14:00", "15:00"),
    (23, "dana@siemens.com", "Innovation Workshop", 1, "13:00", "15:00"),
]


def seed(db_path: str | Path | None = None) -> None:
    if db_path is None:
        db_path = os.getenv("MR_DB_PATH", "meeting_rooms.db")
    conn = get_connection(db_path)
    init_db(conn)

    # Check if already seeded
    count = conn.execute("SELECT COUNT(*) FROM buildings").fetchone()[0]
    if count > 0:
        print("Database already seeded. Skipping.")
        conn.close()
        return

    # Insert buildings
    for name, address in BUILDINGS:
        conn.execute(
            "INSERT INTO buildings (name, address) VALUES (?, ?)",
            (name, address),
        )

    # Insert rooms
    for name, building_id, floor, capacity, equipment in ROOMS:
        conn.execute(
            "INSERT INTO rooms (name, building_id, floor, capacity, equipment) VALUES (?, ?, ?, ?, ?)",
            (name, building_id, floor, capacity, json.dumps(equipment)),
        )

    # Insert sample bookings
    today = date.today()
    for room_id, booked_by, title, day_offset, start, end in SAMPLE_BOOKINGS:
        booking_date = today + timedelta(days=day_offset)
        conn.execute(
            "INSERT INTO bookings (room_id, booked_by, title, date, start_time, end_time) VALUES (?, ?, ?, ?, ?, ?)",
            (room_id, booked_by, title, booking_date.isoformat(), start, end),
        )

    conn.commit()
    conn.close()
    print(f"Seeded: {len(BUILDINGS)} buildings, {len(ROOMS)} rooms, {len(SAMPLE_BOOKINGS)} bookings")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--schema-only", action="store_true",
                        help="Create tables only, skip demo data")
    args = parser.parse_args()
    if args.schema_only:
        from meeting_rooms.db import get_connection, init_db
        db_path = os.getenv("MR_DB_PATH", "meeting_rooms.db")
        conn = get_connection(db_path)
        init_db(conn)
        conn.close()
        print(f"Schema initialised at {db_path}.")
    else:
        seed()