#!/bin/sh
# Generates the HMAC secret njs/bot_challenge.js signs challenge cookies
# with. Regenerated fresh on every container start (not persisted in a
# volume) - the only cost of that is every outstanding challenge cookie
# becomes invalid on a restart, so already-verified visitors silently redo
# the (instant, invisible-to-humans) JS challenge once. Deliberately not
# shared with the backend/Postgres: the bot challenge is a waf-engine-only
# concern, consistent with this project having no control-plane channel
# between backend and waf-engine beyond the rendered shared volumes (see
# CLAUDE.md) - this secret never needs to leave this container.
set -eu

SECRET_FILE=/etc/nginx/njs/challenge-secret
if [ ! -s "$SECRET_FILE" ]; then
  openssl rand -hex 32 > "$SECRET_FILE"
  chmod 644 "$SECRET_FILE"
fi
