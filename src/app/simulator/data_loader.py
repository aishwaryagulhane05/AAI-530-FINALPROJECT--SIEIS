"""Load and clean Intel Lab sensor data for simulation."""

import pandas as pd
import logging
from datetime import datetime
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


def load_data_loader(data_path: str, mote_locs_path: str, filter_today_only: bool = True) -> Tuple[Dict[int, pd.DataFrame], pd.DataFrame]:
    """
    Load Intel Lab sensor data and mote locations.
    
    Args:
        data_path: Path to data file (8-column legacy or 9-column with updated_timestamp)
        mote_locs_path: Path to mote_locs.txt file
        filter_today_only: If True, only load records where updated_timestamp is TODAY
    
    Returns:
        Tuple of (mote_data_dict, mote_locations_df)
        - mote_data_dict: {mote_id: DataFrame with sensor readings}
        - mote_locations_df: DataFrame with mote locations
    """
    
    logger.info(f"Loading sensor data from {data_path}")
    
    # Load sensor data
    # File columns: date time epoch moteid temperature humidity light voltage [updated_timestamp]
    # 9th column (updated_timestamp) is optional for backward compatibility
    # Note: Only specify dtype for first 8 columns, let pandas infer the 9th (if present)
    df = pd.read_csv(
        data_path,
        sep=r'\s+',
        header=None,
        names=['date', 'time', 'epoch', 'moteid', 'temperature', 'humidity', 'light', 'voltage', 'updated_timestamp'],
        na_values=['?']
    )
    
    # Ensure proper dtypes for numeric columns
    df['epoch'] = pd.to_numeric(df['epoch'], errors='coerce')
    df['moteid'] = pd.to_numeric(df['moteid'], errors='coerce')
    df['temperature'] = pd.to_numeric(df['temperature'], errors='coerce')
    df['humidity'] = pd.to_numeric(df['humidity'], errors='coerce')
    df['light'] = pd.to_numeric(df['light'], errors='coerce')
    df['voltage'] = pd.to_numeric(df['voltage'], errors='coerce')
    
    raw_count = len(df)
    logger.info(f"Loaded {raw_count:,} total records")

    # ── Row validation ────────────────────────────────────────────────────
    # Shifted rows: when a source line has fewer fields than expected, pandas
    # shifts all values left.  The symptom is an ISO-8601 timestamp string
    # landing in the `voltage` column and `updated_timestamp` becoming NaN.
    # Detect these early by coercing numeric columns and flagging NaN moteids.

    # Guard 1 — moteid must be numeric (already coerced above; NaN rows dropped here)
    non_numeric_mote = df['moteid'].isna().sum()
    if non_numeric_mote:
        logger.warning(
            f"Row validation: dropped {non_numeric_mote:,} rows with non-numeric moteid"
        )
    df = df.dropna(subset=['moteid'])

    # Guard 2 — moteid must be within the Intel Lab sensor range (1–100)
    # Rows outside this range are artefacts of column-shift parse errors.
    MOTE_ID_MIN, MOTE_ID_MAX = 1, 100
    out_of_range = ~df['moteid'].between(MOTE_ID_MIN, MOTE_ID_MAX)
    if out_of_range.any():
        logger.warning(
            f"Row validation: dropped {out_of_range.sum():,} rows with "
            f"moteid outside [{MOTE_ID_MIN}, {MOTE_ID_MAX}] "
            f"(saw values: {sorted(df.loc[out_of_range, 'moteid'].unique().tolist()[:10])})"
        )
    df = df[~out_of_range]

    total_dropped = raw_count - len(df)
    if total_dropped:
        logger.info(
            f"Row validation complete: {total_dropped:,} malformed rows removed "
            f"({total_dropped / raw_count * 100:.2f}% of input), "
            f"{len(df):,} clean rows retained"
        )

    # Combine date + time into a single timestamp column (original 2004 timestamps)
    df['timestamp'] = pd.to_datetime(
        df['date'].astype(str) + ' ' + df['time'].astype(str), format='%Y-%m-%d %H:%M:%S.%f', errors='coerce'
    )

    # Drop rows where timestamp could not be parsed
    df = df.dropna(subset=['timestamp'])

    # Parse updated_timestamp if present (pre-mapped to current year)
    if 'updated_timestamp' in df.columns and df['updated_timestamp'].notna().any():
        df['updated_timestamp'] = pd.to_datetime(df['updated_timestamp'], errors='coerce')
        logger.info("Found updated_timestamp column in data file")

        # Guard 3 — drop rows whose updated_timestamp failed to parse.
        # In 9-column mode these are the remaining shifted rows: their voltage
        # column holds a timestamp string, so `updated_timestamp` is NaN.
        bad_ts = df['updated_timestamp'].isna()
        if bad_ts.any():
            logger.warning(
                f"Row validation: dropped {bad_ts.sum():,} rows with "
                "unparseable updated_timestamp (likely shifted-column rows)"
            )
        df = df[~bad_ts]

        # FILTER: Only keep records for TODAY if requested
        if filter_today_only:
            today = datetime.now().date()
            initial_count = len(df)
            df = df[df['updated_timestamp'].dt.date == today].copy()
            logger.info(f"Filtered to {len(df):,} records for today ({today}) from {initial_count:,} total records")

            if len(df) == 0:
                logger.warning(f"⚠️  No records found for today ({today})!")
                logger.warning("   This might mean:")
                logger.warning("   1. The transformation was run on a different date")
                logger.warning("   2. All today's data was filtered as future timestamps")
                logger.warning("   3. The realtime_data.txt file needs to be regenerated")
    else:
        logger.info("No updated_timestamp column found - using legacy 8-column format")

    # Convert moteid to int (moteid is already validated and non-null above)
    df['moteid'] = df['moteid'].astype(int)
    # Drop rows with null temperature or humidity
    df = df.dropna(subset=['temperature', 'humidity'])
    
    # Fill null light with 0
    df['light'] = df['light'].fillna(0.0)
    
    # Forward fill voltage per mote to keep continuity in streams
    df = df.sort_values(['moteid', 'timestamp'])
    df['voltage'] = df.groupby('moteid')['voltage'].ffill()
    
    # Fill any remaining null voltage with backward fill (for first readings)
    df['voltage'] = df['voltage'].bfill()
    
    # Split by mote ID for per-sensor simulation
    mote_data_dict = {}
    unique_motes = df['moteid'].unique()
    logger.info(f"Processing {len(unique_motes)} unique motes")
    
    for mote_id in unique_motes:
        mote_df = df[df['moteid'] == mote_id].copy()
        # Sort by timestamp
        mote_df = mote_df.sort_values('timestamp').reset_index(drop=True)
        mote_data_dict[mote_id] = mote_df
        logger.debug(f"  Mote {mote_id}: {len(mote_df)} records")
    
    # Load mote locations
    mote_locs_df = pd.read_csv(
        mote_locs_path,
        sep=r'\s+',
        header=None,
        names=['moteid', 'x', 'y'],
        dtype={'moteid': int, 'x': float, 'y': float}
    )
    
    return mote_data_dict, mote_locs_df


def get_mote_data(data_path: str, mote_locs_path: str, mote_id: int) -> pd.DataFrame:
    """
    Get sensor data for a specific mote.
    
    Args:
        data_path: Path to data.txt file
        mote_locs_path: Path to mote_locs.txt file
        mote_id: Mote ID to retrieve
    
    Returns:
        DataFrame with sensor readings for the mote
    """
    mote_data_dict, _ = load_data_loader(data_path, mote_locs_path)
    return mote_data_dict.get(mote_id, pd.DataFrame())


def get_mote_location(mote_locs_path: str, mote_id: int) -> Optional[Tuple[float, float]]:
    """
    Get (x, y) location for a mote.
    
    Args:
        mote_locs_path: Path to mote_locs.txt file
        mote_id: Mote ID to retrieve
    
    Returns:
        Tuple of (x, y) coordinates
    """
    mote_locs_df = pd.read_csv(
        mote_locs_path,
        sep=r'\s+',
        header=None,
        names=['moteid', 'x', 'y'],
        dtype={'moteid': int, 'x': float, 'y': float}
    )
    
    loc = mote_locs_df[mote_locs_df['moteid'] == mote_id]
    if len(loc) > 0:
        return (loc.iloc[0]['x'], loc.iloc[0]['y'])
    return None
