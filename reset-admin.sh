#!/bin/sh
# Resets the dashboard admin password when you've lost it - equivalent to
# SafeLine's `docker exec safeline-mgt resetadmin`. Prints the new
# password straight to this terminal. Also signs out every other active
# session (see backend/app/auth.py's rotate_jwt_secret).
set -eu

cd "$(dirname "$0")"

docker compose exec backend python -m app.reset_admin
