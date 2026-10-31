from pydantic import BaseModel


class CatalogEntry(BaseModel):
    id: str
    name: str
    version: str
    url: str
    description: str


# Curated list of known-good OWASP Core Rule Set releases (the "minimal"
# release asset - rules + crs-setup.conf.example, no docs/test suite).
# Verified against https://github.com/coreruleset/coreruleset/releases at
# the time this was written. Re-check that page when adding new entries -
# GitHub release asset URLs are stable once published, but new CRS
# versions obviously won't appear here automatically.
CRS_CATALOG: list[CatalogEntry] = [
    CatalogEntry(
        id="crs-4.30.0",
        name="OWASP Core Rule Set",
        version="4.30.0",
        url="https://github.com/coreruleset/coreruleset/releases/download/v4.30.0/coreruleset-4.30.0-minimal.tar.gz",
        description="Latest CRS 4.x stable release.",
    ),
    CatalogEntry(
        id="crs-4.29.0",
        name="OWASP Core Rule Set",
        version="4.29.0",
        url="https://github.com/coreruleset/coreruleset/releases/download/v4.29.0/coreruleset-4.29.0-minimal.tar.gz",
        description="Previous CRS 4.x stable release.",
    ),
    CatalogEntry(
        id="crs-4.28.0",
        name="OWASP Core Rule Set",
        version="4.28.0",
        url="https://github.com/coreruleset/coreruleset/releases/download/v4.28.0/coreruleset-4.28.0-minimal.tar.gz",
        description="Older CRS 4.x stable release.",
    ),
    CatalogEntry(
        id="crs-3.3.10",
        name="OWASP Core Rule Set",
        version="3.3.10",
        url="https://github.com/coreruleset/coreruleset/releases/download/v3.3.10/coreruleset-3.3.10-minimal.tar.gz",
        description="Legacy CRS 3.x branch, for compatibility with older ModSecurity setups.",
    ),
]


def get_catalog_entry(catalog_id: str) -> CatalogEntry | None:
    return next((e for e in CRS_CATALOG if e.id == catalog_id), None)
