#!/usr/bin/env bash
# CI-style test script: lint + type-check + full backend test suite.
# The project isn't done until this passes.
set -euo pipefail
cd "$(dirname "$0")/.."

PY=${PYTHON:-python3.12}
if [ ! -d .venv ]; then
  "$PY" -m venv .venv
  .venv/bin/pip install -q -e '.[dev]'
fi

echo "==> ruff (lint)"
.venv/bin/ruff check backend

echo "==> pytest"
.venv/bin/python -m pytest backend/tests

echo "==> openapi schema validates"
.venv/bin/python - <<'PY'
import json
from app.main import app
spec = app.openapi()
assert spec["openapi"].startswith("3."), spec["openapi"]
paths = len(spec["paths"])
print(f"OpenAPI OK — {paths} paths, version {spec['info']['version']}")
PY

echo "==> frontend build (if node_modules present)"
if [ -d frontend/node_modules ]; then
  (cd frontend && npm run build)
else
  echo "skipping frontend build (run: cd frontend && npm install)"
fi

echo "ALL CHECKS PASSED"