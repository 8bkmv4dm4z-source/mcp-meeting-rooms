# MCP Meeting Room Booking Server — Design Spec

**Date:** 2026-04-04
**Status:** Approved
**Context:** Siemens interview preparation — demonstrate MCP, Spec-Driven Development, typed Python

---

## 1. Purpose

A local MCP server that manages meeting room bookings via SQLite. Clients (Claude Code, VS Code Copilot, CLI) interact through MCP protocol to query availability, book rooms, and manage reservations.

This is not a web application. It is a tool server — the LLM is the interface, the server is the data layer.

## 2. Architecture

### 2.1 Layer Diagram

```
MCP Client (Claude Code / VS Code Copilot / CLI)
    ↓ stdio or SSE transport (MCP protocol)
server.py       — Transport & auth gate
    ↓ function calls
tools.py        — Tool definitions, input validation, response formatting
    ↓ function calls
repository.py   — Data access, all SQL queries, returns typed models
    ↓ SQL
db.py           — Connection factory, schema DDL, WAL configuration
    ↓
SQLite file
```

### 2.2 Layer Responsibilities

| Layer | Responsibility | Why it's separate |
|-------|---------------|-------------------|
| `server.py` | MCP protocol, tool registration, optional API key check | Protocol concerns isolated. Swapping stdio→SSE is a 3-line change here, zero changes elsewhere. |
| `tools.py` | Input validation (JSON strings → typed Python), calls repository, formats structured responses | The "what does this tool do" layer. No SQL, no protocol. System boundary where untrusted MCP input becomes clean typed data. |
| `repository.py` | SQL queries, returns Pydantic models. Joins across tables as needed. | Single source of truth for data access. Test SQL logic without MCP overhead. Swap SQLite→Postgres here only. |
| `db.py` | SQLite connection, `CREATE TABLE` DDL, WAL mode, pragma config | Schema definition separate from queries. Shape of the database in one file. |

### 2.3 Why Not Fewer Layers?

- Merging tools + repository puts SQL in tool definitions — harder to read, harder to test, harder to swap databases.
- Merging server + tools couples protocol to logic — can't reuse tools from tests or a future REST API.

### 2.4 Why Not More Layers?

- No service layer — 6 tools over 3 tables. A service layer just proxies calls. Add it when there's cross-tool orchestration.
- No ORM — SQLAlchemy adds configuration weight for 3 tables. `sqlite3` + Pydantic gives typed results without it.
- No dependency injection framework — constructor injection (`Repository(db)`) is sufficient.

### 2.5 Auth

Optional API key via `MCP_API_KEY` env var, checked in `server.py` on connection. If not set, no auth (local use). Documents where access control belongs without over-building for a demo.

## 3. Data Models

### 3.1 Pydantic Models

```python
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
    equipment: list[str]  # stored as JSON in SQLite

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
    alternatives_hint: dict[str, Any] | None = None  # {"tool": str, "params": dict}
```

### 3.2 SQLite Schema

```sql
CREATE TABLE buildings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    address TEXT
);

CREATE TABLE rooms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    building_id INTEGER NOT NULL REFERENCES buildings(id),
    floor INTEGER NOT NULL,
    capacity INTEGER NOT NULL,
    equipment TEXT NOT NULL DEFAULT '[]',
    UNIQUE(building_id, name)
);

CREATE TABLE bookings (
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

CREATE INDEX idx_bookings_room_date ON bookings(room_id, date);
CREATE INDEX idx_bookings_user ON bookings(booked_by);
```

### 3.3 Schema Design Decisions

| Decision | Rationale |
|----------|-----------|
| Equipment as JSON list, not junction table | 3-5 items per room. Queried via Python `set.issubset()`. Many-to-many adds complexity for no gain at this scale. |
| `booked_by` as string, not User table | No auth system. A user table adds migration, model, FK constraints for a field that's just a label. |
| `CHECK(start_time < end_time)` | Database-level constraint. Defense in depth — prevents invalid bookings even if tool validation is bypassed. |
| Index on `(room_id, date)` | Hot query: "is this room available on this date?" Composite index serves single-room and date-range lookups. |
| Index on `booked_by` | `my_bookings` filters by user. Without index, full table scan. |
| `UNIQUE(building_id, name)` | No duplicate room names per building. Different buildings can reuse names. |
| ISO date/time as TEXT | SQLite has no native date type. ISO TEXT enables string comparison for range queries, is human-readable, and sorts correctly. |

## 4. MCP Tools

### 4.1 Tool Definitions

| Tool | Required Inputs | Optional Inputs | Returns |
|------|----------------|-----------------|---------|
| `list_rooms` | — | `building`, `floor`, `min_capacity`, `equipment` | List of rooms with building info |
| `search_available_rooms` | `date`, `start_time`, `end_time` | `building`, `min_capacity`, `equipment` | Available rooms for that slot |
| `get_room_availability` | `room_id`, `date` | — | All bookings + computed free slots for that room/day |
| `book_room` | `room_id`, `date`, `start_time`, `end_time`, `booked_by`, `title` | — | `BookingResult` (success + booking or conflict detail) |
| `cancel_booking` | `booking_id` | — | Success/failure confirmation |
| `my_bookings` | `booked_by` | `date` | List of user's bookings |

### 4.2 Tool Design Decisions

| Decision | Rationale |
|----------|-----------|
| `search_available_rooms` and `list_rooms` are separate tools | Different intent: "what rooms exist?" vs "what's free right now?" Merging overloads one tool with parameters that change its meaning. |
| `get_room_availability` returns computed free slots | The LLM shouldn't compute gaps between bookings. Repository calculates free slots given working hours (08:00-18:00). |
| No `update_booking` tool | Rebooking = cancel + book. Simpler mental model, fewer edge cases (update to a conflicting slot?). |
| All dates/times as ISO strings in tool inputs | MCP sends JSON. Parsing happens in `tools.py`. Repository receives native `date`/`time` types. |

### 4.3 Structured Conflict Response

All tools return Pydantic models, never formatted strings. Conflict responses include typed fields enabling cross-MCP orchestration:

```python
BookingResult(
    success=False,
    conflict=ConflictDetail(
        booking_id=42,
        room_id=5,
        room_name="Board Room A",
        booked_by="dana@siemens.com",
        date="2026-04-07",
        start_time="13:30",
        end_time="15:00",
        title="Sprint Review"
    ),
    alternatives_hint={
        "tool": "search_available_rooms",
        "params": {"date": "2026-04-07", "start_time": "14:00", "end_time": "15:00"}
    }
)
```

**Expected usage:** The LLM receives this structured data and can:
- Call `search_available_rooms` with the hint params to find alternatives
- Call a Slack MCP server to message `conflict.booked_by` about a room swap
- Call a Gmail MCP server to send a formal room swap request
- Present options to the user with full conflict context

The meeting rooms server returns data. The LLM decides what to do with it.

### 4.4 Validation (tools.py)

Input validation at the system boundary:
- ISO string → native `date`/`time` objects (reject malformed input)
- `end_time > start_time` (reject impossible ranges)
- Date not in the past
- Capacity > 0
- Room/building existence checks

Repository trusts its inputs — it only receives validated, typed Python objects.

## 5. Concurrency & ACID

### 5.1 Current Design (SQLite)

```python
# db.py
conn.execute("PRAGMA journal_mode=WAL")   # concurrent readers, serialized writers
conn.execute("PRAGMA busy_timeout=5000")   # wait 5s for write lock, don't fail instantly
```

**Booking transaction (atomic check-and-insert):**

```python
def create_booking(self, ...) -> BookingResult:
    with self.conn:  # BEGIN IMMEDIATE — acquires write lock
        # 1. Check for overlapping bookings
        conflicts = self.conn.execute(
            "SELECT ... WHERE room_id=? AND date=? AND start_time<? AND end_time>?",
            (room_id, date, end_time, start_time)
        )
        if conflict := conflicts.fetchone():
            return BookingResult(success=False, conflict=...)
        # 2. Insert — same transaction
        self.conn.execute("INSERT INTO bookings ...")
        return BookingResult(success=True, booking=...)
    # COMMIT — both steps or neither
```

Two users booking the same room at the same time: one wins, one gets a structured conflict. Never a double-booking.

### 5.2 Production Migration Path

| Concern | SQLite (current) | Postgres (production) |
|---------|-------------------|----------------------|
| Concurrent users | WAL mode, serialized writes | Connection pool + row-level locks |
| Transaction isolation | Serialized by default | `READ COMMITTED` + `SELECT ... FOR UPDATE` on time slot |
| Race conditions | Impossible — write lock held during check+insert | Row lock on room+date prevents phantom reads |
| Write throughput | Sufficient for ~50 concurrent users | Thousands of concurrent writes |
| Migration cost | — | Changes to `db.py` (connection) and `repository.py` (SQL dialect). Zero changes to tools or server. |

The repository layer is the abstraction boundary. Database choice is a deployment decision, not an architecture decision.

## 6. Transport

| Transport | Use Case | Config |
|-----------|----------|--------|
| `stdio` (default) | Local use — Claude Code, VS Code Copilot | Client spawns `python -m meeting_rooms.server` |
| `sse` | Remote access, multi-client | `python -m meeting_rooms.server --transport sse --port 8080` |

**Claude Code configuration:**

```json
{
  "meeting-rooms": {
    "command": "python",
    "args": ["-m", "meeting_rooms.server"],
    "cwd": "/path/to/mcp-meeting-rooms"
  }
}
```

## 7. Project Structure

```
mcp-meeting-rooms/
├── src/
│   └── meeting_rooms/
│       ├── __init__.py
│       ├── models.py        # Pydantic models (Building, Room, Booking, BookingResult, ConflictDetail)
│       ├── db.py            # Connection factory, schema DDL, WAL config
│       ├── repository.py    # All SQL queries, returns typed models
│       ├── tools.py         # MCP tool logic, input validation, calls repository
│       └── server.py        # MCP registration, transport routing, auth gate
├── tests/
│   ├── conftest.py          # In-memory SQLite fixture with seed data
│   └── test_repository.py   # Conflict detection, availability gaps, search filters
├── seed.py                  # Populate Siemens-flavored campus demo data
├── pyproject.toml           # Dependencies and project metadata
├── CLAUDE.md                # Project-specific development instructions
└── README.md                # Setup, usage, architecture decisions
```

## 8. Testing Strategy

### 8.1 What We Test

| Test Area | Why |
|-----------|-----|
| Booking conflict detection | Core correctness — double-booking cannot exist |
| Availability gap calculation | Non-trivial — computing free slots from existing bookings |
| Search filters (capacity, equipment, building) | Subset matching, optional filters combining correctly |
| Concurrent booking simulation | Two bookings for same slot — verify one wins, one gets conflict |

### 8.2 What We Don't Test

| Skip | Why |
|------|-----|
| MCP protocol layer | SDK handles it. Testing `server.py` is testing someone else's library. |
| Pydantic models | Pydantic validates itself. |
| Seed data | It inserts or crashes. |

### 8.3 Test Infrastructure

- In-memory SQLite for speed (`:memory:`)
- `conftest.py` provides seeded database fixture
- `pytest` only — no test framework overhead

## 9. Dependencies

```toml
[project]
requires-python = ">=3.12"

[project.dependencies]
dependencies = [
    "mcp",
    "pydantic>=2",
]

[project.optional-dependencies]
dev = ["pytest"]
```

Three packages total. Python stdlib `sqlite3` handles the database.

## 10. Seed Data

Siemens-flavored manufacturing campus:
- 3 buildings (e.g., Innovation Tower, Manufacturing Hub, R&D Center)
- 2-4 floors per building
- ~25 rooms: huddle rooms (4-person), meeting rooms (8-12), boardrooms (20+)
- Equipment distribution: projectors in large rooms, whiteboards everywhere, video conferencing in boardrooms
- ~10 pre-existing bookings across different days so availability queries return interesting results

Seed data loaded via `seed.py` — run once to populate, or included in test fixtures.
