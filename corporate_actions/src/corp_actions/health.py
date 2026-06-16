"""
Health Check — test each data source and report status.

Usage:
    from corp_actions.health import HealthChecker

    checker = HealthChecker()
    report = checker.run_all()
    print(report)
"""

import logging
import os
import time
from pathlib import Path

from corp_actions.db import get_db

logger = logging.getLogger(__name__)


class HealthChecker:
    """Test each data source and report operational status."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def run_all(self) -> list[dict]:
        """Run all health checks and return results."""
        checks = []
        checks.append(self.check_sqlite())
        checks.append(self.check_yfinance())
        checks.append(self.check_edgar())
        checks.append(self.check_groq())
        return checks

    def check_sqlite(self) -> dict:
        """Check SQLite database status."""
        result = {
            "source": "SQLite",
            "status": "UNKNOWN",
            "latency_ms": 0,
            "details": {},
        }
        start = time.monotonic()
        try:
            conn = get_db(self._db_path)
            elapsed = (time.monotonic() - start) * 1000

            # Get table row counts
            tables = {}
            for table in [
                "securities",
                "corporate_actions",
                "identifier_history",
                "data_fetch_log",
            ]:
                try:
                    row = conn.execute(
                        f"SELECT COUNT(*) as c FROM {table}"
                    ).fetchone()
                    tables[table] = row["c"] if row else 0
                except Exception:
                    tables[table] = "N/A"

            # Get DB file size
            db_path = self._db_path
            if db_path is None:
                db_path = str(
                    Path.home() / ".corp-actions" / "corp_actions.db"
                )
            try:
                size_bytes = os.path.getsize(db_path)
                size_kb = size_bytes / 1024
                result["details"]["file_size"] = f"{size_kb:.1f} KB"
            except OSError:
                result["details"]["file_size"] = "N/A"

            result["status"] = "OK"
            result["latency_ms"] = round(elapsed, 1)
            result["details"]["tables"] = tables
            conn.close()

        except Exception as e:
            result["status"] = "ERROR"
            result["details"]["error"] = str(e)
            result["latency_ms"] = round(
                (time.monotonic() - start) * 1000, 1
            )

        return result

    def check_yfinance(self) -> dict:
        """Check yfinance connectivity by fetching AAPL splits."""
        result = {
            "source": "yfinance",
            "status": "UNKNOWN",
            "latency_ms": 0,
            "details": {},
        }
        start = time.monotonic()
        try:
            import yfinance as yf

            t = yf.Ticker("AAPL")
            splits = t.splits
            elapsed = (time.monotonic() - start) * 1000

            if splits is not None and len(splits) > 0:
                result["status"] = "OK"
                result["details"]["aapl_splits"] = len(splits)
            else:
                result["status"] = "DEGRADED"
                result["details"]["note"] = "No splits returned for AAPL"

            result["latency_ms"] = round(elapsed, 1)

        except ImportError:
            result["status"] = "ERROR"
            result["details"]["error"] = "yfinance not installed"
        except Exception as e:
            result["status"] = "ERROR"
            result["details"]["error"] = str(e)
            result["latency_ms"] = round(
                (time.monotonic() - start) * 1000, 1
            )

        return result

    def check_edgar(self) -> dict:
        """Check EDGAR/edgartools connectivity."""
        result = {
            "source": "SEC EDGAR",
            "status": "UNKNOWN",
            "latency_ms": 0,
            "details": {},
        }
        start = time.monotonic()
        try:
            from edgar import Company

            c = Company("AAPL")
            name = c.name if hasattr(c, "name") else str(c)
            elapsed = (time.monotonic() - start) * 1000

            result["status"] = "OK"
            result["latency_ms"] = round(elapsed, 1)
            result["details"]["company"] = name

        except ImportError:
            result["status"] = "ERROR"
            result["details"]["error"] = "edgartools not installed"
        except Exception as e:
            result["status"] = "ERROR"
            result["details"]["error"] = str(e)
            result["latency_ms"] = round(
                (time.monotonic() - start) * 1000, 1
            )

        return result

    def check_groq(self) -> dict:
        """Check Groq LLM availability."""
        result = {
            "source": "Groq LLM",
            "status": "UNKNOWN",
            "latency_ms": 0,
            "details": {},
        }

        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            result["status"] = "SKIPPED"
            result["details"]["note"] = (
                "GROQ_API_KEY not set. Using keyword fallback. "
                "Get a free key at console.groq.com"
            )
            return result

        start = time.monotonic()
        try:
            from groq import Groq

            client = Groq(api_key=api_key)
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": "Reply with just: OK"}],
                temperature=0.0,
                max_tokens=5,
            )
            elapsed = (time.monotonic() - start) * 1000

            text = response.choices[0].message.content.strip()
            result["status"] = "OK"
            result["latency_ms"] = round(elapsed, 1)
            result["details"]["model"] = "llama-3.3-70b-versatile"
            result["details"]["response"] = text

        except ImportError:
            result["status"] = "ERROR"
            result["details"]["error"] = (
                "groq package not installed. pip install corp-actions[llm]"
            )
        except Exception as e:
            result["status"] = "ERROR"
            result["details"]["error"] = str(e)
            result["latency_ms"] = round(
                (time.monotonic() - start) * 1000, 1
            )

        return result

    @staticmethod
    def format_report(checks: list[dict]) -> str:
        """Format health check results as a readable table."""
        lines = []
        lines.append("")
        lines.append("  Health Check Results")
        lines.append("  " + "=" * 56)

        for check in checks:
            icon = {
                "OK": "OK",
                "DEGRADED": "WARN",
                "ERROR": "FAIL",
                "SKIPPED": "SKIP",
            }.get(check["status"], "????")

            latency = (
                f"{check['latency_ms']}ms"
                if check["latency_ms"]
                else ""
            )

            lines.append(
                f"  [{icon:4s}] {check['source']:15s} {latency:>8s}"
            )

            details = check.get("details", {})
            if "error" in details:
                lines.append(f"         Error: {details['error']}")
            elif "note" in details:
                lines.append(f"         {details['note']}")
            elif "tables" in details:
                tables = details["tables"]
                counts = ", ".join(
                    f"{k}={v}" for k, v in tables.items()
                )
                lines.append(f"         Rows: {counts}")
                if "file_size" in details:
                    lines.append(
                        f"         DB size: {details['file_size']}"
                    )

        lines.append("")
        return "\n".join(lines)
