"""SQLite database layer — zero cost, zero setup."""

import json
import sqlite3
from pathlib import Path
from uuid import uuid4

DB_DIR = Path.home() / ".corp-actions"
DB_PATH = DB_DIR / "corp_actions.db"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS securities (
    id TEXT PRIMARY KEY,
    ticker TEXT,
    cusip TEXT,
    isin TEXT,
    figi TEXT,
    cik TEXT,
    name TEXT NOT NULL,
    security_type TEXT DEFAULT 'Common Stock',
    exchange TEXT,
    currency TEXT DEFAULT 'USD',
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_sec_ticker ON securities(ticker);
CREATE INDEX IF NOT EXISTS idx_sec_cusip ON securities(cusip);
CREATE INDEX IF NOT EXISTS idx_sec_isin ON securities(isin);
CREATE INDEX IF NOT EXISTS idx_sec_cik ON securities(cik);

CREATE TABLE IF NOT EXISTS corporate_actions (
    id TEXT PRIMARY KEY,
    security_id TEXT REFERENCES securities(id),
    action_type TEXT NOT NULL,
    announcement_date TEXT,
    ex_date TEXT,
    record_date TEXT,
    effective_date TEXT,
    pay_date TEXT,
    split_ratio_from INTEGER,
    split_ratio_to INTEGER,
    split_factor REAL,
    dividend_amount REAL,
    dividend_currency TEXT,
    dividend_type TEXT,
    acquirer_security_id TEXT REFERENCES securities(id),
    conversion_ratio REAL,
    cash_component REAL,
    spinoff_security_id TEXT REFERENCES securities(id),
    spinoff_ratio REAL,
    parent_adjustment_factor REAL,
    old_value TEXT,
    new_value TEXT,
    source TEXT NOT NULL,
    source_url TEXT,
    source_filing_id TEXT,
    extraction_confidence REAL,
    raw_data TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    verified INTEGER DEFAULT 0,
    verified_by TEXT,
    verified_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_ca_security ON corporate_actions(security_id);
CREATE INDEX IF NOT EXISTS idx_ca_type ON corporate_actions(action_type);
CREATE INDEX IF NOT EXISTS idx_ca_effective ON corporate_actions(effective_date);
CREATE INDEX IF NOT EXISTS idx_ca_ex_date ON corporate_actions(ex_date);
CREATE INDEX IF NOT EXISTS idx_ca_source ON corporate_actions(source);

CREATE TABLE IF NOT EXISTS identifier_history (
    id TEXT PRIMARY KEY,
    security_id TEXT REFERENCES securities(id),
    identifier_type TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    effective_date TEXT,
    corporate_action_id TEXT REFERENCES corporate_actions(id),
    source TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_ih_security ON identifier_history(security_id);
CREATE INDEX IF NOT EXISTS idx_ih_old ON identifier_history(identifier_type, old_value);
CREATE INDEX IF NOT EXISTS idx_ih_new ON identifier_history(identifier_type, new_value);

CREATE TABLE IF NOT EXISTS data_fetch_log (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    ticker TEXT,
    fetch_type TEXT,
    fetched_at TEXT DEFAULT (datetime('now')),
    success INTEGER DEFAULT 1,
    error_message TEXT,
    records_found INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_fetch_ticker ON data_fetch_log(ticker, source);
CREATE INDEX IF NOT EXISTS idx_fetch_time ON data_fetch_log(fetched_at);
"""


def get_db(db_path: str | None = None) -> sqlite3.Connection:
    """Get a database connection. Creates DB and tables on first use."""
    path = Path(db_path) if db_path else DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA_SQL)

    return conn


def new_id() -> str:
    """Generate a UUID string for use as primary key."""
    return str(uuid4())


def store_json(data: dict) -> str:
    """Serialize a dict to JSON string for SQLite TEXT column."""
    return json.dumps(data, default=str)


def load_json(text: str | None) -> dict:
    """Deserialize JSON string from SQLite TEXT column."""
    if text is None:
        return {}
    return json.loads(text)


def log_fetch(
    conn: sqlite3.Connection,
    source: str,
    ticker: str,
    fetch_type: str,
    success: bool = True,
    error_message: str | None = None,
    records_found: int = 0,
) -> None:
    """Log a data fetch attempt for cache management."""
    conn.execute(
        """INSERT INTO data_fetch_log
           (id, source, ticker, fetch_type, success, error_message, records_found)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (new_id(), source, ticker, fetch_type, int(success), error_message, records_found),
    )
    conn.commit()
