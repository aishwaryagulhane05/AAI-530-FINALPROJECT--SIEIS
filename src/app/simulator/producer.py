import json
import logging
from typing import Any, Optional

from kafka import KafkaProducer

logger = logging.getLogger(__name__)


class Producer:
    """Simple Kafka producer wrapper using kafka-python.

    If the broker is unavailable, sends are logged and skipped.
    """

    def __init__(self, broker: str = "localhost:9092", topic: str = "sensor_readings"):
        self.broker = broker
        self.topic = topic
        self._producer: Optional[KafkaProducer] = None
        try:
            self._producer = KafkaProducer(
                bootstrap_servers=[broker],
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                key_serializer=lambda k: str(k).encode("utf-8") if k is not None else None,
                retries=3,
                acks=1,
            )
            logger.info("Connected Kafka producer to %s", broker)
        except Exception as exc:  # pragma: no cover - runtime environment dependent
            logger.warning("Could not initialize KafkaProducer (%s); sending will be no-op", exc)
            self._producer = None

    def send(self, value: Any, key: Any = None) -> None:
        """Send a message to the configured topic. Synchronous by default.

        This method will log and return if the producer was not initialized.
        """
        if not self._producer:
            logger.debug("Producer not initialized — skipping send: %s", value)
            return

        try:
            fut = self._producer.send(self.topic, key=key, value=value)
            fut.get(timeout=10)
        except Exception:
            logger.exception("Failed to send message to Kafka: %s", value)

    def flush(self) -> None:
        if self._producer:
            try:
                self._producer.flush()
            except Exception:
                logger.exception("Kafka flush failed")

    def close(self) -> None:
        if self._producer:
            try:
                self._producer.close()
            except Exception:
                logger.exception("Kafka close failed")
