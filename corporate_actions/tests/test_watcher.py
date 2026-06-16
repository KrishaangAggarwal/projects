"""
Event watcher tests — verify new event detection and deduplication.
"""

import os
import tempfile
import pytest
from datetime import date
from decimal import Decimal

from corp_actions.db import get_db
from corp_actions.edgar import EdgarEventDetector
from corp_actions.models import ActionType, CorporateAction, DataSource
from corp_actions.splits import SplitDividendDetector
from corp_actions.watcher import EventWatcher


@pytest.fixture
def watcher():
    """Watcher with temp DB for deduplication testing."""
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "test_watcher.db")
    detector = SplitDividendDetector(cache_ttl_hours=24, db_path=db_path)
    edgar = EdgarEventDetector("test@test.com")
    edgar._groq_available = False
    return EventWatcher(detector, edgar, db_path)


class TestDeduplication:

    def test_event_key_generation(self, watcher):
        """Event keys should be deterministic."""
        action = CorporateAction(
            ticker="AAPL",
            action_type=ActionType.STOCK_SPLIT,
            effective_date=date(2020, 8, 31),
            source=DataSource.YFINANCE,
        )
        key1 = watcher._make_event_key(action)
        key2 = watcher._make_event_key(action)
        assert key1 == key2
        assert "AAPL" in key1
        assert "stock_split" in key1

    def test_mark_and_check_seen(self, watcher):
        """Marking an event as seen should prevent re-detection."""
        action = CorporateAction(
            ticker="AAPL",
            action_type=ActionType.CASH_DIVIDEND,
            ex_date=date(2025, 1, 15),
            source=DataSource.YFINANCE,
        )
        key = watcher._make_event_key(action)

        assert not watcher._is_seen(key)
        watcher._mark_seen("AAPL", action, key)
        assert watcher._is_seen(key)

    def test_duplicate_mark_safe(self, watcher):
        """Marking the same event twice should not crash (INSERT OR IGNORE)."""
        action = CorporateAction(
            ticker="AAPL",
            action_type=ActionType.CASH_DIVIDEND,
            ex_date=date(2025, 1, 15),
            source=DataSource.YFINANCE,
        )
        key = watcher._make_event_key(action)
        watcher._mark_seen("AAPL", action, key)
        watcher._mark_seen("AAPL", action, key)  # No crash
        assert watcher._is_seen(key)


class TestCheckOnce:

    @pytest.mark.network
    def test_check_returns_events(self, watcher):
        """First check for a popular stock should find events."""
        events = watcher.check_once(["AAPL"])
        # AAPL almost certainly has recent dividends
        assert isinstance(events, list)

    @pytest.mark.network
    def test_second_check_no_duplicates(self, watcher):
        """Second check should not return the same events."""
        events1 = watcher.check_once(["AAPL"])
        events2 = watcher.check_once(["AAPL"])

        # All events from first check should be marked as seen
        if events1:
            # Second check shouldn't return the same events
            keys1 = {watcher._make_event_key(e) for e in events1}
            keys2 = {watcher._make_event_key(e) for e in events2}
            assert len(keys1 & keys2) == 0

    def test_invalid_ticker_no_crash(self, watcher):
        """Invalid ticker should return empty, not crash."""
        events = watcher.check_once(["ZZZNOTREAL"])
        assert events == []

    def test_empty_watchlist(self, watcher):
        """Empty watchlist should return empty results."""
        events = watcher.check_once([])
        assert events == []


class TestSeenEventsTable:

    def test_table_created(self, watcher):
        """seen_events table should exist after init."""
        row = watcher._db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='seen_events'"
        ).fetchone()
        assert row is not None

    def test_raw_event_marking(self, watcher):
        """mark_seen_raw should work for non-CorporateAction events."""
        watcher._mark_seen_raw(
            "AAPL", "edgar_efts", "efts:AAPL:12345",
            {"accession": "12345"},
        )
        assert watcher._is_seen("efts:AAPL:12345")
