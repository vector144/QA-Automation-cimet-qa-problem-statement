"""
routers/leads.py
GET /api/leads         — list leads (with optional filters)
GET /api/leads/{id}    — single lead detail
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
import aiosqlite

from database.connection import get_db_connection
from models.lead import LeadDetail, LeadSummary

router = APIRouter()


@router.get("", response_model=list[LeadSummary])
async def list_leads(
    gate_status: Optional[str] = None,
    retailer_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    db: aiosqlite.Connection = Depends(get_db_connection),
):
    """
    Return all leads, optionally filtered by gate_status / retailer_id / agent_id.
    Also returns has_transcript flag per lead.
    """
    query = """
        SELECT 
            l.id, l.retailer_id, l.retailer_name,
            l.agent_id, l.agent_name, l.call_date,
            l.gate_status, l.recording_url, l.crm_fields,
            CASE WHEN t.lead_id IS NOT NULL THEN 1 ELSE 0 END AS has_transcript
        FROM leads l
        LEFT JOIN transcripts t ON t.lead_id = l.id
        WHERE 1=1
    """
    params: list = []

    if gate_status:
        query += " AND l.gate_status = ?"
        params.append(gate_status)
    if retailer_id:
        query += " AND l.retailer_id = ?"
        params.append(retailer_id)
    if agent_id:
        query += " AND l.agent_id = ?"
        params.append(agent_id)

    query += " ORDER BY l.created_at DESC"

    cursor = await db.execute(query, params)
    rows = await cursor.fetchall()

    import json

    def _extract_customer_name(crm_raw: str | None) -> str | None:
        if not crm_raw:
            return None
        try:
            fields = json.loads(crm_raw) if isinstance(crm_raw, str) else crm_raw
            return fields.get("customer_full_name") or fields.get("customer_name")
        except Exception:
            return None

    return [
        LeadSummary(
            id=row["id"],
            retailer_id=row["retailer_id"],
            retailer_name=row["retailer_name"],
            customer_name=_extract_customer_name(row["crm_fields"]),
            agent_id=row["agent_id"],
            agent_name=row["agent_name"],
            call_date=row["call_date"],
            gate_status=row["gate_status"],
            recording_url=row["recording_url"],
            has_transcript=bool(row["has_transcript"]),
        )
        for row in rows
    ]


@router.get("/{lead_id}", response_model=LeadDetail)
async def get_lead(
    lead_id: str,
    db: aiosqlite.Connection = Depends(get_db_connection),
):
    """Return full lead detail including CRM fields and rate card."""
    cursor = await db.execute(
        """SELECT id, retailer_id, retailer_name, agent_id, agent_name,
                  call_date, crm_fields, rate_card, recording_url,
                  gate_status, created_at
           FROM leads WHERE id = ?""",
        (lead_id,),
    )
    row = await cursor.fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail=f"Lead '{lead_id}' not found")

    return LeadDetail(
        id=row["id"],
        retailer_id=row["retailer_id"],
        retailer_name=row["retailer_name"],
        agent_id=row["agent_id"],
        agent_name=row["agent_name"],
        call_date=row["call_date"],
        crm_fields=row["crm_fields"],
        rate_card=row["rate_card"],
        recording_url=row["recording_url"],
        gate_status=row["gate_status"],
        created_at=row["created_at"],
    )


@router.get("/{lead_id}/transcript")
async def get_lead_transcript(
    lead_id: str,
    db: aiosqlite.Connection = Depends(get_db_connection),
):
    """Return structured speaker turns and transcript for a lead."""
    import json
    cursor = await db.execute(
        "SELECT turns, full_text, redacted, source FROM transcripts WHERE lead_id = ?",
        (lead_id,),
    )
    row = await cursor.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"No transcript found for lead '{lead_id}'")

    turns = json.loads(row["turns"]) if isinstance(row["turns"], str) else row["turns"]
    return {
        "lead_id": lead_id,
        "turns": turns,
        "full_text": row["full_text"],
        "redacted": bool(row["redacted"]),
        "source": row["source"],
    }
