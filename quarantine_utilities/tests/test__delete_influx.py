"""Script to delete all sensor data from InfluxDB.

Run this to clear test data between test runs.
Usage: python tests/test__delete_influx.py
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.app.config import INFLUX_URL, INFLUX_TOKEN, INFLUX_ORG, INFLUX_BUCKET
from influxdb_client import InfluxDBClient


def delete_all_data():
    """Delete all sensor_reading data from InfluxDB."""
    print("\n" + "="*80)
    print("🗑️  DELETING ALL DATA FROM INFLUXDB")
    print("="*80 + "\n")
    
    print(f"Configuration:")
    print(f"   • InfluxDB URL: {INFLUX_URL}")
    print(f"   • Organization: {INFLUX_ORG}")
    print(f"   • Bucket: {INFLUX_BUCKET}")
    print(f"   • Token: {INFLUX_TOKEN[:10]}...{INFLUX_TOKEN[-4:]}")
    print()
    
    try:
        client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
        delete_api = client.delete_api()
        
        print("⏳ Deleting all sensor_reading data...")
        print("   Time range: 1970-01-01 to 2099-12-31")
        print()
        
        # Delete ALL data from sensor_reading measurement
        delete_api.delete(
            start="1970-01-01T00:00:00Z",
            stop="2099-12-31T23:59:59Z",
            predicate='_measurement="sensor_reading"',
            bucket=INFLUX_BUCKET,
            org=INFLUX_ORG
        )
        
        print("✅ All sensor_reading data deleted successfully!")
        print()
        
        client.close()
        return True
        
    except Exception as e:
        print(f"❌ Error deleting data: {e}")
        print()
        import traceback
        traceback.print_exc()
        print()
        return False


def verify_empty():
    """Verify the bucket is now empty."""
    print("⏳ Verifying deletion...")
    print()
    
    try:
        client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
        query_api = client.query_api()
        
        # Count remaining points
        query = f'''
        from(bucket: "{INFLUX_BUCKET}")
          |> range(start: 1970-01-01T00:00:00Z, stop: now())
          |> filter(fn: (r) => r._measurement == "sensor_reading")
          |> count()
        '''
        
        result = query_api.query(query=query)
        
        for table in result:
            for record in table.records:
                count = record.get_value()
                if count == 0:
                    print("✅ InfluxDB bucket is now empty!")
                    print()
                    return True
                else:
                    print(f"⚠️  Warning: Found {count} data points still in bucket")
                    print()
                    return False
        
        print("✅ No data found in bucket")
        print()
        return True
        
    except Exception as e:
        print(f"⚠️  Could not verify: {e}")
        print()
        return False
        
    finally:
        client.close()


def main():
    """Run delete and verification."""
    success = delete_all_data()
    
    if success:
        verify_empty()
        
        print("="*80)
        print("✅ DELETION COMPLETE")
        print("="*80)
        print("\n💡 Ready to run fresh test: python tests\\test_end_to_end.py\n")
        return 0
    else:
        print("="*80)
        print("❌ DELETION FAILED")
        print("="*80 + "\n")
        return 1


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⚠️  Operation interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
