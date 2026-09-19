"""
tests/test_scoring_router.py
TDD tests for the Scoring API router (/api/scoring/run, /api/scoring/results).
Run: uv run pytest tests/test_scoring_router.py -v
"""

import pytest
import json
from unittest.mock import patch
from fastapi.testclient import TestClient
from main import app
from database.connection import init_db, get_db
from services.openrouter import MockOpenRouterClient

client = TestClient(app)


@pytest.fixture(autouse=True)
async def setup_lead_and_transcript():
    """Sets up a lead and transcript for scoring tests."""
    await init_db()
    async with get_db() as db:
        await db.execute("DELETE FROM check_results")
        await db.execute("DELETE FROM score_runs")
        await db.execute("DELETE FROM transcripts")
        await db.execute("DELETE FROM leads")

        crm_fields = {
            "customer_full_name": "John Connor",
            "email": "john.connor@example.com",
            "service_address": "100 Tech Blvd, Melbourne VIC 3000",
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
                "lead-router-01",
                "retailer-broadband",
                "SuperFast NBN",
                "agent-42",
                "Agent Smith",
                "2024-06-01",
                json.dumps(crm_fields),
                "PENDING",
            ),
        )

        turns = [
            {"turn_index": 0, "speaker": "Agent", "text": "This call is recorded for quality purposes.", "start_ms": 0, "end_ms": 3000},
            {"turn_index": 1, "speaker": "Customer", "text": "Sure thing.", "start_ms": 3500, "end_ms": 4000},
            {"turn_index": 2, "speaker": "Agent", "text": "Your price is $75 a month.", "start_ms": 4500, "end_ms": 7000},
        ]
        await db.execute(
            "INSERT INTO transcripts (lead_id, turns, full_text, redacted) VALUES (?, ?, ?, ?)",
            ("lead-router-01", json.dumps(turns), "Full text here", 0),
        )
        await db.commit()


def test_score_run_unknown_lead_returns_404():
    response = client.post("/api/scoring/run/unknown-lead-id")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_score_run_success():
    def mock_pass_responder(messages):
        return {
            "status": "PASS",
            "confidence": 0.95,
            "spoken_value": "75.0",
            "agent_said": "Your price is $75 a month.",
            "transcript_turn": 2,
            "reason": "Passed check.",
        }

    mock_llm = MockOpenRouterClient(responder_fn=mock_pass_responder)

    with patch("services.scoring.orchestrator.get_openrouter_client", return_value=mock_llm):
        response = client.post("/api/scoring/run/lead-router-01")
        assert response.status_code == 200, response.json()
        data = response.json()
        assert data["lead_id"] == "lead-router-01"
        assert "gate_decision" in data
        assert "score" in data
        assert "check_results" in data
        assert len(data["check_results"]) > 0


def test_get_scoring_results_after_run():
    # First run scoring
    mock_llm = MockOpenRouterClient(default_response={"status": "PASS", "confidence": 0.9, "reason": "OK"})
    with patch("services.scoring.orchestrator.get_openrouter_client", return_value=mock_llm):
        client.post("/api/scoring/run/lead-router-01")

    # Fetch results
    response = client.get("/api/scoring/results/lead-router-01")
    assert response.status_code == 200
    data = response.json()
    assert data["lead_id"] == "lead-router-01"
    assert "gate_decision" in data
    assert "check_results" in data
    assert len(data["check_results"]) > 0


def test_get_scoring_results_not_found():
    response = client.get("/api/scoring/results/non-existent-lead")
    assert response.status_code == 404
