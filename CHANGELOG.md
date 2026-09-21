# Changelog

All notable changes to LaTablée are documented here. Format based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning: SemVer.

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