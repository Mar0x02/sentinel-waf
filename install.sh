#!/bin/sh
# One-shot installer: starts the stack detached (docker compose up -d) and
# waits for the backend to finish its startup hook (DB connect + admin
# account seeding - see backend/app/auth.py) before printing the initial
# admin credentials straight to this terminal. `docker compose up -d` on
# its own can't do this: it returns as soon as containers are created,
# well before the app inside has even connected to Postgres, so there's
# nothing to print yet at that point - this script just waits for the
# right moment.
#
# Usage:
#   ./install.sh          - dev mode (docker-compose.yml): dashboard on
#                            :5173, API on :8000, two ports to open.
#   ./install.sh --prod   - production mode (docker-compose.prod.yml):
#                            dashboard + API both behind nginx on :8000,
#                            only one port to open. See
#                            docker-compose.prod.yml for what differs.
set -eu

cd "$(dirname "$0")"

compose_file="docker-compose.yml"
health_url="http://localhost:8000/api/health"
dashboard_url="http://localhost:5173"

if [ "${1:-}" = "--prod" ]; then
  compose_file="docker-compose.prod.yml"
  # The backend has no host-exposed port in prod mode - health-check
  # through nginx's /api/* proxy instead (same path a real login request
  # would take), not the backend directly.
  health_url="http://localhost:8000/api/health"
  dashboard_url="http://localhost:8000"
fi

# Logs persist for a container's whole lifetime, so on a rerun against an
# already-running backend `docker compose logs backend` would still
# contain the FIRST run's admin-created block - stale, and possibly wrong
# if the password's been changed since. Scoping to logs emitted from this
# invocation onward avoids ever showing a stale password.
start_time="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

echo "==> Starting Sentinel WAF (docker compose -f $compose_file up -d --build)..."
docker compose -f "$compose_file" up -d --build

echo "==> Waiting for the backend to finish starting..."
attempt=0
max_attempts=60
until curl -sf "$health_url" >/dev/null 2>&1; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge "$max_attempts" ]; then
    echo
    echo "Backend didn't respond after ${max_attempts}s. Check: docker compose -f $compose_file logs backend"
    exit 1
  fi
  sleep 1
done

echo
echo "=================================================================="
echo "  Sentinel WAF is up."
echo "=================================================================="
if docker compose -f "$compose_file" logs --since "$start_time" backend 2>/dev/null | grep -q "admin account created"; then
  docker compose -f "$compose_file" logs --since "$start_time" backend 2>/dev/null | grep -A5 "admin account created" | tail -n +2
else
  echo "  This isn't a fresh install - an admin account already exists,"
  echo "  so there's no new password to show here. If you lost it, see"
  echo "  the README for how to reset it."
fi
echo "=================================================================="
echo
echo "  Dashboard:      $dashboard_url"
echo "  WAF entrypoint: http://localhost:8080"
echo
