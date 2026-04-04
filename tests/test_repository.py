
from datetime import date, time, timedelta

from src.meeting_rooms.repository import Repository


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