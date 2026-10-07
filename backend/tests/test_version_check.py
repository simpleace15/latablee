# Version checker (0.7.x): GET /api/v1/admin/version-check compares the running
# version with the latest GitHub release/tags (6h cache; admin-only; offline-safe).
from unittest.mock import patch


def test_version_check_reports_update_available(client, admin, monkeypatch):
    from app.api.v1 import admin as mod

    with patch.object(mod, "_fetch_latest_github_version", return_value="9.9.9"):
        got = client.get("/api/v1/admin/version-check", headers=admin).json()
    assert got["current"] and got["latest"] == "9.9.9"
    assert got["update_available"] is True
    assert got["checked"] is True


def test_version_check_up_to_date(client, admin):
    from app.api.v1 import admin as mod
    from app.core.config import get_settings
    with patch.object(mod, "_fetch_latest_github_version", return_value=get_settings().version):
        got = client.get("/api/v1/admin/version-check", headers=admin).json()
    assert got["update_available"] is False
    assert got["checked"] is True


def test_version_check_offline_still_responds(client, admin):
    from app.api.v1 import admin as mod

    with patch.object(mod, "_fetch_latest_github_version", return_value=None):
        got = client.get("/api/v1/admin/version-check", headers=admin).json()
    assert got["checked"] is False
    assert got["update_available"] is False  # never nags when it can't verify
    assert got["error"]


def test_version_gt_semantics():
    from app.api.v1.admin import _version_gt

    assert _version_gt("0.8.0", "0.7.3")
    assert _version_gt("v1.0.0", "0.9.9")
    assert not _version_gt("0.7.3", "0.7.3")
    assert not _version_gt("0.7.2", "0.7.3")
