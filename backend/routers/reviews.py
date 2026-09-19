"""
routers/reviews.py
Human-in-the-loop QA reviewer workflow, sampling queue, and override audit logs.
"""

from uuid import uuid4
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, status
from models.review import QAOverrideRequest, QAOverrideRecord
from database.connection import get_db

router = APIRouter()


@router.post("/{lead_id}/override", response_model=QAOverrideRecord, status_code=status.HTTP_200_OK)
async def submit_qa_override(lead_id: str, req: QAOverrideRequest):
    """
    Certified QA Manager override endpoint.
    Permits overturning false positive / negative check outcomes with a mandatory audit justification.
    """
    if not req.justification or len(req.justification.strip()) < 5:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A substantive justification note (minimum 5 characters) is mandatory for regulatory audit compliance.",
        )

    override_id = f"ovr-{uuid4().hex[:12]}"
    now_str = datetime.now(timezone.utc).isoformat()

    async with get_db() as db:
        # 1. Check lead existence
        async with db.execute("SELECT gate_status FROM leads WHERE id = ?", (lead_id,)) as cursor:
            lead_row = await cursor.fetchone()
            if not lead_row:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Lead '{lead_id}' not found")

        previous_status = lead_row["gate_status"]

        # 2. Check if a specific check is being overridden
        if req.check_id:
            async with db.execute(
                """
                SELECT cr.id, cr.status
                FROM check_results cr
                JOIN score_runs sr ON cr.run_id = sr.id
                WHERE sr.lead_id = ? AND cr.check_id = ?
                ORDER BY sr.run_at DESC
                LIMIT 1
                """,
                (lead_id, req.check_id),
            ) as chk_cursor:
                chk_row = await chk_cursor.fetchone()
                if chk_row:
                    previous_status = chk_row["status"]
                    # Update check_results table
                    await db.execute(
                        """
                        UPDATE check_results
                        SET status = ?, reason = reason || ' [HUMAN AUDITOR OVERRIDE: ' || ? || ']'
                        WHERE id = ?
                        """,
                        (req.new_status.upper(), req.justification, chk_row["id"]),
                    )

        # 3. Insert override audit record
        await db.execute(
            """
            INSERT INTO qa_overrides (id, lead_id, check_id, reviewer_id, reviewer_name, previous_status, new_status, justification, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                override_id,
                lead_id,
                req.check_id,
                req.reviewer_id,
                req.reviewer_name,
                previous_status,
                req.new_status.upper(),
                req.justification,
                now_str,
            ),
        )

        # 4. Update gate status on lead if provided
        new_gate = req.gate_status_override or (req.new_status.upper() if req.new_status.upper() in ("PASSED", "FAILED", "NEEDS_REVIEW") else None)
        if new_gate:
            await db.execute(
                "UPDATE leads SET gate_status = ? WHERE id = ?",
                (new_gate, lead_id),
            )
            await db.execute(
                "UPDATE score_runs SET human_override = ?, human_sampled = 1 WHERE lead_id = ?",
                (new_gate, lead_id),
            )
        else:
            await db.execute(
                "UPDATE score_runs SET human_sampled = 1 WHERE lead_id = ?",
                (lead_id,),
            )

        await db.commit()

    return QAOverrideRecord(
        id=override_id,
        lead_id=lead_id,
        check_id=req.check_id,
        reviewer_id=req.reviewer_id,
        reviewer_name=req.reviewer_name,
        previous_status=previous_status,
        new_status=req.new_status.upper(),
        justification=req.justification,
        created_at=now_str,
    )


@router.get("/{lead_id}/history", response_model=list[QAOverrideRecord], status_code=status.HTTP_200_OK)
async def get_override_history(lead_id: str):
    """
    Returns full chronological audit log of human QA overrides for a lead.
    """
    async with get_db() as db:
        async with db.execute(
            """
            SELECT id, lead_id, check_id, reviewer_id, reviewer_name, previous_status, new_status, justification, created_at
            FROM qa_overrides
            WHERE lead_id = ?
            ORDER BY created_at DESC
            """,
            (lead_id,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [QAOverrideRecord(**dict(r)) for r in rows]


@router.get("/sampled", status_code=status.HTTP_200_OK)
async def get_sampled_queue():
    """
    Returns leads prioritized for human QA review (e.g. NEEDS_REVIEW, FAILED, or human sampled).
    """
    async with get_db() as db:
        async with db.execute(
            """
            SELECT l.id, l.retailer_id, l.retailer_name, l.agent_id, l.agent_name, l.call_date, l.gate_status, sr.score
            FROM leads l
            LEFT JOIN score_runs sr ON l.id = sr.lead_id
            WHERE l.gate_status IN ('NEEDS_REVIEW', 'FAILED')
            ORDER BY l.call_date DESC
            """
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
