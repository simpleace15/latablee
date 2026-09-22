# Shared test fixtures: temp SQLite DB, admin user, household, auth client.
import os
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("LATABLEE_DATABASE_URL", "sqlite:///./data/test.db")
os.environ.setdefault("LATABLEE_SECRET_KEY", "test-secret-not-for-prod")
os.environ.setdefault("LATABLEE_CORS_ORIGINS", "http://localhost:3000")

from app.db import engine as db_engine  # noqa: E402
from app.main import app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """Fresh DB per test via temp file, TestClient with admin auth headers."""
    monkeypatch.setenv("LATABLEE_DATABASE_URL", f"sqlite:///{tmp_path}/test.db")
    db_engine._engine = None  # reset cached engine to pick up tmp DB
    db_engine.reset_database()
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def admin(client):
    """Register first user (becomes admin) + onboard household; return auth headers."""
    resp = client.post("/api/v1/auth/register", json={"name": "Admin", "password": "hunter2hunter"})
    assert resp.status_code == 201, resp.text
    token = resp.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.post("/api/v1/household/onboard", json={
        "name": "Example Household", "timezone": "America/Denver",
        "dietary_preferences": {}, "allergies": [], "dislikes": ["olives"],
        "favorites": ["tacos"], "things_to_remember": "Mild for the kids",
    }, headers=headers)
    assert resp.status_code == 200, resp.text
    return headers


@pytest.fixture()
def household_id(admin, client):
    resp = client.get("/api/v1/auth/me", headers=admin)
    return resp.json()["household_id"]
