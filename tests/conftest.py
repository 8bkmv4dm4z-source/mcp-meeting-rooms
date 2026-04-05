
"""Shared fixtures — in-memory SQLite with seed data."""

from __future__ import annotations

import json
import sqlite3
from datetime import date, timedelta

import pytest

from meeting_rooms.db import get_connection, init_db


@pytest.fixture
def db() -> sqlite3.Connection:
    """In-memory SQLite with schema + minimal seed data for testing."""
    conn = get_connection(":memory:")
    init_db(conn)

    conn.execute("BEGIN")

    # Seed buildings
    conn.execute("INSERT INTO buildings (name, address) VALUES (?, ?)", ("Tower A", "Address A"))
    conn.execute("INSERT INTO buildings (name, address) VALUES (?, ?)", ("Tower B", "Address B"))

    # Seed rooms
    rooms = [
        ("Huddle 1", 1, 1, 4, json.dumps(["whiteboard"])),
        ("Meeting A", 1, 2, 10, json.dumps(["whiteboard", "projector"])),
        ("Board Room", 1, 3, 20, json.dumps(["whiteboard", "projector", "video_conf"])),
        ("Huddle 2", 2, 1, 4, json.dumps([])),
        ("Meeting B", 2, 1, 8, json.dumps(["whiteboard", "projector"])),
    ]
    for name, bid, floor, cap, equip in rooms:
        conn.execute(
            "INSERT INTO rooms (name, building_id, floor, capacity, equipment) VALUES (?, ?, ?, ?, ?)",
            (name, bid, floor, cap, equip),
        )

    # Seed a couple of bookings for conflict/availability tests
    today = date.today().isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    conn.execute(
        "INSERT INTO bookings (room_id, booked_by, title, date, start_time, end_time) VALUES (?, ?, ?, ?, ?, ?)",
        (1, "alice@test.com", "Standup", today, "09:00", "09:30"),
    )
    conn.execute(
        "INSERT INTO bookings (room_id, booked_by, title, date, start_time, end_time) VALUES (?, ?, ?, ?, ?, ?)",
        (2, "bob@test.com", "Design Review", today, "14:00", "15:30"),
    )
    conn.execute(
        "INSERT INTO bookings (room_id, booked_by, title, date, start_time, end_time) VALUES (?, ?, ?, ?, ?, ?)",
        (1, "alice@test.com", "Planning", tomorrow, "10:00", "11:00"),
    )

    conn.execute("COMMIT")
    return conn
