"""
STEP 2 TESTS — Database Connection & Schema
TDD: These tests define the DB contract before implementation.
Run: uv run pytest tests/test_db.py -v
"""

import pytest
import aiosqlite
import os
from database.connection import init_db, get_db, DB_PATH


@pytest.fixture(autouse=True)
async def clean_db():
    """Remove test DB before each test to guarantee a clean slate."""
    test_db = DB_PATH.replace(".db", "_test.db")
    if os.path.exists(test_db):
        os.remove(test_db)
    yield
    if os.path.exists(test_db):
        os.remove(test_db)


@pytest.mark.asyncio
async def test_init_db_creates_leads_table():
    """init_db() must create the leads table."""
    await init_db(test_mode=True)
    async with get_db(test_mode=True) as db:
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='leads'"
        )
        row = await cursor.fetchone()
    assert row is not None, "leads table was not created"


@pytest.mark.asyncio
async def test_init_db_creates_transcripts_table():
    """init_db() must create the transcripts table."""
    await init_db(test_mode=True)
    async with get_db(test_mode=True) as db:
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='transcripts'"
        )
        row = await cursor.fetchone()
    assert row is not None, "transcripts table was not created"


@pytest.mark.asyncio
async def test_init_db_creates_score_runs_table():
    """init_db() must create the score_runs table."""
    await init_db(test_mode=True)
    async with get_db(test_mode=True) as db:
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='score_runs'"
        )
        row = await cursor.fetchone()
    assert row is not None, "score_runs table was not created"


@pytest.mark.asyncio
async def test_init_db_creates_check_results_table():
    """init_db() must create the check_results table."""
    await init_db(test_mode=True)
    async with get_db(test_mode=True) as db:
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='check_results'"
        )
        row = await cursor.fetchone()
    assert row is not None, "check_results table was not created"


@pytest.mark.asyncio
async def test_can_insert_and_retrieve_lead():
    """Must be able to insert a lead row and read it back."""
    await init_db(test_mode=True)
    async with get_db(test_mode=True) as db:
        await db.execute(
            """INSERT INTO leads (id, retailer_id, retailer_name, agent_id, call_date, crm_fields)
               VALUES (?, ?, ?, ?, ?, ?)""",
            ("lead-test-001", "retailer-1", "Provider A", "agent-01", "2024-06-15", '{"email": "test@example.com"}'),
        )
        await db.commit()

        cursor = await db.execute("SELECT id, retailer_name FROM leads WHERE id = ?", ("lead-test-001",))
        row = await cursor.fetchone()

    assert row is not None
    assert row[0] == "lead-test-001"
    assert row[1] == "Provider A"


@pytest.mark.asyncio
async def test_lead_default_gate_status_is_pending():
    """New leads must default to PENDING gate status."""
    await init_db(test_mode=True)
    async with get_db(test_mode=True) as db:
        await db.execute(
            """INSERT INTO leads (id, retailer_id, call_date, crm_fields)
               VALUES (?, ?, ?, ?)""",
            ("lead-test-002", "retailer-1", "2024-06-15", "{}"),
        )
        await db.commit()
        cursor = await db.execute("SELECT gate_status FROM leads WHERE id = ?", ("lead-test-002",))
        row = await cursor.fetchone()

    assert row[0] == "PENDING"
