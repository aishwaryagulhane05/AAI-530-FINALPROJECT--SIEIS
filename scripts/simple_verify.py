"""Simple verification: Check if 80% bulk load succeeded."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

import pandas as pd
from src.app.config import INFLUX_URL, INFLUX_TOKEN, INFLUX_ORG, INFLUX_BUCKET, DATA_DIR
DATA_PATH = DATA_DIR / "processed" / "historical_data.txt"
from influxdb_client import InfluxDBClient

print("🔍 SIMPLE 80% DATA LOAD VERIFICATION")
print("="*50)

# Expected 80% counts
df = pd.read_csv(DATA_PATH, sep=r'\s+', header=None, 
                names=['date', 'time', 'epoch', 'moteid', 'temperature', 'humidity', 'light', 'voltage'],
                na_values=['?'])
df['timestamp'] = pd.to_datetime(df['date'] + ' ' + df['time'], format='%Y-%m-%d %H:%M:%S.%f', errors='coerce')
df = df.dropna(subset=['timestamp', 'moteid', 'temperature', 'humidity'])
df = df.sort_values('timestamp')

min_ts = df['timestamp'].min()
max_ts = df['timestamp'].max()
cutoff_ts = min_ts + (max_ts - min_ts) * 0.80
df_80 = df[df['timestamp'] <= cutoff_ts]

expected_records = len(df_80)
expected_points = expected_records * 4  # 4 fields per record

print(f"Expected from CSV (80%):")
print(f"  Records: {expected_records:,}")
print(f"  Points:  {expected_points:,}")
print(f"  Date range: {min_ts.date()} to {cutoff_ts.date()}")

# Check InfluxDB
client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG, timeout=60000)
query_api = client.query_api()

# Simple count query
result = query_api.query(f'from(bucket: "{INFLUX_BUCKET}") |> range(start: 2004-01-01, stop: 2005-01-01) |> filter(fn: (r) => r._measurement == "sensor_reading") |> count()')
total_points = sum(record.get_value() for table in result for record in table.records)

print(f"\nActual in InfluxDB:")
print(f"  Points: {total_points:,}")

# Check success
success_rate = (total_points / expected_points) * 100 if expected_points > 0 else 0
print(f"\nVerification:")
print(f"  Success rate: {success_rate:.1f}%")

if success_rate >= 95:
    print("  Status: ✅ PASSED - 80% bulk load successful!")
elif success_rate >= 80:
    print("  Status: ⚠️  PARTIAL - Most data loaded")
else:
    print("  Status: ❌ FAILED - Data load incomplete")

client.close()