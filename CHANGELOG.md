# Changelog

All notable changes to LaTablée are documented here. Format based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning: SemVer.

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