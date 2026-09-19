"""
models/scoring.py
Pydantic models for scoring runs and check evaluation results.
"""

from typing import Optional
from pydantic import BaseModel
from services.check_library import CheckType


class CheckEvaluationResult(BaseModel):
    """Result of running a single compliance check against a transcript."""
    check_id: str
    check_name: str
    check_type: CheckType
    is_critical: bool
    blocks_sale: bool
    status: str              # "PASS" | "FAIL"
    confidence: float = 1.0  # 0.0 to 1.0
    agent_said: Optional[str] = None
    expected_value: Optional[str] = None
    transcript_turn: Optional[int] = None
    transcript_line: Optional[str] = None
    timestamp_ms: Optional[int] = None
    reason: str
    check_library_version: Optional[str] = None


class ScoreRunResponse(BaseModel):
    """Aggregated score run outcome with gate determination and check breakdown."""
    run_id: str
    lead_id: str
    check_library_id: str
    check_library_version: str
    score: float
    overall_status: str      # "PASS" | "FAIL" | "NEEDS_REVIEW"
    gate_decision: str       # "PASSED" | "FAILED" | "NEEDS_REVIEW"
    critical_failed_count: int
    total_checks: int
    passed_checks: int
    check_results: list[CheckEvaluationResult]
    run_at: str
