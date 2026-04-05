"""Tests for tools.py — input validation and orchestration layer."""

from datetime import date, timedelta

from meeting_rooms.repository import Repository
from meeting_rooms import tools


class TestListRooms:
    def test_returns_all_rooms(self, db):
        repo = Repository(db)
        result = tools.list_rooms(repo)
        assert len(result) == 5
        assert all(isinstance(r, dict) for r in result)

    def test_filter_by_building(self, db):
        repo = Repository(db)
        result = tools.list_rooms(repo, building="Tower A")
        assert all(r["building_id"] == 1 for r in result)

    def test_filter_by_floor(self, db):
        repo = Repository(db)
        result = tools.list_rooms(repo, floor=1)
        assert all(r["floor"] == 1 for r in result)

    def test_filter_by_capacity(self, db):
        repo = Repository(db)
        result = tools.list_rooms(repo, min_capacity=10)
        assert all(r["capacity"] >= 10 for r in result)

    def test_filter_by_equipment(self, db):
        repo = Repository(db)
        result = tools.list_rooms(repo, equipment=["video_conf"])
        assert all("video_conf" in r["equipment"] for r in result)

    def test_combined_filters(self, db):
        repo = Repository(db)
        result = tools.list_rooms(repo, building="Tower A", min_capacity=10)
        assert all(r["building_id"] == 1 and r["capacity"] >= 10 for r in result)


class TestSearchAvailableRooms:
    def test_valid_search(self, db):
        repo = Repository(db)
        today = date.today().isoformat()
        result = tools.search_available_rooms(repo, date=today,
                                              start_time="16:00", end_time="17:00")
        assert isinstance(result, list)
        assert len(result) > 0
        assert "error" not in result[0]

    def test_invalid_date(self, db):
        repo = Repository(db)
        result = tools.search_available_rooms(repo, date="not-a-date",
                                              start_time="09:00", end_time="10:00")
        assert result[0]["error"].startswith("Invalid date")

    def test_invalid_time(self, db):
        repo = Repository(db)
        today = date.today().isoformat()
        result = tools.search_available_rooms(repo, date=today,
                                              start_time="bad", end_time="10:00")
        assert result[0]["error"].startswith("Invalid time")

    def test_end_before_start(self, db):
        repo = Repository(db)
        today = date.today().isoformat()
        result = tools.search_available_rooms(repo, date=today,
                                              start_time="10:00", end_time="09:00")
        assert result[0]["error"] == "end_time must be after start_time"

    def test_end_equals_start(self, db):
        repo = Repository(db)
        today = date.today().isoformat()
        result = tools.search_available_rooms(repo, date=today,
                                              start_time="10:00", end_time="10:00")
        assert result[0]["error"] == "end_time must be after start_time"


class TestGetRoomAvailability:
    def test_valid_request(self, db):
        repo = Repository(db)
        today = date.today().isoformat()
        result = tools.get_room_availability(repo, room_id=1, date=today)
        assert "bookings" in result
        assert "free_slots" in result
        assert result["room_id"] == 1

    def test_invalid_date(self, db):
        repo = Repository(db)
        result = tools.get_room_availability(repo, room_id=1, date="nope")
        assert "error" in result


class TestBookRoom:
    def test_successful_booking(self, db):
        repo = Repository(db)
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        result = tools.book_room(repo, room_id=3, date=tomorrow,
                                 start_time="10:00", end_time="11:00",
                                 booked_by="test@test.com", title="Test")
        assert result["success"] is True
        assert result["booking"] is not None

    def test_conflict(self, db):
        repo = Repository(db)
        today = date.today().isoformat()
        result = tools.book_room(repo, room_id=1, date=today,
                                 start_time="09:00", end_time="09:30",
                                 booked_by="test@test.com", title="Conflict")
        assert result["success"] is False
        assert result["conflict"] is not None

    def test_invalid_date(self, db):
        repo = Repository(db)
        result = tools.book_room(repo, room_id=1, date="bad",
                                 start_time="09:00", end_time="10:00",
                                 booked_by="x", title="x")
        assert result["success"] is False
        assert "error" in result

    def test_end_before_start(self, db):
        repo = Repository(db)
        today = date.today().isoformat()
        result = tools.book_room(repo, room_id=1, date=today,
                                 start_time="10:00", end_time="09:00",
                                 booked_by="x", title="x")
        assert result["success"] is False
        assert result["error"] == "end_time must be after start_time"


class TestCancelBooking:
    def test_cancel_existing(self, db):
        repo = Repository(db)
        result = tools.cancel_booking(repo, booking_id=1)
        assert result["success"] is True
        assert result["booking_id"] == 1

    def test_cancel_nonexistent(self, db):
        repo = Repository(db)
        result = tools.cancel_booking(repo, booking_id=999)
        assert result["success"] is False
        assert result["booking_id"] == 999


class TestMyBookings:
    def test_returns_bookings(self, db):
        repo = Repository(db)
        result = tools.my_bookings(repo, booked_by="alice@test.com")
        assert len(result) == 2

    def test_filter_by_date(self, db):
        repo = Repository(db)
        today = date.today().isoformat()
        result = tools.my_bookings(repo, booked_by="alice@test.com", date=today)
        assert len(result) == 1

    def test_invalid_date(self, db):
        repo = Repository(db)
        result = tools.my_bookings(repo, booked_by="alice@test.com", date="bad")
        assert result[0]["error"].startswith("Invalid date")

    def test_no_bookings(self, db):
        repo = Repository(db)
        result = tools.my_bookings(repo, booked_by="nobody@test.com")
        assert len(result) == 0
