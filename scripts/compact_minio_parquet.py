"""
compact_minio_parquet.py — PyArrow-only MinIO Parquet compaction.

Groups the 166k+ small batch files by their Hive partition
(year / month / day / mote_id) and rewrites each partition as a single
snappy-compressed Parquet file, then deletes the originals.

Expected outcome
----------------
  Before : ~166,228 files  (~1 KB each)
  After  :    ~3,000 files  (~70 KB each)
  Speedup: ML training load time drops from ~30 min → ~3 min

Usage
-----
  # Dry-run (lists what would happen, no changes)
  python scripts/compact_minio_parquet.py --dry-run

  # Compact everything
  python scripts/compact_minio_parquet.py

  # Compact only one specific partition key
  python scripts/compact_minio_parquet.py --partition year=2026/month=02/day=10/mote_id=1084

  # Compact but keep originals (no delete)
  python scripts/compact_minio_parquet.py --keep-originals

  # Limit to N partitions (useful for testing)
  python scripts/compact_minio_parquet.py --limit 10
"""

import argparse
import io
import logging
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Path helpers ─────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Partition key pattern: year=YYYY/month=MM/day=DD/mote_id=XXXXX
PARTITION_RE = re.compile(
    r"^(year=\d+/month=\d+/day=\d+/mote_id=\d+)/(.+\.parquet)$"
)


def _minio_client():
    from minio import Minio
    from src.app import config

    return (
        Minio(
            config.MINIO_ENDPOINT,
            access_key=config.MINIO_ACCESS_KEY,
            secret_key=config.MINIO_SECRET_KEY,
            secure=config.MINIO_SECURE,
        ),
        config.MINIO_BUCKET,
    )


# ── Core functions ────────────────────────────────────────────────────────────

def list_partitions(client, bucket: str) -> dict[str, list[str]]:
    """Return {partition_key: [object_name, ...]} for all Parquet files."""
    log.info(f"Listing objects in bucket '{bucket}' ...")
    partitions: dict[str, list[str]] = defaultdict(list)
    skipped = 0

    for obj in client.list_objects(bucket, recursive=True):
        name = obj.object_name
        if not name.endswith(".parquet"):
            continue
        m = PARTITION_RE.match(name)
        if m:
            partitions[m.group(1)].append(name)
        else:
            # Could be an already-compacted file at root level — skip.
            skipped += 1

    log.info(
        f"Found {sum(len(v) for v in partitions.values()):,} Parquet files "
        f"across {len(partitions):,} partitions  ({skipped} non-partition files skipped)"
    )
    return dict(partitions)


def compact_partition(
    client,
    bucket: str,
    partition_key: str,
    object_names: list[str],
    dry_run: bool,
    keep_originals: bool,
) -> dict:
    """
    Read all files in a partition, concatenate with PyArrow,
    write one compacted file back, delete originals.

    Returns a result dict with counts and status.
    """
    result = {
        "partition": partition_key,
        "input_files": len(object_names),
        "input_rows": 0,
        "output_rows": 0,
        "status": "ok",
        "error": None,
    }

    if len(object_names) == 1:
        result["status"] = "skipped_single"
        return result

    # ── Read all small files ──────────────────────────────────────
    tables = []
    clock_skew_count = 0

    for obj_name in object_names:
        for attempt in range(3):
            try:
                response = client.get_object(bucket, obj_name)
                data = response.read()
                response.close()
                response.release_conn()
                tables.append(pq.read_table(io.BytesIO(data)))
                break
            except Exception as e:
                err = str(e)
                if "RequestTimeTooSkewed" in err:
                    clock_skew_count += 1
                    break  # no point retrying
                if attempt < 2:
                    time.sleep(0.5)
                else:
                    log.warning(f"  ⚠ Failed {obj_name}: {e}")
                    result["status"] = "partial"

    if not tables:
        result["status"] = "error"
        result["error"] = "No files could be read"
        return result

    if clock_skew_count:
        log.warning(f"  ⚠ {clock_skew_count} files skipped due to clock skew in {partition_key}")
        result["status"] = "partial"

    # ── Concatenate ───────────────────────────────────────────────
    combined = pa.concat_tables(tables, promote_options="default")
    result["input_rows"] = combined.num_rows
    result["output_rows"] = combined.num_rows

    # ── Build output object name ──────────────────────────────────
    # e.g.  year=2026/month=02/day=10/mote_id=1084/compacted.parquet
    output_name = f"{partition_key}/compacted.parquet"

    if dry_run:
        log.info(
            f"  [DRY-RUN] {partition_key}: "
            f"{len(object_names)} files → 1 file  ({combined.num_rows:,} rows)"
        )
        result["status"] = "dry_run"
        return result

    # ── Write compacted file ──────────────────────────────────────
    buf = io.BytesIO()
    pq.write_table(combined, buf, compression="snappy")
    buf.seek(0)
    data_bytes = buf.getvalue()

    client.put_object(
        bucket,
        output_name,
        io.BytesIO(data_bytes),
        length=len(data_bytes),
        content_type="application/octet-stream",
    )

    # ── Delete originals ──────────────────────────────────────────
    if not keep_originals:
        for obj_name in object_names:
            try:
                client.remove_object(bucket, obj_name)
            except Exception as e:
                log.warning(f"  ⚠ Could not delete {obj_name}: {e}")

    return result


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Compact MinIO Parquet files — one file per partition."
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would happen without making any changes",
    )
    parser.add_argument(
        "--keep-originals", action="store_true",
        help="Write compacted files but do NOT delete the originals",
    )
    parser.add_argument(
        "--partition", type=str, default=None,
        help="Compact only this specific partition key (e.g. year=2026/month=02/day=10/mote_id=1084)",
    )
    parser.add_argument(
        "--limit", type=int, default=0,
        help="Stop after compacting this many partitions (0 = all)",
    )
    parser.add_argument(
        "--min-files", type=int, default=2,
        help="Only compact partitions with at least this many files (default: 2)",
    )
    args = parser.parse_args()

    print("=" * 65)
    print("SIEIS — PyArrow MinIO Parquet Compaction")
    mode = "DRY-RUN" if args.dry_run else ("KEEP ORIGINALS" if args.keep_originals else "COMPACT + DELETE")
    print(f"Mode       : {mode}")
    print(f"Min files  : {args.min_files}")
    print(f"Limit      : {args.limit if args.limit else 'ALL'}")
    if args.partition:
        print(f"Partition  : {args.partition}")
    print("=" * 65)

    client, bucket = _minio_client()

    # ── Get partition map ─────────────────────────────────────────
    if args.partition:
        # Verify partition exists
        all_parts = list_partitions(client, bucket)
        if args.partition not in all_parts:
            print(f"❌ Partition '{args.partition}' not found in bucket.")
            sys.exit(1)
        partitions = {args.partition: all_parts[args.partition]}
    else:
        partitions = list_partitions(client, bucket)

    # Filter by min-files threshold
    partitions = {k: v for k, v in partitions.items() if len(v) >= args.min_files}
    print(f"\nPartitions needing compaction : {len(partitions):,}")

    if not partitions:
        print("Nothing to compact. Exiting.")
        return

    # Apply limit
    partition_list = list(partitions.items())
    if args.limit:
        partition_list = partition_list[: args.limit]
        print(f"Limited to first {args.limit} partitions.\n")

    # ── Compact each partition ────────────────────────────────────
    stats = {"ok": 0, "partial": 0, "error": 0, "dry_run": 0, "skipped_single": 0}
    total_input_files = 0
    total_input_rows = 0
    start = time.time()

    for i, (pkey, obj_names) in enumerate(partition_list, 1):
        prefix = f"[{i}/{len(partition_list)}]"
        print(f"{prefix} {pkey}  ({len(obj_names)} files)", end=" ... ", flush=True)

        result = compact_partition(
            client, bucket, pkey, obj_names,
            dry_run=args.dry_run,
            keep_originals=args.keep_originals,
        )

        status = result["status"]
        stats[status] = stats.get(status, 0) + 1
        total_input_files += result["input_files"]
        total_input_rows += result["input_rows"]

        if status in ("ok", "partial"):
            print(f"✅ {result['input_rows']:,} rows")
        elif status == "dry_run":
            print(f"(dry-run)")
        elif status == "skipped_single":
            print(f"skipped (already 1 file)")
        else:
            print(f"❌ {result['error']}")

    elapsed = time.time() - start
    print()
    print("=" * 65)
    print("COMPACTION COMPLETE")
    print(f"  Elapsed         : {elapsed:.1f}s  ({elapsed/60:.1f} min)")
    print(f"  Partitions      : {len(partition_list):,}")
    print(f"  Input files     : {total_input_files:,}")
    print(f"  Input rows      : {total_input_rows:,}")
    print(f"  ✅ OK            : {stats.get('ok', 0):,}")
    print(f"  ⚠  Partial       : {stats.get('partial', 0):,}")
    print(f"  ❌ Errors        : {stats.get('error', 0):,}")
    if args.dry_run:
        print(f"\n  ℹ Run without --dry-run to apply changes.")
    print("=" * 65)


if __name__ == "__main__":
    main()
