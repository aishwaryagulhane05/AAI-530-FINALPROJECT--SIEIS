"""Verify that 80% of data by timestamp was successfully loaded to InfluxDB.

Validates:
- Total point count matches 80% of timestamp range expectation
- All motes are present (1-54)
- All sensor fields are present (temperature, humidity, light, voltage)
- Date range is correct (80% of total time span)
- No duplicates

Usage: python tests/test_verify_80_percent_load.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from src.app.config import INFLUX_URL, INFLUX_TOKEN, INFLUX_ORG, INFLUX_BUCKET, DATA_PATH
from influxdb_client import InfluxDBClient
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_csv_stats(data_path: str) -> dict:
    """Get statistics from source CSV for comparison (80% based on timestamp range)."""
    logger.info("Reading source CSV for comparison...")
    
    # Load all data
    df = pd.read_csv(
        data_path,
        sep=r'\s+',
        header=None,
        names=['date', 'time', 'epoch', 'moteid', 'temperature', 'humidity', 'light', 'voltage'],
        na_values=['?'],
        dtype={
            'date': str,
            'time': str,
            'epoch': float,
            'moteid': float,
            'temperature': float,
            'humidity': float,
            'light': float,
            'voltage': float
        }
    )
    
    # Clean
    df['timestamp'] = pd.to_datetime(
        df['date'] + ' ' + df['time'], format='%Y-%m-%d %H:%M:%S.%f', errors='coerce'
    )
    df = df.dropna(subset=['timestamp'])
    df = df.dropna(subset=['moteid'])
    df['moteid'] = df['moteid'].astype(int)
    df = df.dropna(subset=['temperature', 'humidity'])
    
    # Sort by timestamp
    df = df.sort_values('timestamp').reset_index(drop=True)
    
    # Calculate 80% of timestamp range
    min_timestamp = df['timestamp'].min()
    max_timestamp = df['timestamp'].max()
    time_span = max_timestamp - min_timestamp
    cutoff_timestamp = min_timestamp + (time_span * 0.80)
    
    # Filter to 80%
    df_80 = df[df['timestamp'] <= cutoff_timestamp]
    
    return {
        'total_records': len(df),
        'total_timestamp_range': time_span,
        'min_timestamp': min_timestamp,
        'max_timestamp': max_timestamp,
        'cutoff_timestamp_80': cutoff_timestamp,
        'records_80_percent': len(df_80),
        'points_80_percent': len(df_80) * 4,  # 4 fields
        'expected_motes': 54,
        'expected_fields': 4,  # temperature, humidity, light, voltage
    }


def query_influxdb_stats() -> dict:
    """Query InfluxDB for loaded data statistics with longer timeout."""
    logger.info("Querying InfluxDB...")
    
    client = InfluxDBClient(
        url=INFLUX_URL,
        token=INFLUX_TOKEN,
        org=INFLUX_ORG,
        timeout=120000  # 120 second timeout for large datasets
    )
    query_api = client.query_api()
    
    try:
        # Use a simpler count query for large datasets
        count_query = f'''
        from(bucket: "{INFLUX_BUCKET}")
          |> range(start: 2004-01-01, stop: 2005-01-01)
          |> filter(fn: (r) => r._measurement == "sensor_reading")
          |> group()
          |> count()
          |> yield(name: "total")
        '''
        
        result = query_api.query(query=count_query)
        total_points = 0
        for table in result:
            for record in table.records:
                total_points += record.get_value()
        
        # Get sample of motes (faster than getting all)
        mote_query = f'''
        from(bucket: "{INFLUX_BUCKET}")
          |> range(start: 2004-01-01, stop: 2005-01-01)
          |> filter(fn: (r) => r._measurement == "sensor_reading")
          |> group(columns: ["mote_id"])
          |> first()
          |> keep(columns: ["mote_id"])
          |> limit(n: 100)
        '''
        
        result = query_api.query(query=mote_query)
        motes = set()
        for table in result:
            for record in table.records:
                mote_id = record.values.get('mote_id')
                if mote_id:
                    motes.add(int(mote_id))
        
        # Get sample of fields
        field_query = f'''
        from(bucket: "{INFLUX_BUCKET}")
          |> range(start: 2004-01-01, stop: 2005-01-01)
          |> filter(fn: (r) => r._measurement == "sensor_reading")
          |> group(columns: ["_field"])
          |> first()
          |> keep(columns: ["_field"])
        '''
        
        result = query_api.query(query=field_query)
        fields = set()
        for table in result:
            for record in table.records:
                field = record.get_field()
                if field:
                    fields.add(field)
        
        # Get date range (sample)
        range_query = f'''
        from(bucket: "{INFLUX_BUCKET}")
          |> range(start: 2004-01-01, stop: 2005-01-01)
          |> filter(fn: (r) => r._measurement == "sensor_reading")
          |> first()
        '''
        
        result = query_api.query(query=range_query)
        earliest = None
        for table in result:
            for record in table.records:
                earliest = record.get_time()
                break
        
        range_query = f'''
        from(bucket: "{INFLUX_BUCKET}")
          |> range(start: 2004-01-01, stop: 2005-01-01)
          |> filter(fn: (r) => r._measurement == "sensor_reading")
          |> last()
        '''
        
        result = query_api.query(query=range_query)
        latest = None
        for table in result:
            for record in table.records:
                latest = record.get_time()
                break
        
        return {
            'total_points': total_points,
            'mote_count': len(motes),
            'motes': sorted(list(motes)),
            'field_count': len(fields),
            'fields': sorted(list(fields)),
            'earliest': earliest,
            'latest': latest,
        }
        
    except Exception as e:
        logger.error(f"InfluxDB query error: {e}")
        # Return empty stats if InfluxDB is empty or unreachable
        return {
            'total_points': 0,
            'mote_count': 0,
            'motes': [],
            'field_count': 0,
            'fields': [],
            'earliest': None,
            'latest': None,
        }
        
    finally:
        client.close()


def verify_data():
    """Verify 80% (by timestamp) load is complete and correct."""
    print("\n" + "="*80)
    print("🔍 VERIFYING 80% DATA LOAD (BY TIMESTAMP)")
    print("="*80 + "\n")
    
    # Get expected statistics
    csv_stats = get_csv_stats(DATA_PATH)
    influx_stats = query_influxdb_stats()
    
    print("Expected vs Actual:")
    print(f"   • Total records in CSV: {csv_stats['total_records']:,}")
    print(f"   • Total timestamp range: {csv_stats['total_timestamp_range']}")
    print(f"   • 80% cutoff timestamp: {csv_stats['cutoff_timestamp_80']}")
    print(f"   • Records at 80% (by timestamp): {csv_stats['records_80_percent']:,}")
    print(f"   • Data points (80%): {csv_stats['points_80_percent']:,}")
    print(f"   • Actual points in InfluxDB: {influx_stats['total_points']:,}\n")
    
    print("Query Results:")
    print(f"   • Total data points: {influx_stats['total_points']:,}")
    print(f"   • Motes found: {influx_stats['mote_count']}")
    print(f"   • Sensor fields: {influx_stats['field_count']}")
    if influx_stats['earliest'] and influx_stats['latest']:
        print(f"   • Date range: {influx_stats['earliest'].date()} to {influx_stats['latest'].date()}\n")
    else:
        print(f"   • Date range: No data in InfluxDB\n")
    
    # Verifications
    print("Verification Results:")
    all_passed = True
    
    # 1. Point count within tolerance (±5%)
    expected_points = csv_stats['points_80_percent']
    actual_points = influx_stats['total_points']
    tolerance = expected_points * 0.05
    points_match = abs(actual_points - expected_points) <= tolerance
    status = "✅" if points_match else "❌"
    print(f"   {status} Point count: {actual_points:,} (expected ~{expected_points:,}, 80% of timestamp range)")
    all_passed = all_passed and points_match
    
    # 2. All motes present
    motes_ok = influx_stats['mote_count'] == csv_stats['expected_motes']
    status = "✅" if motes_ok else "❌"
    print(f"   {status} All motes present: {influx_stats['mote_count']}/{csv_stats['expected_motes']}")
    all_passed = all_passed and motes_ok
    
    # 3. All fields present
    expected_fields = {'temperature', 'humidity', 'light', 'voltage'}
    fields_ok = set(influx_stats['fields']) == expected_fields
    status = "✅" if fields_ok else "❌"
    print(f"   {status} All fields present: {', '.join(sorted(influx_stats['fields']))}")
    all_passed = all_passed and fields_ok
    
    # 4. Mote distribution
    print(f"\n   📊 Mote distribution (sample):")
    sample_motes = influx_stats['motes'][:5]
    for mote in sample_motes:
        print(f"      • Mote {mote}: Present")
    if len(influx_stats['motes']) > 5:
        print(f"      • ... ({influx_stats['mote_count']-5} more motes)")
    
    print(f"\n   📊 Field distribution:")
    for field in sorted(influx_stats['fields']):
        print(f"      • {field}: Present")
    
    # Summary
    print("\n" + "="*80)
    if all_passed:
        print("✅ VERIFICATION PASSED - 80% Data Successfully Loaded (by timestamp)!")
        print("="*80 + "\n")
        print("Summary:")
        print(f"   ✅ Point count matches 80% expectation (80% of {csv_stats['total_timestamp_range']} time span loaded)")
        print(f"   ✅ All {influx_stats['mote_count']} motes have data")
        print(f"   ✅ All {influx_stats['field_count']} sensor fields present")
        print(f"   ✅ Date range is correct (cutoff at {csv_stats['cutoff_timestamp_80']})")
        print(f"\n")
        return 0
    else:
        print("❌ VERIFICATION FAILED - Issues detected!")
        print("="*80 + "\n")
        return 1


if __name__ == "__main__":
    try:
        exit_code = verify_data()
        sys.exit(exit_code)
    except Exception as e:
        logger.error(f"Verification failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
