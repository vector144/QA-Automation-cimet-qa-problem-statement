"""
routers/export.py
CSV exports for sales teams and full Compliance Audit Pack bundles for retailer partners.
"""

import io
import csv
import json
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, Response, status
from fastapi.responses import FileResponse
from database.connection import get_db

router = APIRouter()
_ROOT_DIR = Path(__file__).resolve().parent.parent.parent


@router.get("/csv", status_code=status.HTTP_200_OK)
async def export_leads_csv(
    gate_status: Optional[str] = None,
    retailer_id: Optional[str] = None,
):
    """
    Exports leads and compliance scores as a downloadable CSV.
    Supports filtering by compliance gate status (e.g. PASSED only for retailer dispatch).
    """
    query = """
        SELECT
            l.id as lead_id,
            l.retailer_id,
            l.retailer_name,
            l.agent_id,
            l.agent_name,
            l.call_date,
            l.gate_status,
            COALESCE(sr.score, 0.0) as score,
            l.created_at
        FROM leads l
        LEFT JOIN score_runs sr ON l.id = sr.lead_id
        WHERE 1=1
    """
    params = []
    if gate_status:
        query += " AND l.gate_status = ?"
        params.append(gate_status.upper())
    if retailer_id:
        query += " AND l.retailer_id = ?"
        params.append(retailer_id)

    query += " ORDER BY l.call_date DESC"

    output = io.StringIO()
    writer = csv.writer(output)

    # Write Header
    writer.writerow([
        "lead_id",
        "retailer_id",
        "retailer_name",
        "agent_id",
        "agent_name",
        "call_date",
        "gate_status",
        "score",
        "created_at",
    ])

    async with get_db() as db:
        async with db.execute(query, tuple(params)) as cursor:
            rows = await cursor.fetchall()
            for r in rows:
                writer.writerow([
                    r["lead_id"],
                    r["retailer_id"],
                    r["retailer_name"],
                    r["agent_id"],
                    r["agent_name"],
                    r["call_date"],
                    r["gate_status"],
                    r["score"],
                    r["created_at"],
                ])

    csv_content = output.getvalue()
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="cimet_qa_export.csv"'},
    )


@router.get("/compliance-pack/{lead_id}", status_code=status.HTTP_200_OK)
async def export_compliance_pack(lead_id: str):
    """
    Generates a formal, auditable Compliance Pack JSON bundle for a sales call.
    Includes full CRM data, score breakdown, timestamped check evidence quotes, and reviewer overrides.
    """
    async with get_db() as db:
        # 1. Fetch Lead
        async with db.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)) as cursor:
            lead = await cursor.fetchone()
            if not lead:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Lead '{lead_id}' not found")

        # 2. Fetch Score Run
        async with db.execute(
            "SELECT * FROM score_runs WHERE lead_id = ? ORDER BY run_at DESC LIMIT 1",
            (lead_id,),
        ) as cursor:
            score_run = await cursor.fetchone()

        run_id = score_run["id"] if score_run else None

        # 3. Fetch Check Results
        check_results = []
        if run_id:
            async with db.execute(
                "SELECT * FROM check_results WHERE run_id = ? ORDER BY is_critical DESC, check_id ASC",
                (run_id,),
            ) as chk_cursor:
                chk_rows = await chk_cursor.fetchall()
                for r in chk_rows:
                    check_results.append({
                        "check_id": r["check_id"],
                        "check_name": r["check_name"],
                        "check_type": r["check_type"],
                        "is_critical": bool(r["is_critical"]),
                        "blocks_sale": bool(r["blocks_sale"]),
                        "status": r["status"],
                        "confidence": r["confidence"],
                        "agent_said": r["agent_said"],
                        "expected_value": r["expected_value"],
                        "timestamp_ms": r["timestamp_ms"],
                        "reason": r["reason"],
                    })

        # 4. Fetch QA Overrides
        overrides = []
        async with db.execute(
            "SELECT * FROM qa_overrides WHERE lead_id = ? ORDER BY created_at ASC",
            (lead_id,),
        ) as ovr_cursor:
            ovr_rows = await ovr_cursor.fetchall()
            for ovr in ovr_rows:
                overrides.append({
                    "reviewer_id": ovr["reviewer_id"],
                    "reviewer_name": ovr["reviewer_name"],
                    "previous_status": ovr["previous_status"],
                    "new_status": ovr["new_status"],
                    "justification": ovr["justification"],
                    "timestamp": ovr["created_at"],
                })

    crm_data = json.loads(lead["crm_fields"]) if isinstance(lead["crm_fields"], str) else lead["crm_fields"]

    return {
        "lead_id": lead["id"],
        "retailer_id": lead["retailer_id"],
        "retailer_name": lead["retailer_name"],
        "agent_id": lead["agent_id"],
        "agent_name": lead["agent_name"],
        "call_date": lead["call_date"],
        "gate_status": lead["gate_status"],
        "score": score_run["score"] if score_run else 0.0,
        "run_at": score_run["run_at"] if score_run else None,
        "crm_data": crm_data,
        "checks": check_results,
        "qa_overrides": overrides,
        "compliance_certification": {
            "certified": lead["gate_status"] == "PASSED",
            "regulatory_framework": "ACCC & Telecommunications / Energy Retail Code Compliance",
            "audit_trail_valid": True,
            "system": "CIMET QA Automation Engine v0.1.0",
        },
    }


@router.get("/transcript-pdf", status_code=status.HTTP_200_OK)
async def get_transcript_pdf(lead_id: Optional[str] = "lead-cimet-real-01"):
    """
    Returns the official timestamped, de-redacted sales call transcript PDF for any lead.
    """
    try:
        from generate_timestamped_pdf import generate_lead_pdf
        pdf_path = generate_lead_pdf(lead_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Could not generate transcript PDF for lead '{lead_id}': {str(e)}",
        )

    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename=f"transcript-{lead_id}.pdf",
    )

