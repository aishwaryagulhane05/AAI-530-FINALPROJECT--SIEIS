"""SIEIS FastAPI application - main entry point."""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.app.api.routes import sensors, analytics, ml
from src.app import config

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info(f"🚀 SIEIS API starting — env={config.ENVIRONMENT}, influxdb={config.INFLUX_URL}")
    yield
    logger.info("SIEIS API shutting down")


app = FastAPI(
    title=config.API_TITLE,
    version=config.API_VERSION,
    description="SIEIS — Smart IoT Environmental Information System API",
    lifespan=lifespan,
)

# CORS — allow all origins for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(sensors.router, prefix="/api/v1")
app.include_router(analytics.router, prefix="/api/v1")
app.include_router(ml.router, prefix="/api/v1")


@app.get("/", tags=["root"])
def root():
    return {"message": "SIEIS API", "version": config.API_VERSION, "docs": "/docs"}


@app.get("/health", tags=["health"])
@app.get("/api/v1/health", tags=["health"])
def health():
    """Basic health check — verifies InfluxDB connectivity."""
    influx_status = "unknown"
    try:
        from influxdb_client import InfluxDBClient
        client = InfluxDBClient(
            url=config.INFLUX_URL,
            token=config.INFLUX_TOKEN,
            org=config.INFLUX_ORG,
        )
        ping_ok = client.ping()
        influx_status = "ok" if ping_ok else "error"
        client.close()
    except Exception as e:
        influx_status = f"error: {e}"

    # Check if model is loaded
    from src.app.api.routes.ml import _get_model
    model_loaded = _get_model() is not None

    status = "ok" if influx_status == "ok" else "degraded"
    return JSONResponse(
        status_code=200,
        content={
            "status": status,
            "influxdb": influx_status,
            "model_loaded": model_loaded,
            "version": config.API_VERSION,
        },
    )
