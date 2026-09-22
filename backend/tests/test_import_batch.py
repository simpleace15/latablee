# Multi-URL batch import: per-URL results, one failure never kills the batch.
# Uses the same fixture-HTML monkeypatch trick as the single-URL test (no live sites).
import pytest


@pytest.fixture()
def recipe_html():
    from pathlib import Path
    return (Path(__file__).parent / "fixtures" / "recipe_page.html").read_text()


def _patch_scraper(monkeypatch, html_by_url: dict[str, object]):
    """Fake httpx.Client: per-URL html, or Exception for failing URLs."""
    from app.services import recipe_url_import as mod

    class Ctx:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def get(self, url, **kw):
            outcome = html_by_url[url]

            class R:
                status_code = 200

                def __init__(self, text):
                    self.text = text

                def raise_for_status(self):
                    pass

            if isinstance(outcome, Exception):
                raise outcome
            return R(outcome)

    monkeypatch.setattr(mod.httpx, "Client", lambda **kw: Ctx())


GOOD = "https://example.com/recipe"
GOOD2 = "https://example.com/recipe2"
BAD = "https://example.com/broken"


def test_batch_mixed_results(client, admin, recipe_html, monkeypatch):
    _patch_scraper(monkeypatch, {GOOD: recipe_html, GOOD2: recipe_html,
                                 BAD: RuntimeError("connection refused")})
    resp = client.post("/api/v1/import/urls",
                       json={"urls": f"check these: {GOOD} and {BAD} + {GOOD2}"},
                       headers=admin)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 3 and body["ok_count"] == 2
    by_url = {r["url"]: r for r in body["results"]}
    assert by_url[GOOD]["ok"] and by_url[GOOD]["parsed"]["title"] == "Classic Pancakes"
    assert not by_url[BAD]["ok"] and "RuntimeError" in by_url[BAD]["error"]
    # order preserved
    assert [r["url"] for r in body["results"]] == [GOOD, BAD, GOOD2]


def test_batch_dedupes_and_caps(client, admin, recipe_html, monkeypatch):
    _patch_scraper(monkeypatch, {GOOD: recipe_html})
    text = f"{GOOD}\n{GOOD} \n{GOOD} and more text"
    resp = client.post("/api/v1/import/urls", json={"urls": text}, headers=admin)
    assert resp.status_code == 200
    assert resp.json()["total"] == 1  # exact dups collapsed


def test_batch_no_urls_422(client, admin):
    resp = client.post("/api/v1/import/urls", json={"urls": "no links here at all"},
                       headers=admin)
    assert resp.status_code == 422


def test_batch_requires_auth(client):
    resp = client.post("/api/v1/import/urls", json={"urls": "https://example.com/x"})
    assert resp.status_code in (401, 403)
