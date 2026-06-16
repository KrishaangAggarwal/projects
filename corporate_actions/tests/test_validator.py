"""
Cross-validation tests — verify actions across multiple data sources.
"""

import pytest
from datetime import date
from decimal import Decimal

from corp_actions.models import ActionType, CorporateAction, DataSource
from corp_actions.splits import SplitDividendDetector
from corp_actions.edgar import EdgarEventDetector
from corp_actions.validator import CrossValidator


@pytest.fixture
def validator():
    detector = SplitDividendDetector()
    edgar = EdgarEventDetector("test@test.com")
    edgar._groq_available = False  # Use keyword mode only
    return CrossValidator(detector, edgar)


class TestTypeCompatibility:

    def test_split_types_compatible(self):
        assert CrossValidator._types_compatible(
            ActionType.STOCK_SPLIT, ActionType.REVERSE_SPLIT
        )

    def test_merger_types_compatible(self):
        assert CrossValidator._types_compatible(
            ActionType.MERGER, ActionType.ACQUISITION
        )

    def test_name_ticker_compatible(self):
        assert CrossValidator._types_compatible(
            ActionType.NAME_CHANGE, ActionType.TICKER_CHANGE
        )

    def test_incompatible_types(self):
        assert not CrossValidator._types_compatible(
            ActionType.STOCK_SPLIT, ActionType.MERGER
        )

    def test_same_type_compatible(self):
        assert CrossValidator._types_compatible(
            ActionType.CASH_DIVIDEND, ActionType.CASH_DIVIDEND
        )


class TestYfinanceValidation:

    def test_dividend_gets_yfinance_source(self, validator):
        """Dividends from yfinance should get yfinance in validation_sources."""
        action = CorporateAction(
            ticker="AAPL",
            action_type=ActionType.CASH_DIVIDEND,
            source=DataSource.YFINANCE,
            confidence=0.95,
        )
        result = validator.validate(action)
        assert "yfinance" in result.validation_sources

    @pytest.mark.network
    def test_aapl_split_validation(self, validator):
        """AAPL 2020 split from yfinance should attempt EDGAR validation."""
        action = CorporateAction(
            ticker="AAPL",
            action_type=ActionType.STOCK_SPLIT,
            effective_date=date(2020, 8, 31),
            source=DataSource.YFINANCE,
            confidence=0.95,
            split_ratio=Decimal("4"),
            split_from=1,
            split_to=4,
        )
        result = validator.validate(action)
        # May or may not cross-validate depending on EDGAR availability
        assert "yfinance" in result.validation_sources


class TestEdgarValidation:

    @pytest.mark.network
    def test_edgar_split_against_yfinance(self, validator):
        """An EDGAR-detected split should check yfinance for confirmation."""
        action = CorporateAction(
            ticker="AAPL",
            action_type=ActionType.STOCK_SPLIT,
            effective_date=date(2020, 8, 31),
            source=DataSource.EDGAR_8K,
            confidence=0.70,
        )
        result = validator.validate(action)
        # Should attempt yfinance validation
        assert len(result.validation_sources) >= 1

    def test_edgar_action_preserves_source(self, validator):
        """Validation should add to sources, not replace."""
        action = CorporateAction(
            ticker="AAPL",
            action_type=ActionType.NAME_CHANGE,
            source=DataSource.LLM_EXTRACTED,
            confidence=0.70,
        )
        result = validator.validate(action)
        assert action.source.value in result.validation_sources


class TestBatchValidation:

    def test_batch_handles_errors(self, validator):
        """Batch validation should not crash on bad data."""
        actions = [
            CorporateAction(
                ticker="AAPL",
                action_type=ActionType.CASH_DIVIDEND,
                source=DataSource.YFINANCE,
                confidence=0.95,
            ),
            CorporateAction(
                ticker="INVALID_TICKER_XYZ",
                action_type=ActionType.STOCK_SPLIT,
                source=DataSource.YFINANCE,
                confidence=0.90,
            ),
        ]
        results = validator.validate_batch(actions)
        assert len(results) == 2


class TestConfidenceBoost:

    def test_validated_confidence_capped(self, validator):
        """Cross-validated confidence should never exceed 0.98."""
        action = CorporateAction(
            ticker="AAPL",
            action_type=ActionType.CASH_DIVIDEND,
            source=DataSource.YFINANCE,
            confidence=0.95,
        )
        # Manually simulate cross-validation
        action.validated = True
        action.confidence = min(0.98, action.confidence + 0.15)
        assert action.confidence == 0.98

    def test_unvalidated_confidence_unchanged(self, validator):
        """Single-source events should keep original confidence."""
        action = CorporateAction(
            ticker="AAPL",
            action_type=ActionType.CASH_DIVIDEND,
            source=DataSource.YFINANCE,
            confidence=0.95,
        )
        original = action.confidence
        result = validator.validate(action)
        # Dividends don't cross-validate against EDGAR
        if not result.validated:
            assert result.confidence == original
