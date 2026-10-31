from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, error_pages, logs, rule_sets, settings_api, sites, stats
from app.auth import ensure_admin_seeded, get_current_admin
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

# /api/auth/login must stay public; every other router requires a valid
# session (see app/auth.py - Bearer JWT, checked once per request here
# rather than per-endpoint).
require_admin = [Depends(get_current_admin)]
app.include_router(auth.router)
app.include_router(rule_sets.router, dependencies=require_admin)
app.include_router(sites.router, dependencies=require_admin)
app.include_router(settings_api.router, dependencies=require_admin)
app.include_router(error_pages.router, dependencies=require_admin)
app.include_router(logs.router, dependencies=require_admin)
app.include_router(stats.router, dependencies=require_admin)


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    settings = get_settings()
    db = SessionLocal()
    try:
        ensure_admin_seeded(db)
        importer.ensure_custom_rule_set(db)
        render_service.render_all(db, settings)
    finally:
        db.close()


@app.get("/api/health")
def health():
    return {"status": "ok"}
