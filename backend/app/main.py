from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import logs, rule_sets, settings_api, sites, stats
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

app.include_router(rule_sets.router)
app.include_router(sites.router)
app.include_router(settings_api.router)
app.include_router(logs.router)
app.include_router(stats.router)


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    settings = get_settings()
    db = SessionLocal()
    try:
        importer.ensure_custom_rule_set(db)
        render_service.render_all(db, settings)
    finally:
        db.close()


@app.get("/api/health")
def health():
    return {"status": "ok"}
