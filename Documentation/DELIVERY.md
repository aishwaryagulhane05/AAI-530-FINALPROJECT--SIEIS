# SIEIS Delivery Notes

## Overview
This document summarizes the current implementation, classes, functions, and tests in simple English.

## Implemented Modules

### src/app/config.py
- Purpose: Centralized configuration for local services and simulator defaults.
- Variables:
  - KAFKA_BROKER, KAFKA_TOPIC: Kafka connection settings.
  - INFLUX_URL, INFLUX_TOKEN, INFLUX_ORG, INFLUX_BUCKET: InfluxDB settings.
  - SPEED_FACTOR, DATA_PATH, MOTE_LOCS_PATH: Simulator settings.

### src/app/simulator/data_loader.py
- Purpose: Load and clean Intel Lab sensor data and mote locations.
- Functions:
  - load_data_loader(data_path, mote_locs_path)
    - Loads the sensor CSV and mote locations.
    - Cleans missing values and sorts by timestamp.
    - Returns a dictionary of per-mote DataFrames plus the locations DataFrame.
  - get_mote_data(data_path, mote_locs_path, mote_id)
    - Returns the DataFrame for a single mote.
  - get_mote_location(mote_locs_path, mote_id)
    - Returns the (x, y) location for a single mote.

### src/app/simulator/emitter.py
- Purpose: Emit per-mote readings to Kafka with time compression.
- Functions:
  - emit_mote(mote_id, df, producer, speed_factor=100.0, stop_event=None)
    - Iterates rows in timestamp order.
    - Sleeps based on delta time divided by speed_factor.
    - Sends a JSON message to Kafka for each row.
    - Stops early if stop_event is set.

### src/app/simulator/producer.py
- Purpose: Kafka producer wrapper using kafka-python.
- Class: Producer
  - __init__(broker, topic)
    - Creates the Kafka producer with JSON serialization.
    - If Kafka is unavailable, it degrades safely.
  - send(value, key=None)
    - Sends a message and waits for broker ack.
  - flush()
    - Flushes any buffered messages.
  - close()
    - Closes the underlying Kafka producer.

### src/app/simulator/orchestrator.py
- Purpose: Orchestrate per-mote emitters and producer lifecycle.
- Class: Orchestrator
  - __init__(broker, topic, max_motes=None)
    - Loads data and prepares a producer and stop event.
  - start()
    - Starts one thread per mote to emit messages.
  - stop()
    - Signals stop, joins threads, flushes and closes producer.

### src/app/simulator/main.py
- Purpose: Simulator entry point.
- Function:
  - main()
    - Starts the orchestrator and keeps the process alive.
    - Handles Ctrl+C to stop gracefully.

### src/app/simulator/simulator.py
- Purpose: Placeholder simulator module.
- Function:
  - run()
    - Prints a placeholder message.

### Package __init__.py files
- src/app/__init__.py, src/app/simulator/__init__.py, src/app/consumer/__init__.py, src/app/ml/__init__.py
- Purpose: Package markers and brief descriptions.

## Tests

### tests/test_data_loader.py
- Class: TestDataLoader
  - test_load_without_error
  - test_returns_mote_groups
  - test_each_group_sorted_by_timestamp
  - test_no_null_temperature
  - test_no_null_humidity

### tests/test_producer.py
- Class: TestProducer
  - test_producer_initializes_successfully
  - test_send_single_message
  - test_message_appears_in_kafka (integration send-only)
  - test_producer_handles_multiple_sends
  - test_producer_close_is_safe

### tests/test_orchestrator.py
- test_orchestrator_start_and_stop
- test_orchestrator_max_motes

### tests/test_placeholder.py
- test_placeholder

### test_loader_quick.py (root)
- Quick script to validate data loading speed and shape.

### test_simple.py (root)
- Simple CSV load and timestamp conversion check.

## Code Quality Review
- Positive:
  - Clear module boundaries for loader, producer, emitter, and orchestrator.
  - Safe handling of Kafka connection failures in Producer.
  - Orchestrator cleanly manages thread shutdown.
- Issues noted and addressed:
  - Unused imports were removed in tests and data loader.
  - Added concise module docstrings and small clarifying comments.
- Remaining gaps:
  - Consumer (Phase 11), ML API (Phase 12), main app entry (Phase 13), and dashboard (Phase 14) are not implemented yet.
  - Integration test that reads back from Kafka is deferred to Phase 11 consumer tests.

## How to Run Implemented Components
- Start infrastructure:
  - docker-compose up -d
- Run simulator:
  - python -m src.app.simulator.main
- Run tests:
  - python -m pytest tests/ -v

## Next Steps
- Implement Phase 11 (Kafka consumer + InfluxDB writer).
- Implement Phase 12 (ML service) and Phase 13 (main entry).
- Implement Phase 14 (dashboard).
