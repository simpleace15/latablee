# LaTablée

**Self-hosted recipe & meal planning for the whole table.** A Mealie replacement built around one
idea: the app succeeds only if it can be handed to a non-technical spouse and immediately make sense.

- 🌐 **LaTablée** (French: *the company gathered around the table*) — spoken "lah-tah-BLAY"
- 🏠 One household, multiple users, invited by link
- 📱 Mobile-first PWA — installable, offline-ready for kitchen use
- 🔌 Works standalone; optional integrations attach via the versioned REST API

## Quickstart (Docker)

```bash
git clone https://github.com/<your-github-account>/latablee.git
cd latablee
cp .env.example .env          # set LATABLEE_SECRET_KEY to a long random string!
docker compose up -d
# open http://localhost:3000 — first run walks you through household setup
```

SQLite by default (zero-config). Prefer Postgres?

```bash
docker compose --profile postgres up -d
```

## Local development

```bash
# backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
uvicorn app.main:app --reload --app-dir backend   # API docs at /api/docs

# frontend
cd frontend && npm install && npm run dev
```

## The API

Versioned under `/api/v1`, OpenAPI docs at `/api/docs`. Highlights for integrators:

| Endpoint | Purpose |
|---|---|
| `POST /api/v1/voice/command` | Transcript in → structured actions + TTS-friendly reply |
| `GET /api/v1/plan?start=&days=` | Weekly meal plan |
| `POST /api/v1/plan` | Plan a meal (`date`, `slot`, `recipe_id`/`title_override`) |
| `GET /api/v1/lists` | Shopping lists (with check-off state) |
| `POST /api/v1/lists/{id}/items` | Add item (consolidates duplicates) |
| `GET /api/v1/events?after_id=` | Event log for polling integrations |
| `GET /api/v1/export/json` | One-click JSON export |

### Voice endpoint example

```bash
curl -X POST http://localhost:8000/api/v1/voice/command \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"transcript": "add milk to my shopping list"}'
# {"reply": "Added milk to Groceries.", "actions": [{"type": "add_to_list", ...}]}
```

See `docs/API.md` for the full voice contract (including transcription-hint handling for
"LaTablée" → "la table"/"latable" satellite STT variants).

## Tests

```bash
source .venv/bin/activate && pytest backend/tests
# or the full CI-style script:
./scripts/test.sh
```

## License

AGPL-3.0 — see [LICENSE](LICENSE).