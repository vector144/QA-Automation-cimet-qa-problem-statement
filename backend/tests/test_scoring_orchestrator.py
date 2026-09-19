"""
tests/test_scoring_orchestrator.py
TDD tests for the Scoring Orchestrator and Compliance Gatekeeper.
Run: uv run pytest tests/test_scoring_orchestrator.py -v
"""

import pytest
import json
import aiosqlite
from database.connection import init_db, get_db
from services.scoring.orchestrator import score_lead
from services.openrouter import MockOpenRouterClient
from models.scoring import ScoreRunResponse


@pytest.fixture(autouse=True)
async def setup_test_database():
    """Ensure clean test database for each test."""
    await init_db(test_mode=True)
    async with get_db(test_mode=True) as db:
        # Clear tables
        await db.execute("DELETE FROM check_results")
        await db.execute("DELETE FROM score_runs")
        await db.execute("DELETE FROM transcripts")
        await db.execute("DELETE FROM leads")

        # Insert a sample broadband lead
        crm_fields = {
            "customer_full_name": "Sarah Connor",
            "email": "sarah.connor@example.com",
            "service_address": "42 Cyberdyne Way, Sydney NSW 2000",
            "plan_price_intro": 75.0,
            "plan_price_standard": 90.0,
            "modem_upfront_cost": 0.0,
            "delivery_days": "3 to 5 business days",
        }
        await db.execute(
            """
            INSERT INTO leads (id, retailer_id, retailer_name, agent_id, agent_name, call_date, crm_fields, gate_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "lead-broadband-01",
                "retailer-broadband",
                "SuperFast NBN",
                "agent-007",
                "James Bond",
                "2024-06-01",
                json.dumps(crm_fields),
                "PENDING",
            ),
        )
        await db.commit()


@pytest.mark.asyncio
async def test_score_lead_not_found_raises_error():
    mock_llm = MockOpenRouterClient()
    with pytest.raises(ValueError, match="Lead 'non-existent' not found"):
        await score_lead("non-existent", test_mode=True, llm_client=mock_llm)


@pytest.mark.asyncio
async def test_score_lead_without_transcript_raises_error():
    mock_llm = MockOpenRouterClient()
    with pytest.raises(ValueError, match="No transcript found"):
        await score_lead("lead-broadband-01", test_mode=True, llm_client=mock_llm)


@pytest.mark.asyncio
async def test_score_lead_all_pass_returns_passed_gate():
    # Insert transcript turns
    turns = [
        {"turn_index": 0, "speaker": "Agent", "text": "This call will be recorded for quality assurance.", "start_ms": 0, "end_ms": 3000},
        {"turn_index": 1, "speaker": "Customer", "text": "Okay.", "start_ms": 3500, "end_ms": 4000},
        {"turn_index": 2, "speaker": "Agent", "text": "Your introductory price is $75 per month.", "start_ms": 5000, "end_ms": 8000},
    ]
    async with get_db(test_mode=True) as db:
        await db.execute(
            "INSERT INTO transcripts (lead_id, turns, full_text, redacted) VALUES (?, ?, ?, ?)",
            ("lead-broadband-01", json.dumps(turns), "Full call text", 0),
        )
        await db.commit()

    # Mock LLM returns matching values for each check
    def mock_all_pass_responder(messages):
        content = messages[1]["content"]
        if "plan_price_intro" in content:
            return {"status": "PASS", "spoken_value": "75.0", "confidence": 0.99, "reason": "Match"}
        elif "plan_price_standard" in content:
            return {"status": "PASS", "spoken_value": "90.0", "confidence": 0.99, "reason": "Match"}
        elif "customer_full_name" in content:
            return {"status": "PASS", "spoken_value": "Sarah Connor", "confidence": 0.99, "reason": "Match"}
        elif "email" in content:
            return {"status": "PASS", "spoken_value": "sarah.connor@example.com", "confidence": 0.99, "reason": "Match"}
        elif "service_address" in content:
            return {"status": "PASS", "spoken_value": "42 Cyberdyne Way, Sydney NSW 2000", "confidence": 0.99, "reason": "Match"}
        elif "modem_upfront_cost" in content:
            return {"status": "PASS", "spoken_value": "0", "confidence": 0.99, "reason": "Match"}
        elif "delivery_days" in content:
            return {"status": "PASS", "spoken_value": "3 to 5 business days", "confidence": 0.99, "reason": "Match"}
        return {
            "status": "PASS",
            "confidence": 0.98,
            "agent_said": "Compliant statement",
            "transcript_turn": 0,
            "reason": "Fully compliant disclosure.",
        }

    mock_llm = MockOpenRouterClient(responder_fn=mock_all_pass_responder)

    result = await score_lead("lead-broadband-01", test_mode=True, llm_client=mock_llm)

    assert isinstance(result, ScoreRunResponse)
    assert result.lead_id == "lead-broadband-01"
    assert result.gate_decision == "PASSED"
    assert result.overall_status == "PASS"
    assert result.critical_failed_count == 0
    assert result.score >= 85.0

    # Verify DB update on leads table
    async with get_db(test_mode=True) as db:
        async with db.execute("SELECT gate_status FROM leads WHERE id = 'lead-broadband-01'") as cursor:
            row = await cursor.fetchone()
            assert row["gate_status"] == "PASSED"


@pytest.mark.asyncio
async def test_score_lead_critical_fail_blocks_sale():
    turns = [
        {"turn_index": 0, "speaker": "Agent", "text": "Hello there.", "start_ms": 0, "end_ms": 2000},
    ]
    async with get_db(test_mode=True) as db:
        await db.execute(
            "INSERT INTO transcripts (lead_id, turns, full_text, redacted) VALUES (?, ?, ?, ?)",
            ("lead-broadband-01", json.dumps(turns), "Hello there.", 0),
        )
        await db.commit()

    # Mock LLM returns FAIL for critical verbatim check
    def mock_responder(messages):
        content = messages[1]["content"]
        if "Recording Disclaimer" in content:
            return {
                "status": "FAIL",
                "confidence": 0.99,
                "agent_said": None,
                "reason": "Agent completely omitted call recording disclosure.",
            }
        return {"status": "PASS", "confidence": 0.9, "spoken_value": "$75", "reason": "OK"}

    mock_llm = MockOpenRouterClient(responder_fn=mock_responder)
    result = await score_lead("lead-broadband-01", test_mode=True, llm_client=mock_llm)

    assert result.gate_decision == "FAILED"
    assert result.overall_status == "FAIL"
    assert result.critical_failed_count >= 1

    # Verify DB update on leads table
    async with get_db(test_mode=True) as db:
        async with db.execute("SELECT gate_status FROM leads WHERE id = 'lead-broadband-01'") as cursor:
            row = await cursor.fetchone()
            assert row["gate_status"] == "FAILED"
