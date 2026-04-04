"""SQLite connection factory and schema DDL."""


from __future__ import annotations

import json
import sqlite3
from pathlib import Path

_SCHEMA="""
CREATE TABLE IF NOT EXISTS buildings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    address TEXT
);

CREATE TABLE IF NOT EXISTS rooms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    building_id INTEGER NOT NULL REFERENCES buildings(id),
    floor INTEGER NOT NULL,
    capacity INTEGER NOT NULL,
    equipment TEXT NOT NULL DEFAULT '[]',
    UNIQUE(building_id, name)
);

CREATE TABLE IF NOT EXISTS bookings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id INTEGER NOT NULL REFERENCES rooms(id),
    booked_by TEXT NOT NULL,
    title TEXT NOT NULL,
    date TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK(start_time < end_time)
);

CREATE INDEX IF NOT EXISTS idx_bookings_room_date ON bookings(room_id, date);
CREATE INDEX IF NOT EXISTS idx_bookings_user ON bookings(booked_by);


    """
def get_connection(db_path: str | Path = "meeting_rooms.db") -> sqlite3.Connection:
    """Create a configured SQLite connection."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Create tables and indexes if they don't exist."""
    conn.executescript(_SCHEMA)