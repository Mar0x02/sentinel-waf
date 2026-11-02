"""Country resolution for client IPs in audit log stats.

Wraps geoip2fast, which ships its own compact offline IP->country database
inside the pip package itself - no MaxMind account/license key to set up,
no per-lookup external API call (a visitor's IP never leaves this
container, unlike calling something like ip-api.com on every stats page
load - a real concern for a security product logging attacker IPs).
Country-level only: confirmed by inspecting a real lookup() result that
this database's city/lat/lng fields are always empty, which is why
country centroids (country_centroids.py) are used for globe plotting
instead of trying to get per-request coordinates.

geoip2fast.GeoIP2Fast() loads its whole database into memory once at
import time - deliberately a module-level singleton, not constructed per
request, since re-parsing the database on every stats call would be
wasteful (lookups themselves are sub-millisecond once loaded, confirmed
locally: ~0.00005s per lookup).
"""

from functools import lru_cache

from geoip2fast import GeoIP2Fast

_geoip = GeoIP2Fast()


@lru_cache(maxsize=4096)
def lookup_country(ip: str) -> tuple[str, str] | None:
    """Returns (ISO 3166-1 alpha-2 country code, country name) for a
    public IP, or None for private/reserved/unresolvable addresses -
    confirmed geoip2fast reports those as country_code "--" rather than
    raising, so this is a simple membership check, not exception-driven."""
    result = _geoip.lookup(ip)
    if not result or not result.country_code or result.country_code == "--":
        return None
    return result.country_code, result.country_name
