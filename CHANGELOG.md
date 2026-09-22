# Changelog

All notable changes to LaTablée are documented here. Format based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning: SemVer.

## [0.4.4] — 2026-09-22

### Added
- **Multi-URL batch import.** Paste a pile of links into Import → URL; links
  are regex-extracted from surrounding text, deduped (max 20), and fetched
  one at a time. Review queue: Save & next / Skip per recipe, progress bar,
  failed-URL summary at the end. One bad link never kills the batch.
- **Admin AI diagnostics** (Settings → AI endpoint): "Test connection" with
  measured latency, recent AI-activity log (last 50 calls: kind, duration,
  errors), and an adjustable **AI timeout** setting.

### Fixed
- **"AI endpoint failed: timed out"** — the old hard-coded 60s single-float
  timeout starved local models (Ollama cold-starts and long photo-import
  reads). Timeout is now connect=10s / read=configurable (default 120s,
  Settings or `LATABLEE_LLM_TIMEOUT_SECONDS` env), with a clear error
  message telling you where to raise it.
- JSON-mode calls no longer hard-fail on local servers that ignore
  `response_format` (llama.cpp, older Ollama) — they retry with a
  plain-prompt instruction and extract the JSON from the reply.

## [0.4.3] — 2026-09-22

### Fixed
- **First account creation was broken (HTTP 422).** `/auth/register` declared
  `name`/`password`/`invite_token` as bare scalar params, which FastAPI binds
  as *query* parameters — but the UI sends a JSON body. Every first registration
  attempt failed validation. Now a `RegisterRequest` body model (same response
  shape); invite-token flow fixed with it. 5 regression tests added.
- No other endpoints had the mismatch (audited POST/PUT/PATCH handlers).

## [0.4.2] — 2026-09-22

### Changed
- **Single-container deployment** — the default now. One image serves the
  web UI *and* the API on port 3000 (FastAPI mounts the built SPA with a
  catch-all fallback registered after the API router; deep links work).
  The nginx frontend container is gone.
- New env: `LATABLEE_STATIC_DIR` — set it to serve a UI build from the API
  (the Dockerfile sets it automatically); unset keeps UI unserved.
- `Dockerfile.frontend` + `frontend/nginx.conf` removed; the Node UI build
  is a stage inside the main Dockerfile.
- Version string corrected (was reporting 0.1.0 at `/api/health`; now 0.4.2).

### For existing deployments
- `docker compose down` then `up -d` — data volume (`latablee-data`) is
  unchanged and carries over; port 3000 stays the only published port.

## [0.4.1] — 2026-09-21

### Added
- **Device tokens:** Settings → Device tokens mints long-lived `lat_…` keys for
  integrations (Home Assistant, scripts). Shown once, hashed at rest, revocable,
  last-used tracked. Accepted by every authed endpoint (JWT still primary).
- **Backup restore:** Settings → Restore from backup (admin) wipes and restores
  from a backup archive (.zip) or JSON export — with a confirm dialog. Recipes,
  plan, lists, images, and user logins (public_id + password hash) all survive
  the round trip; export now includes users + favorites + source provenance.
- **URL import fetches the image:** recipe photos are downloaded at import time
  (schema.org image first, then og:image/twitter:image) and stored locally on
  save — no more hotlinked photos that die when the source site changes.

## [0.4.0] — 2026-09-21

### Added
- **Favorites:** heart on every recipe card + recipe page, Favorites filter chip
  on the Recipes grid, `PUT /recipes/{id}/favorite`, `?favorite=1` filter.
- **One-click add to grocery list:** "Add to list" on each recipe pushes all
  ingredients, stacking compatible units (½ loaf + ½ loaf → 1 loaf) and
  attributing each line to the recipe(s) it came from — shown under the item.
- **Refill week (AI):** button on the Plan page fills empty dinner slots for
  the next 7 days — picks from your recipe book directly (favorites biased),
  and proposes brand-new dishes as review cards with one-tap "Save to book"
  (saves + books the slot). Voice: "refill my week" fast path added.
- **Food preferences in Settings:** allergies and dislikes (any user) — the
  refill/suggestion prompts treat them as hard constraints.
- SQLite fast-path column migrations at startup (is_favorite), so existing
  deployments upgrade in place without a migration tool.

## [0.3.2] — 2026-09-21

### Changed
- **Usernames are now case-insensitive.** Display case is preserved exactly as
  typed (sign-up choice), but logins match any capitalization, and duplicate
  detection is case-insensitive — "Tyler", "TYLER", and "tyler" are the same
  account; a second registration differing only by case is rejected (409).
  Names are whitespace-trimmed (max 40 chars). Login page notes the rule.

## [0.3.1] — 2026-09-21

### Added
- Sign out: button in Settings (Account card, shows signed-in name/role) and
  pinned at the bottom of the desktop sidebar. Clears the stored token and
  returns to login.

## [0.3.0] — 2026-09-21

### Added
- **Migration import** (Settings → "Import from Mealie or other apps"): upload a
  Mealie backup zip (current database.json format or legacy per-recipe folders),
  a zip of schema.org JSON-LD recipe files (Tandoor/Nextcloud exports), or a
  single recipe JSON. Recipes, photos, tags, prep/cook times (ISO-8601 parsed),
  and source links all come across. Dry-run preview before anything is written;
  admin-only (`POST /api/v1/migrate[/preview]`), documented in docs/API.md.
- Offline check-off queue: grocery check-offs made offline queue in localStorage
  and sync automatically on reconnect, with an outbox banner.
- Delete confirmations on all destructive actions (recipe, plan entry, list item).
- Source button/link preserved on URL-imported recipes (RecipeIn now persists
  source_url/source_name).
- Demo-data loading: `python -m app.seed` CLI args, `docker compose --profile
  seed run --rm seed`, and a Settings admin button (`POST /api/v1/admin/seed`).
- docs/API.md — full API guide; every curl example live-verified against a
  running stack.

### Fixed
- Recipe URL import flattened all schema.org recipeInstructions shapes (ItemList
  dicts, HowToSection groups, HowToStep dicts) — steps no longer leak schema keys
  like @type/numberOfItems/itemListElement.
- Photo-import pipeline verified end-to-end (OpenAI-compatible vision endpoint).

## [0.2.0] — 2026-09-20

### Added
- **Next.js PWA frontend** (static export, nginx-served): Today (dinner-tonight +
  list summary), Plan (weekly b/l/d slots, add-entry sheet, week nav), Recipes
  (search + tag chips, detail with servings scaling, **cook mode** with 22px steps
  and tap-advance), shopping list (check-off, fill-from-plan), Settings
  (household profile, invite link, AI endpoint config, theme, JSON export).
- **First-run onboarding wizard** — household name, allergies, dislikes,
  favorites, things-to-remember, timezone; under 2 minutes.
- Invite-link registration flow (spouse joins via link).
- PWA offline: manifest, service worker (pages/assets cache-first, API always
  network), 192/512 icons, self-hosted fonts.
- Typed API client mirroring the backend contract; nginx same-origin `/api` +
  `/images` proxy with 25 MB upload cap for photo imports.

## [0.1.1] — 2026-09-20

### Fixed
- **Postgres URL rewriting injected a literal `***` password** — `str(sqlalchemy URL)`
  masks the password; switched to `render_as_string(hide_password=False)`.
  Compose `--profile postgres` now boots and passes the full smoke suite.
- **Household-timezone date resolution** — `generate-from-plan`, plan-window defaults,
  and voice date phrases ("tonight"/"Wednesday") previously used the server's UTC date;
  now resolve against the household timezone (`app/services/dates.py`).
- **Removed btree index on JSON `tags` column** — invalid in Postgres
  (no default operator class); SQLite tolerated it, Postgres refused to create the table.

### Added
- `scripts/smoke.sh` — committed e2e smoke suite against a running API
  (health → register → onboard → recipes → search → plan → list consolidation →
  voice fast path → events → export).

## [0.1.0] — 2026-09-20

### Added
- FastAPI backend (`/api/v1`): auth (Argon2id + JWT, admin-invite-only registration),
  household onboarding, recipes CRUD/search/tags, weekly meal planner (b/l/d slots),
  shopping lists (generation from plan, unit-aware consolidation, check-off), multi-list.
- Import pipelines: URL scrape (schema.org/JSON-LD via extruct) and LLM-vision photo import —
  both return parsed drafts for review, never auto-save.
- LLM module: any OpenAI-compatible endpoint (base URL + key in admin Settings); meal
  suggestions, recipe generation, auto-tagging; fails gracefully (409) when unconfigured.
- Voice-command endpoint `POST /api/v1/voice/command`: transcript in → structured actions +
  TTS-friendly reply; wake-word fuzzy matching for "LaTablée"/"la table"/"latable";
  rule-based fast path works even with no LLM configured.
- Event log `/api/v1/events?after_id=` for polling integration clients (webhooks later).
- Data export: JSON export + full backup archive (DB + images) endpoints.
- Seed command (`python -m app.seed`) with 12 sample recipes + sample week plan.
- Docker: `docker-compose.yml` (SQLite default, `--profile postgres` optional),
  backend Dockerfile (non-root, healthcheck), frontend Dockerfile.
- Test suite: 29 integration/unit tests (auth, recipes, planner, lists, imports via fixture
  HTML, voice, LLM-mock, events); `scripts/test.sh` CI-style gate.
- AGPL-3.0 LICENSE from the first commit.