"""Retrain the SIEIS anomaly detection model with fresh data.

Usage:
    python scripts/retrain_model.py [--days 30] [--source local|minio]

This script is for incremental retraining — run it after new data arrives.
Like refreshing a spam filter after the spam landscape changes.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import argparse
import json
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Retrain SIEIS anomaly detection model")
    parser.add_argument("--days", type=int, default=30, help="Days of recent data to use")
    parser.add_argument(
        "--source",
        choices=["local", "minio", "influxdb"],
        default="local",
        help="Data source for retraining",
    )
    parser.add_argument("--contamination", type=float, default=0.05)
    args = parser.parse_args()

    from src.app import config
    from src.app.ml.detector import _load_registry, train_anomaly_detector, save_model
    from src.app.ml.preprocessing.data_prep import (
        load_from_local_file,
        load_parquet_from_minio,
        prepare_features,
    )

    print("=" * 60)
    print("SIEIS — Incremental Model Retraining")
    print(f"Source: {args.source} | Days: {args.days}")
    print("=" * 60)

    # Show current registry state
    registry = _load_registry()
    print(f"\nCurrent registry: {len(registry.get('models', []))} model(s)")
    if registry.get("latest"):
        print(f"Current latest: {registry['latest']}")

    # Load data
    print(f"\n[1/4] Loading data...")
    if args.source == "minio":
        df = load_parquet_from_minio(max_files=50)
        if df.empty:
            print("⚠️  No MinIO data, falling back to local")
            args.source = "local"

    if args.source == "influxdb":
        print("Loading recent data from InfluxDB...")
        try:
            from influxdb_client import InfluxDBClient
            client = InfluxDBClient(
                url=config.INFLUX_URL, token=config.INFLUX_TOKEN, org=config.INFLUX_ORG
            )
            query_api = client.query_api()
            flux = f"""
from(bucket: "{config.INFLUX_BUCKET}")
  |> range(start: -{args.days}d)
  |> filter(fn: (r) => r["_measurement"] == "sensor_reading")
  |> pivot(rowKey:["_time","mote_id"], columnKey: ["_field"], valueColumn: "_value")
  |> limit(n: 200000)
"""
            import pandas as pd
            tables = query_api.query_data_frame(flux, org=config.INFLUX_ORG)
            client.close()
            if isinstance(tables, list):
                df = pd.concat(tables, ignore_index=True)
            else:
                df = tables
            # Rename _time to timestamp
            if "_time" in df.columns:
                df = df.rename(columns={"_time": "timestamp"})
            print(f"   Loaded {len(df):,} rows from InfluxDB")
        except Exception as e:
            print(f"⚠️  InfluxDB load failed ({e}), falling back to local")
            args.source = "local"

    if args.source == "local":
        hist_path = config.DATA_DIR / "processed" / "historical_data.txt"
        if not hist_path.exists():
            print(f"❌ historical_data.txt not found at {hist_path}")
            sys.exit(1)
        df = load_from_local_file(str(hist_path), max_rows=200_000)

    print(f"   Loaded {len(df):,} rows")

    # Prepare features
    print("\n[2/4] Preparing features...")
    X, mote_ids = prepare_features(df)
    print(f"   Feature matrix: {X.shape}")

    # Train
    print(f"\n[3/4] Training new model version...")
    pipeline, metrics = train_anomaly_detector(X, contamination=args.contamination)
    print(f"   Anomalies: {metrics['n_anomalies_detected']:,} ({metrics['anomaly_ratio']:.1%})")

    # Save with retrain tag
    print("\n[4/4] Saving new model version...")
    filename = save_model(pipeline, metrics, tag="retrain")

    print("\n" + "=" * 60)
    print("RETRAINING COMPLETE")
    print("=" * 60)
    print(f"  New model: {filename}")
    print(f"  Reload API: curl -X POST http://localhost:8000/api/v1/ml/model/reload")


if __name__ == "__main__":
    main()
