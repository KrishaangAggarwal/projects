"""
Database layer tests — verify SQLite caching works.
"""

import os
import tempfile
import pytest

from corp_actions.db import get_db, new_id, store_json, load_json, log_fetch


class TestDatabase:

    def test_db_creation(self):
        """DB should auto-create on first use."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.db")
            conn = get_db(path)
            # Verify tables exist
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            table_names = {row[0] for row in tables}
            assert "securities" in table_names
            assert "corporate_actions" in table_names
            assert "identifier_history" in table_names
            assert "data_fetch_log" in table_names
            conn.close()

    def test_new_id_unique(self):
        """IDs should be unique."""
        ids = {new_id() for _ in range(100)}
        assert len(ids) == 100

    def test_store_load_json(self):
        """JSON round-trip should preserve data."""
        data = {"ticker": "AAPL", "ratio": 4.0, "date": "2020-08-31"}
        serialized = store_json(data)
        assert isinstance(serialized, str)
        loaded = load_json(serialized)
        assert loaded == data

    def test_load_json_none(self):
        assert load_json(None) == {}

    def test_log_fetch(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.db")
            conn = get_db(path)
            log_fetch(conn, "yfinance", "AAPL", "splits", True, None, 5)
            row = conn.execute(
                "SELECT * FROM data_fetch_log WHERE ticker='AAPL'"
            ).fetchone()
            assert row is not None
            assert row["source"] == "yfinance"
            assert row["records_found"] == 5
            conn.close()
