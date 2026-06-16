"""
EDGAR event detection tests.

Tests keyword-based classification (no LLM needed) and
optionally LLM classification if GROQ_API_KEY is set.
"""

import os
import pytest
from datetime import date
from unittest.mock import patch

from corp_actions.edgar import EdgarEventDetector
from corp_actions.models import ActionType, DataSource


@pytest.fixture
def detector():
    identity = os.environ.get("EDGAR_IDENTITY", "test@test.com")
    return EdgarEventDetector(identity)


class TestKeywordClassification:
    """Test keyword-based 8-K classification (no LLM, no network)."""

    def _make_detector_no_llm(self):
        """Detector with Groq disabled."""
        d = EdgarEventDetector("test@test.com")
        d._groq_available = False
        return d

    def test_name_change_keywords(self):
        d = self._make_detector_no_llm()
        text = (
            "The company amended its certificate of incorporation "
            "to change the name from Acme Corp to NewCo Inc. "
            "The name change was effective October 1, 2024."
        )
        action = d._classify_with_keywords(
            "ACME", text, "Item 5.03", date(2024, 10, 1), "0001-24-000001"
        )
        assert action is not None
        assert action.action_type == ActionType.NAME_CHANGE
        assert action.confidence == 0.60

    def test_merger_keywords(self):
        d = self._make_detector_no_llm()
        text = (
            "On January 15, 2025, the Company completed the acquisition "
            "of TargetCo pursuant to the merger agreement dated November 2024."
        )
        action = d._classify_with_keywords(
            "BUYER", text, "Item 2.01", date(2025, 1, 15), "0001-25-000001"
        )
        assert action is not None
        assert action.action_type == ActionType.MERGER

    def test_spinoff_keywords(self):
        d = self._make_detector_no_llm()
        text = (
            "The board approved a spin-off of the infrastructure division. "
            "Shareholders will receive shares in the new entity."
        )
        action = d._classify_with_keywords(
            "PARENT", text, "Item 8.01", date(2024, 6, 1), "0001-24-000002"
        )
        assert action is not None
        assert action.action_type == ActionType.SPIN_OFF

    def test_ticker_change_keywords(self):
        d = self._make_detector_no_llm()
        text = (
            "Effective March 1, the company will trade under a new ticker "
            "symbol on the NYSE."
        )
        action = d._classify_with_keywords(
            "OLD", text, "Item 8.01", date(2024, 3, 1), "0001-24-000003"
        )
        assert action is not None
        assert action.action_type == ActionType.TICKER_CHANGE

    def test_irrelevant_item_returns_none(self):
        d = self._make_detector_no_llm()
        text = "The quarterly earnings report showed revenue growth of 15%."
        action = d._classify_with_keywords(
            "XYZ", text, "Item 2.02", date(2024, 1, 1), "0001-24-000004"
        )
        assert action is None

    def test_no_matching_keywords_returns_none(self):
        d = self._make_detector_no_llm()
        text = "The company appointed a new Chief Financial Officer."
        action = d._classify_with_keywords(
            "XYZ", text, "Item 5.03", date(2024, 1, 1), "0001-24-000005"
        )
        assert action is None


class TestNameChangeExtraction:
    """Test regex-based name change extraction."""

    def test_extract_name_from_to(self):
        d = EdgarEventDetector("test@test.com")
        text = 'The company changed its name from "Facebook, Inc." to "Meta Platforms, Inc."'
        old, new = d._extract_name_change(text)
        assert old == "Facebook, Inc."
        assert new == "Meta Platforms, Inc."

    def test_extract_name_no_quotes(self):
        d = EdgarEventDetector("test@test.com")
        text = "The registrant changed its name from Acme Corp to NewCo Inc effective today."
        old, new = d._extract_name_change(text)
        assert old == "Acme Corp"
        assert new == "NewCo Inc"

    def test_no_name_change_in_text(self):
        d = EdgarEventDetector("test@test.com")
        text = "The company reported strong quarterly earnings."
        old, new = d._extract_name_change(text)
        assert old is None
        assert new is None


class TestFilingTextExtraction:
    """Test that _extract_filing_text handles different edgartools objects."""

    def test_callable_text(self):
        d = EdgarEventDetector("test@test.com")

        class MockReport:
            def text(self):
                return "This is the 8-K filing text content."

        result = d._extract_filing_text(MockReport())
        assert "8-K filing text content" in result

    def test_text_truncation(self):
        d = EdgarEventDetector("test@test.com")

        class MockReport:
            def text(self):
                return "x" * 10000

        result = d._extract_filing_text(MockReport())
        assert len(result) == 5000

    def test_no_text_method(self):
        d = EdgarEventDetector("test@test.com")

        class MockReport:
            pass

        result = d._extract_filing_text(MockReport())
        assert result == ""


@pytest.mark.network
class TestEdgarLive:
    """Live EDGAR tests (require network + EDGAR_IDENTITY)."""

    def test_meta_name_change_detected(self, detector):
        """The FB->META name change (2021-10-28) should be detectable."""
        events = detector.get_recent_events("META", days_back=1825)

        name_changes = [
            e for e in events if e.action_type == ActionType.NAME_CHANGE
        ]

        # Should find at least one name change
        assert len(name_changes) >= 1

        # The most relevant one should reference Meta or Facebook
        found_fb_meta = any(
            (e.old_value and "facebook" in e.old_value.lower())
            or (e.new_value and "meta" in e.new_value.lower())
            for e in name_changes
        )
        assert found_fb_meta, (
            f"Expected FB->META name change, got: "
            f"{[(e.old_value, e.new_value) for e in name_changes]}"
        )

    def test_recent_meta_events_no_crash(self, detector):
        """Recent META filings should be parseable without errors."""
        events = detector.get_recent_events("META", days_back=90)
        assert isinstance(events, list)

    def test_invalid_ticker_graceful(self, detector):
        """Invalid ticker should return empty, not crash."""
        events = detector.get_recent_events("ZZZZZNOTREAL", days_back=30)
        assert events == []
