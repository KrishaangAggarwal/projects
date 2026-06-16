# corp-actions

**Corporate Actions Intelligence Engine** — free, open-source Python library for trading operations.

Detects stock splits, dividends, mergers, name changes, and other corporate actions from public data sources. Calculates position impacts and explains reconciliation breaks. **Total cost: $0.**

## Installation

```bash
# Basic install (splits, dividends, break explanation)
pip install corp-actions

# Full install (adds LLM-powered merger/name-change detection from 8-K filings)
pip install "corp-actions[llm]"
```

## Quick Start

```python
from corp_actions import CorporateActionsEngine

engine = CorporateActionsEngine()

# Get all corporate actions for Apple (last 10 years)
actions = engine.get_actions("AAPL", days_back=3650)

# Explain a reconciliation break
# "My system says 40,000 shares but PB says 10,000"
explanation = engine.explain_break("AAPL", internal_qty=40000, external_qty=10000)
print(explanation.explanation)
# → "Break explained by 1:4 stock split on 2020-08-31..."

# Monitor a portfolio for upcoming corporate actions
alerts = engine.monitor(["AAPL", "MSFT", "NVDA", "TSLA"], days_ahead=14)

# Resolve historical tickers
current = engine.resolve_ticker("FB")   # → "META"

# Get identifier change timeline
history = engine.get_identifier_history("FB")
```

## CLI

```bash
# Stock splits
$ corp-actions splits AAPL

  Splits for AAPL:

  2020-08-31 | 1:4 split (ratio: 4.0)

# Explain a reconciliation break
$ corp-actions explain AAPL 40000 10000

  BREAK EXPLAINED (confidence: 92%)
     Break explained by 1:4 stock split on 2020-08-31.
     External shows pre-split qty (10000.0), internal shows
     post-split qty (40000.0). Expected: 10000.0 x 4.0 = 40000.00.

# Dividends
$ corp-actions dividends MSFT --days 365

  Dividends for MSFT (last 365 days):

  2025-05-15 | $  0.8300 | Regular
  2025-08-21 | $  0.8300 | Regular
  2025-11-20 | $  0.9100 | Regular
  2026-02-19 | $  0.9100 | Regular

# Identifier history (works with old tickers too)
$ corp-actions history FB

  Identifier History: Meta Platforms, Inc.
  Current ticker: META

  2021-10-28 | NAME     | Facebook, Inc. -> Meta Platforms, Inc.  [seed]
  2022-06-09 | TICKER   | FB -> META  [seed]

# All corporate actions (with EDGAR 8-K scanning)
$ corp-actions actions META --days 1825

  Corporate actions for META (last 1825 days):

  2025-12-15 | cash_dividend        | $0.525 dividend
  2025-09-22 | cash_dividend        | $0.525 dividend
  ...
  2021-10-28 | name_change          | Name change: Facebook, Inc. -> Meta Platforms, Inc. [70%]

# Portfolio monitoring
$ corp-actions monitor AAPL MSFT NVDA --days-ahead 14

# Position impact calculator
$ corp-actions impact AAPL 10000
```

## What It Does

| Feature | Description | Accuracy |
|---------|-------------|----------|
| Split detection | Stock splits and reverse splits from Yahoo Finance | >95% |
| Dividend detection | Cash dividends and special dividends | >95% |
| Break explanation | "Why do my numbers not match?" finds the corporate action | >90% for splits |
| Merger detection | From SEC EDGAR 8-K filings (LLM or keyword) | 70-80% (LLM) / 50-60% (keyword) |
| Name/ticker changes | From SEC EDGAR 8-K filings | 70-80% (LLM) / 50-60% (keyword) |
| Identifier tracking | Resolve historical tickers (FB -> META, RDS.A -> SHEL) | Deterministic (seeded) |
| Portfolio monitoring | Alerts for upcoming/recent actions | Depends on source |
| Position impact | Calculate new position after any corporate action | Deterministic |

## Environment Variables

```bash
# Required: your identity for SEC EDGAR requests (any email works)
export EDGAR_IDENTITY="Your Name your@email.com"

# Optional: free Groq key for LLM-powered 8-K analysis
export GROQ_API_KEY="your-free-key-here"  # Get at console.groq.com
```

## Data Sources (All Free)

| Source | What It Provides | API Key |
|--------|-----------------|---------|
| Yahoo Finance (yfinance) | Splits, dividends, prices | None needed |
| SEC EDGAR (edgartools) | 8-K filings, mergers, name changes | None needed |
| Groq (Llama 3.3 70B) | LLM extraction from filings | Free key (optional) |
| SQLite | Local caching & offline resilience | Built into Python |

## Architecture

```
corp-actions/
  src/corp_actions/
    engine.py       # Public API — CorporateActionsEngine
    splits.py       # Yahoo Finance split/dividend detector + SQLite cache
    edgar.py        # SEC EDGAR 8-K filing scanner (keyword + LLM)
    identifiers.py  # Historical ticker/name resolution
    impact.py       # Position impact calculator + break explainer
    monitor.py      # Portfolio monitoring
    models.py       # Data classes (CorporateAction, BreakExplanation, etc.)
    db.py           # SQLite persistence layer
    cli.py          # Click CLI
```

## Testing

```bash
# Unit tests only (no network, fast)
python -m pytest tests/ -v -m "not network"

# Full suite including live EDGAR/Yahoo tests
EDGAR_IDENTITY="you@email.com" python -m pytest tests/ -v

# With LLM classification tests
GROQ_API_KEY="your-key" EDGAR_IDENTITY="you@email.com" python -m pytest tests/ -v
```

86 tests covering splits, dividends, break explanation, EDGAR classification, identifier resolution, position impact, and portfolio monitoring.

## Limitations

- **NOT a Bloomberg Terminal replacement.** Bloomberg has real-time, verified, global corporate actions.
- **NOT real-time.** Data refreshes when you call the functions.
- **NOT global.** US equities only (v0.1).
- **NOT 100% accurate for LLM-extracted events.** Confidence scores are provided.

This library provides corporate actions intelligence from free public data sources. Accuracy is high for splits and dividends (>95%) and lower for mergers and spin-offs (~70-80% with LLM, ~50-60% with keyword fallback). All LLM-extracted data is flagged with a confidence score.

## License

MIT
