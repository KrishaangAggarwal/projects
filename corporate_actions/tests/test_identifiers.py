"""
Identifier tracker tests — seed data, resolve_historical, history.
"""

import os
import tempfile
import pytest
from datetime import date

from corp_actions.db import get_db
from corp_actions.identifiers import IdentifierTracker


@pytest.fixture
def tracker():
    """Fresh tracker with an in-memory-like temp DB."""
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "test_identifiers.db")
    conn = get_db(db_path)
    t = IdentifierTracker(conn)
    yield t
    conn.close()


@pytest.fixture
def seeded_tracker():
    """Tracker pre-loaded with seed data."""
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "test_identifiers.db")
    conn = get_db(db_path)
    t = IdentifierTracker(conn)
    t.seed_known_changes()
    yield t
    conn.close()


class TestSeedData:

    def test_seed_inserts_records(self, tracker):
        """Seeding should insert known identifier changes."""
        count = tracker.seed_known_changes()
        assert count > 0

    def test_seed_is_idempotent(self, tracker):
        """Seeding twice should not create duplicates."""
        count1 = tracker.seed_known_changes()
        count2 = tracker.seed_known_changes()
        assert count1 > 0
        assert count2 == 0  # All already exist

    def test_seed_creates_securities(self, seeded_tracker):
        """Seeding should create security records."""
        row = seeded_tracker.db.execute(
            "SELECT COUNT(*) as c FROM securities"
        ).fetchone()
        assert row["c"] >= 4  # META, SHEL, DJT, TWTR

    def test_seed_creates_history(self, seeded_tracker):
        """Seeding should create identifier_history records."""
        row = seeded_tracker.db.execute(
            "SELECT COUNT(*) as c FROM identifier_history"
        ).fetchone()
        assert row["c"] >= 6  # Multiple changes across securities


class TestResolveHistorical:

    def test_resolve_fb_to_meta(self, seeded_tracker):
        """'FB' (old ticker) should resolve to META's security_id."""
        sec_id = seeded_tracker.resolve_historical("FB", "ticker")
        assert sec_id is not None

        # And META should resolve to the same security
        sec_id_meta = seeded_tracker.resolve_historical("META", "ticker")
        assert sec_id_meta == sec_id

    def test_resolve_current_ticker(self, seeded_tracker):
        """Current ticker 'META' should resolve directly."""
        sec_id = seeded_tracker.resolve_historical("META", "ticker")
        assert sec_id is not None

    def test_resolve_rdsa_to_shel(self, seeded_tracker):
        """'RDS.A' should resolve to SHEL's security_id."""
        sec_id_old = seeded_tracker.resolve_historical("RDS.A", "ticker")
        sec_id_new = seeded_tracker.resolve_historical("SHEL", "ticker")
        assert sec_id_old is not None
        assert sec_id_old == sec_id_new

    def test_resolve_dwac_to_djt(self, seeded_tracker):
        """'DWAC' should resolve to DJT's security_id."""
        sec_id_old = seeded_tracker.resolve_historical("DWAC", "ticker")
        sec_id_new = seeded_tracker.resolve_historical("DJT", "ticker")
        assert sec_id_old is not None
        assert sec_id_old == sec_id_new

    def test_resolve_twtr_delisted(self, seeded_tracker):
        """'TWTR' should resolve to a security (even though delisted)."""
        sec_id = seeded_tracker.resolve_historical("TWTR", "ticker")
        assert sec_id is not None

    def test_resolve_unknown_returns_none(self, seeded_tracker):
        """Unknown ticker should return None."""
        sec_id = seeded_tracker.resolve_historical("ZZZZNOTREAL", "ticker")
        assert sec_id is None

    def test_resolve_by_name(self, seeded_tracker):
        """Should be able to resolve by name too."""
        sec_id = seeded_tracker.resolve_historical("Facebook, Inc.", "name")
        assert sec_id is not None


class TestFullHistory:

    def test_meta_history(self, seeded_tracker):
        """META should have both name and ticker change history."""
        sec_id = seeded_tracker.resolve_historical("META", "ticker")
        history = seeded_tracker.get_full_history(sec_id)

        assert len(history) >= 2

        types = {h["identifier_type"] for h in history}
        assert "ticker" in types
        assert "name" in types

        # Verify chronological order
        dates = [h["effective_date"] for h in history]
        assert dates == sorted(dates)

    def test_shel_history(self, seeded_tracker):
        """SHEL should have ticker + name change from Royal Dutch Shell."""
        sec_id = seeded_tracker.resolve_historical("SHEL", "ticker")
        history = seeded_tracker.get_full_history(sec_id)

        assert len(history) >= 2
        ticker_changes = [h for h in history if h["identifier_type"] == "ticker"]
        assert any(h["old_value"] == "RDS.A" for h in ticker_changes)

    def test_empty_history(self, seeded_tracker):
        """Nonexistent security should return empty history."""
        history = seeded_tracker.get_full_history("nonexistent-id")
        assert history == []


class TestRecordChange:

    def test_record_and_retrieve(self, tracker):
        """Manually recorded changes should be retrievable."""
        # Create a security first
        sec_id = tracker._ensure_security("TEST", "Test Corp")

        tracker.record_change(
            security_id=sec_id,
            id_type="ticker",
            old_value="OLD",
            new_value="TEST",
            effective_date=date(2024, 1, 1),
            source="manual",
        )

        # Should resolve both old and new
        assert tracker.resolve_historical("TEST", "ticker") == sec_id
        assert tracker.resolve_historical("OLD", "ticker") == sec_id

        # History should contain the change
        history = tracker.get_full_history(sec_id)
        assert len(history) == 1
        assert history[0]["old_value"] == "OLD"
        assert history[0]["new_value"] == "TEST"


class TestIdentifierAsOf:

    def test_ticker_as_of_date(self, seeded_tracker):
        """Should return the correct ticker for a given date."""
        sec_id = seeded_tracker.resolve_historical("META", "ticker")

        # After the ticker change
        ticker = seeded_tracker.get_identifier_as_of(
            sec_id, "ticker", date(2023, 1, 1)
        )
        assert ticker == "META"

    def test_name_as_of_date(self, seeded_tracker):
        """Should return the correct name for a given date."""
        sec_id = seeded_tracker.resolve_historical("META", "ticker")

        # After the name change
        name = seeded_tracker.get_identifier_as_of(
            sec_id, "name", date(2022, 1, 1)
        )
        assert name == "Meta Platforms, Inc."


class TestEngineIntegration:
    """Test identifier features through the engine."""

    def test_engine_resolves_fb(self):
        from corp_actions import CorporateActionsEngine
        engine = CorporateActionsEngine()
        assert engine.resolve_ticker("FB") == "META"

    def test_engine_resolves_rdsa(self):
        from corp_actions import CorporateActionsEngine
        engine = CorporateActionsEngine()
        assert engine.resolve_ticker("RDS.A") == "SHEL"

    def test_engine_history_fb(self):
        from corp_actions import CorporateActionsEngine
        engine = CorporateActionsEngine()
        result = engine.get_identifier_history("FB")
        assert result["security"] is not None
        assert result["security"]["ticker"] == "META"
        assert len(result["history"]) >= 2

    def test_engine_history_unknown(self):
        from corp_actions import CorporateActionsEngine
        engine = CorporateActionsEngine()
        result = engine.get_identifier_history("ZZZZNOTREAL")
        assert result["security"] is None
        assert result["history"] == []
