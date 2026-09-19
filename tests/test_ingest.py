"""
STEP 4 TESTS — POST /api/ingest
TDD: Tests written before router + service implementation.
Run: uv run pytest tests/test_ingest.py -v
"""

import json
import pytest
from fastapi.testclient import TestClient

from main import app
from database.connection import init_db, get_db, get_db_connection, TEST_DB_PATH


# ── Fixtures ──────────────────────────────────────────────────────────────────

async def override_get_db():
    async with get_db(test_mode=True) as db:
        yield db


SAMPLE_TURNS = [
    {"speaker": "Speaker 2", "text": "Hi, this is John from Internet Comparison. How are you?"},
    {"speaker": "Speaker 1", "text": "Good thanks. How are you?"},
    {"speaker": "Speaker 2", "text": "Please be advised that this call will be recorded for quality assurance and training purposes."},
    {"speaker": "Speaker 1", "text": "Okay."},
    {"speaker": "Speaker 2", "text": "Your address is 12 Test Street Sydney. Correct?"},
    {"speaker": "Speaker 1", "text": "Yes that is correct."},
]


@pytest.fixture(autouse=True)
async def setup_test_db():
    import os
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)

    await init_db(test_mode=True)

    # Seed one valid lead
    async with get_db(test_mode=True) as db:
        await db.execute(
            """INSERT INTO leads (id, retailer_id, call_date, crm_fields)
               VALUES (?, ?, ?, ?)""",
            ("lead-ingest-001", "retailer-broadband", "2024-06-15", "{}"),
        )
        await db.commit()

    app.dependency_overrides[get_db_connection] = override_get_db
    yield
    app.dependency_overrides.clear()
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


# ── POST /api/ingest ──────────────────────────────────────────────────────────

def test_ingest_unknown_lead_returns_404(client):
    """Ingesting a transcript for a non-existent lead must return 404."""
    response = client.post("/api/ingest", json={
        "lead_id": "lead-does-not-exist",
        "turns": SAMPLE_TURNS,
    })
    assert response.status_code == 404


def test_ingest_valid_lead_returns_201(client):
    """Valid ingest must return 201 Created."""
    response = client.post("/api/ingest", json={
        "lead_id": "lead-ingest-001",
        "turns": SAMPLE_TURNS,
    })
    assert response.status_code == 201


def test_ingest_response_has_correct_shape(client):
    """Response must contain lead_id, transcript_stored, turns_count."""
    response = client.post("/api/ingest", json={
        "lead_id": "lead-ingest-001",
        "turns": SAMPLE_TURNS,
    })
    data = response.json()
    assert data["lead_id"] == "lead-ingest-001"
    assert data["transcript_stored"] is True
    assert data["turns_count"] == len(SAMPLE_TURNS)


def test_ingest_stores_transcript_in_db(client):
    """After ingest, transcript must be retrievable from the DB."""
    client.post("/api/ingest", json={
        "lead_id": "lead-ingest-001",
        "turns": SAMPLE_TURNS,
    })

    import asyncio

    async def fetch():
        async with get_db(test_mode=True) as db:
            cursor = await db.execute(
                "SELECT lead_id, turns FROM transcripts WHERE lead_id = ?",
                ("lead-ingest-001",),
            )
            return await cursor.fetchone()

    row = asyncio.get_event_loop().run_until_complete(fetch())
    assert row is not None
    stored_turns = json.loads(row["turns"])
    assert len(stored_turns) == len(SAMPLE_TURNS)


def test_ingest_turns_have_estimated_timestamps(client):
    """Stored turns must each have start_ms and end_ms fields."""
    client.post("/api/ingest", json={
        "lead_id": "lead-ingest-001",
        "turns": SAMPLE_TURNS,
    })

    import asyncio

    async def fetch():
        async with get_db(test_mode=True) as db:
            cursor = await db.execute(
                "SELECT turns FROM transcripts WHERE lead_id = ?",
                ("lead-ingest-001",),
            )
            return await cursor.fetchone()

    row = asyncio.get_event_loop().run_until_complete(fetch())
    turns = json.loads(row["turns"])

    for turn in turns:
        assert "start_ms" in turn, "Missing start_ms"
        assert "end_ms" in turn, "Missing end_ms"
        assert "turn_index" in turn, "Missing turn_index"
        assert turn["end_ms"] > turn["start_ms"]


def test_ingest_timestamps_are_sequential(client):
    """Turn timestamps must be monotonically increasing."""
    client.post("/api/ingest", json={
        "lead_id": "lead-ingest-001",
        "turns": SAMPLE_TURNS,
    })

    import asyncio

    async def fetch():
        async with get_db(test_mode=True) as db:
            cursor = await db.execute(
                "SELECT turns FROM transcripts WHERE lead_id = ?",
                ("lead-ingest-001",),
            )
            return await cursor.fetchone()

    row = asyncio.get_event_loop().run_until_complete(fetch())
    turns = json.loads(row["turns"])

    for i in range(1, len(turns)):
        assert turns[i]["start_ms"] >= turns[i - 1]["end_ms"], \
            f"Turn {i} starts before turn {i-1} ends"


def test_ingest_redacts_card_number(client):
    """A 16-digit card number spoken in a turn must be redacted."""
    turns_with_card = SAMPLE_TURNS + [
        {"speaker": "Speaker 1", "text": "My card number is 4111 1111 1111 1111 thanks."}
    ]
    client.post("/api/ingest", json={
        "lead_id": "lead-ingest-001",
        "turns": turns_with_card,
    })

    import asyncio

    async def fetch():
        async with get_db(test_mode=True) as db:
            cursor = await db.execute(
                "SELECT turns, full_text FROM transcripts WHERE lead_id = ?",
                ("lead-ingest-001",),
            )
            return await cursor.fetchone()

    row = asyncio.get_event_loop().run_until_complete(fetch())
    turns = json.loads(row["turns"])
    last_turn = turns[-1]["text"]

    assert "4111" not in last_turn, "Card number must not appear in stored transcript"
    assert "[CARD_REDACTED]" in last_turn, "Redaction placeholder must be present"


def test_ingest_second_call_updates_transcript(client):
    """Calling ingest twice for the same lead must upsert (replace) the transcript."""
    client.post("/api/ingest", json={
        "lead_id": "lead-ingest-001",
        "turns": SAMPLE_TURNS,
    })

    new_turns = [{"speaker": "Speaker 2", "text": "Updated transcript version."}]
    response = client.post("/api/ingest", json={
        "lead_id": "lead-ingest-001",
        "turns": new_turns,
    })
    assert response.status_code == 201

    import asyncio

    async def fetch():
        async with get_db(test_mode=True) as db:
            cursor = await db.execute(
                "SELECT turns FROM transcripts WHERE lead_id = ?",
                ("lead-ingest-001",),
            )
            return await cursor.fetchone()

    row = asyncio.get_event_loop().run_until_complete(fetch())
    turns = json.loads(row["turns"])
    assert len(turns) == 1
    assert turns[0]["text"] == "Updated transcript version."
