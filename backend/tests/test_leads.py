"""
STEP 3 TESTS — Leads API Endpoints
TDD: Tests written before router implementation.
Run: uv run pytest tests/test_leads.py -v
"""

import json
import pytest
from fastapi.testclient import TestClient

from main import app
from database.connection import init_db, get_db, get_db_connection


# ── Test DB override ──────────────────────────────────────────────────────────

async def override_get_db():
    """Redirect all DB calls to the isolated test database."""
    async with get_db(test_mode=True) as db:
        yield db


@pytest.fixture(autouse=True)
async def setup_test_db():
    """Fresh test DB + seed data before every test, teardown after."""
    import os
    from database.connection import TEST_DB_PATH

    # Clean slate
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)

    await init_db(test_mode=True)

    # Seed two leads
    async with get_db(test_mode=True) as db:
        await db.execute("DELETE FROM leads")
        await db.executemany(
            """INSERT INTO leads
               (id, retailer_id, retailer_name, agent_id, agent_name, call_date, crm_fields, gate_status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    "lead-001",
                    "retailer-broadband",
                    "Provider A",
                    "agent-01",
                    "John Agent",
                    "2024-06-15",
                    json.dumps({
                        "customer_full_name": "Jane Smith",
                        "email": "jane.smith@example.com",
                        "phone": "0400000001",
                        "dob": "1975-03-22",
                        "service_address": "12 Test St, Sydney NSW 2000",
                        "plan_price_intro": 42.90,
                        "plan_price_standard": 72.90,
                    }),
                    "HELD",
                ),
                (
                    "lead-002",
                    "retailer-energy",
                    "Provider B",
                    "agent-02",
                    "Sarah Agent",
                    "2024-06-16",
                    json.dumps({
                        "customer_full_name": "Bob Jones",
                        "email": "bob.jones@example.com",
                        "phone": "0400000002",
                        "peak_rate_cents": 31.9,
                    }),
                    "AUTO_SUBMIT",
                ),
            ],
        )
        await db.commit()

    # Override DB dependency for the entire test
    app.dependency_overrides[get_db_connection] = override_get_db
    yield
    app.dependency_overrides.clear()

    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


# ── GET /api/leads ────────────────────────────────────────────────────────────

def test_list_leads_returns_200(client):
    response = client.get("/api/leads")
    assert response.status_code == 200


def test_list_leads_returns_list(client):
    response = client.get("/api/leads")
    data = response.json()
    assert isinstance(data, list)


def test_list_leads_returns_all_seeded_leads(client):
    response = client.get("/api/leads")
    data = response.json()
    assert len(data) == 2


def test_list_leads_contains_required_fields(client):
    response = client.get("/api/leads")
    lead = response.json()[0]
    for field in ("id", "retailer_name", "agent_name", "call_date", "gate_status"):
        assert field in lead, f"Missing field: {field}"


def test_list_leads_filter_by_gate_status(client):
    response = client.get("/api/leads?gate_status=HELD")
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == "lead-001"
    assert data[0]["gate_status"] == "HELD"


def test_list_leads_filter_by_retailer(client):
    response = client.get("/api/leads?retailer_id=retailer-energy")
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == "lead-002"


# ── GET /api/leads/{id} ───────────────────────────────────────────────────────

def test_get_lead_by_id_returns_200(client):
    response = client.get("/api/leads/lead-001")
    assert response.status_code == 200


def test_get_lead_by_id_returns_correct_lead(client):
    response = client.get("/api/leads/lead-001")
    data = response.json()
    assert data["id"] == "lead-001"
    assert data["retailer_name"] == "Provider A"


def test_get_lead_by_id_includes_crm_fields(client):
    response = client.get("/api/leads/lead-001")
    data = response.json()
    assert "crm_fields" in data
    assert data["crm_fields"]["email"] == "jane.smith@example.com"


def test_get_lead_unknown_id_returns_404(client):
    response = client.get("/api/leads/lead-does-not-exist")
    assert response.status_code == 404


def test_get_lead_404_has_detail_message(client):
    response = client.get("/api/leads/lead-does-not-exist")
    data = response.json()
    assert "detail" in data
