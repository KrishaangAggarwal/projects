"""Module 5: Portfolio Monitor — scan portfolio for corporate action alerts."""

import logging
from datetime import date, timedelta

from corp_actions.models import ActionType, CorporateAction
from corp_actions.splits import SplitDividendDetector

logger = logging.getLogger(__name__)


class PortfolioMonitor:
    """Monitor a portfolio for upcoming and recent corporate actions."""

    def __init__(self, split_detector: SplitDividendDetector, edgar_detector=None):
        self.split_detector = split_detector
        self.edgar_detector = edgar_detector

    def scan_portfolio(
        self,
        tickers: list[str],
        days_back: int = 7,
        days_ahead: int = 14,
    ) -> list[dict]:
        """Scan a portfolio for recent and upcoming corporate actions."""
        alerts = []
        today = date.today()
        start = today - timedelta(days=days_back)
        end = today + timedelta(days=days_ahead)

        for ticker in tickers:
            try:
                actions = self.split_detector.get_all_actions(ticker, start, end)
            except Exception as e:
                logger.warning(f"Failed to fetch actions for {ticker}: {e}")
                continue

            for action in actions:
                action_date = action.effective_date or action.ex_date
                if action_date is None:
                    continue

                is_upcoming = action_date > today
                is_recent = action_date <= today and action_date >= start

                alert = {
                    "ticker": ticker,
                    "action": action,
                    "date": action_date,
                    "is_upcoming": is_upcoming,
                    "is_recent": is_recent,
                    "urgency": (
                        "high"
                        if (is_upcoming and (action_date - today).days <= 3)
                        else "normal"
                    ),
                    "summary": self._summarize(action),
                }
                alerts.append(alert)

            if self.edgar_detector:
                try:
                    events = self.edgar_detector.get_recent_events(ticker, days_back)
                    for event in events:
                        alerts.append({
                            "ticker": ticker,
                            "action": event,
                            "date": event.announcement_date or event.effective_date,
                            "is_upcoming": False,
                            "is_recent": True,
                            "urgency": (
                                "high"
                                if event.action_type
                                in (ActionType.MERGER, ActionType.DELISTING)
                                else "normal"
                            ),
                            "summary": self._summarize(event),
                        })
                except Exception as e:
                    logger.warning(f"EDGAR scan failed for {ticker}: {e}")

        alerts.sort(key=lambda a: a["date"] or date.min)
        return alerts

    def _summarize(self, action: CorporateAction) -> str:
        """Generate a one-line summary for an alert."""
        if action.action_type == ActionType.STOCK_SPLIT:
            return f"{action.ticker}: {action.split_from}:{action.split_to} stock split on {action.effective_date}"
        elif action.action_type == ActionType.REVERSE_SPLIT:
            return f"{action.ticker}: {action.split_from}:{action.split_to} reverse split on {action.effective_date}"
        elif action.action_type == ActionType.CASH_DIVIDEND:
            return f"{action.ticker}: ${action.dividend_amount} dividend (ex-date: {action.ex_date})"
        elif action.action_type == ActionType.SPECIAL_DIVIDEND:
            return f"{action.ticker}: ${action.dividend_amount} SPECIAL dividend (ex-date: {action.ex_date})"
        elif action.action_type == ActionType.MERGER:
            return f"{action.ticker}: MERGER - acquired by {action.acquirer_ticker or 'unknown'}"
        elif action.action_type == ActionType.NAME_CHANGE:
            return f"{action.ticker}: Name changed from {action.old_value} to {action.new_value}"
        elif action.action_type == ActionType.TICKER_CHANGE:
            return f"{action.ticker}: Ticker changing from {action.old_value} to {action.new_value}"
        elif action.action_type == ActionType.SPIN_OFF:
            return f"{action.ticker}: Spinning off {action.spinoff_ticker or 'new entity'}"
        elif action.action_type == ActionType.DELISTING:
            return f"{action.ticker}: DELISTING"
        else:
            return f"{action.ticker}: {action.action_type.value} on {action.effective_date or action.ex_date}"
