from pydantic import BaseModel


class StatsSummary(BaseModel):
    total_requests: int
    total_blocked: int
    total_detected: int
    unique_ips: int


class RuleCount(BaseModel):
    rule_id: str
    message: str | None = None
    count: int


class IpCount(BaseModel):
    ip: str
    count: int


class SeverityCount(BaseModel):
    severity: str
    count: int


class CategoryCount(BaseModel):
    category: str
    count: int


class CategorySeries(BaseModel):
    category: str
    counts: list[int]


class CategoryTrend(BaseModel):
    buckets: list[str]
    series: list[CategorySeries]


class TrendPoint(BaseModel):
    bucket: str
    total: int
    blocked: int


class CountryCount(BaseModel):
    country_code: str
    country_name: str
    lat: float
    lng: float
    count: int
    blocked_count: int
