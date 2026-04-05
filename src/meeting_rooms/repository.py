# src/meeting_rooms/repository.py
"""Data access layer — all SQL queries behind typed methods."""

from __future__ import annotations

import json
import sqlite3
from datetime import date, time, datetime

from meeting_rooms.models import (
    Booking,
    BookingResult,
    Building,
    ConflictDetail,
    CrossMcpAction,
    CrossMcpContext,
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

    def create_booking(
        self,
        room_id: int,
        date_: date,
        start_time: time,
        end_time: time,
        booked_by: str,
        title: str,
    ) -> BookingResult:
        date_str = date_.isoformat()
        start_str = start_time.strftime("%H:%M")
        end_str = end_time.strftime("%H:%M")

        # BEGIN IMMEDIATE acquires a write lock upfront, preventing
        # two concurrent bookings from both passing the conflict check.
        self.conn.execute("BEGIN IMMEDIATE")

        conflict_row = self.conn.execute(
            """
            SELECT b.*, r.name AS room_name
            FROM bookings b
            JOIN rooms r ON b.room_id = r.id
            WHERE b.room_id = ?
              AND b.date = ?
              AND b.start_time < ?
              AND b.end_time > ?
            LIMIT 1
            """,
            (room_id, date_str, end_str, start_str),
        ).fetchone()

        if conflict_row:
            conflict = ConflictDetail(
                booking_id=conflict_row["id"],
                room_id=conflict_row["room_id"],
                room_name=conflict_row["room_name"],
                booked_by=conflict_row["booked_by"],
                date=conflict_row["date"],
                start_time=conflict_row["start_time"],
                end_time=conflict_row["end_time"],
                title=conflict_row["title"],
            )

            alternatives = self.search_available_rooms(date_, start_time, end_time)

            time_slot = f"{start_str}–{end_str}"
            owner = conflict_row["booked_by"]
            room_name = conflict_row["room_name"]
            meeting_title = conflict_row["title"]
            meeting_date = conflict_row["date"]

            cross_mcp_context = CrossMcpContext(
                conflict_owner={
                    "name": owner,
                    "booking_id": conflict_row["id"],
                    "room": room_name,
                    "date": meeting_date,
                    "time_slot": time_slot,
                    "meeting_title": meeting_title,
                },
                suggested_actions=[
                    CrossMcpAction(
                        action="notify_via_slack",
                        recipient_name=owner,
                        message=(
                            f"Hi {owner}, your meeting '{meeting_title}' is booked in "
                            f"{room_name} on {meeting_date} {time_slot}. "
                            f"Someone is requesting the same slot — can you switch rooms?"
                        ),
                        metadata={"booking_id": conflict_row["id"]},
                    ),
                    CrossMcpAction(
                        action="notify_via_email",
                        recipient_name=owner,
                        subject=f"Meeting Room Conflict — {room_name} on {meeting_date}",
                        message=(
                            f"Hi {owner},\n\n"
                            f"Your booking '{meeting_title}' in {room_name} on {meeting_date} "
                            f"({time_slot}) has a scheduling conflict.\n\n"
                            f"There are {len(alternatives)} alternative room(s) available. "
                            f"Please coordinate or consider switching."
                        ),
                        metadata={"booking_id": conflict_row["id"], "alternative_count": len(alternatives)},
                    ),
                    CrossMcpAction(
                        action="request_swap",
                        recipient_name=owner,
                        message=f"Swap request for booking #{conflict_row['id']} ({room_name}, {time_slot})",
                        metadata={
                            "booking_id": conflict_row["id"],
                            "alternative_room_ids": [r.id for r in alternatives],
                        },
                    ),
                ],
            )

            self.conn.rollback()
            return BookingResult(
                success=False,
                conflict=conflict,
                alternatives=alternatives,
                cross_mcp_context=cross_mcp_context,
            )

        cur = self.conn.execute(
            """
            INSERT INTO bookings (room_id, booked_by, title, date, start_time, end_time)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (room_id, booked_by, title, date_str, start_str, end_str),
        )
        self.conn.execute("COMMIT")
        row = self.conn.execute(
            "SELECT * FROM bookings WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
        booking = Booking(
            id=row["id"],
            room_id=row["room_id"],
            booked_by=row["booked_by"],
            title=row["title"],
            date=row["date"],
            start_time=row["start_time"],
            end_time=row["end_time"],
            created_at=row["created_at"],
        )
        return BookingResult(success=True, booking=booking)

    def cancel_booking(self, booking_id: int) -> bool:
        self.conn.execute("BEGIN IMMEDIATE")
        cur = self.conn.execute(
            "DELETE FROM bookings WHERE id = ?", (booking_id,)
        )
        self.conn.execute("COMMIT")
        return cur.rowcount > 0

    def search_available_rooms(
        self,
        date_: date,
        start_time: time,
        end_time: time,
        min_capacity: int | None = None,
        equipment: list[str] | None = None,
        building: str | None = None,
    ) -> list[Room]:
        """Rooms not booked during the given slot, with optional filters."""
        date_str = date_.isoformat()
        start_str = start_time.strftime("%H:%M")
        end_str = end_time.strftime("%H:%M")

        if building:
            query = """
                SELECT r.* FROM rooms r
                JOIN buildings b ON r.building_id = b.id
                WHERE b.name = ?
                  AND r.id NOT IN (
                    SELECT room_id FROM bookings
                    WHERE date = ?
                      AND start_time < ?
                      AND end_time > ?
                  )
            """
            params: list = [building, date_str, end_str, start_str]
        else:
            query = """
                SELECT r.* FROM rooms r
                WHERE r.id NOT IN (
                    SELECT room_id FROM bookings
                    WHERE date = ?
                      AND start_time < ?
                      AND end_time > ?
                )
            """
            params = [date_str, end_str, start_str]

        if min_capacity is not None:
            query += " AND r.capacity >= ?"
            params.append(min_capacity)

        rows = self.conn.execute(query, params).fetchall()
        rooms = [self._row_to_room(row) for row in rows]

        if equipment:
            wanted = set(equipment)
            rooms = [r for r in rooms if wanted.issubset(set(r.equipment))]

        return rooms

    def get_room_availability(
        self, room_id: int, date_: date
    ) -> tuple[list[Booking], list[TimeSlot]]:
        """Return bookings and free slots for a room on a given day (08:00–18:00)."""
        date_str = date_.isoformat()
        rows = self.conn.execute(
            "SELECT * FROM bookings WHERE room_id = ? AND date = ? ORDER BY start_time",
            (room_id, date_str),
        ).fetchall()

        bookings = [
            Booking(
                id=row["id"],
                room_id=row["room_id"],
                booked_by=row["booked_by"],
                title=row["title"],
                date=row["date"],
                start_time=row["start_time"],
                end_time=row["end_time"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

        work_start = time(8, 0)
        work_end = time(18, 0)
        free_slots: list[TimeSlot] = []
        cursor = work_start

        for booking in bookings:
            if booking.start_time > cursor:
                free_slots.append(TimeSlot(start_time=cursor, end_time=booking.start_time))
            cursor = booking.end_time

        if cursor < work_end:
            free_slots.append(TimeSlot(start_time=cursor, end_time=work_end))

        return bookings, free_slots

    def get_bookings_by_user(
        self, email: str, date_: date | None = None
    ) -> list[Booking]:
        """Return all bookings for a user, optionally filtered by date."""
        query = "SELECT * FROM bookings WHERE booked_by = ?"
        params: list = [email]

        if date_ is not None:
            query += " AND date = ?"
            params.append(date_.isoformat())

        query += " ORDER BY date, start_time"
        rows = self.conn.execute(query, params).fetchall()

        return [
            Booking(
                id=row["id"],
                room_id=row["room_id"],
                booked_by=row["booked_by"],
                title=row["title"],
                date=row["date"],
                start_time=row["start_time"],
                end_time=row["end_time"],
                created_at=row["created_at"],
            )
            for row in rows
        ]