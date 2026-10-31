#!/bin/sh
# Backgrounds a watcher that reloads nginx whenever the dashboard backend
# re-renders rule or site config on the shared volumes. Runs as an orphaned
# background job (standard sidecar-in-one-container pattern) since nginx
# itself becomes PID 1 right after docker-entrypoint.d finishes.
set -eu

mkdir -p /etc/modsecurity.d/dashboard-rules /etc/nginx/conf.d/dashboard-sites

# setup.conf.template's Include uses the glob dashboard-rules/*/*.conf (one
# subdirectory per rule set - see render_service.py). Unlike Apache,
# ModSecurity's Include treats a glob with zero matches as a FATAL config
# error, not a no-op - confirmed by crashing nginx outright on first boot
# before the backend has rendered anything into the fresh shared volume.
# This placeholder must therefore live one level deep too, so it always
# satisfies the glob until the backend's own render (which always writes
# zzz-overrides/000-overrides.conf unconditionally) takes over.
if [ ! -e /etc/modsecurity.d/dashboard-rules/0000-placeholder/000-placeholder.conf ]; then
  mkdir -p /etc/modsecurity.d/dashboard-rules/0000-placeholder
  echo "# Waiting for the dashboard backend to render rules" > /etc/modsecurity.d/dashboard-rules/0000-placeholder/000-placeholder.conf
fi

(
  inotifywait -m -q -e modify,create,delete,move,close_write \
    /etc/modsecurity.d/dashboard-rules /etc/nginx/conf.d/dashboard-sites 2>>/tmp/watch-reload.log |
  while read -r _; do
    # Debounce: the backend's render pass writes several files per change,
    # so wait a beat for it to finish before reloading.
    sleep 1
    if nginx -t 2>/tmp/nginx-reload-error.log; then
      nginx -s reload
      echo "$(date -Iseconds) reloaded ok" >> /tmp/watch-reload.log
    else
      echo "$(date -Iseconds) reload skipped, invalid config:" >> /tmp/watch-reload.log
      cat /tmp/nginx-reload-error.log >> /tmp/watch-reload.log
    fi
  done
) &
