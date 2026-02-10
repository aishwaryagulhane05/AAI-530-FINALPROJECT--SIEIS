"""Load and clean Intel Lab sensor data for simulation."""

import pandas as pd
from typing import Dict, Optional, Tuple


def load_data_loader(data_path: str, mote_locs_path: str) -> Tuple[Dict[int, pd.DataFrame], pd.DataFrame]:
    """
    Load Intel Lab sensor data and mote locations.
    
    Args:
        data_path: Path to data.txt file
        mote_locs_path: Path to mote_locs.txt file
    
    Returns:
        Tuple of (mote_data_dict, mote_locations_df)
        - mote_data_dict: {mote_id: DataFrame with sensor readings}
        - mote_locations_df: DataFrame with mote locations
    """
    
    # Load sensor data
    # File columns: date time epoch moteid temperature humidity light voltage
    df = pd.read_csv(
        data_path,
        sep=r'\s+',
        header=None,
        names=['date', 'time', 'epoch', 'moteid', 'temperature', 'humidity', 'light', 'voltage'],
        na_values=['?'],
        dtype={
            'date': str,
            'time': str,
            'epoch': float,  # read as float to allow missing values
            'moteid': float,
            'temperature': float,
            'humidity': float,
            'light': float,
            'voltage': float
        }
    )

    # Combine date + time into a single timestamp column
    df['timestamp'] = pd.to_datetime(
        df['date'] + ' ' + df['time'], format='%Y-%m-%d %H:%M:%S.%f', errors='coerce'
    )

    # Drop rows where timestamp could not be parsed
    df = df.dropna(subset=['timestamp'])

    # Convert moteid to int and drop rows missing moteid
    df = df.dropna(subset=['moteid'])
    df['moteid'] = df['moteid'].astype(int)
    # Drop rows with null temperature or humidity
    df = df.dropna(subset=['temperature', 'humidity'])
    
    # Fill null light with 0
    df['light'] = df['light'].fillna(0.0)
    
    # Forward fill voltage per mote to keep continuity in streams
    df = df.sort_values(['moteid', 'timestamp'])
    df['voltage'] = df.groupby('moteid')['voltage'].fillna(method='ffill')
    
    # Fill any remaining null voltage with backward fill (for first readings)
    df['voltage'] = df['voltage'].fillna(method='bfill')
    
    # Split by mote ID for per-sensor simulation
    mote_data_dict = {}
    for mote_id in df['moteid'].unique():
        mote_df = df[df['moteid'] == mote_id].copy()
        # Sort by timestamp
        mote_df = mote_df.sort_values('timestamp').reset_index(drop=True)
        mote_data_dict[mote_id] = mote_df
    
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
