"""Sensor data query endpoints - reads from InfluxDB."""

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from src.app.api.schemas import LatestReading, SensorReading
from src.app import config

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sensors", tags=["sensors"])


def _get_influx_client():
    from influxdb_client import InfluxDBClient
    return InfluxDBClient(
        url=config.INFLUX_URL,
        token=config.INFLUX_TOKEN,
        org=config.INFLUX_ORG,
    )


@router.get("/latest", response_model=List[LatestReading], summary="Get latest reading per mote")
def get_latest_readings(
    mote_id: Optional[str] = Query(default=None, description="Filter by mote ID"),
    window: str = Query(default="-1h", description="Time window, e.g. -1h, -15m, -24h"),
):
    """Return the most recent sensor reading for each mote (or a specific mote)."""
    try:
        client = _get_influx_client()
        query_api = client.query_api()

        mote_filter = f'|> filter(fn: (r) => r["mote_id"] == "{mote_id}")' if mote_id else ""

        flux = f"""
from(bucket: "{config.INFLUX_BUCKET}")
  |> range(start: {window})
  |> filter(fn: (r) => r["_measurement"] == "sensor_reading")
  {mote_filter}
  |> last()
  |> pivot(rowKey:["_time","mote_id"], columnKey: ["_field"], valueColumn: "_value")
"""
        tables = query_api.query(flux, org=config.INFLUX_ORG)
        client.close()

        results = []
        for table in tables:
            for record in table.records:
                results.append(LatestReading(
                    mote_id=record.values.get("mote_id", "unknown"),
                    temperature=record.values.get("temperature"),
                    humidity=record.values.get("humidity"),
                    light=record.values.get("light"),
                    voltage=record.values.get("voltage"),
                    timestamp=str(record.get_time()) if record.get_time() else None,
                ))
        return results
    except Exception as e:
        logger.exception("Failed to query latest readings")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history", response_model=List[SensorReading], summary="Get sensor readings over time")
def get_sensor_history(
    mote_id: str = Query(..., description="Mote ID to query"),
    start: str = Query(default="-1h", description="Start time, e.g. -1h, -24h, or ISO timestamp"),
    stop: str = Query(default="now()", description="Stop time"),
    limit: int = Query(default=500, ge=1, le=5000),
):
    """Return time-series sensor readings for a specific mote."""
    try:
        client = _get_influx_client()
        query_api = client.query_api()

        flux = f"""
from(bucket: "{config.INFLUX_BUCKET}")
  |> range(start: {start}, stop: {stop})
  |> filter(fn: (r) => r["_measurement"] == "sensor_reading")
  |> filter(fn: (r) => r["mote_id"] == "{mote_id}")
  |> pivot(rowKey:["_time","mote_id"], columnKey: ["_field"], valueColumn: "_value")
  |> limit(n: {limit})
"""
        tables = query_api.query(flux, org=config.INFLUX_ORG)
        client.close()

        results = []
        for table in tables:
            for record in table.records:
                results.append(SensorReading(
                    mote_id=record.values.get("mote_id", mote_id),
                    temperature=record.values.get("temperature"),
                    humidity=record.values.get("humidity"),
                    light=record.values.get("light"),
                    voltage=record.values.get("voltage"),
                    timestamp=record.get_time(),
                ))
        return results
    except Exception as e:
        logger.exception("Failed to query sensor history")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/motes", response_model=List[str], summary="List all active mote IDs")
def list_motes(
    window: str = Query(default="-24h", description="Time window to look for active motes"),
):
    """Return list of mote IDs that have data in the given time window."""
    try:
        client = _get_influx_client()
        query_api = client.query_api()

        flux = f"""
from(bucket: "{config.INFLUX_BUCKET}")
  |> range(start: {window})
  |> filter(fn: (r) => r["_measurement"] == "sensor_reading")
  |> keep(columns: ["mote_id"])
  |> distinct(column: "mote_id")
"""
        tables = query_api.query(flux, org=config.INFLUX_ORG)
        client.close()

        mote_ids = []
        for table in tables:
            for record in table.records:
                val = record.values.get("mote_id") or record.get_value()
                if val and val not in mote_ids:
                    mote_ids.append(str(val))
        return sorted(mote_ids)
    except Exception as e:
        logger.exception("Failed to list motes")
        raise HTTPException(status_code=500, detail=str(e))
