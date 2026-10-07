# Scheduled backups: GET /api/export/archive/cron?token=lat_… (device token as
# query param — curl-friendly) returns the full backup zip, updates last_used_at.


def _mk_token(client, headers, name="Nightly Backup"):
    r = client.post("/api/v1/tokens", headers=headers, json={"name": name})
    assert r.status_code in (200, 201), r.text
    return r.json()["token"]


def test_cron_archive_with_valid_token(client, admin):
    tok = _mk_token(client, admin)
    r = client.get(f"/api/export/archive/cron?token={tok}")
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("application/zip")
    assert len(r.content) > 100  # a real zip, not an error page


def test_cron_archive_rejects_bad_token(client, admin):
    r = client.get("/api/export/archive/cron?token=lat_00000000000000000000000000000000")
    assert r.status_code == 401
    r = client.get("/api/export/archive/cron")
    assert r.status_code == 401


def test_cron_archive_updates_last_used(client, admin):
    tok = _mk_token(client, admin, "used-at-check")
    r = client.get(f"/api/export/archive/cron?token={tok}")
    assert r.status_code == 200
    toks = client.get("/api/v1/tokens", headers=admin).json()["tokens"]
    row = next(t for t in toks if t["name"] == "used-at-check")
    assert row["last_used_at"] is not None
