"""
services/check_library.py
Loads check library JSON files and resolves the correct version for a given
retailer + call date (always scores against rules that were live on the call date).
"""

import json
from enum import Enum
from pathlib import Path
from typing import Optional
from pydantic import BaseModel

# Absolute path to the data/check-library directory
_LIBRARY_DIR = Path(__file__).resolve().parent.parent / "data" / "check-library"


class CheckType(str, Enum):
    VERBATIM = "VERBATIM"
    FACTUAL = "FACTUAL"
    BEHAVIOUR = "BEHAVIOUR"


class Check(BaseModel):
    id: str
    name: str
    type: CheckType
    is_critical: bool
    blocks_sale: bool

    # VERBATIM fields
    script: Optional[str] = None
    fuzzy_threshold: Optional[float] = 0.80

    # FACTUAL fields
    crm_field: Optional[str] = None
    crm_field_type: Optional[str] = None   # "email" | "numeric" | "string" | "date"
    extraction_hint: Optional[str] = None

    # BEHAVIOUR fields
    threshold_seconds: Optional[int] = None


class CheckLibrary(BaseModel):
    id: str
    retailer_id: str
    effective_from: str          # ISO date string "YYYY-MM-DD"
    checks: list[Check]

    # ── Convenience properties ────────────────────────────────────────────────

    @property
    def verbatim_checks(self) -> list[Check]:
        return [c for c in self.checks if c.type == CheckType.VERBATIM]

    @property
    def factual_checks(self) -> list[Check]:
        return [c for c in self.checks if c.type == CheckType.FACTUAL]

    @property
    def behaviour_checks(self) -> list[Check]:
        return [c for c in self.checks if c.type == CheckType.BEHAVIOUR]

    @property
    def critical_checks(self) -> list[Check]:
        return [c for c in self.checks if c.is_critical]


def load_library(library_id: str) -> CheckLibrary:
    """
    Load a check library by its exact ID (e.g. "broadband-v1").
    Raises FileNotFoundError if the file does not exist.
    """
    path = _LIBRARY_DIR / f"{library_id}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"Check library '{library_id}' not found at {path}"
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    return CheckLibrary(**data)


def resolve_library(retailer_id: str, call_date: str) -> CheckLibrary:
    """
    Find the most recent check library for a retailer that was effective
    on or before the given call_date (ISO format "YYYY-MM-DD").

    This ensures scoring always uses the rules that were live on the call date,
    not today's version.

    Raises ValueError if no matching library is found.
    """
    candidates: list[CheckLibrary] = []

    for path in _LIBRARY_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            lib = CheckLibrary(**data)
            if lib.retailer_id == retailer_id and lib.effective_from <= call_date:
                candidates.append(lib)
        except Exception:
            continue  # skip malformed files

    if not candidates:
        raise ValueError(
            f"No check library found for retailer '{retailer_id}' "
            f"effective on or before '{call_date}'"
        )

    # Return the one with the latest effective_from date
    return max(candidates, key=lambda lib: lib.effective_from)
