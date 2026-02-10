"""Quick test: write one point to InfluxDB, query it back."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS
from src.app.config import INFLUX_URL, INFLUX_TOKEN, INFLUX_ORG, INFLUX_BUCKET

client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
print(f"Health: {client.health().status}")

# Write a test point via line protocol
w = client.write_api(write_options=SYNCHRONOUS)
line = "sensor_reading,mote_id=99 temperature=25.5,humidity=50.0,light=100.0,voltage=2.5 1078012800000000000"
try:
    w.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=line)
    print("Single write: OK")
except Exception as e:
    print(f"Single write FAILED: {e}")

# Write a batch
lines = [
    "sensor_reading,mote_id=98 temperature=20.0,humidity=40.0,light=80.0,voltage=2.3 1078012800000000000",
    "sensor_reading,mote_id=97 temperature=22.0,humidity=45.0,light=90.0,voltage=2.4 1078012900000000000",
]
try:
    w.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=lines)
    print("Batch write: OK")
except Exception as e:
    print(f"Batch write FAILED: {e}")

# Query total
q = client.query_api()
result = q.query(f'from(bucket: "{INFLUX_BUCKET}") |> range(start: 2004-01-01, stop: 2005-01-01) |> filter(fn: (r) => r._measurement == "sensor_reading") |> count()')
total = 0
for table in result:
    for record in table.records:
        total += record.get_value()
print(f"Total points in InfluxDB: {total}")

client.close()
