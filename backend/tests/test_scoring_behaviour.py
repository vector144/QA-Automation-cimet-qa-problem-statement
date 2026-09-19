"""
tests/test_scoring_behaviour.py
TDD tests for Type C Behavioural checks (Dead Air & timeline heuristics).
Run: uv run pytest tests/test_scoring_behaviour.py -v
"""

import pytest
from services.check_library import Check, CheckType
from services.scoring.behaviour import evaluate_dead_air, evaluate_behaviour_check
from models.scoring import CheckEvaluationResult


@pytest.fixture
def dead_air_check():
    return Check(
        id="BB-011",
        name="Dead Air Detection",
        type=CheckType.BEHAVIOUR,
        is_critical=False,
        blocks_sale=False,
        threshold_seconds=30,
    )


def test_dead_air_passes_when_no_pauses_exceed_threshold(dead_air_check):
    # Turns with normal 1-2 second gaps (1000ms - 2000ms)
    turns = [
        {"turn_index": 0, "speaker": "Agent", "text": "Hello, thank you for calling.", "start_ms": 0, "end_ms": 3000},
        {"turn_index": 1, "speaker": "Customer", "text": "Hi, I want to check my internet plan.", "start_ms": 4000, "end_ms": 7000},
        {"turn_index": 2, "speaker": "Agent", "text": "Sure, let me pull up your account.", "start_ms": 8500, "end_ms": 12000},
    ]
    result = evaluate_dead_air(turns, dead_air_check)

    assert isinstance(result, CheckEvaluationResult)
    assert result.status == "PASS"
    assert result.check_id == "BB-011"
    assert result.is_critical is False
    assert result.confidence == 1.0
    assert "No dead air detected" in result.reason or "within threshold" in result.reason


def test_dead_air_fails_when_pause_exceeds_threshold(dead_air_check):
    # Turns with a 35-second gap between turn 1 and turn 2
    turns = [
        {"turn_index": 0, "speaker": "Agent", "text": "Let me look that up for you.", "start_ms": 0, "end_ms": 5000},
        # 5000ms to 42000ms = 37,000ms silence (37 seconds > 30 seconds threshold)
        {"turn_index": 1, "speaker": "Agent", "text": "Thank you for holding, I found it.", "start_ms": 42000, "end_ms": 46000},
    ]
    result = evaluate_dead_air(turns, dead_air_check)

    assert result.status == "FAIL"
    assert result.check_id == "BB-011"
    assert result.timestamp_ms == 5000
    assert result.transcript_turn == 0
    assert "37" in result.reason or "exceeded" in result.reason


def test_dead_air_handles_empty_or_single_turn(dead_air_check):
    # 0 or 1 turn cannot have dead air between turns
    assert evaluate_dead_air([], dead_air_check).status == "PASS"
    assert evaluate_dead_air([{"turn_index": 0, "speaker": "Agent", "text": "Hi", "start_ms": 0, "end_ms": 1000}], dead_air_check).status == "PASS"


def test_evaluate_behaviour_check_dispatcher(dead_air_check):
    turns = [
        {"turn_index": 0, "speaker": "Agent", "text": "Hello", "start_ms": 0, "end_ms": 2000},
        {"turn_index": 1, "speaker": "Customer", "text": "Hi", "start_ms": 3000, "end_ms": 4000},
    ]
    result = evaluate_behaviour_check(turns, dead_air_check)
    assert isinstance(result, CheckEvaluationResult)
    assert result.status == "PASS"
