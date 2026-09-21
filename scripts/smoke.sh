#!/usr/bin/env bash
# End-to-end smoke test against a RUNNING LaTablée API (default localhost:8000).
# Exercises: health, register (first user = admin), onboarding, recipe CRUD +
# search, planner, shopping list + consolidation, voice fast path, events, export.
# Usage: BASE=http://localhost:8000 ./scripts/smoke.sh
set -euo pipefail
BASE="${BASE:-http://localhost:8000}"

if ! command -v jq >/dev/null; then
  echo "jq required (sudo apt install jq)"; exit 1
fi

fail() { echo "SMOKE FAIL: $1" >&2; exit 1; }
step() { printf "\n==> %s\n" "$1"; }

step "health"
curl -fsS "$BASE/api/health" | grep -q '"status": *"ok"' || fail "health"

step "register first user (becomes admin)"
TOKEN=$(curl -fsS -X POST "$BASE/api/v1/auth/register?name=Smoke&password=smoke-test-1234" | jq -r .token)
[ -n "$TOKEN" ] && [ "$TOKEN" != "null" ] || fail "register"
AUTH="Authorization: Bearer $TOKEN"

step "onboard household"
curl -fsS -X POST "$BASE/api/v1/household/onboard" -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"name":"Smoke Household","timezone":"America/Denver","dislikes":["olives"]}' | jq -e '.id' >/dev/null || fail "onboard"

step "create recipe (unit normalization: 500 g -> 500 gram)"
RID=$(curl -fsS -X POST "$BASE/api/v1/recipes" -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"title":"Smoke Chili","instructions":["brown","simmer"],"ingredients":[{"name":"beans","quantity":400,"unit":"g"}]}' \
  | jq -r '.id')
[ -n "$RID" ] || fail "recipe create"
curl -fsS "$BASE/api/v1/recipes/$RID" -H "$AUTH" | jq -e '.ingredients[0].unit == "gram"' >/dev/null || fail "unit normalization"

step "search"
curl -fsS "$BASE/api/v1/recipes?q=chili" -H "$AUTH" | jq -e 'length == 1' >/dev/null || fail "search"

step "plan dinner today"
TODAY=$(date +%F)
curl -fsS -X POST "$BASE/api/v1/plan" -H "$AUTH" -H "Content-Type: application/json" \
  -d "{\"date\":\"$TODAY\",\"slot\":\"dinner\",\"recipe_id\":$RID}" | jq -e '.id' >/dev/null || fail "plan add"
curl -fsS "$BASE/api/v1/plan?start=$TODAY&days=1" -H "$AUTH" | jq -e '.entries[0].recipe_title == "Smoke Chili"' >/dev/null || fail "plan query"

step "shopping list: add 500 g flour, then 1 kg -> merges to 1500 gram"
LID=$(curl -fsS -X POST "$BASE/api/v1/lists" -H "$AUTH" -H "Content-Type: application/json" -d '{"name":"Groceries"}' | jq -r .id)
curl -fsS -X POST "$BASE/api/v1/lists/$LID/items" -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"name":"flour","quantity":500,"unit":"g"}' | jq -e . >/dev/null || fail "item add"
curl -fsS -X POST "$BASE/api/v1/lists/$LID/items" -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"name":"flour","quantity":1,"unit":"kg"}' >/dev/null || fail "item add 2"
curl -fsS "$BASE/api/v1/lists/$LID" -H "$AUTH" | jq -e '[.items[] | select(.name=="flour")] | length == 1' >/dev/null || fail "consolidation merge"
curl -fsS "$BASE/api/v1/lists/$LID" -H "$AUTH" | jq -e '.items[] | select(.name=="flour") | .quantity == 1500' >/dev/null || fail "consolidation quantity"
IID=$(curl -fsS "$BASE/api/v1/lists/$LID" -H "$AUTH" | jq -r '.items[0].id')
curl -fsS -X PATCH "$BASE/api/v1/lists/$LID/items/$IID" -H "$AUTH" -H "Content-Type: application/json" -d '{"done":true}' | jq -e '.done' >/dev/null || fail "check-off"

step "generate list from plan"
curl -fsS -X POST "$BASE/api/v1/lists/$LID/generate-from-plan" -H "$AUTH" | jq -e '[.items[] | select(.name=="beans")] | length == 1' >/dev/null || fail "generate from plan"

step "voice: 'add milk to my shopping list' (no LLM needed)"
curl -fsS -X POST "$BASE/api/v1/voice/command" -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"transcript":"LaTablée, add milk to my shopping list"}' | grep -q '"Added milk' || fail "voice add"
curl -fsS -X POST "$BASE/api/v1/voice/command" -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"transcript":"what'"'"'s for dinner tonight"}' | grep -q 'Smoke Chili' || fail "voice query"

step "events log"
curl -fsS "$BASE/api/v1/events?after_id=0" -H "$AUTH" | jq -e '[.events[] | select(.event=="meal_plan_updated")] | length >= 1' >/dev/null || fail "events"

step "export JSON"
curl -fsS "$BASE/api/v1/export/json" -H "$AUTH" | jq -e '.recipes | length == 1' >/dev/null || fail "export"

echo
echo "SMOKE PASSED — all endpoints exercised against $BASE"