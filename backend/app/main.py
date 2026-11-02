from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, discord, engine_settings, error_pages, logs, rule_sets, settings_api, sites, stats, users
from app.auth import ensure_admin_seeded, get_current_user
from app.config import get_settings
from app.db import Base, SessionLocal, engine
from app.services import importer, render_service

app = FastAPI(title="Sentinel WAF")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# /api/auth/login must stay public. Every other router requires at least
# a logged-in session (any role, including viewer) at the router level;
# routers that mix reads and writes (rule_sets, sites, settings_api,
# error_pages) additionally guard each write endpoint with
# require_write_access (admin/operator only) individually, since a
# viewer must be able to GET from those same routers - see CLAUDE.md for
# why that can't be expressed as a single router-level dependency.
# app/api/users.py is admin-only end to end, enforced in its own router.
logged_in = [Depends(get_current_user)]
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(rule_sets.router, dependencies=logged_in)
app.include_router(sites.router, dependencies=logged_in)
app.include_router(settings_api.router, dependencies=logged_in)
app.include_router(error_pages.router, dependencies=logged_in)
app.include_router(logs.router, dependencies=logged_in)
app.include_router(stats.router, dependencies=logged_in)
app.include_router(engine_settings.router, dependencies=logged_in)
app.include_router(discord.router, dependencies=logged_in)


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    settings = get_settings()
    db = SessionLocal()
    try:
        ensure_admin_seeded(db)
        importer.ensure_custom_rule_set(db)
        importer.ensure_base_tuning_rule_set(db)
        render_service.render_all(db, settings)
    finally:
        db.close()


@app.get("/api/health")
def health():
    return {"status": "ok"}
