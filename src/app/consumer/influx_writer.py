"""InfluxDB writer for sensor readings."""

import logging
from datetime import datetime
from typing import Dict, Iterable, List, Optional

from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

logger = logging.getLogger(__name__)


class InfluxWriter:
    """Write batches of sensor readings to InfluxDB."""

    def __init__(
        self,
        url: str,
        token: str,
        org: str,
        bucket: str,
        measurement: str = "sensor_reading",
    ) -> None:
        self.org = org
        self.bucket = bucket
        self.measurement = measurement
        self.client = InfluxDBClient(url=url, token=token, org=org)
        self.write_api = self.client.write_api(write_options=SYNCHRONOUS)

    def _to_point(self, message: Dict) -> Optional[Point]:
        mote_id = message.get("mote_id")
        if mote_id is None:
            logger.warning("Message missing mote_id, skipping")
            return None

        point = Point(self.measurement).tag("mote_id", str(mote_id))

        # Add fields
        field_count = 0
        for field in ("temperature", "humidity", "light", "voltage"):
            value = message.get(field)
            if value is not None:
                point = point.field(field, float(value))
                field_count += 1

        if field_count == 0:
            logger.warning(f"Message for mote {mote_id} has no valid fields")
            return None

        # Parse and set timestamp
        ts = message.get("timestamp")
        if ts is not None:
            try:
                # Parse ISO format timestamp string to datetime
                if isinstance(ts, str):
                    ts = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                point = point.time(ts, WritePrecision.NS)
            except Exception as e:
                logger.error(f"Failed to parse timestamp '{ts}': {e}")
                return None

        return point

    def write_batch(self, messages: Iterable[Dict]) -> None:
        points: List[Point] = []
        skipped = 0
        
        for message in messages:
            point = self._to_point(message)
            if point is not None:
                points.append(point)
            else:
                skipped += 1

        if not points:
            logger.warning(f"No valid points to write (skipped {skipped} invalid messages)")
            return

        try:
            logger.info(f"Writing {len(points)} points to InfluxDB bucket={self.bucket}, org={self.org}, measurement={self.measurement}")
            if skipped > 0:
                logger.warning(f"Skipped {skipped} invalid messages")
            
            self.write_api.write(bucket=self.bucket, org=self.org, record=points)
            logger.info(f"Successfully wrote {len(points)} points to measurement '{self.measurement}'")
        except Exception as e:
            logger.exception(f"Failed to write batch to InfluxDB: {e}")
            # Print first point for debugging
            if points:
                logger.error(f"Sample point that failed: {points[0].to_line_protocol()}")
            raise  # Re-raise to see error in test output

    def close(self) -> None:
        try:
            self.client.close()
        except Exception:
            logger.exception("Failed to close InfluxDB client")
