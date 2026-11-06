FROM owasp/modsecurity-crs:nginx

USER root
RUN apt-get update && apt-get install -y --no-install-recommends inotify-tools && rm -rf /var/lib/apt/lists/*

# Overrides the vendor's CRS-only setup.conf: the dashboard backend is the
# single source of truth for rule content (including CRS itself), rendered
# into /etc/modsecurity.d/dashboard-rules/ - see setup.conf.template and
# CLAUDE.md.
COPY setup.conf.template /etc/nginx/templates/modsecurity.d/setup.conf.template

# Overrides the vendor's own nginx.conf.template, adding load_module +
# js_import for the per-site bot challenge (Sites page toggle) - see
# njs/bot_challenge.js and render_service.py's _proxy_location(). Only
# addition versus the vendor's template; everything else kept verbatim.
COPY nginx.conf.template /etc/nginx/templates/nginx.conf.template
COPY njs/bot_challenge.js /etc/nginx/njs/bot_challenge.js
COPY docker-entrypoint.d/02-generate-challenge-secret.sh /docker-entrypoint.d/02-generate-challenge-secret.sh
RUN chmod +x /docker-entrypoint.d/02-generate-challenge-secret.sh

# Static include stub for per-site server blocks the dashboard renders
# into /etc/nginx/conf.d/dashboard-sites/ - not a template, never changes.
COPY dashboard-sites-include.conf /etc/nginx/conf.d/00-dashboard-sites.conf

# Custom block/error page wiring (error_page directives + internal
# location serving the dashboard-rendered HTML). Static, baked at build
# time - only the HTML files in the mounted volume change at runtime.
COPY error-pages.conf /etc/nginx/includes/sentinel-error-pages.conf

COPY docker-entrypoint.d/99-watch-and-reload.sh /docker-entrypoint.d/99-watch-and-reload.sh
RUN chmod +x /docker-entrypoint.d/99-watch-and-reload.sh
