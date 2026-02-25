"""
Split raw sensor data into Historical and Incremental datasets with time mapping.

Logic:
1. Load raw data from data/raw/data.txt
2. Sort by timestamp (ascending)
3. Determine 80% split point based on time range
4. Split data:
   - Historical: <= 80% date (Mapped so last date = TODAY, rest backwards)
   - Incremental: > 80% date (Mapped so first date = TOMORROW, rest forwards)
"""

import logging
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def parse_raw_data(file_path):
    """
    Read raw intel lab data.
    Format is space separated: date time epoch moteid temp humidity light voltage
    """
    logger.info(f"📖 Reading raw data from {file_path}...")
    
    # Define column names based on Intel Lab dataset format
    col_names = ['date', 'time', 'epoch', 'moteid', 'temperature', 'humidity', 'light', 'voltage']
    
    try:
        # Read using pandas for efficiency
        df = pd.read_csv(
            file_path, 
            sep=r'\s+', 
            header=None, 
            names=col_names,
            on_bad_lines='skip',
            engine='python' # Python engine is more robust for variable whitespace
        )
        
        # Create a single timestamp column for sorting
        df['original_ts'] = pd.to_datetime(
            df['date'] + ' ' + df['time'], 
            format='%Y-%m-%d %H:%M:%S.%f', 
            errors='coerce'
        )
        
        # Drop invalid rows
        initial_len = len(df)
        df = df.dropna(subset=['original_ts'])
        if len(df) < initial_len:
            logger.warning(f"⚠️ Dropped {initial_len - len(df)} rows with invalid timestamps")
            
        # Sort by timestamp
        logger.info("⚡ Sorting data by timestamp...")
        df = df.sort_values('original_ts')
        
        return df
        
    except Exception as e:
        logger.error(f"❌ Failed to parse data: {e}")
        raise


def calculate_split_date(df):
    """Find the date that represents the 80% mark of the time range."""
    min_date = df['original_ts'].min()
    max_date = df['original_ts'].max()
    
    total_duration = max_date - min_date
    split_offset = total_duration * 0.8
    split_date = min_date + split_offset
    
    logger.info(f"📅 Date Range: {min_date} to {max_date}")
    logger.info(f"⏱️  Duration: {total_duration}")
    logger.info(f"✂️  80% Split Timestamp: {split_date}")
    
    return split_date


def map_timestamps(df, target_anchor_date, is_historical=True):
    """
    Map timestamps to new range.
    
    Args:
        df: DataFrame slice
        target_anchor_date: The target date to map the specific anchor point to.
        is_historical: 
            If True: Map MAX date in df -> target_anchor_date (Today).
            If False: Map MIN date in df -> target_anchor_date (Tomorrow).
    """
    if df.empty:
        return df

    # Calculate offsets
    if is_historical:
        # For historical: Last record = Today (aligned at same time of day as original max)
        anchor_original = df['original_ts'].max()
        time_offset = target_anchor_date - anchor_original
        logger.info(f"Mapping Historical: Max Original {anchor_original} -> Target {target_anchor_date}")
    else:
        # For incremental: First record = Tomorrow (Start of day)
        anchor_original = df['original_ts'].min()
        time_offset = target_anchor_date - anchor_original
        logger.info(f"Mapping Incremental: Min Original {anchor_original} -> Target {target_anchor_date}")

    # Apply offset
    df = df.copy()
    df['updated_timestamp'] = df['original_ts'] + time_offset
    
    return df


def save_processed_file(df, output_path):
    """Save the processed DataFrame to CSV/TXT format expected by simulator."""
    if df.empty:
        logger.warning(f"⚠️ Skipping empty dataframe save to {output_path}")
        return

    logger.info(f"💾 Saving {len(df):,} records to {output_path}...")
    
    # NEW LOGIC: Format updated_timestamp to be ISO format (no spaces) to prevent parse errors downstream
    # pd.to_csv default string representation might include spaces.
    if 'updated_timestamp' in df.columns:
        # We need to operate on a copy or modify safely. 
        # Since this function is the last step for these DFs, modifying in place or copy is fine.
        df = df.copy()
        df['updated_timestamp'] = df['updated_timestamp'].dt.strftime('%Y-%m-%dT%H:%M:%S.%f')
    
    # Ensure directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Columns to save: original columns + updated_timestamp
    # Note: Simulator might expect specific column order. Usually it reads columns by name if header/names provided in pd.read_csv
    # Original raw data has no header.
    # Our data_loader.py reads: 'date', 'time', 'epoch', 'moteid', 'temperature', 'humidity', 'light', 'voltage', 'updated_timestamp'
    
    cols_to_save = ['date', 'time', 'epoch', 'moteid', 'temperature', 'humidity', 'light', 'voltage', 'updated_timestamp']
    
    # Use space separator as per original format, no header, index=False
    import csv as csv_module
    df.to_csv(
        output_path, 
        sep=' ', 
        index=False, 
        columns=cols_to_save, 
        header=False, 
        quoting=csv_module.QUOTE_NONE, 
        escapechar=' '
    )


def main():
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent
    
    # Check possible input file locations
    possible_inputs = [
        project_root / "data" / "raw" / "data.txt",
        project_root / "data" / "data.txt"
    ]
    
    raw_file = None
    for p in possible_inputs:
        if p.exists():
            raw_file = p
            break
            
    if not raw_file:
        logger.error("❌ Raw data file not found in data/raw/data.txt")
        return 1

    # 1. Load and Sort
    try:
        df = parse_raw_data(raw_file)
    except Exception as e:
        logger.error(f"Failed to load data: {e}")
        return 1
    
    # 2. Determine Split
    split_timestamp = calculate_split_date(df)
    
    # 3. Split Dataframes
    mask_historical = df['original_ts'] <= split_timestamp
    df_hist = df[mask_historical].copy()
    df_incr = df[~mask_historical].copy()
    
    logger.info(f"📊 Split Stats:")
    logger.info(f"   Historical Records:  {len(df_hist):,} (Max Orig Date: {df_hist['original_ts'].max()})")
    logger.info(f"   Incremental Records: {len(df_incr):,} (Min Orig Date: {df_incr['original_ts'].min() if not df_incr.empty else 'N/A'})")

    # 4. Map Dates
    now = datetime.now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Calculate target anchor for Historical (End of Today or Now?)
    # "80th% percent date is mapped to today" implies the end of the historical range is today.
    # Let's map it to NOW.
    target_hist_anchor = now
    
    df_hist_mapped = map_timestamps(df_hist, target_hist_anchor, is_historical=True)
    
    # Calculate target anchor for Incremental
    # User requested: "transmit only current day data from incremental data file"
    # To facilitate this, we start the incremental data TODAY (now + 1 minute) 
    # instead of tomorrow, so the simulator picks it up immediately.
    target_incr_start = now + timedelta(minutes=1)
    
    df_incr_mapped = map_timestamps(df_incr, target_incr_start, is_historical=False)

    # 5. Save Files
    output_dir = project_root / "data" / "processed"
    
    save_processed_file(df_hist_mapped, output_dir / "historical_data.txt")
    save_processed_file(df_incr_mapped, output_dir / "incremental_data.txt")
    
    # 6. Create 'realtime_data.txt' for simulator backward compatibility
    # The simulator currently points to data/processed/realtime_data.txt
    # We should probably combine them or just use historical?
    # Request implies splitting, maybe for a staged simulation (load historical, then stream incremental).
    # For now, I'll save the historical data as 'realtime_data.txt' too so the current simulator has something relevant to play.
    # OR better: save the concatenation of both mapped datasets to realtime_data.txt so the simulator can iterate through all.
    # Since mapped timestamps are contiguous (Today -> Tomorrow...), let's save the Combined set.
    
    logger.info("🔗 Creating combined realtime_data.txt for simulator compatibility...")
    df_combined = pd.concat([df_hist_mapped, df_incr_mapped])
    save_processed_file(df_combined, output_dir / "realtime_data.txt")
    
    logger.info("✅ Data transformation complete.")
    logger.info(f"   Output 1: {output_dir / 'historical_data.txt'}")
    logger.info(f"   Output 2: {output_dir / 'incremental_data.txt'}")
    logger.info(f"   Output 3: {output_dir / 'realtime_data.txt'} (Combined)")
    return 0

if __name__ == "__main__":
    sys.exit(main())
