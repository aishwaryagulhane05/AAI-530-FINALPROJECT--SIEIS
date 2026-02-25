"""MinIO Parquet writer for historical sensor data archive."""

import logging
import hashlib
from io import BytesIO
from typing import Dict, List, Set, Tuple
from datetime import datetime, timezone

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from minio import Minio
from minio.error import S3Error

logger = logging.getLogger(__name__)


class ParquetWriter:
    """Write sensor data batches to MinIO as Parquet files with date partitioning."""

    def __init__(self, minio_client: Minio, bucket_name: str, enable_deduplication: bool = True) -> None:
        """Initialize ParquetWriter with MinIO client.
        
        Args:
            minio_client: Initialized MinIO client
            bucket_name: Target bucket name (e.g., 'sieis-archive')
            enable_deduplication: Enable in-memory deduplication of messages (default: True)
        """
        self.minio_client = minio_client
        self.bucket_name = bucket_name
        self.enable_deduplication = enable_deduplication
        
        # In-memory cache of seen (mote_id, timestamp) pairs for deduplication
        self._seen_keys: Set[Tuple[int, str]] = set()
        
        # Ensure bucket exists
        if not self.minio_client.bucket_exists(bucket_name):
            logger.warning(f"Bucket '{bucket_name}' does not exist, attempting to create")
            try:
                self.minio_client.make_bucket(bucket_name)
                logger.info(f"Created bucket '{bucket_name}'")
            except Exception as e:
                logger.error(f"Failed to create bucket '{bucket_name}': {e}")
                raise

    def _deduplicate_messages(self, messages: List[Dict]) -> List[Dict]:
        """Remove duplicate messages based on (mote_id, timestamp) key.
        
        Args:
            messages: List of sensor reading dictionaries
            
        Returns:
            Deduplicated list of messages
        """
        if not self.enable_deduplication:
            return messages
            
        deduplicated = []
        initial_count = len(messages)
        
        for msg in messages:
            # Use updated_timestamp if available, otherwise regular timestamp
            ts = msg.get("updated_timestamp") or msg.get("timestamp")
            if ts is None:
                logger.warning(f"Message missing timestamp, including anyway: {msg}")
                deduplicated.append(msg)
                continue
                
            key = (msg.get("mote_id"), str(ts))
            if key not in self._seen_keys:
                self._seen_keys.add(key)
                deduplicated.append(msg)
        
        if initial_count > len(deduplicated):
            logger.info(f"Deduplicated {initial_count - len(deduplicated)} duplicate messages")
            
        return deduplicated
    
    def clear_deduplication_cache(self) -> None:
        """Clear the in-memory deduplication cache.
        
        Call this periodically to prevent unbounded memory growth in long-running processes.
        """
        logger.info(f"Clearing deduplication cache ({len(self._seen_keys)} entries)")
        self._seen_keys.clear()

    def write_batch(self, messages: List[Dict]) -> None:
        """Convert message batch to Parquet and upload to MinIO.
        
        Messages are partitioned by date extracted from updated_timestamp.
        File path structure: year=YYYY/month=MM/day=DD/mote_id=X/batch_TIMESTAMP.parquet
        
        Uses deterministic filenames based on content to ensure idempotency.
        Deduplicates messages to prevent duplicate data.
        
        Args:
            messages: List of sensor reading dictionaries
        """
        if not messages:
            logger.warning("Empty batch provided to ParquetWriter, skipping")
            return

        try:
            # Deduplicate messages first
            messages = self._deduplicate_messages(messages)
            
            if not messages:
                logger.info("All messages were duplicates, skipping write")
                return
            
            # Convert to DataFrame
            df = pd.DataFrame(messages)
            
            # Parse updated_timestamp for partitioning
            if "updated_timestamp" not in df.columns:
                logger.error("Messages missing 'updated_timestamp' field, cannot partition")
                return
                
            df["updated_timestamp"] = pd.to_datetime(df["updated_timestamp"])
            
            # Extract partition columns
            df["year"] = df["updated_timestamp"].dt.year
            df["month"] = df["updated_timestamp"].dt.month.astype(str).str.zfill(2)
            df["day"] = df["updated_timestamp"].dt.day.astype(str).str.zfill(2)
            
            # Group by partition and mote_id for efficient storage
            grouped = df.groupby(["year", "month", "day", "mote_id"])
            
            upload_count = 0
            skipped_count = 0
            for (year, month, day, mote_id), group in grouped:
                try:
                    # Create deterministic filename based on content (idempotent)
                    min_ts = group["updated_timestamp"].min().strftime("%Y%m%d_%H%M%S")
                    max_ts = group["updated_timestamp"].max().strftime("%Y%m%d_%H%M%S")
                    record_count = len(group)
                    
                    # Create content hash for additional uniqueness (in case same time range)
                    content_str = f"{min_ts}_{max_ts}_{record_count}_{mote_id}"
                    content_hash = hashlib.sha256(content_str.encode()).hexdigest()[:8]
                    
                    object_name = f"year={year}/month={month}/day={day}/mote_id={mote_id}/batch_{min_ts}_{max_ts}_{record_count}_{content_hash}.parquet"
                    
                    # Check if file already exists (idempotency - skip if exists)
                    try:
                        self.minio_client.stat_object(self.bucket_name, object_name)
                        logger.debug(f"File {object_name} already exists, skipping upload (idempotent)")
                        skipped_count += 1
                        continue
                    except S3Error as e:
                        if e.code != "NoSuchKey":
                            logger.error(f"Error checking object existence for {object_name}: {e}")
                            # If checking fails, try to proceed with upload anyway or continue? 
                            # Safer to log and attempt upload, or just raise. 
                            # Let's attempt upload, worst case it overwrites or fails.
                        # File doesn't exist, proceed with upload
                    
                    # Drop partition columns (already in path) and write to buffer
                    parquet_df = group.drop(columns=["year", "month", "day"])
                    buffer = BytesIO()
                    
                    # Write Parquet to in-memory buffer
                    table = pa.Table.from_pandas(parquet_df)
                    pq.write_table(table, buffer, compression="snappy")
                    
                    # Upload to MinIO
                    buffer.seek(0)
                    self.minio_client.put_object(
                        bucket_name=self.bucket_name,
                        object_name=object_name,
                        data=buffer,
                        length=buffer.getbuffer().nbytes,
                        content_type="application/octet-stream"
                    )
                    
                    upload_count += 1
                    logger.debug(f"Uploaded {len(group)} records to {object_name}")

                except Exception as e:
                    logger.error(f"Failed to process group for mote {mote_id} (year={year}, month={month}, day={day}): {e}")
                    # Continue to next group instead of failing the whole batch
                    continue
            
            if skipped_count > 0:
                logger.info(f"Successfully wrote {len(messages)} messages to MinIO: {upload_count} new files, {skipped_count} skipped (already exist)")
            else:
                logger.info(f"Successfully wrote {len(messages)} messages to MinIO as {upload_count} Parquet files")
            
        except Exception as e:
            logger.exception(f"Failed to write batch to MinIO: {e}")
            # Don't raise - we don't want Parquet write failures to block InfluxDB writes

    def close(self) -> None:
        """Cleanup resources (MinIO client doesn't need explicit closing)."""
        pass
