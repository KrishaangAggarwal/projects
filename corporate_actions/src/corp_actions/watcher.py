"""
Near-Real-Time Event Watcher — monitor for new corporate actions.

Uses SEC EDGAR full-text search (EFTS) API and yfinance cache diffs.
NOT true real-time (that requires paid DTCC feeds). Latency: minutes
to hours for EDGAR, 1-2 days for yfinance.

Usage:
    from corp_actions.watcher import EventWatcher

    watcher = EventWatcher(split_detector, edgar_detector, db_conn)
    new_events = watcher.check_once(["AAPL", "META", "NVDA"])
"""

import json
import logging
import time
from datetime import date, timedelta

from corp_actions.db import get_db, new_id
from corp_actions.models import ActionType, CorporateAction, DataSource

logger = logging.getLogger(__name__)

# Minimum poll interval in seconds
MIN_INTERVAL = 300  # 5 minutes


class EventWatcher:
    """Monitor for new corporate actions across watchlist tickers.

    Two detection methods:
    1. EDGAR EFTS API — searches for new 8-K filings matching tickers
    2. yfinance cache diff — detects new splits/dividends not in SQLite
    """

    def __init__(self, split_detector, edgar_detector, db_path=None):
        self.split_detector = split_detector
        self.edgar_detector = edgar_detector
        self._db_path = db_path
        self._db = get_db(db_path)
        self._ensure_seen_table()

    def _ensure_seen_table(self):
        """Create the seen_events table if it doesn't exist."""
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS seen_events (
                id TEXT PRIMARY KEY,
                ticker TEXT NOT NULL,
                event_type TEXT NOT NULL,
                event_key TEXT NOT NULL UNIQUE,
                first_seen_at TEXT NOT NULL DEFAULT (datetime('now')),
                source TEXT,
                raw_data TEXT
            )
        """)
        self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_seen_ticker
            ON seen_events(ticker)
        """)
        self._db.commit()

    def check_once(self, tickers: list[str]) -> list[CorporateAction]:
        """
        Check all tickers once for new events. Returns only genuinely
        new events not previously seen.
        """
        new_events = []

        for ticker in tickers:
            # 1. Check yfinance for new splits/dividends
            try:
                yf_events = self._check_yfinance(ticker)
                new_events.extend(yf_events)
            except Exception as e:
                logger.warning(f"yfinance check failed for {ticker}: {e}")

            # 2. Check EDGAR EFTS for new 8-K filings
            try:
                edgar_events = self._check_edgar_efts(ticker)
                new_events.extend(edgar_events)
            except Exception as e:
                logger.warning(f"EDGAR EFTS check failed for {ticker}: {e}")

        return new_events

    def watch(
        self,
        tickers: list[str],
        interval: int = 1800,
        callback=None,
    ):
        """
        Continuously monitor tickers for new events.

        Args:
            tickers: list of tickers to watch
            interval: seconds between checks (default 1800 = 30 min,
                      minimum 300 = 5 min)
            callback: optional function called with each new event.
                      If None, events are printed to stdout.
        """
        interval = max(interval, MIN_INTERVAL)

        logger.info(
            f"Monitoring started for {len(tickers)} tickers. "
            f"Interval: {interval}s. "
            f"Note: this uses free data sources with variable latency. "
            f"Events may appear 1-24 hours after they occur."
        )

        try:
            while True:
                new_events = self.check_once(tickers)

                for event in new_events:
                    if callback:
                        callback(event)
                    else:
                        _date = event.effective_date or event.ex_date or event.announcement_date
                        print(
                            f"  NEW: {event.ticker} | "
                            f"{event.action_type.value} | "
                            f"{_date} | "
                            f"[{event.source.value}]"
                        )

                if not new_events:
                    logger.debug(
                        f"No new events. Next check in {interval}s."
                    )

                time.sleep(interval)

        except KeyboardInterrupt:
            logger.info("Monitoring stopped.")

    def _check_yfinance(self, ticker: str) -> list[CorporateAction]:
        """
        Compare current yfinance data against SQLite cache.
        New splits/dividends not in cache = new events.
        """
        new_events = []

        try:
            # Fetch current data
            today = date.today()
            start = today - timedelta(days=30)  # Only check recent
            actions = self.split_detector.get_all_actions(ticker, start, today)

            for action in actions:
                event_key = self._make_event_key(action)
                if not self._is_seen(event_key):
                    self._mark_seen(ticker, action, event_key)
                    new_events.append(action)

        except Exception as e:
            logger.debug(f"yfinance diff check failed for {ticker}: {e}")

        return new_events

    def _check_edgar_efts(self, ticker: str) -> list[CorporateAction]:
        """
        Search EDGAR EFTS API for recent 8-K filings.
        Only returns events not previously seen.

        Uses httpx to query:
        https://efts.sec.gov/LATEST/search-index?q="TICKER"&forms=8-K
        """
        new_events = []

        try:
            import httpx

            today = date.today()
            start = today - timedelta(days=3)  # Only check last 3 days

            url = "https://efts.sec.gov/LATEST/search-index"
            params = {
                "q": f'"{ticker}"',
                "forms": "8-K",
                "dateRange": "custom",
                "startdt": start.isoformat(),
                "enddt": today.isoformat(),
            }
            headers = {
                "User-Agent": (
                    self.edgar_detector._identity_email
                    if hasattr(self.edgar_detector, "_identity_email")
                    else "corp-actions-watcher corp-actions@example.com"
                ),
                "Accept": "application/json",
            }

            resp = httpx.get(
                url, params=params, headers=headers, timeout=15.0
            )

            if resp.status_code != 200:
                # EFTS may not be available — fall back to edgartools
                return self._check_edgar_edgartools(ticker)

            data = resp.json()
            hits = data.get("hits", {}).get("hits", [])

            for hit in hits[:10]:
                source = hit.get("_source", {})
                accession = source.get("file_num", "") or source.get("accession_no", "")
                filing_date_str = source.get("file_date", "")

                event_key = f"edgar_8k:{ticker}:{accession}"
                if self._is_seen(event_key):
                    continue

                # We found a new 8-K — classify it via the normal pipeline
                try:
                    events = self.edgar_detector.get_recent_events(
                        ticker, days_back=7
                    )
                    for event in events:
                        ek = self._make_event_key(event)
                        if not self._is_seen(ek):
                            self._mark_seen(ticker, event, ek)
                            new_events.append(event)
                except Exception as e:
                    logger.debug(f"EDGAR classify failed for {ticker}: {e}")

                # Mark the EFTS hit as seen regardless
                self._mark_seen_raw(ticker, "edgar_efts", event_key, {
                    "accession": accession,
                    "filing_date": filing_date_str,
                })
                break  # Only process first new hit per cycle

        except ImportError:
            logger.debug("httpx not available for EFTS, falling back to edgartools")
            return self._check_edgar_edgartools(ticker)
        except Exception as e:
            logger.debug(f"EFTS search failed for {ticker}: {e}")
            return self._check_edgar_edgartools(ticker)

        return new_events

    def _check_edgar_edgartools(self, ticker: str) -> list[CorporateAction]:
        """Fallback: use edgartools to check recent filings."""
        new_events = []
        try:
            events = self.edgar_detector.get_recent_events(ticker, days_back=7)
            for event in events:
                event_key = self._make_event_key(event)
                if not self._is_seen(event_key):
                    self._mark_seen(ticker, event, event_key)
                    new_events.append(event)
        except Exception as e:
            logger.debug(f"edgartools check failed for {ticker}: {e}")
        return new_events

    def _make_event_key(self, action: CorporateAction) -> str:
        """Create a unique key for deduplication."""
        _date = (
            action.effective_date
            or action.ex_date
            or action.announcement_date
            or date.min
        )
        filing_id = action.source_filing_id or ""
        return (
            f"{action.ticker}:{action.action_type.value}:"
            f"{_date}:{filing_id}"
        )

    def _is_seen(self, event_key: str) -> bool:
        """Check if we've already seen this event."""
        row = self._db.execute(
            "SELECT 1 FROM seen_events WHERE event_key = ?",
            (event_key,),
        ).fetchone()
        return row is not None

    def _mark_seen(
        self,
        ticker: str,
        action: CorporateAction,
        event_key: str,
    ):
        """Record that we've seen this event."""
        try:
            self._db.execute(
                """INSERT OR IGNORE INTO seen_events
                   (id, ticker, event_type, event_key, source, raw_data)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    new_id(),
                    ticker,
                    action.action_type.value,
                    event_key,
                    action.source.value,
                    json.dumps(action.raw_data) if action.raw_data else None,
                ),
            )
            self._db.commit()
        except Exception as e:
            logger.debug(f"Failed to mark event as seen: {e}")

    def _mark_seen_raw(
        self,
        ticker: str,
        event_type: str,
        event_key: str,
        raw_data: dict | None = None,
    ):
        """Record a raw event key as seen."""
        try:
            self._db.execute(
                """INSERT OR IGNORE INTO seen_events
                   (id, ticker, event_type, event_key, source, raw_data)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    new_id(),
                    ticker,
                    event_type,
                    event_key,
                    "edgar_efts",
                    json.dumps(raw_data) if raw_data else None,
                ),
            )
            self._db.commit()
        except Exception as e:
            logger.debug(f"Failed to mark raw event as seen: {e}")
