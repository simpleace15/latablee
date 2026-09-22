# LaTablée

**Self-hosted recipe & meal planning for the whole table.** A Mealie replacement built around one
idea: the app succeeds only if it can be handed to a non-technical spouse and immediately make sense.

- 🌐 **LaTablée** (French: *the company gathered around the table*) — spoken "lah-tah-BLAY"
- 🏠 One household, multiple users, invited by link
- 📱 Mobile-first PWA — installable, works in a dead-zone grocery aisle, scales up to desktop
- 🔌 Works standalone; optional integrations attach via the versioned REST API ([API guide](docs/API.md))

## Prerequisites

- **Docker Engine 24+ with the compose plugin** (`docker compose version` to check) — that's it for deployment. Any Docker-capable host works: Unraid, Synology, a VPS, a Raspberry Pi 4+ (arm64 images build fine).
- **2 GB+ free RAM** and a few GB of disk for recipes/images.
- **A long random string for `LATABLEE_SECRET_KEY`** (the only required config): `openssl rand -hex 32`
- Optional: any **OpenAI-compatible LLM endpoint** (Ollama, llama.cpp, LocalAI, cloud) for AI features — photo import, refill-week, freeform voice. Everything else works without one.
- Developing from source instead? Python 3.12+, Node 22, and Docker for CI.

## Quickstart (Docker)

```bash
git clone https://github.com/simpleace15/latablee.git
cd latablee
cp .env.example .env          # set LATABLEE_SECRET_KEY to a long random string!
docker compose up -d
# open http://localhost:3000 — first run walks you through household setup
```

**Guides:** [Unraid deployment](docs/UNRAID.md) · [API reference](docs/API.md) ·
[Home Assistant connector](https://github.com/simpleace15/latablee-ha)

SQLite by default (zero-config). Prefer Postgres?

```bash
docker compose --profile postgres up -d
```

### Try it with demo data (optional)

On a fresh instance, any of these loads 12 sample recipes, a sample week plan, and a grocery list
(login `Admin` / `latablee-demo` — change or delete after the tour):

```bash
docker compose --profile seed run --rm seed   # CLI
# or: Settings → "Load demo data" as admin
```

Refuses to run once real data exists — it can never overwrite your household's recipes.

## Local development

```bash
# backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
uvicorn app.main:app --reload --app-dir backend   # API docs at /api/docs

# frontend
cd frontend && npm install && npm run dev
```

## What's inside

| Area | Notes |
|---|---|
| Recipes | CRUD, search, tags, photos, per-serving scaling |
| Import | Recipe URLs (schema.org/JSON-LD incl. ItemList/HowToSection shapes) + cookbook photos via any OpenAI-compatible vision model |
| Planner | Weekly calendar, breakfast/lunch/dinner slots, multi-week |
| Lists | Auto-generated from the plan, duplicate consolidation, offline check-off queue that syncs on reconnect |
| Voice | `/api/v1/voice/command`: transcript in → spoken reply + structured actions out ([contract](docs/API.md#voice-command-ha-agnostic)) |
| LLM | Any OpenAI-compatible endpoint (Ollama, llama.cpp, LocalAI, cloud) — optional; deterministic features work without it |
| PWA | Installable, app-shell cached, static export behind nginx |
| Export | JSON + full backup archive (DB + images) |

Deletes in the UI always require confirmation. Recipes imported from a URL keep a **Source**
button linking back to the original.

## The API

Versioned under `/api/v1`, OpenAPI docs at `/api/docs`, full guide with curl examples in
[docs/API.md](docs/API.md). Highlights for integrators:

| Endpoint | Purpose |
|---|---|
| `POST /api/v1/voice/command` | Transcript in → structured actions + TTS-friendly reply |
| `GET /api/v1/plan?start=&days=` | Weekly meal plan |
| `POST /api/v1/plan` | Plan a meal (`planned_date`, `slot`, `recipe_id`) |
| `GET /api/v1/lists` | Shopping lists (with check-off state) |
| `POST /api/v1/lists/{id}/items` | Add item (consolidates duplicates) |
| `POST /api/v1/import/url` / `import/photo` | Recipe import (draft for review) |
| `GET /api/v1/events?after_id=` | Event log for polling integrations |
| `GET /api/v1/export/json` · `/export/archive` | JSON export · full backup |

### Voice endpoint example

```bash
TOKEN=$(curl -fsS -X POST http://localhost:3000/api/v1/auth/token \
  -d "username=you" -d "password=***" | jq -r .access_token)

curl -sS -X POST http://localhost:3000/api/v1/voice/command \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"transcript": "add milk to my shopping list"}'
# {"reply": "Added milk to Week.", "actions": [{"type": "add_to_list", "params": {"list_id": 1, "item": "milk"}}]}
```

## Tests

```bash
source .venv/bin/activate && pytest backend/tests
# or the full CI-style script:
./scripts/test.sh
```

## License

AGPL-3.0 — see [LICENSE](LICENSE).