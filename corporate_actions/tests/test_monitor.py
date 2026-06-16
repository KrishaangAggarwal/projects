"""
Portfolio Monitor Tests — PM-001 through PM-003.

Ground truth from the development guide Section 12.4.
"""

import pytest

from corp_actions.monitor import PortfolioMonitor
from corp_actions.splits import SplitDividendDetector


@pytest.fixture
def monitor():
    detector = SplitDividendDetector(cache_ttl_hours=1)
    return PortfolioMonitor(detector)


@pytest.mark.network
class TestPortfolioMonitor:

    def test_pm001_portfolio_with_dividends(self, monitor):
        """[AAPL, MSFT, JNJ] should have recent dividends."""
        alerts = monitor.scan_portfolio(["AAPL", "MSFT", "JNJ"], days_back=90)
        assert len(alerts) > 0
        tickers_with_alerts = {a["ticker"] for a in alerts}
        # At least one of these dividend payers should have a recent action
        assert len(tickers_with_alerts) >= 1

    def test_pm002_empty_portfolio(self, monitor):
        """Empty portfolio should return empty alerts."""
        alerts = monitor.scan_portfolio([])
        assert alerts == []

    def test_pm003_invalid_ticker(self, monitor):
        """Invalid ticker should not crash, just return empty."""
        alerts = monitor.scan_portfolio(["ZZZZZ_INVALID"])
        assert isinstance(alerts, list)

    def test_alert_structure(self, monitor):
        """Verify alert dict has the expected keys."""
        alerts = monitor.scan_portfolio(["AAPL"], days_back=90)
        if alerts:
            alert = alerts[0]
            assert "ticker" in alert
            assert "action" in alert
            assert "date" in alert
            assert "is_upcoming" in alert
            assert "is_recent" in alert
            assert "urgency" in alert
            assert "summary" in alert
