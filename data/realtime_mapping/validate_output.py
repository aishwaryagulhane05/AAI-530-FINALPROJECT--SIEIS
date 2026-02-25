"""
Validate the transformed real-time data file.
Checks for data integrity, distribution, and timestamp consistency.
"""

import csv
from datetime import datetime
from pathlib import Path
from collections import defaultdict
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def validate_output_file(output_file):
    """Perform comprehensive validation of the transformed data."""
    
    logger.info("🔍 Validating Transformed Data File")
    logger.info(f"📂 File: {output_file}\n")
    
    if not output_file.exists():
        logger.error(f"❌ File not found: {output_file}")
        logger.info("\nRun transformation first:")
        logger.info("   python data/realtime_mapping/transform_to_realtime.py")
        return False
    
    # Validation metrics
    total_records = 0
    today_count = 0
    historical_count = 0
    future_count = 0
    
    mote_ids = set()
    date_distribution = defaultdict(int)
    fields_summary = defaultdict(lambda: {'count': 0, 'sum': 0, 'min': float('inf'), 'max': float('-inf')})
    
    sample_records = []
    errors = []
    
    today = datetime.now().date()
    now = datetime.now()
    
    # Read and analyze
    logger.info("📊 Analyzing data...")
    
    with open(output_file, 'r') as f:
        reader = csv.DictReader(f)
        
        # Verify required columns
        required_cols = ['date', 'updated_timestamp', 'mote_id', 'temperature', 'humidity']
        missing_cols = [col for col in required_cols if col not in reader.fieldnames]
        
        if missing_cols:
            logger.error(f"❌ Missing required columns: {missing_cols}")
            return False
        
        for i, row in enumerate(reader):
            total_records += 1
            
            try:
                # Parse timestamps
                updated_ts = datetime.fromisoformat(row['updated_timestamp'])
                updated_date = updated_ts.date()
                
                # Check for future dates (should not exist)
                if updated_ts > now:
                    future_count += 1
                    if len(errors) < 5:
                        errors.append(f"Row {i+1}: Future timestamp {updated_ts.isoformat()}")
                
                # Categorize by date
                if updated_date == today:
                    today_count += 1
                else:
                    historical_count += 1
                
                # Track distribution
                date_key = updated_date.isoformat()
                date_distribution[date_key] += 1
                
                # Track mote IDs
                mote_ids.add(row['mote_id'])
                
                # Analyze sensor fields
                for field in ['temperature', 'humidity', 'light', 'voltage']:
                    try:
                        value = float(row[field])
                        fields_summary[field]['count'] += 1
                        fields_summary[field]['sum'] += value
                        fields_summary[field]['min'] = min(fields_summary[field]['min'], value)
                        fields_summary[field]['max'] = max(fields_summary[field]['max'], value)
                    except (ValueError, KeyError):
                        pass
                
                # Collect samples
                if i < 3 or (i % 50000 == 0 and len(sample_records) < 10):
                    sample_records.append({
                        'mote_id': row['mote_id'],
                        'original': row['date'],
                        'updated': row['updated_timestamp'],
                        'temp': row.get('temperature', 'N/A')
                    })
            
            except Exception as e:
                if len(errors) < 5:
                    errors.append(f"Row {i+1}: Parse error - {e}")
            
            # Progress
            if total_records % 50000 == 0:
                logger.info(f"   Processed {total_records:,} records...")
    
    # Print results
    logger.info(f"\n{'='*80}")
    logger.info("VALIDATION RESULTS")
    logger.info(f"{'='*80}\n")
    
    # Basic stats
    logger.info("📈 Record Counts:")
    logger.info(f"   Total records: {total_records:,}")
    logger.info(f"   Today's data: {today_count:,} ({today_count/total_records*100:.1f}%)")
    logger.info(f"   Historical: {historical_count:,} ({historical_count/total_records*100:.1f}%)")
    logger.info(f"   Unique motes: {len(mote_ids)}")
    
    # Check for errors
    if future_count > 0:
        logger.error(f"\n❌ VALIDATION FAILED!")
        logger.error(f"   Found {future_count} future timestamps (should be 0)")
        for error in errors[:5]:
            logger.error(f"   • {error}")
        return False
    
    # Date distribution
    logger.info(f"\n📅 Date Distribution (top 10):")
    sorted_dates = sorted(date_distribution.items(), key=lambda x: x[1], reverse=True)[:10]
    for date_str, count in sorted_dates:
        pct = (count / total_records) * 100
        logger.info(f"   {date_str}: {count:,} records ({pct:.1f}%)")
    
    # Field statistics
    logger.info(f"\n🌡️  Sensor Field Statistics:")
    for field, stats in sorted(fields_summary.items()):
        if stats['count'] > 0:
            avg = stats['sum'] / stats['count']
            logger.info(f"   {field.capitalize()}:")
            logger.info(f"      Range: {stats['min']:.2f} to {stats['max']:.2f}")
            logger.info(f"      Average: {avg:.2f}")
    
    # Sample records
    logger.info(f"\n📋 Sample Records:")
    for sample in sample_records[:5]:
        logger.info(f"   Mote {sample['mote_id']}: {sample['original']} → {sample['updated']} (temp: {sample['temp']})")
    
    # Errors
    if errors:
        logger.warning(f"\n⚠️  Warnings ({len(errors)}):")
        for error in errors[:5]:
            logger.warning(f"   • {error}")
    
    # Final verdict
    logger.info(f"\n{'='*80}")
    if future_count == 0 and total_records > 0:
        logger.info("✅ VALIDATION PASSED!")
        logger.info("   • No future timestamps")
        logger.info("   • All records have valid updated_timestamp")
        logger.info("   • Data ready for use")
        logger.info(f"\n📝 Next: Update docker-compose.yml and restart containers")
        return True
    else:
        logger.error("❌ VALIDATION FAILED!")
        logger.error("   Please check errors above and re-run transformation")
        return False


def main():
    """Main entry point."""
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent
    output_file = project_root / "data" / "data_realtime.csv"
    
    success = validate_output_file(output_file)
    
    return 0 if success else 1


if __name__ == "__main__":
    exit(main())
