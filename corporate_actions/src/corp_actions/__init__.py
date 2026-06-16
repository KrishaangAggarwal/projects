"""Corporate Actions Intelligence Engine — free, open-source corporate actions data."""

from corp_actions.models import (
    ActionType,
    CorporateAction,
    DataSource,
    PositionImpact,
    BreakExplanation,
    ReplayResult,
    ReconMatch,
)
from corp_actions.engine import CorporateActionsEngine

__version__ = "0.1.0"
__all__ = [
    "CorporateActionsEngine",
    "ActionType",
    "CorporateAction",
    "DataSource",
    "PositionImpact",
    "BreakExplanation",
    "ReplayResult",
    "ReconMatch",
]
