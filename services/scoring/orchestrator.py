"""
services/scoring/orchestrator.py
End-to-end Compliance Scoring Orchestrator and Gatekeeper.
Loads lead and transcript, executes all checks concurrently, enforces regulatory gate logic,
and persists runs and citations to SQLite.
"""

import asyncio
import json
from uuid import uuid4
from datetime import datetime, timezone
from typing import Any, Optional

from database.connection import get_db
from services.check_library import resolve_library, CheckType
from services.openrouter import get_openrouter_client
from services.scoring.verbatim import evaluate_verbatim_check
from services.scoring.factual import evaluate_factual_check
from services.scoring.behaviour import evaluate_behaviour_check
from models.scoring import ScoreRunResponse, CheckEvaluationResult


async def score_lead(
    lead_id: str,
    test_mode: bool = False,
    llm_client: Optional[Any] = None,
) -> ScoreRunResponse:
    """
    Orchestrates full compliance evaluation for a lead.
    Enforces the Compliance Gatekeeper: any critical check failure sets gate_decision to 'FAILED'.
    """
    async with get_db(test_mode=test_mode) as db:
        # 1. Fetch Lead
        async with db.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)) as cursor:
            lead_row = await cursor.fetchone()
            if not lead_row:
                raise ValueError(f"Lead '{lead_id}' not found")

        # 2. Fetch Transcript
        async with db.execute("SELECT * FROM transcripts WHERE lead_id = ?", (lead_id,)) as cursor:
            transcript_row = await cursor.fetchone()
            if not transcript_row:
                raise ValueError(f"No transcript found for lead '{lead_id}'")

    # Parse JSON fields
    crm_fields = json.loads(lead_row["crm_fields"]) if isinstance(lead_row["crm_fields"], str) else lead_row["crm_fields"]
    turns = json.loads(transcript_row["turns"]) if isinstance(transcript_row["turns"], str) else transcript_row["turns"]
    retailer_id = lead_row["retailer_id"]
    call_date = lead_row["call_date"]
    agent_id = lead_row["agent_id"] or "unknown-agent"

    # 3. Resolve Check Library
    library = resolve_library(retailer_id, call_date)
    resolved_client = llm_client or get_openrouter_client()

    # 4. Schedule all checks concurrently
    tasks = []
    for check in library.checks:
        if check.type == CheckType.VERBATIM:
            tasks.append(evaluate_verbatim_check(turns, check, llm_client=resolved_client))
        elif check.type == CheckType.FACTUAL:
            tasks.append(evaluate_factual_check(turns, check, crm_fields, llm_client=resolved_client))
        elif check.type == CheckType.BEHAVIOUR:
            # Behaviour evaluator is sync, wrap in coroutine
            async def run_behaviour(t=turns, c=check):
                return evaluate_behaviour_check(t, c)
            tasks.append(run_behaviour())

    check_results: list[CheckEvaluationResult] = await asyncio.gather(*tasks)

    # Set library version tag on results
    for res in check_results:
        res.check_library_version = library.id

    # 5. Gatekeeper & Scoring Logic
    critical_failed = [r for r in check_results if (r.is_critical or r.blocks_sale) and r.status == "FAIL"]
    critical_failed_count = len(critical_failed)
    total_checks = len(check_results)
    passed_checks = len([r for r in check_results if r.status == "PASS"])
    score = round((passed_checks / total_checks) * 100, 1) if total_checks > 0 else 0.0

    if critical_failed_count > 0:
        gate_decision = "FAILED"
        overall_status = "FAIL"
    elif score >= 85.0:
        gate_decision = "PASSED"
        overall_status = "PASS"
    else:
        gate_decision = "NEEDS_REVIEW"
        overall_status = "NEEDS_REVIEW"

    run_id = f"run-{uuid4().hex[:12]}"
    run_at_str = datetime.now(timezone.utc).isoformat()

    # 6. Persist results in SQLite
    async with get_db(test_mode=test_mode) as db:
        # Insert score run
        await db.execute(
            """
            INSERT INTO score_runs (id, lead_id, check_library_id, check_library_version, overall_status, gate_decision, score, run_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (run_id, lead_id, library.id, library.id, overall_status, gate_decision, score, run_at_str),
        )

        # Insert individual check results
        for r in check_results:
            chk_result_id = f"chk-{uuid4().hex[:12]}"
            await db.execute(
                """
                INSERT INTO check_results (
                    id, run_id, check_id, check_name, check_type, is_critical, blocks_sale,
                    status, confidence, agent_said, expected_value, transcript_turn,
                    timestamp_ms, reason, check_library_version
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    chk_result_id,
                    run_id,
                    r.check_id,
                    r.check_name,
                    r.check_type.value,
                    1 if r.is_critical else 0,
                    1 if r.blocks_sale else 0,
                    r.status,
                    r.confidence,
                    r.agent_said,
                    r.expected_value,
                    r.transcript_turn,
                    r.timestamp_ms,
                    r.reason,
                    library.id,
                ),
            )

        # Update lead gate_status
        await db.execute(
            "UPDATE leads SET gate_status = ? WHERE id = ?",
            (gate_decision, lead_id),
        )

        # Repeat offence tracking
        for cf in critical_failed:
            async with db.execute(
                "SELECT COUNT(*) as cnt FROM repeat_offences WHERE agent_id = ? AND check_id = ?",
                (agent_id, cf.check_id),
            ) as rep_cursor:
                rep_row = await rep_cursor.fetchone()
                if rep_row and rep_row["cnt"] > 0:
                    # Log additional repeat offence
                    await db.execute(
                        """
                        INSERT INTO repeat_offences (id, agent_id, check_id, check_name, fail_date, lead_id)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (f"rep-{uuid4().hex[:10]}", agent_id, cf.check_id, cf.check_name, call_date, lead_id),
                    )

        await db.commit()

    return ScoreRunResponse(
        run_id=run_id,
        lead_id=lead_id,
        check_library_id=library.id,
        check_library_version=library.id,
        score=score,
        overall_status=overall_status,
        gate_decision=gate_decision,
        critical_failed_count=critical_failed_count,
        total_checks=total_checks,
        passed_checks=passed_checks,
        check_results=check_results,
        run_at=run_at_str,
    )
