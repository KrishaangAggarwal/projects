"""
Data models for the Corporate Actions Intelligence Engine.

All models are plain dataclasses — no ORM, no dependencies.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4


class ActionType(Enum):
    """Every type of corporate action the engine can detect."""
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
    """Where the corporate action data came from."""
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

    # Key dates
    announcement_date: Optional[date] = None
    ex_date: Optional[date] = None
    record_date: Optional[date] = None
    effective_date: Optional[date] = None
    pay_date: Optional[date] = None

    # Split data
    split_ratio: Optional[Decimal] = None   # e.g. 4.0 for 4:1
    split_from: Optional[int] = None        # e.g. 1
    split_to: Optional[int] = None          # e.g. 4

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

    # Source tracking
    source: DataSource = DataSource.YFINANCE
    source_url: Optional[str] = None
    source_filing_id: Optional[str] = None
    confidence: float = 1.0

    # Raw data for debugging
    raw_data: dict = field(default_factory=dict)


@dataclass
class PositionImpact:
    """The calculated impact of a corporate action on a position."""
    action: CorporateAction

    # Before
    original_quantity: Decimal = Decimal(0)
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
