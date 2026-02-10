"""Debug test to verify InfluxDB write with actual message format."""

import pytest
from datetime import datetime
from src.app.config import INFLUX_URL, INFLUX_TOKEN, INFLUX_ORG, INFLUX_BUCKET
from src.app.consumer.influx_writer import InfluxWriter
from influxdb_client import InfluxDBClient


@pytest.mark.integration
def test_write_with_actual_message_format():
    """Test InfluxWriter with the actual message format from Kafka."""
    
    # Sample message in the format sent by emitter.py
    sample_message = {
        "mote_id": 1,
        "timestamp": "2004-02-28T00:59:16.02785",  # ISO format from emitter
        "original_timestamp": "2004-02-28T00:59:16.027850",
        "temperature": 19.9884033203125,
        "humidity": 37.0933837890625,
        "light": 45.08,
        "voltage": 2.03397,
        "epoch": 1078014923
    }
    
    print(f"Sample message: {sample_message}")
    print(f"Timestamp type: {type(sample_message['timestamp'])}")
    
    # Write to InfluxDB
    writer = InfluxWriter(
        url=INFLUX_URL,
        token=INFLUX_TOKEN,
        org=INFLUX_ORG,
        bucket=INFLUX_BUCKET
    )
    
    try:
        print("Writing message to InfluxDB...")
        writer.write_batch([sample_message])
        print("Write successful!")
    except Exception as e:
        print(f"Write failed: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        writer.close()
    
    # Query back
    client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
    query_api = client.query_api()
    
    # Query with wide time range
    query = f"""
    from(bucket: "{INFLUX_BUCKET}")
        |> range(start: 2004-01-01T00:00:00Z, stop: 2005-01-01T00:00:00Z)
        |> filter(fn: (r) => r._measurement == "sensor_reading")
        |> filter(fn: (r) => r.mote_id == "1")
    """
    
    print(f"Querying InfluxDB...")
    result = query_api.query(query=query)
    
    points = []
    for table in result:
        for record in table.records:
            points.append(record)
            print(f"Found point: time={record.get_time()}, mote_id={record.values.get('mote_id')}, "
                  f"field={record.get_field()}, value={record.get_value()}")
    
    client.close()
    
    print(f"Total points found: {len(points)}")
    assert len(points) > 0, f"Expected to find points, but got {len(points)}"
    print(f"✓ Successfully wrote and read {len(points)} points")
