"""
Pytest configuration and shared fixtures.
"""

import pytest
from fastapi.testclient import TestClient
from main import app


@pytest.fixture(scope="module")
def client():
    """Shared TestClient — reused across all tests in a module."""
    with TestClient(app) as c:
        yield c
