"""
Corporate Actions Engine — the main public API.

Usage:
    from corp_actions import CorporateActionsEngine

    engine = CorporateActionsEngine()

    # Get all actions for a security
    actions = engine.get_actions("AAPL", days_back=365)

    # Check if a break is explained by a corporate action
    explanation = engine.explain_break("AAPL", internal_qty=40000, external_qty=10000)

    # Monitor a portfolio
    alerts = engine.monitor(["AAPL", "MSFT", "NVDA"], days_ahead=14)
"""

import logging
import os
from datetime import date, timedelta
from decimal import Decimal

from corp_actions.db import get_db
from corp_actions.edgar import EdgarEventDetector
from corp_actions.identifiers import IdentifierTracker
from corp_actions.impact import BreakExplainer, PositionImpactCalculator
from corp_actions.models import BreakExplanation, CorporateAction, PositionImpact
from corp_actions.monitor import PortfolioMonitor
from corp_actions.splits import SplitDividendDetector

logger = logging.getLogger(__name__)


class CorporateActionsEngine:
    """
    Main entry point for the corporate actions library.

    ZERO COST by default. Optional Groq key enables LLM-powered
    8-K filing analysis for merger/name-change detection.
    """

    def __init__(
        self,
        edgar_identity: str | None = None,
        groq_api_key: str | None = None,
        cache_ttl_hours: int = 24,
        db_path: str | None = None,
    ):
        """
        Initialize the engine.

        Args:
            edgar_identity: Email for SEC EDGAR User-Agent (required by SEC, free).
                           Defaults to EDGAR_IDENTITY env var.
            groq_api_key: Optional free tier key from console.groq.com.
            cache_ttl_hours: How long to cache yfinance data (default 24h).
            db_path: Path to SQLite database. Default: ~/.corp-actions/corp_actions.db
        """
        identity = edgar_identity or os.environ.get(
            "EDGAR_IDENTITY", "corp-actions-user@example.com"
        )

        if groq_api_key:
            os.environ["GROQ_API_KEY"] = groq_api_key

        self._db_path = db_path
        self.split_detector = SplitDividendDetector(cache_ttl_hours, db_path)
        self.edgar_detector = EdgarEventDetector(identity)
        self.calculator = PositionImpactCalculator()
        self.explainer = BreakExplainer(self.split_detector, self.edgar_detector)
        self.monitor_engine = PortfolioMonitor(
            self.split_detector, self.edgar_detector
        )

        # Seed identifier history on first use
        self._seed_identifiers()

        # Log what's available
        if os.environ.get("GROQ_API_KEY"):
            logger.info(
                "Groq API key found — LLM extraction enabled for 8-K filings"
            )
        else:
            logger.info(
                "No GROQ_API_KEY set — using keyword-based 8-K classification. "
                "For better accuracy, sign up for a free key at console.groq.com"
            )

    def get_actions(
        self,
        ticker: str,
        days_back: int = 365,
        include_edgar: bool = True,
    ) -> list[CorporateAction]:
        """Get all corporate actions for a security."""
        end = date.today()
        start = end - timedelta(days=days_back)

        # Always get splits and dividends
        actions = self.split_detector.get_all_actions(ticker, start, end)

        # Optionally get EDGAR events
        if include_edgar:
            try:
                events = self.edgar_detector.get_recent_events(ticker, days_back)
                actions.extend(events)
            except Exception as e:
                logger.warning(f"EDGAR fetch failed for {ticker}: {e}")

        return sorted(
            actions,
            key=lambda a: (a.effective_date or a.ex_date or date.min),
            reverse=True,
        )

    def explain_break(
        self,
        ticker: str,
        internal_qty: float | Decimal,
        external_qty: float | Decimal,
        as_of_date: date | None = None,
        lookback_days: int = 3650,
    ) -> BreakExplanation:
        """Check if a reconciliation break is explained by a corporate action."""
        return self.explainer.explain_break(
            ticker,
            Decimal(str(internal_qty)),
            Decimal(str(external_qty)),
            as_of_date,
            lookback_days,
        )

    def calculate_impact(
        self,
        action: CorporateAction,
        quantity: float | Decimal,
        price: float | Decimal | None = None,
    ) -> PositionImpact:
        """Calculate how a corporate action affects a position."""
        return self.calculator.calculate(
            action,
            Decimal(str(quantity)),
            Decimal(str(price)) if price else None,
        )

    def monitor(
        self,
        tickers: list[str],
        days_back: int = 7,
        days_ahead: int = 14,
    ) -> list[dict]:
        """Scan a portfolio for relevant corporate actions."""
        return self.monitor_engine.scan_portfolio(tickers, days_back, days_ahead)

    def get_splits(
        self, ticker: str, days_back: int = 3650
    ) -> list[CorporateAction]:
        """Get all stock splits for a security (last 10 years by default)."""
        start = date.today() - timedelta(days=days_back)
        return self.split_detector.get_splits(ticker, start)

    def get_dividends(
        self, ticker: str, days_back: int = 365
    ) -> list[CorporateAction]:
        """Get all dividends for a security (last year by default)."""
        start = date.today() - timedelta(days=days_back)
        return self.split_detector.get_dividends(ticker, start)

    def get_daily_actions(
        self, tickers: list[str] | None = None
    ) -> list[CorporateAction]:
        """
        Get all corporate actions happening today.

        If tickers is None, checks a default set of major tickers.
        """
        today = date.today()

        if tickers is None:
            tickers = [
                "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META",
                "TSLA", "BRK-B", "JPM", "V", "JNJ", "WMT", "PG",
                "MA", "UNH", "HD", "DIS", "PYPL", "NFLX", "ADBE",
            ]

        results = []
        for ticker in tickers:
            actions = self.split_detector.get_all_actions(ticker, today, today)
            results.extend(actions)

        return results

    def _seed_identifiers(self) -> None:
        """Seed known identifier changes on first use."""
        try:
            conn = get_db(self._db_path)
            tracker = IdentifierTracker(conn)
            tracker.seed_known_changes()
            conn.close()
        except Exception as e:
            logger.debug(f"Identifier seeding: {e}")

    def get_identifier_history(self, ticker: str) -> dict:
        """Get the full identifier change timeline for a security.

        Returns a dict with 'security' info and 'history' list.
        Resolves both current and historical tickers (e.g. 'FB' -> META).
        """
        conn = get_db(self._db_path)
        tracker = IdentifierTracker(conn)

        security_id = tracker.resolve_historical(ticker, "ticker")
        if not security_id:
            conn.close()
            return {"security": None, "history": []}

        info = tracker.get_security_info(security_id)
        history = tracker.get_full_history(security_id)
        conn.close()

        return {"security": info, "history": history}

    def resolve_ticker(self, identifier: str) -> str | None:
        """Resolve a possibly-old ticker to the current ticker.

        e.g. resolve_ticker('FB') -> 'META'
        """
        conn = get_db(self._db_path)
        tracker = IdentifierTracker(conn)

        security_id = tracker.resolve_historical(identifier, "ticker")
        if not security_id:
            conn.close()
            return None

        info = tracker.get_security_info(security_id)
        conn.close()
        return info["ticker"] if info else None
