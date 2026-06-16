"""Module 3: CUSIP/Ticker Change Tracker with seed data."""

import logging
import sqlite3
from datetime import date

from corp_actions.db import get_db, new_id

logger = logging.getLogger(__name__)


# Known historical identifier changes for bootstrapping.
# These are well-documented, high-confidence events.
SEED_DATA = [
    {
        "ticker": "META",
        "name": "Meta Platforms, Inc.",
        "changes": [
            {
                "id_type": "ticker",
                "old": "FB",
                "new": "META",
                "date": "2022-06-09",
                "source": "seed",
            },
            {
                "id_type": "name",
                "old": "Facebook, Inc.",
                "new": "Meta Platforms, Inc.",
                "date": "2021-10-28",
                "source": "seed",
            },
        ],
    },
    {
        "ticker": "SHEL",
        "name": "Shell plc",
        "changes": [
            {
                "id_type": "ticker",
                "old": "RDS.A",
                "new": "SHEL",
                "date": "2022-01-31",
                "source": "seed",
            },
            {
                "id_type": "name",
                "old": "Royal Dutch Shell plc",
                "new": "Shell plc",
                "date": "2022-01-31",
                "source": "seed",
            },
        ],
    },
    {
        "ticker": "DJT",
        "name": "Trump Media & Technology Group Corp.",
        "changes": [
            {
                "id_type": "ticker",
                "old": "DWAC",
                "new": "DJT",
                "date": "2024-03-26",
                "source": "seed",
            },
        ],
    },
    {
        "ticker": None,
        "name": "Twitter, Inc.",
        "is_active": False,
        "changes": [
            {
                "id_type": "ticker",
                "old": "TWTR",
                "new": None,
                "date": "2022-10-28",
                "source": "seed",
            },
        ],
    },
]


class IdentifierTracker:
    """Track historical identifier changes for securities."""

    def __init__(self, db: sqlite3.Connection):
        self.db = db

    def seed_known_changes(self) -> int:
        """Load well-known identifier changes into the database.

        Returns the number of new records inserted (skips existing).
        """
        inserted = 0
        for entry in SEED_DATA:
            # Upsert the security
            sec_id = self._ensure_security(
                ticker=entry.get("ticker"),
                name=entry["name"],
                is_active=entry.get("is_active", True),
            )

            for change in entry["changes"]:
                # Skip if this exact change already exists
                existing = self.db.execute(
                    """SELECT id FROM identifier_history
                       WHERE security_id = ? AND identifier_type = ?
                       AND old_value IS ? AND new_value IS ?
                       AND effective_date = ?""",
                    (
                        sec_id,
                        change["id_type"],
                        change["old"],
                        change["new"],
                        change["date"],
                    ),
                ).fetchone()

                if existing:
                    continue

                self.db.execute(
                    """INSERT INTO identifier_history
                       (id, security_id, identifier_type, old_value, new_value,
                        effective_date, source)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        new_id(),
                        sec_id,
                        change["id_type"],
                        change["old"],
                        change["new"],
                        change["date"],
                        change["source"],
                    ),
                )
                inserted += 1

        self.db.commit()
        logger.info(f"Seeded {inserted} identifier change(s)")
        return inserted

    def _ensure_security(
        self, ticker: str | None, name: str, is_active: bool = True
    ) -> str:
        """Find or create a security record. Returns security_id."""
        # Try by current ticker first
        if ticker:
            row = self.db.execute(
                "SELECT id FROM securities WHERE ticker = ?", (ticker,)
            ).fetchone()
            if row:
                return row[0]

        # Try by name
        row = self.db.execute(
            "SELECT id FROM securities WHERE name = ?", (name,)
        ).fetchone()
        if row:
            return row[0]

        # Try to find by old ticker in identifier_history
        if ticker:
            row = self.db.execute(
                """SELECT security_id FROM identifier_history
                   WHERE identifier_type = 'ticker' AND new_value = ?
                   ORDER BY effective_date DESC LIMIT 1""",
                (ticker,),
            ).fetchone()
            if row:
                return row[0]

        # Create new security
        sec_id = new_id()
        self.db.execute(
            """INSERT INTO securities (id, ticker, name, is_active)
               VALUES (?, ?, ?, ?)""",
            (sec_id, ticker, name, int(is_active)),
        )
        self.db.commit()
        return sec_id

    def record_change(
        self,
        security_id: str,
        id_type: str,
        old_value: str,
        new_value: str,
        effective_date: date,
        corporate_action_id: str | None = None,
        source: str = "manual",
    ) -> None:
        """Record an identifier change."""
        self.db.execute(
            """INSERT INTO identifier_history
            (id, security_id, identifier_type, old_value, new_value,
             effective_date, corporate_action_id, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                new_id(), security_id, id_type, old_value, new_value,
                effective_date.isoformat(), corporate_action_id, source,
            ),
        )

        column_map = {"ticker": "ticker", "cusip": "cusip", "isin": "isin", "name": "name"}
        if id_type in column_map:
            col = column_map[id_type]
            self.db.execute(
                f"UPDATE securities SET {col} = ?, updated_at = datetime('now') WHERE id = ?",
                (new_value, security_id),
            )

        self.db.commit()

    def resolve_historical(
        self, identifier: str, id_type: str, as_of_date: date | None = None
    ) -> str | None:
        """Resolve an identifier (current or old) to a security_id."""
        column_map = {"ticker": "ticker", "cusip": "cusip", "isin": "isin", "name": "name"}

        # Try current identifiers
        if id_type in column_map:
            col = column_map[id_type]
            row = self.db.execute(
                f"SELECT id FROM securities WHERE {col} = ?", (identifier,)
            ).fetchone()
            if row:
                return row[0]

        # Check identifier_history for old values
        if as_of_date:
            row = self.db.execute(
                """SELECT security_id FROM identifier_history
                WHERE identifier_type = ? AND old_value = ?
                AND effective_date <= ?
                ORDER BY effective_date DESC LIMIT 1""",
                (id_type, identifier, as_of_date.isoformat()),
            ).fetchone()
        else:
            row = self.db.execute(
                """SELECT security_id FROM identifier_history
                WHERE identifier_type = ? AND old_value = ?
                ORDER BY effective_date DESC LIMIT 1""",
                (id_type, identifier),
            ).fetchone()

        # Also check new_value (for when identifier was assigned)
        if not row:
            row = self.db.execute(
                """SELECT security_id FROM identifier_history
                WHERE identifier_type = ? AND new_value = ?
                ORDER BY effective_date DESC LIMIT 1""",
                (id_type, identifier),
            ).fetchone()

        return row[0] if row else None

    def get_full_history(self, security_id: str) -> list[dict]:
        """Get the complete identifier history for a security."""
        rows = self.db.execute(
            """SELECT identifier_type, old_value, new_value, effective_date, source
            FROM identifier_history
            WHERE security_id = ?
            ORDER BY effective_date ASC""",
            (security_id,),
        ).fetchall()

        return [dict(row) for row in rows]

    def get_security_info(self, security_id: str) -> dict | None:
        """Get the current security record."""
        row = self.db.execute(
            "SELECT * FROM securities WHERE id = ?", (security_id,)
        ).fetchone()
        return dict(row) if row else None

    def get_identifier_as_of(
        self, security_id: str, id_type: str, as_of_date: date
    ) -> str | None:
        """What was this security's ticker/cusip/name on a specific date?"""
        row = self.db.execute(
            """SELECT new_value FROM identifier_history
            WHERE security_id = ? AND identifier_type = ?
              AND effective_date <= ?
            ORDER BY effective_date DESC LIMIT 1""",
            (security_id, id_type, as_of_date.isoformat()),
        ).fetchone()

        if row:
            return row[0]

        column_map = {"ticker": "ticker", "cusip": "cusip", "isin": "isin", "name": "name"}
        if id_type in column_map:
            row = self.db.execute(
                f"SELECT {column_map[id_type]} FROM securities WHERE id = ?",
                (security_id,),
            ).fetchone()
            return row[0] if row else None

        return None
