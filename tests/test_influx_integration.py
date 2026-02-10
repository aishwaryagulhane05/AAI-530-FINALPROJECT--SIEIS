"""Integration test for writing and reading points in InfluxDB."""

import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

from src.app.config import INFLUX_BUCKET, INFLUX_ORG, INFLUX_TOKEN, INFLUX_URL


@pytest.mark.integration
def test_influx_write_and_read_roundtrip():
    """Write a small batch and verify it can be queried."""
    client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
    if not client.ping():
        client.close()
        pytest.skip("InfluxDB not reachable")

    test_id = str(uuid.uuid4())
    measurement = "sensor_reading_test"
    now = datetime.now(timezone.utc)

    points = [
        Point(measurement)
        .tag("test_id", test_id)
        .tag("mote_id", "999")
        .field("temperature", 21.5)
        .field("humidity", 40.0)
        .time(now, WritePrecision.NS),
        Point(measurement)
        .tag("test_id", test_id)
        .tag("mote_id", "999")
        .field("temperature", 22.0)
        .field("humidity", 41.0)
        .time(now + timedelta(seconds=1), WritePrecision.NS),
    ]

    write_api = client.write_api(write_options=SYNCHRONOUS)
    write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=points)

    # Allow InfluxDB to index the points.
    time.sleep(1)

    query_api = client.query_api()
    flux = (
        f"from(bucket: \"{INFLUX_BUCKET}\")"
        f" |> range(start: -5m)"
        f" |> filter(fn: (r) => r._measurement == \"{measurement}\")"
        f" |> filter(fn: (r) => r.test_id == \"{test_id}\")"
        f" |> keep(columns: [\"_field\", \"_value\"])"
    )

    tables = query_api.query(flux)
    client.close()

    values = [record.get_value() for table in tables for record in table.records]

    assert 21.5 in values
    assert 22.0 in values
    assert 40.0 in values
    assert 41.0 in values
