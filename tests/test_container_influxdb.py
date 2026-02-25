"""Test InfluxDB 2.7 container functionality."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import time
from datetime import datetime, timedelta
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
from tests.test_config import INFLUX_URL, INFLUX_TOKEN, INFLUX_ORG, INFLUX_BUCKET


def test_influxdb_container():
    """Test 1: Verify InfluxDB container is running and accessible."""
    print("\n" + "="*80)
    print("TEST 1: InfluxDB Container Health Check")
    print("="*80)
    
    try:
        client = InfluxDBClient(
            url=INFLUX_URL,
            token=INFLUX_TOKEN,
            org=INFLUX_ORG,
            timeout=10000
        )
        
        health = client.health()
        print(f"✅ Connected to InfluxDB at {INFLUX_URL}")
        print(f"✅ Health status: {health.status}")
        print(f"✅ Version: {health.version}")
        
        orgs_api = client.organizations_api()
        orgs = orgs_api.find_organizations()
        org_names = [org.name for org in orgs]
        print(f"✅ Organizations: {org_names}")
        
        if INFLUX_ORG in org_names:
            print(f"✅ Target organization found: {INFLUX_ORG}")
        
        client.close()
        return True
    except Exception as e:
        print(f"❌ Failed to connect to InfluxDB: {e}")
        return False


def test_bucket_access():
    """Test 2: Verify bucket exists and is accessible."""
    print("\n" + "="*80)
    print("TEST 2: Bucket Access Verification")
    print("="*80)
    
    try:
        client = InfluxDBClient(
            url=INFLUX_URL,
            token=INFLUX_TOKEN,
            org=INFLUX_ORG
        )
        
        buckets_api = client.buckets_api()
        buckets = buckets_api.find_buckets().buckets
        bucket_names = [bucket.name for bucket in buckets]
        
        print(f"✅ Available buckets: {bucket_names}")
        
        if INFLUX_BUCKET in bucket_names:
            print(f"✅ Target bucket found: {INFLUX_BUCKET}")
            target_bucket = next(b for b in buckets if b.name == INFLUX_BUCKET)
            print(f"  - ID: {target_bucket.id}")
            print(f"  - Retention: {target_bucket.retention_rules}")
            client.close()
            return True
        else:
            print(f"❌ Target bucket not found: {INFLUX_BUCKET}")
            client.close()
            return False
    except Exception as e:
        print(f"❌ Bucket access test failed: {e}")
        return False


def test_write_query():
    """Test 3: Verify write and query operations."""
    print("\n" + "="*80)
    print("TEST 3: Write and Query Operations")
    print("="*80)
    
    try:
        client = InfluxDBClient(
            url=INFLUX_URL,
            token=INFLUX_TOKEN,
            org=INFLUX_ORG
        )
        
        write_api = client.write_api(write_options=SYNCHRONOUS)
        
        test_points = []
        now = datetime.utcnow()
        
        for i in range(5):
            point = Point("test_measurement") \
                .tag("mote_id", "999") \
                .tag("test", "true") \
                .field("temperature", 20.0 + i * 0.5) \
                .field("humidity", 50.0 + i) \
                .time(now - timedelta(minutes=i), WritePrecision.NS)
            test_points.append(point)
        
        print(f"📝 Writing {len(test_points)} test points...")
        write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=test_points)
        print("✅ Write successful")
        
        time.sleep(2)
        
        query_api = client.query_api()
        query = f'''
        from(bucket: "{INFLUX_BUCKET}")
          |> range(start: -1h)
          |> filter(fn: (r) => r._measurement == "test_measurement")
          |> filter(fn: (r) => r.mote_id == "999")
        '''
        
        print("🔍 Executing Flux query...")
        tables = query_api.query(query, org=INFLUX_ORG)
        
        record_count = 0
        for table in tables:
            for record in table.records:
                record_count += 1
                if record_count <= 3:
                    print(f"  ✅ Record: {record.get_field()} = {record.get_value()}")
        
        print(f"✅ Query returned {record_count} records")
        client.close()
        return record_count > 0
    except Exception as e:
        print(f"❌ Write/Query test failed: {e}")
        return False


def test_sensor_reading_check():
    """Test 4: Check if sensor_reading measurement has data."""
    print("\n" + "="*80)
    print("TEST 4: Sensor Reading Measurement Check")
    print("="*80)
    
    try:
        client = InfluxDBClient(
            url=INFLUX_URL,
            token=INFLUX_TOKEN,
            org=INFLUX_ORG
        )
        
        query_api = client.query_api()
        query = f'''
        from(bucket: "{INFLUX_BUCKET}")
          |> range(start: -24h)
          |> filter(fn: (r) => r._measurement == "sensor_reading")
          |> limit(n: 5)
        '''
        
        print("🔍 Checking for sensor_reading data...")
        tables = query_api.query(query, org=INFLUX_ORG)
        
        record_count = 0
        mote_ids = set()
        
        for table in tables:
            for record in table.records:
                record_count += 1
                mote_id = record.values.get("mote_id")
                if mote_id:
                    mote_ids.add(mote_id)
                if record_count <= 3:
                    print(f"  ✅ Sample: mote={mote_id}, {record.get_field()}={record.get_value():.2f}")
        
        if record_count > 0:
            print(f"✅ Found {record_count} sensor records from {len(mote_ids)} motes")
        else:
            print("⚠️  No sensor_reading data found yet (simulator may not have run)")
        
        client.close()
        return True
    except Exception as e:
        print(f"❌ Sensor data check failed: {e}")
        return False


def main():
    """Run all InfluxDB container tests."""
    print("\n" + "💾" * 40)
    print("INFLUXDB 2.7 CONTAINER TEST SUITE")
    print("💾" * 40)
    print(f"\nTarget: {INFLUX_URL}")
    print(f"Organization: {INFLUX_ORG}")
    print(f"Bucket: {INFLUX_BUCKET}")
    
    results = []
    
    results.append(("Container Health", test_influxdb_container()))
    results.append(("Bucket Access", test_bucket_access()))
    results.append(("Write/Query", test_write_query()))
    results.append(("Sensor Data Check", test_sensor_reading_check()))
    
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All InfluxDB tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
