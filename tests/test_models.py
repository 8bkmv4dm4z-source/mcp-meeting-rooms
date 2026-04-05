"""Tests for models.py — Pydantic model validation and serialization."""

from datetime import date, datetime, time

import pytest
from pydantic import ValidationError

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


class TestBuilding:
    def test_required_fields(self):
        b = Building(id=1, name="Tower A")
        assert b.id == 1
        assert b.name == "Tower A"
        assert b.address is None

    def test_optional_address(self):
        b = Building(id=1, name="Tower A", address="123 Main St")
        assert b.address == "123 Main St"


class TestRoom:
    def test_required_fields(self):
        r = Room(id=1, name="Huddle", building_id=1, floor=2, capacity=4)
        assert r.equipment == []

    def test_with_equipment(self):
        r = Room(id=1, name="Huddle", building_id=1, floor=2, capacity=4,
                 equipment=["whiteboard", "projector"])
        assert "projector" in r.equipment

    def test_invalid_missing_name(self):
        with pytest.raises(ValidationError):
            Room(id=1, building_id=1, floor=2, capacity=4)


class TestBooking:
    def test_full_booking(self):
        b = Booking(
            id=1, room_id=2, booked_by="alice@test.com", title="Standup",
            date=date(2026, 4, 5), start_time=time(9, 0), end_time=time(9, 30),
            created_at=datetime(2026, 4, 5, 8, 0, 0),
        )
        assert b.booked_by == "alice@test.com"
        assert b.date == date(2026, 4, 5)

    def test_json_serialization(self):
        b = Booking(
            id=1, room_id=2, booked_by="alice@test.com", title="Standup",
            date=date(2026, 4, 5), start_time=time(9, 0), end_time=time(9, 30),
            created_at=datetime(2026, 4, 5, 8, 0, 0),
        )
        data = b.model_dump(mode="json")
        assert data["date"] == "2026-04-05"
        assert data["start_time"] == "09:00:00"


class TestTimeSlot:
    def test_time_slot(self):
        ts = TimeSlot(start_time=time(8, 0), end_time=time(9, 0))
        assert ts.start_time == time(8, 0)
        assert ts.end_time == time(9, 0)


class TestConflictDetail:
    def test_all_fields(self):
        c = ConflictDetail(
            booking_id=1, room_id=2, room_name="Huddle",
            booked_by="alice@test.com", date="2026-04-05",
            start_time="09:00", end_time="09:30", title="Standup",
        )
        assert c.room_name == "Huddle"


class TestCrossMcpAction:
    def test_slack_action(self):
        a = CrossMcpAction(
            action="notify_via_slack",
            recipient_name="alice@test.com",
            message="Room conflict",
        )
        assert a.subject is None
        assert a.metadata == {}

    def test_email_action(self):
        a = CrossMcpAction(
            action="notify_via_email",
            recipient_name="alice@test.com",
            subject="Conflict",
            message="Room conflict",
            metadata={"booking_id": 1},
        )
        assert a.subject == "Conflict"
        assert a.metadata["booking_id"] == 1


class TestCrossMcpContext:
    def test_with_actions(self):
        ctx = CrossMcpContext(
            conflict_owner={"name": "alice@test.com", "booking_id": 1},
            suggested_actions=[
                CrossMcpAction(action="notify_via_slack",
                               recipient_name="alice", message="hi"),
            ],
        )
        assert len(ctx.suggested_actions) == 1


class TestBookingResult:
    def test_success_result(self):
        r = BookingResult(success=True)
        assert r.booking is None
        assert r.conflict is None
        assert r.alternatives == []
        assert r.cross_mcp_context is None

    def test_failure_result(self):
        r = BookingResult(
            success=False,
            conflict=ConflictDetail(
                booking_id=1, room_id=2, room_name="Huddle",
                booked_by="alice@test.com", date="2026-04-05",
                start_time="09:00", end_time="09:30", title="Standup",
            ),
        )
        assert r.success is False
        assert r.conflict.booking_id == 1
