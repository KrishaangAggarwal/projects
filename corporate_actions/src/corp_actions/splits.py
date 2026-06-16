"""
Module 1: Split & Dividend Detector — powered by yfinance.

COST: $0. No API key needed. Yahoo Finance is free (but unofficial).
Caches aggressively to survive yfinance outages.
"""

import logging
from datetime import date, datetime, timedelta
from decimal import Decimal

import yfinance as yf

from corp_actions.db import get_db, log_fetch, store_json, new_id
from corp_actions.models import ActionType, CorporateAction, DataSource

logger = logging.getLogger(__name__)


class SplitDividendDetector:
    """Fetch splits and dividends from Yahoo Finance with caching."""

    def __init__(self, cache_ttl_hours: int = 24, db_path: str | None = None):
        self.cache_ttl = timedelta(hours=cache_ttl_hours)
        self._cache: dict[str, dict] = {}  # ticker → {data, fetched_at}
        self._db_path = db_path

    def get_splits(
        self,
        ticker: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[CorporateAction]:
        """
        Get all stock splits for a ticker.

        Returns list of CorporateAction with action_type STOCK_SPLIT or REVERSE_SPLIT.
        """
        raw = self._fetch_actions(ticker)
        if raw is None:
            return []

        splits = raw.get("splits", {})
        results = []

        for split_date, ratio in splits.items():
            ratio_float = float(ratio)

            # Determine split type
            if ratio_float > 1.0:
                action_type = ActionType.STOCK_SPLIT
                split_from = 1
                split_to = int(ratio_float) if ratio_float == int(ratio_float) else None
            elif 0 < ratio_float < 1.0:
                action_type = ActionType.REVERSE_SPLIT
                split_to = 1
                split_from = int(round(1 / ratio_float))
            else:
                logger.warning(
                    f"Unexpected split ratio {ratio} for {ticker} on {split_date}"
                )
                continue

            # Handle fractional ratios like 3:2 (ratio=1.5)
            if split_to is None:
                # e.g. 1.5 → 3:2
                from fractions import Fraction
                frac = Fraction(ratio_float).limit_denominator(100)
                split_to = frac.numerator
                split_from = frac.denominator

            eff_date = split_date.date() if hasattr(split_date, "date") else split_date

            action = CorporateAction(
                ticker=ticker,
                action_type=action_type,
                effective_date=eff_date,
                ex_date=eff_date,
                split_ratio=Decimal(str(ratio_float)),
                split_from=split_from,
                split_to=split_to,
                source=DataSource.YFINANCE,
                confidence=0.95,
                raw_data={"ratio": ratio_float, "date": str(split_date)},
            )

            # Apply date filter
            if start_date and eff_date < start_date:
                continue
            if end_date and eff_date > end_date:
                continue

            results.append(action)

        return sorted(results, key=lambda a: a.effective_date or date.min)

    def get_dividends(
        self,
        ticker: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[CorporateAction]:
        """
        Get all dividends for a ticker.

        Returns list of CorporateAction with action_type CASH_DIVIDEND or SPECIAL_DIVIDEND.
        """
        raw = self._fetch_actions(ticker)
        if raw is None:
            return []

        dividends = raw.get("dividends", {})
        results = []

        # Detect special dividends (significantly larger than typical)
        amounts = [float(amt) for amt in dividends.values() if float(amt) > 0]
        median_dividend = sorted(amounts)[len(amounts) // 2] if amounts else 0

        for div_date, amount in dividends.items():
            amount_dec = Decimal(str(float(amount)))

            if amount_dec <= 0:
                continue

            # Heuristic: special dividend if >3x the median
            is_special = median_dividend > 0 and float(amount_dec) > median_dividend * 3

            ex = div_date.date() if hasattr(div_date, "date") else div_date

            action = CorporateAction(
                ticker=ticker,
                action_type=(
                    ActionType.SPECIAL_DIVIDEND if is_special else ActionType.CASH_DIVIDEND
                ),
                ex_date=ex,
                effective_date=ex,
                dividend_amount=amount_dec,
                dividend_currency="USD",
                source=DataSource.YFINANCE,
                confidence=0.95,
                raw_data={"amount": float(amount), "date": str(div_date)},
            )

            # Apply date filter
            if start_date and ex < start_date:
                continue
            if end_date and ex > end_date:
                continue

            results.append(action)

        return sorted(results, key=lambda a: a.ex_date or date.min)

    def get_all_actions(
        self,
        ticker: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[CorporateAction]:
        """Get all splits and dividends combined, sorted by date."""
        splits = self.get_splits(ticker, start_date, end_date)
        dividends = self.get_dividends(ticker, start_date, end_date)

        combined = splits + dividends
        return sorted(
            combined, key=lambda a: (a.effective_date or a.ex_date or date.min)
        )

    def _fetch_actions(self, ticker: str) -> dict | None:
        """Fetch from yfinance with in-memory + SQLite caching."""
        # Check in-memory cache
        if ticker in self._cache:
            cached = self._cache[ticker]
            if datetime.now() - cached["fetched_at"] < self.cache_ttl:
                return cached["data"]

        try:
            yf_ticker = yf.Ticker(ticker)
            splits = yf_ticker.splits
            dividends = yf_ticker.dividends

            # Convert pandas Series to plain dicts so .items()/.values()
            # work consistently (pandas Series.values is a numpy array, not callable)
            data = {
                "splits": (
                    dict(splits) if splits is not None and len(splits) > 0 else {}
                ),
                "dividends": (
                    dict(dividends) if dividends is not None and len(dividends) > 0 else {}
                ),
            }

            self._cache[ticker] = {"data": data, "fetched_at": datetime.now()}

            # Persist to SQLite for offline use
            self._cache_to_db(ticker, data)

            return data

        except Exception as e:
            logger.error(f"yfinance error for {ticker}: {e}")

            # Return stale in-memory cache if available
            if ticker in self._cache:
                logger.warning(f"Returning stale cache for {ticker}")
                return self._cache[ticker]["data"]

            # Try SQLite cache as last resort
            db_data = self._load_from_db(ticker)
            if db_data:
                logger.warning(f"Returning SQLite cache for {ticker}")
                return db_data

            return None

    def _cache_to_db(self, ticker: str, data: dict) -> None:
        """Persist fetched data to SQLite for offline resilience."""
        try:
            conn = get_db(self._db_path)
            # Store splits
            for split_date, ratio in data.get("splits", {}).items():
                eff = split_date.date() if hasattr(split_date, "date") else split_date
                ratio_f = float(ratio)

                # Check if already cached
                existing = conn.execute(
                    """SELECT id FROM corporate_actions
                       WHERE action_type IN ('stock_split', 'reverse_split')
                       AND source = 'yfinance'
                       AND effective_date = ?
                       AND raw_data LIKE ?""",
                    (str(eff), f'%"ticker": "{ticker}"%'),
                ).fetchone()

                if not existing:
                    conn.execute(
                        """INSERT INTO corporate_actions
                           (id, action_type, effective_date, ex_date, split_factor,
                            source, extraction_confidence, raw_data)
                           VALUES (?, ?, ?, ?, ?, 'yfinance', 0.95, ?)""",
                        (
                            new_id(),
                            "stock_split" if ratio_f > 1 else "reverse_split",
                            str(eff),
                            str(eff),
                            ratio_f,
                            store_json(
                                {"ticker": ticker, "ratio": ratio_f, "date": str(eff)}
                            ),
                        ),
                    )

            # Store dividends
            for div_date, amount in data.get("dividends", {}).items():
                ex = div_date.date() if hasattr(div_date, "date") else div_date
                amt = float(amount)

                existing = conn.execute(
                    """SELECT id FROM corporate_actions
                       WHERE action_type IN ('cash_dividend', 'special_dividend')
                       AND source = 'yfinance'
                       AND ex_date = ?
                       AND raw_data LIKE ?""",
                    (str(ex), f'%"ticker": "{ticker}"%'),
                ).fetchone()

                if not existing:
                    conn.execute(
                        """INSERT INTO corporate_actions
                           (id, action_type, ex_date, effective_date,
                            dividend_amount, dividend_currency,
                            source, extraction_confidence, raw_data)
                           VALUES (?, 'cash_dividend', ?, ?, ?, 'USD', 'yfinance', 0.95, ?)""",
                        (
                            new_id(),
                            str(ex),
                            str(ex),
                            amt,
                            store_json(
                                {"ticker": ticker, "amount": amt, "date": str(ex)}
                            ),
                        ),
                    )

            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"Failed to cache to SQLite for {ticker}: {e}")

    def _load_from_db(self, ticker: str) -> dict | None:
        """Load cached data from SQLite (fallback when yfinance is down)."""
        try:
            conn = get_db(self._db_path)

            splits_rows = conn.execute(
                """SELECT effective_date, split_factor FROM corporate_actions
                   WHERE action_type IN ('stock_split', 'reverse_split')
                   AND source = 'yfinance'
                   AND raw_data LIKE ?""",
                (f'%"ticker": "{ticker}"%',),
            ).fetchall()

            div_rows = conn.execute(
                """SELECT ex_date, dividend_amount FROM corporate_actions
                   WHERE action_type IN ('cash_dividend', 'special_dividend')
                   AND source = 'yfinance'
                   AND raw_data LIKE ?""",
                (f'%"ticker": "{ticker}"%',),
            ).fetchall()

            conn.close()

            if not splits_rows and not div_rows:
                return None

            from pandas import Timestamp

            splits = {}
            for row in splits_rows:
                ts = Timestamp(row["effective_date"])
                splits[ts] = row["split_factor"]

            dividends = {}
            for row in div_rows:
                ts = Timestamp(row["ex_date"])
                dividends[ts] = row["dividend_amount"]

            return {"splits": splits, "dividends": dividends}
        except Exception as e:
            logger.warning(f"Failed to load SQLite cache for {ticker}: {e}")
            return None
