# Unraid deployment guide

LaTablée runs on Unraid two ways: **Docker Compose (recommended)** or the
**Compose Manager plugin** (Unraid 6.10+ has it built in as "Docker Compose
Manager" from the Community Apps store). Both end up with the same containers.

**Architecture: ONE container.** A single image serves the web UI *and* the
API on port 3000 (FastAPI serves the built SPA directly). The only other
container that can exist is an optional Postgres — and it's opt-in.

## Prerequisites (Unraid)

- Unraid 6.11+ with **Docker enabled** (Settings → Docker).
- The **Docker Compose Manager plugin** (Community Applications → search
  "Docker Compose") — gives you `docker compose` on Unraid.
- A share for persistent data, e.g. `appdata/latablee/`.
- 2 GB+ free RAM.

## Option A — Compose Manager plugin (UI-friendly)

1. Install **Docker Compose Manager** from Community Apps.
2. Put the compose file + .env on the flash drive or a share, e.g.
   `/boot/config/plugins/compose/latablee/docker-compose.yml` (plugin UI points
   at that path).
3. From the plugin UI: **Compose Up**. First run builds both images (~5 min).
4. Web UI: `http://<tower-ip>:3000` — first run walks through household setup.
   (First run builds one image; the Node UI build takes a few minutes.)

## Option B — plain docker compose in the shell

```bash
cd /mnt/user/appdata
git clone https://github.com/simpleace15/latablee.git latablee && cd latablee
cp .env.example .env

# generate the required secret
sed -i "s|LATABLEE_SECRET_KEY=.*|LATABLEE_SECRET_KEY=$(openssl rand -hex 32)|" .env
# point invite links at your real LAN address (important — localhost links are useless to other users)
sed -i "s|LATABLEE_PUBLIC_ORIGIN=.*|LATABLEE_PUBLIC_ORIGIN=http://<tower-ip>:3000|" .env
sed -i "s|LATABLEE_CORS_ORIGINS=.*|LATABLEE_CORS_ORIGINS=http://<tower-ip>:3000|" .env

docker compose up -d
```

Open `http://<tower-ip>:3000`. First login creates the admin account + household.

## Updating LaTablée

```bash
cd /mnt/user/appdata/latablee
git pull
docker compose build latablee
docker compose up -d latablee
```

The image is built from source (there is no Docker Hub image), so never use
"update stack"/`docker compose pull` alone — with `pull_policy: build` it now
falls back to building instead of erroring.

### Optional: Postgres instead of SQLite

```bash
docker compose --profile postgres up -d
# then in .env:
# LATABLEE_DATABASE_URL=postgresql://latablee:posablee@db:5432/latablee
```

SQLite is genuinely fine for a household — switch to Postgres if multiple
users hammer the app at once or you want DB-level tooling.

### Optional: demo data (fresh install only)

```bash
docker compose --profile seed run --rm seed
# login: Admin / latablee-demo — change or delete after the tour
```

## Data & backups

- All app data (SQLite DB + recipe images) lives in the named Docker volume
  `latablee-data` — find the physical path with
  `docker volume inspect latablee_latablee-data` (default under
  `/var/lib/docker/volumes/...` — consider the appdata share instead by
  editing the compose file to bind-mount `/mnt/user/appdata/latablee/data:/srv/latablee/data`).
- In-app backups: Settings → **Download backup** (zip with DB + images) and
  **Restore from backup** — works across machines, logins included.

## Home Assistant connector (repo 2)

Point the *LaTablée Proxy* add-on at `http://<tower-ip>:3000` (or your reverse
proxy URL), paste a device token from Settings → Device tokens, and the app
shows in the HA sidebar. Full guide: `simpleace15/latablee-ha`.

### Exposing to HA satellites / other VLANs

The compose stack binds `3000` and `8000` on all interfaces. To restrict:

```yaml
# in docker-compose.yml, under api: / web:
ports:
  - "127.0.0.1:3000:80"   # localhost only (put a reverse proxy in front)
```

Or front it with your existing reverse proxy (Nginx Proxy Manager, Traefik,
Caddy) and set `LATABLEE_PUBLIC_ORIGIN` to the public URL.
