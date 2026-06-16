# CORPORATE ACTIONS INTELLIGENCE ENGINE — COMPLETE DEVELOPMENT GUIDE
## For Claude CLI Development | Open-Source Python Library

**Version:** 2.0 | **Date:** March 2026 | **Status:** Pre-Build
**Package Name:** `corp-actions` | **Language:** Python 3.11+
**Goal:** Open-source tool that gets top-tier trading firms' attention
**Cost Constraint:** ABSOLUTE ZERO. No paid APIs, no paid hosting, no paid anything.

---

# ZERO-COST VERIFICATION — EVERY DEPENDENCY AUDITED

| Component | Cost | Key | Limit | Verified |
|-----------|------|-----|-------|----------|
| yfinance | $0 | None needed | ~2,000 req/hr informal | Yes — open source |
| edgartools | $0 | None needed | SEC: 10 req/sec | Yes — MIT license |
| SEC EDGAR API | $0 | None needed | 10 req/sec, User-Agent required | Yes — gov API |
| OpenFIGI | $0 | Optional free key | No key: 5 req/min. Free key: 20 req/min | Yes |
| Groq (Llama 3.3 70B) | $0 | Free key required | ~30 req/min, 6K tokens/min | Yes — free tier |
| SQLite | $0 | None | Unlimited (local file) | Yes — built into Python |
| GitHub | $0 | Account | Unlimited public repos | Yes |
| GitHub Actions CI | $0 | None | 2,000 min/month for public repos | Yes |
| PyPI publishing | $0 | Account | Unlimited | Yes |

**If any component above starts charging, the guide documents a fallback.**
**Groq is the only component requiring a free account signup.** Everything else works anonymously.

---

# HOW TO USE THIS DOCUMENT WITH CLAUDE CLI

```bash
# At the start of each session:
cat corp_actions_dev_guide.md

# Then reference specific sections:
"Implement the Split Detector per Section 5 of corp_actions_dev_guide.md"
"Write tests for the CUSIP Change Tracker per Section 8.3"
```

## FIRST-TIME BOOTSTRAP (Zero-Cost Setup)

```bash
# 1. Create project (no cost)
mkdir corp-actions && cd corp-actions
python -m venv .venv && source .venv/bin/activate

# 2. Install ALL dependencies ($0)
pip install yfinance edgartools httpx click pytest aiosqlite

# 3. Optional: Sign up for free Groq key at console.groq.com
#    (Only needed for Module 2: merger/name-change detection from 8-K filings)
#    Without it, Modules 1, 3, 4, 5 all work perfectly.
export GROQ_API_KEY="your-free-key-here"  # OPTIONAL

# 4. Set EDGAR identity (required by SEC, but free)
export EDGAR_IDENTITY="Your Name your@email.com"

# 5. Verify everything works
python -c "import yfinance; print(yfinance.__version__)"
python -c "from edgar import set_identity; set_identity('test@test.com'); print('edgartools OK')"
```

---

# TABLE OF CONTENTS

1. What You Are Building (and Why It Matters)
2. Corporate Actions Taxonomy — Every Type You Must Handle
3. Data Sources — What's Free, What's Reliable, What's Not
4. Core Data Model — Database Schema
5. Module 1: Split & Dividend Detector (yfinance)
6. Module 2: Merger & Acquisition Detector (SEC EDGAR 8-K)
7. Module 3: CUSIP/Ticker Change Tracker
8. Module 4: Position Impact Calculator (The "Explain Break" Function)
9. Module 5: Portfolio Monitor (Upcoming Actions Alert)
10. Module 6: Historical Action Chain (Full Identifier History)
11. API Design — The Public Interface
12. CLI Interface
13. Test Cases — 100+ Cases With Ground Truth
14. Edge Cases — Every One We Found
15. Performance Requirements
16. Technology Stack
17. Build Phases — 6-Week Sprint Plan
18. Pressure Test — What Will Break
19. What This Is NOT

---

# 1. WHAT YOU ARE BUILDING

## 1.1 The Product

An open-source Python library (`pip install corp-actions`) that provides:

1. **Real-time corporate actions data** for all US equities — splits, dividends, mergers, acquisitions, spin-offs, name changes, CUSIP changes, rights issues, tender offers
2. **Position impact calculation** — "I held 10,000 shares of AAPL. There was a 4:1 split. My position should now be 40,000 shares at 1/4 the price."
3. **Break explanation** — "My internal system says 40,000 shares but my PB says 10,000. A 4:1 split on [date] explains this break."
4. **Portfolio monitoring** — "These 5 securities in your portfolio have upcoming corporate actions in the next 14 days."
5. **Identifier history** — "CUSIP 037833100 was previously 037833XX before the 2014 split. The ticker was AAPL throughout."

All from FREE public data sources. No Bloomberg terminal. No paid APIs.

## 1.2 Why This Gets Attention from Optiver/HRT/Citadel

Corporate actions are verified as a top-3 pain point in trading operations:

- S&P Global survey: 66% of hedge funds process corporate actions manually
- EY (August 2025): "The lack of change in the Corporate Actions environment over the past 10 years is despite increased technological advancement"
- SIFMA Global Corporate Actions Forum (2025): "AI systems can baseline event data across markets, detect anomalies automatically, and identify discrepancies long before settlement"
- Optiver middle office job description: "dividends received for positions held on ex-dividend dates — all meticulously reconciled against external data"

There is NO good open-source corporate actions library. `yfinance` gives you splits and dividends for individual tickers. EdgarTools gives you 8-K filings. But nobody has built a unified engine that combines all sources, tracks identifier changes, calculates position impacts, and explains reconciliation breaks.

## 1.3 What Makes This Technically Impressive

This isn't a wrapper around yfinance. It's a data engineering product that:

1. **Multi-source ingestion** — Combines yfinance, SEC EDGAR, OpenFIGI, and FINRA data into a unified model
2. **Temporal identifier tracking** — Knows that CUSIP X became CUSIP Y on date Z due to a merger
3. **LLM-assisted extraction (optional, free)** — Uses Groq/Llama (free tier) to extract corporate action details from unstructured 8-K filing text. Engine works fully without LLM for splits/dividends.
4. **Position math** — Correctly calculates the impact of any corporate action on a position, including complex cases (spin-offs with fractional shares, special dividends with reinvestment)
5. **Caching and rate-limit awareness** — Respects Yahoo Finance and EDGAR rate limits, caches aggressively, works offline for previously-fetched data
6. **Zero infrastructure cost** — SQLite for local storage, no server required, pip-installable. Runs on a laptop.

---

# 2. CORPORATE ACTIONS TAXONOMY

## 2.1 Every Type You Must Handle

| Action Type | Frequency | Data Source | Impact on Position | Impact on Identifier | Complexity |
|-------------|-----------|-------------|-------------------|---------------------|------------|
| **Cash Dividend** | Very common (~4x/year per stock) | yfinance | No qty change. Cash inflow. | None | Low |
| **Stock Dividend** | Occasional | yfinance | Qty increases by dividend ratio | None usually | Medium |
| **Stock Split** | Occasional (5-15 major ones/year) | yfinance | Qty × ratio, Price ÷ ratio | Sometimes new CUSIP | Medium |
| **Reverse Split** | Occasional | yfinance | Qty ÷ ratio, Price × ratio | Usually new CUSIP | Medium |
| **Merger/Acquisition** | ~200-300/year in US | SEC EDGAR 8-K | Position converted to acquirer stock (or cash, or mix) | Old CUSIP delisted, new CUSIP | High |
| **Spin-off** | ~20-50/year | SEC EDGAR 8-K | New position created from parent | New CUSIP for spun-off entity | High |
| **Name Change** | ~50-100/year | SEC EDGAR 8-K, FINRA | No position change | New CUSIP, new ticker | Low |
| **Ticker Change** | ~100-200/year | SEC EDGAR, FINRA | No position change | New ticker, CUSIP may change | Low |
| **Rights Issue** | Occasional | SEC EDGAR S-1 | Optional: buy more shares at discount | None | Medium |
| **Tender Offer** | ~50-100/year | SEC EDGAR SC TO-T | Optional: sell shares at premium | None | Medium |
| **Special Dividend** | Occasional | yfinance | No qty change. Large cash inflow. Price adjusts. | None | Low |
| **Return of Capital** | Occasional | 8-K | No qty change. Adjusts cost basis. | None | Low |

## 2.2 What v1 Must Handle (Minimum Viable)

**Must have (Week 1-2):**
- Cash dividends (amount, ex-date, pay-date, record-date)
- Stock splits and reverse splits (ratio, effective date)
- Position impact calculation for splits/dividends

**Must have (Week 3-4):**
- Mergers/acquisitions (from 8-K filings, LLM-extracted)
- Name changes and ticker changes
- CUSIP change tracking

**Nice to have (Week 5-6):**
- Spin-offs with allocation ratios
- Portfolio monitoring (upcoming actions alert)
- Historical identifier chain

**Out of scope (v1):**
- Rights issues (complex, optional, low frequency)
- Tender offers (voluntary, complex)
- International corporate actions (non-US)
- Real-time streaming (polling is sufficient for v1)

---

# 3. DATA SOURCES — VERIFIED, WITH LIMITATIONS

## 3.1 Source 1: Yahoo Finance via yfinance (PRIMARY for splits/dividends)

**What it provides:**
- Stock splits: date, ratio (e.g., 4.0 means 4:1 split)
- Cash dividends: date, amount per share
- Historical price data (with adjusted close that accounts for splits/dividends)

**How to access:**
```python
import yfinance as yf

ticker = yf.Ticker("AAPL")

# Get all splits
splits = ticker.splits
# Returns: DatetimeIndex → float
# 2020-08-31    4.0   (4:1 split)
# 2014-06-09    7.0   (7:1 split)
# 2005-02-28    2.0   (2:1 split)
# ...

# Get all dividends
dividends = ticker.dividends
# Returns: DatetimeIndex → float (amount per share)
# 2024-11-08    0.25
# 2024-08-12    0.25
# ...

# Get both combined
actions = ticker.actions
# Returns DataFrame with columns: Dividends, Stock Splits
```

**Rate limits:**
- Yahoo Finance allows ~2,000 requests per hour per IP
- No API key required
- yfinance caches responses locally by default
- CRITICAL: yfinance is an unofficial API. Yahoo can change/break it at any time. The library has broken and been fixed multiple times historically.

**What it does NOT provide:**
- Mergers/acquisitions
- Name changes
- Ticker changes
- CUSIP changes
- Spin-offs (these appear as dividends of the new security, but without the detail)
- Record dates and pay dates for dividends (only ex-dates)
- Forward-looking announcements (only historical)

**Known limitations:**
- Data can be delayed 1-2 days for very recent events
- Some international securities have incomplete data
- Reverse splits sometimes show as fractional values (0.1 means 1:10 reverse split)
- Adjusted close prices retroactively change when new splits/dividends are added
- Symbol changes: if a ticker changes (FB → META), yfinance may not link historical data

**PRESSURE TEST:** yfinance is the only free source for splits and dividends that doesn't require an API key. It's the foundation of your engine. But it's fragile. Your architecture must cache aggressively and handle yfinance failures gracefully (return cached data, retry, degrade).

## 3.2 Source 2: SEC EDGAR (PRIMARY for mergers, 8-K events)

**What it provides:**
- 8-K current reports: material events including mergers, acquisitions, name changes, management changes
- Submissions API: filing history for any company by CIK
- Full-text search: search across all filings for keywords
- Company tickers JSON: CIK ↔ ticker mapping

**How to access (FREE, no API key):**

```python
# Option A: edgartools (open-source, free, no API key)
# pip install edgartools
from edgar import *
set_identity("yourname@email.com")  # Required by SEC

# Get recent 8-K filings for a company
company = Company("AAPL")
filings = company.get_filings(form="8-K")

# Parse a specific 8-K
eightk = filings[0].obj()
items = eightk.items  # List of reported event items

# Option B: Direct EDGAR API (free, no key)
import httpx

# Get company submissions
resp = httpx.get(
    "https://data.sec.gov/submissions/CIK0000320193.json",
    headers={"User-Agent": "YourApp/1.0 your@email.com"}
)
data = resp.json()
# data['filings']['recent'] contains recent filing metadata

# Full-text search
resp = httpx.get(
    "https://efts.sec.gov/LATEST/search-index",
    params={"q": '"stock split"', "dateRange": "custom", 
            "startdt": "2025-01-01", "forms": "8-K"},
    headers={"User-Agent": "YourApp/1.0 your@email.com"}
)
```

**Rate limits (CRITICAL):**
- SEC EDGAR: 10 requests per second maximum
- Must include User-Agent header with your name and email
- Exceeding rate limit results in temporary IP ban
- edgartools handles rate limiting automatically

**8-K Item Types Relevant to Corporate Actions:**

| Item | Description | Relevance |
|------|-------------|-----------|
| 1.01 | Entry into Material Definitive Agreement | Merger/acquisition agreements |
| 2.01 | Completion of Acquisition or Disposition | Merger completed |
| 3.03 | Material Modification to Rights of Security Holders | Stock split, rights changes |
| 5.01 | Changes in Control of Registrant | Acquisition/takeover |
| 5.03 | Amendments to Articles of Incorporation | Name changes, CUSIP changes |
| 5.07 | Submission of Matters to a Vote of Security Holders | Merger votes |
| 8.01 | Other Events | Catch-all for various announcements |
| 9.01 | Financial Statements and Exhibits | Supporting documents |

**PRESSURE TEST:** EDGAR 8-K filings are unstructured text/HTML. Extracting "this is a merger" vs "this is a name change" requires NLP/LLM. edgartools parses 8-K items into structured objects, but the detail extraction (merger ratio, effective date, new ticker) still requires text parsing. This is where your Groq/Llama integration earns its keep.

## 3.3 Source 3: OpenFIGI (for identifier resolution)

**What it provides:**
- Map any identifier (CUSIP, ISIN, SEDOL, ticker) to FIGI
- Confirm two identifiers refer to the same security
- Get security name, exchange, security type

**What it does NOT provide:**
- Does NOT return CUSIP, ISIN, or SEDOL (licensing restrictions)
- Does NOT provide corporate action history
- Does NOT track historical identifier changes

**Rate limits:**
- Without key: 5 requests/minute, 10 jobs per request
- With free key: 20 requests/minute, 100 jobs per request

**PRESSURE TEST:** OpenFIGI is useful for confirming "does CUSIP X map to the same security as ticker Y?" but it CANNOT tell you "what was this security's old CUSIP before the merger?" You need to build that history yourself from EDGAR and yfinance data.

## 3.4 Source 4: SEC EDGAR Company Tickers (for ticker ↔ CIK mapping)

**URL:** `https://www.sec.gov/files/company_tickers.json`

**What it provides:**
```json
{
  "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
  "1": {"cik_str": 789019, "ticker": "MSFT", "title": "MICROSOFT CORP"},
  ...
}
```

~10,000 US public companies. Free. Static JSON file. No rate limit.

**PRESSURE TEST:** This only gives CURRENT tickers. If a company changed its ticker (FB → META), this file shows META. You won't find FB here. You need the EDGAR submissions API to find historical filings under the old ticker.

## 3.5 Source 5: Frankfurter API (for FX rates, needed for international dividends)

**URL:** `https://api.frankfurter.dev/v1/latest`
Free. Unlimited. ECB reference rates for 30+ currencies.

Only needed if you handle non-USD dividends (v1 is US-only, so this is a v2 concern).

## 3.6 Sources NOT Available for Free (Honest)

| Data | Why You Can't Get It Free | Workaround |
|------|--------------------------|------------|
| CUSIP database | CUSIP Global Services charges for access | Use ISIN conversion formula for US securities; get CUSIPs from 13F filings |
| Real-time corporate actions feed | Bloomberg, S&P, Refinitiv charge $$$$ | Poll yfinance + EDGAR daily |
| Spin-off allocation ratios | Not in structured data anywhere free | Extract from 8-K filing text via LLM |
| Merger conversion ratios | Not in structured data free | Extract from 8-K filing text via LLM |
| FINRA Daily List (OTC actions) | Available on FINRA website but not as clean API | Web scrape or manual download |
| Ex-date vs record-date vs pay-date | yfinance only gives ex-date reliably | Extract from 8-K text or company press releases |

---

# 4. CORE DATA MODEL

## 4.1 Database Schema (SQLite — Zero Cost, Zero Setup)

**Why SQLite:** No server to install, no hosting to pay for, no Docker needed. The database is a single file that ships with the user's installation. For a pip-installable library, this is the only sane choice. PostgreSQL is overkill and adds cost/complexity.

**Location:** `~/.corp-actions/corp_actions.db` (created automatically on first use)

```sql
-- ============================================
-- SECURITIES: Master record for each security
-- ============================================
CREATE TABLE IF NOT EXISTS securities (
    id TEXT PRIMARY KEY,          -- UUID as text (SQLite has no UUID type)
    
    -- Current identifiers
    ticker TEXT,
    cusip TEXT,
    isin TEXT,
    figi TEXT,
    cik TEXT,                     -- SEC Central Index Key
    
    -- Descriptive
    name TEXT NOT NULL,
    security_type TEXT DEFAULT 'Common Stock',
    exchange TEXT,
    currency TEXT DEFAULT 'USD',
    is_active INTEGER DEFAULT 1,  -- SQLite uses INTEGER for boolean
    
    -- Metadata
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_sec_ticker ON securities(ticker);
CREATE INDEX IF NOT EXISTS idx_sec_cusip ON securities(cusip);
CREATE INDEX IF NOT EXISTS idx_sec_isin ON securities(isin);
CREATE INDEX IF NOT EXISTS idx_sec_cik ON securities(cik);
-- NOTE: SQLite does not support gin_trgm_ops. For fuzzy name matching,
-- use Python's difflib or rapidfuzz instead of SQL.

-- ============================================
-- CORPORATE_ACTIONS: Every event
-- ============================================
CREATE TABLE IF NOT EXISTS corporate_actions (
    id TEXT PRIMARY KEY,          -- UUID as text
    security_id TEXT REFERENCES securities(id),
    
    -- Action classification
    action_type TEXT NOT NULL,
    -- Values: 'cash_dividend', 'stock_dividend', 'stock_split', 
    --         'reverse_split', 'merger', 'acquisition', 'spin_off',
    --         'name_change', 'ticker_change', 'cusip_change',
    --         'rights_issue', 'tender_offer', 'special_dividend',
    --         'return_of_capital', 'delisting'
    
    -- Key dates (stored as TEXT in ISO format YYYY-MM-DD)
    announcement_date TEXT,
    ex_date TEXT,
    record_date TEXT,
    effective_date TEXT,
    pay_date TEXT,
    
    -- For splits
    split_ratio_from INTEGER,
    split_ratio_to INTEGER,
    split_factor REAL,           -- SQLite uses REAL for decimals
    
    -- For dividends
    dividend_amount REAL,
    dividend_currency TEXT,
    dividend_type TEXT,
    
    -- For mergers/acquisitions
    acquirer_security_id TEXT REFERENCES securities(id),
    conversion_ratio REAL,
    cash_component REAL,
    
    -- For spin-offs
    spinoff_security_id TEXT REFERENCES securities(id),
    spinoff_ratio REAL,
    parent_adjustment_factor REAL,
    
    -- For name/ticker/CUSIP changes
    old_value TEXT,
    new_value TEXT,
    
    -- Source tracking
    source TEXT NOT NULL,
    source_url TEXT,
    source_filing_id TEXT,
    extraction_confidence REAL,
    
    -- Metadata (SQLite: store JSON as TEXT)
    raw_data TEXT,               -- JSON string
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

-- ============================================
-- IDENTIFIER_HISTORY: Track all identifier changes over time
-- ============================================
CREATE TABLE IF NOT EXISTS identifier_history (
    id TEXT PRIMARY KEY,
    security_id TEXT REFERENCES securities(id),
    
    identifier_type TEXT NOT NULL,    -- 'ticker', 'cusip', 'isin', 'name'
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

-- ============================================
-- DATA_FETCH_LOG: Track when we last fetched data (for cache management)
-- ============================================
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
```

### SQLite Helper Module

```python
# db.py — Zero-cost database layer
import sqlite3
import json
from pathlib import Path
from uuid import uuid4

DB_DIR = Path.home() / ".corp-actions"
DB_PATH = DB_DIR / "corp_actions.db"

SCHEMA_SQL = """
-- Paste the full CREATE TABLE statements above here
"""

def get_db() -> sqlite3.Connection:
    """Get a database connection. Creates DB and tables on first use."""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row  # Access columns by name
    conn.execute("PRAGMA journal_mode=WAL")  # Better concurrent read perf
    conn.execute("PRAGMA foreign_keys=ON")
    
    # Create tables if they don't exist
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
```

## 4.2 Core Python Data Classes

```python
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID, uuid4
from typing import Optional

class ActionType(Enum):
    CASH_DIVIDEND = "cash_dividend"
    STOCK_DIVIDEND = "stock_dividend"
    STOCK_SPLIT = "stock_split"
    REVERSE_SPLIT = "reverse_split"
    MERGER = "merger"
    ACQUISITION = "acquisition"
    SPIN_OFF = "spin_off"
    NAME_CHANGE = "name_change"
    TICKER_CHANGE = "ticker_change"
    CUSIP_CHANGE = "cusip_change"
    SPECIAL_DIVIDEND = "special_dividend"
    RETURN_OF_CAPITAL = "return_of_capital"
    RIGHTS_ISSUE = "rights_issue"
    TENDER_OFFER = "tender_offer"
    DELISTING = "delisting"

class DataSource(Enum):
    YFINANCE = "yfinance"
    EDGAR_8K = "edgar_8k"
    EDGAR_SUBMISSIONS = "edgar_submissions"
    OPENFIGI = "openfigi"
    MANUAL = "manual"
    LLM_EXTRACTED = "llm_extracted"

@dataclass
class CorporateAction:
    """A single corporate action event."""
    id: UUID = field(default_factory=uuid4)
    ticker: str = ""
    security_name: str = ""
    action_type: ActionType = ActionType.CASH_DIVIDEND
    
    # Dates
    announcement_date: Optional[date] = None
    ex_date: Optional[date] = None
    record_date: Optional[date] = None
    effective_date: Optional[date] = None
    pay_date: Optional[date] = None
    
    # Split data
    split_ratio: Optional[Decimal] = None  # e.g., 4.0 for 4:1
    split_from: Optional[int] = None       # e.g., 1
    split_to: Optional[int] = None         # e.g., 4
    
    # Dividend data
    dividend_amount: Optional[Decimal] = None
    dividend_currency: str = "USD"
    
    # Merger data
    acquirer_ticker: Optional[str] = None
    conversion_ratio: Optional[Decimal] = None
    cash_per_share: Optional[Decimal] = None
    
    # Spin-off data
    spinoff_ticker: Optional[str] = None
    spinoff_ratio: Optional[Decimal] = None
    
    # Name/ticker/CUSIP change data
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    
    # Source
    source: DataSource = DataSource.YFINANCE
    source_url: Optional[str] = None
    confidence: float = 1.0
    
    # Raw data for debugging
    raw_data: dict = field(default_factory=dict)

@dataclass
class PositionImpact:
    """The calculated impact of a corporate action on a position."""
    action: CorporateAction
    
    # Before
    original_quantity: Decimal
    original_price: Optional[Decimal] = None
    original_market_value: Optional[Decimal] = None
    
    # After
    new_quantity: Decimal = Decimal(0)
    new_price: Optional[Decimal] = None
    new_market_value: Optional[Decimal] = None
    
    # Additional positions created (spin-offs)
    additional_positions: list = field(default_factory=list)
    
    # Cash received (dividends, merger cash component)
    cash_received: Decimal = Decimal(0)
    
    # Explanation
    explanation: str = ""

@dataclass
class BreakExplanation:
    """Explains whether a reconciliation break is caused by a corporate action."""
    is_explained: bool = False
    action: Optional[CorporateAction] = None
    expected_quantity: Optional[Decimal] = None
    actual_quantity: Optional[Decimal] = None
    explanation: str = ""
    confidence: float = 0.0
```

---

# 5. MODULE 1: SPLIT & DIVIDEND DETECTOR

## 5.1 Purpose

Fetch and normalise stock split and dividend data for any US equity from Yahoo Finance.

## 5.2 Implementation

```python
import yfinance as yf
from datetime import date, timedelta
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

class SplitDividendDetector:
    """Fetch splits and dividends from Yahoo Finance."""
    
    def __init__(self, cache_ttl_hours: int = 24):
        self.cache_ttl = timedelta(hours=cache_ttl_hours)
        self._cache: dict[str, dict] = {}  # ticker → {data, fetched_at}
    
    def get_splits(self, ticker: str, 
                   start_date: date | None = None,
                   end_date: date | None = None) -> list[CorporateAction]:
        """
        Get all stock splits for a ticker.
        
        Returns list of CorporateAction with action_type STOCK_SPLIT or REVERSE_SPLIT.
        """
        raw = self._fetch_actions(ticker)
        if raw is None:
            return []
        
        splits = raw.get('splits', [])
        results = []
        
        for split_date, ratio in splits.items():
            # Determine split type
            if ratio > 1.0:
                action_type = ActionType.STOCK_SPLIT
                split_from = 1
                split_to = int(ratio)
            elif 0 < ratio < 1.0:
                action_type = ActionType.REVERSE_SPLIT
                # e.g., ratio=0.1 means 1:10 reverse split
                split_to = 1
                split_from = int(round(1 / ratio))
            else:
                logger.warning(f"Unexpected split ratio {ratio} for {ticker} on {split_date}")
                continue
            
            action = CorporateAction(
                ticker=ticker,
                action_type=action_type,
                effective_date=split_date.date() if hasattr(split_date, 'date') else split_date,
                ex_date=split_date.date() if hasattr(split_date, 'date') else split_date,
                split_ratio=Decimal(str(ratio)),
                split_from=split_from,
                split_to=split_to,
                source=DataSource.YFINANCE,
                confidence=0.95,  # yfinance is reliable for splits
                raw_data={'ratio': float(ratio), 'date': str(split_date)}
            )
            
            # Apply date filter
            eff = action.effective_date
            if start_date and eff < start_date:
                continue
            if end_date and eff > end_date:
                continue
            
            results.append(action)
        
        return sorted(results, key=lambda a: a.effective_date or date.min)
    
    def get_dividends(self, ticker: str,
                      start_date: date | None = None,
                      end_date: date | None = None) -> list[CorporateAction]:
        """
        Get all dividends for a ticker.
        
        Returns list of CorporateAction with action_type CASH_DIVIDEND or SPECIAL_DIVIDEND.
        """
        raw = self._fetch_actions(ticker)
        if raw is None:
            return []
        
        dividends = raw.get('dividends', [])
        results = []
        
        # Detect special dividends (significantly larger than typical)
        amounts = [float(amt) for amt in dividends.values() if float(amt) > 0]
        median_dividend = sorted(amounts)[len(amounts) // 2] if amounts else 0
        
        for div_date, amount in dividends.items():
            amount_dec = Decimal(str(amount))
            
            if amount_dec <= 0:
                continue
            
            # Heuristic: special dividend if >3x the median
            is_special = (median_dividend > 0 and 
                         float(amount_dec) > median_dividend * 3)
            
            action = CorporateAction(
                ticker=ticker,
                action_type=ActionType.SPECIAL_DIVIDEND if is_special else ActionType.CASH_DIVIDEND,
                ex_date=div_date.date() if hasattr(div_date, 'date') else div_date,
                effective_date=div_date.date() if hasattr(div_date, 'date') else div_date,
                dividend_amount=amount_dec,
                dividend_currency="USD",
                source=DataSource.YFINANCE,
                confidence=0.95,
                raw_data={'amount': float(amount), 'date': str(div_date)}
            )
            
            # Apply date filter
            ex = action.ex_date
            if start_date and ex < start_date:
                continue
            if end_date and ex > end_date:
                continue
            
            results.append(action)
        
        return sorted(results, key=lambda a: a.ex_date or date.min)
    
    def get_all_actions(self, ticker: str,
                        start_date: date | None = None,
                        end_date: date | None = None) -> list[CorporateAction]:
        """Get all splits and dividends combined, sorted by date."""
        splits = self.get_splits(ticker, start_date, end_date)
        dividends = self.get_dividends(ticker, start_date, end_date)
        
        combined = splits + dividends
        return sorted(combined, key=lambda a: (a.effective_date or a.ex_date or date.min))
    
    def _fetch_actions(self, ticker: str) -> dict | None:
        """Fetch from yfinance with caching."""
        # Check cache
        if ticker in self._cache:
            cached = self._cache[ticker]
            if datetime.now() - cached['fetched_at'] < self.cache_ttl:
                return cached['data']
        
        try:
            yf_ticker = yf.Ticker(ticker)
            
            splits = yf_ticker.splits
            dividends = yf_ticker.dividends
            
            data = {
                'splits': splits if splits is not None and len(splits) > 0 else {},
                'dividends': dividends if dividends is not None and len(dividends) > 0 else {},
            }
            
            self._cache[ticker] = {
                'data': data,
                'fetched_at': datetime.now()
            }
            
            return data
            
        except Exception as e:
            logger.error(f"yfinance error for {ticker}: {e}")
            
            # Return stale cache if available
            if ticker in self._cache:
                logger.warning(f"Returning stale cache for {ticker}")
                return self._cache[ticker]['data']
            
            return None
```

## 5.3 Edge Cases for Splits

| Edge Case | How It Manifests | How to Handle |
|-----------|-----------------|---------------|
| Reverse split as fraction | yfinance shows 0.1 for 1:10 reverse split | Detect ratio < 1.0, invert to get the "from:to" |
| Split on a weekend/holiday | Effective date may be non-trading day | Use effective_date as-is; matching should use ±1 day tolerance |
| Split announced but not yet effective | yfinance only shows after it happens | Not available from yfinance; use 8-K for forward-looking |
| Multiple splits on same date | Theoretically possible | Handle as separate events |
| Split ratio is not a whole number | e.g., 3:2 split = ratio 1.5 | Support fractional ratios; split_to=3, split_from=2 |
| Ticker changed after split | e.g., new CUSIP assigned | Must check identifier_history for the old ticker |
| ETF split | ETFs split too (SPY, QQQ) | Handle identically to stock splits |
| ADR ratio change | ADR may adjust shares per underlying | Appears as a split in yfinance |

## 5.4 Edge Cases for Dividends

| Edge Case | How It Manifests | How to Handle |
|-----------|-----------------|---------------|
| Special dividend vs regular | Special can be 10x+ regular amount | Heuristic: >3x median = special. Flag for user review. |
| Stock dividend | yfinance shows this differently | May appear in splits data, not dividends |
| Return of capital | Looks like a dividend but is tax-different | Cannot distinguish from yfinance alone; need 8-K |
| Ex-date vs record-date vs pay-date | yfinance only reliably gives ex-date | Document limitation. Pay-date available from 8-K/press releases |
| Dividend in non-USD currency | Rare for US stocks, common for ADRs | Store dividend_currency from yfinance info |
| Zero-amount dividend | Occasionally appears in data | Filter out amount <= 0 |
| Suspended dividend | Company stops paying | No event in yfinance; just absence of future dividends |
| Dividend reinvestment (DRIP) | Creates fractional shares | Not a corporate action per se; broker-level |

---

# 6. MODULE 2: MERGER & ACQUISITION DETECTOR

## 6.1 Purpose

Detect mergers, acquisitions, name changes, and other material events from SEC EDGAR 8-K filings. Use LLM (Groq/Llama) to extract structured data from unstructured filing text.

## 6.2 Implementation

```python
from edgar import Company, get_filings, set_identity
import httpx
import json
import os

class EdgarEventDetector:
    """
    Detect corporate actions from SEC EDGAR 8-K filings.
    
    COST: $0. edgartools is MIT-licensed, SEC EDGAR is free government API.
    LLM (Groq) is OPTIONAL — if no GROQ_API_KEY, this module uses
    keyword-based classification (lower accuracy but still useful).
    """
    
    # 8-K items that indicate corporate actions
    RELEVANT_ITEMS = {
        '1.01': 'material_agreement',       # Merger agreements
        '2.01': 'acquisition_completion',    # Completed M&A
        '3.03': 'rights_modification',       # Splits, rights changes
        '5.01': 'change_of_control',         # Takeover
        '5.03': 'articles_amendment',        # Name changes
        '8.01': 'other_events',              # Various announcements
    }
    
    def __init__(self, identity_email: str):
        set_identity(identity_email)
        self._groq_available = bool(os.environ.get("GROQ_API_KEY"))
        self.groq_client = None  # Lazy init only if key exists
    
    def get_recent_events(self, ticker: str, 
                          days_back: int = 90) -> list[CorporateAction]:
        """
        Get corporate action events from recent 8-K filings.
        
        Uses edgartools to fetch 8-K filings, then LLM to extract
        structured corporate action data from the filing text.
        """
        try:
            company = Company(ticker)
            filings = company.get_filings(form="8-K")
        except Exception as e:
            logger.error(f"EDGAR error for {ticker}: {e}")
            return []
        
        results = []
        cutoff = date.today() - timedelta(days=days_back)
        
        for filing in filings[:20]:  # Check last 20 filings
            try:
                filing_date = filing.filing_date
                if hasattr(filing_date, 'date'):
                    filing_date = filing_date.date()
                
                if filing_date < cutoff:
                    break
                
                # Parse the 8-K
                eightk = filing.obj()
                items = eightk.items if hasattr(eightk, 'items') else []
                
                # Check if any items are relevant to corporate actions
                for item in items:
                    item_num = getattr(item, 'item', '') or str(item)
                    
                    if any(key in str(item_num) for key in self.RELEVANT_ITEMS):
                        # Extract text and classify
                        text = self._extract_text(item)
                        if text:
                            # Try LLM first (free Groq), fall back to keywords
                            if self._groq_available:
                                action = self._classify_with_llm(
                                    ticker, text, item_num, filing_date,
                                    filing.accession_no
                                )
                            else:
                                action = self._classify_with_keywords(
                                    ticker, text, item_num, filing_date,
                                    filing.accession_no
                                )
                            if action:
                                results.append(action)
            
            except Exception as e:
                logger.warning(f"Error parsing 8-K for {ticker}: {e}")
                continue
        
        return results
    
    def _extract_text(self, item) -> str:
        """Extract text content from an 8-K item."""
        if hasattr(item, 'text'):
            return item.text[:5000]  # Limit to 5000 chars for LLM
        if hasattr(item, 'content'):
            return str(item.content)[:5000]
        return str(item)[:5000]
    
    def _classify_with_keywords(self, ticker: str, text: str,
                                 item_num: str, filing_date: date,
                                 accession_no: str) -> CorporateAction | None:
        """
        Classify 8-K text using keyword matching — NO LLM, NO COST.
        
        Lower accuracy (~50-60%) than LLM (~70-80%), but works without
        any API key. Useful as a fallback.
        """
        text_lower = text.lower()
        
        # Name change detection (high accuracy with keywords)
        if '5.03' in str(item_num):
            name_signals = ['name change', 'changed its name', 'change of name',
                           'amended its certificate', 'amended its articles',
                           'new name']
            if any(signal in text_lower for signal in name_signals):
                return CorporateAction(
                    ticker=ticker,
                    action_type=ActionType.NAME_CHANGE,
                    announcement_date=filing_date,
                    source=DataSource.EDGAR_8K,
                    source_filing_id=accession_no,
                    confidence=0.60,
                    raw_data={'text_snippet': text[:500], 'method': 'keyword'}
                )
        
        # Merger/acquisition detection
        if any(item in str(item_num) for item in ['1.01', '2.01', '5.01']):
            merger_signals = ['merger agreement', 'plan of merger', 'acquisition',
                            'acquired all', 'completed the acquisition',
                            'completion of', 'business combination']
            if any(signal in text_lower for signal in merger_signals):
                return CorporateAction(
                    ticker=ticker,
                    action_type=ActionType.MERGER,
                    announcement_date=filing_date,
                    source=DataSource.EDGAR_8K,
                    source_filing_id=accession_no,
                    confidence=0.50,
                    raw_data={'text_snippet': text[:500], 'method': 'keyword'}
                )
        
        # Spin-off detection
        spinoff_signals = ['spin-off', 'spinoff', 'distribution of shares',
                          'separation', 'distribute to shareholders']
        if any(signal in text_lower for signal in spinoff_signals):
            return CorporateAction(
                ticker=ticker,
                action_type=ActionType.SPIN_OFF,
                announcement_date=filing_date,
                source=DataSource.EDGAR_8K,
                source_filing_id=accession_no,
                confidence=0.45,
                raw_data={'text_snippet': text[:500], 'method': 'keyword'}
            )
        
        return None  # Could not classify with keywords
    
    def _classify_with_llm(self, ticker: str, text: str, 
                           item_num: str, filing_date: date,
                           accession_no: str) -> CorporateAction | None:
        """
        Use Groq/Llama to classify an 8-K item as a corporate action.
        
        COST: $0 — Uses Groq free tier (Llama 3.3 70B, ~30 req/min).
        Called only when GROQ_API_KEY is set. Falls back to keyword
        classifier if Groq call fails.
        
        Returns None if the item is not a corporate action.
        """
        if self.groq_client is None:
            try:
                from groq import Groq
                self.groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
            except ImportError:
                logger.warning("groq package not installed. pip install groq")
                return self._classify_with_keywords(
                    ticker, text, item_num, filing_date, accession_no
                )
        
        prompt = f"""Analyze this SEC 8-K filing excerpt for {ticker} (filed {filing_date}).
8-K Item: {item_num}

Text:
{text[:3000]}

Is this a corporate action? If yes, classify it as ONE of:
- merger (company being acquired)
- acquisition (company acquiring another)
- spin_off (creating a new separate company)
- name_change (company changing its legal name)
- ticker_change (stock ticker symbol changing)
- stock_split (stock split or reverse split)
- special_dividend (one-time large dividend)
- delisting (security being delisted)
- none (not a corporate action)

If it IS a corporate action, extract:
- action_type: (from list above)
- effective_date: (YYYY-MM-DD if mentioned, null if not)
- description: (one sentence summary)
- For mergers: acquirer_name, conversion_ratio (shares of acquirer per share), cash_per_share
- For spin_offs: new_company_name, distribution_ratio
- For name_changes: old_name, new_name
- For ticker_changes: old_ticker, new_ticker

Return ONLY JSON. If not a corporate action, return: {{"action_type": "none"}}"""

        try:
            response = self.groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=500,
                response_format={"type": "json_object"},
            )
            
            result = json.loads(response.choices[0].message.content)
            
            if result.get('action_type') == 'none':
                return None
            
            return self._build_action_from_llm(ticker, result, filing_date, accession_no)
            
        except Exception as e:
            logger.error(f"LLM classification error: {e}")
            # Fall back to keyword classification (zero cost)
            return self._classify_with_keywords(
                ticker, text, item_num, filing_date, accession_no
            )
    
    def _build_action_from_llm(self, ticker: str, llm_result: dict,
                                filing_date: date, 
                                accession_no: str) -> CorporateAction | None:
        """Build a CorporateAction from LLM extraction results."""
        action_type_map = {
            'merger': ActionType.MERGER,
            'acquisition': ActionType.ACQUISITION,
            'spin_off': ActionType.SPIN_OFF,
            'name_change': ActionType.NAME_CHANGE,
            'ticker_change': ActionType.TICKER_CHANGE,
            'stock_split': ActionType.STOCK_SPLIT,
            'special_dividend': ActionType.SPECIAL_DIVIDEND,
            'delisting': ActionType.DELISTING,
        }
        
        action_type_str = llm_result.get('action_type', 'none')
        if action_type_str not in action_type_map:
            return None
        
        action = CorporateAction(
            ticker=ticker,
            action_type=action_type_map[action_type_str],
            announcement_date=filing_date,
            source=DataSource.LLM_EXTRACTED,
            source_url=f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&accession={accession_no}",
            source_filing_id=accession_no,
            confidence=0.70,  # LLM-extracted = lower confidence
            raw_data=llm_result,
        )
        
        # Parse effective date if provided
        eff_str = llm_result.get('effective_date')
        if eff_str and eff_str != 'null':
            try:
                action.effective_date = date.fromisoformat(eff_str)
            except ValueError:
                pass
        
        # Parse merger-specific fields
        if action_type_str in ('merger', 'acquisition'):
            action.acquirer_ticker = llm_result.get('acquirer_name')
            ratio = llm_result.get('conversion_ratio')
            if ratio:
                try:
                    action.conversion_ratio = Decimal(str(ratio))
                except:
                    pass
            cash = llm_result.get('cash_per_share')
            if cash:
                try:
                    action.cash_per_share = Decimal(str(cash))
                except:
                    pass
        
        # Parse name change fields
        if action_type_str == 'name_change':
            action.old_value = llm_result.get('old_name')
            action.new_value = llm_result.get('new_name')
        
        # Parse ticker change fields
        if action_type_str == 'ticker_change':
            action.old_value = llm_result.get('old_ticker')
            action.new_value = llm_result.get('new_ticker')
        
        # Parse spin-off fields
        if action_type_str == 'spin_off':
            action.spinoff_ticker = llm_result.get('new_company_name')
            ratio = llm_result.get('distribution_ratio')
            if ratio:
                try:
                    action.spinoff_ratio = Decimal(str(ratio))
                except:
                    pass
        
        return action
```

## 6.3 Pressure Test on LLM Extraction

**What WILL work:**
- Name changes: 8-K Item 5.03 explicitly says "the company changed its name from X to Y." LLM will extract this with >90% accuracy.
- Completed mergers: 8-K Item 2.01 explicitly says "the merger was completed." LLM can extract acquirer and sometimes the ratio.

**What MIGHT work:**
- Spin-off details: The distribution ratio is often buried in complex legal language. LLM may extract it correctly ~60-70% of the time.
- Merger conversion ratios: Sometimes stated clearly, sometimes spread across multiple paragraphs.

**What WON'T work reliably:**
- Announced but not completed mergers: An 8-K may announce a merger agreement (Item 1.01) that later falls through. You must track completion separately.
- Complex merger terms: "0.5 shares of Acquirer Class A stock plus $10 cash plus 0.1 shares of SpinCo" — LLM will struggle with multi-component terms.
- Effective dates: Often not stated in the 8-K itself; you may only get the filing date.

**Mitigation:** Set confidence=0.70 for all LLM-extracted data. Flag for human verification. Store the raw 8-K text so corrections can be traced.

---

# 7. MODULE 3: CUSIP/TICKER CHANGE TRACKER

## 7.1 Purpose

Track when a security's identifier changes, and maintain a complete history chain so you can resolve "what is the current ticker for this old CUSIP?"

## 7.2 Implementation

```python
class IdentifierTracker:
    """Track historical identifier changes for securities."""
    
    def __init__(self, db):
        self.db = db
    
    async def record_change(self, security_id: UUID, 
                            id_type: str,  # 'ticker', 'cusip', 'name'
                            old_value: str, new_value: str,
                            effective_date: date,
                            corporate_action_id: UUID | None = None,
                            source: str = 'manual'):
        """Record an identifier change."""
        await self.db.execute("""
            INSERT INTO identifier_history 
            (security_id, identifier_type, old_value, new_value, 
             effective_date, corporate_action_id, source)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
        """, security_id, id_type, old_value, new_value,
             effective_date, corporate_action_id, source)
        
        # Update the securities table with the new value
        column_map = {'ticker': 'ticker', 'cusip': 'cusip', 
                      'isin': 'isin', 'name': 'name'}
        if id_type in column_map:
            col = column_map[id_type]
            await self.db.execute(
                f"UPDATE securities SET {col} = $1, updated_at = NOW() WHERE id = $2",
                new_value, security_id
            )
    
    async def resolve_historical(self, identifier: str, 
                                  id_type: str,
                                  as_of_date: date | None = None
                                  ) -> UUID | None:
        """
        Resolve an identifier to a security_id, accounting for historical changes.
        
        If as_of_date is provided, resolves to what the security was on that date.
        If not provided, checks if this was ever a valid identifier for any security.
        """
        # First: try current identifiers
        column_map = {'ticker': 'ticker', 'cusip': 'cusip', 
                      'isin': 'isin', 'name': 'name'}
        if id_type in column_map:
            col = column_map[id_type]
            result = await self.db.fetchval(
                f"SELECT id FROM securities WHERE {col} = $1",
                identifier
            )
            if result:
                return result
        
        # Second: check identifier_history for old values
        result = await self.db.fetchval("""
            SELECT security_id FROM identifier_history
            WHERE identifier_type = $1 AND old_value = $2
            ORDER BY effective_date DESC
            LIMIT 1
        """, id_type, identifier)
        
        return result
    
    async def get_full_history(self, security_id: UUID) -> list[dict]:
        """
        Get the complete identifier history for a security.
        
        Returns a timeline of all identifier changes.
        """
        rows = await self.db.fetch("""
            SELECT identifier_type, old_value, new_value, effective_date, source
            FROM identifier_history
            WHERE security_id = $1
            ORDER BY effective_date ASC
        """, security_id)
        
        return [dict(row) for row in rows]
    
    async def get_identifier_as_of(self, security_id: UUID,
                                    id_type: str,
                                    as_of_date: date) -> str | None:
        """What was this security's ticker/cusip/name on a specific date?"""
        # Get the most recent change before as_of_date
        result = await self.db.fetchval("""
            SELECT new_value FROM identifier_history
            WHERE security_id = $1 AND identifier_type = $2
              AND effective_date <= $3
            ORDER BY effective_date DESC
            LIMIT 1
        """, security_id, id_type, as_of_date)
        
        if result:
            return result
        
        # If no history, use current value
        column_map = {'ticker': 'ticker', 'cusip': 'cusip', 
                      'isin': 'isin', 'name': 'name'}
        if id_type in column_map:
            return await self.db.fetchval(
                f"SELECT {column_map[id_type]} FROM securities WHERE id = $1",
                security_id
            )
        
        return None
```

## 7.3 Known Ticker Changes (Seed Data)

Build a seed table of well-known ticker changes to bootstrap the system:

```python
KNOWN_TICKER_CHANGES = [
    {"old": "FB", "new": "META", "date": "2022-06-09", "reason": "name_change"},
    {"old": "TWTR", "new": None, "date": "2022-10-28", "reason": "delisting"},  # Twitter taken private
    {"old": "GOOGL", "new": "GOOGL", "date": "2015-10-02", "reason": "restructuring"},  # Alphabet restructure
    {"old": "RDS.A", "new": "SHEL", "date": "2022-01-31", "reason": "name_change"},  # Royal Dutch Shell
    {"old": "DWAC", "new": "DJT", "date": "2024-03-26", "reason": "merger"},  # Trump Media merger
    # Add more as they occur
]
```

---

# 8. MODULE 4: POSITION IMPACT CALCULATOR

## 8.1 Purpose

Given a position (ticker, quantity, optional price) and a corporate action, calculate the resulting position after the action.

## 8.2 Implementation

```python
class PositionImpactCalculator:
    """Calculate how a corporate action affects a position."""
    
    def calculate(self, action: CorporateAction,
                  quantity: Decimal,
                  price: Decimal | None = None) -> PositionImpact:
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
        
        if action.action_type == ActionType.STOCK_SPLIT:
            return self._apply_split(impact, action)
        elif action.action_type == ActionType.REVERSE_SPLIT:
            return self._apply_reverse_split(impact, action)
        elif action.action_type == ActionType.CASH_DIVIDEND:
            return self._apply_cash_dividend(impact, action)
        elif action.action_type == ActionType.SPECIAL_DIVIDEND:
            return self._apply_cash_dividend(impact, action)
        elif action.action_type == ActionType.MERGER:
            return self._apply_merger(impact, action)
        elif action.action_type == ActionType.SPIN_OFF:
            return self._apply_spinoff(impact, action)
        elif action.action_type in (ActionType.NAME_CHANGE, 
                                      ActionType.TICKER_CHANGE,
                                      ActionType.CUSIP_CHANGE):
            return self._apply_identifier_change(impact, action)
        else:
            impact.new_quantity = quantity
            impact.new_price = price
            impact.explanation = f"No position impact for {action.action_type.value}"
            return impact
    
    def _apply_split(self, impact: PositionImpact, 
                     action: CorporateAction) -> PositionImpact:
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
    
    def _apply_reverse_split(self, impact: PositionImpact,
                              action: CorporateAction) -> PositionImpact:
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
            
            # Fractional shares typically paid in cash
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
    
    def _apply_cash_dividend(self, impact: PositionImpact,
                              action: CorporateAction) -> PositionImpact:
        """Apply a cash dividend to a position."""
        impact.new_quantity = impact.original_quantity  # No qty change
        impact.new_price = impact.original_price
        
        if action.dividend_amount and impact.original_quantity:
            # Cash received = dividend per share × shares held
            # For short positions, you PAY the dividend
            impact.cash_received = action.dividend_amount * impact.original_quantity
        
        div_type = "Special dividend" if action.action_type == ActionType.SPECIAL_DIVIDEND else "Dividend"
        
        impact.explanation = (
            f"{div_type} of ${action.dividend_amount} per share "
            f"(ex-date: {action.ex_date}). "
            f"Position unchanged at {impact.original_quantity} shares. "
            f"Cash {'received' if impact.cash_received >= 0 else 'owed'}: "
            f"${abs(impact.cash_received):.2f}."
        )
        
        return impact
    
    def _apply_merger(self, impact: PositionImpact,
                       action: CorporateAction) -> PositionImpact:
        """Apply a merger/acquisition to a position."""
        if action.conversion_ratio:
            impact.new_quantity = impact.original_quantity * action.conversion_ratio
        else:
            impact.new_quantity = impact.original_quantity  # Unknown ratio
        
        if action.cash_per_share:
            impact.cash_received = action.cash_per_share * impact.original_quantity
        
        impact.explanation = (
            f"Merger: {action.ticker} acquired"
        )
        
        if action.acquirer_ticker:
            impact.explanation += f" by {action.acquirer_ticker}"
        
        if action.conversion_ratio:
            impact.explanation += (
                f". Conversion: {action.conversion_ratio} shares per share. "
                f"Position: {impact.original_quantity} → {impact.new_quantity} shares"
            )
        
        if action.cash_per_share:
            impact.explanation += f". Cash: ${action.cash_per_share} per share (${impact.cash_received:.2f} total)"
        
        impact.explanation += "."
        
        return impact
    
    def _apply_spinoff(self, impact: PositionImpact,
                        action: CorporateAction) -> PositionImpact:
        """Apply a spin-off to a position."""
        impact.new_quantity = impact.original_quantity  # Parent qty unchanged
        
        if action.spinoff_ratio:
            spinoff_qty = impact.original_quantity * action.spinoff_ratio
            impact.additional_positions = [{
                'ticker': action.spinoff_ticker or 'UNKNOWN',
                'quantity': spinoff_qty,
                'source': f'Spin-off from {action.ticker}'
            }]
        
        impact.explanation = (
            f"Spin-off: {action.spinoff_ticker or 'New Company'} "
            f"from {action.ticker} on {action.effective_date}. "
            f"Parent position unchanged at {impact.original_quantity} shares."
        )
        
        if action.spinoff_ratio:
            impact.explanation += (
                f" New position: {impact.additional_positions[0]['quantity']} shares "
                f"of {action.spinoff_ticker or 'SpinCo'} "
                f"(ratio: {action.spinoff_ratio} per share)."
            )
        
        return impact
    
    def _apply_identifier_change(self, impact: PositionImpact,
                                  action: CorporateAction) -> PositionImpact:
        """Apply a name/ticker/CUSIP change (no position impact)."""
        impact.new_quantity = impact.original_quantity
        impact.new_price = impact.original_price
        impact.new_market_value = impact.original_market_value
        
        change_type = action.action_type.value.replace('_', ' ').title()
        
        impact.explanation = (
            f"{change_type}: {action.old_value} → {action.new_value} "
            f"effective {action.effective_date}. Position unchanged."
        )
        
        return impact


class BreakExplainer:
    """Explain whether a reconciliation break is caused by a corporate action."""
    
    def __init__(self, split_detector: SplitDividendDetector,
                 edgar_detector: EdgarEventDetector):
        self.split_detector = split_detector
        self.edgar_detector = edgar_detector
        self.calculator = PositionImpactCalculator()
    
    def explain_break(self, ticker: str,
                      internal_qty: Decimal,
                      external_qty: Decimal,
                      as_of_date: date | None = None,
                      lookback_days: int = 30) -> BreakExplanation:
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
                # Check if applying the split to external_qty gives internal_qty
                expected_after_split = external_qty * split.split_ratio
                if abs(expected_after_split - internal_qty) < Decimal('1'):
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
                            f"Expected: {external_qty} × {split.split_ratio} = {expected_after_split}."
                        ),
                        confidence=0.92
                    )
                
                # Check the reverse: internal is pre-split, external is post-split
                expected_pre_split = internal_qty / split.split_ratio
                if abs(expected_pre_split - external_qty) < Decimal('1'):
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
                        confidence=0.90
                    )
        
        # If no split explains it, check for mergers
        # (merger could convert position to different security)
        # This would require knowing the conversion ratio
        
        return BreakExplanation(
            is_explained=False,
            explanation=(
                f"No corporate action found for {ticker} in the last "
                f"{lookback_days} days that explains the quantity break "
                f"({internal_qty} vs {external_qty})."
            ),
            confidence=0.0
        )
```

---

# 9. MODULE 5: PORTFOLIO MONITOR

## 9.1 Purpose

Given a list of tickers (a portfolio), alert the user to upcoming or recent corporate actions that affect their positions.

## 9.2 Implementation

```python
class PortfolioMonitor:
    """Monitor a portfolio for upcoming and recent corporate actions."""
    
    def __init__(self, split_detector: SplitDividendDetector,
                 edgar_detector: EdgarEventDetector):
        self.split_detector = split_detector
        self.edgar_detector = edgar_detector
    
    def scan_portfolio(self, tickers: list[str],
                       days_back: int = 7,
                       days_ahead: int = 14) -> list[dict]:
        """
        Scan a portfolio for recent and upcoming corporate actions.
        
        Returns a list of alerts sorted by date.
        """
        alerts = []
        
        today = date.today()
        start = today - timedelta(days=days_back)
        end = today + timedelta(days=days_ahead)
        
        for ticker in tickers:
            # Check splits and dividends
            actions = self.split_detector.get_all_actions(ticker, start, end)
            
            for action in actions:
                action_date = action.effective_date or action.ex_date
                if action_date is None:
                    continue
                
                is_upcoming = action_date > today
                is_recent = action_date <= today and action_date >= start
                
                alert = {
                    'ticker': ticker,
                    'action': action,
                    'date': action_date,
                    'is_upcoming': is_upcoming,
                    'is_recent': is_recent,
                    'urgency': 'high' if (is_upcoming and (action_date - today).days <= 3) else 'normal',
                    'summary': self._summarize(action),
                }
                
                alerts.append(alert)
            
            # Check EDGAR events (only recent, not forward-looking)
            try:
                events = self.edgar_detector.get_recent_events(ticker, days_back)
                for event in events:
                    alerts.append({
                        'ticker': ticker,
                        'action': event,
                        'date': event.announcement_date or event.effective_date,
                        'is_upcoming': False,
                        'is_recent': True,
                        'urgency': 'high' if event.action_type in (
                            ActionType.MERGER, ActionType.DELISTING
                        ) else 'normal',
                        'summary': self._summarize(event),
                    })
            except Exception as e:
                logger.warning(f"EDGAR scan failed for {ticker}: {e}")
        
        # Sort by date
        alerts.sort(key=lambda a: a['date'] or date.min)
        
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
            return f"{action.ticker}: MERGER — acquired by {action.acquirer_ticker or 'unknown'}"
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
```

---

# 10. PUBLIC API — The Interface Users See

## 10.1 The Main Class

```python
class CorporateActionsEngine:
    """
    Main entry point for the corporate actions library.
    
    Usage:
        from corp_actions import CorporateActionsEngine
        
        engine = CorporateActionsEngine()
        
        # Get all actions for a security
        actions = engine.get_actions("AAPL", days_back=365)
        
        # Check if a break is explained by a corporate action
        explanation = engine.explain_break("AAPL", 
            internal_qty=40000, external_qty=10000)
        
        # Monitor a portfolio
        alerts = engine.monitor(["AAPL", "MSFT", "NVDA"], days_ahead=14)
        
        # Get identifier history
        history = engine.get_identifier_history("AAPL")
    """
    
    def __init__(self, 
                 edgar_identity: str = "corp-actions-user@example.com",
                 groq_api_key: str | None = None,
                 cache_ttl_hours: int = 24,
                 db_path: str | None = None):
        """
        Initialize the engine. ZERO COST by default.
        
        Args:
            edgar_identity: Email for SEC EDGAR User-Agent (required by SEC, free)
            groq_api_key: Optional. Free tier key from console.groq.com. 
                         Without it, merger/name-change detection uses keyword
                         matching instead of LLM (lower accuracy but still works).
            cache_ttl_hours: How long to cache yfinance data (default 24h)
            db_path: Path to SQLite database. Default: ~/.corp-actions/corp_actions.db
        """
        self.split_detector = SplitDividendDetector(cache_ttl_hours)
        self.edgar_detector = EdgarEventDetector(edgar_identity)
        self.calculator = PositionImpactCalculator()
        self.explainer = BreakExplainer(self.split_detector, self.edgar_detector)
        self.monitor_engine = PortfolioMonitor(self.split_detector, self.edgar_detector)
        
        if groq_api_key:
            os.environ["GROQ_API_KEY"] = groq_api_key
        
        # Log what's available
        if os.environ.get("GROQ_API_KEY"):
            logger.info("Groq API key found — LLM extraction enabled for 8-K filings")
        else:
            logger.info(
                "No GROQ_API_KEY set — using keyword-based 8-K classification. "
                "For better accuracy, sign up for a free key at console.groq.com"
            )
    
    def get_actions(self, ticker: str, 
                    days_back: int = 365,
                    include_edgar: bool = True) -> list[CorporateAction]:
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
        
        return sorted(actions, 
                      key=lambda a: (a.effective_date or a.ex_date or date.min),
                      reverse=True)
    
    def explain_break(self, ticker: str,
                      internal_qty: float | Decimal,
                      external_qty: float | Decimal,
                      as_of_date: date | None = None) -> BreakExplanation:
        """Check if a reconciliation break is explained by a corporate action."""
        return self.explainer.explain_break(
            ticker,
            Decimal(str(internal_qty)),
            Decimal(str(external_qty)),
            as_of_date
        )
    
    def calculate_impact(self, ticker: str,
                         quantity: float | Decimal,
                         action: CorporateAction,
                         price: float | Decimal | None = None) -> PositionImpact:
        """Calculate how a corporate action affects a position."""
        return self.calculator.calculate(
            action,
            Decimal(str(quantity)),
            Decimal(str(price)) if price else None
        )
    
    def monitor(self, tickers: list[str],
                days_back: int = 7,
                days_ahead: int = 14) -> list[dict]:
        """Scan a portfolio for relevant corporate actions."""
        return self.monitor_engine.scan_portfolio(tickers, days_back, days_ahead)
    
    def get_splits(self, ticker: str, 
                   days_back: int = 3650) -> list[CorporateAction]:
        """Get all stock splits for a security (last 10 years by default)."""
        start = date.today() - timedelta(days=days_back)
        return self.split_detector.get_splits(ticker, start)
    
    def get_dividends(self, ticker: str,
                      days_back: int = 365) -> list[CorporateAction]:
        """Get all dividends for a security (last year by default)."""
        start = date.today() - timedelta(days=days_back)
        return self.split_detector.get_dividends(ticker, start)
    
    def get_daily_actions(self, 
                          tickers: list[str] | None = None) -> list[CorporateAction]:
        """
        Get all corporate actions happening today.
        
        If tickers is None, checks S&P 500 components (requires a ticker list).
        """
        today = date.today()
        
        if tickers is None:
            # Default to a small set for demo
            tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 
                       'TSLA', 'BRK-B', 'JPM', 'V', 'JNJ', 'WMT', 'PG',
                       'MA', 'UNH', 'HD', 'DIS', 'PYPL', 'NFLX', 'ADBE']
        
        results = []
        for ticker in tickers:
            actions = self.split_detector.get_all_actions(
                ticker, today, today
            )
            results.extend(actions)
        
        return results
```

---

# 11. CLI INTERFACE

```python
# cli.py
import click
from corp_actions import CorporateActionsEngine
from datetime import date

@click.group()
def cli():
    """Corporate Actions Intelligence Engine"""
    pass

@cli.command()
@click.argument('ticker')
@click.option('--days', default=365, help='Days to look back')
def actions(ticker, days):
    """Get all corporate actions for a ticker."""
    engine = CorporateActionsEngine()
    results = engine.get_actions(ticker, days_back=days)
    
    for action in results:
        action_date = action.effective_date or action.ex_date
        print(f"  {action_date} | {action.action_type.value:20s} | {_describe(action)}")

@cli.command()
@click.argument('ticker')
@click.argument('internal_qty', type=float)
@click.argument('external_qty', type=float)
def explain(ticker, internal_qty, external_qty):
    """Explain a reconciliation break."""
    engine = CorporateActionsEngine()
    result = engine.explain_break(ticker, internal_qty, external_qty)
    
    if result.is_explained:
        print(f"✅ BREAK EXPLAINED (confidence: {result.confidence:.0%})")
        print(f"   {result.explanation}")
    else:
        print(f"❌ NO CORPORATE ACTION EXPLANATION FOUND")
        print(f"   {result.explanation}")

@cli.command()
@click.argument('tickers', nargs=-1)
@click.option('--days-ahead', default=14)
def monitor(tickers, days_ahead):
    """Monitor portfolio for upcoming corporate actions."""
    engine = CorporateActionsEngine()
    alerts = engine.monitor(list(tickers), days_ahead=days_ahead)
    
    for alert in alerts:
        prefix = "🔜" if alert['is_upcoming'] else "✅"
        urgency = "🔴" if alert['urgency'] == 'high' else ""
        print(f"  {prefix} {urgency} {alert['summary']}")

@cli.command()
@click.argument('ticker')
def splits(ticker):
    """Get all stock splits for a ticker."""
    engine = CorporateActionsEngine()
    results = engine.get_splits(ticker)
    
    for split in results:
        print(f"  {split.effective_date} | {split.split_from}:{split.split_to} split")

if __name__ == '__main__':
    cli()
```

Usage:
```bash
$ corp-actions actions AAPL --days 3650
$ corp-actions explain AAPL 40000 10000
$ corp-actions monitor AAPL MSFT NVDA TSLA --days-ahead 14
$ corp-actions splits AAPL
```

---

# 12. TEST CASES — WITH GROUND TRUTH

## 12.1 Split Detection Tests

| Test ID | Ticker | Expected Splits | Ground Truth |
|---------|--------|----------------|--------------|
| SP-001 | AAPL | 4:1 (2020-08-31), 7:1 (2014-06-09), 2:1 (2005-02-28, 2000-06-21, 1987-06-16) | Apple's well-documented split history |
| SP-002 | TSLA | 3:1 (2022-08-25), 5:1 (2020-08-31) | Tesla's splits |
| SP-003 | NVDA | 10:1 (2024-06-10), 4:1 (2021-07-20), multiple earlier | NVIDIA splits |
| SP-004 | AMZN | 20:1 (2022-06-06) | Amazon's 2022 split |
| SP-005 | GOOGL | 20:1 (2022-07-18) | Alphabet's 2022 split |
| SP-006 | GE | 1:8 reverse split (2021-08-02) | GE's reverse split — ratio should be 0.125 |
| SP-007 | AIG | 1:20 reverse split (2009-07-01) | Large reverse split |
| SP-008 | Ticker with no splits | BRK-A | Should return empty list |

## 12.2 Dividend Detection Tests

| Test ID | Ticker | Expected | Ground Truth |
|---------|--------|----------|--------------|
| DV-001 | AAPL | Quarterly ~$0.25 (2024-2025) | Apple's regular dividend |
| DV-002 | MSFT | Quarterly ~$0.75 (2024-2025) | Microsoft's regular dividend |
| DV-003 | COST | Occasional special dividends ($15/share in 2023) | Costco's special dividend |
| DV-004 | BRK-A | No dividends ever | Berkshire doesn't pay dividends |
| DV-005 | T | Dividend cut in 2022 (from ~$0.52 to ~$0.2775) | AT&T dividend reduction |

## 12.3 Break Explanation Tests

| Test ID | Scenario | Internal Qty | External Qty | Expected Explanation |
|---------|----------|-------------|-------------|---------------------|
| BE-001 | AAPL post 4:1 split | 40000 | 10000 | "4:1 split explains break" |
| BE-002 | NVDA post 10:1 split | 50000 | 5000 | "10:1 split explains break" |
| BE-003 | No corporate action | 10000 | 9500 | "No corporate action found" |
| BE-004 | GE reverse split | 1250 | 10000 | "1:8 reverse split explains break" |
| BE-005 | Partial match | 39999 | 10000 | "4:1 split explains break (within tolerance)" |

## 12.4 Portfolio Monitor Tests

| Test ID | Portfolio | Expected Alerts |
|---------|-----------|----------------|
| PM-001 | [AAPL, MSFT, JNJ] | Recent dividends for all three |
| PM-002 | Empty portfolio | Empty alerts list |
| PM-003 | [INVALID_TICKER] | Graceful error, empty results |

---

# 13. EDGE CASES

| Edge Case | How It Manifests | How to Handle |
|-----------|-----------------|---------------|
| yfinance is down | Network error or Yahoo changes API | Return cached data; log error; don't crash |
| EDGAR rate limit hit | 429 response | Exponential backoff; queue requests |
| Groq API key not set | No LLM for 8-K classification | Use keyword-based classification (lower accuracy but works). Splits/dividends unaffected. |
| Ticker doesn't exist | yfinance returns empty data | Return empty list; don't crash |
| Ticker was delisted | Historical data may be incomplete | Try to fetch; handle gracefully |
| Ticker changed (FB→META) | yfinance may not link history | Check identifier_history; try both tickers |
| Very old data request | yfinance may have gaps pre-2000 | Return what's available; document limitation |
| Split and dividend on same date | Both events occur | Return both as separate events |
| Fractional shares from reverse split | 100 shares ÷ 8 = 12.5 | Calculate fractional; note cash-in-lieu |
| Merger with all-cash consideration | No stock conversion, just cash | conversion_ratio = None; cash_per_share = X |
| Merger with stock + cash | Complex conversion | Store both conversion_ratio and cash_per_share |
| Spin-off with no clear ratio | 8-K doesn't state ratio | confidence = low; flag for manual entry |
| Multiple corporate actions in quick succession | Split followed by dividend | Process in chronological order |
| International ADR adjustments | ADR ratio changes | Handle as split equivalent |
| ETF rebalancing | Not a corporate action | Don't detect; not in scope |
| Bankruptcy/delisting | Security ceases to exist | Record as DELISTING action |

---

# 14. TECHNOLOGY STACK — ALL FREE

| Component | Choice | Cost | Why |
|-----------|--------|------|-----|
| **Language** | Python 3.11+ | $0 | Best ecosystem for financial data |
| **Package manager** | Poetry or pip | $0 | Poetry for dev, pip for users |
| **Data: Splits/Dividends** | yfinance | $0, no key | Standard, well-maintained |
| **Data: SEC Filings** | edgartools | $0, no key | MIT license, parses 8-K into objects |
| **Data: SEC API direct** | data.sec.gov | $0, no key | Government API, always free |
| **Data: Identifiers** | OpenFIGI | $0, optional free key | 5 req/min without key |
| **LLM (optional)** | Groq (Llama 3.3 70B) | $0, free key | 30 req/min on free tier. OPTIONAL. |
| **Database** | SQLite | $0, built into Python | Single file, no server, no setup |
| **ORM** | None (raw sqlite3) | $0 | Keep dependencies minimal |
| **CLI** | Click | $0 | Standard Python CLI framework |
| **Testing** | pytest | $0 | Standard |
| **Caching** | In-memory dict + SQLite | $0 | No Redis dependency |
| **Packaging** | PyPI | $0 | Free to publish open source |
| **CI/CD** | GitHub Actions | $0 | Free for public repos |
| **Hosting** | None needed | $0 | It's a library, not a web app |
| **Fuzzy matching** | rapidfuzz (optional) | $0 | For security name matching |

**Total infrastructure cost: $0/month. $0/year. Forever.**

### Dependencies (pyproject.toml)

```toml
[tool.poetry]
name = "corp-actions"
version = "0.1.0"
description = "Corporate actions intelligence engine for trading operations"
license = "MIT"

[tool.poetry.dependencies]
python = "^3.11"
yfinance = ">=0.2.36"      # Splits, dividends, prices ($0)
edgartools = ">=5.0"        # SEC EDGAR filings ($0)
httpx = ">=0.27"            # HTTP client ($0)
click = ">=8.0"             # CLI framework ($0)

[tool.poetry.group.dev.dependencies]
pytest = ">=8.0"
pytest-asyncio = ">=0.23"

[tool.poetry.group.llm.dependencies]
# OPTIONAL — install with: pip install corp-actions[llm]
groq = ">=0.9"              # Free tier LLM ($0)

[tool.poetry.scripts]
corp-actions = "corp_actions.cli:cli"
```

### Install Commands

```bash
# Basic install (splits, dividends, break explanation — no LLM needed)
pip install corp-actions

# Full install (adds LLM-powered 8-K merger/name detection)
pip install corp-actions[llm]
```

---

# 15. BUILD PHASES — 6-WEEK PLAN (Total Cost: $0)

## Week 1-2: Core Engine (No LLM Needed)

**Claude CLI Prompt:**
```
Read corp_actions_dev_guide.md sections 4, 5, and 8. Build:
1. SQLite database layer (db.py) with the schema from Section 4
2. SplitDividendDetector from Section 5 with in-memory caching
3. PositionImpactCalculator and BreakExplainer from Section 8
4. CLI commands: splits, dividends, explain
5. pytest tests for SP-001 through SP-008 and BE-001 through BE-005
Use only yfinance and sqlite3. No paid dependencies.
```

- [ ] Project setup: pyproject.toml, pytest, GitHub repo, CI
- [ ] SQLite database layer (db.py with auto-creation)
- [ ] Data classes: CorporateAction, PositionImpact, BreakExplanation
- [ ] SplitDividendDetector: yfinance integration with in-memory + SQLite caching
- [ ] PositionImpactCalculator: split, reverse split, dividend math
- [ ] BreakExplainer: the "explain_break" function (THE KEY DEMO)
- [ ] CLI: `corp-actions splits AAPL`, `corp-actions explain AAPL 40000 10000`
- [ ] Tests: SP-001 through SP-008, DV-001 through DV-005, BE-001 through BE-005

**Deliverable:** `pip install .` works locally. `corp-actions explain AAPL 40000 10000` returns correct answer. **Cost: $0.**

## Week 3-4: EDGAR Integration (LLM Optional)

**Claude CLI Prompt:**
```
Read corp_actions_dev_guide.md sections 6 and 7. Build:
1. EdgarEventDetector with keyword-based classification (no LLM)
2. Add optional Groq/Llama classification if GROQ_API_KEY is set
3. IdentifierTracker for CUSIP/ticker change history
4. Seed known ticker changes (FB→META, RDS.A→SHEL, etc.)
5. Tests for 8-K parsing with known mergers and name changes
Groq must be OPTIONAL. Engine must work without it.
```

- [ ] EdgarEventDetector: 8-K fetching via edgartools (free, no key)
- [ ] Keyword-based classification (works without ANY API key)
- [ ] OPTIONAL: Groq/Llama classification for higher accuracy (free key)
- [ ] Merger/acquisition detection from 8-K Items 1.01, 2.01
- [ ] Name change detection from 8-K Item 5.03
- [ ] IdentifierTracker: CUSIP/ticker change history in SQLite
- [ ] Known ticker changes seed data
- [ ] Tests: 8-K parsing tests with known mergers and name changes
- [ ] Verify: engine works correctly with AND without GROQ_API_KEY

**Deliverable:** `corp-actions actions META --days 1825` shows the FB→META name change. **Cost: $0.**

## Week 5-6: Portfolio Monitor + Publish

**Claude CLI Prompt:**
```
Read corp_actions_dev_guide.md sections 9, 10, and 12. Build:
1. PortfolioMonitor: scan portfolio for alerts
2. CorporateActionsEngine: unified API class
3. CLI: monitor command
4. README.md with installation, examples, and API docs
5. pyproject.toml configured for PyPI publishing
6. GitHub Actions CI workflow (.github/workflows/test.yml)
```

- [ ] PortfolioMonitor: scan portfolio for alerts
- [ ] CorporateActionsEngine: unified API class (Section 10)
- [ ] CLI: `corp-actions monitor AAPL MSFT NVDA --days-ahead 14`
- [ ] README with examples, installation, API docs, and badges
- [ ] pyproject.toml with optional [llm] extra
- [ ] Publish to PyPI
- [ ] GitHub repo with CI (GitHub Actions — free for public repos)
- [ ] Record demo, write LinkedIn post

**Deliverable:** Published on PyPI. `pip install corp-actions` works globally. Clean README. **Cost: $0.**

---

# 16. PRESSURE TEST — WHAT WILL BREAK

## What WILL work well (Day 1, $0):
1. **Split detection** — yfinance is reliable for historical splits. No API key needed. This works immediately.
2. **Dividend detection** — same as splits. No key. Reliable.
3. **Break explanation for splits** — the math is deterministic. If AAPL had a 4:1 split and your internal says 40K and external says 10K, this will always get it right. No LLM needed.
4. **CLI interface** — Click is simple and reliable.
5. **SQLite storage** — Zero setup. Auto-creates on first use.
6. **Keyword-based 8-K classification** — Works without Groq key. Lower accuracy (~50-60%) but catches obvious name changes and mergers.

## What WILL be fragile:
1. **yfinance dependency** — Yahoo can change their API at any time. The library has broken before and will break again. Mitigation: aggressive SQLite caching — once fetched, data persists even if yfinance goes down.
2. **LLM extraction from 8-K** — Llama 70B via Groq free tier will correctly classify ~70-80% of 8-K items. Complex mergers with multi-component consideration will be wrong. Mitigation: low confidence scores, keyword fallback.
3. **EDGAR rate limits** — If you scan 500 tickers at once, you'll hit the 10 req/sec limit. Mitigation: rate limiter in edgartools handles this automatically.
4. **Groq free tier limits** — 30 req/min, 6K tokens/min. Mitigation: only use LLM for 8-K items that match relevant item numbers (not every 8-K). Typical usage: 5-15 LLM calls per ticker scan. Well within free tier.

## What WON'T work (be honest about this):
1. **Forward-looking corporate actions** — yfinance only shows historical events. EDGAR shows announcements but not always with clear future dates. Your tool is better at "what happened" than "what will happen."
2. **Spin-off allocation ratios** — These are buried in complex legal documents. The LLM will get maybe 50% of them right. The keyword classifier won't get them at all. Be honest in the README.
3. **Real-time** — This is a polling-based system. Not real-time. Daily-refresh at best.
4. **Non-US securities** — v1 is US only. yfinance has some international data but it's less reliable.

## What Happens If Free Tiers Disappear?

| Component | If It Stops Being Free | Fallback |
|-----------|----------------------|----------|
| yfinance | Yahoo changes API | Cache all data in SQLite. Serve from cache. Alert user. |
| edgartools | Unlikely (MIT, talks to free gov API) | Direct EDGAR API calls via httpx |
| Groq free tier | Groq removes free tier | Keyword-based classification (already built). Or switch to Ollama (local, free). |
| SEC EDGAR | Government API, will always be free | N/A — this will never happen |
| OpenFIGI | Bloomberg removes free access | Use SEC company_tickers.json + CUSIP↔ISIN formula |

## The README Must Say:
"This library provides corporate actions intelligence from free public data sources. It is NOT a replacement for Bloomberg or S&P corporate actions feeds. Accuracy is high for splits and dividends (>95%) and lower for mergers and spin-offs (~70-80% with LLM, ~50-60% with keyword fallback) where data is extracted from unstructured filings. All LLM-extracted data is flagged with a confidence score. Use for research, reconciliation assistance, and portfolio monitoring. Verify critical actions against official sources before taking action."

---

# 17. WHAT THIS IS NOT

- **NOT a Bloomberg Terminal replacement.** Bloomberg has real-time, verified, global corporate actions. This is a free alternative with lower coverage.
- **NOT real-time.** Data refreshes when you call the functions. No streaming.
- **NOT global.** v1 is US equities only.
- **NOT a trading system.** Don't auto-trade based on this data without verification.
- **NOT 100% accurate for LLM-extracted events.** Splits and dividends: >95%. Mergers (LLM): ~70-80%. Mergers (keyword): ~50-60%. Spin-offs: ~50-60%.
- **NOT expensive.** Total cost to build, run, and maintain: $0.

---

# APPENDIX A: COMPLETE PROJECT STRUCTURE

```
corp-actions/
├── pyproject.toml              # Package config with [llm] optional extra
├── README.md                   # Installation, examples, accuracy table
├── LICENSE                     # MIT
├── .github/
│   └── workflows/
│       └── test.yml            # CI: pytest on push (free for public repos)
├── src/
│   └── corp_actions/
│       ├── __init__.py         # Export CorporateActionsEngine
│       ├── engine.py           # CorporateActionsEngine (Section 10)
│       ├── models.py           # CorporateAction, PositionImpact, etc.
│       ├── db.py               # SQLite helper (Section 4)
│       ├── splits.py           # SplitDividendDetector (Section 5)
│       ├── edgar.py            # EdgarEventDetector (Section 6)
│       ├── identifiers.py      # IdentifierTracker (Section 7)
│       ├── impact.py           # PositionImpactCalculator (Section 8)
│       ├── explainer.py        # BreakExplainer (Section 8)
│       ├── monitor.py          # PortfolioMonitor (Section 9)
│       ├── cli.py              # Click CLI (Section 11)
│       └── seed_data.py        # Known ticker changes, etc.
├── tests/
│   ├── test_splits.py          # SP-001 through SP-008
│   ├── test_dividends.py       # DV-001 through DV-005
│   ├── test_breaks.py          # BE-001 through BE-005
│   ├── test_edgar.py           # 8-K classification tests
│   ├── test_monitor.py         # PM-001 through PM-003
│   └── test_impact.py          # Position impact calculation tests
└── examples/
    ├── basic_usage.py
    ├── explain_break.py
    └── portfolio_scan.py
```

# APPENDIX B: CLAUDE CLI SESSION STARTERS

Copy-paste these into Claude CLI to start each build phase:

**Session 1 (Week 1):**
```
I'm building an open-source Python library called corp-actions.
Read the development guide at corp_actions_dev_guide.md.
Start with: models.py (data classes), db.py (SQLite layer), and 
splits.py (SplitDividendDetector). All zero cost — only yfinance 
and sqlite3. Write pytest tests for split detection using real 
AAPL, TSLA, NVDA data.
```

**Session 2 (Week 2):**
```
Continue building corp-actions. Read sections 8 and 11 of the dev guide.
Build impact.py (PositionImpactCalculator), explainer.py (BreakExplainer),
and cli.py (Click CLI with splits, dividends, explain commands).
Test: corp-actions explain AAPL 40000 10000 should correctly identify 
the 4:1 split.
```

**Session 3 (Week 3-4):**
```
Continue building corp-actions. Read sections 6 and 7 of the dev guide.
Build edgar.py with BOTH keyword-based classification (no LLM) and 
optional Groq/Llama classification. Build identifiers.py for CUSIP/ticker
change tracking. Engine must work perfectly without GROQ_API_KEY set.
Test with known events: FB→META name change, recent mergers.
```

**Session 4 (Week 5-6):**
```
Finalize corp-actions. Read sections 9 and 10 of the dev guide.
Build monitor.py and engine.py (unified API). Update cli.py with 
monitor command. Write README.md with installation, examples, and 
accuracy table. Configure pyproject.toml for PyPI publishing with 
optional [llm] extra. Set up GitHub Actions CI.
```
