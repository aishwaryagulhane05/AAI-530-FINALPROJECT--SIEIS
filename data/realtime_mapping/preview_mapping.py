"""
Preview how dates will be mapped without creating the full file.
Quick way to verify the mapping logic before processing.
"""

import csv
from datetime import datetime, timedelta
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def main():
    # Navigate to project root from data/realtime_mapping/
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent
    input_file = project_root / "data" / "data.csv"
    
    if not input_file.exists():
        logger.error(f"❌ File not found: {input_file}")
        logger.info(f"\nSearching for data files...")
        
        # Try alternative locations
        alt_locations = [
            project_root / "data" / "raw" / "data.txt",
            project_root / "data" / "data.txt",
        ]
        
        for alt_file in alt_locations:
            if alt_file.exists():
                logger.info(f"Found: {alt_file}")
                input_file = alt_file
                break
        else:
            logger.error(f"\n❌ No data file found. Please ensure data.csv exists in:")
            logger.error(f"   {project_root / 'data' / 'data.csv'}")
            return 1
    
    logger.info("🔍 Previewing Date Mapping")
    logger.info(f"📂 Input: {input_file.relative_to(project_root)}\n")
    
    # Read all unique dates
    dates = []
    with open(input_file, 'r') as f:
        # Check if space-delimited or CSV
        first_line = f.readline()
        f.seek(0)
        
        if ',' in first_line:
            # CSV format
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    ts = datetime.strptime(row['date'], "%Y-%m-%d %H:%M:%S.%f")
                except (ValueError, KeyError):
                    continue
                dates.append(ts.date())
        else:
            # Space-delimited format: date time mote_id epoch temp humidity light voltage
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 2:
                    try:
                        timestamp_str = f"{parts[0]} {parts[1]}"
                        ts = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S.%f")
                        dates.append(ts.date())
                    except ValueError:
                        continue
    
    if not dates:
        logger.error("❌ No valid dates found in file")
        return 1
    
    unique_dates = sorted(set(dates))
    min_date = unique_dates[0]
    max_date = unique_dates[-1]
    total_days = (max_date - min_date).days + 1
    
    # Calculate 80% point
    days_to_80 = int(total_days * 0.80)
    date_at_80 = min_date + timedelta(days=days_to_80)
    
    today = datetime.now().date()
    
    logger.info(f"📊 Original Dataset:")
    logger.info(f"   Date Range: {min_date} to {max_date}")
    logger.info(f"   Total Days: {total_days}")
    logger.info(f"   Unique Dates: {len(unique_dates)}")
    logger.info(f"   80% Point: {date_at_80} (day {days_to_80})")
    
    logger.info(f"\n🎯 Mapping Strategy:")
    logger.info(f"   {date_at_80} → {today} (TODAY)")
    logger.info(f"   All dates map relative to this anchor")
    
    logger.info(f"\n📋 Complete Date Mapping:\n")
    logger.info(f"   {'Original Date':<15} → {'New Date':<15} {'Description'}")
    logger.info(f"   {'-'*15}   {'-'*15} {'-'*30}")
    
    # Show all mappings
    for orig_date in unique_dates:
        days_offset = (orig_date - date_at_80).days
        new_date = today + timedelta(days=days_offset)
        
        # Description
        diff = (new_date - today).days
        if diff == 0:
            desc = "TODAY ⭐"
        elif diff < 0:
            desc = f"{abs(diff)} days ago"
        else:
            desc = f"{diff} days in FUTURE (filtered)"
        
        # Highlight special dates
        marker = ""
        if orig_date == min_date:
            marker = " ← oldest"
        elif orig_date == max_date:
            marker = " ← newest"
        elif orig_date == date_at_80:
            marker = " ← 80% anchor"
        
        logger.info(f"   {orig_date}   →   {new_date}   {desc}{marker}")
    
    # Count records per date
    logger.info(f"\n📊 Records per Original Date:")
    date_counts = {}
    for d in dates:
        date_counts[d] = date_counts.get(d, 0) + 1
    
    for date in sorted(date_counts.keys())[:10]:
        count = date_counts[date]
        logger.info(f"   {date}: {count:,} records")
    
    if len(date_counts) > 10:
        logger.info(f"   ... ({len(date_counts) - 10} more dates)")
    
    # Calculate expected distribution
    future_count = sum(1 for d in dates if (today + timedelta(days=(d - date_at_80).days)) > today)
    past_count = sum(1 for d in dates if (today + timedelta(days=(d - date_at_80).days)) <= today)
    
    logger.info(f"\n📈 Expected Output:")
    logger.info(f"   Total records: {len(dates):,}")
    logger.info(f"   Will be kept: {past_count:,} ({past_count/len(dates)*100:.1f}%)")
    logger.info(f"   Will be filtered (future): {future_count:,} ({future_count/len(dates)*100:.1f}%)")
    
    logger.info(f"\n✅ Ready to transform? Run:")
    logger.info(f"   python data/realtime_mapping/transform_to_realtime.py")
    
    return 0


if __name__ == "__main__":
    exit(main())
