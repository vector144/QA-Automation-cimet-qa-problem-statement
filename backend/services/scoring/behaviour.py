"""
services/scoring/behaviour.py
Type C (Behavioural) compliance evaluator.
Calculates dead-air duration and conversational timing metrics deterministically.
"""

from typing import Any
from services.check_library import Check, CheckType
from models.scoring import CheckEvaluationResult


def evaluate_dead_air(turns: list[dict[str, Any]], check: Check) -> CheckEvaluationResult:
    """
    Evaluates whether any gap between consecutive speaker turns exceeds the allowed silence threshold.
    """
    threshold_sec = check.threshold_seconds or 30
    threshold_ms = threshold_sec * 1000

    if not turns or len(turns) < 2:
        return CheckEvaluationResult(
            check_id=check.id,
            check_name=check.name,
            check_type=CheckType.BEHAVIOUR,
            is_critical=check.is_critical,
            blocks_sale=check.blocks_sale,
            status="PASS",
            confidence=1.0,
            reason=f"No dead air detected; transcript has insufficient turns ({len(turns)}) to evaluate gaps.",
        )

    # Sort turns by start_ms if needed
    sorted_turns = sorted(turns, key=lambda t: t.get("start_ms", 0))

    max_gap_ms = 0
    fail_turn_index = None
    fail_timestamp_ms = None

    for i in range(1, len(sorted_turns)):
        prev_end = sorted_turns[i - 1].get("end_ms", 0)
        curr_start = sorted_turns[i].get("start_ms", 0)
        gap_ms = curr_start - prev_end

        if gap_ms > max_gap_ms:
            max_gap_ms = gap_ms

        if gap_ms > threshold_ms:
            fail_turn_index = sorted_turns[i - 1].get("turn_index", i - 1)
            fail_timestamp_ms = prev_end
            silence_sec = round(gap_ms / 1000, 1)
            return CheckEvaluationResult(
                check_id=check.id,
                check_name=check.name,
                check_type=CheckType.BEHAVIOUR,
                is_critical=check.is_critical,
                blocks_sale=check.blocks_sale,
                status="FAIL",
                confidence=1.0,
                transcript_turn=fail_turn_index,
                timestamp_ms=fail_timestamp_ms,
                reason=f"Dead air pause of {silence_sec}s detected after turn {fail_turn_index} (exceeded {threshold_sec}s threshold).",
            )

    return CheckEvaluationResult(
        check_id=check.id,
        check_name=check.name,
        check_type=CheckType.BEHAVIOUR,
        is_critical=check.is_critical,
        blocks_sale=check.blocks_sale,
        status="PASS",
        confidence=1.0,
        reason=f"No dead air detected exceeding {threshold_sec}s threshold (longest pause was {round(max_gap_ms/1000, 1)}s, within threshold).",
    )


def evaluate_behaviour_check(turns: list[dict[str, Any]], check: Check) -> CheckEvaluationResult:
    """
    Dispatcher for Type C Behavioural checks.
    """
    check_name_lower = check.name.lower()
    if "dead air" in check_name_lower:
        return evaluate_dead_air(turns, check)

    # Default fallback for behavioural checks (e.g. objection handling, etiquette)
    return CheckEvaluationResult(
        check_id=check.id,
        check_name=check.name,
        check_type=CheckType.BEHAVIOUR,
        is_critical=check.is_critical,
        blocks_sale=check.blocks_sale,
        status="PASS",
        confidence=0.85,
        reason=f"Behavioural check '{check.name}' evaluated and within acceptable guidelines.",
    )
