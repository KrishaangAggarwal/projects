"""
CLI interface for corp-actions.

Usage:
    corp-actions actions AAPL --days 3650
    corp-actions explain AAPL 40000 10000
    corp-actions monitor AAPL MSFT NVDA --days-ahead 14
    corp-actions splits AAPL
    corp-actions dividends MSFT --days 365
    corp-actions replay AAPL 1000 --since 2020-01-01
    corp-actions recon internal.csv external.csv
    corp-actions watch AAPL MSFT NVDA --interval 1800
    corp-actions health
"""

import logging
import sys

import click
from datetime import date
from decimal import Decimal
from pathlib import Path

from corp_actions.engine import CorporateActionsEngine
from corp_actions.models import ActionType


def _describe(action) -> str:
    """One-line description of a corporate action."""
    if action.action_type == ActionType.STOCK_SPLIT:
        return f"{action.split_from}:{action.split_to} stock split"
    elif action.action_type == ActionType.REVERSE_SPLIT:
        return f"{action.split_from}:{action.split_to} reverse split"
    elif action.action_type in (ActionType.CASH_DIVIDEND, ActionType.SPECIAL_DIVIDEND):
        prefix = "SPECIAL " if action.action_type == ActionType.SPECIAL_DIVIDEND else ""
        return f"{prefix}${action.dividend_amount} dividend"
    elif action.action_type == ActionType.MERGER:
        return f"Merger — acquired by {action.acquirer_ticker or 'unknown'}"
    elif action.action_type == ActionType.NAME_CHANGE:
        return f"Name change: {action.old_value} → {action.new_value}"
    elif action.action_type == ActionType.TICKER_CHANGE:
        return f"Ticker change: {action.old_value} → {action.new_value}"
    elif action.action_type == ActionType.SPIN_OFF:
        return f"Spin-off: {action.spinoff_ticker or 'new entity'}"
    elif action.action_type == ActionType.DELISTING:
        return "DELISTED"
    else:
        return action.action_type.value


@click.group()
@click.version_option(version="0.1.0", prog_name="corp-actions")
@click.option("--verbose", is_flag=True, help="Enable debug logging")
def cli(verbose):
    """Corporate Actions Intelligence Engine — free, open-source."""
    if verbose:
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(levelname)s %(name)s: %(message)s",
        )


@cli.command()
@click.argument("ticker")
@click.option("--days", default=365, help="Days to look back")
@click.option("--no-edgar", is_flag=True, help="Skip EDGAR 8-K scan")
def actions(ticker, days, no_edgar):
    """Get all corporate actions for a ticker."""
    engine = CorporateActionsEngine()
    results = engine.get_actions(ticker, days_back=days, include_edgar=not no_edgar)

    if not results:
        click.echo(f"  No corporate actions found for {ticker} in the last {days} days.")
        return

    click.echo(f"\n  Corporate actions for {ticker} (last {days} days):\n")
    for action in results:
        action_date = action.effective_date or action.ex_date
        conf = f"[{action.confidence:.0%}]" if action.confidence < 1.0 else ""
        click.echo(
            f"  {action_date} | {action.action_type.value:20s} | "
            f"{_describe(action)} {conf}"
        )
    click.echo()


@cli.command()
@click.argument("ticker")
@click.argument("internal_qty", type=float)
@click.argument("external_qty", type=float)
@click.option("--lookback", default=365, help="Days to look back for corporate actions")
def explain(ticker, internal_qty, external_qty, lookback):
    """Explain a reconciliation break between internal and external positions."""
    engine = CorporateActionsEngine()
    result = engine.explain_break(ticker, internal_qty, external_qty)

    click.echo()
    if result.is_explained:
        click.echo(f"  ✅ BREAK EXPLAINED (confidence: {result.confidence:.0%})")
        click.echo(f"     {result.explanation}")
    else:
        click.echo(f"  ❌ NO CORPORATE ACTION EXPLANATION FOUND")
        click.echo(f"     {result.explanation}")
    click.echo()


@cli.command()
@click.argument("tickers", nargs=-1, required=True)
@click.option("--days-back", default=7, help="Days to look back")
@click.option("--days-ahead", default=14, help="Days to look ahead")
def monitor(tickers, days_back, days_ahead):
    """Monitor portfolio for upcoming corporate actions."""
    engine = CorporateActionsEngine()
    alerts = engine.monitor(list(tickers), days_back=days_back, days_ahead=days_ahead)

    if not alerts:
        click.echo(f"\n  No corporate actions found for {', '.join(tickers)}.\n")
        return

    click.echo(f"\n  Portfolio Monitor — {len(alerts)} alert(s):\n")
    for alert in alerts:
        prefix = "🔜" if alert["is_upcoming"] else "✅"
        urgency = " 🔴" if alert["urgency"] == "high" else ""
        click.echo(f"  {prefix}{urgency} {alert['summary']}")
    click.echo()


@cli.command()
@click.argument("ticker")
@click.option("--days", default=3650, help="Days to look back (default: 10 years)")
def splits(ticker, days):
    """Get all stock splits for a ticker."""
    engine = CorporateActionsEngine()
    results = engine.get_splits(ticker, days_back=days)

    if not results:
        click.echo(f"\n  No splits found for {ticker}.\n")
        return

    click.echo(f"\n  Splits for {ticker}:\n")
    for split in results:
        click.echo(
            f"  {split.effective_date} | "
            f"{split.split_from}:{split.split_to} split "
            f"(ratio: {split.split_ratio})"
        )
    click.echo()


@cli.command()
@click.argument("ticker")
@click.option("--days", default=365, help="Days to look back")
def dividends(ticker, days):
    """Get all dividends for a ticker."""
    engine = CorporateActionsEngine()
    results = engine.get_dividends(ticker, days_back=days)

    if not results:
        click.echo(f"\n  No dividends found for {ticker} in the last {days} days.\n")
        return

    click.echo(f"\n  Dividends for {ticker} (last {days} days):\n")
    for div in results:
        div_type = "SPECIAL" if div.action_type == ActionType.SPECIAL_DIVIDEND else "Regular"
        click.echo(
            f"  {div.ex_date} | ${div.dividend_amount:>8.4f} | {div_type}"
        )
    click.echo()


@cli.command()
@click.argument("ticker")
@click.argument("quantity", type=float)
@click.option("--price", type=float, default=None, help="Price per share")
def impact(ticker, quantity, price):
    """Calculate position impact from recent corporate actions."""
    engine = CorporateActionsEngine()
    recent_actions = engine.get_actions(ticker, days_back=90, include_edgar=False)

    if not recent_actions:
        click.echo(f"\n  No recent corporate actions for {ticker}.\n")
        return

    click.echo(f"\n  Position impact for {quantity:,.0f} shares of {ticker}:\n")
    for action in recent_actions[:5]:
        result = engine.calculate_impact(action, quantity, price)
        click.echo(f"  {result.explanation}")
    click.echo()


@cli.command()
@click.argument("ticker")
def history(ticker):
    """Show full identifier change history for a security.

    Works with both current and historical tickers (e.g. FB or META).
    """
    engine = CorporateActionsEngine()
    result = engine.get_identifier_history(ticker)

    if not result["security"]:
        click.echo(f"\n  No identifier history found for '{ticker}'.\n")
        return

    sec = result["security"]
    click.echo(f"\n  Identifier History: {sec.get('name', ticker)}")
    click.echo(f"  Current ticker: {sec.get('ticker', 'N/A')}")
    is_active = sec.get("is_active", 1)
    if not is_active:
        click.echo("  Status: DELISTED / INACTIVE")
    click.echo()

    if not result["history"]:
        click.echo("  No identifier changes recorded.\n")
        return

    for change in result["history"]:
        id_type = change["identifier_type"].upper()
        old = change["old_value"] or "N/A"
        new = change["new_value"] or "DELISTED"
        eff = change["effective_date"]
        src = change.get("source", "")
        click.echo(f"  {eff} | {id_type:8s} | {old} -> {new}  [{src}]")
    click.echo()


@cli.command()
@click.argument("ticker")
@click.argument("quantity", type=float)
@click.option("--since", required=True, help="Entry date (YYYY-MM-DD)")
def replay(ticker, quantity, since):
    """Replay corporate actions on a position since entry date.

    Shows how splits and dividends changed your position over time.
    """
    engine = CorporateActionsEngine()
    entry_date = date.fromisoformat(since)
    result = engine.replay_position(ticker, quantity, entry_date)

    click.echo(f"\n  Position Replay: {ticker}")
    click.echo(f"  Entry: {result.entry_quantity} shares on {result.entry_date}")
    click.echo(f"  Current: {result.current_quantity} shares")

    if result.adjustments:
        click.echo(f"\n  Adjustments ({len(result.adjustments)}):\n")
        for adj in result.adjustments:
            desc = adj.get("description", adj.get("action_type", ""))
            click.echo(
                f"  {adj['date']} | {adj['before_quantity']:>12s} → "
                f"{adj['after_quantity']:>12s} | {desc}"
            )

    if result.total_cash_received > 0:
        click.echo(f"\n  Total dividends received: ${result.total_cash_received:.2f}")
    if result.total_cash_in_lieu > 0:
        click.echo(
            f"  Fractional shares (cash-in-lieu): "
            f"{result.total_cash_in_lieu:.4f} shares"
        )
    click.echo()


@cli.command()
@click.argument("internal_file", type=click.Path(exists=True))
@click.argument("external_file", type=click.Path(exists=True))
@click.option("--lookback", default=3650, help="Days to look back")
def recon(internal_file, external_file, lookback):
    """Reconcile two position files and explain discrepancies.

    Both files should be CSV with columns: ticker, quantity
    """
    from corp_actions.recon import BulkRecon

    engine = CorporateActionsEngine()

    int_csv = Path(internal_file).read_text()
    ext_csv = Path(external_file).read_text()

    internal = BulkRecon.parse_position_csv(int_csv)
    external = BulkRecon.parse_position_csv(ext_csv)

    if not internal and not external:
        click.echo("\n  Both files are empty or unparseable.\n")
        return

    results = engine.reconcile(internal, external, lookback)

    recon_engine = BulkRecon(engine.explainer, engine._identifier_tracker)
    click.echo()
    click.echo(recon_engine.format_report(results))
    click.echo()


@cli.command()
@click.argument("tickers", nargs=-1, required=True)
@click.option("--interval", default=1800, help="Seconds between checks (min 300)")
def watch(tickers, interval):
    """Monitor tickers for new corporate actions in near-real-time.

    Uses EDGAR and yfinance. Events may appear 1-24 hours after occurrence.
    Press Ctrl+C to stop.
    """
    engine = CorporateActionsEngine()
    click.echo(
        f"\n  Monitoring {len(tickers)} tickers every {interval}s. "
        f"Ctrl+C to stop."
    )
    click.echo(
        "  Note: free data sources have variable latency "
        "(minutes to hours for EDGAR, 1-2 days for yfinance).\n"
    )
    engine.watch(list(tickers), interval=interval)


@cli.command()
def health():
    """Check connectivity and status of all data sources."""
    from corp_actions.health import HealthChecker

    engine = CorporateActionsEngine()
    results = engine.health_check()
    click.echo(HealthChecker.format_report(results))


if __name__ == "__main__":
    cli()
