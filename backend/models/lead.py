"""
models/lead.py
Pydantic schemas for Lead request/response shapes.
"""

import json
from typing import Any, Optional
from pydantic import BaseModel, field_validator


class LeadSummary(BaseModel):
    """Lightweight lead row — used in the list endpoint."""
    id: str
    retailer_id: str
    retailer_name: Optional[str] = None
    customer_name: Optional[str] = None
    agent_id: Optional[str] = None
    agent_name: Optional[str] = None
    call_date: str
    gate_status: str
    recording_url: Optional[str] = None
    has_transcript: bool = False


class LeadDetail(BaseModel):
    """Full lead detail — used in the single lead endpoint."""
    id: str
    retailer_id: str
    retailer_name: Optional[str] = None
    agent_id: Optional[str] = None
    agent_name: Optional[str] = None
    call_date: str
    crm_fields: dict[str, Any]
    rate_card: Optional[dict[str, Any]] = None
    recording_url: Optional[str] = None
    gate_status: str
    created_at: str

    @field_validator("crm_fields", mode="before")
    @classmethod
    def parse_crm_fields(cls, v: Any) -> dict:
        """SQLite stores JSON as text — parse it back to dict."""
        if isinstance(v, str):
            return json.loads(v)
        return v

    @field_validator("rate_card", mode="before")
    @classmethod
    def parse_rate_card(cls, v: Any) -> Optional[dict]:
        if isinstance(v, str):
            return json.loads(v)
        return v
