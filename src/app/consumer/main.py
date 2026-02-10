"""Kafka-to-InfluxDB consumer entry point."""

import logging

from src.app.config import (
    INFLUX_BUCKET,
    INFLUX_ORG,
    INFLUX_TOKEN,
    INFLUX_URL,
    KAFKA_BROKER,
    KAFKA_TOPIC,
)
from src.app.consumer.kafka_consumer import KafkaBatchConsumer
from src.app.consumer.influx_writer import InfluxWriter

logger = logging.getLogger(__name__)


def run_consumer() -> None:
    logging.basicConfig(level=logging.INFO)
    consumer = KafkaBatchConsumer(broker=KAFKA_BROKER, topic=KAFKA_TOPIC)
    writer = InfluxWriter(
        url=INFLUX_URL,
        token=INFLUX_TOKEN,
        org=INFLUX_ORG,
        bucket=INFLUX_BUCKET,
    )

    try:
        for batch in consumer.consume_batches():
            writer.write_batch(batch)
            consumer.commit()
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received - stopping consumer")
    finally:
        consumer.close()
        writer.close()


if __name__ == "__main__":
    run_consumer()
