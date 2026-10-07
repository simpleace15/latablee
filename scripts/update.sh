#!/usr/bin/env bash
# One-command update for the git-clone deploy (Compose Manager "shell route").
# Pulls latest code, rebuilds, and recreates the container. GHCR-based deploys
# should just use Unraid's "update stack" (docker compose pull) instead.
set -euo pipefail
cd "$(dirname "$0")"

echo "==> git pull"
git pull --ff-only origin main

echo "==> build"
docker compose build latablee

echo "==> swap container (down+up avoids the half-recreated-port trap)"
docker compose down --remove-orphans
docker compose up -d --no-build latablee

echo "==> verify"
sleep 5
health=$(curl -fsS http://localhost:3000/api/health)
echo "$health"
version=$(echo "$health" | sed -n 's/.*"version":"\([^"]*\)".*/\1/p')
remote=$(git describe --tags --always --dirty 2>/dev/null || git rev-parse --short HEAD)
echo "Running v${version:-?} from code ${remote:-?}"
if [ -n "${version:-}" ]; then
  echo "UPDATE OK — LaTablée is serving v$version"
else
  echo "WARNING: /api/health didn't report a version — check container logs"
  exit 1
fi