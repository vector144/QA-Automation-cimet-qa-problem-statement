"""
tests/test_export.py
TDD tests for Export and Retailer Compliance Pack endpoints (/api/export/csv, /api/export/compliance-pack/{lead_id}).
Run: uv run pytest tests/test_export.py -v
"""

import pytest
import json
from fastapi.testclient import TestClient
from main import app
from database.connection import init_db, get_db

client = TestClient(app)


@pytest.fixture(autouse=True)
async def setup_export_fixtures():
    await init_db()
    async with get_db() as db:
        await db.execute("DELETE FROM check_results")
        await db.execute("DELETE FROM score_runs")
        await db.execute("DELETE FROM leads")

        # Insert a passed lead
        await db.execute(
            """
            INSERT INTO leads (id, retailer_id, retailer_name, agent_id, agent_name, call_date, crm_fields, gate_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "lead-exp-01",
                "retailer-broadband",
                "SuperFast NBN",
                "agent-01",
                "Alice Wonder",
                "2024-06-01",
                json.dumps({"plan_price_intro": 75.0, "customer_full_name": "Bob Smith"}),
                "PASSED",
            ),
        )

        # Insert score run
        await db.execute(
            """
            INSERT INTO score_runs (id, lead_id, check_library_id, check_library_version, overall_status, gate_decision, score)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("run-exp-01", "lead-exp-01", "broadband-v1", "broadband-v1", "PASS", "PASSED", 100.0),
        )

        # Insert a check result
        await db.execute(
            """
            INSERT INTO check_results (id, run_id, check_id, check_name, check_type, is_critical, blocks_sale, status, confidence, agent_said, reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "chk-exp-01",
                "run-exp-01",
                "BB-001",
                "Recording Disclaimer",
                "VERBATIM",
                1,
                1,
                "PASS",
                0.98,
                "This call will be recorded for quality assurance.",
                "Delivered clearly at start of call.",
            ),
        )
        await db.commit()


def test_export_csv_returns_csv_header_and_data():
    response = client.get("/api/export/csv")
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert "cimet_qa_export.csv" in response.headers.get("content-disposition", "")

    lines = response.text.strip().split("\n")
    header = lines[0].strip()
    assert "lead_id" in header
    assert "retailer_name" in header
    assert "gate_status" in header
    assert "score" in header

    # At least our fixture line is present
    assert any("lead-exp-01" in line for line in lines[1:])


def test_export_csv_filters_by_gate_status():
    response = client.get("/api/export/csv?gate_status=FAILED")
    assert response.status_code == 200
    lines = response.text.strip().split("\n")
    # Header exists, but lead-exp-01 (PASSED) should not be in FAILED export
    assert not any("lead-exp-01" in line for line in lines[1:])


def test_export_compliance_pack_returns_complete_bundle():
    response = client.get("/api/export/compliance-pack/lead-exp-01")
    assert response.status_code == 200
    data = response.json()

    assert data["lead_id"] == "lead-exp-01"
    assert data["retailer_name"] == "SuperFast NBN"
    assert data["gate_status"] == "PASSED"
    assert data["score"] == 100.0
    assert "checks" in data
    assert len(data["checks"]) == 1
    assert data["checks"][0]["check_id"] == "BB-001"
    assert data["checks"][0]["agent_said"] == "This call will be recorded for quality assurance."
    assert "compliance_certification" in data


def test_export_compliance_pack_unknown_lead_returns_404():
    response = client.get("/api/export/compliance-pack/non-existent-lead")
    assert response.status_code == 404
