"""End-to-end test validating the complete data pipeline.

Tests the flow: Simulator (CSV → Kafka) → Consumer (Kafka → InfluxDB).
Verifies that original sensor data from Intel Lab CSV successfully persists
to InfluxDB through the Kafka message queue.
"""

import time
import threading
import logging
import pytest
from src.app.config import (
    INFLUX_URL, INFLUX_TOKEN, INFLUX_ORG, INFLUX_BUCKET,
    KAFKA_BROKER, KAFKA_TOPIC
)
from influxdb_client import InfluxDBClient

# Configure logging to see InfluxWriter logs
logging.basicConfig(level=logging.INFO, format='%(name)s - %(levelname)s - %(message)s')


def _run_simulator_safe(stop_event: threading.Event) -> None:
    """Run simulator with graceful shutdown on stop_event."""
    try:
        from src.app.simulator.orchestrator import Orchestrator
        
        print(f"Simulator: Starting orchestrator on {KAFKA_BROKER}")
        orch = Orchestrator(broker=KAFKA_BROKER, topic=KAFKA_TOPIC, max_motes=3)
        orch.start()
        print("Simulator: Orchestrator started")
        
        # Run until stop_event is set
        while not stop_event.is_set():
            time.sleep(0.5)
        
        print("Simulator: Stopping orchestrator")
        orch.stop()
        print("Simulator: Orchestrator stopped")
    except Exception as e:
        print(f"Simulator error: {e}")
        import traceback
        traceback.print_exc()


def _run_consumer_safe(stop_event: threading.Event) -> None:
    """Run consumer with graceful shutdown on stop_event."""
    try:
        from src.app.consumer.kafka_consumer import KafkaBatchConsumer
        from src.app.consumer.influx_writer import InfluxWriter
        
        consumer = KafkaBatchConsumer(
            broker=KAFKA_BROKER,
            topic=KAFKA_TOPIC,
            group_id="sieis-e2e-test",
            batch_timeout=0.5  # Short timeout to respond to stop_event quickly
        )
        writer = InfluxWriter(
            url=INFLUX_URL,
            token=INFLUX_TOKEN,
            org=INFLUX_ORG,
            bucket=INFLUX_BUCKET
        )
        
        batch_count = 0
        # Consume and write until stop_event is set
        for batch in consumer.consume_batches():
            if not batch:  # Empty batch
                if stop_event.is_set():
                    break
                continue
            
            # Print first message from first batch for debugging
            if batch_count == 0 and batch:
                print(f"Sample message: {batch[0]}")
            
            print(f"Consumer received batch of {len(batch)} messages")
            writer.write_batch(batch)
            consumer.commit()
            print(f"Wrote {len(batch)} messages to InfluxDB")
            batch_count += 1
        
        consumer.close()
        writer.close()
    except Exception as e:
        print(f"Consumer error: {e}")
        import traceback
        traceback.print_exc()


@pytest.mark.integration
def test_end_to_end_pipeline():
    """Test complete simulator → Kafka → consumer → InfluxDB pipeline.
    
    Steps:
    1. Start simulator in background thread (emits sensor data to Kafka)
    2. Start consumer in background thread (reads Kafka, writes to InfluxDB)
    3. Wait for data to flow through pipeline
    4. Query InfluxDB to verify original data persisted
    5. Assert 10+ sensor readings from multiple motes
    """
    # Flag to stop background threads
    stop_event = threading.Event()
    
    # Start simulator in background
    simulator_thread = threading.Thread(
        target=_run_simulator_safe,
        args=(stop_event,),
        daemon=True
    )
    simulator_thread.start()
    
    # Start consumer in background
    consumer_thread = threading.Thread(
        target=_run_consumer_safe,
        args=(stop_event,),
        daemon=True
    )
    consumer_thread.start()
    
    # Wait for data to flow (simulator emits, kafka queues, consumer writes)
    print("Waiting for data to flow through pipeline...")
    time.sleep(15)
    
    try:
        # Query InfluxDB for written data
        client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
        query_api = client.query_api()
        
        # Query all points from sensor_reading measurement (historical data from 2004)
        query = f"""
        from(bucket: "{INFLUX_BUCKET}")
            |> range(start: 2004-01-01T00:00:00Z, stop: 2005-01-01T00:00:00Z)
            |> filter(fn: (r) => r._measurement == "sensor_reading")
        """
        
        print(f"Querying InfluxDB...")
        result = query_api.query(query=query)
        
        # Flatten results and count points
        points = []
        for table in result:
            for record in table.records:
                points.append(record)
        
        print(f"Query returned {len(points)} points")
        for i, point in enumerate(points[:5]):  # Print first 5 for debugging
            print(f"  Point {i}: mote_id={point.values.get('mote_id')}, field={point.get_field()}, value={point.get_value()}")
        
        client.close()
        
        # Assertions
        assert len(points) >= 10, f"Expected 10+ points, got {len(points)}"
        
        # Extract mote_ids from values
        mote_ids = set()
        for point in points:
            mote_id = point.values.get("mote_id")
            if mote_id:
                mote_ids.add(mote_id)
        
        assert len(mote_ids) >= 2, f"Expected data from 2+ motes, got {len(mote_ids)}"
        
        # Verify sensor fields present
        field_names = set()
        for point in points:
            field_names.add(point.get_field())
        
        expected_fields = {"temperature", "humidity", "light", "voltage"}
        assert expected_fields.issubset(field_names), \
            f"Expected fields {expected_fields}, got {field_names}"
        
    finally:
        # Stop background threads
        print("Stopping background threads...")
        stop_event.set()
        simulator_thread.join(timeout=5)
        consumer_thread.join(timeout=5)
