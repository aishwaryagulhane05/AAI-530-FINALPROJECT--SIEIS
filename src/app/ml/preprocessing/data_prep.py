"""Data preparation for ML training — fetches from MinIO Parquet files."""

import io
import logging
import os
from datetime import datetime
from typing import Optional, Tuple

import pandas as pd
import pyarrow.parquet as pq

logger = logging.getLogger(__name__)

FEATURE_COLS = ["temperature", "humidity", "light", "voltage"]
TIME_FEATURE_COLS = ["hour", "day_of_week"]
ALL_FEATURES = FEATURE_COLS + TIME_FEATURE_COLS


def _get_minio_client():
    from minio import Minio
    from src.app import config
    return Minio(
        config.MINIO_ENDPOINT,
        access_key=config.MINIO_ACCESS_KEY,
        secret_key=config.MINIO_SECRET_KEY,
        secure=config.MINIO_SECURE,
    )


def load_parquet_from_minio(
    bucket: Optional[str] = None,
    max_files: int = 0,
) -> pd.DataFrame:
    """Load Parquet files from MinIO and return a combined DataFrame.
    
    Think of MinIO as a filing cabinet where each drawer is a day's data.
    This function opens the drawers and reads all the files inside.
    
    Args:
        bucket: MinIO bucket name (defaults to config.MINIO_BUCKET)
        max_files: Maximum number of Parquet files to load (0 = all files)
    
    Returns:
        Combined DataFrame with all sensor readings
    """
    from src.app import config
    client = _get_minio_client()
    bucket = bucket or config.MINIO_BUCKET

    logger.info(f"Loading Parquet files from MinIO bucket={bucket}")
    objects = list(client.list_objects(bucket, recursive=True))
    parquet_objects = [o for o in objects if o.object_name.endswith(".parquet")]

    if not parquet_objects:
        logger.warning("No Parquet files found in MinIO")
        return pd.DataFrame()

    if max_files > 0:
        logger.info(f"Found {len(parquet_objects)} Parquet files, loading up to {max_files}")
        parquet_objects = parquet_objects[:max_files]
    else:
        logger.info(f"Found {len(parquet_objects)} Parquet files, loading ALL")

    frames = []
    for obj in parquet_objects:
        try:
            response = client.get_object(bucket, obj.object_name)
            data = response.read()
            response.close()
            df = pd.read_parquet(io.BytesIO(data))
            frames.append(df)
        except Exception as e:
            logger.warning(f"Failed to load {obj.object_name}: {e}")

    if not frames:
        logger.warning("All Parquet files failed to load")
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)
    logger.info(f"Loaded {len(combined)} rows from {len(frames)} files")
    return combined


def load_from_local_file(file_path: str, max_rows: int = 500_000) -> pd.DataFrame:
    """Load sensor data from a local text file (historical_data.txt format).
    
    Columns: date, time, epoch, mote_id, temperature, humidity, light, voltage, updated_timestamp
    """
    logger.info(f"Loading from local file: {file_path}")
    cols = ["date", "time", "epoch", "mote_id", "temperature", "humidity", "light", "voltage", "updated_timestamp"]
    df = pd.read_csv(
        file_path,
        sep=r"\s+",
        names=cols,
        na_values=["N/A", "nan", ""],
        nrows=max_rows,
        on_bad_lines="skip",
    )
    # Combine date + time into timestamp
    try:
        df["timestamp"] = pd.to_datetime(df["date"] + " " + df["time"], errors="coerce")
    except Exception:
        df["timestamp"] = pd.NaT
    return df


def prepare_features(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
    """Clean and engineer features for ML training.
    
    Like a chef prepping ingredients — this removes bad data,
    adds time-based features, and returns a clean feature matrix.
    
    Returns:
        X: Feature DataFrame (ready for sklearn)
        mote_ids: Series of mote IDs aligned with X
    """
    df = df.copy()

    # Ensure sensor columns are numeric
    for col in FEATURE_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Drop rows with all sensor values missing
    df = df.dropna(subset=FEATURE_COLS, how="all")

    # Parse timestamp columns from strings if needed
    # (consumer writes updated_timestamp as ISO strings in Parquet)
    for ts_col in ("updated_timestamp", "timestamp"):
        if ts_col in df.columns and not pd.api.types.is_datetime64_any_dtype(df[ts_col]):
            df[ts_col] = pd.to_datetime(df[ts_col], utc=True, errors="coerce")

    # Add time features — prefer updated_timestamp (real-time mapped), fall back to timestamp
    ts_series = None
    for ts_col in ("updated_timestamp", "timestamp"):
        if ts_col in df.columns and pd.api.types.is_datetime64_any_dtype(df[ts_col]):
            ts_series = df[ts_col]
            break

    if ts_series is not None:
        df["hour"] = ts_series.dt.hour
        df["day_of_week"] = ts_series.dt.dayofweek
    else:
        df["hour"] = 12  # fallback
        df["day_of_week"] = 0

    # Keep only valid ranges (sensor physics bounds)
    df = df[df["temperature"].between(-10, 80) | df["temperature"].isna()]
    df = df[df["humidity"].between(0, 100) | df["humidity"].isna()]
    df = df[df["light"].between(0, 3000) | df["light"].isna()]
    df = df[df["voltage"].between(0, 5) | df["voltage"].isna()]

    available_features = [c for c in ALL_FEATURES if c in df.columns]
    X = df[available_features].copy()

    # Fill remaining NaN with column medians
    X = X.fillna(X.median(numeric_only=True))

    mote_ids = df.get("mote_id", pd.Series(["unknown"] * len(df)))

    logger.info(f"Prepared feature matrix: {X.shape}, features={available_features}")
    return X, mote_ids
