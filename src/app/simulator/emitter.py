import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)


def emit_mote(mote_id: int, df, producer, speed_factor: float = 100.0, stop_event: Optional[object] = None) -> None:
    """Emit rows for a single mote DataFrame to Kafka using the provided producer.

    - `df` is expected to contain columns: `timestamp`, `epoch`, `temperature`,
      `humidity`, `light`, `voltage`.
    - `speed_factor` compresses real-time delays (delay_seconds = delta / speed_factor).
    - `stop_event` (optional) should be an object with `is_set()` method to allow graceful shutdown.
    """
    prev_ts = None
    for _, row in df.iterrows():
        if stop_event is not None and getattr(stop_event, "is_set", lambda: False)():
            logger.info("Stop event set for mote %s, exiting emitter", mote_id)
            break

        ts = row["timestamp"]
        if prev_ts is not None:
            delta = (ts - prev_ts).total_seconds()
            if delta > 0:
                delay = float(delta) / float(speed_factor)
                time.sleep(delay)

        msg = {
            "mote_id": int(mote_id),
            "timestamp": ts.isoformat(),
            "original_timestamp": ts.strftime("%Y-%m-%dT%H:%M:%S.%f"),
            "temperature": float(row.get("temperature")) if row.get("temperature") is not None else None,
            "humidity": float(row.get("humidity")) if row.get("humidity") is not None else None,
            "light": float(row.get("light")) if row.get("light") is not None else None,
            "voltage": float(row.get("voltage")) if row.get("voltage") is not None else None,
            "epoch": int(row.get("epoch")) if row.get("epoch") is not None else None,
        }

        try:
            producer.send(msg, key=mote_id)
        except Exception:
            logger.exception("Emitter failed sending message for mote %s", mote_id)

        prev_ts = ts
