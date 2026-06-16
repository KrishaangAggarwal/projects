"""
Health check tests.
"""

import pytest
from corp_actions.health import HealthChecker


class TestHealthCheck:

    def test_sqlite_check(self):
        """SQLite check should always work."""
        checker = HealthChecker()
        result = checker.check_sqlite()
        assert result["source"] == "SQLite"
        assert result["status"] == "OK"
        assert "tables" in result["details"]

    @pytest.mark.network
    def test_yfinance_check(self):
        """yfinance check should succeed with network."""
        checker = HealthChecker()
        result = checker.check_yfinance()
        assert result["source"] == "yfinance"
        assert result["status"] == "OK"
        assert result["latency_ms"] > 0

    @pytest.mark.network
    def test_edgar_check(self):
        """EDGAR check should succeed with network."""
        checker = HealthChecker()
        result = checker.check_edgar()
        assert result["source"] == "SEC EDGAR"
        assert result["status"] == "OK"

    def test_groq_check_skipped(self):
        """Groq check should be SKIPPED without API key."""
        import os
        original = os.environ.pop("GROQ_API_KEY", None)
        try:
            checker = HealthChecker()
            result = checker.check_groq()
            assert result["status"] == "SKIPPED"
        finally:
            if original:
                os.environ["GROQ_API_KEY"] = original

    def test_run_all(self):
        """run_all should return a list of checks."""
        checker = HealthChecker()
        results = checker.run_all()
        assert len(results) == 4
        sources = {r["source"] for r in results}
        assert "SQLite" in sources
        assert "yfinance" in sources

    def test_format_report(self):
        """Report formatting should not crash."""
        checker = HealthChecker()
        results = checker.run_all()
        report = HealthChecker.format_report(results)
        assert "Health Check" in report
        assert "SQLite" in report
