"""
Verify InfluxDB has data in the sensor_data bucket.
"""
from influxdb_client import InfluxDBClient
import logging
import sys

# Force UTF-8 output to avoid encoding errors
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("InfluxDB-Verify")

INFLUXDB_URL = "http://localhost:8086"
INFLUXDB_TOKEN = "my-super-secret-token"
INFLUXDB_ORG = "sieis"
INFLUXDB_BUCKET = "sensor_data"

def check_date_range(client):
    """Check the earliest and latest timestamps in the bucket."""
    query_api = client.query_api()
    
    # Query for earliest record
    earliest_query = f'''
    from(bucket:"{INFLUXDB_BUCKET}") 
      |> range(start: 0)
      |> sort(columns: ["_time"])
      |> limit(n:1)
    '''
    
    # Query for latest record
    latest_query = f'''
    from(bucket:"{INFLUXDB_BUCKET}") 
      |> range(start: 0)
      |> sort(columns: ["_time"], desc: true)
      |> limit(n:1)
    '''
    
    try:
        logger.info("Checking date range of stored data...")
        
        earliest_tables = query_api.query(earliest_query)
        latest_tables = query_api.query(latest_query)
        
        earliest_time = None
        latest_time = None
        
        for table in earliest_tables:
            if table.records:
                earliest_time = table.records[0].get_time()
                break
        
        for table in latest_tables:
            if table.records:
                latest_time = table.records[0].get_time()
                break
        
        if earliest_time and latest_time:
            logger.info(f"📅 Date Range:")
            logger.info(f"   Earliest: {earliest_time}")
            logger.info(f"   Latest:   {latest_time}")
            logger.info(f"   Span:     {latest_time - earliest_time}")
            return earliest_time, latest_time
        else:
            logger.warning("⚠️  Could not determine date range (no data found)")
            return None, None
            
    except Exception as e:
        logger.error(f"❌ Error checking date range: {e}")
        return None, None

def main():
    logger.info(f"Connecting to InfluxDB at {INFLUXDB_URL}...")
    
    try:
        client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
        query_api = client.query_api()
        
        # First check date range
        earliest, latest = check_date_range(client)
        
        if not earliest:
            logger.warning("⚠️  No data found in InfluxDB at all!")
            logger.info("Possible reasons:")
            logger.info("  1) Consumer hasn't started yet")
            logger.info("  2) Simulator hasn't produced data")
            logger.info("  3) Check: docker logs sieis-consumer")
            client.close()
            return
        
        # Query for ALL data first (no measurement filter) to see what's there
        all_data_query = f'''
        from(bucket:"{INFLUXDB_BUCKET}") 
          |> range(start: 0)
          |> limit(n:1000)
        '''
        
        logger.info("Querying all data in bucket...")
        all_tables = query_api.query(all_data_query)
        
        # Collect measurements, fields, and other info
        total_count = 0
        mote_ids = set()
        fields = set()
        measurements = set()
        
        for table in all_tables:
            for record in table.records:
                total_count += 1
                mote_id = record.values.get("mote_id")
                field = record.get_field()
                measurement = record.get_measurement()
                
                if mote_id:
                    mote_ids.add(mote_id)
                if field:
                    fields.add(field)
                if measurement:
                    measurements.add(measurement)
        
        logger.info(f"✅ Total records (sample of 1000): {total_count:,}")
        logger.info(f"✅ Measurements found: {measurements}")
        logger.info(f"✅ Fields found: {fields}")
        
        # Get unique motes from actual data
        logger.info(f"✅ Unique motes: {len(mote_ids)}")
        if mote_ids:
            sample_motes = sorted(list(mote_ids))[:10]
            logger.info(f"   Sample: {sample_motes}")
        
        # Query for sample recent data
        query = f'''
        from(bucket:"{INFLUXDB_BUCKET}") 
          |> range(start: -24h)
          |> filter(fn: (r) => r._measurement == "sensor_reading")
          |> limit(n:5)
        '''
        
        logger.info("")
        logger.info("Querying for sample records (last 24h)...")
        tables = query_api.query(query)
        
        record_count = sum(len(table.records) for table in tables)
        
        if record_count > 0:
            logger.info(f"✅ Found {record_count} recent records")
            logger.info("Sample records:")
            for table in tables[:1]:
                for record in table.records[:3]:
                    logger.info(f"   {record.get_time()}: mote={record.values.get('mote_id')} {record.get_field()}={record.get_value()}")
        else:
            logger.warning("⚠️  No records in last 24h (but older data exists)")
        
        logger.info("")
        logger.info("✅ InfluxDB verification complete!")
        client.close()
        
    except Exception as e:
        logger.error(f"❌ Error querying InfluxDB: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()