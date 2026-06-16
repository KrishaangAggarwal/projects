"""
Portfolio replay tests — verify position adjustments through corporate actions.
Uses REAL yfinance data.
"""

import pytest
from datetime import date
from decimal import Decimal

from corp_actions.replay import PortfolioReplay
from corp_actions.splits import SplitDividendDetector


@pytest.fixture
def replay():
    return PortfolioReplay(SplitDividendDetector())


@pytest.mark.network
class TestSinglePositionReplay:

    def test_aapl_4to1_split(self, replay):
        """1000 AAPL shares from 2020-01-01 → 4000 after 4:1 split."""
        result = replay.replay_position(
            "AAPL", 1000, date(2020, 1, 1)
        )
        assert result.entry_quantity == Decimal("1000")
        assert result.current_quantity == Decimal("4000")
        assert len(result.adjustments) >= 1

        # Should have the split in adjustments
        split_adjs = [
            a for a in result.adjustments
            if "split" in a.get("description", "").lower()
        ]
        assert len(split_adjs) >= 1

    def test_nvda_10to1_split(self, replay):
        """500 NVDA shares from 2023-01-01 → 5000 after 10:1 split."""
        result = replay.replay_position(
            "NVDA", 500, date(2023, 1, 1)
        )
        assert result.entry_quantity == Decimal("500")
        assert result.current_quantity == Decimal("5000")

    def test_ge_reverse_split(self, replay):
        """10000 GE shares from 2021-01-01 → reduced by 1:8 reverse split.

        Note: GE also did a GE Vernova spin-off split in 2024, so the
        final quantity is not exactly 1250. We check that the reverse
        split was applied (qty reduced from 10000).
        """
        result = replay.replay_position(
            "GE", 10000, date(2021, 1, 1)
        )
        assert result.entry_quantity == Decimal("10000")
        # Should have been reduced by the 1:8 reverse split
        assert result.current_quantity < Decimal("10000")
        # Should have the reverse split in adjustments
        split_adjs = [
            a for a in result.adjustments
            if "reverse" in a.get("description", "").lower()
            or "split" in a.get("action_type", "").lower()
        ]
        assert len(split_adjs) >= 1

    def test_brka_no_splits(self, replay):
        """100 BRK-A from 2020-01-01 → 100 (no splits ever)."""
        result = replay.replay_position(
            "BRK-A", 100, date(2020, 1, 1)
        )
        assert result.entry_quantity == Decimal("100")
        # BRK-A has no splits, so quantity unchanged
        # (dividends don't change qty)
        split_adjs = [
            a for a in result.adjustments
            if "split" in a.get("description", "").lower()
        ]
        assert len(split_adjs) == 0

    def test_dividends_tracked(self, replay):
        """AAPL replay should track cumulative dividends received."""
        result = replay.replay_position(
            "AAPL", 1000, date(2024, 1, 1)
        )
        # AAPL pays quarterly dividends
        assert result.total_cash_received > 0

    def test_no_actions_in_period(self, replay):
        """Very recent entry with no actions should return unchanged."""
        result = replay.replay_position(
            "AAPL", 1000, date.today()
        )
        assert result.current_quantity == Decimal("1000")
        assert len(result.adjustments) == 0


class TestPortfolioReplay:

    @pytest.mark.network
    def test_multi_position_replay(self, replay):
        """Replay multiple positions at once."""
        positions = [
            {"ticker": "AAPL", "quantity": 1000, "entry_date": "2020-01-01"},
            {"ticker": "BRK-A", "quantity": 100, "entry_date": "2020-01-01"},
        ]
        results = replay.replay_portfolio(positions)
        assert len(results) == 2
        assert results[0].ticker == "AAPL"
        assert results[0].current_quantity == Decimal("4000")

    def test_empty_portfolio(self, replay):
        """Empty portfolio returns empty results."""
        results = replay.replay_portfolio([])
        assert results == []

    def test_missing_entry_date_skipped(self, replay):
        """Position with no entry_date is skipped."""
        positions = [
            {"ticker": "AAPL", "quantity": 1000},
        ]
        results = replay.replay_portfolio(positions)
        assert len(results) == 0


class TestCSVParsing:

    def test_standard_csv(self):
        csv = "ticker,quantity,entry_date\nAAPL,1000,2020-01-01\nMSFT,500,2021-06-15"
        positions = PortfolioReplay.parse_csv(csv)
        assert len(positions) == 2
        assert positions[0]["ticker"] == "AAPL"
        assert positions[0]["quantity"] == 1000.0

    def test_alternative_column_names(self):
        csv = "symbol,shares,date\nAAPL,1000,2020-01-01"
        positions = PortfolioReplay.parse_csv(csv)
        assert len(positions) == 1
        assert positions[0]["ticker"] == "AAPL"

    def test_empty_csv(self):
        csv = "ticker,quantity,entry_date\n"
        positions = PortfolioReplay.parse_csv(csv)
        assert positions == []

    def test_whitespace_handling(self):
        csv = "ticker , quantity , entry_date\n  AAPL , 1000 , 2020-01-01 \n"
        positions = PortfolioReplay.parse_csv(csv)
        assert len(positions) == 1
        assert positions[0]["ticker"] == "AAPL"
