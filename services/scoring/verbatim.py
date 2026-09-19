"""
services/scoring/verbatim.py
Evaluates Type A (Verbatim / Scripted) regulatory compliance checks.
Prompts LLM to verify semantic compliance against defined mandatory scripts.
"""

import re
from typing import Any, Optional
from services.check_library import Check, CheckType
from services.openrouter import get_openrouter_client, OpenRouterClient
from models.scoring import CheckEvaluationResult


def evaluate_verbatim_heuristic(
    turns: list[dict[str, Any]],
    check: Check,
) -> CheckEvaluationResult:
    """
    Fallback deterministic semantic evaluator for verbatim compliance checks.
    Evaluates agent speech turns for regulatory disclosure keywords, returning
    exact turn citations, spoken quotes, and audio timestamps.
    """
    check_lower = check.name.lower()
    script_lower = (check.script or "").lower()

    # BB-001 / EN-001: Recording Disclaimer
    if "recording" in check_lower and "disclaimer" in check_lower:
        keywords = ["record", "recorded", "recording", "monitored", "monitoring"]
        qualifiers = ["training", "quality", "coaching", "purposes", "assurance"]
        for t in turns:
            if t.get("speaker") == "Agent":
                txt = t.get("text", "").lower()
                if any(k in txt for k in keywords) and any(q in txt for q in qualifiers):
                    return CheckEvaluationResult(
                        check_id=check.id,
                        check_name=check.name,
                        check_type=CheckType.VERBATIM,
                        is_critical=check.is_critical,
                        blocks_sale=check.blocks_sale,
                        status="PASS",
                        confidence=0.96,
                        agent_said=t.get("text"),
                        transcript_turn=t.get("turn_index"),
                        timestamp_ms=t.get("start_ms"),
                        reason="Mandatory call recording disclaimer confirmed in agent speech.",
                    )

    # BB-002 / EN-002: Agent Identity Disclosed
    elif "agent" in check_lower and "identity" in check_lower:
        keywords = ["calling from", "this is", "my name is", "from compare", "from internet", "from equinix", "from econnex"]
        for t in turns:
            if t.get("speaker") == "Agent":
                txt = t.get("text", "").lower()
                if any(k in txt for k in keywords):
                    return CheckEvaluationResult(
                        check_id=check.id,
                        check_name=check.name,
                        check_type=CheckType.VERBATIM,
                        is_critical=check.is_critical,
                        blocks_sale=check.blocks_sale,
                        status="PASS",
                        confidence=0.95,
                        agent_said=t.get("text"),
                        transcript_turn=t.get("turn_index"),
                        timestamp_ms=t.get("start_ms"),
                        reason="Agent introduced themselves and stated the operating comparison company identity.",
                    )

    # BB-003: Recording Muted Before Card Collection
    elif "muted" in check_lower or "card" in check_lower:
        keywords = ["mute", "muting", "pause the recording", "pause the call"]
        for t in turns:
            if t.get("speaker") == "Agent":
                txt = t.get("text", "").lower()
                if any(k in txt for k in keywords):
                    return CheckEvaluationResult(
                        check_id=check.id,
                        check_name=check.name,
                        check_type=CheckType.VERBATIM,
                        is_critical=check.is_critical,
                        blocks_sale=check.blocks_sale,
                        status="PASS",
                        confidence=0.94,
                        agent_said=t.get("text"),
                        transcript_turn=t.get("turn_index"),
                        timestamp_ms=t.get("start_ms"),
                        reason="Agent confirmed muting/pausing the recording before sensitive card collection.",
                    )

    # EN-003: Cooling-Off Period (Energy)
    elif "cooling" in check_lower:
        keywords = ["cooling-off", "cooling off", "10 business days", "ten business days", "cancel without penalty"]
        for t in turns:
            if t.get("speaker") == "Agent":
                txt = t.get("text", "").lower()
                if any(k in txt for k in keywords):
                    return CheckEvaluationResult(
                        check_id=check.id,
                        check_name=check.name,
                        check_type=CheckType.VERBATIM,
                        is_critical=check.is_critical,
                        blocks_sale=check.blocks_sale,
                        status="PASS",
                        confidence=0.95,
                        agent_said=t.get("text"),
                        transcript_turn=t.get("turn_index"),
                        timestamp_ms=t.get("start_ms"),
                        reason="Mandatory 10-day cooling-off period clearly stated to customer.",
                    )

    # General concept token matching against agent speech
    stopwords = {"this", "that", "with", "from", "your", "have", "will", "what", "when", "were", "been", "they", "their", "please", "about"}
    tokens = [w for w in re.findall(r"\b[a-z]{4,}\b", script_lower) if w not in stopwords]
    best_turn = None
    best_overlap = 0

    if tokens:
        for t in turns:
            if t.get("speaker") == "Agent":
                txt = t.get("text", "").lower()
                overlap = sum(1 for tok in tokens if tok in txt)
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_turn = t

    threshold = max(2, len(tokens) // 3)
    if best_turn and best_overlap >= threshold:
        return CheckEvaluationResult(
            check_id=check.id,
            check_name=check.name,
            check_type=CheckType.VERBATIM,
            is_critical=check.is_critical,
            blocks_sale=check.blocks_sale,
            status="PASS",
            confidence=round(min(0.95, 0.70 + (best_overlap / len(tokens)) * 0.25), 2),
            agent_said=best_turn.get("text"),
            transcript_turn=best_turn.get("turn_index"),
            timestamp_ms=best_turn.get("start_ms"),
            reason=f"Mandatory disclosure semantic concepts confirmed in Turn {best_turn.get('turn_index')}.",
        )

    return CheckEvaluationResult(
        check_id=check.id,
        check_name=check.name,
        check_type=CheckType.VERBATIM,
        is_critical=check.is_critical,
        blocks_sale=check.blocks_sale,
        status="FAIL",
        confidence=0.85,
        agent_said=None,
        transcript_turn=None,
        timestamp_ms=None,
        reason=f"Mandatory disclosure '{check.name}' was not detected in agent speech.",
    )


VERBATIM_SYSTEM_PROMPT = """You are an expert regulatory compliance auditor for Australian energy and telecommunications sales calls.
Your job is to determine whether an agent delivered a mandatory legal disclosure during a sales call.

Evaluation Rules:
1. Semantic equivalence: The exact wording does not need to be 100% identical unless strictly required, but ALL essential legal concepts, obligations, disclosures, and customer rights described in the mandatory script MUST be communicated accurately and unambiguously.
2. If placeholders like [AGENT_NAME] or [COMPANY_NAME] exist in the script, verify that the agent supplied realistic values.
3. Identify the exact transcript turn where the disclosure occurred.

Respond ONLY with valid JSON in this exact schema:
{
  "status": "PASS" or "FAIL",
  "confidence": float between 0.0 and 1.0,
  "agent_said": "exact quote of what the agent said" or null,
  "transcript_turn": integer turn index or null,
  "reason": "concise explanation of the decision"
}
"""


async def evaluate_verbatim_check(
    turns: list[dict[str, Any]],
    check: Check,
    llm_client: Optional[Any] = None,
) -> CheckEvaluationResult:
    """
    Evaluates whether the mandatory script required by `check` was spoken during the call.
    """
    if not turns:
        return CheckEvaluationResult(
            check_id=check.id,
            check_name=check.name,
            check_type=CheckType.VERBATIM,
            is_critical=check.is_critical,
            blocks_sale=check.blocks_sale,
            status="FAIL",
            confidence=1.0,
            reason="Empty transcript: call contains no dialogue to evaluate.",
        )

    if llm_client is None or isinstance(llm_client, OpenRouterClient):
        # Tier 1: Fast deterministic script disclosure match (< 1ms)
        heuristic_res = evaluate_verbatim_heuristic(turns, check)
        if heuristic_res.status == "PASS" and heuristic_res.confidence >= 0.85:
            return heuristic_res

    client = llm_client or get_openrouter_client()

    # If OpenRouter is not configured or in offline mode, return heuristic result
    if isinstance(client, OpenRouterClient) and not getattr(client, "is_configured", True):
        return heuristic_res

    # Tier 2: Deep LLM Semantic Evaluation for nuanced/unmatched cases
    check_words = set(re.findall(r"\b[a-z]{4,}\b", (check.name + " " + (check.script or "")).lower()))
    candidate_indices = set()
    for idx, t in enumerate(turns):
        t_words = set(re.findall(r"\b[a-z]{4,}\b", t.get("text", "").lower()))
        if check_words & t_words:
            for window_idx in range(max(0, idx - 1), min(len(turns), idx + 2)):
                candidate_indices.add(window_idx)

    # Always include initial 5 turns for disclosures/identities
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

    user_prompt = f"""Mandatory Compliance Check to evaluate:
- Check ID: {check.id}
- Check Name: {check.name}
- Mandatory Script / Statement: "{check.script}"

Transcript of the call:
\"\"\"
{dialogue_str}
\"\"\"

Did the agent communicate this mandatory disclosure? Provide your audit evaluation in the required JSON format."""

    messages = [
        {"role": "system", "content": VERBATIM_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    try:
        response_data = await client.complete_json(messages)
    except Exception:
        # Graceful fallback to heuristic evaluation
        return evaluate_verbatim_heuristic(turns, check)

    status = response_data.get("status", "FAIL").upper()
    if status not in ("PASS", "FAIL"):
        status = "FAIL"

    confidence = float(response_data.get("confidence", 0.5))
    agent_said = response_data.get("agent_said")
    transcript_turn = response_data.get("transcript_turn")
    reason = response_data.get("reason", "No reason provided.")

    # Calculate timestamp if we know which turn it was spoken on
    timestamp_ms = None
    if transcript_turn is not None and transcript_turn in turn_lookup:
        timestamp_ms = turn_lookup[transcript_turn].get("start_ms")

    return CheckEvaluationResult(
        check_id=check.id,
        check_name=check.name,
        check_type=CheckType.VERBATIM,
        is_critical=check.is_critical,
        blocks_sale=check.blocks_sale,
        status=status,
        confidence=confidence,
        agent_said=agent_said,
        transcript_turn=transcript_turn,
        timestamp_ms=timestamp_ms,
        reason=reason,
    )
