"""
Module 4: Position Impact Calculator & Break Explainer.

The "Explain Break" function is the KEY feature that makes this tool
useful for trading operations reconciliation.
"""

import logging
from datetime import date, timedelta
from decimal import Decimal

from corp_actions.models import (
    ActionType, BreakExplanation, CorporateAction, PositionImpact,
)

logger = logging.getLogger(__name__)


class PositionImpactCalculator:
    """Calculate how a corporate action affects a position."""

    def calculate(
        self,
        action: CorporateAction,
        quantity: Decimal,
        price: Decimal | None = None,
    ) -> PositionImpact:
        """
        Calculate the impact of a corporate action on a position.

        Args:
            action: The corporate action
            quantity: Number of shares held (negative for short)
            price: Price per share (optional)

        Returns:
            PositionImpact with new quantity, price, and explanation
        """
        market_value = quantity * price if price else None

        impact = PositionImpact(
            action=action,
            original_quantity=quantity,
            original_price=price,
            original_market_value=market_value,
        )

        handlers = {
            ActionType.STOCK_SPLIT: self._apply_split,
            ActionType.REVERSE_SPLIT: self._apply_reverse_split,
            ActionType.CASH_DIVIDEND: self._apply_cash_dividend,
            ActionType.SPECIAL_DIVIDEND: self._apply_cash_dividend,
            ActionType.MERGER: self._apply_merger,
            ActionType.ACQUISITION: self._apply_merger,
            ActionType.SPIN_OFF: self._apply_spinoff,
            ActionType.NAME_CHANGE: self._apply_identifier_change,
            ActionType.TICKER_CHANGE: self._apply_identifier_change,
            ActionType.CUSIP_CHANGE: self._apply_identifier_change,
        }

        handler = handlers.get(action.action_type)
        if handler:
            return handler(impact, action)

        # Default: no position change
        impact.new_quantity = quantity
        impact.new_price = price
        impact.explanation = f"No position impact for {action.action_type.value}"
        return impact

    def _apply_split(
        self, impact: PositionImpact, action: CorporateAction
    ) -> PositionImpact:
        """Apply a stock split to a position."""
        ratio = action.split_ratio
        if not ratio:
            impact.new_quantity = impact.original_quantity
            impact.explanation = "Split ratio not available"
            return impact

        impact.new_quantity = impact.original_quantity * ratio

        if impact.original_price:
            impact.new_price = impact.original_price / ratio
            impact.new_market_value = impact.new_quantity * impact.new_price

        impact.explanation = (
            f"{action.split_from}:{action.split_to} stock split on "
            f"{action.effective_date}. "
            f"Position: {impact.original_quantity} → {impact.new_quantity} shares. "
            f"Market value unchanged."
        )
        return impact

    def _apply_reverse_split(
        self, impact: PositionImpact, action: CorporateAction
    ) -> PositionImpact:
        """Apply a reverse split to a position."""
        ratio = action.split_ratio
        if not ratio:
            impact.new_quantity = impact.original_quantity
            impact.explanation = "Split ratio not available"
            return impact

        impact.new_quantity = impact.original_quantity * ratio

        # Handle fractional shares (common in reverse splits)
        whole_shares = int(impact.new_quantity)
        fractional = impact.new_quantity - whole_shares

        if impact.original_price:
            impact.new_price = impact.original_price / ratio

            if fractional > 0:
                impact.cash_received = fractional * impact.new_price
                impact.new_quantity = Decimal(whole_shares)
                impact.new_market_value = impact.new_quantity * impact.new_price
            else:
                impact.new_market_value = impact.new_quantity * impact.new_price

        impact.explanation = (
            f"{action.split_from}:{action.split_to} reverse split on "
            f"{action.effective_date}. "
            f"Position: {impact.original_quantity} → {impact.new_quantity} shares."
        )

        if fractional > 0:
            impact.explanation += (
                f" Fractional shares ({fractional:.4f}) paid in cash: "
                f"${impact.cash_received:.2f}."
            )

        return impact

    def _apply_cash_dividend(
        self, impact: PositionImpact, action: CorporateAction
    ) -> PositionImpact:
        """Apply a cash dividend to a position."""
        impact.new_quantity = impact.original_quantity
        impact.new_price = impact.original_price

        if action.dividend_amount and impact.original_quantity:
            impact.cash_received = action.dividend_amount * impact.original_quantity

        div_type = (
            "Special dividend"
            if action.action_type == ActionType.SPECIAL_DIVIDEND
            else "Dividend"
        )

        impact.explanation = (
            f"{div_type} of ${action.dividend_amount} per share "
            f"(ex-date: {action.ex_date}). "
            f"Position unchanged at {impact.original_quantity} shares. "
            f"Cash {'received' if impact.cash_received >= 0 else 'owed'}: "
            f"${abs(impact.cash_received):.2f}."
        )
        return impact

    def _apply_merger(
        self, impact: PositionImpact, action: CorporateAction
    ) -> PositionImpact:
        """Apply a merger/acquisition to a position."""
        if action.conversion_ratio:
            impact.new_quantity = impact.original_quantity * action.conversion_ratio
        else:
            impact.new_quantity = impact.original_quantity

        if action.cash_per_share:
            impact.cash_received = action.cash_per_share * impact.original_quantity

        impact.explanation = f"Merger: {action.ticker} acquired"

        if action.acquirer_ticker:
            impact.explanation += f" by {action.acquirer_ticker}"

        if action.conversion_ratio:
            impact.explanation += (
                f". Conversion: {action.conversion_ratio} shares per share. "
                f"Position: {impact.original_quantity} → {impact.new_quantity} shares."
            )

        if action.cash_per_share:
            impact.explanation += (
                f" Cash component: ${action.cash_per_share} per share "
                f"(total: ${impact.cash_received:.2f})."
            )

        return impact

    def _apply_spinoff(
        self, impact: PositionImpact, action: CorporateAction
    ) -> PositionImpact:
        """Apply a spin-off to a position."""
        impact.new_quantity = impact.original_quantity
        impact.new_price = impact.original_price

        if action.spinoff_ratio:
            spinoff_qty = impact.original_quantity * action.spinoff_ratio
            impact.additional_positions = [
                {
                    "ticker": action.spinoff_ticker or "UNKNOWN",
                    "quantity": spinoff_qty,
                    "source": f"Spin-off from {action.ticker}",
                }
            ]

        impact.explanation = (
            f"Spin-off: {action.spinoff_ticker or 'New Company'} "
            f"from {action.ticker} on {action.effective_date}. "
            f"Parent position unchanged at {impact.original_quantity} shares."
        )

        if action.spinoff_ratio and impact.additional_positions:
            impact.explanation += (
                f" New position: {impact.additional_positions[0]['quantity']} shares "
                f"of {action.spinoff_ticker or 'SpinCo'} "
                f"(ratio: {action.spinoff_ratio} per share)."
            )

        return impact

    def _apply_identifier_change(
        self, impact: PositionImpact, action: CorporateAction
    ) -> PositionImpact:
        """Apply a name/ticker/CUSIP change (no position impact)."""
        impact.new_quantity = impact.original_quantity
        impact.new_price = impact.original_price
        impact.new_market_value = impact.original_market_value

        change_type = action.action_type.value.replace("_", " ").title()

        impact.explanation = (
            f"{change_type}: {action.old_value} → {action.new_value} "
            f"effective {action.effective_date}. Position unchanged."
        )
        return impact


class BreakExplainer:
    """Explain whether a reconciliation break is caused by a corporate action."""

    def __init__(self, split_detector, edgar_detector=None):
        self.split_detector = split_detector
        self.edgar_detector = edgar_detector
        self.calculator = PositionImpactCalculator()

    def explain_break(
        self,
        ticker: str,
        internal_qty: Decimal,
        external_qty: Decimal,
        as_of_date: date | None = None,
        lookback_days: int = 365,
    ) -> BreakExplanation:
        """
        Given a quantity break between internal and external positions,
        check if a corporate action explains the discrepancy.

        This is the KEY FUNCTION that makes this tool useful for recon.
        """
        if as_of_date is None:
            as_of_date = date.today()

        start = as_of_date - timedelta(days=lookback_days)

        # Get recent splits
        splits = self.split_detector.get_splits(ticker, start, as_of_date)

        for split in splits:
            if split.split_ratio:
                # Check: external × ratio ≈ internal?
                expected_after_split = external_qty * split.split_ratio
                if abs(expected_after_split - internal_qty) < Decimal("1"):
                    return BreakExplanation(
                        is_explained=True,
                        action=split,
                        expected_quantity=expected_after_split,
                        actual_quantity=internal_qty,
                        explanation=(
                            f"Break explained by {split.split_from}:{split.split_to} "
                            f"stock split on {split.effective_date}. "
                            f"External shows pre-split qty ({external_qty}), "
                            f"internal shows post-split qty ({internal_qty}). "
                            f"Expected: {external_qty} × {split.split_ratio} = "
                            f"{expected_after_split}."
                        ),
                        confidence=0.92,
                    )

                # Check reverse: internal is pre-split, external is post-split
                expected_pre_split = internal_qty / split.split_ratio
                if abs(expected_pre_split - external_qty) < Decimal("1"):
                    return BreakExplanation(
                        is_explained=True,
                        action=split,
                        expected_quantity=internal_qty,
                        actual_quantity=external_qty,
                        explanation=(
                            f"Break explained by {split.split_from}:{split.split_to} "
                            f"stock split on {split.effective_date}. "
                            f"Internal shows pre-split qty ({internal_qty}), "
                            f"external shows post-split qty ({external_qty}). "
                            f"The split may not yet be processed in your internal system."
                        ),
                        confidence=0.90,
                    )

        # No split explains it
        return BreakExplanation(
            is_explained=False,
            explanation=(
                f"No corporate action found for {ticker} in the last "
                f"{lookback_days} days that explains the quantity break "
                f"({internal_qty} vs {external_qty})."
            ),
            confidence=0.0,
        )
