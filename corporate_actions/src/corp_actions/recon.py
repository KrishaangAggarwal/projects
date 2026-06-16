"""
Bulk Reconciliation Engine — compare two position files and explain
every discrepancy using corporate actions.

Usage:
    from corp_actions.recon import BulkRecon

    recon = BulkRecon(engine)
    results = recon.reconcile(internal_positions, external_positions)
"""

import csv
import io
import logging
from decimal import Decimal

from corp_actions.models import ReconMatch

logger = logging.getLogger(__name__)


class BulkRecon:
    """Compare two sets of positions and explain discrepancies."""

    def __init__(self, explainer, identifier_tracker=None):
        """
        Args:
            explainer: BreakExplainer instance
            identifier_tracker: optional IdentifierTracker for ticker renames
        """
        self.explainer = explainer
        self.identifier_tracker = identifier_tracker

    def reconcile(
        self,
        internal: dict[str, Decimal],
        external: dict[str, Decimal],
        lookback_days: int = 3650,
    ) -> list[ReconMatch]:
        """
        Reconcile two position sets.

        Args:
            internal: {ticker: quantity} from internal system
            external: {ticker: quantity} from external source
            lookback_days: how far back to search for explaining actions

        Returns:
            list of ReconMatch sorted by status priority
        """
        # Normalize tickers to uppercase
        internal = {k.upper().strip(): v for k, v in internal.items()}
        external = {k.upper().strip(): v for k, v in external.items()}

        results = []
        matched_external = set()

        # 1. Process tickers in internal
        for ticker, int_qty in internal.items():
            if ticker in external:
                ext_qty = external[ticker]
                matched_external.add(ticker)
                match = self._compare_pair(ticker, int_qty, ext_qty, lookback_days)
                results.append(match)
            else:
                # Only in internal — check if it was renamed
                match = self._handle_missing_external(
                    ticker, int_qty, external, matched_external, lookback_days
                )
                results.append(match)

        # 2. Process tickers only in external
        for ticker, ext_qty in external.items():
            if ticker in matched_external:
                continue
            match = self._handle_missing_internal(
                ticker, ext_qty, internal, lookback_days
            )
            results.append(match)

        # Sort by status priority
        priority = {
            "UNEXPLAINED": 0,
            "MISSING": 1,
            "POSSIBLE": 2,
            "EXPLAINED": 3,
            "MATCHED": 4,
        }
        results.sort(key=lambda m: priority.get(m.status, 0))

        return results

    def _compare_pair(
        self,
        ticker: str,
        int_qty: Decimal,
        ext_qty: Decimal,
        lookback_days: int,
    ) -> ReconMatch:
        """Compare a matched ticker pair."""
        match = ReconMatch(
            ticker=ticker,
            internal_qty=int_qty,
            external_qty=ext_qty,
        )

        # Exact match (within rounding)
        if abs(int_qty - ext_qty) < Decimal("0.01"):
            match.status = "MATCHED"
            return match

        # Try to explain the break
        try:
            explanations = self.explainer.explain_all_breaks(
                ticker, int_qty, ext_qty, lookback_days=lookback_days
            )
            if explanations:
                match.explanations = explanations
                best = explanations[0]
                if best.is_explained and best.confidence >= 0.70:
                    match.status = "EXPLAINED"
                elif best.is_explained:
                    match.status = "POSSIBLE"
                else:
                    match.status = "UNEXPLAINED"
            else:
                match.status = "UNEXPLAINED"
        except Exception as e:
            logger.warning(f"Break explanation failed for {ticker}: {e}")
            match.status = "UNEXPLAINED"
            match.notes = str(e)

        return match

    def _handle_missing_external(
        self,
        ticker: str,
        int_qty: Decimal,
        external: dict[str, Decimal],
        matched_external: set,
        lookback_days: int,
    ) -> ReconMatch:
        """Handle a ticker present in internal but not external."""
        match = ReconMatch(
            ticker=ticker,
            internal_qty=int_qty,
            external_qty=None,
            status="MISSING",
            notes="Only in internal file",
        )

        # Check if ticker was renamed and the new name is in external
        if self.identifier_tracker:
            try:
                sec_id = self.identifier_tracker.resolve_historical(ticker, "ticker")
                if sec_id:
                    info = self.identifier_tracker.get_security_info(sec_id)
                    current_ticker = info.get("ticker", "") if info else ""
                    if (
                        current_ticker
                        and current_ticker.upper() != ticker.upper()
                        and current_ticker.upper() in external
                        and current_ticker.upper() not in matched_external
                    ):
                        # Found the renamed ticker in external
                        ext_qty = external[current_ticker.upper()]
                        matched_external.add(current_ticker.upper())
                        match.matched_ticker = current_ticker
                        match.external_qty = ext_qty
                        match.notes = (
                            f"Ticker renamed: {ticker} → {current_ticker}"
                        )
                        if abs(int_qty - ext_qty) < Decimal("0.01"):
                            match.status = "EXPLAINED"
                        else:
                            match.status = "POSSIBLE"
                            match.notes += (
                                f" (qty mismatch: {int_qty} vs {ext_qty})"
                            )
                        return match

                    # Check if delisted
                    is_active = info.get("is_active", 1) if info else 1
                    if not is_active:
                        match.notes = f"Ticker {ticker} is delisted/inactive"
                        return match
            except Exception as e:
                logger.debug(f"Identifier check failed for {ticker}: {e}")

        # Check external for possible renamed versions
        if self.identifier_tracker:
            for ext_ticker in external:
                if ext_ticker in matched_external:
                    continue
                try:
                    ext_sec = self.identifier_tracker.resolve_historical(
                        ext_ticker, "ticker"
                    )
                    int_sec = self.identifier_tracker.resolve_historical(
                        ticker, "ticker"
                    )
                    if ext_sec and int_sec and ext_sec == int_sec:
                        ext_qty = external[ext_ticker]
                        matched_external.add(ext_ticker)
                        match.matched_ticker = ext_ticker
                        match.external_qty = ext_qty
                        match.notes = (
                            f"Same security: {ticker} = {ext_ticker}"
                        )
                        match.status = "EXPLAINED" if abs(int_qty - ext_qty) < Decimal("0.01") else "POSSIBLE"
                        return match
                except Exception:
                    continue

        return match

    def _handle_missing_internal(
        self,
        ticker: str,
        ext_qty: Decimal,
        internal: dict[str, Decimal],
        lookback_days: int,
    ) -> ReconMatch:
        """Handle a ticker present in external but not internal."""
        match = ReconMatch(
            ticker=ticker,
            internal_qty=None,
            external_qty=ext_qty,
            status="MISSING",
            notes="Only in external file",
        )

        # Could be a spin-off creating a new position
        if self.identifier_tracker:
            try:
                sec_id = self.identifier_tracker.resolve_historical(ticker, "ticker")
                if sec_id:
                    info = self.identifier_tracker.get_security_info(sec_id)
                    current_ticker = info.get("ticker", "") if info else ""
                    if (
                        current_ticker
                        and current_ticker.upper() != ticker.upper()
                        and current_ticker.upper() in internal
                    ):
                        match.matched_ticker = current_ticker
                        match.notes = (
                            f"Old ticker {ticker} → now {current_ticker} "
                            f"(found in internal)"
                        )
                        match.status = "POSSIBLE"
            except Exception:
                pass

        return match

    @staticmethod
    def parse_position_csv(csv_text: str) -> dict[str, Decimal]:
        """Parse a CSV with ticker,quantity columns into a dict.

        Auto-detects common column name variations. Handles duplicates
        by summing quantities.
        """
        reader = csv.DictReader(io.StringIO(csv_text.strip()))
        positions: dict[str, Decimal] = {}

        for row in reader:
            normalized = {k.strip().lower(): v.strip() for k, v in row.items()}

            ticker = (
                normalized.get("ticker")
                or normalized.get("symbol")
                or normalized.get("sym")
                or ""
            ).upper().strip()

            qty_str = (
                normalized.get("quantity")
                or normalized.get("qty")
                or normalized.get("shares")
                or normalized.get("position")
                or "0"
            )

            if not ticker:
                continue

            try:
                qty = Decimal(qty_str.replace(",", ""))
            except Exception:
                logger.warning(f"Bad quantity for {ticker}: {qty_str}")
                continue

            # Sum duplicates
            positions[ticker] = positions.get(ticker, Decimal(0)) + qty

        return positions

    def format_report(self, results: list[ReconMatch]) -> str:
        """Format reconciliation results as a readable report."""
        lines = []
        counts = {"MATCHED": 0, "EXPLAINED": 0, "POSSIBLE": 0, "UNEXPLAINED": 0, "MISSING": 0}

        for r in results:
            counts[r.status] = counts.get(r.status, 0) + 1

        lines.append("Reconciliation Report")
        lines.append("=" * 60)
        lines.append(
            f"  MATCHED: {counts['MATCHED']}  |  EXPLAINED: {counts['EXPLAINED']}  "
            f"|  POSSIBLE: {counts['POSSIBLE']}  |  UNEXPLAINED: {counts['UNEXPLAINED']}  "
            f"|  MISSING: {counts['MISSING']}"
        )
        lines.append("")

        for r in results:
            if r.status == "MATCHED":
                lines.append(f"  [{r.status:11s}] {r.ticker:8s}  {r.internal_qty}")
            elif r.status in ("EXPLAINED", "POSSIBLE", "UNEXPLAINED"):
                int_q = r.internal_qty if r.internal_qty is not None else "N/A"
                ext_q = r.external_qty if r.external_qty is not None else "N/A"
                ticker_display = r.ticker
                if r.matched_ticker:
                    ticker_display += f" ({r.matched_ticker})"
                lines.append(
                    f"  [{r.status:11s}] {ticker_display:16s}  "
                    f"int={int_q}  ext={ext_q}"
                )
                if r.explanations:
                    lines.append(f"                 → {r.explanations[0].explanation}")
                if r.notes:
                    lines.append(f"                 Note: {r.notes}")
            elif r.status == "MISSING":
                side = "internal" if r.external_qty is None else "external"
                qty = r.internal_qty if r.external_qty is None else r.external_qty
                lines.append(
                    f"  [{r.status:11s}] {r.ticker:8s}  {qty} (only in {side})"
                )
                if r.notes:
                    lines.append(f"                 Note: {r.notes}")

        return "\n".join(lines)
