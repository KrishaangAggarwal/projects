"""
Portfolio Replay Engine — apply every corporate action from entry date
to today and compute expected current positions.

Usage:
    from corp_actions.replay import PortfolioReplay

    replay = PortfolioReplay(split_detector)
    result = replay.replay_position("AAPL", 1000, date(2020, 1, 1))
    print(result.current_quantity)  # 4000 (after 4:1 split)
"""

import csv
import io
import logging
import math
from datetime import date
from decimal import Decimal

from corp_actions.models import ActionType, CorporateAction, ReplayResult

logger = logging.getLogger(__name__)


class PortfolioReplay:
    """Replay corporate actions on positions to compute expected holdings."""

    def __init__(self, split_detector):
        self.split_detector = split_detector

    def replay_position(
        self,
        ticker: str,
        quantity: Decimal | float | int,
        entry_date: date,
        end_date: date | None = None,
    ) -> ReplayResult:
        """
        Replay all corporate actions on a single position from entry_date
        to end_date (default: today).

        Returns ReplayResult with current_quantity, adjustments, and
        cumulative cash received.
        """
        qty = Decimal(str(quantity))
        if end_date is None:
            end_date = date.today()

        result = ReplayResult(
            ticker=ticker,
            entry_date=entry_date,
            entry_quantity=qty,
            current_quantity=qty,
        )

        # Fetch all splits and dividends in the period
        try:
            actions = self.split_detector.get_all_actions(
                ticker, entry_date, end_date
            )
        except Exception as e:
            logger.warning(f"Failed to fetch actions for {ticker}: {e}")
            return result

        if not actions:
            return result

        # Sort chronologically (oldest first)
        actions.sort(
            key=lambda a: a.effective_date or a.ex_date or date.min
        )

        running_qty = qty

        for action in actions:
            action_date = action.effective_date or action.ex_date
            if action_date is None:
                continue

            # Only apply actions on or after entry_date
            if action_date < entry_date:
                continue
            if action_date > end_date:
                continue

            before_qty = running_qty
            adjustment = {
                "date": str(action_date),
                "action_type": action.action_type.value,
                "before_quantity": str(before_qty),
            }

            if action.action_type in (ActionType.STOCK_SPLIT, ActionType.REVERSE_SPLIT):
                if action.split_ratio:
                    running_qty = running_qty * action.split_ratio

                    # Reverse splits produce fractional shares → cash-in-lieu
                    if action.action_type == ActionType.REVERSE_SPLIT:
                        whole = Decimal(math.floor(running_qty))
                        fractional = running_qty - whole
                        if fractional > 0:
                            # Estimate cash-in-lieu (we don't know exact price,
                            # so just track the fractional amount)
                            result.total_cash_in_lieu += fractional
                            running_qty = whole

                    adjustment["split_ratio"] = str(action.split_ratio)
                    adjustment["description"] = (
                        f"{action.split_from}:{action.split_to} "
                        f"{'reverse ' if action.action_type == ActionType.REVERSE_SPLIT else ''}"
                        f"split"
                    )

            elif action.action_type in (
                ActionType.CASH_DIVIDEND, ActionType.SPECIAL_DIVIDEND
            ):
                if action.dividend_amount:
                    cash = action.dividend_amount * abs(running_qty)
                    result.total_cash_received += cash
                    adjustment["dividend_amount"] = str(action.dividend_amount)
                    adjustment["cash_received"] = str(cash)
                    adjustment["description"] = (
                        f"${action.dividend_amount}/share dividend"
                    )
                # Quantity unchanged for cash dividends

            elif action.action_type == ActionType.STOCK_DIVIDEND:
                if action.dividend_amount:
                    running_qty += running_qty * action.dividend_amount
                    adjustment["description"] = (
                        f"Stock dividend ratio {action.dividend_amount}"
                    )

            adjustment["after_quantity"] = str(running_qty)
            result.adjustments.append(adjustment)

        result.current_quantity = running_qty
        return result

    def replay_portfolio(
        self,
        positions: list[dict],
        end_date: date | None = None,
    ) -> list[ReplayResult]:
        """
        Replay corporate actions on a portfolio.

        Args:
            positions: list of dicts with 'ticker', 'quantity', 'entry_date'
                       entry_date can be a date object or 'YYYY-MM-DD' string
            end_date: optional end date (default: today)

        Returns:
            list of ReplayResult, one per position
        """
        results = []
        for pos in positions:
            ticker = pos.get("ticker", "").strip().upper()
            if not ticker:
                continue

            qty = pos.get("quantity", 0)
            entry = pos.get("entry_date")
            if isinstance(entry, str):
                entry = date.fromisoformat(entry)

            if not entry:
                logger.warning(f"Skipping {ticker}: no entry_date")
                continue

            result = self.replay_position(ticker, qty, entry, end_date)
            results.append(result)

        return results

    @staticmethod
    def parse_csv(csv_text: str) -> list[dict]:
        """Parse a CSV string (or file contents) into position dicts.

        Expected columns: ticker, quantity, entry_date
        Auto-detects common column name variations.
        """
        reader = csv.DictReader(io.StringIO(csv_text.strip()))

        # Normalize field names
        positions = []
        for row in reader:
            normalized = {k.strip().lower(): v.strip() for k, v in row.items()}

            ticker = (
                normalized.get("ticker")
                or normalized.get("symbol")
                or normalized.get("sym")
                or ""
            )
            quantity = (
                normalized.get("quantity")
                or normalized.get("qty")
                or normalized.get("shares")
                or "0"
            )
            entry_date = (
                normalized.get("entry_date")
                or normalized.get("date")
                or normalized.get("purchase_date")
                or normalized.get("since")
                or ""
            )

            if ticker and entry_date:
                try:
                    positions.append({
                        "ticker": ticker.upper(),
                        "quantity": float(quantity),
                        "entry_date": entry_date,
                    })
                except (ValueError, TypeError) as e:
                    logger.warning(f"Skipping bad CSV row: {row} ({e})")

        return positions
