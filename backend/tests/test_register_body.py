"""Regression tests for the /auth/register body-model fix (query-vs-body 422 bug)."""
from fastapi.testclient import TestClient


def _first_register(client: TestClient, name: str, password: str):
    # JSON body — the exact shape the frontend sends (would 422 under the old query-param contract)
    return client.post("/api/v1/auth/register", json={"name": name, "password": password})


def test_register_json_body_first_user_becomes_admin(client: TestClient):
    """The regression test that would have caught the 422: JSON body on empty DB."""
    r = _first_register(client, "Admin", "long-enough-pw")
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["user"]["role"] == "admin"
    assert "token" in body


def test_register_later_user_requires_invite(client: TestClient):
    assert _first_register(client, "A", "longenough1").status_code == 201
    r = _first_register(client, "B", "longenough1")
    assert r.status_code == 403


def test_register_with_invite_token_json_body(client: TestClient, admin):
    """admin fixture: registered + onboarded — invite preconditions met."""
    inv = client.post("/api/v1/auth/invite", headers=admin).json()
    token = inv.get("token") or inv["invite_url"].split("invite=")[1]
    r = client.post("/api/v1/auth/register",
                    json={"name": "Wife", "password": "longenough1", "invite_token": token})
    assert r.status_code == 201, r.text
    assert r.json()["user"]["role"] == "user"
    # bound to the invite's household: member can see household-scoped data
    tok = r.json()["token"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tok}"}).json()
    assert me["name"] == "Wife"


def test_login_form_encoded_still_works(client: TestClient):
    _first_register(client, "Admin", "hunter2hunter")
    r = client.post("/api/v1/auth/token", data={"username": "admin", "password": "hunter2hunter"})
    assert r.status_code == 200, r.text
    assert r.json()["access_token"]


def test_register_validates_lengths_still(client: TestClient):
    # Pydantic Field guards: short password → 422 from the model (not the old handler text)
    r = _first_register(client, "Shorty", "short")
    assert r.status_code == 422
