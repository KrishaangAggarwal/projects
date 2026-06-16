"""
Break Explanation Tests — BE-001 through BE-005.

Ground truth from the development guide Section 12.3.
"""

import pytest
from datetime import date
from decimal import Decimal

from corp_actions.impact import BreakExplainer
from corp_actions.splits import SplitDividendDetector


@pytest.fixture
def explainer():
    detector = SplitDividendDetector(cache_ttl_hours=1)
    return BreakExplainer(detector)


# These splits are historical (AAPL 4:1 was 2020, NVDA 10:1 was 2024, GE 1:8 was 2021).
# We need a large lookback to find them.


@pytest.mark.network
class TestBreakExplanation:
    """BE-001 through BE-005."""

    def test_be001_aapl_4to1_split(self, explainer):
        """AAPL: 40000 internal vs 10000 external → 4:1 split explains it."""
        result = explainer.explain_break(
            "AAPL",
            internal_qty=Decimal("40000"),
            external_qty=Decimal("10000"),
            lookback_days=3650,
        )
        assert result.is_explained is True
        assert result.confidence > 0.8
        assert "split" in result.explanation.lower()

    def test_be002_nvda_10to1_split(self, explainer):
        """NVDA: 50000 internal vs 5000 external → 10:1 split explains it."""
        result = explainer.explain_break(
            "NVDA",
            internal_qty=Decimal("50000"),
            external_qty=Decimal("5000"),
            lookback_days=3650,
        )
        assert result.is_explained is True
        assert result.confidence > 0.8
        assert "split" in result.explanation.lower()

    def test_be003_no_corporate_action(self, explainer):
        """AAPL: 10000 vs 9500 — no split explains a 500 share difference."""
        result = explainer.explain_break(
            "AAPL",
            internal_qty=Decimal("10000"),
            external_qty=Decimal("9500"),
        )
        assert result.is_explained is False
        assert result.confidence == 0.0

    def test_be004_ge_reverse_split(self, explainer):
        """GE: 1250 internal vs 10000 external → 1:8 reverse split."""
        result = explainer.explain_break(
            "GE",
            internal_qty=Decimal("1250"),
            external_qty=Decimal("10000"),
            lookback_days=3650,
        )
        assert result.is_explained is True
        assert result.confidence > 0.8
        assert "split" in result.explanation.lower()

    def test_be005_partial_match(self, explainer):
        """AAPL: 39999 vs 10000 — 4:1 split within tolerance of 1 share."""
        result = explainer.explain_break(
            "AAPL",
            internal_qty=Decimal("39999"),
            external_qty=Decimal("10000"),
            lookback_days=3650,
        )
        assert result.is_explained is True
        assert result.confidence > 0.8

    def test_invalid_ticker_graceful(self, explainer):
        """Invalid ticker should not crash, just return unexplained."""
        result = explainer.explain_break(
            "ZZZZ_INVALID_TICKER",
            internal_qty=Decimal("1000"),
            external_qty=Decimal("500"),
        )
        assert result.is_explained is False
