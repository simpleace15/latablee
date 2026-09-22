"""Username case rules: case-insensitive login + duplicate detection, display case preserved."""
from fastapi.testclient import TestClient


def _register(client: TestClient, name: str, password: str = "hunter2hunter"):
    return client.post("/api/v1/auth/register", json={"name": name, "password": password})


def test_login_case_insensitive(client: TestClient):
    r = _register(client, "Tyler")
    assert r.status_code == 201, r.text
    # login with any case variation, same account
    for attempt in ("tyler", "TYLER", "TyLeR"):
        tok = client.post("/api/v1/auth/token", data={"username": attempt, "password": "hunter2hunter"})
        assert tok.status_code == 200, f"{attempt}: {tok.text}"
    me = client.get("/api/v1/auth/me", headers={
        "Authorization": f"Bearer {tok.json()['access_token']}"})
    assert me.json()["name"] == "Tyler"  # display case preserved


def test_duplicate_case_insensitive(client: TestClient):
    assert _register(client, "Casey").status_code == 201  # first user → admin
    dup = _register(client, "casey")  # invite-less anyway, but dup must fail before invite check
    assert dup.status_code in (403, 409)  # 409 dup (no invite), never a second Casey
    # with an admin invite, dup must STILL fail — that's the real casefolding path
    admin_tok = client.post("/api/v1/auth/token", data={"username": "CASEY", "password": "hunter2hunter"}).json()["access_token"]
    onboard = client.post("/api/v1/household/onboard", json={
        "name": "Household", "timezone": "America/Denver", "dietary_preferences": {},
        "allergies": [], "dislikes": [], "favorites": [], "things_to_remember": "",
    }, headers={"Authorization": f"Bearer {admin_tok}"})
    assert onboard.status_code == 200, onboard.text
    inv = client.post("/api/v1/auth/invite", json={}, headers={"Authorization": f"Bearer {admin_tok}"}).json()
    r = client.post("/api/v1/auth/register",
                    json={"name": "cAsEy", "password": "hunter2hunter", "invite_token": inv["invite_url"].split("invite=")[1]})
    assert r.status_code == 409, r.text
    assert "taken" in r.json()["detail"]


def test_name_stripped_and_validated(client: TestClient):
    assert _register(client, "   ").status_code == 422
    r = _register(client, "  spaced  ")
    assert r.status_code == 201
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {r.json()['token']}"})
    assert me.json()["name"] == "spaced"  # whitespace trimmed, case kept
