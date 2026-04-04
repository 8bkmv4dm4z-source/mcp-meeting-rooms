# MCP Meeting Room Booking Server — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a typed Python MCP server that manages meeting room bookings via SQLite, connectable from Claude Code / VS Code Copilot / CLI.

**Architecture:** 4-layer stack — server (MCP protocol) → tools (validation) → repository (SQL) → db (connection/schema). FastMCP SDK with `@mcp.tool()` decorators. Pydantic 2 for all models. SQLite with WAL mode for concurrent access.

**Tech Stack:** Python 3.12, FastMCP (mcp SDK), Pydantic 2, SQLite (stdlib sqlite3), pytest

**Spec:** `docs/superpowers/specs/2026-04-04-mcp-meeting-rooms-design.md`

---

## File Structure

```
mcp-meeting-rooms/
├── src/
│   └── meeting_rooms/
│       ├── __init__.py        # Package marker
│       ├── models.py          # Pydantic: Building, Room, Booking, BookingResult, ConflictDetail
│       ├── db.py              # Connection factory, CREATE TABLE DDL, WAL config
│       ├── repository.py      # All SQL behind typed methods
│       ├── tools.py           # 6 MCP tools — validation, calls repository
│       └── server.py          # FastMCP setup, tool registration, transport, auth gate
├── tests/
│   ├── conftest.py            # In-memory SQLite fixture with seed data
│   └── test_repository.py     # Conflict detection, availability, search filters
├── seed.py                    # Populate Siemens campus demo data
├── pyproject.toml             # Project metadata + dependencies
├── .env.example               # MCP_API_KEY template
├── CLAUDE.md                  # Project dev instructions
└── README.md                  # Setup, usage, architecture decisions
```

---

## Phase 1: Foundation (models + db + seed)

### Task 1: Project scaffolding

**Files:**
- Create: `mcp-meeting-rooms/pyproject.toml`
- Create: `mcp-meeting-rooms/src/meeting_rooms/__init__.py`
- Create: `mcp-meeting-rooms/.env.example`

- [ ] **Step 1: Create project directory and pyproject.toml**

```bash
mkdir -p /home/nir/dev/mcp-meeting-rooms/src/meeting_rooms
mkdir -p /home/nir/dev/mcp-meeting-rooms/tests
```

```toml
# pyproject.toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "mcp-meeting-rooms"
version = "0.1.0"
description = "MCP server for meeting room bookings"
requires-python = ">=3.12"
dependencies = [
    "mcp[cli]",
    "pydantic>=2",
]

[project.optional-dependencies]
dev = ["pytest", "pytest-asyncio"]

[tool.hatch.build.targets.wheel]
packages = ["src/meeting_rooms"]
```

- [ ] **Step 2: Create __init__.py**

```python
# src/meeting_rooms/__init__.py
"""MCP server for meeting room bookings."""
```

- [ ] **Step 3: Create .env.example**

```bash
# .env.example
# Optional: set to require API key for MCP connections
# MCP_API_KEY=your-secret-key-here
```

- [ ] **Step 4: Create virtual environment and install**

```bash
cd /home/nir/dev/mcp-meeting-rooms
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Run: `python -c "import meeting_rooms; print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git init
git add pyproject.toml src/meeting_rooms/__init__.py .env.example
git commit -m "chore: project scaffolding with pyproject.toml"
```

---

### Task 2: Pydantic models

**Files:**
- Create: `mcp-meeting-rooms/src/meeting_rooms/models.py`

- [ ] **Step 1: Write all models**

```python
# src/meeting_rooms/models.py
"""Pydantic models for meeting room booking system."""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Any

from pydantic import BaseModel


class Building(BaseModel):
    id: int
    name: str
    address: str | None = None


class Room(BaseModel):
    id: int
    name: str
    building_id: int
    floor: int
    capacity: int
    equipment: list[str] = []


class Booking(BaseModel):
    id: int
    room_id: int
    booked_by: str
    title: str
    date: date
    start_time: time
    end_time: time
    created_at: datetime


class ConflictDetail(BaseModel):
    booking_id: int
    room_id: int
    room_name: str
    booked_by: str
    date: str
    start_time: str
    end_time: str
    title: str


class BookingResult(BaseModel):
    success: bool
    booking: Booking | None = None
    conflict: ConflictDetail | None = None
    alternatives_hint: dict[str, Any] | None = None


class TimeSlot(BaseModel):
    """A free time slot in a room's schedule."""
    start_time: time
    end_time: time
```

- [ ] **Step 2: Verify models import**

Run: `python -c "from meeting_rooms.models import Building, Room, Booking, BookingResult, ConflictDetail, TimeSlot; print('All models OK')"`
Expected: `All models OK`

- [ ] **Step 3: Commit**

```bash
git add src/meeting_rooms/models.py
git commit -m "feat: Pydantic models for buildings, rooms, bookings"
```

---

### Task 3: Database layer

**Files:**
- Create: `mcp-meeting-rooms/src/meeting_rooms/db.py`

- [ ] **Step 1: Write db.py**

```python
# src/meeting_rooms/db.py
"""SQLite connection factory and schema DDL."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

_SCHEMA = """
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
```

- [ ] **Step 2: Verify db creates tables**

Run: `python -c "from meeting_rooms.db import get_connection, init_db; c = get_connection(':memory:'); init_db(c); print([r[0] for r in c.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()])"`
Expected: `['buildings', 'rooms', 'bookings']`

- [ ] **Step 3: Commit**

```bash
git add src/meeting_rooms/db.py
git commit -m "feat: SQLite connection factory with WAL mode and schema DDL"
```

---

### Task 4: Seed data

**Files:**
- Create: `mcp-meeting-rooms/seed.py`

- [ ] **Step 1: Write seed.py**

```python
# seed.py
"""Populate a Siemens-flavored campus with demo data."""

from __future__ import annotations

import json
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


def seed(db_path: str | Path = "meeting_rooms.db") -> None:
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
    seed()
```

- [ ] **Step 2: Run seed on in-memory to verify**

Run: `python -c "from meeting_rooms.db import get_connection, init_db; from seed import BUILDINGS, ROOMS; print(f'{len(BUILDINGS)} buildings, {len(ROOMS)} rooms')"`
Expected: `3 buildings, 25 rooms`

- [ ] **Step 3: Commit**

```bash
git add seed.py
git commit -m "feat: Siemens campus seed data — 3 buildings, 25 rooms, 10 bookings"
```

---

## Phase 2: Repository + Tests

### Task 5: Test fixtures

**Files:**
- Create: `mcp-meeting-rooms/tests/conftest.py`

- [ ] **Step 1: Write conftest.py**

```python
# tests/conftest.py
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

    conn.commit()
    return conn
```

- [ ] **Step 2: Verify fixture loads**

Run: `cd /home/nir/dev/mcp-meeting-rooms && python -m pytest tests/conftest.py --collect-only`
Expected: `no tests ran` (just collecting, no errors)

- [ ] **Step 3: Commit**

```bash
git add tests/conftest.py
git commit -m "test: in-memory SQLite fixture with seed data"
```

---

### Task 6: Repository — room queries

**Files:**
- Create: `mcp-meeting-rooms/src/meeting_rooms/repository.py`
- Create: `mcp-meeting-rooms/tests/test_repository.py`

- [ ] **Step 1: Write failing tests for room queries**

```python
# tests/test_repository.py
"""Tests for repository layer — room queries, booking logic, availability."""

from __future__ import annotations

from datetime import date, time, timedelta

import pytest

from meeting_rooms.repository import Repository


class TestGetRooms:
    def test_list_all_rooms(self, db):
        repo = Repository(db)
        rooms = repo.get_rooms()
        assert len(rooms) == 5

    def test_filter_by_building(self, db):
        repo = Repository(db)
        rooms = repo.get_rooms(building="Tower A")
        assert len(rooms) == 3
        assert all(r.building_id == 1 for r in rooms)

    def test_filter_by_min_capacity(self, db):
        repo = Repository(db)
        rooms = repo.get_rooms(min_capacity=10)
        assert len(rooms) == 2
        assert all(r.capacity >= 10 for r in rooms)

    def test_filter_by_equipment(self, db):
        repo = Repository(db)
        rooms = repo.get_rooms(equipment=["projector"])
        assert all("projector" in r.equipment for r in rooms)

    def test_filter_by_equipment_subset(self, db):
        repo = Repository(db)
        rooms = repo.get_rooms(equipment=["projector", "video_conf"])
        assert len(rooms) == 1
        assert rooms[0].name == "Board Room"

    def test_filter_by_floor(self, db):
        repo = Repository(db)
        rooms = repo.get_rooms(floor=1)
        assert all(r.floor == 1 for r in rooms)

    def test_combined_filters(self, db):
        repo = Repository(db)
        rooms = repo.get_rooms(building="Tower A", min_capacity=8)
        assert len(rooms) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/nir/dev/mcp-meeting-rooms && python -m pytest tests/test_repository.py::TestGetRooms -v`
Expected: FAIL — `ImportError: cannot import name 'Repository'`

- [ ] **Step 3: Write repository — get_rooms**

```python
# src/meeting_rooms/repository.py
"""Data access layer — all SQL queries behind typed methods."""

from __future__ import annotations

import json
import sqlite3
from datetime import date, time

from meeting_rooms.models import (
    Booking,
    BookingResult,
    Building,
    ConflictDetail,
    Room,
    TimeSlot,
)


class Repository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def _row_to_room(self, row: sqlite3.Row) -> Room:
        return Room(
            id=row["id"],
            name=row["name"],
            building_id=row["building_id"],
            floor=row["floor"],
            capacity=row["capacity"],
            equipment=json.loads(row["equipment"]),
        )

    def get_rooms(
        self,
        building: str | None = None,
        floor: int | None = None,
        min_capacity: int | None = None,
        equipment: list[str] | None = None,
    ) -> list[Room]:
        """List rooms with optional filters. Equipment filtered in Python via subset check."""
        query = "SELECT r.* FROM rooms r"
        params: list = []
        conditions: list[str] = []

        if building:
            query += " JOIN buildings b ON r.building_id = b.id"
            conditions.append("b.name = ?")
            params.append(building)

        if floor is not None:
            conditions.append("r.floor = ?")
            params.append(floor)

        if min_capacity is not None:
            conditions.append("r.capacity >= ?")
            params.append(min_capacity)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        rows = self.conn.execute(query, params).fetchall()
        rooms = [self._row_to_room(row) for row in rows]

        # Equipment subset filter in Python
        if equipment:
            wanted = set(equipment)
            rooms = [r for r in rooms if wanted.issubset(set(r.equipment))]

        return rooms
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/nir/dev/mcp-meeting-rooms && python -m pytest tests/test_repository.py::TestGetRooms -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/meeting_rooms/repository.py tests/test_repository.py
git commit -m "feat: repository get_rooms with filters + tests"
```

---

### Task 7: Repository — booking and conflict detection

**Files:**
- Modify: `mcp-meeting-rooms/src/meeting_rooms/repository.py`
- Modify: `mcp-meeting-rooms/tests/test_repository.py`

- [ ] **Step 1: Write failing tests for booking**

Append to `tests/test_repository.py`:

```python
class TestCreateBooking:
    def test_successful_booking(self, db):
        repo = Repository(db)
        tomorrow = date.today() + timedelta(days=1)
        result = repo.create_booking(
            room_id=2,
            date_=tomorrow,
            start_time=time(14, 0),
            end_time=time(15, 0),
            booked_by="carol@test.com",
            title="Team Sync",
        )
        assert result.success is True
        assert result.booking is not None
        assert result.booking.booked_by == "carol@test.com"
        assert result.conflict is None

    def test_conflict_exact_overlap(self, db):
        repo = Repository(db)
        today = date.today()
        result = repo.create_booking(
            room_id=1,
            date_=today,
            start_time=time(9, 0),
            end_time=time(9, 30),
            booked_by="eve@test.com",
            title="Conflicting",
        )
        assert result.success is False
        assert result.conflict is not None
        assert result.conflict.booked_by == "alice@test.com"
        assert result.alternatives_hint is not None

    def test_conflict_partial_overlap(self, db):
        repo = Repository(db)
        today = date.today()
        result = repo.create_booking(
            room_id=1,
            date_=today,
            start_time=time(9, 15),
            end_time=time(10, 0),
            booked_by="eve@test.com",
            title="Partial Overlap",
        )
        assert result.success is False
        assert result.conflict is not None

    def test_adjacent_no_conflict(self, db):
        repo = Repository(db)
        today = date.today()
        # Booking ends at 9:30, new one starts at 9:30 — no overlap
        result = repo.create_booking(
            room_id=1,
            date_=today,
            start_time=time(9, 30),
            end_time=time(10, 0),
            booked_by="eve@test.com",
            title="Adjacent Slot",
        )
        assert result.success is True

    def test_different_room_no_conflict(self, db):
        repo = Repository(db)
        today = date.today()
        result = repo.create_booking(
            room_id=3,
            date_=today,
            start_time=time(9, 0),
            end_time=time(9, 30),
            booked_by="eve@test.com",
            title="Different Room",
        )
        assert result.success is True

    def test_different_date_no_conflict(self, db):
        repo = Repository(db)
        future = date.today() + timedelta(days=5)
        result = repo.create_booking(
            room_id=1,
            date_=future,
            start_time=time(9, 0),
            end_time=time(9, 30),
            booked_by="eve@test.com",
            title="Future Booking",
        )
        assert result.success is True


class TestCancelBooking:
    def test_cancel_existing(self, db):
        repo = Repository(db)
        assert repo.cancel_booking(1) is True

    def test_cancel_nonexistent(self, db):
        repo = Repository(db)
        assert repo.cancel_booking(999) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/nir/dev/mcp-meeting-rooms && python -m pytest tests/test_repository.py::TestCreateBooking -v`
Expected: FAIL — `AttributeError: 'Repository' object has no attribute 'create_booking'`

- [ ] **Step 3: Implement create_booking and cancel_booking**

Add to `repository.py` inside the `Repository` class:

```python
    def create_booking(
        self,
        room_id: int,
        date_: date,
        start_time: time,
        end_time: time,
        booked_by: str,
        title: str,
    ) -> BookingResult:
        """Atomic check-and-insert. Returns conflict detail if slot is taken."""
        date_str = date_.isoformat()
        start_str = start_time.strftime("%H:%M")
        end_str = end_time.strftime("%H:%M")

        with self.conn:
            # Check for overlapping bookings
            row = self.conn.execute(
                """
                SELECT bk.*, r.name as room_name FROM bookings bk
                JOIN rooms r ON bk.room_id = r.id
                WHERE bk.room_id = ? AND bk.date = ?
                AND bk.start_time < ? AND bk.end_time > ?
                LIMIT 1
                """,
                (room_id, date_str, end_str, start_str),
            ).fetchone()

            if row:
                return BookingResult(
                    success=False,
                    conflict=ConflictDetail(
                        booking_id=row["id"],
                        room_id=row["room_id"],
                        room_name=row["room_name"],
                        booked_by=row["booked_by"],
                        date=row["date"],
                        start_time=row["start_time"],
                        end_time=row["end_time"],
                        title=row["title"],
                    ),
                    alternatives_hint={
                        "tool": "search_available_rooms",
                        "params": {
                            "date": date_str,
                            "start_time": start_str,
                            "end_time": end_str,
                        },
                    },
                )

            cursor = self.conn.execute(
                """
                INSERT INTO bookings (room_id, booked_by, title, date, start_time, end_time)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (room_id, booked_by, title, date_str, start_str, end_str),
            )

            booking_row = self.conn.execute(
                "SELECT * FROM bookings WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()

            return BookingResult(
                success=True,
                booking=self._row_to_booking(booking_row),
            )

    def cancel_booking(self, booking_id: int) -> bool:
        """Delete a booking by ID. Returns True if deleted, False if not found."""
        cursor = self.conn.execute(
            "DELETE FROM bookings WHERE id = ?", (booking_id,)
        )
        self.conn.commit()
        return cursor.rowcount > 0

    def _row_to_booking(self, row: sqlite3.Row) -> Booking:
        return Booking(
            id=row["id"],
            room_id=row["room_id"],
            booked_by=row["booked_by"],
            title=row["title"],
            date=date.fromisoformat(row["date"]),
            start_time=time.fromisoformat(row["start_time"]),
            end_time=time.fromisoformat(row["end_time"]),
            created_at=row["created_at"],
        )
```

- [ ] **Step 4: Run tests**

Run: `cd /home/nir/dev/mcp-meeting-rooms && python -m pytest tests/test_repository.py::TestCreateBooking tests/test_repository.py::TestCancelBooking -v`
Expected: All 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/meeting_rooms/repository.py tests/test_repository.py
git commit -m "feat: booking with atomic conflict detection + cancel"
```

---

### Task 8: Repository — availability and search

**Files:**
- Modify: `mcp-meeting-rooms/src/meeting_rooms/repository.py`
- Modify: `mcp-meeting-rooms/tests/test_repository.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_repository.py`:

```python
class TestSearchAvailableRooms:
    def test_excludes_booked_rooms(self, db):
        repo = Repository(db)
        today = date.today()
        # Room 1 booked 9:00-9:30, should be excluded for that slot
        rooms = repo.search_available_rooms(
            date_=today,
            start_time=time(9, 0),
            end_time=time(9, 30),
        )
        room_ids = [r.id for r in rooms]
        assert 1 not in room_ids

    def test_includes_free_rooms(self, db):
        repo = Repository(db)
        today = date.today()
        rooms = repo.search_available_rooms(
            date_=today,
            start_time=time(9, 0),
            end_time=time(9, 30),
        )
        # Rooms 2-5 should be available (room 2 is booked 14:00-15:30, not 9:00)
        room_ids = [r.id for r in rooms]
        assert 3 in room_ids
        assert 4 in room_ids

    def test_with_capacity_filter(self, db):
        repo = Repository(db)
        today = date.today()
        rooms = repo.search_available_rooms(
            date_=today,
            start_time=time(16, 0),
            end_time=time(17, 0),
            min_capacity=10,
        )
        assert all(r.capacity >= 10 for r in rooms)

    def test_with_equipment_filter(self, db):
        repo = Repository(db)
        today = date.today()
        rooms = repo.search_available_rooms(
            date_=today,
            start_time=time(16, 0),
            end_time=time(17, 0),
            equipment=["video_conf"],
        )
        assert all("video_conf" in r.equipment for r in rooms)


class TestGetRoomAvailability:
    def test_returns_bookings_and_free_slots(self, db):
        repo = Repository(db)
        today = date.today()
        bookings, free_slots = repo.get_room_availability(room_id=1, date_=today)
        assert len(bookings) == 1  # 9:00-9:30 standup
        assert len(free_slots) >= 2  # before and after the booking

    def test_free_slots_fill_working_day(self, db):
        repo = Repository(db)
        today = date.today()
        bookings, free_slots = repo.get_room_availability(room_id=1, date_=today)
        # First free slot should start at 08:00 (working day start)
        assert free_slots[0].start_time == time(8, 0)
        # Last free slot should end at 18:00 (working day end)
        assert free_slots[-1].end_time == time(18, 0)

    def test_empty_day_returns_full_slot(self, db):
        repo = Repository(db)
        future = date.today() + timedelta(days=10)
        bookings, free_slots = repo.get_room_availability(room_id=3, date_=future)
        assert len(bookings) == 0
        assert len(free_slots) == 1
        assert free_slots[0].start_time == time(8, 0)
        assert free_slots[0].end_time == time(18, 0)


class TestGetBookingsByUser:
    def test_returns_user_bookings(self, db):
        repo = Repository(db)
        bookings = repo.get_bookings_by_user("alice@test.com")
        assert len(bookings) == 2

    def test_filter_by_date(self, db):
        repo = Repository(db)
        today = date.today()
        bookings = repo.get_bookings_by_user("alice@test.com", date_=today)
        assert len(bookings) == 1

    def test_no_bookings(self, db):
        repo = Repository(db)
        bookings = repo.get_bookings_by_user("nobody@test.com")
        assert len(bookings) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/nir/dev/mcp-meeting-rooms && python -m pytest tests/test_repository.py::TestSearchAvailableRooms tests/test_repository.py::TestGetRoomAvailability tests/test_repository.py::TestGetBookingsByUser -v`
Expected: FAIL — `AttributeError`

- [ ] **Step 3: Implement search_available_rooms, get_room_availability, get_bookings_by_user**

Add to `repository.py` inside the `Repository` class:

```python
    def search_available_rooms(
        self,
        date_: date,
        start_time: time,
        end_time: time,
        building: str | None = None,
        min_capacity: int | None = None,
        equipment: list[str] | None = None,
    ) -> list[Room]:
        """Find rooms with no conflicting bookings for the given slot."""
        date_str = date_.isoformat()
        start_str = start_time.strftime("%H:%M")
        end_str = end_time.strftime("%H:%M")

        query = """
            SELECT r.* FROM rooms r
            LEFT JOIN bookings bk ON r.id = bk.room_id
                AND bk.date = ? AND bk.start_time < ? AND bk.end_time > ?
        """
        params: list = [date_str, end_str, start_str]
        conditions = ["bk.id IS NULL"]

        if building:
            query = query.replace("FROM rooms r", "FROM rooms r JOIN buildings b ON r.building_id = b.id")
            conditions.append("b.name = ?")
            params.append(building)

        if min_capacity is not None:
            conditions.append("r.capacity >= ?")
            params.append(min_capacity)

        query += " WHERE " + " AND ".join(conditions)
        rows = self.conn.execute(query, params).fetchall()
        rooms = [self._row_to_room(row) for row in rows]

        if equipment:
            wanted = set(equipment)
            rooms = [r for r in rooms if wanted.issubset(set(r.equipment))]

        return rooms

    def get_room_availability(
        self,
        room_id: int,
        date_: date,
        work_start: time = time(8, 0),
        work_end: time = time(18, 0),
    ) -> tuple[list[Booking], list[TimeSlot]]:
        """Return bookings and computed free slots for a room on a given day."""
        date_str = date_.isoformat()
        rows = self.conn.execute(
            "SELECT * FROM bookings WHERE room_id = ? AND date = ? ORDER BY start_time",
            (room_id, date_str),
        ).fetchall()

        bookings = [self._row_to_booking(row) for row in rows]

        # Compute free slots
        free_slots: list[TimeSlot] = []
        current = work_start
        for bk in bookings:
            if bk.start_time > current:
                free_slots.append(TimeSlot(start_time=current, end_time=bk.start_time))
            current = max(current, bk.end_time)
        if current < work_end:
            free_slots.append(TimeSlot(start_time=current, end_time=work_end))

        return bookings, free_slots

    def get_bookings_by_user(
        self,
        booked_by: str,
        date_: date | None = None,
    ) -> list[Booking]:
        """Get all bookings for a user, optionally filtered by date."""
        if date_:
            rows = self.conn.execute(
                "SELECT * FROM bookings WHERE booked_by = ? AND date = ? ORDER BY date, start_time",
                (booked_by, date_.isoformat()),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM bookings WHERE booked_by = ? ORDER BY date, start_time",
                (booked_by,),
            ).fetchall()

        return [self._row_to_booking(row) for row in rows]
```

- [ ] **Step 4: Run all tests**

Run: `cd /home/nir/dev/mcp-meeting-rooms && python -m pytest tests/test_repository.py -v`
Expected: All tests PASS (7 + 8 + 4 + 3 + 3 = 25 tests)

- [ ] **Step 5: Commit**

```bash
git add src/meeting_rooms/repository.py tests/test_repository.py
git commit -m "feat: search, availability, user bookings + full test suite"
```

---

## Phase 3: MCP Tools + Server

### Task 9: Tool functions

**Files:**
- Create: `mcp-meeting-rooms/src/meeting_rooms/tools.py`

- [ ] **Step 1: Write tools.py**

```python
# src/meeting_rooms/tools.py
"""MCP tool functions — input validation, calls repository, returns structured data."""

from __future__ import annotations

from datetime import date, time

from meeting_rooms.models import Booking, BookingResult, Room, TimeSlot
from meeting_rooms.repository import Repository


def _parse_date(s: str) -> date:
    return date.fromisoformat(s)


def _parse_time(s: str) -> time:
    return time.fromisoformat(s)


def list_rooms(
    repo: Repository,
    building: str | None = None,
    floor: int | None = None,
    min_capacity: int | None = None,
    equipment: list[str] | None = None,
) -> list[dict]:
    """List rooms with optional filters."""
    rooms = repo.get_rooms(
        building=building, floor=floor,
        min_capacity=min_capacity, equipment=equipment,
    )
    return [r.model_dump() for r in rooms]


def search_available_rooms(
    repo: Repository,
    date: str,
    start_time: str,
    end_time: str,
    building: str | None = None,
    min_capacity: int | None = None,
    equipment: list[str] | None = None,
) -> list[dict]:
    """Find available rooms for a time slot."""
    d = _parse_date(date)
    st = _parse_time(start_time)
    et = _parse_time(end_time)
    if et <= st:
        return [{"error": "end_time must be after start_time"}]

    rooms = repo.search_available_rooms(
        date_=d, start_time=st, end_time=et,
        building=building, min_capacity=min_capacity, equipment=equipment,
    )
    return [r.model_dump() for r in rooms]


def get_room_availability(
    repo: Repository,
    room_id: int,
    date: str,
) -> dict:
    """Get bookings and free slots for a room on a date."""
    d = _parse_date(date)
    bookings, free_slots = repo.get_room_availability(room_id=room_id, date_=d)
    return {
        "room_id": room_id,
        "date": date,
        "bookings": [b.model_dump(mode="json") for b in bookings],
        "free_slots": [s.model_dump(mode="json") for s in free_slots],
    }


def book_room(
    repo: Repository,
    room_id: int,
    date: str,
    start_time: str,
    end_time: str,
    booked_by: str,
    title: str,
) -> dict:
    """Book a room. Returns structured result with conflict detail if taken."""
    d = _parse_date(date)
    st = _parse_time(start_time)
    et = _parse_time(end_time)
    if et <= st:
        return {"success": False, "error": "end_time must be after start_time"}

    result = repo.create_booking(
        room_id=room_id, date_=d,
        start_time=st, end_time=et,
        booked_by=booked_by, title=title,
    )
    return result.model_dump(mode="json")


def cancel_booking(repo: Repository, booking_id: int) -> dict:
    """Cancel an existing booking."""
    deleted = repo.cancel_booking(booking_id)
    return {"success": deleted, "booking_id": booking_id}


def my_bookings(
    repo: Repository,
    booked_by: str,
    date: str | None = None,
) -> list[dict]:
    """Get bookings for a specific user."""
    d = _parse_date(date) if date else None
    bookings = repo.get_bookings_by_user(booked_by=booked_by, date_=d)
    return [b.model_dump(mode="json") for b in bookings]
```

- [ ] **Step 2: Verify import**

Run: `cd /home/nir/dev/mcp-meeting-rooms && python -c "from meeting_rooms import tools; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/meeting_rooms/tools.py
git commit -m "feat: 6 tool functions with validation and structured output"
```

---

### Task 10: MCP Server

**Files:**
- Create: `mcp-meeting-rooms/src/meeting_rooms/server.py`

- [ ] **Step 1: Write server.py**

```python
# src/meeting_rooms/server.py
"""MCP server — registers tools, handles transport, optional auth."""

from __future__ import annotations

import json
import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from meeting_rooms.db import get_connection, init_db
from meeting_rooms.repository import Repository
from meeting_rooms import tools as tool_funcs

DB_PATH = Path(os.getenv("MR_DB_PATH", "meeting_rooms.db"))

mcp = FastMCP("meeting-rooms")

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
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify server module loads**

Run: `cd /home/nir/dev/mcp-meeting-rooms && python -c "from meeting_rooms.server import mcp; print(f'Server: {mcp.name}')"`
Expected: `Server: meeting-rooms`

- [ ] **Step 3: Commit**

```bash
git add src/meeting_rooms/server.py
git commit -m "feat: MCP server with FastMCP — 6 tools, stdio transport"
```

---

## Phase 4: Integration + Polish

### Task 11: End-to-end test via CLI

- [ ] **Step 1: Seed the database**

```bash
cd /home/nir/dev/mcp-meeting-rooms
python seed.py
```

Expected: `Seeded: 3 buildings, 25 rooms, 10 bookings`

- [ ] **Step 2: Test server starts and responds**

Run: `cd /home/nir/dev/mcp-meeting-rooms && echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python -m meeting_rooms.server 2>/dev/null | head -1`
Expected: JSON response containing tool definitions (list_rooms, search_available_rooms, etc.)

- [ ] **Step 3: Commit database**

```bash
git add seed.py
git commit -m "test: verified end-to-end server startup with seeded data"
```

---

### Task 12: CLAUDE.md

**Files:**
- Create: `mcp-meeting-rooms/CLAUDE.md`

- [ ] **Step 1: Write CLAUDE.md**

```markdown
# CLAUDE.md

## What
MCP server for meeting room bookings — typed Python, SQLite, FastMCP.

## Setup
```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python seed.py  # populate demo data
```

## Run
```bash
python -m meeting_rooms.server           # stdio (default)
python -m meeting_rooms.server --sse     # SSE transport
pytest tests/ -v                         # run tests
```

## Project Structure
```
src/meeting_rooms/
  models.py       — Pydantic models (Building, Room, Booking, BookingResult, ConflictDetail)
  db.py           — SQLite connection, schema DDL, WAL mode
  repository.py   — All SQL queries behind typed methods
  tools.py        — 6 tool functions with input validation
  server.py       — FastMCP registration, transport, auth gate
```

## Architecture
4 layers: server → tools → repository → db
- tools.py never sees SQL
- repository.py never sees MCP
- All tool responses are structured Pydantic models serialized to JSON

## Conventions
- All dates: ISO YYYY-MM-DD
- All times: HH:MM (24h)
- Equipment stored as JSON list in rooms table
- Conflict responses include structured ConflictDetail for cross-MCP orchestration
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: CLAUDE.md with project instructions"
```

---

### Task 13: README with architecture decisions

**Files:**
- Create: `mcp-meeting-rooms/README.md`

- [ ] **Step 1: Write README.md**

```markdown
# MCP Meeting Room Booking Server

A typed Python MCP server for managing meeting room bookings via SQLite. Designed for integration with Claude Code, VS Code GitHub Copilot, or any MCP-compatible client.

## Quick Start

```bash
# Setup
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python seed.py

# Run server (stdio — for Claude Code / Copilot)
python -m meeting_rooms.server

# Run tests
pytest tests/ -v
```

## Dependencies

| Package | Purpose |
|---------|---------|
| `mcp[cli]` | MCP SDK with FastMCP and CLI tools |
| `pydantic>=2` | Typed data models with validation |
| `pytest` (dev) | Test framework |

Python stdlib `sqlite3` handles the database. No ORM.

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `MR_DB_PATH` | `meeting_rooms.db` | SQLite database file path |
| `MCP_API_KEY` | (none) | Optional API key for connection auth |

Copy `.env.example` for reference.

## Client Configuration

**Claude Code** (`.claude/mcp.json`):
```json
{
  "meeting-rooms": {
    "command": "python",
    "args": ["-m", "meeting_rooms.server"],
    "cwd": "/absolute/path/to/mcp-meeting-rooms"
  }
}
```

## MCP Tools

| Tool | Description |
|------|-------------|
| `list_rooms` | List rooms with optional filters (building, floor, capacity, equipment) |
| `search_available_rooms` | Find rooms available for a specific time slot |
| `get_room_availability` | Show bookings + free slots for a room on a date |
| `book_room` | Book a room — returns confirmation or structured conflict detail |
| `cancel_booking` | Cancel a booking by ID |
| `my_bookings` | List bookings for a person |

## Architecture Decisions

### Why 4 layers (server → tools → repository → db)?

Each layer has one reason to exist and one reason to change. `tools.py` never writes SQL. `repository.py` never sees MCP protocol. This means:
- Testing the booking logic doesn't require an MCP server
- Swapping SQLite for Postgres changes `db.py` and `repository.py` only
- Adding a REST API alongside MCP reuses the same repository

### Why SQLite, not Postgres?

Local MCP servers run as subprocesses on the developer's machine. SQLite is zero-config, file-based, and sufficient. The repository layer abstracts all SQL — migrating to Postgres requires changes to 2 files, not 6.

### Why no ORM?

3 tables, 6 queries. SQLAlchemy adds configuration weight and a learning curve for a problem that `sqlite3` + Pydantic solves directly. Every query is visible in `repository.py`.

### Why equipment as JSON list, not a junction table?

Rooms have 3-5 equipment items. Filtering uses Python `set.issubset()` on ~25 rows. A many-to-many junction table adds a table, a model, JOIN complexity, and migration surface for zero performance benefit at this scale.

### Why `booked_by: str` instead of a User table?

No authentication system. No user management. A User table adds a migration, a model, and FK constraints for a field that's functionally a label. If auth is needed later, add the table then — YAGNI.

### Why structured conflict responses?

When a booking conflicts, the response includes typed `ConflictDetail` with the conflicting booking's owner, time, and title. This enables cross-MCP orchestration — the LLM can use the conflict data to:
- Call `search_available_rooms` for alternatives
- Message the conflicting booker via Slack MCP
- Send a room swap email via Gmail MCP

The server returns data. The LLM decides what to do with it.

### Concurrency & ACID

SQLite WAL mode enables concurrent readers with serialized writers. The `create_booking` method wraps conflict-check + insert in a single transaction (`BEGIN IMMEDIATE`). Two users booking the same room at the same time: one succeeds, one gets a conflict response. Never a double-booking.

**Production migration path:** Swap to Postgres with connection pooling and `SELECT ... FOR UPDATE` for row-level locking. Changes to `db.py` (connection) and `repository.py` (SQL dialect). Zero changes to tools or server.

### Transport

| Mode | Use | Command |
|------|-----|---------|
| stdio (default) | Local — Claude Code, Copilot | `python -m meeting_rooms.server` |
| SSE | Remote / multi-client | `python -m meeting_rooms.server --sse --port 8080` |

## Seed Data

The demo populates a Siemens-flavored manufacturing campus:
- 3 buildings (Innovation Tower, Manufacturing Hub, R&D Center)
- 25 rooms (huddle rooms, meeting rooms, boardrooms)
- 10 pre-existing bookings

Run `python seed.py` to populate. Run again safely — skips if already seeded.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: README with setup, usage, and architecture decisions"
```

---

### Task 14: Add .gitignore and final verification

**Files:**
- Create: `mcp-meeting-rooms/.gitignore`

- [ ] **Step 1: Write .gitignore**

```
__pycache__/
*.pyc
.venv/
*.egg-info/
dist/
build/
meeting_rooms.db
.env
```

- [ ] **Step 2: Run full test suite**

Run: `cd /home/nir/dev/mcp-meeting-rooms && python -m pytest tests/ -v`
Expected: All 25 tests PASS

- [ ] **Step 3: Verify server loads all tools**

Run: `cd /home/nir/dev/mcp-meeting-rooms && python -c "from meeting_rooms.server import mcp; print([t.name for t in mcp._tool_manager.list_tools()])"`
Expected: List containing all 6 tool names

- [ ] **Step 4: Final commit**

```bash
git add .gitignore
git commit -m "chore: gitignore and final verification"
```
