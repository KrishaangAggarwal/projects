"""
Position Impact Calculator tests — unit tests (no network needed).
"""

import pytest
from datetime import date
from decimal import Decimal

from corp_actions.impact import PositionImpactCalculator
from corp_actions.models import ActionType, CorporateAction


@pytest.fixture
def calc():
    return PositionImpactCalculator()


class TestStockSplitImpact:
    def test_4to1_split(self, calc):
        action = CorporateAction(
            ticker="AAPL",
            action_type=ActionType.STOCK_SPLIT,
            effective_date=date(2020, 8, 31),
            split_ratio=Decimal("4"),
            split_from=1,
            split_to=4,
        )
        impact = calc.calculate(action, Decimal("10000"), Decimal("500"))
        assert impact.new_quantity == Decimal("40000")
        assert impact.new_price == Decimal("125")
        assert impact.new_market_value == Decimal("5000000")

    def test_10to1_split(self, calc):
        action = CorporateAction(
            ticker="NVDA",
            action_type=ActionType.STOCK_SPLIT,
            effective_date=date(2024, 6, 10),
            split_ratio=Decimal("10"),
            split_from=1,
            split_to=10,
        )
        impact = calc.calculate(action, Decimal("5000"), Decimal("1200"))
        assert impact.new_quantity == Decimal("50000")
        assert impact.new_price == Decimal("120")

    def test_split_no_price(self, calc):
        action = CorporateAction(
            ticker="AAPL",
            action_type=ActionType.STOCK_SPLIT,
            split_ratio=Decimal("4"),
            split_from=1,
            split_to=4,
        )
        impact = calc.calculate(action, Decimal("10000"))
        assert impact.new_quantity == Decimal("40000")
        assert impact.new_price is None

    def test_split_no_ratio(self, calc):
        action = CorporateAction(
            ticker="AAPL",
            action_type=ActionType.STOCK_SPLIT,
        )
        impact = calc.calculate(action, Decimal("10000"))
        assert impact.new_quantity == Decimal("10000")
        assert "not available" in impact.explanation.lower()

    def test_short_position_split(self, calc):
        """Short positions should also be multiplied."""
        action = CorporateAction(
            ticker="AAPL",
            action_type=ActionType.STOCK_SPLIT,
            split_ratio=Decimal("4"),
            split_from=1,
            split_to=4,
        )
        impact = calc.calculate(action, Decimal("-10000"), Decimal("500"))
        assert impact.new_quantity == Decimal("-40000")
        assert impact.new_price == Decimal("125")


class TestReverseSplitImpact:
    def test_1to8_reverse_split(self, calc):
        action = CorporateAction(
            ticker="GE",
            action_type=ActionType.REVERSE_SPLIT,
            effective_date=date(2021, 8, 2),
            split_ratio=Decimal("0.125"),
            split_from=8,
            split_to=1,
        )
        impact = calc.calculate(action, Decimal("10000"), Decimal("12.50"))
        assert impact.new_quantity == Decimal("1250")
        assert impact.new_price == Decimal("100.0")

    def test_reverse_split_fractional_shares(self, calc):
        """100 shares / 8 = 12.5 → 12 shares + cash for 0.5."""
        action = CorporateAction(
            ticker="GE",
            action_type=ActionType.REVERSE_SPLIT,
            effective_date=date(2021, 8, 2),
            split_ratio=Decimal("0.125"),
            split_from=8,
            split_to=1,
        )
        impact = calc.calculate(action, Decimal("100"), Decimal("12.50"))
        assert impact.new_quantity == Decimal("12")
        assert impact.cash_received > 0


class TestCashDividendImpact:
    def test_regular_dividend(self, calc):
        action = CorporateAction(
            ticker="AAPL",
            action_type=ActionType.CASH_DIVIDEND,
            ex_date=date(2024, 8, 12),
            dividend_amount=Decimal("0.25"),
        )
        impact = calc.calculate(action, Decimal("10000"))
        assert impact.new_quantity == Decimal("10000")  # unchanged
        assert impact.cash_received == Decimal("2500")

    def test_special_dividend(self, calc):
        action = CorporateAction(
            ticker="COST",
            action_type=ActionType.SPECIAL_DIVIDEND,
            ex_date=date(2023, 12, 28),
            dividend_amount=Decimal("15.00"),
        )
        impact = calc.calculate(action, Decimal("1000"))
        assert impact.new_quantity == Decimal("1000")
        assert impact.cash_received == Decimal("15000")
        assert "Special" in impact.explanation

    def test_short_position_dividend(self, calc):
        """Short positions owe the dividend (negative cash)."""
        action = CorporateAction(
            ticker="AAPL",
            action_type=ActionType.CASH_DIVIDEND,
            dividend_amount=Decimal("0.25"),
        )
        impact = calc.calculate(action, Decimal("-10000"))
        assert impact.cash_received == Decimal("-2500")


class TestMergerImpact:
    def test_stock_merger(self, calc):
        action = CorporateAction(
            ticker="TARGET",
            action_type=ActionType.MERGER,
            acquirer_ticker="ACQUIRER",
            conversion_ratio=Decimal("0.5"),
        )
        impact = calc.calculate(action, Decimal("10000"))
        assert impact.new_quantity == Decimal("5000")

    def test_cash_merger(self, calc):
        action = CorporateAction(
            ticker="TARGET",
            action_type=ActionType.MERGER,
            cash_per_share=Decimal("50"),
        )
        impact = calc.calculate(action, Decimal("10000"))
        assert impact.cash_received == Decimal("500000")
        assert impact.new_quantity == Decimal("10000")  # no conversion ratio

    def test_mixed_merger(self, calc):
        action = CorporateAction(
            ticker="TARGET",
            action_type=ActionType.MERGER,
            acquirer_ticker="ACQUIRER",
            conversion_ratio=Decimal("0.5"),
            cash_per_share=Decimal("10"),
        )
        impact = calc.calculate(action, Decimal("10000"))
        assert impact.new_quantity == Decimal("5000")
        assert impact.cash_received == Decimal("100000")


class TestSpinoffImpact:
    def test_spinoff(self, calc):
        action = CorporateAction(
            ticker="PARENT",
            action_type=ActionType.SPIN_OFF,
            spinoff_ticker="SPINCO",
            spinoff_ratio=Decimal("0.25"),
            effective_date=date(2024, 1, 15),
        )
        impact = calc.calculate(action, Decimal("10000"))
        assert impact.new_quantity == Decimal("10000")  # parent unchanged
        assert len(impact.additional_positions) == 1
        assert impact.additional_positions[0]["ticker"] == "SPINCO"
        assert impact.additional_positions[0]["quantity"] == Decimal("2500")


class TestIdentifierChangeImpact:
    def test_name_change(self, calc):
        action = CorporateAction(
            ticker="META",
            action_type=ActionType.NAME_CHANGE,
            old_value="Facebook Inc.",
            new_value="Meta Platforms Inc.",
            effective_date=date(2021, 10, 28),
        )
        impact = calc.calculate(action, Decimal("10000"), Decimal("300"))
        assert impact.new_quantity == Decimal("10000")
        assert impact.new_price == Decimal("300")
        assert impact.new_market_value == Decimal("3000000")


class TestEdgeCases:
    def test_unknown_action_type(self, calc):
        action = CorporateAction(
            ticker="XYZ",
            action_type=ActionType.RIGHTS_ISSUE,
        )
        impact = calc.calculate(action, Decimal("10000"))
        assert impact.new_quantity == Decimal("10000")
        assert "No position impact" in impact.explanation

    def test_zero_quantity(self, calc):
        action = CorporateAction(
            ticker="AAPL",
            action_type=ActionType.STOCK_SPLIT,
            split_ratio=Decimal("4"),
            split_from=1,
            split_to=4,
        )
        impact = calc.calculate(action, Decimal("0"))
        assert impact.new_quantity == Decimal("0")
