"""
tests/test_reviews.py
TDD tests for QA Reviewer Workflow and Human-in-the-loop Overrides (/api/reviews).
Run: uv run pytest tests/test_reviews.py -v
"""

import pytest
import json
from fastapi.testclient import TestClient
from main import app
from database.connection import init_db, get_db

client = TestClient(app)


@pytest.fixture(autouse=True)
async def setup_review_fixtures():
    await init_db()
    async with get_db() as db:
        await db.execute("DELETE FROM qa_overrides")
        await db.execute("DELETE FROM check_results")
        await db.execute("DELETE FROM score_runs")
        await db.execute("DELETE FROM leads")

        # Insert a lead with FAILED gate status
        await db.execute(
            """
            INSERT INTO leads (id, retailer_id, retailer_name, agent_id, agent_name, call_date, crm_fields, gate_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "lead-rev-01",
                "retailer-broadband",
                "SuperFast NBN",
                "agent-99",
                "Max Smart",
                "2024-06-01",
                json.dumps({"plan_price_intro": 75.0}),
                "FAILED",
            ),
        )

        # Insert a score run
        await db.execute(
            """
            INSERT INTO score_runs (id, lead_id, check_library_id, check_library_version, overall_status, gate_decision, score)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("run-rev-01", "lead-rev-01", "broadband-v1", "broadband-v1", "FAIL", "FAILED", 60.0),
        )

        # Insert a failed check
        await db.execute(
            """
            INSERT INTO check_results (id, run_id, check_id, check_name, check_type, is_critical, blocks_sale, status, reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "chk-rev-01",
                "run-rev-01",
                "BB-001",
                "Recording Disclaimer",
                "VERBATIM",
                1,
                1,
                "FAIL",
                "Script allegedly omitted.",
            ),
        )
        await db.commit()


def test_override_requires_justification():
    payload = {
        "check_id": "BB-001",
        "reviewer_id": "auditor-01",
        "reviewer_name": "Chief Auditor",
        "new_status": "PASS",
        "justification": "",  # Empty justification should be rejected
    }
    response = client.post("/api/reviews/lead-rev-01/override", json=payload)
    assert response.status_code == 422 or response.status_code == 400


def test_override_check_and_lead_gate_status():
    payload = {
        "check_id": "BB-001",
        "reviewer_id": "auditor-01",
        "reviewer_name": "Chief Auditor",
        "new_status": "PASS",
        "gate_status_override": "PASSED",
        "justification": "Verified audio manually; agent spoke disclosure at 00:15 with slight dialect accent that LLM misclassified.",
    }
    response = client.post("/api/reviews/lead-rev-01/override", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["lead_id"] == "lead-rev-01"
    assert data["previous_status"] == "FAIL"
    assert data["new_status"] == "PASS"

    # Verify lead gate status was updated to PASSED
    lead_resp = client.get("/api/leads/lead-rev-01")
    assert lead_resp.status_code == 200
    assert lead_resp.json()["gate_status"] == "PASSED"


def test_get_review_history():
    # Submit an override first
    payload = {
        "check_id": "BB-001",
        "reviewer_id": "auditor-01",
        "reviewer_name": "Chief Auditor",
        "new_status": "PASS",
        "gate_status_override": "PASSED",
        "justification": "Human acoustic verification completed.",
    }
    client.post("/api/reviews/lead-rev-01/override", json=payload)

    history_resp = client.get("/api/reviews/lead-rev-01/history")
    assert history_resp.status_code == 200
    history = history_resp.json()
    assert len(history) >= 1
    assert history[0]["reviewer_id"] == "auditor-01"
    assert "acoustic verification" in history[0]["justification"]


def test_get_sampled_reviews_list():
    response = client.get("/api/reviews/sampled")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
