
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