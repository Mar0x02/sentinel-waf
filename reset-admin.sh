#!/bin/sh
# Resets a dashboard user's password when it's lost - equivalent to
# SafeLine's `docker exec safeline-mgt resetadmin`. Prints the new
# password straight to this terminal. Also signs out every other active
# session (see backend/app/auth.py's rotate_jwt_secret).
#
# Usage: ./reset-admin.sh [username]   (defaults to "admin")
set -eu

cd "$(dirname "$0")"

docker compose exec backend python -m app.reset_admin "$@"
