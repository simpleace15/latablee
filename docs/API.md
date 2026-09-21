# LaTablée API Guide

Versioned REST API under `/api/v1`. Interactive OpenAPI docs ship with the app at
`/api/docs` (schema at `/api/openapi.json`) — always the source of truth for your exact
deployment version. This guide covers the workflows integrators actually automate,
with copy-paste curl examples.

## Authentication

Sessions are JWT (HS256). Get a token with the OAuth2-style form endpoint:

```bash
TOKEN=$(curl -fsS -X POST http://localhost:3000/api/v1/auth/token \
  -d "username=you@example.com" -d "password=yourpassword" | jq -r .access_token)

curl -sS http://localhost:3000/api/v1/auth/me -H "Authorization: Bearer $TOKEN"
```

Tokens expire — re-fetch when you get a 401. Admin-only endpoints (settings, invites,
demo seed) return 403 for regular users.

## Recipes

```bash
# create
curl -sS -X POST http://localhost:3000/api/v1/recipes \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{
    "title": "Weeknight Chili",
    "servings": 4,
    "instructions": ["Brown the beef.", "Add everything, simmer 30 min."],
    "ingredients": [{"name": "ground beef", "raw": "1 lb ground beef"}],
    "tags": ["dinner", "freezer-friendly"],
    "source_url": "https://example.com/chili",   # shown as the Source button
    "source_name": "Example Kitchen"
  }'

# search (matches title, ingredients, tags)
curl -sS "http://localhost:3000/api/v1/recipes?q=chili" -H "Authorization: Bearer $TOKEN"

# delete (frontend always confirms first — the API does not)
curl -sS -X DELETE http://localhost:3000/api/v1/recipes/5 -H "Authorization: Bearer $TOKEN"
```

`ingredients` require `name`; `raw` is optional free text for display.

## Import

Two paths, both returning a **draft** you review and save via `POST /recipes`:

```bash
# from a recipe URL (schema.org/JSON-LD, handles ItemList/HowToSection instruction shapes)
curl -sS -X POST http://localhost:3000/api/v1/import/url \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"url": "https://www.budgetbytes.com/skillet-lasagna/"}'

# from a cookbook photo (requires an OpenAI-compatible vision endpoint in Settings)
curl -sS -X POST http://localhost:3000/api/v1/import/photo \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/path/to/cookbook_page.jpg"
```

Both return `{"parsed": {...}, "note": "Review and save via POST /recipes"}`.

## Meal plan

```bash
# week view (slots: breakfast / lunch / dinner)
curl -sS "http://localhost:3000/api/v1/plan?start=2026-09-21&days=7" \
  -H "Authorization: Bearer $TOKEN"

# plan a meal
curl -sS -X POST http://localhost:3000/api/v1/plan \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"planned_date": "2026-09-22", "slot": "dinner", "recipe_id": 3}'

# move/unplan
curl -sS -X PATCH http://localhost:3000/api/v1/plan/12 \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"planned_date": "2026-09-24"}'

curl -sS -X DELETE http://localhost:3000/api/v1/plan/12 -H "Authorization: Bearer $TOKEN"
```

Dates are interpreted on the **household's timezone** (set in Settings), not the
server's — "today" means what the family means.

## Shopping lists

```bash
curl -sS http://localhost:3000/api/v1/lists -H "Authorization: Bearer $TOKEN"

# add item (consolidates duplicates by name+unit)
curl -sS -X POST http://localhost:3000/api/v1/lists/1/items \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name": "milk", "quantity": 2, "unit": "gallon"}'

# check off / uncheck
curl -sS -X PATCH http://localhost:3000/api/v1/lists/1/items/7 \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"done": true}'

# remove
curl -sS -X DELETE http://localhost:3000/api/v1/lists/1/items/7 -H "Authorization: Bearer $TOKEN"

# rebuild the list from everything planned this week
curl -sS -X POST http://localhost:3000/api/v1/lists/1/generate-from-plan \
  -H "Authorization: Bearer $TOKEN"
```

The web UI queues check-offs offline (localStorage outbox) and replays them when
connectivity returns — a phone in a dead-zone grocery aisle still works.

## Voice command (HA-agnostic)

One endpoint, transcript in → structured actions out. Designed for any satellite
that can POST JSON and speak a reply string. Full payload reference below.

```bash
curl -sS -X POST http://localhost:3000/api/v1/voice/command \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"transcript": "add milk to my shopping list"}'
```

```json
{
  "reply": "Added milk to Week.",
  "actions": [
    {"type": "add_to_list", "params": {"list_id": 1, "item": "milk"}}
  ]
}
```

### Voice request fields

| Field | Type | Required | Purpose |
|---|---|---|---|
| `transcript` | string | ✅ | Raw text from the satellite's STT |
| `device_hint` | string | — | Optional wake-word hint; satellites often mangle "LaTablée" ("la table", "latable") — pass what you heard and the wake-word stripper handles both |

Supported intents today: `add_to_list` ("add milk to the list"), `plan_meal`
("plan chili for dinner tonight" — deterministic fast path, LLM fallback for
everything else), plus `what's for dinner`-style queries. The LLM-based path
needs an OpenAI-compatible endpoint configured in Settings; without one, the
deterministic intents still work and other phrases return a graceful
"can't do that yet" reply rather than an error.

### Integration pattern (recommended)

1. Satellite STT → `POST /api/v1/voice/command` with transcript (+ `device_hint`)
2. Speak/render `reply` verbatim — it's written to be read aloud
3. Optionally execute `actions` locally for sub-second feedback; the server has
   already applied them, so treat actions as informational

## Events (polling)

`GET /api/v1/events?after_id=N` returns an append-only event log — the cheap way for
an HA integration or dashboard to notice changes without polling every endpoint.
Pass the highest `id` you've seen; you get everything newer.

## Export / backup

```bash
# portable JSON
curl -sS http://localhost:3000/api/v1/export/json -H "Authorization: Bearer $TOKEN" > recipes.json

# full backup archive (DB + images) — cron this
curl -sS http://localhost:3000/api/v1/export/archive -H "Authorization: Bearer $TOKEN" -o latablee-backup.tar.gz
```

## Admin

```bash
# demo data (12 recipes, sample week, groceries) — ONLY on an empty instance, admin-only
curl -sS -X POST http://localhost:3000/api/v1/admin/seed \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d '{}'
```

Returns 409 once any user exists. Same via CLI:
`docker compose --profile seed run --rm seed`, or the Settings → "Load demo data" button.

## Versioning

`/api/v1` is the stable contract. Breaking changes ship as `/api/v2` alongside; the
frontend and any HA connector pin what they speak.