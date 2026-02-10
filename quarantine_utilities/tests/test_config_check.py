"""Configuration and connectivity check for SIEIS pipeline.

Run this before test_end_to_end.py to verify:
- Configuration values are loaded
- InfluxDB is reachable
- Kafka is reachable
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.app.config import (
    INFLUX_URL, INFLUX_TOKEN, INFLUX_ORG, INFLUX_BUCKET,
    KAFKA_BROKER, KAFKA_TOPIC
)


def check_config():
    """Display configuration values."""
    print("\n" + "="*80)
    print("🔍 SIEIS CONFIGURATION CHECK")
    print("="*80 + "\n")
    
    print("📡 Kafka Configuration:")
    print(f"   • Broker: {KAFKA_BROKER}")
    print(f"   • Topic: {KAFKA_TOPIC}")
    print()
    
    print("💾 InfluxDB Configuration:")
    print(f"   • URL: {INFLUX_URL}")
    print(f"   • Organization: {INFLUX_ORG}")
    print(f"   • Bucket: {INFLUX_BUCKET}")
    print(f"   • Token: {INFLUX_TOKEN[:10]}...{INFLUX_TOKEN[-4:]}")
    print()


def check_influx():
    """Test InfluxDB connectivity."""
    print("🔌 Testing InfluxDB Connection...")
    try:
        from influxdb_client import InfluxDBClient
        client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
        health = client.health()
        
        if health.status == "pass":
            print(f"   ✅ InfluxDB Status: {health.status}")
            print(f"   ✅ Version: {health.version}")
            
            # Check bucket exists
            buckets_api = client.buckets_api()
            bucket = buckets_api.find_bucket_by_name(INFLUX_BUCKET)
            if bucket:
                print(f"   ✅ Bucket '{INFLUX_BUCKET}' exists")
            else:
                print(f"   ⚠️  Bucket '{INFLUX_BUCKET}' not found (will be created on first write)")
        else:
            print(f"   ❌ InfluxDB Status: {health.status}")
            return False
            
        client.close()
        return True
        
    except Exception as e:
        print(f"   ❌ InfluxDB Connection Failed!")
        print(f"   Error: {e}")
        return False


def check_kafka():
    """Test Kafka connectivity."""
    print("\n🔌 Testing Kafka Connection...")
    try:
        from kafka import KafkaProducer
        from kafka.errors import NoBrokersAvailable
        
        producer = KafkaProducer(
            bootstrap_servers=KAFKA_BROKER,
            request_timeout_ms=5000,
            api_version_auto_timeout_ms=5000
        )
        
        print(f"   ✅ Kafka connected successfully")
        print(f"   ✅ Broker: {KAFKA_BROKER}")
        
        producer.close()
        return True
        
    except NoBrokersAvailable:
        print(f"   ❌ No Kafka brokers available at {KAFKA_BROKER}")
        print(f"   💡 Make sure Docker containers are running: docker-compose up -d")
        return False
        
    except Exception as e:
        print(f"   ❌ Kafka Connection Failed!")
        print(f"   Error: {e}")
        return False


def check_data_files():
    """Check if data files exist."""
    print("\n📁 Checking Data Files...")
    
    data_file = Path(__file__).parent.parent / "data" / "raw" / "data.txt"
    mote_file = Path(__file__).parent.parent / "data" / "raw" / "mote_locs.txt"
    
    if data_file.exists():
        print(f"   ✅ data.txt found ({data_file.stat().st_size:,} bytes)")
    else:
        print(f"   ❌ data.txt not found at {data_file}")
        return False
    
    if mote_file.exists():
        print(f"   ✅ mote_locs.txt found ({mote_file.stat().st_size:,} bytes)")
    else:
        print(f"   ❌ mote_locs.txt not found at {mote_file}")
        return False
    
    return True


def main():
    """Run all configuration checks."""
    check_config()
    
    influx_ok = check_influx()
    kafka_ok = check_kafka()
    data_ok = check_data_files()
    
    print("\n" + "="*80)
    
    if influx_ok and kafka_ok and data_ok:
        print("✅ ALL CHECKS PASSED - Ready to run end-to-end test!")
        print("="*80)
        print("\n💡 Next step: python tests\\test_end_to_end.py\n")
        return 0
    else:
        print("❌ SOME CHECKS FAILED - Fix issues before running tests")
        print("="*80)
        print("\n💡 Troubleshooting:")
        if not kafka_ok or not influx_ok:
            print("   1. Start Docker containers: docker-compose up -d")
            print("   2. Wait 10 seconds for services to initialize")
            print("   3. Run this check again")
        if not data_ok:
            print("   1. Ensure data files are in data/raw/ directory")
        print()
        return 1


if __name__ == "__main__":
    import sys
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⚠️  Check interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Check failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
