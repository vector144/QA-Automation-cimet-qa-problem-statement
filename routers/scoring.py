"""
routers/scoring.py
Endpoints for triggering compliance scoring and retrieving audit results.
"""

from fastapi import APIRouter, HTTPException, status
from services.scoring.orchestrator import score_lead
from models.scoring import ScoreRunResponse
from database.connection import get_db

router = APIRouter()


@router.api_route("/run/{lead_id}", methods=["GET", "POST"], response_model=ScoreRunResponse, status_code=status.HTTP_200_OK)
async def run_scoring(lead_id: str):
    """
    Triggers compliance evaluation for a lead across all regulatory checks.
    Evaluates semantic verbatim disclosures, CRM factual matches, and dead-air gaps.
    Enforces compliance gating (blocks sale if any critical check fails).
    """
    try:
        result = await score_lead(lead_id)
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Scoring pipeline error: {str(e)}",
        )


@router.get("/results/{lead_id}", status_code=status.HTTP_200_OK)
async def get_scoring_results(lead_id: str):
    """
    Retrieves the latest compliance evaluation run and all check results for a lead.
    """
    async with get_db() as db:
        # Get latest score run
        async with db.execute(
            """
            SELECT * FROM score_runs
            WHERE lead_id = ?
            ORDER BY run_at DESC
            LIMIT 1
            """,
            (lead_id,),
        ) as cursor:
            run_row = await cursor.fetchone()
            if not run_row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"No scoring results found for lead '{lead_id}'",
                )

        run_id = run_row["id"]

        # Get check results
        async with db.execute(
            """
            SELECT * FROM check_results
            WHERE run_id = ?
            ORDER BY is_critical DESC, check_id ASC
            """,
            (run_id,),
        ) as chk_cursor:
            chk_rows = await chk_cursor.fetchall()

        results_list = []
        for r in chk_rows:
            results_list.append({
                "id": r["id"],
                "check_id": r["check_id"],
                "check_name": r["check_name"],
                "check_type": r["check_type"],
                "is_critical": bool(r["is_critical"]),
                "blocks_sale": bool(r["blocks_sale"]),
                "status": r["status"],
                "confidence": r["confidence"],
                "agent_said": r["agent_said"],
                "expected_value": r["expected_value"],
                "transcript_turn": r["transcript_turn"],
                "timestamp_ms": r["timestamp_ms"],
                "reason": r["reason"],
                "check_library_version": r["check_library_version"],
            })

    return {
        "run_id": run_row["id"],
        "lead_id": run_row["lead_id"],
        "check_library_id": run_row["check_library_id"],
        "check_library_version": run_row["check_library_version"],
        "overall_status": run_row["overall_status"],
        "gate_decision": run_row["gate_decision"],
        "score": run_row["score"],
        "run_at": run_row["run_at"],
        "check_results": results_list,
    }


@router.post("/reset/{lead_id}", status_code=status.HTTP_200_OK)
async def reset_lead_scoring(lead_id: str):
    """
    Resets a lead's gate_status back to PENDING so scoring can be re-triggered.
    Useful during development / re-testing without touching the DB directly.
    """
    async with get_db() as db:
        async with db.execute("SELECT id FROM leads WHERE id = ?", (lead_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Lead '{lead_id}' not found",
                )
        await db.execute("UPDATE leads SET gate_status = 'PENDING' WHERE id = ?", (lead_id,))
        await db.commit()
    return {"lead_id": lead_id, "gate_status": "PENDING", "message": "Lead reset to PENDING. Ready to re-score."}


@router.get("/repeat-offences", status_code=status.HTTP_200_OK)
async def get_repeat_offences():
    """
    Returns list of repeat compliance check failures grouped by agent.
    """
    async with get_db() as db:
        async with db.execute(
            """
            SELECT ro.id, ro.agent_id, ro.check_id, ro.check_name, ro.fail_date, ro.lead_id, l.agent_name
            FROM repeat_offences ro
            LEFT JOIN leads l ON ro.lead_id = l.id
            ORDER BY ro.fail_date DESC
            """
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
