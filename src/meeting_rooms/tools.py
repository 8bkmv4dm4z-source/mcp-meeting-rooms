"""MCP tool functions — input validation, calls repository, returns structured data."""

from __future__ import annotations

from datetime import date, time

from meeting_rooms.models import Booking, BookingResult, Room, TimeSlot
from meeting_rooms.repository import Repository


def _parse_date(s: str) -> date:
    try:
        return date.fromisoformat(s)
    except ValueError:
        raise ValueError(f"Invalid date '{s}' — expected YYYY-MM-DD")


def _parse_time(s: str) -> time:
    try:
        return time.fromisoformat(s)
    except ValueError:
        raise ValueError(f"Invalid time '{s}' — expected HH:MM")


def _normalize_equipment(equipment) -> list[str] | None:
    """Accept equipment as a list, a single string, or a JSON string."""
    if equipment is None:
        return None
    if isinstance(equipment, str):
        import json
        try:
            parsed = json.loads(equipment)
            if isinstance(parsed, list):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass
        return [equipment]
    return list(equipment)


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
        min_capacity=min_capacity, equipment=_normalize_equipment(equipment),
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
    try:
        d = _parse_date(date)
        st = _parse_time(start_time)
        et = _parse_time(end_time)
    except ValueError as e:
        return [{"error": str(e)}]
    if et <= st:
        return [{"error": "end_time must be after start_time"}]

    rooms = repo.search_available_rooms(
        date_=d, start_time=st, end_time=et,
        building=building, min_capacity=min_capacity, equipment=_normalize_equipment(equipment),
    )
    return [r.model_dump() for r in rooms]


def get_room_availability(
    repo: Repository,
    room_id: int,
    date: str,
) -> dict:
    """Get bookings and free slots for a room on a date."""
    try:
        d = _parse_date(date)
    except ValueError as e:
        return {"error": str(e)}
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
    try:
        d = _parse_date(date)
        st = _parse_time(start_time)
        et = _parse_time(end_time)
    except ValueError as e:
        return {"success": False, "error": str(e)}
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
    try:
        d = _parse_date(date) if date else None
    except ValueError as e:
        return [{"error": str(e)}]
    bookings = repo.get_bookings_by_user(email=booked_by, date_=d)
    return [b.model_dump(mode="json") for b in bookings]