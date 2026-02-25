"""
load_historical_data_new.py — Compact-First Historical Data Loader

Reuses the proven parse_line() from load_historical_data.py.
Writes ONE Parquet file per day (all motes combined) to MinIO.

Result:
  Before : 166,228 files (~1 KB each)
  After  :     ~65 files (~500 KB each, 1 per day)
  ML load: 30 min → seconds

Usage:
  python scripts/load_historical_data_new.py
  python scripts/load_historical_data_new.py --dry-run
  python scripts/load_historical_data_new.py --clear-first
"""

import sys
import os
import io
import logging
import argparse
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv()

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from minio import Minio
from tqdm import tqdm

from src.app.config import (
    MINIO_ENDPOINT,
    MINIO_ACCESS_KEY,
    MINIO_SECRET_KEY,
    MINIO_BUCKET,
    MINIO_SECURE,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_FILE    = PROJECT_ROOT / "data" / "processed" / "historical_data.txt"

# PyArrow schema
SCHEMA = pa.schema([
    pa.field("mote_id",           pa.int32()),
    pa.field("temperature",       pa.float32()),
    pa.field("humidity",          pa.float32()),
    pa.field("light",             pa.float32()),
    pa.field("voltage",           pa.float32()),
    pa.field("timestamp",         pa.string()),
    pa.field("updated_timestamp", pa.string()),
])


# ── Parser ────────────────────────────────────────────────────────────────────
def parse_line(line: str) -> dict:
    """
    Parse a single line from historical_data.txt.

    Actual Intel Lab format:
      4 parts : date time mote_id updated_timestamp          (no epoch, no sensors)
      9 parts : date time epoch mote_id temp hum light volt updated_timestamp

    NOTE: For 9-part lines parts[2] is the epoch sequence number (NOT mote_id).
          mote_id is at parts[3], sensors at parts[4–7], updated_ts at parts[8].
    """
    try:
        parts = line.strip().split()

        if len(parts) < 4:
            return None

        date = parts[0]   # 2004-02-28
        time = parts[1]   # 00:58:46.002832

        if len(parts) == 4:
            # Sparse line: date time mote_id updated_timestamp (no epoch column)
            return {
                "mote_id":           int(parts[2]),
                "timestamp":         f"{date} {time}",
                "updated_timestamp": parts[3],
                "temperature":       None,
                "humidity":          None,
                "light":             None,
                "voltage":           None,
            }

        elif len(parts) >= 9:
            # Full record: date time epoch mote_id temp hum light volt updated_ts
            # parts[2] = epoch (skip), parts[3] = mote_id, parts[4–7] = sensors
            return {
                "mote_id":           int(float(parts[3])),
                "timestamp":         f"{date} {time}",
                "updated_timestamp": parts[8],
                "temperature":       float(parts[4]) if parts[4] != "?" else None,
                "humidity":          float(parts[5]) if parts[5] != "?" else None,
                "light":             float(parts[6]) if parts[6] != "?" else None,
                "voltage":           float(parts[7]) if parts[7] != "?" else None,
            }

        else:
            return None

    except (ValueError, IndexError):
        return None


# ── MinIO helpers ─────────────────────────────────────────────────────────────
def get_minio_client() -> Minio:
    return Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=MINIO_SECURE,
    )


def clear_bucket(client: Minio, bucket: str):
    objects = list(client.list_objects(bucket, recursive=True))
    if not objects:
        logger.info("Bucket already empty")
        return
    logger.info(f"Deleting {len(objects):,} existing objects...")
    for obj in objects:
        client.remove_object(bucket, obj.object_name)
    logger.info(f"✅ Deleted {len(objects):,} objects")


def upload_day_parquet(
    client: Minio,
    bucket: str,
    year: int,
    month: int,
    day: int,
    records: list,
) -> int:
    """Compact all records for one day → upload as single Parquet file."""
    df = pd.DataFrame(records)

    # Drop rows with no sensor values
    df = df.dropna(subset=["temperature", "humidity", "light", "voltage"])
    if df.empty:
        return 0

    # Cast types
    df["mote_id"]           = df["mote_id"].astype("int32")
    df["temperature"]       = df["temperature"].astype("float32")
    df["humidity"]          = df["humidity"].astype("float32")
    df["light"]             = df["light"].astype("float32")
    df["voltage"]           = df["voltage"].astype("float32")
    df["timestamp"]         = df["timestamp"].astype(str)
    df["updated_timestamp"] = df["updated_timestamp"].astype(str)

    table = pa.Table.from_pandas(
        df[["mote_id","temperature","humidity","light","voltage","timestamp","updated_timestamp"]],
        schema=SCHEMA,
        preserve_index=False,
    )

    buf = io.BytesIO()
    pq.write_table(table, buf, compression="snappy", use_dictionary=True)
    buf.seek(0)
    size = buf.getbuffer().nbytes

    object_name = f"year={year}/month={month:02d}/day={day:02d}/data.parquet"
    client.put_object(
        bucket,
        object_name,
        buf,
        length=size,
        content_type="application/octet-stream",
    )
    return size


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Load historical data into MinIO — compact-first (1 file per day)"
    )
    parser.add_argument("--data-file",    default=str(DATA_FILE))
    parser.add_argument("--dry-run",      action="store_true", help="Preview only, no uploads")
    parser.add_argument("--clear-first",  action="store_true", help="Delete all existing MinIO objects first")
    args = parser.parse_args()

    print("=" * 60)
    print("SIEIS — Historical Data Loader (Compact-First)")
    print(f"Source : {args.data_file}")
    print(f"Bucket : {MINIO_BUCKET}")
    print(f"Mode   : {'DRY-RUN' if args.dry_run else 'LIVE'}")
    print("=" * 60)

    # ── Connect ────────────────────────────────────────────────────
    print("\n[1/4] Connecting to MinIO...")
    client = get_minio_client()
    if not client.bucket_exists(MINIO_BUCKET):
        client.make_bucket(MINIO_BUCKET)
        logger.info(f"Created bucket: {MINIO_BUCKET}")
    else:
        logger.info(f"Bucket exists: {MINIO_BUCKET}")

    if args.clear_first and not args.dry_run:
        print("\n[!] Clearing existing bucket contents...")
        clear_bucket(client, MINIO_BUCKET)

    # ── Parse ──────────────────────────────────────────────────────
    print("\n[2/4] Parsing historical data...")
    data_path = Path(args.data_file)
    if not data_path.exists():
        print(f"❌ File not found: {data_path}")
        sys.exit(1)

    # Count lines for progress bar
    with open(data_path, "r") as f:
        total_lines = sum(1 for _ in f)
    logger.info(f"Total lines: {total_lines:,}")

    # Group records by (year, month, day) using updated_timestamp
    day_buckets = defaultdict(list)   # key: (year, month, day)
    parsed = skipped = 0

    with open(data_path, "r") as f:
        for line in tqdm(f, total=total_lines, desc="Parsing", unit=" lines"):
            record = parse_line(line)
            if record is None or record["updated_timestamp"] is None:
                skipped += 1
                continue
            # Only keep records with sensor values
            if record["temperature"] is None:
                skipped += 1
                continue
            try:
                ts  = datetime.fromisoformat(record["updated_timestamp"])
                key = (ts.year, ts.month, ts.day)
                day_buckets[key].append(record)
                parsed += 1
            except ValueError:
                skipped += 1

    print(f"\n   ✅ Parsed  : {parsed:,} rows with sensor data")
    print(f"   ⏭️  Skipped : {skipped:,} rows (no sensor values or parse error)")
    print(f"   📅 Days    : {len(day_buckets)} unique day partitions")

    if parsed == 0:
        print("❌ No data parsed.")
        sys.exit(1)

    # ── Compact + Upload ───────────────────────────────────────────
    print("\n[3/4] Compacting and uploading (1 file per day)...")

    stats = {"files": 0, "rows": 0, "bytes": 0}

    for (year, month, day), records in tqdm(
        sorted(day_buckets.items()),
        desc="Uploading",
        unit=" days",
    ):
        if args.dry_run:
            motes = len({r["mote_id"] for r in records})
            logger.info(
                f"   [DRY-RUN] year={year}/month={month:02d}/day={day:02d}/data.parquet "
                f"— {len(records):,} rows, {motes} motes"
            )
            stats["files"] += 1
            stats["rows"]  += len(records)
            continue

        try:
            size = upload_day_parquet(client, MINIO_BUCKET, year, month, day, records)
            if size > 0:
                stats["files"] += 1
                stats["rows"]  += len(records)
                stats["bytes"] += size
        except Exception as e:
            logger.error(f"Failed year={year}/month={month:02d}/day={day:02d}: {e}")

    # ── Summary ────────────────────────────────────────────────────
    print("\n[4/4] Summary")
    print("=" * 60)
    print(f"  Rows parsed      : {parsed:,}")
    print(f"  Day partitions   : {stats['files']}")
    print(f"  Rows uploaded    : {stats['rows']:,}")
    print(f"  Data uploaded    : {stats['bytes']/1024/1024:.2f} MB")
    print("=" * 60)

    if args.dry_run:
        print("\n⚠️  DRY-RUN — no changes made. Remove --dry-run to execute.")
    else:
        print("\n✅ Done! Next step:")
        print("   python scripts/train_model.py --source minio")


if __name__ == "__main__":
    main()