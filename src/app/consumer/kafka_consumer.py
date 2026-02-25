"""Kafka consumer that batches messages for downstream processing."""

import json
import logging
import time
from typing import Dict, Iterable, List, Optional

from kafka import KafkaConsumer

logger = logging.getLogger(__name__)


class KafkaBatchConsumer:
    """Consume Kafka messages and yield them in batches."""

    def __init__(
        self,
        broker: str,
        topic: str,
        group_id: str = "sieis-consumers",
        batch_size: int = 100,
        batch_timeout: float = 1.0,
        auto_offset_reset: str = "earliest",  # "latest" caused messages to be missed if consumer starts after simulator
    ) -> None:
        self.topic = topic
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        self.consumer = KafkaConsumer(
            topic,
            bootstrap_servers=[broker],
            group_id=group_id,
            auto_offset_reset=auto_offset_reset,
            enable_auto_commit=False,
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        )

    def consume_batches(self) -> Iterable[List[Dict]]:
        """Yield message batches based on size or time window."""
        batch: List[Dict] = []
        batch_start = time.time()

        while True:
            records = self.consumer.poll(timeout_ms=100)
            for _, msgs in records.items():
                for msg in msgs:
                    if msg.value is None:
                        continue
                    batch.append(msg.value)

            now = time.time()
            if batch and (len(batch) >= self.batch_size or (now - batch_start) >= self.batch_timeout):
                yield batch
                batch = []
                batch_start = now

    def commit(self) -> None:
        """Commit current offsets after successful processing."""
        try:
            self.consumer.commit()
        except Exception:
            logger.exception("Failed to commit Kafka offsets")

    def close(self) -> None:
        try:
            self.consumer.close()
        except Exception:
            logger.exception("Failed to close Kafka consumer")
