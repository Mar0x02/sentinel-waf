from fastapi import APIRouter, Depends, Query

from app.config import Settings, get_settings
from app.schemas.stats import CountryCount, IpCount, RuleCount, SeverityCount, StatsSummary, TrendPoint
from app.services import stats_service

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/summary", response_model=StatsSummary)
def summary(settings: Settings = Depends(get_settings)):
    return stats_service.get_summary(settings)


@router.get("/top-rules", response_model=list[RuleCount])
def top_rules(limit: int = Query(10, ge=1, le=100), settings: Settings = Depends(get_settings)):
    return stats_service.get_top_rules(settings, limit)


@router.get("/top-ips", response_model=list[IpCount])
def top_ips(limit: int = Query(10, ge=1, le=100), settings: Settings = Depends(get_settings)):
    return stats_service.get_top_ips(settings, limit)


@router.get("/severity-breakdown", response_model=list[SeverityCount])
def severity_breakdown(settings: Settings = Depends(get_settings)):
    return stats_service.get_severity_breakdown(settings)


@router.get("/trend", response_model=list[TrendPoint])
def trend(settings: Settings = Depends(get_settings)):
    return stats_service.get_trend(settings)


@router.get("/countries", response_model=list[CountryCount])
def countries(limit: int = Query(50, ge=1, le=250), settings: Settings = Depends(get_settings)):
    return stats_service.get_country_counts(settings, limit)
