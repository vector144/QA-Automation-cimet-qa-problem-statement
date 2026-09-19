"""
STEP 1 TESTS — Health Check
TDD: These tests define the contract before implementation details are added.
Run: uv run pytest tests/test_health.py -v
"""

import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_health_returns_200():
    """API must respond 200 on /health."""
    response = client.get("/health")
    assert response.status_code == 200


def test_health_returns_ok_status():
    """Response body must contain status: ok."""
    response = client.get("/health")
    data = response.json()
    assert data["status"] == "ok"


def test_health_returns_service_name():
    """Response must identify the service."""
    response = client.get("/health")
    data = response.json()
    assert data["service"] == "cimet-qa-api"


def test_health_returns_version():
    """Response must include a version string."""
    response = client.get("/health")
    data = response.json()
    assert "version" in data
    assert isinstance(data["version"], str)
