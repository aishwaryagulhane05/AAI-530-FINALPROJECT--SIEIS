"""Split the full sensor dataset into 80% historical and 20% incremental.

The source file is data/processed/realtime_data.txt (full dataset with
remapped 2026 timestamps). Lines are split in chronological order so the
80% block represents the past and the 20% block represents "new" data.

Usage:
    python scripts/split_dataset.py
    python scripts/split_dataset.py --split 0.8
    python scripts/split_dataset.py --source data/processed/realtime_data.txt
    python scripts/split_dataset.py --dry-run

Analogy: Think of the dataset like a stack of dated newspapers. We keep
the oldest 80% as the archive (historical), and the newest 20% as the
fresh pile that arrives incrementally.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()


def count_lines(filepath: Path) -> int:
    """Count lines in a file efficiently without loading it all into memory."""
    count = 0
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        for _ in f:
            count += 1
    return count


def split_dataset(
    source: Path,
    historical_out: Path,
    incremental_out: Path,
    split_ratio: float = 0.8,
    dry_run: bool = False,
):
    """Split source file into historical (split_ratio) and incremental (1-split_ratio).

    Args:
        source:          Input file (full dataset with remapped timestamps)
        historical_out:  Output file for first split_ratio of lines
        incremental_out: Output file for remaining lines
        split_ratio:     Fraction for historical split (default 0.8 = 80%)
        dry_run:         If True, only count and report without writing
    """
    print("=" * 65)
    print("SIEIS Dataset Split")
    print(f"Source : {source}")
    print(f"Split  : {split_ratio:.0%} historical / {1-split_ratio:.0%} incremental")
    print(f"Dry run: {dry_run}")
    print("=" * 65)

    # ── Step 1: count total lines ──────────────────────────────────────────
    print("\n[1/3] Counting lines in source file...")
    total = count_lines(source)
    historical_count = int(total * split_ratio)
    incremental_count = total - historical_count

    print(f"  Total lines      : {total:>12,}")
    print(f"  Historical (80%) : {historical_count:>12,}")
    print(f"  Incremental (20%): {incremental_count:>12,}")

    if dry_run:
        print("\n✅ Dry run complete — no files written.")
        return historical_count, incremental_count

    # ── Step 2: backup existing files if present ───────────────────────────
    print("\n[2/3] Backing up existing split files...")
    for path in (historical_out, incremental_out):
        if path.exists():
            backup = path.with_suffix(".txt.bak")
            shutil.copy2(path, backup)
            print(f"  Backed up: {path.name} → {backup.name}")

    # ── Step 3: stream-write the split ────────────────────────────────────
    print("\n[3/3] Writing split files...")

    written_hist = 0
    written_incr = 0
    start = datetime.now()

    with open(source, "r", encoding="utf-8", errors="replace") as src, \
         open(historical_out, "w", encoding="utf-8") as hist_f, \
         open(incremental_out, "w", encoding="utf-8") as incr_f:

        for line_num, line in enumerate(src, 1):
            if line_num <= historical_count:
                hist_f.write(line)
                written_hist += 1
            else:
                incr_f.write(line)
                written_incr += 1

            # Print progress every 10%
            if line_num % max(1, total // 10) == 0:
                pct = line_num / total * 100
                elapsed = (datetime.now() - start).total_seconds()
                rate = line_num / elapsed if elapsed > 0 else 0
                print(f"  {pct:5.0f}% — {line_num:,}/{total:,} lines  ({rate:,.0f} lines/sec)")

    elapsed = (datetime.now() - start).total_seconds()

    # ── Reset checkpoint so load_historical_data starts fresh ─────────────
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
            "note": f"Reset by split_dataset.py — {split_ratio:.0%}/{1-split_ratio:.0%} split",
        }, f, indent=2)
    print(f"\n  ✅ Checkpoint reset: {checkpoint_path}")

    # ── Summary ───────────────────────────────────────────────────────────
    hist_size_mb = historical_out.stat().st_size / (1024 * 1024)
    incr_size_mb = incremental_out.stat().st_size / (1024 * 1024)

    print("\n" + "=" * 65)
    print("SPLIT COMPLETE")
    print("=" * 65)
    print(f"  Time elapsed : {elapsed:.1f}s")
    print(f"  historical_data.txt : {written_hist:>10,} lines  ({hist_size_mb:.1f} MB)")
    print(f"  incremental_data.txt: {written_incr:>10,} lines  ({incr_size_mb:.1f} MB)")
    print()
    print("Next steps:")
    print("  1. Load historical data into InfluxDB + MinIO:")
    print("       python scripts/load_historical_data.py")
    print("  2. Start Docker pipeline (streams incremental data):")
    print("       docker compose up -d")
    print("  3. Verify data is flowing:")
    print("       python scripts/verify_influxDb.py")
    print("       python scripts/verify_minio_storage.py")
    print("  4. Train the ML model:")
    print("       python scripts/train_model.py")
    print("=" * 65)

    return written_hist, written_incr


def main():
    parser = argparse.ArgumentParser(description="Split SIEIS dataset into historical/incremental")
    parser.add_argument(
        "--source",
        default="data/processed/realtime_data.txt",
        help="Source file (default: data/processed/realtime_data.txt)",
    )
    parser.add_argument(
        "--historical-out",
        default="data/processed/historical_data.txt",
        help="Output path for historical split (default: data/processed/historical_data.txt)",
    )
    parser.add_argument(
        "--incremental-out",
        default="data/processed/incremental_data.txt",
        help="Output path for incremental split (default: data/processed/incremental_data.txt)",
    )
    parser.add_argument(
        "--split",
        type=float,
        default=0.8,
        metavar="RATIO",
        help="Fraction of data for historical split (default: 0.8 = 80%%)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Count lines and report only — do not write files",
    )
    args = parser.parse_args()

    source = Path(args.source)
    if not source.exists():
        print(f"❌ Source file not found: {source}")
        sys.exit(1)

    if not (0.0 < args.split < 1.0):
        print(f"❌ --split must be between 0 and 1 (got {args.split})")
        sys.exit(1)

    split_dataset(
        source=source,
        historical_out=Path(args.historical_out),
        incremental_out=Path(args.incremental_out),
        split_ratio=args.split,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
