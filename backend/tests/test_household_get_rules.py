# Regression: GET /household must echo back planning_rules — it didn't (0.7.0), so
# the Settings page textarea came up blank after saving, and users lost track of
# what the planner was actually using.
import pytest


@pytest.fixture()
def admin_and_headers(client):
    r = client.post("/api/v1/auth/register", json={"name": "Admin", "password": "hunter2hunter"})
    return client, {"Authorization": f"Bearer {r.json()['token']}"}


def test_get_household_returns_planning_rules(client, admin):
    res = client.patch("/api/v1/household", headers=admin, json={
        "name": "Home",
        "planning_rules": ["Only 1 chicken meal per week", "Meatless on Wednesdays"],
    })
    assert res.status_code == 200, res.text
    assert res.json()["planning_rules"] == ["Only 1 chicken meal per week",
                                            "Meatless on Wednesdays"]

    got = client.get("/api/v1/household", headers=admin).json()
    assert got["planning_rules"] == ["Only 1 chicken meal per week",
                                     "Meatless on Wednesdays"]


def test_get_household_planning_rules_default_empty_list(client, admin):
    got = client.get("/api/v1/household", headers=admin).json()
    assert got["planning_rules"] == []
