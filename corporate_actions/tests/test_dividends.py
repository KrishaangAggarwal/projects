"""
Dividend Detection Tests — DV-001 through DV-005.

Ground truth from the development guide Section 12.2.
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
class TestDividendDetection:
    """DV-001 through DV-005."""

    def test_dv001_aapl_quarterly_dividends(self, detector):
        """AAPL: quarterly dividends ~$0.25 in recent years."""
        divs = detector.get_dividends(
            "AAPL", start_date=date(2024, 1, 1), end_date=date(2024, 12, 31)
        )
        assert len(divs) >= 4  # quarterly
        for d in divs:
            assert d.action_type == ActionType.CASH_DIVIDEND
            assert float(d.dividend_amount) > 0.10
            assert float(d.dividend_amount) < 1.00

    def test_dv002_msft_quarterly_dividends(self, detector):
        """MSFT: quarterly dividends ~$0.75 in recent years."""
        divs = detector.get_dividends(
            "MSFT", start_date=date(2024, 1, 1), end_date=date(2024, 12, 31)
        )
        assert len(divs) >= 4
        for d in divs:
            assert d.action_type == ActionType.CASH_DIVIDEND
            assert float(d.dividend_amount) > 0.50
            assert float(d.dividend_amount) < 2.00

    def test_dv003_cost_special_dividend(self, detector):
        """COST: had a large special dividend ($15/share in Dec 2023)."""
        divs = detector.get_dividends(
            "COST", start_date=date(2023, 1, 1), end_date=date(2023, 12, 31)
        )
        specials = [d for d in divs if d.action_type == ActionType.SPECIAL_DIVIDEND]
        # Should detect at least one special dividend
        assert len(specials) >= 1
        assert any(float(d.dividend_amount) > 10 for d in specials)

    def test_dv004_brka_no_dividends(self, detector):
        """BRK-A: Berkshire doesn't pay dividends."""
        divs = detector.get_dividends("BRK-A", start_date=date(2020, 1, 1))
        assert divs == []

    def test_dv005_t_dividend_cut(self, detector):
        """AT&T: dividend was cut in 2022 (from ~$0.52 to ~$0.2775)."""
        divs_before = detector.get_dividends(
            "T", start_date=date(2021, 1, 1), end_date=date(2021, 12, 31)
        )
        divs_after = detector.get_dividends(
            "T", start_date=date(2023, 1, 1), end_date=date(2023, 12, 31)
        )

        if divs_before and divs_after:
            avg_before = sum(float(d.dividend_amount) for d in divs_before) / len(divs_before)
            avg_after = sum(float(d.dividend_amount) for d in divs_after) / len(divs_after)
            assert avg_after < avg_before  # Dividend was cut

    def test_dividend_fields_populated(self, detector):
        """All returned dividends should have key fields populated."""
        divs = detector.get_dividends(
            "AAPL", start_date=date(2024, 1, 1), end_date=date(2024, 12, 31)
        )
        for d in divs:
            assert d.ticker == "AAPL"
            assert d.ex_date is not None
            assert d.dividend_amount is not None
            assert d.dividend_amount > 0
            assert d.dividend_currency == "USD"
            assert d.source.value == "yfinance"

    def test_zero_amount_dividends_filtered(self, detector):
        """Zero or negative dividend amounts should be filtered out."""
        divs = detector.get_dividends("AAPL")
        for d in divs:
            assert d.dividend_amount > 0
