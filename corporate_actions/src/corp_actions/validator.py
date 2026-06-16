"""
Multi-Source Cross-Validation — verify corporate actions across data sources.

When an event is detected from one source, check the other for confirmation.
Cross-validated events get a confidence boost.

Split from yfinance → search EDGAR for corroborating 8-K filing
Merger from EDGAR → check if yfinance shows ticker as inactive
"""

import logging
from datetime import date, timedelta

from corp_actions.models import ActionType, CorporateAction

logger = logging.getLogger(__name__)


class CrossValidator:
    """Validate corporate actions across multiple data sources."""

    def __init__(self, split_detector, edgar_detector):
        self.split_detector = split_detector
        self.edgar_detector = edgar_detector

    def validate(self, action: CorporateAction) -> CorporateAction:
        """
        Attempt to cross-validate a corporate action using the other
        data source. Updates the action's validated flag and
        validation_sources in-place.

        Returns the action with updated validation fields.
        """
        if action.source.value == "yfinance":
            return self._validate_yfinance_action(action)
        elif action.source.value in ("edgar_8k", "llm_extracted"):
            return self._validate_edgar_action(action)
        return action

    def validate_batch(
        self, actions: list[CorporateAction]
    ) -> list[CorporateAction]:
        """Validate a batch of actions. Logs progress."""
        validated = []
        for action in actions:
            try:
                result = self.validate(action)
                validated.append(result)
            except Exception as e:
                logger.warning(
                    f"Validation failed for {action.ticker} "
                    f"{action.action_type.value}: {e}"
                )
                validated.append(action)
        return validated

    def _validate_yfinance_action(
        self, action: CorporateAction
    ) -> CorporateAction:
        """
        Validate a yfinance-detected split/dividend against EDGAR.

        Look for 8-K filings from the same company within ±7 days
        that reference the same corporate action type.
        """
        if action.action_type not in (
            ActionType.STOCK_SPLIT,
            ActionType.REVERSE_SPLIT,
        ):
            # Only cross-validate splits against EDGAR for now.
            # Dividends don't typically generate 8-K filings.
            action.validation_sources.append("yfinance")
            return action

        action_date = action.effective_date or action.ex_date
        if not action_date:
            return action

        try:
            # Search EDGAR for 8-K filings around the split date
            days_back = (date.today() - action_date).days + 7
            if days_back < 0:
                return action

            events = self.edgar_detector.get_recent_events(
                action.ticker, days_back=min(days_back, 365)
            )

            # Look for matching event type within ±7 days
            for event in events:
                event_date = event.effective_date or event.announcement_date
                if event_date is None:
                    continue

                date_diff = abs((event_date - action_date).days)
                if date_diff > 7:
                    continue

                # Check if action types are compatible
                if self._types_compatible(action.action_type, event.action_type):
                    action.validated = True
                    action.validation_sources = ["yfinance", "edgar_8k"]
                    # Boost confidence but cap at 0.98
                    action.confidence = min(0.98, action.confidence + 0.15)
                    logger.info(
                        f"Cross-validated {action.ticker} "
                        f"{action.action_type.value} against EDGAR"
                    )
                    return action

        except Exception as e:
            logger.debug(
                f"EDGAR cross-validation failed for {action.ticker}: {e}"
            )

        # Not cross-validated — keep original confidence
        action.validation_sources.append("yfinance")
        return action

    def _validate_edgar_action(
        self, action: CorporateAction
    ) -> CorporateAction:
        """
        Validate an EDGAR-detected event against yfinance.

        For mergers/name changes: check if the old ticker is inactive
        in yfinance. For splits: check if yfinance has the same split.
        """
        if action.action_type in (
            ActionType.STOCK_SPLIT,
            ActionType.REVERSE_SPLIT,
        ):
            return self._validate_edgar_split(action)

        if action.action_type in (
            ActionType.MERGER,
            ActionType.ACQUISITION,
            ActionType.NAME_CHANGE,
            ActionType.TICKER_CHANGE,
            ActionType.DELISTING,
        ):
            return self._validate_edgar_structural(action)

        action.validation_sources.append(action.source.value)
        return action

    def _validate_edgar_split(
        self, action: CorporateAction
    ) -> CorporateAction:
        """Check if yfinance confirms an EDGAR-detected split."""
        action_date = action.effective_date or action.announcement_date
        if not action_date:
            action.validation_sources.append(action.source.value)
            return action

        try:
            start = action_date - timedelta(days=7)
            end = action_date + timedelta(days=7)
            splits = self.split_detector.get_splits(action.ticker, start, end)

            for split in splits:
                split_date = split.effective_date
                if split_date and abs((split_date - action_date).days) <= 7:
                    action.validated = True
                    action.validation_sources = [action.source.value, "yfinance"]
                    action.confidence = min(0.98, action.confidence + 0.15)
                    logger.info(
                        f"Cross-validated {action.ticker} split against yfinance"
                    )
                    return action

        except Exception as e:
            logger.debug(
                f"yfinance cross-validation failed for {action.ticker}: {e}"
            )

        action.validation_sources.append(action.source.value)
        return action

    def _validate_edgar_structural(
        self, action: CorporateAction
    ) -> CorporateAction:
        """
        Validate a merger/name change/delisting by checking if yfinance
        shows the old ticker as inactive.
        """
        old_ticker = action.old_value or action.ticker
        try:
            import yfinance as yf

            t = yf.Ticker(old_ticker)
            info = t.info or {}

            # yfinance returns minimal info for inactive tickers
            # Common indicators: no market cap, no regular market price,
            # or explicit "delisted" status
            market_price = info.get("regularMarketPrice")
            market_cap = info.get("marketCap")

            if market_price is None and market_cap is None:
                # Ticker appears inactive in yfinance
                action.validated = True
                action.validation_sources = [action.source.value, "yfinance"]
                action.confidence = min(0.98, action.confidence + 0.15)
                logger.info(
                    f"Cross-validated {action.ticker} "
                    f"{action.action_type.value}: "
                    f"old ticker {old_ticker} inactive in yfinance"
                )
                return action

        except Exception as e:
            logger.debug(
                f"yfinance validation failed for {old_ticker}: {e}"
            )

        action.validation_sources.append(action.source.value)
        return action

    @staticmethod
    def _types_compatible(type_a: ActionType, type_b: ActionType) -> bool:
        """Check if two action types are compatible for cross-validation."""
        compatible_groups = [
            {ActionType.STOCK_SPLIT, ActionType.REVERSE_SPLIT},
            {ActionType.MERGER, ActionType.ACQUISITION},
            {ActionType.NAME_CHANGE, ActionType.TICKER_CHANGE},
        ]
        for group in compatible_groups:
            if type_a in group and type_b in group:
                return True
        return type_a == type_b
