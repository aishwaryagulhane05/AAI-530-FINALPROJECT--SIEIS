"""Pydantic schemas for SIEIS API request/response models."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class SensorReading(BaseModel):
    mote_id: str
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    light: Optional[float] = None
    voltage: Optional[float] = None
    timestamp: Optional[datetime] = None


class SensorQuery(BaseModel):
    mote_id: Optional[str] = None
    start: str = Field(default="-1h", description="Flux duration or ISO timestamp, e.g. '-1h', '-24h', '2026-01-01T00:00:00Z'")
    stop: str = Field(default="now()", description="Flux stop time")
    limit: int = Field(default=500, ge=1, le=10000)


class LatestReading(BaseModel):
    mote_id: str
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    light: Optional[float] = None
    voltage: Optional[float] = None
    timestamp: Optional[str] = None


class AggregatedStats(BaseModel):
    mote_id: Optional[str] = None
    metric: str
    mean: Optional[float] = None
    min: Optional[float] = None
    max: Optional[float] = None
    count: Optional[int] = None
    period: str


class AnomalyInput(BaseModel):
    temperature: float
    humidity: float
    light: float
    voltage: float
    mote_id: Optional[str] = None


class AnomalyResult(BaseModel):
    mote_id: Optional[str] = None
    anomaly_score: float
    is_anomaly: bool
    severity: str  # "normal", "warning", "critical"
    input: AnomalyInput


class HealthResponse(BaseModel):
    status: str
    influxdb: str
    model_loaded: bool
    version: str = "1.0.0"
