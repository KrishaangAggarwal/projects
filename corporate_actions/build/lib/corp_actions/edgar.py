"""
Module 2: Merger & Acquisition Detector — powered by SEC EDGAR + optional Groq LLM.

COST: $0. edgartools is MIT-licensed, SEC EDGAR is free government API.
LLM (Groq/Llama) is OPTIONAL — keyword fallback works without any API key.
"""

import json
import logging
import os
from datetime import date, timedelta
from decimal import Decimal

from corp_actions.models import ActionType, CorporateAction, DataSource

logger = logging.getLogger(__name__)


class EdgarEventDetector:
    """
    Detect corporate actions from SEC EDGAR 8-K filings.

    Works in two modes:
    1. With GROQ_API_KEY: LLM-powered extraction (~70-80% accuracy)
    2. Without GROQ_API_KEY: Keyword-based classification (~50-60% accuracy)
    """

    # 8-K items that indicate corporate actions
    RELEVANT_ITEMS = {
        "1.01": "material_agreement",
        "2.01": "acquisition_completion",
        "3.03": "rights_modification",
        "5.01": "change_of_control",
        "5.03": "articles_amendment",
        "8.01": "other_events",
    }

    def __init__(self, identity_email: str):
        self._identity_email = identity_email
        try:
            from edgar import set_identity
            set_identity(identity_email)
        except Exception as e:
            logger.warning(f"Failed to set EDGAR identity: {e}")

        self._groq_available = bool(os.environ.get("GROQ_API_KEY"))
        self.groq_client = None  # Lazy init

    def get_recent_events(
        self, ticker: str, days_back: int = 90
    ) -> list[CorporateAction]:
        """
        Get corporate action events from recent 8-K filings.

        Uses edgartools to fetch, then LLM or keywords to classify.
        """
        try:
            from edgar import Company
            company = Company(ticker)
            filings = company.get_filings(form="8-K")
        except Exception as e:
            logger.error(f"EDGAR error for {ticker}: {e}")
            return []

        results = []
        cutoff = date.today() - timedelta(days=days_back)

        # Scale scan depth with lookback window.
        # Large-cap companies file 30-40+ 8-Ks per year.
        max_filings = min(max(20, (days_back // 365 + 1) * 40), 500)

        for filing in filings[:max_filings]:
            try:
                filing_date = filing.filing_date
                if hasattr(filing_date, "date"):
                    filing_date = filing_date.date()

                if filing_date < cutoff:
                    break

                # Parse the 8-K
                eightk = filing.obj()
                items = eightk.items if hasattr(eightk, "items") else []

                # Check if any items are relevant to corporate actions
                has_relevant = any(
                    any(key in str(item) for key in self.RELEVANT_ITEMS)
                    for item in items
                )
                if not has_relevant:
                    continue

                # edgartools 8-K items are plain strings (e.g. "Item 5.03").
                # The actual text is in obj.text() (the full document).
                text = self._extract_filing_text(eightk)
                if not text:
                    continue

                # Build a combined item string for matching
                item_str = " ".join(str(item) for item in items)

                if self._groq_available:
                    action = self._classify_with_llm(
                        ticker, text, item_str, filing_date,
                        filing.accession_no,
                    )
                else:
                    action = self._classify_with_keywords(
                        ticker, text, item_str, filing_date,
                        filing.accession_no,
                    )
                if action:
                    results.append(action)

            except Exception as e:
                logger.warning(f"Error parsing 8-K for {ticker}: {e}")
                continue

        return results

    def _extract_filing_text(self, eightk) -> str:
        """Extract text content from a CurrentReport (8-K) object.

        edgartools 5.x: obj.text() is a method returning the full document text.
        We grab up to 5000 chars for classification.
        """
        try:
            if callable(getattr(eightk, "text", None)):
                return eightk.text()[:5000]
            elif hasattr(eightk, "text"):
                return str(eightk.text)[:5000]
        except Exception as e:
            logger.debug(f"Failed to get text from 8-K: {e}")

        # Fallback: try .document
        try:
            if hasattr(eightk, "document"):
                doc = eightk.document
                if hasattr(doc, "text"):
                    t = doc.text() if callable(doc.text) else doc.text
                    return str(t)[:5000]
        except Exception:
            pass

        return ""

    def _classify_with_keywords(
        self,
        ticker: str,
        text: str,
        item_str: str,
        filing_date: date,
        accession_no: str,
    ) -> CorporateAction | None:
        """
        Classify 8-K text using keyword matching — NO LLM, NO COST.

        ~50-60% accuracy. Useful as a fallback.
        """
        text_lower = text.lower()

        # Name change detection (high accuracy with keywords)
        if "5.03" in item_str:
            name_signals = [
                "name change", "changed its name", "change of name",
                "amended its certificate", "amended its articles",
                "new name", "change the name",
            ]
            if any(signal in text_lower for signal in name_signals):
                # Try to extract old/new names from text
                old_name, new_name = self._extract_name_change(text)
                return CorporateAction(
                    ticker=ticker,
                    action_type=ActionType.NAME_CHANGE,
                    announcement_date=filing_date,
                    effective_date=filing_date,
                    old_value=old_name,
                    new_value=new_name,
                    source=DataSource.EDGAR_8K,
                    source_filing_id=accession_no,
                    confidence=0.60,
                    raw_data={"text_snippet": text[:500], "method": "keyword"},
                )

        # Merger/acquisition detection
        if any(item in item_str for item in ["1.01", "2.01", "5.01"]):
            merger_signals = [
                "merger agreement", "plan of merger", "acquisition",
                "acquired all", "completed the acquisition",
                "completion of", "business combination",
            ]
            if any(signal in text_lower for signal in merger_signals):
                return CorporateAction(
                    ticker=ticker,
                    action_type=ActionType.MERGER,
                    announcement_date=filing_date,
                    source=DataSource.EDGAR_8K,
                    source_filing_id=accession_no,
                    confidence=0.50,
                    raw_data={"text_snippet": text[:500], "method": "keyword"},
                )

        # Spin-off detection
        spinoff_signals = [
            "spin-off", "spinoff", "distribution of shares",
            "separation", "distribute to shareholders",
        ]
        if any(signal in text_lower for signal in spinoff_signals):
            return CorporateAction(
                ticker=ticker,
                action_type=ActionType.SPIN_OFF,
                announcement_date=filing_date,
                source=DataSource.EDGAR_8K,
                source_filing_id=accession_no,
                confidence=0.45,
                raw_data={"text_snippet": text[:500], "method": "keyword"},
            )

        # Ticker change detection
        ticker_signals = [
            "ticker symbol", "trading symbol", "new ticker",
            "symbol change", "will trade under",
        ]
        if any(signal in text_lower for signal in ticker_signals):
            return CorporateAction(
                ticker=ticker,
                action_type=ActionType.TICKER_CHANGE,
                announcement_date=filing_date,
                source=DataSource.EDGAR_8K,
                source_filing_id=accession_no,
                confidence=0.55,
                raw_data={"text_snippet": text[:500], "method": "keyword"},
            )

        return None

    def _extract_name_change(self, text: str) -> tuple[str | None, str | None]:
        """Best-effort extraction of old/new company names from 8-K text."""
        import re

        # Pattern 1: quoted names — "from "Old Name" to "New Name""
        m = re.search(
            r'(?:changed?|change)\s+(?:its\s+)?name\s+from\s+"([^"]+)"\s+to\s+"([^"]+)"',
            text, re.IGNORECASE,
        )
        if m:
            return m.group(1).strip(), m.group(2).strip()

        # Pattern 2: unquoted — "from Old Name to New Name" (stop at sentence-ending punctuation)
        m = re.search(
            r'(?:changed?|change)\s+(?:its\s+)?name\s+from\s+(.+?)\s+to\s+(.+?)(?:\s*[.;,]|\s+effective|\s+on\s|\s+as\s+of|\s*$)',
            text, re.IGNORECASE,
        )
        if m:
            return m.group(1).strip(), m.group(2).strip()

        # Pattern 3: "name of the Company from X to Y"
        m = re.search(
            r'name\s+of\s+the\s+\w+\s+from\s+"([^"]+)"\s+to\s+"([^"]+)"',
            text, re.IGNORECASE,
        )
        if m:
            return m.group(1).strip(), m.group(2).strip()

        m = re.search(
            r'name\s+of\s+the\s+\w+\s+from\s+(.+?)\s+to\s+(.+?)(?:\s*[.;,]|\s+effective|\s+on\s|\s+as\s+of|\s*$)',
            text, re.IGNORECASE,
        )
        if m:
            return m.group(1).strip(), m.group(2).strip()

        return None, None

    def _classify_with_llm(
        self,
        ticker: str,
        text: str,
        item_str: str,
        filing_date: date,
        accession_no: str,
    ) -> CorporateAction | None:
        """
        Use Groq/Llama to classify an 8-K filing.

        COST: $0 — Groq free tier (Llama 3.3 70B, ~30 req/min).
        Falls back to keyword classifier on failure.
        """
        if self.groq_client is None:
            try:
                from groq import Groq
                self.groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
            except ImportError:
                logger.warning("groq package not installed. pip install corp-actions[llm]")
                return self._classify_with_keywords(
                    ticker, text, item_str, filing_date, accession_no
                )

        prompt = f"""Analyze this SEC 8-K filing excerpt for {ticker} (filed {filing_date}).
8-K Items reported: {item_str}

Text:
{text[:3000]}

Is this a corporate action? If yes, classify it as ONE of:
- merger (company being acquired)
- acquisition (company acquiring another)
- spin_off (creating a new separate company)
- name_change (company changing its legal name)
- ticker_change (stock ticker symbol changing)
- stock_split (stock split or reverse split)
- special_dividend (one-time large dividend)
- delisting (security being delisted)
- none (not a corporate action)

If it IS a corporate action, extract:
- action_type: (from list above)
- effective_date: (YYYY-MM-DD if mentioned, null if not)
- description: (one sentence summary)
- For mergers: acquirer_name, conversion_ratio (shares of acquirer per share), cash_per_share
- For spin_offs: new_company_name, distribution_ratio
- For name_changes: old_name, new_name
- For ticker_changes: old_ticker, new_ticker

Return ONLY JSON. If not a corporate action, return: {{"action_type": "none"}}"""

        try:
            response = self.groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=500,
                response_format={"type": "json_object"},
            )

            result = json.loads(response.choices[0].message.content)
            logger.debug(f"LLM result for {ticker}: {result}")

            if result.get("action_type") == "none":
                return None

            return self._build_action_from_llm(ticker, result, filing_date, accession_no)

        except Exception as e:
            logger.error(f"LLM classification error: {e}")
            return self._classify_with_keywords(
                ticker, text, item_str, filing_date, accession_no
            )

    def _build_action_from_llm(
        self,
        ticker: str,
        llm_result: dict,
        filing_date: date,
        accession_no: str,
    ) -> CorporateAction | None:
        """Build a CorporateAction from LLM extraction results."""
        action_type_map = {
            "merger": ActionType.MERGER,
            "acquisition": ActionType.ACQUISITION,
            "spin_off": ActionType.SPIN_OFF,
            "name_change": ActionType.NAME_CHANGE,
            "ticker_change": ActionType.TICKER_CHANGE,
            "stock_split": ActionType.STOCK_SPLIT,
            "special_dividend": ActionType.SPECIAL_DIVIDEND,
            "delisting": ActionType.DELISTING,
        }

        action_type_str = llm_result.get("action_type", "none")
        if action_type_str not in action_type_map:
            return None

        action = CorporateAction(
            ticker=ticker,
            action_type=action_type_map[action_type_str],
            announcement_date=filing_date,
            source=DataSource.LLM_EXTRACTED,
            source_filing_id=accession_no,
            confidence=0.70,
            raw_data=llm_result,
        )

        # Parse effective date
        eff_str = llm_result.get("effective_date")
        if eff_str and eff_str != "null":
            try:
                action.effective_date = date.fromisoformat(eff_str)
            except ValueError:
                pass

        # Merger-specific fields
        if action_type_str in ("merger", "acquisition"):
            action.acquirer_ticker = llm_result.get("acquirer_name")
            ratio = llm_result.get("conversion_ratio")
            if ratio:
                try:
                    action.conversion_ratio = Decimal(str(ratio))
                except (ValueError, TypeError, ArithmeticError):
                    pass
            cash = llm_result.get("cash_per_share")
            if cash:
                try:
                    action.cash_per_share = Decimal(str(cash))
                except (ValueError, TypeError, ArithmeticError):
                    pass

        # Name change fields
        if action_type_str == "name_change":
            action.old_value = llm_result.get("old_name")
            action.new_value = llm_result.get("new_name")

        # Ticker change fields
        if action_type_str == "ticker_change":
            action.old_value = llm_result.get("old_ticker")
            action.new_value = llm_result.get("new_ticker")

        # Spin-off fields
        if action_type_str == "spin_off":
            action.spinoff_ticker = llm_result.get("new_company_name")
            ratio = llm_result.get("distribution_ratio")
            if ratio:
                try:
                    action.spinoff_ratio = Decimal(str(ratio))
                except (ValueError, TypeError, ArithmeticError):
                    pass

        return action
