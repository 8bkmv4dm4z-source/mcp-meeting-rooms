"""Cross-layer integration tests — tools → repository → db, end-to-end workflows."""

from datetime import date, timedelta

from meeting_rooms.db import get_connection, init_db
from meeting_rooms.repository import Repository
from meeting_rooms import tools


class TestBookingWorkflow:
    """Full find → book → verify → cancel flow."""

    def test_search_book_verify_cancel(self, db):
        repo = Repository(db)
        tomorrow = (date.today() + timedelta(days=1)).isoformat()

        # 1. Search for available rooms
        available = tools.search_available_rooms(
            repo, date=tomorrow, start_time="14:00", end_time="15:00",
            min_capacity=8,
        )
        assert len(available) > 0
        room_id = available[0]["id"]

        # 2. Book the room
        result = tools.book_room(
            repo, room_id=room_id, date=tomorrow,
            start_time="14:00", end_time="15:00",
            booked_by="integration@test.com", title="Integration Test",
        )
        assert result["success"] is True
        booking_id = result["booking"]["id"]

        # 3. Verify it shows in availability
        avail = tools.get_room_availability(repo, room_id=room_id, date=tomorrow)
        booking_ids = [b["id"] for b in avail["bookings"]]
        assert booking_id in booking_ids

        # 4. Verify it shows in my_bookings
        my = tools.my_bookings(repo, booked_by="integration@test.com")
        assert any(b["id"] == booking_id for b in my)

        # 5. Cancel
        cancel_result = tools.cancel_booking(repo, booking_id=booking_id)
        assert cancel_result["success"] is True

        # 6. Room is available again
        available_after = tools.search_available_rooms(
            repo, date=tomorrow, start_time="14:00", end_time="15:00",
        )
        assert room_id in [r["id"] for r in available_after]

    def test_search_book_conflict_find_alternative(self, db):
        repo = Repository(db)
        today = date.today().isoformat()

        # Room 1 is booked 09:00-09:30 (seed data)
        # 1. Try to book the same slot
        result = tools.book_room(
            repo, room_id=1, date=today,
            start_time="09:00", end_time="09:30",
            booked_by="new@test.com", title="Conflicting Meeting",
        )
        assert result["success"] is False
        assert result["conflict"] is not None

        # 2. Alternatives should be provided
        assert len(result["alternatives"]) > 0

        # 3. Cross-MCP context should have actions
        assert result["cross_mcp_context"] is not None
        actions = result["cross_mcp_context"]["suggested_actions"]
        action_types = [a["action"] for a in actions]
        assert "notify_via_slack" in action_types
        assert "notify_via_email" in action_types
        assert "request_swap" in action_types

        # 4. Book an alternative instead
        alt_id = result["alternatives"][0]["id"]
        alt_result = tools.book_room(
            repo, room_id=alt_id, date=today,
            start_time="09:00", end_time="09:30",
            booked_by="new@test.com", title="Rescheduled Meeting",
        )
        assert alt_result["success"] is True


class TestDoubleBookingPrevention:
    """Verify that booking the same slot twice fails correctly."""

    def test_cannot_double_book(self, db):
        repo = Repository(db)
        future = (date.today() + timedelta(days=5)).isoformat()

        # First booking succeeds
        r1 = tools.book_room(
            repo, room_id=3, date=future,
            start_time="10:00", end_time="11:00",
            booked_by="first@test.com", title="First",
        )
        assert r1["success"] is True

        # Same slot, same room — conflict
        r2 = tools.book_room(
            repo, room_id=3, date=future,
            start_time="10:00", end_time="11:00",
            booked_by="second@test.com", title="Second",
        )
        assert r2["success"] is False
        assert r2["conflict"]["booked_by"] == "first@test.com"

    def test_partial_overlap_blocked(self, db):
        repo = Repository(db)
        future = (date.today() + timedelta(days=5)).isoformat()

        tools.book_room(
            repo, room_id=3, date=future,
            start_time="10:00", end_time="11:00",
            booked_by="first@test.com", title="First",
        )

        # Overlapping slot
        r2 = tools.book_room(
            repo, room_id=3, date=future,
            start_time="10:30", end_time="11:30",
            booked_by="second@test.com", title="Overlap",
        )
        assert r2["success"] is False

    def test_adjacent_slots_allowed(self, db):
        repo = Repository(db)
        future = (date.today() + timedelta(days=5)).isoformat()

        r1 = tools.book_room(
            repo, room_id=3, date=future,
            start_time="10:00", end_time="11:00",
            booked_by="first@test.com", title="First",
        )
        assert r1["success"] is True

        # Immediately after — no conflict
        r2 = tools.book_room(
            repo, room_id=3, date=future,
            start_time="11:00", end_time="12:00",
            booked_by="second@test.com", title="Adjacent",
        )
        assert r2["success"] is True


class TestAvailabilityConsistency:
    """Verify that search results and availability view agree."""

    def test_search_matches_availability(self, db):
        repo = Repository(db)
        today = date.today().isoformat()

        # Search says room 1 is NOT available 09:00-09:30
        available = tools.search_available_rooms(
            repo, date=today, start_time="09:00", end_time="09:30",
        )
        available_ids = [r["id"] for r in available]
        assert 1 not in available_ids

        # Availability view should show that slot as booked
        avail = tools.get_room_availability(repo, room_id=1, date=today)
        assert len(avail["bookings"]) > 0
        assert avail["bookings"][0]["start_time"] == "09:00:00"

    def test_free_slots_exclude_bookings(self, db):
        repo = Repository(db)
        future = (date.today() + timedelta(days=5)).isoformat()

        # Book a slot
        tools.book_room(
            repo, room_id=4, date=future,
            start_time="12:00", end_time="13:00",
            booked_by="test@test.com", title="Lunch Meeting",
        )

        # Free slots should not include 12:00-13:00
        avail = tools.get_room_availability(repo, room_id=4, date=future)
        for slot in avail["free_slots"]:
            # No free slot should overlap with 12:00-13:00
            assert not (slot["start_time"] < "13:00:00" and slot["end_time"] > "12:00:00")


class TestCancelRestoresAvailability:
    """Verify cancel makes the room bookable again."""

    def test_cancel_then_rebook(self, db):
        repo = Repository(db)
        future = (date.today() + timedelta(days=6)).isoformat()

        # Book
        r1 = tools.book_room(
            repo, room_id=5, date=future,
            start_time="09:00", end_time="10:00",
            booked_by="a@test.com", title="First",
        )
        booking_id = r1["booking"]["id"]

        # Confirm room not available
        available = tools.search_available_rooms(
            repo, date=future, start_time="09:00", end_time="10:00",
        )
        assert 5 not in [r["id"] for r in available]

        # Cancel
        tools.cancel_booking(repo, booking_id=booking_id)

        # Room should be available again
        available = tools.search_available_rooms(
            repo, date=future, start_time="09:00", end_time="10:00",
        )
        assert 5 in [r["id"] for r in available]

        # Can rebook
        r2 = tools.book_room(
            repo, room_id=5, date=future,
            start_time="09:00", end_time="10:00",
            booked_by="b@test.com", title="Second",
        )
        assert r2["success"] is True


class TestMultipleBookingsSameRoom:
    """Verify multiple non-overlapping bookings on the same room/day work."""

    def test_back_to_back_bookings(self, db):
        repo = Repository(db)
        future = (date.today() + timedelta(days=7)).isoformat()

        for hour in range(8, 12):
            result = tools.book_room(
                repo, room_id=4, date=future,
                start_time=f"{hour:02d}:00", end_time=f"{hour+1:02d}:00",
                booked_by=f"user{hour}@test.com", title=f"Meeting {hour}",
            )
            assert result["success"] is True

        # Verify all 4 bookings show up
        avail = tools.get_room_availability(repo, room_id=4, date=future)
        assert len(avail["bookings"]) == 4

        # Free slots should cover 12:00-18:00
        assert any(s["start_time"] == "12:00:00" for s in avail["free_slots"])


class TestIsolationBetweenDays:
    """Bookings on one day don't affect another day."""

    def test_different_days_independent(self, db):
        repo = Repository(db)
        day1 = (date.today() + timedelta(days=8)).isoformat()
        day2 = (date.today() + timedelta(days=9)).isoformat()

        # Book room 4 on day1
        tools.book_room(
            repo, room_id=4, date=day1,
            start_time="09:00", end_time="10:00",
            booked_by="a@test.com", title="Day 1",
        )

        # Room 4 should still be available on day2 at same time
        available = tools.search_available_rooms(
            repo, date=day2, start_time="09:00", end_time="10:00",
        )
        assert 4 in [r["id"] for r in available]


class TestFreshDatabase:
    """Verify the system works from a clean state (no conftest fixture)."""

    def test_empty_db_workflow(self):
        conn = get_connection(":memory:")
        init_db(conn)

        conn.execute("BEGIN")
        conn.execute("INSERT INTO buildings (name, address) VALUES ('HQ', '123 St')")
        conn.execute(
            "INSERT INTO rooms (name, building_id, floor, capacity, equipment) "
            "VALUES ('Room 1', 1, 1, 10, '[\"whiteboard\"]')"
        )
        conn.execute("COMMIT")

        repo = Repository(conn)

        # List rooms
        rooms = tools.list_rooms(repo)
        assert len(rooms) == 1

        # Book
        result = tools.book_room(
            repo, room_id=1, date="2026-12-01",
            start_time="09:00", end_time="10:00",
            booked_by="admin@test.com", title="First Ever",
        )
        assert result["success"] is True

        conn.close()
