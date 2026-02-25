"""Clear all data from InfluxDB and MinIO for a fresh load.

Usage:
    python scripts/clear_storage.py
    python scripts/clear_storage.py --influx-only
    python scripts/clear_storage.py --minio-only
    python scripts/clear_storage.py --dry-run

WARNING: This is destructive. All sensor data will be deleted.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import argparse
import json
from datetime import datetime
from pathlib import Path

from src.app import config


def clear_influxdb(dry_run: bool = False) -> bool:
    """Drop and recreate InfluxDB bucket (instant regardless of record count)."""
    print("\n📊 Clearing InfluxDB...")
    try:
        from influxdb_client import InfluxDBClient

        client = InfluxDBClient(
            url=config.INFLUX_URL,
            token=config.INFLUX_TOKEN,
            org=config.INFLUX_ORG,
            timeout=30_000,   # 30s is plenty — drop/create is instant
        )

        # Ping first
        if not client.ping():
            print("  ❌ Cannot reach InfluxDB")
            return False

        # Count existing records before drop
        query_api = client.query_api()
        flux = f"""
from(bucket: "{config.INFLUX_BUCKET}")
  |> range(start: 2020-01-01T00:00:00Z, stop: 2030-01-01T00:00:00Z)
  |> filter(fn: (r) => r["_measurement"] == "sensor_reading")
  |> filter(fn: (r) => r["_field"] == "temperature")
  |> count()
"""
        try:
            tables = query_api.query(flux, org=config.INFLUX_ORG)
            existing = sum(r.get_value() or 0 for t in tables for r in t.records)
            print(f"  Records found : {existing:,}")
        except Exception:
            print("  Records found : (count query timed out — proceeding anyway)")

        if dry_run:
            print("  DRY RUN — no data deleted")
            client.close()
            return True

        # ── Drop + recreate the bucket (instantaneous, avoids delete-API timeout) ──
        buckets_api = client.buckets_api()

        existing_bucket = buckets_api.find_bucket_by_name(config.INFLUX_BUCKET)
        if existing_bucket is None:
            print(f"  ⚠️  Bucket '{config.INFLUX_BUCKET}' not found — creating it fresh")
        else:
            buckets_api.delete_bucket(existing_bucket)
            print(f"  Dropped bucket  : '{config.INFLUX_BUCKET}'")

        # Resolve org ID
        orgs_api = client.organizations_api()
        org_list = orgs_api.find_organizations(org=config.INFLUX_ORG)
        if not org_list:
            print(f"  ❌ Organisation '{config.INFLUX_ORG}' not found in InfluxDB")
            client.close()
            return False
        org_id = org_list[0].id

        buckets_api.create_bucket(bucket_name=config.INFLUX_BUCKET, org_id=org_id)
        print(f"  ✅ Recreated bucket '{config.INFLUX_BUCKET}' (empty, ready for fresh load)")

        client.close()
        return True

    except Exception as e:
        print(f"  ❌ InfluxDB clear failed: {e}")
        return False


def clear_minio(dry_run: bool = False) -> bool:
    """Delete all objects from MinIO bucket."""
    print("\n🪣 Clearing MinIO...")
    try:
        from minio import Minio

        client = Minio(
            config.MINIO_ENDPOINT,
            access_key=config.MINIO_ACCESS_KEY,
            secret_key=config.MINIO_SECRET_KEY,
            secure=config.MINIO_SECURE,
        )

        if not client.bucket_exists(config.MINIO_BUCKET):
            print(f"  ⚠️  Bucket '{config.MINIO_BUCKET}' does not exist — nothing to clear")
            return True

        # List all objects
        objects = list(client.list_objects(config.MINIO_BUCKET, recursive=True))
        total = len(objects)
        parquet_count = sum(1 for o in objects if o.object_name.endswith(".parquet"))
        total_mb = sum(o.size or 0 for o in objects) / (1024 * 1024)

        print(f"  Objects found : {total:,}  ({parquet_count:,} Parquet, {total_mb:.1f} MB)")

        if dry_run:
            print("  DRY RUN — no objects deleted")
            return True

        if total == 0:
            print("  ✅ Bucket already empty")
            return True

        # Delete in batches
        deleted = 0
        for obj in objects:
            client.remove_object(config.MINIO_BUCKET, obj.object_name)
            deleted += 1
            if deleted % 100 == 0:
                print(f"  Deleted {deleted}/{total} objects...")

        print(f"  ✅ Deleted {deleted:,} objects from bucket '{config.MINIO_BUCKET}'")
        return True

    except Exception as e:
        print(f"  ❌ MinIO clear failed: {e}")
        return False


def reset_checkpoint() -> None:
    """Reset the load checkpoint so loader starts from line 0."""
    checkpoint_path = Path("data/.checkpoint_historical.json")
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    with open(checkpoint_path, "w") as f:
        json.dump({
            "last_line": 0,
            "timestamp": datetime.now().isoformat(),
            "stats": {
                "total_read": 0,
                "influx_written": 0,
                "minio_written": 0,
                "skipped": 0,
                "errors": 0,
            },
            "note": "Reset by clear_storage.py",
        }, f, indent=2)
    print(f"\n🔄 Checkpoint reset: {checkpoint_path}")


def main():
    parser = argparse.ArgumentParser(description="Clear InfluxDB and MinIO for a fresh data load")
    parser.add_argument("--influx-only", action="store_true", help="Clear InfluxDB only")
    parser.add_argument("--minio-only",  action="store_true", help="Clear MinIO only")
    parser.add_argument("--dry-run",     action="store_true", help="Show what would be deleted without deleting")
    args = parser.parse_args()

    do_influx = not args.minio_only
    do_minio  = not args.influx_only

    print("=" * 55)
    print("SIEIS Storage Clear")
    print(f"Time    : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"InfluxDB: {'yes' if do_influx else 'skip'} — {config.INFLUX_URL} / {config.INFLUX_BUCKET}")
    print(f"MinIO   : {'yes' if do_minio  else 'skip'} — {config.MINIO_ENDPOINT} / {config.MINIO_BUCKET}")
    print(f"Dry run : {args.dry_run}")
    print("=" * 55)

    if not args.dry_run:
        confirm = input("\n⚠️  This will DELETE ALL sensor data. Type YES to continue: ")
        if confirm.strip().upper() != "YES":
            print("Aborted.")
            sys.exit(0)

    influx_ok = clear_influxdb(dry_run=args.dry_run) if do_influx else True
    minio_ok  = clear_minio(dry_run=args.dry_run)    if do_minio  else True

    if not args.dry_run:
        reset_checkpoint()

    print("\n" + "=" * 55)
    print("SUMMARY")
    print("=" * 55)
    print(f"  InfluxDB : {'✅ Cleared' if influx_ok else '❌ Failed'}")
    print(f"  MinIO    : {'✅ Cleared' if minio_ok  else '❌ Failed'}")

    if not args.dry_run and influx_ok and minio_ok:
        print("\n✅ Storage cleared. Ready for fresh load.")
        print("   Next: python scripts/load_historical_data.py")


if __name__ == "__main__":
    main()
