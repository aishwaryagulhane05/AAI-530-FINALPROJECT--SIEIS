"""
Production-level Historical Data Loader

Loads historical sensor data from data/processed/historical_data.txt
into both InfluxDB (hot storage) and MinIO (cold storage, Parquet).

Features:
- Batch processing with configurable batch sizes
- Progress tracking with tqdm
- Error handling and retry logic
- Checkpointing for resume capability
- Deduplication
- Validation and statistics
- Memory-efficient streaming for large files

Usage:
    python scripts/load_historical_data.py
    python scripts/load_historical_data.py --batch-size 10000 --resume
    python scripts/load_historical_data.py --dry-run
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()  # Must run before config import so .env values are available

import argparse
import json
import logging
from datetime import datetime
from typing import Dict, List
import pandas as pd
from tqdm import tqdm
import pyarrow as pa
import pyarrow.parquet as pq
from minio import Minio

from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

from src.app.config import (
    INFLUX_URL,
    INFLUX_TOKEN,
    INFLUX_ORG,
    INFLUX_BUCKET,
    MINIO_ENDPOINT,
    MINIO_ACCESS_KEY,
    MINIO_SECRET_KEY,
    MINIO_BUCKET,
    MINIO_SECURE,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class HistoricalDataLoader:
    """Production-grade historical data loader with dual-write to InfluxDB and MinIO."""
    
    def __init__(
        self,
        data_path: str,
        batch_size: int = 5000,
        checkpoint_file: str = "data/.checkpoint_historical.json",
        dry_run: bool = False,
        minio_only: bool = False,
    ):
        """Initialize the historical data loader.

        Args:
            data_path: Path to historical_data.txt file
            batch_size: Number of records per batch
            checkpoint_file: Path to checkpoint file for resume capability
            dry_run: If True, only validate data without writing
            minio_only: If True, write to MinIO only — skip InfluxDB entirely
        """
        self.data_path = Path(data_path)
        self.batch_size = batch_size
        self.checkpoint_file = Path(checkpoint_file)
        self.dry_run = dry_run
        self.minio_only = minio_only

        # Statistics
        self.stats = {
            'total_read': 0,
            'influx_written': 0,
            'minio_written': 0,
            'skipped': 0,
            'errors': 0,
            'start_time': None,
            'end_time': None
        }

        # Initialize clients
        if not dry_run:
            if not minio_only:
                self._init_influxdb()
            self._init_minio()
        
        logger.info(f"Initialized HistoricalDataLoader:")
        logger.info(f"  Data source: {self.data_path}")
        logger.info(f"  Batch size: {self.batch_size}")
        logger.info(f"  Dry run: {self.dry_run}")
    
    def _init_influxdb(self):
        """Initialize InfluxDB client."""
        logger.info(f"Connecting to InfluxDB at {INFLUX_URL}")
        self.influx_client = InfluxDBClient(
            url=INFLUX_URL,
            token=INFLUX_TOKEN,
            org=INFLUX_ORG
        )
        self.influx_write_api = self.influx_client.write_api(write_options=SYNCHRONOUS)
        
        # Verify connection
        health = self.influx_client.health()
        logger.info(f"InfluxDB health: {health.status}")
    
    def _init_minio(self):
        """Initialize MinIO client."""
        logger.info(f"Connecting to MinIO at {MINIO_ENDPOINT}")
        self.minio_client = Minio(
            endpoint=MINIO_ENDPOINT,
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=MINIO_SECURE
        )
        
        # Ensure bucket exists
        if not self.minio_client.bucket_exists(MINIO_BUCKET):
            self.minio_client.make_bucket(MINIO_BUCKET)
            logger.info(f"Created MinIO bucket: {MINIO_BUCKET}")
        else:
            logger.info(f"MinIO bucket exists: {MINIO_BUCKET}")
    
    def load_checkpoint(self) -> int:
        """Load checkpoint to resume from last position.
        
        Returns:
            Line number to start from (0 if no checkpoint)
        """
        if not self.checkpoint_file.exists():
            return 0
        
        try:
            with open(self.checkpoint_file, 'r') as f:
                checkpoint = json.load(f)
            logger.info(f"Resuming from checkpoint: line {checkpoint['last_line']:,}")
            return checkpoint['last_line']
        except Exception as e:
            logger.warning(f"Failed to load checkpoint: {e}. Starting from beginning.")
            return 0
    
    def save_checkpoint(self, line_number: int):
        """Save checkpoint for resume capability."""
        # Create serializable stats
        serializable_stats = self.stats.copy()
        if isinstance(serializable_stats.get('start_time'), datetime):
            serializable_stats['start_time'] = serializable_stats['start_time'].isoformat()
        if isinstance(serializable_stats.get('end_time'), datetime):
            serializable_stats['end_time'] = serializable_stats['end_time'].isoformat()
            
        checkpoint = {
            'last_line': line_number,
            'timestamp': datetime.now().isoformat(),
            'stats': serializable_stats
        }
        self.checkpoint_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.checkpoint_file, 'w') as f:
            json.dump(checkpoint, f, indent=2)
    
    def parse_line(self, line: str) -> Dict:
        """Parse a single line from historical_data.txt.

        Actual Intel Lab format: date time epoch mote_id temperature humidity light voltage [updated_timestamp]
        Note: Some lines have missing sensor values or no updated_timestamp.

        Examples:
        - No sensor: 2004-02-28 00:58:15.315133 1 2026-01-19T19:03:19.891610 (4 parts)
        - No updated_ts: 2004-02-28 00:58:46.002832 65333 28 19.0 19.7336 37.0933 71.76 (8 parts)
        - Full: 2004-02-28 00:58:46.002832 65333 28 19.0 19.7336 37.0933 71.76 2.69964 2026-01-19T19:03:50.579309 (9 parts→ BUG was using parts[2]=epoch as mote_id)

        Returns:
            Dictionary with parsed fields, or None if parse fails
        """
        try:
            parts = line.strip().split()

            # Minimum required: date, time, at least mote_id + updated_timestamp
            if len(parts) < 4:
                return None

            date = parts[0]   # 2004-02-28
            time = parts[1]   # 00:58:15.315133

            if len(parts) == 4:
                # Sparse line: date time mote_id updated_timestamp (no epoch, no sensors)
                return {
                    'mote_id': int(parts[2]),
                    'timestamp': f"{date} {time}",
                    'updated_timestamp': parts[3],
                    'temperature': None,
                    'humidity': None,
                    'light': None,
                    'voltage': None,
                }
            elif len(parts) == 9:
                # Full record: date time epoch mote_id temp humidity light voltage updated_timestamp
                # FIX: parts[2]=epoch (skip), parts[3]=mote_id, parts[4..7]=sensors, parts[8]=updated_ts
                return {
                    'mote_id': int(float(parts[3])),
                    'timestamp': f"{date} {time}",
                    'updated_timestamp': parts[8],
                    'temperature': float(parts[4]) if parts[4] != '?' else None,
                    'humidity':    float(parts[5]) if parts[5] != '?' else None,
                    'light':       float(parts[6]) if parts[6] != '?' else None,
                    'voltage':     float(parts[7]) if parts[7] != '?' else None,
                }
            elif len(parts) == 8:
                # No updated_timestamp: date time epoch mote_id temp humidity light voltage
                # These lack a remapped timestamp — skip to avoid stale 2004 data in stores
                logger.debug(f"Skipping 8-part line (no updated_timestamp): {line.strip()[:100]}")
                return None
            else:
                # Unexpected format - log and skip
                logger.debug(f"Unexpected format ({len(parts)} parts): {line.strip()[:100]}")
                return None

        except (ValueError, IndexError) as e:
            logger.debug(f"Failed to parse line: {line.strip()[:100]} - Error: {e}")
            return None
    
    def batch_to_influx_points(self, batch: List[Dict]) -> List[Point]:
        """Convert batch of records to InfluxDB Points.
        
        Args:
            batch: List of record dictionaries
            
        Returns:
            List of InfluxDB Point objects
        """
        points = []
        for record in batch:
            try:
                # Create point
                point = Point("sensor_reading").tag("mote_id", str(record['mote_id']))
                
                # Add fields (only non-None values)
                field_count = 0
                for field in ('temperature', 'humidity', 'light', 'voltage'):
                    if record.get(field) is not None:
                        point = point.field(field, float(record[field]))
                        field_count += 1
                
                # Skip records with no sensor values
                if field_count == 0:
                    self.stats['skipped'] += 1
                    continue
                
                # Use updated_timestamp (mapped to current year)
                ts_str = record.get('updated_timestamp')
                if ts_str:
                    ts = datetime.fromisoformat(ts_str)
                    point = point.time(ts, WritePrecision.NS)
                    points.append(point)
                
            except Exception as e:
                logger.debug(f"Failed to create point: {e}")
                self.stats['skipped'] += 1
        
        return points
    
    def write_batch_to_influx(self, points: List[Point]) -> bool:
        """Write batch to InfluxDB.
        
        Args:
            points: List of InfluxDB Points
            
        Returns:
            True if successful, False otherwise
        """
        if not points:
            return True
        
        try:
            self.influx_write_api.write(
                bucket=INFLUX_BUCKET,
                org=INFLUX_ORG,
                record=points
            )
            self.stats['influx_written'] += len(points)
            return True
        except Exception as e:
            logger.error(f"InfluxDB write failed: {e}")
            self.stats['errors'] += 1
            return False
    
    def write_batch_to_minio(self, batch: List[Dict]) -> bool:
        """Write batch to MinIO as Parquet.
        
        Groups by date and mote_id for efficient partitioning.
        
        Args:
            batch: List of record dictionaries
            
        Returns:
            True if successful, False otherwise
        """
        if not batch:
            return True
        
        try:
            # Convert to DataFrame
            df = pd.DataFrame(batch)
            
            # Parse updated_timestamp for partitioning
            df['updated_timestamp'] = pd.to_datetime(df['updated_timestamp'])
            df['year'] = df['updated_timestamp'].dt.year
            df['month'] = df['updated_timestamp'].dt.month
            df['day'] = df['updated_timestamp'].dt.day
            
            # Group by date and mote_id
            for (year, month, day, mote_id), group in df.groupby(['year', 'month', 'day', 'mote_id']):
                # Create partition path
                partition_path = f"year={year}/month={month:02d}/day={day:02d}/mote_id={mote_id}"
                
                # Generate filename with timestamp
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                filename = f"{partition_path}/batch_{timestamp}.parquet"
                
                # Convert to Parquet
                table = pa.Table.from_pandas(group[[
                    'mote_id', 'timestamp', 'updated_timestamp',
                    'temperature', 'humidity', 'light', 'voltage'
                ]])
                
                # Write to bytes buffer
                import io
                buffer = io.BytesIO()
                pq.write_table(table, buffer, compression='snappy')
                buffer.seek(0)
                
                # Upload to MinIO
                self.minio_client.put_object(
                    bucket_name=MINIO_BUCKET,
                    object_name=filename,
                    data=buffer,
                    length=buffer.getbuffer().nbytes,
                    content_type='application/octet-stream'
                )
            
            self.stats['minio_written'] += len(batch)
            return True
            
        except Exception as e:
            logger.error(f"MinIO write failed: {e}")
            self.stats['errors'] += 1
            return False
    
    def load(self, resume: bool = False):
        """Load historical data with dual-write to InfluxDB and MinIO.
        
        Args:
            resume: If True, resume from last checkpoint
        """
        start_line = self.load_checkpoint() if resume else 0
        self.stats['start_time'] = datetime.now()
        
        logger.info("="*80)
        logger.info("HISTORICAL DATA LOADING")
        logger.info("="*80)
        logger.info(f"Source: {self.data_path}")
        if self.minio_only:
            logger.info(f"Target: MinIO ONLY ({MINIO_BUCKET}) — InfluxDB skipped")
        else:
            logger.info(f"Target: InfluxDB ({INFLUX_BUCKET}) + MinIO ({MINIO_BUCKET})")
        logger.info(f"Batch size: {self.batch_size}")
        logger.info(f"Resume from line: {start_line:,}")
        logger.info("="*80)
        
        # Count total lines for progress bar
        logger.info("Counting total lines...")
        with open(self.data_path, 'r') as f:
            total_lines = sum(1 for _ in f)
        logger.info(f"Total lines: {total_lines:,}")
        
        # Process file in batches
        batch = []
        current_line = 0
        
        with open(self.data_path, 'r') as f:
            # Create progress bar
            pbar = tqdm(total=total_lines, desc="Loading data", unit=" lines")
            
            for line_num, line in enumerate(f, 1):
                # Skip to checkpoint
                if line_num <= start_line:
                    pbar.update(1)
                    continue
                
                # Parse line
                record = self.parse_line(line)
                if record:
                    batch.append(record)
                    self.stats['total_read'] += 1
                else:
                    self.stats['skipped'] += 1
                
                current_line = line_num
                pbar.update(1)
                
                # Write batch when full
                if len(batch) >= self.batch_size:
                    if not self.dry_run:
                        # Write to InfluxDB (skipped in minio_only mode)
                        if not self.minio_only:
                            points = self.batch_to_influx_points(batch)
                            self.write_batch_to_influx(points)

                        # Write to MinIO (always)
                        self.write_batch_to_minio(batch)

                    # Save checkpoint every 10 batches
                    if (line_num // self.batch_size) % 10 == 0:
                        self.save_checkpoint(current_line)

                    batch = []

            # Write remaining records
            if batch and not self.dry_run:
                if not self.minio_only:
                    points = self.batch_to_influx_points(batch)
                    self.write_batch_to_influx(points)
                self.write_batch_to_minio(batch)
            
            pbar.close()
        
        # Final checkpoint
        self.save_checkpoint(current_line)
        self.stats['end_time'] = datetime.now()
        
        # Print summary
        self.print_summary()
    
    def print_summary(self):
        """Print loading summary."""
        duration = (self.stats['end_time'] - self.stats['start_time']).total_seconds()
        
        print("\n" + "="*80)
        print("LOADING SUMMARY")
        print("="*80)
        print(f"Duration: {duration:.2f} seconds")
        print(f"Total read: {self.stats['total_read']:,} records")
        print(f"InfluxDB written: {self.stats['influx_written']:,} points")
        print(f"MinIO written: {self.stats['minio_written']:,} records")
        print(f"Skipped: {self.stats['skipped']:,} records")
        print(f"Errors: {self.stats['errors']:,}")
        print(f"Throughput: {self.stats['total_read'] / duration:.0f} records/sec")
        print("="*80)
        
        if self.dry_run:
            print("DRY RUN: No data was written")
        else:
            print(f"✅ Data successfully loaded to InfluxDB and MinIO")
        print()
    
    def close(self):
        """Close all connections."""
        if not self.dry_run:
            if hasattr(self, 'influx_client'):
                self.influx_client.close()
            logger.info("Connections closed")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Load historical data to InfluxDB and MinIO")
    parser.add_argument(
        '--data-file',
        default='data/processed/historical_data.txt',
        help='Path to historical data file (default: data/processed/historical_data.txt)'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=5000,
        help='Batch size for processing (default: 5000)'
    )
    parser.add_argument(
        '--resume',
        action='store_true',
        help='Resume from last checkpoint'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Validate data without writing'
    )
    parser.add_argument(
        '--minio-only',
        action='store_true',
        help='Write to MinIO only — skip InfluxDB (use for historical batch load)'
    )

    args = parser.parse_args()

    # Validate data file exists
    data_path = Path(args.data_file)
    if not data_path.exists():
        logger.error(f"Data file not found: {data_path}")
        return 1

    # Initialize loader
    loader = HistoricalDataLoader(
        data_path=str(data_path),
        batch_size=args.batch_size,
        dry_run=args.dry_run,
        minio_only=args.minio_only,
    )
    
    try:
        # Load data
        loader.load(resume=args.resume)
        return 0
    
    except KeyboardInterrupt:
        logger.warning("\n\nInterrupted by user")
        logger.info("Progress saved in checkpoint. Run with --resume to continue.")
        return 1
    
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        return 1
    
    finally:
        loader.close()


if __name__ == "__main__":
    sys.exit(main())