"""
database/connection.py
Async SQLite connection using aiosqlite.
Supports test_mode to use a separate DB file so tests never touch production data.
"""

import os
import aiosqlite
from contextlib import asynccontextmanager
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Paths
_BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = str(_BASE_DIR / os.getenv("DATABASE_PATH", "cimet.db"))
TEST_DB_PATH = str(_BASE_DIR / "cimet_test.db")
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def _resolve_path(test_mode: bool) -> str:
    return TEST_DB_PATH if test_mode else DB_PATH


async def init_db(test_mode: bool = False) -> None:
    """
    Create all tables defined in schema.sql.
    Safe to call multiple times — uses CREATE TABLE IF NOT EXISTS.
    """
    db_path = _resolve_path(test_mode)
    schema = SCHEMA_PATH.read_text(encoding="utf-8")

    async with aiosqlite.connect(db_path) as db:
        await db.executescript(schema)
        # Safe column addition if existing database was created earlier
        try:
            await db.execute("ALTER TABLE score_runs ADD COLUMN score REAL DEFAULT 100.0")
        except Exception:
            pass  # Already has score column
        await db.commit()

    if not test_mode:
        from database.seed import seed_initial_data
        await seed_initial_data(test_mode=False)


@asynccontextmanager
async def get_db(test_mode: bool = False):
    """
    Async context manager yielding an aiosqlite connection.

    Usage:
        async with get_db() as db:
            await db.execute(...)
    """
    db_path = _resolve_path(test_mode)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row  # access columns by name
        yield db


async def get_db_connection():
    """
    FastAPI dependency that yields a DB connection.
    Override in tests with app.dependency_overrides[get_db_connection].
    """
    async with get_db() as db:
        yield db
