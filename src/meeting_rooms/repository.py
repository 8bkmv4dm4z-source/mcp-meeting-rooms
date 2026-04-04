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
            return BookingResult(
                success=False,
                conflict=conflict,
                alternatives_hint={"message": "Try a different time or room"},
            )

        cur = self.conn.execute(
            """
            INSERT INTO bookings (room_id, booked_by, title, date, start_time, end_time)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (room_id, booked_by, title, date_str, start_str, end_str),
        )
        self.conn.commit()
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
        cur = self.conn.execute(
            "DELETE FROM bookings WHERE id = ?", (booking_id,)
        )
        self.conn.commit()
        return cur.rowcount > 0