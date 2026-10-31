FROM owasp/modsecurity-crs:nginx

USER root
RUN apt-get update && apt-get install -y --no-install-recommends inotify-tools && rm -rf /var/lib/apt/lists/*

# Overrides the vendor's CRS-only setup.conf: the dashboard backend is the
# single source of truth for rule content (including CRS itself), rendered
# into /etc/modsecurity.d/dashboard-rules/ - see setup.conf.template and
# CLAUDE.md.
COPY setup.conf.template /etc/nginx/templates/modsecurity.d/setup.conf.template

# Static include stub for per-site server blocks the dashboard renders
# into /etc/nginx/conf.d/dashboard-sites/ - not a template, never changes.
COPY dashboard-sites-include.conf /etc/nginx/conf.d/00-dashboard-sites.conf

COPY docker-entrypoint.d/99-watch-and-reload.sh /docker-entrypoint.d/99-watch-and-reload.sh
RUN chmod +x /docker-entrypoint.d/99-watch-and-reload.sh
