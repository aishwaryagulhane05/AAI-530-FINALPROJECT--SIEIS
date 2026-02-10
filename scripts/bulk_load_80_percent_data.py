"""Load 80% of CSV data by timestamp to InfluxDB.

Bypasses Kafka/Consumer pipeline for bulk data loading.
Loads data up to the timestamp that represents 80% of the total time span.

Example: If data spans 2 days (Feb 28 - Mar 1), loads data up to Mar 1 12:00 PM (80% = 1.6 days)

Usage: python scripts/load_80_percent_data.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from datetime import datetime
import logging
from src.app.config import INFLUX_URL, INFLUX_TOKEN, INFLUX_ORG, INFLUX_BUCKET, DATA_PATH, MOTE_LOCS_PATH
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
from tqdm import tqdm

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_csv_data(data_path: str, max_percent: float = 0.80) -> pd.DataFrame:
    """Load and prepare CSV data, keeping only 80% based on timestamp range."""
    logger.info(f"Loading CSV data from {data_path}")
    
    # Load all CSV data
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
    
    logger.info(f"Total records loaded: {len(df):,}")
    
    # Create timestamp
    df['timestamp'] = pd.to_datetime(
        df['date'] + ' ' + df['time'], format='%Y-%m-%d %H:%M:%S.%f', errors='coerce'
    )
    
    # Clean data
    df = df.dropna(subset=['timestamp'])
    df = df.dropna(subset=['moteid'])
    df['moteid'] = df['moteid'].astype(int)
    df = df.dropna(subset=['temperature', 'humidity'])
    df['light'] = df['light'].fillna(0.0)
    
    # Forward fill voltage
    df = df.sort_values(['moteid', 'timestamp'])
    df['voltage'] = df.groupby('moteid')['voltage'].ffill()
    df['voltage'] = df['voltage'].bfill()
    
    # Sort by timestamp for 80% calculation
    df = df.sort_values('timestamp').reset_index(drop=True)
    
    # Calculate 80% of timestamp range
    min_timestamp = df['timestamp'].min()
    max_timestamp = df['timestamp'].max()
    time_span = max_timestamp - min_timestamp
    cutoff_timestamp = min_timestamp + (time_span * max_percent)
    
    logger.info(f"Full time range: {min_timestamp} to {max_timestamp}")
    logger.info(f"Total duration: {time_span}")
    logger.info(f"80% cutoff timestamp: {cutoff_timestamp}")
    
    # Filter to 80% of timestamp range
    df = df[df['timestamp'] <= cutoff_timestamp].copy()
    
    logger.info(f"After {max_percent*100:.0f}% timestamp cutoff: {len(df):,} records")
    
    return df


def convert_to_line_protocol(df: pd.DataFrame) -> list:
    """Convert DataFrame to InfluxDB line protocol strings (much faster than Point objects)."""
    lines = []
    
    logger.info(f"Converting {len(df):,} records to InfluxDB line protocol")
    
    # Convert timestamps to nanoseconds since epoch
    timestamps_ns = df['timestamp'].astype('int64')
    
    for i in tqdm(range(len(df)), desc="Converting"):
        row = df.iloc[i]
        mote_id = int(row['moteid'])
        ts_ns = timestamps_ns.iloc[i]
        temp = float(row['temperature'])
        hum = float(row['humidity'])
        light = float(row['light'])
        volt = float(row['voltage'])
        
        line = f"sensor_reading,mote_id={mote_id} temperature={temp},humidity={hum},light={light},voltage={volt} {ts_ns}"
        lines.append(line)
    
    logger.info(f"Successfully converted {len(lines):,} lines")
    return lines


def write_to_influxdb(records: list, batch_size: int = 5000) -> int:
    """Write line protocol records to InfluxDB in batches."""
    logger.info(f"Connecting to InfluxDB at {INFLUX_URL}")
    
    client = InfluxDBClient(
        url=INFLUX_URL,
        token=INFLUX_TOKEN,
        org=INFLUX_ORG
    )
    
    write_api = client.write_api(write_options=SYNCHRONOUS)
    
    total_written = 0
    failed_batches = 0
    
    logger.info(f"Writing {len(records):,} records in batches of {batch_size}")
    
    try:
        # Write in batches
        for i in tqdm(range(0, len(records), batch_size), desc="Writing batches"):
            batch = records[i:i + batch_size]
            
            try:
                write_api.write(
                    bucket=INFLUX_BUCKET,
                    org=INFLUX_ORG,
                    record=batch
                )
                total_written += len(batch)
                
            except Exception as e:
                logger.error(f"Error writing batch {i//batch_size}: {e}")
                failed_batches += 1
                continue
        
        logger.info(f"Successfully wrote {total_written:,} points")
        if failed_batches > 0:
            logger.warning(f"{failed_batches} batches failed")
        
        return total_written
        
    finally:
        client.close()


def get_statistics(df: pd.DataFrame, total_written: int) -> dict:
    """Generate loading statistics."""
    stats = {
        'total_records': len(df),
        'total_points': total_written,
        'motes': df['moteid'].nunique(),
        'fields_per_record': 4,  # temperature, humidity, light, voltage
        'date_start': df['timestamp'].min(),
        'date_end': df['timestamp'].max(),
        'duration_days': (df['timestamp'].max() - df['timestamp'].min()).days,
    }
    
    return stats


def print_summary(stats: dict, duration_seconds: float):
    """Print loading summary."""
    print("\n" + "="*80)
    print("LOADING SUMMARY")
    print("="*80 + "\n")
    
    print("Configuration:")
    print(f"   - Source: {DATA_PATH}")
    print(f"   - Target: {INFLUX_BUCKET}@{INFLUX_URL}")
    print(f"   - Load Percentage: 80% of timestamp range\n")
    
    print("Statistics:")
    print(f"   - Records loaded: {stats['total_records']:,}")
    print(f"   - Data points written: {stats['total_points']:,}")
    print(f"   - Motes covered: {stats['motes']}")
    print(f"   - Fields per record: {stats['fields_per_record']}")
    print(f"   - Date range: {stats['date_start'].date()} to {stats['date_end'].date()}")
    print(f"   - Duration: ~{stats['duration_days']} days\n")
    
    print("Performance:")
    throughput = stats['total_points'] / duration_seconds
    print(f"   - Time taken: {duration_seconds:.1f} seconds")
    print(f"   - Throughput: {throughput:.0f} points/second")
    print(f"   - Avg per record: {stats['total_points']/stats['total_records']:.1f} points\n")
    
    print("="*80)
    print("Loading Complete!")
    print("="*80 + "\n")


def main():
    """Execute 80% data loading pipeline."""
    print("\n" + "="*80)
    print("LOADING 80% OF DATA BY TIMESTAMP TO INFLUXDB")
    print("="*80 + "\n")
    
    print("Configuration:")
    print(f"   - Source: {DATA_PATH}")
    print(f"   - Target: InfluxDB at {INFLUX_URL}")
    print(f"   - Bucket: {INFLUX_BUCKET}")
    print(f"   - Organization: {INFLUX_ORG}\n")
    
    start_time = datetime.now()
    
    try:
        # Step 1: Load CSV data (80%)
        logger.info("Step 1/3: Loading CSV data (80%)...")
        df = load_csv_data(DATA_PATH, max_percent=0.80)
        
        # Step 2: Convert to line protocol
        logger.info("Step 2/3: Converting to line protocol...")
        records = convert_to_line_protocol(df)
        
        # Step 3: Write to InfluxDB
        logger.info("Step 3/3: Writing to InfluxDB...")
        total_written = write_to_influxdb(records)
        
        # Calculate statistics
        stats = get_statistics(df, total_written)
        duration = (datetime.now() - start_time).total_seconds()
        
        # Print summary
        print_summary(stats, duration)
        
        return 0
        
    except Exception as e:
        logger.error(f"Error during loading: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\nOperation interrupted by user")
        sys.exit(1)
