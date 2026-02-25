"""Analytics endpoints - aggregations, trends, statistics."""

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from src.app.api.schemas import AggregatedStats
from src.app import config

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analytics", tags=["analytics"])


def _get_influx_client():
    from influxdb_client import InfluxDBClient
    return InfluxDBClient(
        url=config.INFLUX_URL,
        token=config.INFLUX_TOKEN,
        org=config.INFLUX_ORG,
    )


@router.get("/summary", summary="Get aggregated stats for a metric")
def get_summary(
    metric: str = Query(..., description="Sensor metric: temperature, humidity, light, voltage"),
    mote_id: Optional[str] = Query(default=None, description="Filter by mote ID (optional)"),
    start: str = Query(default="-24h", description="Start time"),
):
    """Return mean, min, max for a given sensor metric over a time window."""
    valid_metrics = {"temperature", "humidity", "light", "voltage"}
    if metric not in valid_metrics:
        raise HTTPException(status_code=400, detail=f"metric must be one of {valid_metrics}")

    try:
        client = _get_influx_client()
        query_api = client.query_api()
        mote_filter = f'|> filter(fn: (r) => r["mote_id"] == "{mote_id}")' if mote_id else ""

        flux = f"""
from(bucket: "{config.INFLUX_BUCKET}")
  |> range(start: {start})
  |> filter(fn: (r) => r["_measurement"] == "sensor_reading")
  |> filter(fn: (r) => r["_field"] == "{metric}")
  {mote_filter}
"""
        tables = query_api.query(flux, org=config.INFLUX_ORG)

        values = []
        for table in tables:
            for record in table.records:
                v = record.get_value()
                if v is not None:
                    values.append(float(v))

        client.close()

        if not values:
            return AggregatedStats(
                mote_id=mote_id, metric=metric,
                mean=None, min=None, max=None, count=0, period=start
            )

        return AggregatedStats(
            mote_id=mote_id,
            metric=metric,
            mean=round(sum(values) / len(values), 4),
            min=round(min(values), 4),
            max=round(max(values), 4),
            count=len(values),
            period=start,
        )
    except Exception as e:
        logger.exception("Failed to compute summary")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/active-motes-count", summary="Count active motes in last 15 minutes")
def active_motes_count():
    """Return count of motes that reported data in the last 15 minutes."""
    try:
        client = _get_influx_client()
        query_api = client.query_api()

        flux = f"""
from(bucket: "{config.INFLUX_BUCKET}")
  |> range(start: -15m)
  |> filter(fn: (r) => r["_measurement"] == "sensor_reading")
  |> keep(columns: ["mote_id"])
  |> distinct(column: "mote_id")
  |> count()
"""
        tables = query_api.query(flux, org=config.INFLUX_ORG)
        client.close()

        count = 0
        for table in tables:
            for record in table.records:
                count = record.get_value() or 0
        return {"active_motes_last_15m": int(count)}
    except Exception as e:
        logger.exception("Failed to count active motes")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ingestion-rate", summary="Messages ingested per minute (last 5m)")
def ingestion_rate():
    """Return approximate records-per-minute ingestion rate."""
    try:
        client = _get_influx_client()
        query_api = client.query_api()

        flux = f"""
from(bucket: "{config.INFLUX_BUCKET}")
  |> range(start: -5m)
  |> filter(fn: (r) => r["_measurement"] == "sensor_reading")
  |> filter(fn: (r) => r["_field"] == "temperature")
  |> count()
"""
        tables = query_api.query(flux, org=config.INFLUX_ORG)
        client.close()

        total = 0
        for table in tables:
            for record in table.records:
                total += record.get_value() or 0
        rate = round(total / 5.0, 2)
        return {"records_per_minute": rate, "total_last_5m": total}
    except Exception as e:
        logger.exception("Failed to compute ingestion rate")
        raise HTTPException(status_code=500, detail=str(e))
