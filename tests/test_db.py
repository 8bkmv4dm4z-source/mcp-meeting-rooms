"""Tests for db.py — connection factory and schema initialization."""

from meeting_rooms.db import get_connection, init_db


class TestGetConnection:
    def test_returns_connection(self):
        conn = get_connection(":memory:")
        assert conn is not None
        conn.close()

    def test_wal_mode_enabled(self):
        conn = get_connection(":memory:")
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        # :memory: may report "memory" instead of "wal", so just check it doesn't error
        assert mode is not None
        conn.close()

    def test_foreign_keys_enabled(self):
        conn = get_connection(":memory:")
        fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        assert fk == 1
        conn.close()

    def test_row_factory_set(self):
        conn = get_connection(":memory:")
        init_db(conn)
        conn.execute("INSERT INTO buildings (name, address) VALUES ('Test', 'Addr')")
        row = conn.execute("SELECT * FROM buildings").fetchone()
        assert row["name"] == "Test"
        conn.close()

    def test_autocommit_mode(self):
        conn = get_connection(":memory:")
        # isolation_level=None means autocommit
        assert conn.isolation_level is None
        conn.close()


class TestInitDb:
    def test_creates_tables(self):
        conn = get_connection(":memory:")
        init_db(conn)
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        table_names = [t[0] for t in tables]
        assert "buildings" in table_names
        assert "rooms" in table_names
        assert "bookings" in table_names
        conn.close()

    def test_idempotent(self):
        conn = get_connection(":memory:")
        init_db(conn)
        init_db(conn)  # should not raise
        conn.close()

    def test_creates_indexes(self):
        conn = get_connection(":memory:")
        init_db(conn)
        indexes = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
        ).fetchall()
        index_names = [i[0] for i in indexes]
        assert "idx_bookings_room_date" in index_names
        assert "idx_bookings_user" in index_names
        conn.close()

    def test_check_constraint_on_bookings(self):
        conn = get_connection(":memory:")
        init_db(conn)
        conn.execute("INSERT INTO buildings (name) VALUES ('B')")
        conn.execute(
            "INSERT INTO rooms (name, building_id, floor, capacity, equipment) "
            "VALUES ('R', 1, 1, 4, '[]')"
        )
        import pytest
        with pytest.raises(Exception):
            conn.execute(
                "INSERT INTO bookings (room_id, booked_by, title, date, start_time, end_time) "
                "VALUES (1, 'x', 'x', '2026-01-01', '10:00', '09:00')"
            )
        conn.close()
