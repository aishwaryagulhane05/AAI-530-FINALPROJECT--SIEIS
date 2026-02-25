"""Kafka-to-InfluxDB-and-MinIO consumer entry point with dual-write pattern."""

import logging
from minio import Minio

from src.app.config import (
    INFLUX_BUCKET,
    INFLUX_ORG,
    INFLUX_TOKEN,
    INFLUX_URL,
    KAFKA_BROKER,
    KAFKA_TOPIC,
    MINIO_ACCESS_KEY,
    MINIO_BUCKET,
    MINIO_ENDPOINT,
    MINIO_SECRET_KEY,
    MINIO_SECURE,
)
from src.app.consumer.kafka_consumer import KafkaBatchConsumer
from src.app.consumer.influx_writer import InfluxWriter
from src.app.consumer.parquet_writer import ParquetWriter

logger = logging.getLogger(__name__)


def run_consumer() -> None:
    """Run dual-write consumer: Kafka → InfluxDB (hot, real-time) + MinIO (cold, Parquet)."""
    logging.basicConfig(level=logging.INFO)
    
    # Initialize Kafka consumer
    consumer = KafkaBatchConsumer(broker=KAFKA_BROKER, topic=KAFKA_TOPIC)
    
    # Initialize InfluxDB 2.x writer (hot path - real-time queries)
    influx_writer = InfluxWriter(
        url=INFLUX_URL,
        token=INFLUX_TOKEN,
        org=INFLUX_ORG,
        bucket=INFLUX_BUCKET,
    )
    
    # Initialize MinIO client
    minio_client = Minio(
        endpoint=MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=MINIO_SECURE
    )
    
    # Initialize Parquet writer (cold path - historical archive)
    parquet_writer = ParquetWriter(
        minio_client=minio_client,
        bucket_name=MINIO_BUCKET
    )
    
    logger.info("Consumer started with dual-write pattern: InfluxDB + MinIO")
    logger.info(f"  InfluxDB: {INFLUX_URL} (org={INFLUX_ORG}, bucket={INFLUX_BUCKET})")
    logger.info(f"  MinIO: {MINIO_ENDPOINT} (bucket={MINIO_BUCKET})")

    try:
        for batch in consumer.consume_batches():
            # Dual-write pattern: write to both destinations
            influx_success = False
            parquet_success = False
            
            # Write to InfluxDB (hot path - critical for real-time dashboard)
            try:
                influx_writer.write_batch(batch)
                influx_success = True
            except Exception as e:
                logger.error(f"InfluxDB write failed: {e}")
                # Continue to try MinIO write even if InfluxDB fails
            
            # Write to MinIO (cold path - best effort, don't block on failure)
            try:
                parquet_writer.write_batch(batch)
                parquet_success = True
            except Exception as e:
                logger.warning(f"MinIO write failed (non-critical): {e}")
                # Don't block consumer on MinIO failures
            
            # Commit offset only if InfluxDB write succeeded (critical path)
            if influx_success:
                consumer.commit()
                if parquet_success:
                    logger.debug("Dual-write successful: InfluxDB + MinIO")
                else:
                    logger.warning("Partial write: InfluxDB succeeded, MinIO failed")
            else:
                logger.error("Skipping Kafka commit due to InfluxDB write failure")
                
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received - stopping consumer")
    finally:
        consumer.close()
        influx_writer.close()
        parquet_writer.close()
        logger.info("Consumer shutdown complete")


if __name__ == "__main__":
    run_consumer()
