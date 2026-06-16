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
    """Explain whether a reconciliation break is caused by a corporate action.

    Checks splits, dividends, mergers, spin-offs, and identifier changes.
    Returns ranked explanations sorted by confidence.
    """

    def __init__(self, split_detector, edgar_detector=None, identifier_tracker=None):
        self.split_detector = split_detector
        self.edgar_detector = edgar_detector
        self.identifier_tracker = identifier_tracker
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

        Returns the highest-confidence explanation found.
        """
        explanations = self.explain_all_breaks(
            ticker, internal_qty, external_qty, as_of_date, lookback_days
        )
        if explanations:
            return explanations[0]

        return BreakExplanation(
            is_explained=False,
            explanation=(
                f"No corporate action found for {ticker} in the last "
                f"{lookback_days} days that explains the quantity break "
                f"({internal_qty} vs {external_qty})."
            ),
            confidence=0.0,
            break_type="quantity",
        )

    def explain_all_breaks(
        self,
        ticker: str,
        internal_qty: Decimal,
        external_qty: Decimal,
        as_of_date: date | None = None,
        lookback_days: int = 365,
    ) -> list[BreakExplanation]:
        """
        Return ALL possible explanations for a quantity break, ranked by
        confidence descending. Checks splits, mergers, spin-offs, and
        multi-action combinations.
        """
        if as_of_date is None:
            as_of_date = date.today()

        # Positions match — no break
        if abs(internal_qty - external_qty) < Decimal("0.01"):
            return []

        start = as_of_date - timedelta(days=lookback_days)
        explanations: list[BreakExplanation] = []

        # 1. Check splits (highest confidence)
        try:
            splits = self.split_detector.get_splits(ticker, start, as_of_date)
            explanations.extend(
                self._check_splits(splits, internal_qty, external_qty)
            )
        except Exception as e:
            logger.warning(f"Split fetch failed for {ticker}: {e}")

        # 2. Check dividends for stock dividend breaks
        try:
            dividends = self.split_detector.get_dividends(ticker, start, as_of_date)
            explanations.extend(
                self._check_stock_dividends(dividends, internal_qty, external_qty)
            )
        except Exception as e:
            logger.warning(f"Dividend fetch failed for {ticker}: {e}")

        # 3. Check EDGAR events for mergers and spin-offs
        if self.edgar_detector:
            try:
                events = self.edgar_detector.get_recent_events(ticker, lookback_days)
                explanations.extend(
                    self._check_mergers(events, internal_qty, external_qty)
                )
                explanations.extend(
                    self._check_spinoffs(events, internal_qty, external_qty)
                )
            except Exception as e:
                logger.warning(f"EDGAR fetch failed for {ticker}: {e}")

        # 4. Check multi-action combinations if single actions didn't explain
        if not any(e.is_explained for e in explanations):
            try:
                splits = self.split_detector.get_splits(ticker, start, as_of_date)
                combo = self._check_combinations(
                    splits, internal_qty, external_qty
                )
                if combo:
                    explanations.append(combo)
            except Exception as e:
                logger.debug(f"Combination check failed for {ticker}: {e}")

        return sorted(explanations, key=lambda e: e.confidence, reverse=True)

    def explain_cash_break(
        self,
        ticker: str,
        shares: Decimal,
        cash_difference: Decimal,
        as_of_date: date | None = None,
        lookback_days: int = 365,
    ) -> list[BreakExplanation]:
        """
        Explain a cash discrepancy. Checks for missed dividends,
        merger cash components, and fractional share cash-in-lieu.
        """
        if as_of_date is None:
            as_of_date = date.today()

        start = as_of_date - timedelta(days=lookback_days)
        explanations: list[BreakExplanation] = []

        # 1. Check dividends
        try:
            dividends = self.split_detector.get_dividends(ticker, start, as_of_date)
            for div in dividends:
                if div.dividend_amount and shares:
                    expected_cash = div.dividend_amount * abs(shares)
                    if abs(expected_cash - abs(cash_difference)) < Decimal("0.50"):
                        explanations.append(BreakExplanation(
                            is_explained=True,
                            action=div,
                            expected_quantity=expected_cash,
                            actual_quantity=cash_difference,
                            explanation=(
                                f"Cash break of ${cash_difference} matches "
                                f"${div.dividend_amount}/share dividend on "
                                f"{div.ex_date} for {shares} shares "
                                f"(expected ${expected_cash})."
                            ),
                            confidence=0.88,
                            break_type="cash",
                        ))

            # Check cumulative dividends
            if dividends:
                total_div = sum(
                    (d.dividend_amount or Decimal(0)) * abs(shares)
                    for d in dividends
                )
                if (
                    abs(total_div - abs(cash_difference)) < Decimal("1.00")
                    and len(dividends) > 1
                ):
                    explanations.append(BreakExplanation(
                        is_explained=True,
                        action=dividends[0],
                        expected_quantity=total_div,
                        actual_quantity=cash_difference,
                        explanation=(
                            f"Cash break of ${cash_difference} matches cumulative "
                            f"dividends of ${total_div} from {len(dividends)} "
                            f"payments on {shares} shares."
                        ),
                        confidence=0.85,
                        break_type="cash",
                    ))
        except Exception as e:
            logger.warning(f"Dividend fetch failed for cash break: {e}")

        # 2. Check EDGAR for merger cash components
        if self.edgar_detector:
            try:
                events = self.edgar_detector.get_recent_events(ticker, lookback_days)
                for event in events:
                    if (
                        event.action_type in (ActionType.MERGER, ActionType.ACQUISITION)
                        and event.cash_per_share
                    ):
                        expected_cash = event.cash_per_share * abs(shares)
                        if abs(expected_cash - abs(cash_difference)) < Decimal("1.00"):
                            explanations.append(BreakExplanation(
                                is_explained=True,
                                action=event,
                                expected_quantity=expected_cash,
                                actual_quantity=cash_difference,
                                explanation=(
                                    f"Cash break matches merger cash component of "
                                    f"${event.cash_per_share}/share for {shares} "
                                    f"shares (expected ${expected_cash})."
                                ),
                                confidence=0.75,
                                break_type="cash",
                            ))
            except Exception as e:
                logger.warning(f"EDGAR fetch failed for cash break: {e}")

        # 3. Check for fractional share cash-in-lieu from reverse splits
        try:
            splits = self.split_detector.get_splits(ticker, start, as_of_date)
            for split in splits:
                if (
                    split.action_type == ActionType.REVERSE_SPLIT
                    and split.split_ratio
                ):
                    post_split = abs(shares) * split.split_ratio
                    fractional = post_split - int(post_split)
                    if fractional > 0 and abs(cash_difference) < Decimal("500"):
                        explanations.append(BreakExplanation(
                            is_explained=True,
                            action=split,
                            expected_quantity=Decimal(str(fractional)),
                            actual_quantity=cash_difference,
                            explanation=(
                                f"Cash break may be cash-in-lieu for {fractional:.4f} "
                                f"fractional shares from {split.split_from}:"
                                f"{split.split_to} reverse split."
                            ),
                            confidence=0.60,
                            break_type="cash",
                        ))
        except Exception as e:
            logger.debug(f"Split fetch failed for cash-in-lieu check: {e}")

        return sorted(explanations, key=lambda e: e.confidence, reverse=True)

    def explain_missing_ticker(
        self,
        ticker: str,
    ) -> list[BreakExplanation]:
        """
        Explain why a ticker might be missing. Checks for renames,
        delistings, and mergers.
        """
        explanations: list[BreakExplanation] = []

        # 1. Check identifier history
        if self.identifier_tracker:
            try:
                sec_id = self.identifier_tracker.resolve_historical(ticker, "ticker")
                if sec_id:
                    info = self.identifier_tracker.get_security_info(sec_id)
                    history = self.identifier_tracker.get_full_history(sec_id)

                    current_ticker = info.get("ticker", "") if info else ""
                    if current_ticker and current_ticker.upper() != ticker.upper():
                        ticker_changes = [
                            h for h in history
                            if h["identifier_type"] == "ticker"
                        ]
                        explanations.append(BreakExplanation(
                            is_explained=True,
                            explanation=(
                                f"Ticker '{ticker}' was renamed to "
                                f"'{current_ticker}'. "
                                + (
                                    f"Change effective "
                                    f"{ticker_changes[0]['effective_date']}."
                                    if ticker_changes
                                    else ""
                                )
                            ),
                            confidence=0.95,
                            break_type="ticker",
                        ))

                    is_active = info.get("is_active", 1) if info else 1
                    if not is_active:
                        explanations.append(BreakExplanation(
                            is_explained=True,
                            explanation=(
                                f"Ticker '{ticker}' is delisted/inactive. "
                                f"Security: {info.get('name', 'unknown')}."
                            ),
                            confidence=0.90,
                            break_type="ticker",
                        ))
            except Exception as e:
                logger.debug(f"Identifier lookup failed for {ticker}: {e}")

        # 2. Check EDGAR for recent merger/delisting
        if self.edgar_detector:
            try:
                events = self.edgar_detector.get_recent_events(ticker, 365)
                for event in events:
                    if event.action_type == ActionType.DELISTING:
                        explanations.append(BreakExplanation(
                            is_explained=True,
                            action=event,
                            explanation=(
                                f"Ticker '{ticker}' was delisted "
                                f"(detected from 8-K filing)."
                            ),
                            confidence=0.80,
                            break_type="ticker",
                        ))
                    elif event.action_type in (
                        ActionType.MERGER, ActionType.ACQUISITION
                    ):
                        explanations.append(BreakExplanation(
                            is_explained=True,
                            action=event,
                            explanation=(
                                f"Ticker '{ticker}' was involved in a merger"
                                + (
                                    f" (acquirer: {event.acquirer_ticker})"
                                    if event.acquirer_ticker
                                    else ""
                                )
                                + "."
                            ),
                            confidence=0.70,
                            break_type="ticker",
                        ))
            except Exception as e:
                logger.debug(f"EDGAR check failed for missing ticker: {e}")

        if not explanations:
            explanations.append(BreakExplanation(
                is_explained=False,
                explanation=(
                    f"Ticker '{ticker}' not found in identifier history "
                    f"or recent EDGAR filings."
                ),
                confidence=0.0,
                break_type="ticker",
            ))

        return sorted(explanations, key=lambda e: e.confidence, reverse=True)

    def _check_splits(
        self,
        splits: list[CorporateAction],
        internal_qty: Decimal,
        external_qty: Decimal,
    ) -> list[BreakExplanation]:
        results = []
        for split in splits:
            if not split.split_ratio:
                continue

            # external × ratio ≈ internal? (external is pre-split)
            expected = external_qty * split.split_ratio
            if abs(expected - internal_qty) < Decimal("1"):
                results.append(BreakExplanation(
                    is_explained=True,
                    action=split,
                    expected_quantity=expected,
                    actual_quantity=internal_qty,
                    explanation=(
                        f"Break explained by {split.split_from}:{split.split_to} "
                        f"stock split on {split.effective_date}. "
                        f"External shows pre-split qty ({external_qty}), "
                        f"internal shows post-split qty ({internal_qty}). "
                        f"Expected: {external_qty} × {split.split_ratio} = "
                        f"{expected}."
                    ),
                    confidence=0.92,
                    break_type="quantity",
                ))

            # internal / ratio ≈ external? (internal is pre-split)
            expected_pre = internal_qty / split.split_ratio
            if abs(expected_pre - external_qty) < Decimal("1"):
                results.append(BreakExplanation(
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
                    break_type="quantity",
                ))

        return results

    def _check_stock_dividends(
        self,
        dividends: list[CorporateAction],
        internal_qty: Decimal,
        external_qty: Decimal,
    ) -> list[BreakExplanation]:
        """Check if a stock dividend explains the quantity difference."""
        results = []
        for div in dividends:
            if div.action_type != ActionType.STOCK_DIVIDEND or not div.dividend_amount:
                continue
            # Stock dividend: qty increases by dividend_amount ratio
            expected = external_qty * (1 + div.dividend_amount)
            if abs(expected - internal_qty) < Decimal("1"):
                results.append(BreakExplanation(
                    is_explained=True,
                    action=div,
                    expected_quantity=expected,
                    actual_quantity=internal_qty,
                    explanation=(
                        f"Break explained by stock dividend of "
                        f"{div.dividend_amount} on {div.ex_date}."
                    ),
                    confidence=0.85,
                    break_type="quantity",
                ))
        return results

    def _check_mergers(
        self,
        events: list[CorporateAction],
        internal_qty: Decimal,
        external_qty: Decimal,
    ) -> list[BreakExplanation]:
        """Check if a merger conversion ratio explains the break."""
        results = []
        for event in events:
            if event.action_type not in (ActionType.MERGER, ActionType.ACQUISITION):
                continue
            if not event.conversion_ratio:
                continue
            expected = external_qty * event.conversion_ratio
            if abs(expected - internal_qty) < Decimal("1"):
                results.append(BreakExplanation(
                    is_explained=True,
                    action=event,
                    expected_quantity=expected,
                    actual_quantity=internal_qty,
                    explanation=(
                        f"Break explained by merger conversion ratio "
                        f"{event.conversion_ratio}"
                        + (f" (acquirer: {event.acquirer_ticker})" if event.acquirer_ticker else "")
                        + f". {external_qty} × {event.conversion_ratio} = {expected}."
                    ),
                    confidence=0.75,
                    break_type="quantity",
                ))
        return results

    def _check_spinoffs(
        self,
        events: list[CorporateAction],
        internal_qty: Decimal,
        external_qty: Decimal,
    ) -> list[BreakExplanation]:
        """Check if a spin-off ratio explains the missing quantity."""
        results = []
        diff = abs(internal_qty - external_qty)
        if diff == 0:
            return results

        for event in events:
            if event.action_type != ActionType.SPIN_OFF or not event.spinoff_ratio:
                continue
            # The "missing" quantity might be spun off
            spinoff_qty = max(internal_qty, external_qty) * event.spinoff_ratio
            if abs(spinoff_qty - diff) < Decimal("1"):
                results.append(BreakExplanation(
                    is_explained=True,
                    action=event,
                    expected_quantity=spinoff_qty,
                    actual_quantity=diff,
                    explanation=(
                        f"Quantity difference of {diff} may be explained by "
                        f"spin-off of {event.spinoff_ticker or 'new entity'} "
                        f"(ratio: {event.spinoff_ratio})."
                    ),
                    confidence=0.65,
                    break_type="quantity",
                ))
        return results

    def _check_combinations(
        self,
        splits: list[CorporateAction],
        internal_qty: Decimal,
        external_qty: Decimal,
    ) -> BreakExplanation | None:
        """Try applying multiple splits chronologically to explain a break."""
        if len(splits) < 2:
            return None

        # Sort chronologically
        sorted_splits = sorted(
            [s for s in splits if s.split_ratio],
            key=lambda s: s.effective_date or date.min,
        )

        # Apply all splits in order to external_qty
        running_qty = external_qty
        applied = []
        for split in sorted_splits:
            running_qty = running_qty * split.split_ratio
            applied.append(split)

        if abs(running_qty - internal_qty) < Decimal("1"):
            desc = " → ".join(
                f"{s.split_from}:{s.split_to}" for s in applied
            )
            return BreakExplanation(
                is_explained=True,
                action=applied[-1],
                expected_quantity=running_qty,
                actual_quantity=internal_qty,
                explanation=(
                    f"Break explained by {len(applied)} sequential splits "
                    f"({desc}). {external_qty} → {running_qty}."
                ),
                confidence=0.88,
                break_type="quantity",
            )
        return None
