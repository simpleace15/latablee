# Recipe list endpoint: q=, tag=, favorite=, ingredient= (require ALL listed
# ingredients — "what can I make with chicken + rice").


def test_ingredient_filter_all_match(client, admin):
    client.post("/api/v1/recipes", headers=admin, json={
        "title": "Chicken Rice Bowl",
        "ingredients": [{"name": "chicken", "quantity": 1, "unit": "lb"},
                        {"name": "rice", "quantity": 2, "unit": "cup"}],
        "instructions": []})
    client.post("/api/v1/recipes", headers=admin, json={
        "title": "Plain Rice",
        "ingredients": [{"name": "rice", "quantity": 1, "unit": "cup"}],
        "instructions": []})

    both = client.get("/api/v1/recipes", headers=admin,
                      params={"ingredients": "chicken,rice"}).json()
    titles = [r["title"] for r in both]
    assert "Chicken Rice Bowl" in titles
    assert "Plain Rice" not in titles

    one = client.get("/api/v1/recipes", headers=admin,
                     params={"ingredients": "rice"}).json()
    titles1 = [r["title"] for r in one]
    assert "Chicken Rice Bowl" in titles1
    assert "Plain Rice" in titles1


def test_ingredient_filter_matches_substring(client, admin):
    client.post("/api/v1/recipes", headers=admin, json={
        "title": "Cacciatore",
        "ingredients": [{"name": "chicken thighs", "quantity": 4, "unit": "piece"}],
        "instructions": []})
    got = client.get("/api/v1/recipes", headers=admin,
                     params={"ingredients": "chicken"}).json()
    assert [r["title"] for r in got] == ["Cacciatore"]


def test_tag_and_favorite_filters_roundtrip(client, admin):
    r = client.post("/api/v1/recipes", headers=admin, json={
        "title": "Tagged One", "tags": ["pasta"], "ingredients": [], "instructions": []})
    rid = r.json()["id"]
    client.put(f"/api/v1/recipes/{rid}/favorite", headers=admin)
    got = client.get("/api/v1/recipes", headers=admin, params={"tag": "pasta"}).json()
    assert [x["title"] for x in got] == ["Tagged One"]
    got = client.get("/api/v1/recipes", headers=admin, params={"favorite": "1"}).json()
    assert [x["title"] for x in got] == ["Tagged One"]
