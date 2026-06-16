"""
Advanced break explainer tests — cash breaks, ticker mismatches,
multi-action combinations.
"""

import os
import tempfile
import pytest
from datetime import date
from decimal import Decimal

from corp_actions.db import get_db
from corp_actions.identifiers import IdentifierTracker
from corp_actions.impact import BreakExplainer
from corp_actions.models import ActionType, CorporateAction, DataSource
from corp_actions.splits import SplitDividendDetector


@pytest.fixture
def explainer():
    """BreakExplainer with real split detector (no EDGAR)."""
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "test_explainer.db")
    detector = SplitDividendDetector(cache_ttl_hours=24, db_path=db_path)
    return BreakExplainer(detector)


@pytest.fixture
def explainer_with_ids():
    """BreakExplainer with identifier tracker."""
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "test_explainer_ids.db")
    detector = SplitDividendDetector(cache_ttl_hours=24, db_path=db_path)
    conn = get_db(db_path)
    tracker = IdentifierTracker(conn)
    tracker.seed_known_changes()
    return BreakExplainer(detector, identifier_tracker=tracker)


class TestQuantityBreaks:
    """Test explain_break and explain_all_breaks for quantity discrepancies."""

    @pytest.mark.network
    def test_aapl_4to1_split_break(self, explainer):
        """AAPL 4:1 split should explain 10000 vs 40000."""
        result = explainer.explain_break(
            "AAPL",
            Decimal("40000"),
            Decimal("10000"),
            lookback_days=3650,
        )
        assert result.is_explained
        assert result.confidence >= 0.90

    @pytest.mark.network
    def test_explain_all_returns_list(self, explainer):
        """explain_all_breaks should return a sorted list."""
        results = explainer.explain_all_breaks(
            "AAPL",
            Decimal("40000"),
            Decimal("10000"),
            lookback_days=3650,
        )
        assert isinstance(results, list)
        assert len(results) >= 1
        # Should be sorted by confidence descending
        for i in range(len(results) - 1):
            assert results[i].confidence >= results[i + 1].confidence

    def test_matching_positions_returns_empty(self, explainer):
        """If positions match, explain_all_breaks returns empty list."""
        results = explainer.explain_all_breaks(
            "AAPL",
            Decimal("10000"),
            Decimal("10000"),
        )
        assert results == []

    @pytest.mark.network
    def test_negative_qty_short_position(self, explainer):
        """Short positions should work too."""
        result = explainer.explain_break(
            "AAPL",
            Decimal("-40000"),
            Decimal("-10000"),
            lookback_days=3650,
        )
        assert result.is_explained


class TestCashBreaks:
    """Test explain_cash_break for dividend/merger cash discrepancies."""

    @pytest.mark.network
    def test_aapl_dividend_cash_break(self, explainer):
        """AAPL dividend should explain a cash difference matching the amount."""
        # Get actual AAPL dividend amount
        from corp_actions.splits import SplitDividendDetector
        start = date.today() - __import__("datetime").timedelta(days=365)
        dividends = explainer.split_detector.get_dividends("AAPL", start)
        if not dividends:
            pytest.skip("No AAPL dividends found")

        div = dividends[0]
        shares = Decimal("10000")
        expected_cash = div.dividend_amount * shares

        results = explainer.explain_cash_break(
            "AAPL", shares, expected_cash, lookback_days=365,
        )
        assert len(results) >= 1
        assert results[0].is_explained
        assert results[0].break_type == "cash"

    def test_cash_break_no_match(self, explainer):
        """Random cash difference with no matching dividend."""
        results = explainer.explain_cash_break(
            "BRK-A",
            Decimal("100"),
            Decimal("99999.99"),
            lookback_days=365,
        )
        # BRK-A pays no dividends, so nothing should match
        matches = [r for r in results if r.is_explained]
        assert len(matches) == 0


class TestTickerMismatch:
    """Test explain_missing_ticker for renamed/delisted tickers."""

    def test_fb_resolved_to_meta(self, explainer_with_ids):
        """FB should be identified as renamed to META."""
        results = explainer_with_ids.explain_missing_ticker("FB")
        assert len(results) >= 1
        assert results[0].is_explained
        assert "META" in results[0].explanation
        assert results[0].break_type == "ticker"

    def test_twtr_identified_as_delisted(self, explainer_with_ids):
        """TWTR should be identified as delisted."""
        results = explainer_with_ids.explain_missing_ticker("TWTR")
        assert len(results) >= 1
        assert results[0].is_explained
        assert results[0].break_type == "ticker"

    def test_unknown_ticker(self, explainer_with_ids):
        """Unknown ticker should return not-explained."""
        results = explainer_with_ids.explain_missing_ticker("ZZZNOTREAL")
        assert len(results) >= 1
        assert not results[0].is_explained

    def test_rdsa_resolved_to_shel(self, explainer_with_ids):
        """RDS.A should resolve to SHEL."""
        results = explainer_with_ids.explain_missing_ticker("RDS.A")
        assert len(results) >= 1
        assert results[0].is_explained
        assert "SHEL" in results[0].explanation


class TestEngineIntegration:
    """Test new explainer methods through the engine."""

    @pytest.mark.network
    def test_engine_explain_all_breaks(self):
        from corp_actions import CorporateActionsEngine
        engine = CorporateActionsEngine()
        results = engine.explain_all_breaks("AAPL", 40000, 10000)
        assert isinstance(results, list)
        assert len(results) >= 1

    @pytest.mark.network
    def test_engine_explain_cash_break(self):
        from corp_actions import CorporateActionsEngine
        engine = CorporateActionsEngine()
        results = engine.explain_cash_break("AAPL", 10000, 2500)
        assert isinstance(results, list)

    def test_engine_explain_missing_ticker(self):
        from corp_actions import CorporateActionsEngine
        engine = CorporateActionsEngine()
        results = engine.explain_missing_ticker("FB")
        assert isinstance(results, list)
        assert len(results) >= 1
        assert results[0].is_explained
