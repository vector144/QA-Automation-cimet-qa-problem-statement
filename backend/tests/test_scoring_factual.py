"""
tests/test_scoring_factual.py
TDD tests for Type B (Factual / CRM Reconciliation) compliance evaluator.
Run: uv run pytest tests/test_scoring_factual.py -v
"""

import pytest
from services.check_library import Check, CheckType
from services.openrouter import MockOpenRouterClient
from services.scoring.factual import evaluate_factual_check, compare_values
from models.scoring import CheckEvaluationResult


@pytest.fixture
def intro_price_check():
    return Check(
        id="BB-004",
        name="Introductory Price Stated Correctly",
        type=CheckType.FACTUAL,
        is_critical=True,
        blocks_sale=True,
        crm_field="plan_price_intro",
        crm_field_type="numeric",
        extraction_hint="agent states monthly price for first promotional period in dollars",
    )


@pytest.fixture
def email_check():
    return Check(
        id="BB-007",
        name="Email Address Confirmed",
        type=CheckType.FACTUAL,
        is_critical=True,
        blocks_sale=True,
        crm_field="email",
        crm_field_type="email",
        extraction_hint="agent reads back or confirms customer email address",
    )


def test_compare_values_numeric():
    # Both exact numbers, strings with currency symbols, etc.
    assert compare_values(75.0, "$75.00", "numeric") is True
    assert compare_values("75", "$75/month", "numeric") is True
    assert compare_values(75.0, "$65.00", "numeric") is False


def test_compare_values_email():
    assert compare_values("john.doe@example.com", "John.Doe@EXAMPLE.com", "email") is True
    assert compare_values("john.doe@example.com", "jane.doe@example.com", "email") is False


@pytest.mark.asyncio
async def test_factual_price_passes_when_matching_crm(intro_price_check):
    crm_data = {"plan_price_intro": 75.0, "customer_name": "Alice"}
    turns = [
        {"turn_index": 0, "speaker": "Agent", "text": "Your promotional price for the first 6 months is $75 a month.", "start_ms": 0, "end_ms": 4000},
    ]

    mock_llm = MockOpenRouterClient(default_response={
        "spoken_value": "$75",
        "agent_said": "Your promotional price for the first 6 months is $75 a month.",
        "transcript_turn": 0,
        "confidence": 0.98,
        "explanation": "Agent clearly stated $75 promotional rate.",
    })

    result = await evaluate_factual_check(turns, intro_price_check, crm_data, llm_client=mock_llm)

    assert isinstance(result, CheckEvaluationResult)
    assert result.status == "PASS"
    assert result.check_id == "BB-004"
    assert result.is_critical is True
    assert result.expected_value == "75.0"
    assert result.agent_said == "Your promotional price for the first 6 months is $75 a month."


@pytest.mark.asyncio
async def test_factual_price_fails_when_mismatched(intro_price_check):
    crm_data = {"plan_price_intro": 75.0}
    turns = [
        {"turn_index": 0, "speaker": "Agent", "text": "We have you locked in at $60 per month.", "start_ms": 0, "end_ms": 3000},
    ]

    mock_llm = MockOpenRouterClient(default_response={
        "spoken_value": "$60",
        "agent_said": "We have you locked in at $60 per month.",
        "transcript_turn": 0,
        "confidence": 0.95,
        "explanation": "Agent stated $60 instead of $75.",
    })

    result = await evaluate_factual_check(turns, intro_price_check, crm_data, llm_client=mock_llm)

    assert result.status == "FAIL"
    assert result.check_id == "BB-004"
    assert result.blocks_sale is True
    assert "mismatch" in result.reason.lower() or "60" in result.reason


@pytest.mark.asyncio
async def test_factual_fails_when_missing_crm_field(intro_price_check):
    crm_data = {}  # Missing 'plan_price_intro'
    turns = [{"turn_index": 0, "speaker": "Agent", "text": "Price is $75", "start_ms": 0, "end_ms": 2000}]

    mock_llm = MockOpenRouterClient()
    result = await evaluate_factual_check(turns, intro_price_check, crm_data, llm_client=mock_llm)

    assert result.status == "FAIL"
    assert "missing from crm" in result.reason.lower()
