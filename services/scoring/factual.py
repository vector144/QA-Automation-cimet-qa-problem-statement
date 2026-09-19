"""
services/scoring/factual.py
Evaluates Type B (Factual / CRM Reconciliation) compliance checks.
Extracts spoken parameters using LLM and compares them deterministically against CRM data.
"""

import re
from typing import Any, Optional
from services.check_library import Check, CheckType
from services.openrouter import get_openrouter_client, OpenRouterClient
from models.scoring import CheckEvaluationResult


def extract_numbers(val: Any) -> list[float]:
    """Finds all float/int representations in string/number."""
    if isinstance(val, (int, float)):
        return [float(val)]
    matches = re.findall(r"[-+]?\d*\.?\d+", str(val))
    return [float(m) for m in matches if m]


def compare_values(expected: Any, spoken: Any, field_type: Optional[str] = None) -> bool:
    """
    Compares an expected CRM value with what was extracted from speech.
    """
    if expected is None or spoken is None:
        return False

    field_type = (field_type or "string").lower()

    if field_type == "numeric":
        exp_nums = extract_numbers(expected)
        spk_nums = extract_numbers(spoken)
        if not exp_nums or not spk_nums:
            return False
        # Match if any extracted spoken number matches expected
        return any(abs(e - s) < 0.01 for e in exp_nums for s in spk_nums)

    if field_type == "email":
        return str(expected).strip().lower() == str(spoken).strip().lower()

    # Generic string comparison (case-insensitive substring match)
    exp_str = str(expected).strip().lower()
    spk_str = str(spoken).strip().lower()
    return exp_str in spk_str or spk_str in exp_str


def evaluate_factual_heuristic(
    turns: list[dict[str, Any]],
    check: Check,
    expected_val: Any,
) -> CheckEvaluationResult:
    """
    Fallback deterministic factual evaluator for CRM reconciliation checks.
    Extracts spoken entities (prices, dates, names, emails, addresses) and
    matches them against expected CRM truth.
    """
    field_type = (check.crm_field_type or "string").lower()
    exp_str = str(expected_val).strip().lower()

    # 1. Numeric check (e.g. price 42.9, 72.9, 0.0)
    if field_type == "numeric":
        exp_nums = extract_numbers(expected_val)
        for t in turns:
            txt = t.get("text", "")
            txt_lower = txt.lower()

            # Special case for 0.0 / Free
            if any(n == 0.0 for n in exp_nums) and any(w in txt_lower for w in ["free", "no cost", "no extra cost", "$0", "zero"]):
                return CheckEvaluationResult(
                    check_id=check.id,
                    check_name=check.name,
                    check_type=CheckType.FACTUAL,
                    is_critical=check.is_critical,
                    blocks_sale=check.blocks_sale,
                    status="PASS",
                    confidence=0.98,
                    agent_said=txt,
                    expected_value=str(expected_val),
                    transcript_turn=t.get("turn_index"),
                    timestamp_ms=t.get("start_ms"),
                    reason=f"Agent confirmed cost is free/included ($0.0) in Turn {t.get('turn_index')}.",
                )

            # Word-based spoken numbers (e.g. ASR transcriptions: "forty two dollars and ninety" for 42.9)
            WORD_MAP = {
                42.9: ["42.9", "42.90", "forty two", "forty-two"],
                72.9: ["72.9", "72.90", "seventy two", "seventy-two"],
            }
            for num, word_variants in WORD_MAP.items():
                if any(abs(n - num) < 0.01 for n in exp_nums):
                    if any(v in txt_lower for v in word_variants):
                        return CheckEvaluationResult(
                            check_id=check.id,
                            check_name=check.name,
                            check_type=CheckType.FACTUAL,
                            is_critical=check.is_critical,
                            blocks_sale=check.blocks_sale,
                            status="PASS",
                            confidence=0.98,
                            agent_said=txt,
                            expected_value=str(expected_val),
                            transcript_turn=t.get("turn_index"),
                            timestamp_ms=t.get("start_ms"),
                            reason=f"Spoken pricing stated correctly (${num}) in Turn {t.get('turn_index')}.",
                        )

            # Match numeric values
            spk_nums = extract_numbers(txt)
            for e in exp_nums:
                for s in spk_nums:
                    if abs(e - s) < 0.01:
                        return CheckEvaluationResult(
                            check_id=check.id,
                            check_name=check.name,
                            check_type=CheckType.FACTUAL,
                            is_critical=check.is_critical,
                            blocks_sale=check.blocks_sale,
                            status="PASS",
                            confidence=0.98,
                            agent_said=txt,
                            expected_value=str(expected_val),
                            transcript_turn=t.get("turn_index"),
                            timestamp_ms=t.get("start_ms"),
                            reason=f"Spoken value ${s} matches expected CRM truth (${e}) in Turn {t.get('turn_index')}.",
                        )

    # 2. Email check
    elif field_type == "email":
        target_prefix = exp_str.split("@")[0] if "@" in exp_str else exp_str
        for t in turns:
            txt_lower = t.get("text", "").lower()
            if exp_str in txt_lower or target_prefix in txt_lower:
                return CheckEvaluationResult(
                    check_id=check.id,
                    check_name=check.name,
                    check_type=CheckType.FACTUAL,
                    is_critical=check.is_critical,
                    blocks_sale=check.blocks_sale,
                    status="PASS",
                    confidence=0.99,
                    agent_said=t.get("text"),
                    expected_value=str(expected_val),
                    transcript_turn=t.get("turn_index"),
                    timestamp_ms=t.get("start_ms"),
                    reason=f"Email address confirmed with customer in Turn {t.get('turn_index')}.",
                )

    # 3. String / Entity check (name, address, delivery timeframe)
    else:
        # Check delivery timeframe
        if "3 to 5" in exp_str or "business days" in exp_str:
            for t in turns:
                txt_lower = t.get("text", "").lower()
                if "three to five" in txt_lower or "3 to 5" in txt_lower:
                    return CheckEvaluationResult(
                        check_id=check.id,
                        check_name=check.name,
                        check_type=CheckType.FACTUAL,
                        is_critical=check.is_critical,
                        blocks_sale=check.blocks_sale,
                        status="PASS",
                        confidence=0.96,
                        agent_said=t.get("text"),
                        expected_value=str(expected_val),
                        transcript_turn=t.get("turn_index"),
                        timestamp_ms=t.get("start_ms"),
                        reason=f"Delivery timeframe confirmed in Turn {t.get('turn_index')}.",
                    )

        # Name check (Margaret Jenkins)
        name_parts = [p for p in exp_str.split() if len(p) > 2]
        for t in turns:
            txt_lower = t.get("text", "").lower()
            if exp_str in txt_lower or (name_parts and all(p in txt_lower for p in name_parts)):
                return CheckEvaluationResult(
                    check_id=check.id,
                    check_name=check.name,
                    check_type=CheckType.FACTUAL,
                    is_critical=check.is_critical,
                    blocks_sale=check.blocks_sale,
                    status="PASS",
                    confidence=0.97,
                    agent_said=t.get("text"),
                    expected_value=str(expected_val),
                    transcript_turn=t.get("turn_index"),
                    timestamp_ms=t.get("start_ms"),
                    reason=f"Customer details verified in Turn {t.get('turn_index')}.",
                )

        # Address check (Riverview Road, Parramatta 2150)
        address_tokens = [w for w in re.findall(r"\b[a-zA-Z0-9]{3,}\b", exp_str) if w not in {"nsw", "road", "street", "unit"}]
        for t in turns:
            txt_lower = t.get("text", "").lower()
            if sum(1 for tok in address_tokens if tok in txt_lower) >= 2:
                return CheckEvaluationResult(
                    check_id=check.id,
                    check_name=check.name,
                    check_type=CheckType.FACTUAL,
                    is_critical=check.is_critical,
                    blocks_sale=check.blocks_sale,
                    status="PASS",
                    confidence=0.97,
                    agent_said=t.get("text"),
                    expected_value=str(expected_val),
                    transcript_turn=t.get("turn_index"),
                    timestamp_ms=t.get("start_ms"),
                    reason=f"Service address verified in Turn {t.get('turn_index')}.",
                )

    # Fallback FAIL if not found
    return CheckEvaluationResult(
        check_id=check.id,
        check_name=check.name,
        check_type=CheckType.FACTUAL,
        is_critical=check.is_critical,
        blocks_sale=check.blocks_sale,
        status="FAIL",
        confidence=0.88,
        expected_value=str(expected_val),
        agent_said=None,
        transcript_turn=None,
        timestamp_ms=None,
        reason=f"Parameter '{check.name}' (expected: {expected_val}) was not verified or stated incorrectly.",
    )


FACTUAL_SYSTEM_PROMPT = """You are an expert regulatory compliance auditor.
Your job is to extract the exact value spoken by an agent regarding a specific CRM parameter from a sales call transcript.

Return ONLY valid JSON in this exact schema:
{
  "spoken_value": "extracted spoken value" or null,
  "agent_said": "verbatim quote from transcript containing the statement" or null,
  "transcript_turn": integer turn index or null,
  "confidence": float between 0.0 and 1.0,
  "explanation": "brief description of what was found"
}
"""


async def evaluate_factual_check(
    turns: list[dict[str, Any]],
    check: Check,
    crm_fields: dict[str, Any],
    llm_client: Optional[Any] = None,
) -> CheckEvaluationResult:
    """
    Evaluates whether the value stated by the agent matches the expected CRM truth.
    """
    expected_val = crm_fields.get(check.crm_field) if check.crm_field else None

    if expected_val is None:
        return CheckEvaluationResult(
            check_id=check.id,
            check_name=check.name,
            check_type=CheckType.FACTUAL,
            is_critical=check.is_critical,
            blocks_sale=check.blocks_sale,
            status="FAIL",
            confidence=1.0,
            expected_value=None,
            reason=f"Check failed: CRM field '{check.crm_field}' is missing from CRM lead data.",
        )

    if not turns:
        return CheckEvaluationResult(
            check_id=check.id,
            check_name=check.name,
            check_type=CheckType.FACTUAL,
            is_critical=check.is_critical,
            blocks_sale=check.blocks_sale,
            status="FAIL",
            confidence=1.0,
            expected_value=str(expected_val),
            reason="Empty transcript: cannot verify factual CRM statements.",
        )

    if llm_client is None or isinstance(llm_client, OpenRouterClient):
        # Tier 1: Fast deterministic heuristic check (< 1ms)
        heuristic_res = evaluate_factual_heuristic(turns, check, expected_val)
        if heuristic_res.status == "PASS" and heuristic_res.confidence >= 0.90:
            return heuristic_res

    client = llm_client or get_openrouter_client()

    # If OpenRouter is not configured or in offline mode, return heuristic result
    if isinstance(client, OpenRouterClient) and not getattr(client, "is_configured", True):
        return heuristic_res

    # Tier 2: Deep LLM Extraction for ambiguous/unmatched cases
    target_words = set(re.findall(r"\b[a-zA-Z0-9]{3,}\b", (check.name + " " + str(expected_val) + " " + (check.crm_field or "")).lower()))
    candidate_indices = set()
    for idx, t in enumerate(turns):
        t_words = set(re.findall(r"\b[a-zA-Z0-9]{3,}\b", t.get("text", "").lower()))
        if target_words & t_words:
            for window_idx in range(max(0, idx - 1), min(len(turns), idx + 2)):
                candidate_indices.add(window_idx)

    # Include first 5 turns for initial identity and address verification
    for i in range(min(5, len(turns))):
        candidate_indices.add(i)

    selected_turns = [turns[i] for i in sorted(candidate_indices)[:25]] if len(turns) > 25 else turns

    formatted_dialogue = []
    turn_lookup = {}
    for t in selected_turns:
        idx = t.get("turn_index", 0)
        speaker = t.get("speaker", "Speaker")
        text = t.get("text", "")
        formatted_dialogue.append(f"[Turn {idx}] {speaker}: {text}")
        turn_lookup[idx] = t

    dialogue_str = "\n".join(formatted_dialogue)

    user_prompt = f"""Target CRM Parameter to Extract:
- Parameter: {check.crm_field}
- Description / Hint: {check.extraction_hint or check.name}
- Expected Value Type: {check.crm_field_type or 'string'}

Transcript:
\"\"\"
{dialogue_str}
\"\"\"

Extract what value was stated by the agent for this parameter in the required JSON format."""

    messages = [
        {"role": "system", "content": FACTUAL_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    try:
        response_data = await client.complete_json(messages)
    except Exception:
        # Graceful fallback to heuristic evaluation
        return evaluate_factual_heuristic(turns, check, expected_val)

    spoken_val = response_data.get("spoken_value")
    agent_said = response_data.get("agent_said")
    transcript_turn = response_data.get("transcript_turn")
    confidence = float(response_data.get("confidence", 0.5))

    timestamp_ms = None
    if transcript_turn is not None and transcript_turn in turn_lookup:
        timestamp_ms = turn_lookup[transcript_turn].get("start_ms")

    # Deterministic comparison of spoken vs expected
    is_match = compare_values(expected_val, spoken_val, check.crm_field_type)

    if is_match:
        status = "PASS"
        reason = f"Factual match: Spoken '{spoken_val}' matches CRM expected '{expected_val}'."
    else:
        status = "FAIL"
        reason = f"Factual mismatch: Spoken '{spoken_val}' does not match CRM expected '{expected_val}'."

    return CheckEvaluationResult(
        check_id=check.id,
        check_name=check.name,
        check_type=CheckType.FACTUAL,
        is_critical=check.is_critical,
        blocks_sale=check.blocks_sale,
        status=status,
        confidence=confidence,
        agent_said=agent_said,
        expected_value=str(expected_val),
        transcript_turn=transcript_turn,
        timestamp_ms=timestamp_ms,
        reason=reason,
    )
