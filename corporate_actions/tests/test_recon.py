"""
Bulk reconciliation tests — comparing position files and explaining breaks.
"""

import os
import tempfile
import pytest
from decimal import Decimal

from corp_actions.db import get_db
from corp_actions.identifiers import IdentifierTracker
from corp_actions.impact import BreakExplainer
from corp_actions.recon import BulkRecon
from corp_actions.splits import SplitDividendDetector


@pytest.fixture
def recon():
    """BulkRecon with real split detector and identifier tracker."""
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "test_recon.db")
    detector = SplitDividendDetector(cache_ttl_hours=24, db_path=db_path)
    conn = get_db(db_path)
    tracker = IdentifierTracker(conn)
    tracker.seed_known_changes()
    explainer = BreakExplainer(detector, identifier_tracker=tracker)
    return BulkRecon(explainer, tracker)


class TestReconciliation:

    def test_matched_positions(self, recon):
        """Matching positions should be MATCHED."""
        internal = {"AAPL": Decimal("10000"), "MSFT": Decimal("5000")}
        external = {"AAPL": Decimal("10000"), "MSFT": Decimal("5000")}
        results = recon.reconcile(internal, external)

        matched = [r for r in results if r.status == "MATCHED"]
        assert len(matched) == 2

    @pytest.mark.network
    def test_split_break_explained(self, recon):
        """AAPL 40000 vs 10000 should be EXPLAINED by 4:1 split."""
        internal = {"AAPL": Decimal("40000")}
        external = {"AAPL": Decimal("10000")}
        results = recon.reconcile(internal, external)

        assert len(results) == 1
        assert results[0].status == "EXPLAINED"
        assert results[0].explanations[0].confidence >= 0.70

    def test_missing_internal_ticker(self, recon):
        """Ticker only in external should be MISSING."""
        internal = {"AAPL": Decimal("1000")}
        external = {"AAPL": Decimal("1000"), "NVDA": Decimal("500")}
        results = recon.reconcile(internal, external)

        missing = [r for r in results if r.status == "MISSING"]
        assert len(missing) == 1
        assert missing[0].ticker == "NVDA"

    def test_missing_external_ticker(self, recon):
        """Ticker only in internal should be MISSING."""
        internal = {"AAPL": Decimal("1000"), "GOOGL": Decimal("200")}
        external = {"AAPL": Decimal("1000")}
        results = recon.reconcile(internal, external)

        missing = [r for r in results if r.status == "MISSING"]
        assert len(missing) == 1
        assert missing[0].ticker == "GOOGL"

    def test_renamed_ticker_matched(self, recon):
        """Internal has FB, external has META → should detect rename."""
        internal = {"FB": Decimal("5000")}
        external = {"META": Decimal("5000")}
        results = recon.reconcile(internal, external)

        # FB should be matched to META
        fb_result = [r for r in results if r.ticker == "FB"]
        assert len(fb_result) == 1
        assert fb_result[0].matched_ticker == "META"
        assert fb_result[0].status in ("EXPLAINED", "POSSIBLE")

    def test_case_insensitive(self, recon):
        """Tickers should match case-insensitively."""
        internal = {"aapl": Decimal("1000")}
        external = {"AAPL": Decimal("1000")}
        results = recon.reconcile(internal, external)

        matched = [r for r in results if r.status == "MATCHED"]
        assert len(matched) == 1

    def test_empty_files(self, recon):
        """Empty position dicts should return empty results."""
        results = recon.reconcile({}, {})
        assert results == []


class TestCSVParsing:

    def test_standard_csv(self):
        csv = "ticker,quantity\nAAPL,10000\nMSFT,5000"
        positions = BulkRecon.parse_position_csv(csv)
        assert positions["AAPL"] == Decimal("10000")
        assert positions["MSFT"] == Decimal("5000")

    def test_alternative_columns(self):
        csv = "symbol,shares\nAAPL,10000"
        positions = BulkRecon.parse_position_csv(csv)
        assert positions["AAPL"] == Decimal("10000")

    def test_duplicate_tickers_summed(self):
        csv = "ticker,quantity\nAAPL,5000\nAAPL,3000"
        positions = BulkRecon.parse_position_csv(csv)
        assert positions["AAPL"] == Decimal("8000")

    def test_commas_in_numbers(self):
        csv = "ticker,quantity\nAAPL,\"10,000\""
        positions = BulkRecon.parse_position_csv(csv)
        assert positions["AAPL"] == Decimal("10000")

    def test_empty_csv(self):
        csv = "ticker,quantity\n"
        positions = BulkRecon.parse_position_csv(csv)
        assert positions == {}


class TestReportFormatting:

    def test_format_report(self, recon):
        internal = {"AAPL": Decimal("10000"), "MSFT": Decimal("5000")}
        external = {"AAPL": Decimal("10000"), "MSFT": Decimal("5000")}
        results = recon.reconcile(internal, external)
        report = recon.format_report(results)
        assert "MATCHED" in report
        assert "AAPL" in report
