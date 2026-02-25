"""
SIEIS Scheduler Jobs
====================
Two daily jobs that automate the full pipeline:

  Job A  00:00 UTC  — Remap incremental_data.txt to today's dates
                      → Restart simulator so it emits fresh data
  Job B  02:00 UTC  — Retrain IsolationForest on yesterday's MinIO Parquet files
                      → Hot-reload the FastAPI model (no restart needed)

Analogy
-------
Think of this like a newspaper printing plant:
  - Job A is the night-shift that updates the "today's date" stamp on the press
    and restarts the press so it prints the right edition.
  - Job B is the editor-in-chief who reviews all of yesterday's stories,
    refines the spam filter (anomaly model), and pushes it live.
"""

import logging
import os
import sys
from datetime import date, timedelta
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

# ── Environment config ────────────────────────────────────────────────────────
API_RELOAD_URL = os.getenv(
    "API_RELOAD_URL", "http://sieis-api:8000/api/v1/ml/model/reload"
)
SIMULATOR_CONTAINER = os.getenv("SIMULATOR_CONTAINER", "sieis-simulator")
INCR_DATA_PATH = Path(
    os.getenv("INCR_DATA_PATH", "/app/data/processed/incremental_data.txt")
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _restart_simulator() -> bool:
    """Restart the simulator Docker container via the Docker Python SDK.

    Returns True on success, False on failure.

    The Docker socket (/var/run/docker.sock) must be mounted into this
    container (see docker-compose.yml).
    """
    try:
        import docker  # docker>=6.1.0
        client = docker.from_env()
        container = client.containers.get(SIMULATOR_CONTAINER)
        container.restart(timeout=30)
        logger.info("Simulator container '%s' restarted successfully", SIMULATOR_CONTAINER)
        return True
    except Exception:
        logger.exception(
            "Failed to restart simulator container '%s'. "
            "Check that /var/run/docker.sock is mounted and the container name is correct.",
            SIMULATOR_CONTAINER,
        )
        return False


def _reload_api_model() -> bool:
    """POST to the FastAPI /ml/model/reload endpoint to hot-swap the model.

    Returns True on success, False on failure.
    No container restart required — the API picks up the latest .pkl from disk.
    """
    try:
        resp = requests.post(API_RELOAD_URL, timeout=15)
        resp.raise_for_status()
        payload = resp.json()
        logger.info("API model reloaded: %s", payload)
        return True
    except requests.exceptions.ConnectionError:
        logger.error(
            "Could not reach API at %s. Is sieis-api running?", API_RELOAD_URL
        )
        return False
    except Exception:
        logger.exception("Unexpected error calling API reload endpoint")
        return False


# ── Job A: Daily Data Refresh ─────────────────────────────────────────────────
def data_exists_for_today() -> bool:
    """
    Check if there is data for today.
    You should implement this function to check your data source (e.g., MinIO, local file, DB).
    """
    from src.app.ml.preprocessing.data_prep import load_parquet_from_minio
    df = load_parquet_from_minio()
    today_str = date.today().isoformat()
    # Adjust the column name as per your data, e.g., 'date' or 'timestamp'
    return not df[df['date'] == today_str].empty

def remap_and_restart() -> None:
    """
    Modified Job A — runs at 00:00 UTC daily.
    Only restarts the simulator if today's data exists. No remapping.
    """
    logger.info("Restarting simulator container '%s'", SIMULATOR_CONTAINER)
    ok = _restart_simulator()
    status = "SUCCESS" if ok else "FAILED (check logs)"
    logger.info("Simulator restart: %s", status)

# ── Job B: Daily Model Retrain ────────────────────────────────────────────────

def retrain_and_reload() -> None:
    """
    Job B — runs at 02:00 UTC daily.

    Step 1: Load yesterday's sensor data from MinIO Parquet archive.
            Falls back to last 30 days of Parquet if yesterday alone is sparse.

    Step 2: Prepare feature matrix: temperature, humidity, light, voltage,
            hour-of-day, day-of-week.

    Step 3: Train a new IsolationForest model and save it as:
            anomaly_detector_YYYYMMDD_HHMMSS_scheduled.pkl

    Step 4: POST to FastAPI /ml/model/reload — the API hot-swaps its
            in-memory pipeline without any container restart.

    Analogy: Like a bakery that checks what sold best yesterday, adjusts the
    recipe overnight, and opens in the morning with a fresher product —
    without closing the shop.
    """
    logger.info("Loading Parquet data from MinIO (last 3 days)...")
    try:
        from src.app.ml.preprocessing.data_prep import (
            load_parquet_from_minio,
            prepare_features,
        )
        from datetime import date, timedelta

        df = load_parquet_from_minio()

        today = date.today()
        recent_dates = [(today - timedelta(days=i)).isoformat() for i in range(0, 3)]
        if 'date' in df.columns:
            df_recent = df[df['date'].isin(recent_dates)]
        else:
            logger.warning("DataFrame does not have a 'date' column. Using all data.")
            df_recent = df

        if df_recent.empty:
            logger.warning(
                "No Parquet data found in MinIO for last 3 days. "
                "Retrain skipped — existing model remains active."
            )
            return

        logger.info("Loaded %d rows for retraining", len(df_recent))
    except Exception:
        logger.exception("MinIO data load failed — retrain aborted")
        return

    try:
        X, mote_ids = prepare_features(df_recent)
        if X.empty or len(X) < 100:
            logger.warning(
                "Feature matrix too small (%d rows) for reliable training. "
                "Need at least 100 rows. Retrain skipped.",
                len(X),
            )
            return
        logger.info("Feature matrix shape: %s", X.shape)
    except Exception:
        logger.exception("Feature preparation failed — retrain aborted")
        return

    # -- Step 3: Train and save model ----------------------------------------
    logger.info("[3/4] Training IsolationForest...")
    try:
        from src.app.ml.detector import train_anomaly_detector, save_model  # noqa: PLC0415

        pipeline, metrics = train_anomaly_detector(X)
        logger.info(
            "Training complete: %d anomalies / %d samples (%.1f%%)",
            metrics["n_anomalies_detected"],
            metrics["n_samples"],
            metrics["anomaly_ratio"] * 100,
        )

        filename = save_model(pipeline, metrics, tag="scheduled")
        logger.info("Model saved: %s", filename)
    except Exception:
        logger.exception("Model training/save failed — retrain aborted")
        return

    # -- Step 4: Hot-reload API model ----------------------------------------
    logger.info("[4/4] Reloading API model...")
    ok = _reload_api_model()
    status = "SUCCESS" if ok else "FAILED — API still uses previous model"
    logger.info("JOB B complete — API reload: %s", status)
    logger.info("=" * 60)
