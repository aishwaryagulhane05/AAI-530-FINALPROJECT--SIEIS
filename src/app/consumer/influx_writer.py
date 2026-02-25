"""InfluxDB 2.x writer for sensor readings."""

import logging
from datetime import datetime
from typing import Dict, Iterable, List, Optional

from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

logger = logging.getLogger(__name__)


class InfluxWriter:
    """Write batches of sensor readings to InfluxDB 2.x."""

    def __init__(
        self,
        url: str,
        token: str,
        org: str,
        bucket: str,
        measurement: str = "sensor_reading",
    ) -> None:
        """Initialize InfluxDB 2.x writer.
        
        Args:
            url: InfluxDB URL (e.g., 'http://localhost:8086')
            token: Authentication token
            org: Organization name
            bucket: Bucket name
            measurement: Measurement name for time series data
        """
        self.org = org
        self.bucket = bucket
        self.measurement = measurement
        self.client = InfluxDBClient(url=url, token=token, org=org)
        self.write_api = self.client.write_api(write_options=SYNCHRONOUS)
        logger.info(f"InfluxDB 2.x writer initialized: url={url}, org={org}, bucket={bucket}")

    def _to_point(self, message: Dict) -> Optional[Point]:
        """Convert message dict to InfluxDB Point.
        
        Uses 'updated_timestamp' for time field (maps 2004 data to 2025+).
        """
        mote_id = message.get("mote_id")
        if mote_id is None:
            logger.warning("Message missing mote_id, skipping")
            return None

        point = Point(self.measurement).tag("mote_id", str(mote_id))

        # Add sensor fields
        field_count = 0
        for field in ("temperature", "humidity", "light", "voltage"):
            value = message.get(field)
            if value is not None:
                point = point.field(field, float(value))
                field_count += 1

        if field_count == 0:
            logger.warning(f"Message for mote {mote_id} has no valid fields")
            return None

        # Use updated_timestamp (2025+ mapped data) for InfluxDB
        ts = message.get("updated_timestamp")
        if ts is None:
            # Fallback to regular timestamp if updated_timestamp not available
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
        """Write a batch of messages to InfluxDB 3.x.
        
        Args:
            messages: Iterable of sensor reading dictionaries
        """
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
            
            # InfluxDB 2.x write API
            self.write_api.write(bucket=self.bucket, org=self.org, record=points)
            logger.info(f"Successfully wrote {len(points)} points to measurement '{self.measurement}'")
        except Exception as e:
            logger.exception(f"Failed to write batch to InfluxDB: {e}")
            # Print first point for debugging
            if points:
                logger.error(f"Sample point that failed: {points[0].to_line_protocol()}")
            raise  # Re-raise to indicate failure

    def close(self) -> None:
        """Close InfluxDB client connection."""
        try:
            self.client.close()
            logger.info("InfluxDB client closed")
        except Exception:
            logger.exception("Failed to close InfluxDB client")
