# Meeting Rooms MCP — Agent Guide

This server exposes meeting room booking capabilities over the Model Context Protocol (MCP).
Connect via stdio transport. All dates are `YYYY-MM-DD`, all times are `HH:MM` (24-hour).

## Connection

The server uses stdio transport. You must complete the MCP handshake before issuing any tool calls:

1. Send `initialize` request
2. Send `notifications/initialized` notification (no response expected)
3. Now call tools freely

```json
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"my-agent","version":"1.0"}}}
{"jsonrpc":"2.0","method":"notifications/initialized"}
```

## Tools

### `list_rooms`

Browse all rooms. All parameters are optional — omit to get everything.

| Parameter | Type | Description |
|-----------|------|-------------|
| `building` | string? | Filter by building name (exact match) |
| `floor` | int? | Filter by floor number |
| `min_capacity` | int? | Minimum number of seats |
| `equipment` | string[]? | Must have ALL listed items (e.g. `["projector","video_conf"]`) |

**Returns:** Array of room objects.

```json
// Request
{"name":"list_rooms","arguments":{"building":"Tower A","min_capacity":8}}

// Response (abbreviated)
[{"id":2,"name":"Meeting A","building_id":1,"floor":2,"capacity":10,"equipment":["whiteboard","projector"]}]
```

---

### `search_available_rooms`

Find rooms not booked during a specific time slot.

| Parameter | Type | Description |
|-----------|------|-------------|
| `date` | string | Date to check — `YYYY-MM-DD` |
| `start_time` | string | Slot start — `HH:MM` |
| `end_time` | string | Slot end — `HH:MM` |
| `building` | string? | Restrict to a building |
| `min_capacity` | int? | Minimum seats |
| `equipment` | string[]? | Required equipment |

**Returns:** Array of room objects that are free for the entire requested slot.

```json
// Find a video-conf room for 10+ people tomorrow at 14:00
{"name":"search_available_rooms","arguments":{"date":"2026-04-05","start_time":"14:00","end_time":"15:30","min_capacity":10,"equipment":["video_conf"]}}
```

---

### `get_room_availability`

See the full picture for one room on one day — both what's booked and what's free.

| Parameter | Type | Description |
|-----------|------|-------------|
| `room_id` | int | Room ID |
| `date` | string | Date — `YYYY-MM-DD` |

**Returns:** Object with `bookings` (existing reservations) and `free_slots` (gaps in the working day, 08:00–18:00).

```json
// Response shape
{
  "room_id": 1,
  "date": "2026-04-04",
  "bookings": [
    {"id":1,"room_id":1,"booked_by":"alice@example.com","title":"Standup","date":"2026-04-04","start_time":"09:00","end_time":"09:30","created_at":"..."}
  ],
  "free_slots": [
    {"start_time":"08:00","end_time":"09:00"},
    {"start_time":"09:30","end_time":"18:00"}
  ]
}
```

---

### `book_room`

Reserve a room. Returns immediately with success or a conflict detail.

| Parameter | Type | Description |
|-----------|------|-------------|
| `room_id` | int | Room to book |
| `date` | string | Date — `YYYY-MM-DD` |
| `start_time` | string | Start — `HH:MM` |
| `end_time` | string | End — `HH:MM` |
| `booked_by` | string | Requester email |
| `title` | string | Meeting title |

**Success response:**
```json
{"success":true,"booking":{"id":5,"room_id":2,"booked_by":"bob@example.com","title":"Sprint Planning","date":"2026-04-05","start_time":"10:00","end_time":"11:00","created_at":"..."},"conflict":null,"alternatives_hint":null}
```

**Conflict response:** `success` is `false`, `conflict` describes the blocking booking, `alternatives_hint` suggests trying a different time or room.

```json
{"success":false,"booking":null,"conflict":{"booking_id":1,"room_id":1,"room_name":"Huddle 1","booked_by":"alice@example.com","date":"2026-04-04","start_time":"09:00","end_time":"09:30","title":"Standup"},"alternatives_hint":{"message":"Try a different time or room"}}
```

---

### `cancel_booking`

Delete a booking by its ID.

| Parameter | Type | Description |
|-----------|------|-------------|
| `booking_id` | int | ID from a previous `book_room` or `my_bookings` call |

**Returns:** `{"success":true,"booking_id":5}` or `{"success":false,"booking_id":999}` if not found.

---

### `my_bookings`

List all upcoming (or past) bookings for a person.

| Parameter | Type | Description |
|-----------|------|-------------|
| `booked_by` | string | Email address |
| `date` | string? | Restrict to a single date — `YYYY-MM-DD` |

**Returns:** Array of booking objects, ordered by date and start time.

---

## Typical Workflows

### Find and book a room

```
1. search_available_rooms(date, start_time, end_time, [filters])
   → pick a room_id from results
2. book_room(room_id, date, start_time, end_time, booked_by, title)
   → check success; if conflict, repeat step 1 with adjusted params
```

### Check a room before booking

```
1. get_room_availability(room_id, date)
   → inspect free_slots to confirm your window is open
2. book_room(...)
```

### Cancel a booking

```
1. my_bookings(booked_by)              ← find the booking_id
2. cancel_booking(booking_id)
```

---

## Equipment Tags

Known values in the seed data: `whiteboard`, `projector`, `video_conf`, `phone`.
The `equipment` filter is an **AND** — every listed tag must be present on the room.

## Working Hours

Free slots are computed within **08:00–18:00**. Bookings outside that range are stored but
free-slot calculation stays within the working day window.

## Error Handling

- `end_time` ≤ `start_time` → tool returns `{"error":"end_time must be after start_time"}`
- Booking a taken slot → `success: false` with `conflict` detail (not an error, handle gracefully)
- Unknown `booking_id` in cancel → `success: false`
