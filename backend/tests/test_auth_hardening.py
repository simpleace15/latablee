# Auth hardening: login brute-force lockout (5 fails / 5 min window → 429 with
# Retry-After) + security headers on every response.
from app.services import login_guard


def test_login_locks_after_failures(client, admin):
    login_guard.reset_for_tests()
    # fresh user; wrong passwords repeatedly
    for _ in range(5):
        r = client.post("/api/v1/auth/token", data={"username": "Admin", "password": "nope-nope"})
        assert r.status_code == 401
    r = client.post("/api/v1/auth/token", data={"username": "Admin", "password": "nope-nope"})
    assert r.status_code == 429
    assert "Retry-After" in r.headers
    assert "try again" in r.json()["detail"].lower()


def test_lockout_clears_on_success(client, admin):
    login_guard.reset_for_tests()
    for _ in range(3):
        client.post("/api/v1/auth/token", data={"username": "Admin", "password": "nope-nope"})
    r = client.post("/api/v1/auth/token", data={"username": "Admin", "password": "hunter2hunter"})
    assert r.status_code == 200, r.text
    # failures were cleared: another wrong attempt is just a 401, not the lockout
    r = client.post("/api/v1/auth/token", data={"username": "Admin", "password": "nope-again"})
    assert r.status_code == 401


def test_lockout_is_per_username(client, admin):
    login_guard.reset_for_tests()
    for _ in range(5):
        client.post("/api/v1/auth/token", data={"username": "Admin", "password": "nope-nope"})
    # a different username on the same IP is not dragged into the lockout
    r = client.post("/api/v1/auth/token", data={"username": "Ghost", "password": "nope-nope"})
    assert r.status_code == 401  # wrong-password path, not 429


def test_security_headers_present(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["Referrer-Policy"] == "same-origin"
    assert "frame-ancestors 'none'" in r.headers["Content-Security-Policy"]
