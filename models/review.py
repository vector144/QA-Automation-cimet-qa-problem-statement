"""
models/review.py
Pydantic models for QA Reviewer Workflow and Overrides.
"""

from typing import Optional
from pydantic import BaseModel, Field


class QAOverrideRequest(BaseModel):
    """Payload submitted by a QA Auditor to override a check outcome or lead gate decision."""
    reviewer_id: str = Field(..., min_length=1, description="Unique ID of QA Auditor")
    reviewer_name: Optional[str] = "QA Auditor"
    check_id: Optional[str] = None
    new_status: str = Field(..., min_length=1, description="New status: PASS or FAIL")
    gate_status_override: Optional[str] = None   # "PASSED" | "FAILED" | "NEEDS_REVIEW"
    justification: str = Field(..., min_length=5, description="Mandatory detailed justification for audit trail")


class QAOverrideRecord(BaseModel):
    id: str
    lead_id: str
    check_id: Optional[str] = None
    reviewer_id: str
    reviewer_name: Optional[str] = None
    previous_status: str
    new_status: str
    justification: str
    created_at: str
