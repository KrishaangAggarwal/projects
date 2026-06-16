"""
Split Detection Tests — SP-001 through SP-008.

These tests hit the real Yahoo Finance API (marked with @pytest.mark.network).
Ground truth from the development guide Section 12.1.
"""

import pytest
from datetime import date
from decimal import Decimal

from corp_actions.models import ActionType
from corp_actions.splits import SplitDividendDetector


@pytest.fixture
def detector():
    return SplitDividendDetector(cache_ttl_hours=1)


@pytest.mark.network
class TestSplitDetection:
    """SP-001 through SP-008: verify known splits from yfinance."""

    def test_sp001_aapl_splits(self, detector):
        """AAPL: 4:1 (2020-08-31), 7:1 (2014-06-09), plus earlier 2:1 splits."""
        splits = detector.get_splits("AAPL")
        ratios = {s.effective_date: float(s.split_ratio) for s in splits}

        assert date(2020, 8, 31) in ratios
        assert ratios[date(2020, 8, 31)] == 4.0

        assert date(2014, 6, 9) in ratios
        assert ratios[date(2014, 6, 9)] == 7.0

        # Should have at least 5 splits total (including 2:1 splits in 2005, 2000, 1987)
        assert len(splits) >= 5

    def test_sp002_tsla_splits(self, detector):
        """TSLA: 3:1 (2022-08-25), 5:1 (2020-08-31)."""
        splits = detector.get_splits("TSLA")
        ratios = {s.effective_date: float(s.split_ratio) for s in splits}

        assert date(2022, 8, 25) in ratios
        assert ratios[date(2022, 8, 25)] == 3.0

        assert date(2020, 8, 31) in ratios
        assert ratios[date(2020, 8, 31)] == 5.0

    def test_sp003_nvda_splits(self, detector):
        """NVDA: 10:1 (2024-06-10), 4:1 (2021-07-20), plus earlier."""
        splits = detector.get_splits("NVDA")
        ratios = {s.effective_date: float(s.split_ratio) for s in splits}

        assert date(2024, 6, 10) in ratios
        assert ratios[date(2024, 6, 10)] == 10.0

        assert date(2021, 7, 20) in ratios
        assert ratios[date(2021, 7, 20)] == 4.0

    def test_sp004_amzn_split(self, detector):
        """AMZN: 20:1 (2022-06-06)."""
        splits = detector.get_splits("AMZN")
        ratios = {s.effective_date: float(s.split_ratio) for s in splits}

        assert date(2022, 6, 6) in ratios
        assert ratios[date(2022, 6, 6)] == 20.0

    def test_sp005_googl_split(self, detector):
        """GOOGL: 20:1 (2022-07-18)."""
        splits = detector.get_splits("GOOGL")
        ratios = {s.effective_date: float(s.split_ratio) for s in splits}

        assert date(2022, 7, 18) in ratios
        assert ratios[date(2022, 7, 18)] == 20.0

    def test_sp006_ge_reverse_split(self, detector):
        """GE: 1:8 reverse split (2021-08-02) — ratio should be 0.125."""
        splits = detector.get_splits("GE")
        reverse = [s for s in splits if s.action_type == ActionType.REVERSE_SPLIT]

        assert len(reverse) >= 1
        ge_reverse = [s for s in reverse if s.effective_date == date(2021, 8, 2)]
        assert len(ge_reverse) == 1
        assert float(ge_reverse[0].split_ratio) == pytest.approx(0.125, abs=0.01)

    def test_sp007_aig_reverse_split(self, detector):
        """AIG: 1:20 reverse split (2009-07-01)."""
        splits = detector.get_splits("AIG")
        reverse = [s for s in splits if s.action_type == ActionType.REVERSE_SPLIT]

        assert len(reverse) >= 1
        aig_reverse = [s for s in reverse if s.effective_date == date(2009, 7, 1)]
        assert len(aig_reverse) == 1
        assert float(aig_reverse[0].split_ratio) == pytest.approx(0.05, abs=0.01)

    def test_sp008_brka_no_splits(self, detector):
        """BRK-A: should return empty list (Berkshire never splits)."""
        splits = detector.get_splits("BRK-A")
        assert splits == []

    def test_split_date_filtering(self, detector):
        """Verify date filtering works correctly."""
        # Only get AAPL splits from 2020
        splits = detector.get_splits(
            "AAPL",
            start_date=date(2020, 1, 1),
            end_date=date(2020, 12, 31),
        )
        assert len(splits) == 1
        assert splits[0].effective_date == date(2020, 8, 31)

    def test_split_action_type_correct(self, detector):
        """Splits > 1 should be STOCK_SPLIT, < 1 should be REVERSE_SPLIT."""
        splits = detector.get_splits("AAPL")
        for s in splits:
            assert s.action_type == ActionType.STOCK_SPLIT
            assert float(s.split_ratio) > 1.0

    def test_split_fields_populated(self, detector):
        """All returned splits should have key fields populated."""
        splits = detector.get_splits("AAPL")
        for s in splits:
            assert s.ticker == "AAPL"
            assert s.effective_date is not None
            assert s.split_ratio is not None
            assert s.split_from is not None
            assert s.split_to is not None
            assert s.source.value == "yfinance"
