"""
tests/test_scoring_verbatim.py
TDD tests for Type A (Verbatim / Scripted) compliance evaluator.
Run: uv run pytest tests/test_scoring_verbatim.py -v
"""

import pytest
from services.check_library import Check, CheckType
from services.openrouter import MockOpenRouterClient
from services.scoring.verbatim import evaluate_verbatim_check
from models.scoring import CheckEvaluationResult


@pytest.fixture
def recording_disclaimer_check():
    return Check(
        id="BB-001",
        name="Recording Disclaimer",
        type=CheckType.VERBATIM,
        is_critical=True,
        blocks_sale=True,
        script="This call will be recorded for quality assurance and training purposes.",
        fuzzy_threshold=0.82,
    )


@pytest.mark.asyncio
async def test_verbatim_evaluator_passes_when_script_spoken(recording_disclaimer_check):
    turns = [
        {"turn_index": 0, "speaker": "Agent", "text": "Hi, please note that this call is recorded for quality and training purposes today.", "start_ms": 0, "end_ms": 4000},
        {"turn_index": 1, "speaker": "Customer", "text": "No worries.", "start_ms": 4500, "end_ms": 5500},
    ]

    mock_llm = MockOpenRouterClient(default_response={
        "status": "PASS",
        "confidence": 0.96,
        "agent_said": "please note that this call is recorded for quality and training purposes today",
        "transcript_turn": 0,
        "reason": "Agent delivered the mandatory call recording disclaimer clearly at the start of the call.",
    })

    result = await evaluate_verbatim_check(turns, recording_disclaimer_check, llm_client=mock_llm)

    assert isinstance(result, CheckEvaluationResult)
    assert result.status == "PASS"
    assert result.check_id == "BB-001"
    assert result.is_critical is True
    assert result.blocks_sale is True
    assert result.confidence == 0.96
    assert result.transcript_turn == 0
    assert result.agent_said == "please note that this call is recorded for quality and training purposes today"
    assert "mandatory call recording" in result.reason


@pytest.mark.asyncio
async def test_verbatim_evaluator_fails_when_script_omitted(recording_disclaimer_check):
    turns = [
        {"turn_index": 0, "speaker": "Agent", "text": "Hi, welcome to internet sales.", "start_ms": 0, "end_ms": 2000},
        {"turn_index": 1, "speaker": "Customer", "text": "Hello.", "start_ms": 2500, "end_ms": 3000},
    ]

    mock_llm = MockOpenRouterClient(default_response={
        "status": "FAIL",
        "confidence": 0.99,
        "agent_said": None,
        "transcript_turn": None,
        "reason": "Agent never stated that the call is being recorded for quality or training.",
    })

    result = await evaluate_verbatim_check(turns, recording_disclaimer_check, llm_client=mock_llm)

    assert result.status == "FAIL"
    assert result.check_id == "BB-001"
    assert result.blocks_sale is True
    assert result.agent_said is None
    assert "never stated" in result.reason


@pytest.mark.asyncio
async def test_verbatim_evaluator_handles_empty_transcript(recording_disclaimer_check):
    mock_llm = MockOpenRouterClient()
    result = await evaluate_verbatim_check([], recording_disclaimer_check, llm_client=mock_llm)

    assert result.status == "FAIL"
    assert result.confidence == 1.0
    assert "empty transcript" in result.reason.lower()
    # Mock LLM shouldn't even need to be called if transcript is empty
    assert len(mock_llm.call_history) == 0
