# Auth + onboarding integration tests
def test_first_user_becomes_admin(client):
    resp = client.post("/api/v1/auth/register", params={"name": "A", "password": "longenough1"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["user"]["role"] == "admin"
    assert body["token"]


def test_second_user_requires_invite(client, admin):
    resp = client.post("/api/v1/auth/register", params={"name": "B", "password": "longenough1"})
    assert resp.status_code == 403
    resp = client.post("/api/v1/auth/invite", headers=admin)
    assert resp.status_code == 200
    import re

    url = resp.json()["invite_url"]
    token = re.search(r"invite=([\w-]+)", url).group(1)
    resp = client.post("/api/v1/auth/register",
                       params={"name": "Wife", "password": "longenough1", "invite_token": token})
    assert resp.status_code == 201
    assert resp.json()["user"]["role"] == "user"
    # token single-use
    resp = client.post("/api/v1/auth/register",
                       params={"name": "C", "password": "longenough1", "invite_token": token})
    assert resp.status_code == 403


def test_login_and_me(client, admin):
    resp = client.post("/api/v1/auth/token", data={"username": "Admin", "password": "hunter2hunter"})
    assert resp.status_code == 200
    resp = client.get("/api/v1/auth/me", headers=admin)
    assert resp.status_code == 200
    assert resp.json()["role"] == "admin"


def test_onboarding_feeds_household_profile(client, admin):
    resp = client.get("/api/v1/household", headers=admin)
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Example Household"
    assert body["timezone"] == "America/Denver"
    assert "olives" in body["dislikes"]


def test_onboard_requires_admin(client):
    client.post("/api/v1/auth/register", params={"name": "A", "password": "longenough1"})
    resp = client.post("/api/v1/auth/invite")  # no token
    assert resp.status_code in (401, 403)
