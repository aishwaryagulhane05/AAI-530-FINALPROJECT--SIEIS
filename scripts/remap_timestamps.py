"""Remap updated_timestamp fields in historical and incremental data files.

Strategy
--------
Historical 80%
  - Find the max updated_timestamp in the file  → call it hist_last_ts
  - Compute offset = yesterday - hist_last_ts.date()
  - Add that offset to EVERY updated_timestamp in the file
  - Result: last historical record lands on yesterday

Incremental 20%
  - Collect all unique ORIGINAL dates (parts[0], e.g. 2004-03-21)
  - Sort them → map unique_dates[0] → today, unique_dates[1] → today+1, …
  - For each line: keep the time-of-day, swap only the date
  - Result: each original calendar day becomes one real calendar day from today

Analogy: Historical is like a printed book — shift all its page-dates by the
same number of days so the last page says "yesterday". Incremental is like a
live diary — each chapter (original date) gets a new publication date starting
from today.

Usage
-----
    python scripts/remap_timestamps.py               # remap both files
    python scripts/remap_timestamps.py --hist-only
    python scripts/remap_timestamps.py --incr-only
    python scripts/remap_timestamps.py --dry-run     # preview, no writes
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import argparse
import shutil
from datetime import date, datetime, timedelta
from pathlib import Path


# ── helpers ──────────────────────────────────────────────────────────────────

def _last_field(parts: list) -> str | None:
    """Return updated_timestamp (last column) if the line has valid data."""
    if len(parts) in (4, 9):
        return parts[-1]
    return None


def _replace_last_field(line: str, new_value: str) -> str:
    """Swap the last whitespace-separated token in a line, keeping all others."""
    parts = line.rstrip("\r\n").rsplit(None, 1)
    if len(parts) == 2:
        # Preserve original spacing prefix
        prefix = parts[0]
        return prefix + " " + new_value + "\n"
    return line  # malformed — leave untouched


def _parse_ts(ts_str: str) -> datetime | None:
    """Parse ISO timestamp string, tolerating Z suffix."""
    try:
        return datetime.fromisoformat(ts_str.replace("Z", "+00:00").split("+")[0])
    except Exception:
        return None


# ── scan passes ──────────────────────────────────────────────────────────────

def _find_hist_max_date(path: Path) -> date | None:
    """Single-pass scan to find the latest updated_timestamp date in the file."""
    max_date = None
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            parts = line.split()
            ts_str = _last_field(parts)
            if not ts_str:
                continue
            ts = _parse_ts(ts_str)
            if ts and (max_date is None or ts.date() > max_date):
                max_date = ts.date()
    return max_date


def _find_incr_orig_dates(path: Path) -> list:
    """Collect unique original dates (parts[0]) from incremental file, sorted."""
    dates = set()
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            parts = line.split()
            if len(parts) >= 4:
                try:
                    dates.add(date.fromisoformat(parts[0]))
                except ValueError:
                    pass
    return sorted(dates)


# ── remap functions ───────────────────────────────────────────────────────────

def remap_historical(path: Path, dry_run: bool = False) -> dict:
    """Shift all updated_timestamps in historical file so max date = yesterday."""
    print(f"\n[Historical] Scanning {path.name} for max updated_timestamp…")
    hist_max = _find_hist_max_date(path)
    if hist_max is None:
        print("  ❌ Could not find any valid timestamps.")
        return {}

    yesterday = date.today() - timedelta(days=1)
    offset    = timedelta(days=(yesterday - hist_max).days)

    print(f"  Max date found : {hist_max}")
    print(f"  Yesterday      : {yesterday}")
    print(f"  Offset applied : {'+' if offset.days >= 0 else ''}{offset.days} days")

    if dry_run:
        print("  DRY RUN — no file written.")
        return {"max_before": str(hist_max), "max_after": str(yesterday), "offset_days": offset.days}

    # Backup
    backup = path.with_suffix(".txt.bak")
    shutil.copy2(path, backup)
    print(f"  Backup written : {backup.name}")

    # Stream-rewrite
    tmp = path.with_suffix(".txt.tmp")
    changed = skipped = 0
    with open(path, "r", encoding="utf-8", errors="replace") as src, \
         open(tmp,  "w", encoding="utf-8") as dst:
        for line in src:
            parts = line.split()
            ts_str = _last_field(parts)
            if ts_str:
                ts = _parse_ts(ts_str)
                if ts:
                    new_ts = (ts + offset).isoformat(timespec="microseconds")
                    # isoformat uses +00:00 suffix if tz-aware; strip it for consistency
                    new_ts = new_ts.split("+")[0]
                    dst.write(_replace_last_field(line, new_ts))
                    changed += 1
                    continue
            dst.write(line)
            skipped += 1

    tmp.replace(path)
    print(f"  Lines remapped : {changed:,}  (skipped {skipped:,} unparseable)")
    print(f"  ✅ {path.name} updated.")
    return {"max_before": str(hist_max), "max_after": str(yesterday),
            "offset_days": offset.days, "changed": changed}


def remap_incremental(path: Path, dry_run: bool = False) -> dict:
    """Remap each unique original date in incremental file → today + N days."""
    print(f"\n[Incremental] Scanning {path.name} for unique original dates…")
    orig_dates = _find_incr_orig_dates(path)
    if not orig_dates:
        print("  ❌ No valid dates found.")
        return {}

    today    = date.today()
    date_map = {d: today + timedelta(days=i) for i, d in enumerate(orig_dates)}

    print(f"  Unique original dates : {len(orig_dates)}")
    print(f"  Mapping preview:")
    for orig, new in list(date_map.items())[:3]:
        print(f"    {orig}  →  {new}")
    if len(date_map) > 3:
        last_orig, last_new = list(date_map.items())[-1]
        print(f"    …")
        print(f"    {last_orig}  →  {last_new}  (last)")

    if dry_run:
        print("  DRY RUN — no file written.")
        return {
            "unique_dates": len(orig_dates),
            "first_day": str(today),
            "last_day": str(today + timedelta(days=len(orig_dates) - 1)),
        }

    # Backup
    backup = path.with_suffix(".txt.bak")
    shutil.copy2(path, backup)
    print(f"  Backup written : {backup.name}")

    # Stream-rewrite
    tmp     = path.with_suffix(".txt.tmp")
    changed = skipped = 0
    with open(path, "r", encoding="utf-8", errors="replace") as src, \
         open(tmp,  "w", encoding="utf-8") as dst:
        for line in src:
            parts = line.split()
            ts_str = _last_field(parts)
            if ts_str and len(parts) >= 4:
                try:
                    orig_date = date.fromisoformat(parts[0])
                    new_date  = date_map.get(orig_date)
                    ts        = _parse_ts(ts_str)
                    if new_date and ts:
                        # Keep the exact time-of-day, swap only the date
                        new_ts = datetime.combine(new_date, ts.time()).isoformat(timespec="microseconds")
                        dst.write(_replace_last_field(line, new_ts))
                        changed += 1
                        continue
                except (ValueError, KeyError):
                    pass
            dst.write(line)
            skipped += 1

    tmp.replace(path)
    print(f"  Lines remapped : {changed:,}  (skipped {skipped:,} unparseable)")
    print(f"  ✅ {path.name} updated.")
    return {
        "unique_dates": len(orig_dates),
        "first_day": str(today),
        "last_day": str(today + timedelta(days=len(orig_dates) - 1)),
        "changed": changed,
    }


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Remap updated_timestamps in SIEIS data files")
    parser.add_argument("--hist-only", action="store_true", help="Remap historical file only")
    parser.add_argument("--incr-only", action="store_true", help="Remap incremental file only")
    parser.add_argument("--dry-run",   action="store_true", help="Preview remapping without writing")
    parser.add_argument(
        "--hist-file", default="data/processed/historical_data.txt",
        help="Path to historical file"
    )
    parser.add_argument(
        "--incr-file", default="data/processed/incremental_data.txt",
        help="Path to incremental file"
    )
    args = parser.parse_args()

    do_hist = not args.incr_only
    do_incr = not args.hist_only

    hist_path = Path(args.hist_file)
    incr_path = Path(args.incr_file)

    print("=" * 60)
    print("SIEIS Timestamp Remap")
    print(f"Today     : {date.today()}")
    print(f"Yesterday : {date.today() - timedelta(days=1)}")
    print(f"Dry run   : {args.dry_run}")
    print("=" * 60)

    results = {}

    if do_hist:
        if not hist_path.exists():
            print(f"\n❌ Historical file not found: {hist_path}")
        else:
            results["historical"] = remap_historical(hist_path, dry_run=args.dry_run)

    if do_incr:
        if not incr_path.exists():
            print(f"\n❌ Incremental file not found: {incr_path}")
        else:
            results["incremental"] = remap_incremental(incr_path, dry_run=args.dry_run)

    # ── summary ──────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    if "historical" in results and results["historical"]:
        r = results["historical"]
        print(f"  Historical : {r.get('max_before')} → {r.get('max_after')}  "
              f"(+{r.get('offset_days')} days)  {r.get('changed', 'n/a'):,} lines")

    if "incremental" in results and results["incremental"]:
        r = results["incremental"]
        print(f"  Incremental: {r.get('unique_dates')} unique dates  "
              f"→  {r.get('first_day')} … {r.get('last_day')}")

    if not args.dry_run:
        print()
        print("Next steps:")
        print("  1. Load historical to MinIO only:")
        print("       python scripts/load_historical_data.py --minio-only")
        print("  2. Start Docker pipeline for incremental stream:")
        print("       docker compose up -d")
    print("=" * 60)


if __name__ == "__main__":
    main()
