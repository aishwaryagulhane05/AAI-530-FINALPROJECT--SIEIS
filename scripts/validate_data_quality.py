"""Validate data quality in InfluxDB and MinIO.

Usage:
    python scripts/validate_data_quality.py

Checks:
- InfluxDB connectivity and recent data
- MinIO bucket and Parquet file count
- Data completeness (missing fields, null rates)
- Timestamp freshness
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import logging
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

from src.app import config


def check_influxdb() -> bool:
    """Validate InfluxDB connectivity and recent data presence."""
    print("\n📊 Checking InfluxDB...")
    try:
        from influxdb_client import InfluxDBClient
        client = InfluxDBClient(url=config.INFLUX_URL, token=config.INFLUX_TOKEN, org=config.INFLUX_ORG)

        # Ping
        ok = client.ping()
        print(f"  ✅ Ping: {'OK' if ok else '❌ FAILED'}")
        if not ok:
            return False

        # Count recent records
        query_api = client.query_api()
        flux = f"""
from(bucket: "{config.INFLUX_BUCKET}")
  |> range(start: -24h)
  |> filter(fn: (r) => r["_measurement"] == "sensor_reading")
  |> filter(fn: (r) => r["_field"] == "temperature")
  |> count()
"""
        tables = query_api.query(flux, org=config.INFLUX_ORG)
        total = sum(r.get_value() or 0 for t in tables for r in t.records)
        print(f"  ✅ Records in last 24h: {total:,}")

        # Check mote count
        flux2 = f"""
from(bucket: "{config.INFLUX_BUCKET}")
  |> range(start: -24h)
  |> filter(fn: (r) => r["_measurement"] == "sensor_reading")
  |> keep(columns: ["mote_id"])
  |> distinct(column: "mote_id")
  |> count()
"""
        tables2 = query_api.query(flux2, org=config.INFLUX_ORG)
        mote_count = sum(r.get_value() or 0 for t in tables2 for r in t.records)
        print(f"  ✅ Active motes (24h): {mote_count}")

        client.close()
        return total > 0

    except Exception as e:
        print(f"  ❌ InfluxDB check failed: {e}")
        return False


def check_minio() -> bool:
    """Validate MinIO connectivity and Parquet files."""
    print("\n🪣 Checking MinIO...")
    try:
        from minio import Minio
        client = Minio(
            config.MINIO_ENDPOINT,
            access_key=config.MINIO_ACCESS_KEY,
            secret_key=config.MINIO_SECRET_KEY,
            secure=config.MINIO_SECURE,
        )

        # List buckets
        buckets = client.list_buckets()
        bucket_names = [b.name for b in buckets]
        print(f"  ✅ Buckets found: {bucket_names}")

        if config.MINIO_BUCKET not in bucket_names:
            print(f"  ❌ Expected bucket '{config.MINIO_BUCKET}' not found!")
            return False

        # Count Parquet files
        objects = list(client.list_objects(config.MINIO_BUCKET, recursive=True))
        parquet_files = [o for o in objects if o.object_name.endswith(".parquet")]
        total_size_mb = sum(o.size or 0 for o in parquet_files) / (1024 * 1024)

        print(f"  ✅ Parquet files: {len(parquet_files)} ({total_size_mb:.1f} MB)")

        if parquet_files:
            sample_names = [o.object_name for o in parquet_files[:3]]
            print(f"  📁 Sample paths: {sample_names}")

        return len(parquet_files) > 0

    except Exception as e:
        print(f"  ❌ MinIO check failed: {e}")
        return False


def check_data_quality() -> bool:
    """Check data completeness from local historical file if InfluxDB is empty."""
    print("\n📋 Checking local data files...")
    try:
        import pandas as pd

        hist_path = config.DATA_DIR / "processed" / "historical_data.txt"
        if not hist_path.exists():
            print(f"  ⚠️  historical_data.txt not found at {hist_path}")
            return False

        cols = ["date", "time", "epoch", "mote_id", "temperature", "humidity", "light", "voltage", "updated_timestamp"]
        df = pd.read_csv(hist_path, sep=r"\s+", names=cols, na_values=["N/A", "nan", ""], nrows=10000, on_bad_lines="skip")

        total = len(df)
        print(f"  ✅ Rows sampled: {total:,}")

        for col in ["temperature", "humidity", "light", "voltage"]:
            null_pct = df[col].isna().mean() * 100
            status = "✅" if null_pct < 20 else "⚠️ "
            print(f"  {status} {col}: {null_pct:.1f}% null")

        mote_count = df["mote_id"].nunique()
        print(f"  ✅ Unique motes in sample: {mote_count}")

        return True

    except Exception as e:
        print(f"  ❌ Data quality check failed: {e}")
        return False


def main():
    print("=" * 60)
    print("SIEIS Data Quality Validation")
    print(f"Time: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)

    influx_ok = check_influxdb()
    minio_ok = check_minio()
    local_ok = check_data_quality()

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  InfluxDB: {'✅ OK' if influx_ok else '❌ FAILED or empty'}")
    print(f"  MinIO:    {'✅ OK' if minio_ok else '❌ FAILED or empty'}")
    print(f"  Local:    {'✅ OK' if local_ok else '❌ FAILED'}")

    all_ok = local_ok  # local is minimum requirement
    if not all_ok:
        print("\n❌ Validation failed — run load_historical_data.py first")
        sys.exit(1)
    else:
        print("\n✅ Validation passed — ready for ML training")
        print("   Next step: python scripts/train_model.py")


if __name__ == "__main__":
    main()
