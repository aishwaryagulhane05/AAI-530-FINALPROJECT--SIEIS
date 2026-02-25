"""Train the SIEIS anomaly detection model.

Usage:
    python scripts/train_model.py [--source local|minio] [--max-rows 500000]

Steps:
1. Load data from MinIO (Parquet) or local file
2. Prepare features (clean, engineer time features)
3. Train Isolation Forest
4. Save model artifact + update registry
5. Auto-reload API + test prediction
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import argparse
import json
import logging
import requests
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# API URL — try localhost first, fallback to container name
API_URLS = [
    "http://localhost:8000",
    "http://sieis-api:8000",
]


def get_api_url():
    """Find which API URL is reachable."""
    for url in API_URLS:
        try:
            r = requests.get(f"{url}/health", timeout=3)
            if r.status_code == 200:
                return url
        except Exception:
            continue
    return None


def fix_registry_paths(registry_path: Path):
    """Fix Windows absolute paths in registry to relative paths for container compatibility."""
    if not registry_path.exists():
        return

    with open(registry_path, "r") as f:
        registry = json.load(f)

    changed = False
    for key, info in registry.items():
        if isinstance(info, dict) and "path" in info:
            p = info["path"]
            filename = Path(p).name
            relative = f"src/app/ml/models/{filename}"
            if info["path"] != relative:
                info["path"] = relative
                changed = True
                logger.info(f"Fixed path for {key}: {p} → {relative}")

    if changed:
        with open(registry_path, "w") as f:
            json.dump(registry, f, indent=2)
        print("   ✅ Registry paths normalized for container compatibility")


def reload_api_model(api_url: str):
    """Tell the API to reload the latest model from disk."""
    try:
        r = requests.post(f"{api_url}/api/v1/ml/model/reload", timeout=10)
        if r.status_code == 200:
            print(f"   ✅ API model reloaded: {r.json()}")
        else:
            print(f"   ⚠️  API reload returned {r.status_code}: {r.text}")
    except Exception as e:
        print(f"   ⚠️  Could not reload API model: {e}")


def test_prediction(api_url: str):
    """Send a test prediction to verify the model is working end-to-end."""
    payload = {
        "temperature": 22.5,
        "humidity": 55.0,
        "light": 300,
        "voltage": 2.9
    }
    try:
        r = requests.post(
            f"{api_url}/api/v1/ml/predict/anomaly",
            json=payload,
            timeout=10
        )
        if r.status_code == 200:
            result = r.json()
            is_anomaly = result.get("is_anomaly", "unknown")
            score = result.get("anomaly_score", "unknown")
            print(f"   ✅ Test prediction OK — is_anomaly: {is_anomaly}, score: {score}")
        else:
            print(f"   ⚠️  Prediction returned {r.status_code}: {r.text}")
    except Exception as e:
        print(f"   ⚠️  Could not test prediction: {e}")


def main():
    parser = argparse.ArgumentParser(description="Train SIEIS anomaly detection model")
    parser.add_argument(
        "--source",
        choices=["local", "minio"],
        default="minio",
        help="Data source: 'local' (historical_data.txt) or 'minio' (Parquet files)",
    )
    parser.add_argument("--max-rows", type=int, default=0, help="Max rows to load (0 = all rows)")
    parser.add_argument("--contamination", type=float, default=0.05, help="Expected anomaly fraction")
    parser.add_argument("--tag", type=str, default=None, help="Optional tag for model filename")
    parser.add_argument("--no-reload", action="store_true", help="Skip API reload after training")
    args = parser.parse_args()

    print("=" * 60)
    print("SIEIS — Anomaly Detection Model Training")
    max_rows_label = 'ALL' if args.max_rows == 0 else f'{args.max_rows:,}'
    print(f"Source: {args.source} | Max rows: {max_rows_label}")
    print("=" * 60)

    from src.app import config
    from src.app.ml.preprocessing.data_prep import (
        load_from_local_file,
        load_parquet_from_minio,
        prepare_features,
    )
    from src.app.ml.detector import train_anomaly_detector, save_model

    # ── Step 1: Load data ──────────────────────────────────────────
    print(f"\n[1/5] Loading data from {args.source}...")
    if args.source == "minio":
        df = load_parquet_from_minio(max_files=0)  # 0 = load all files
        if df.empty:
            print("⚠️  No data in MinIO. Falling back to local file.")
            args.source = "local"
        else:
            if args.max_rows > 0 and len(df) > args.max_rows:
                df = df.sample(n=args.max_rows, random_state=42)
                print(f"   Sampled down to {args.max_rows:,} rows")

    if args.source == "local":
        hist_path = config.DATA_DIR / "processed" / "historical_data.txt"
        if not hist_path.exists():
            print(f"❌ historical_data.txt not found at {hist_path}")
            sys.exit(1)
        df = load_from_local_file(str(hist_path), max_rows=args.max_rows)

    print(f"   ✅ Loaded {len(df):,} rows")

    # ── Step 2: Prepare features ───────────────────────────────────
    print("\n[2/5] Preparing features...")
    X, mote_ids = prepare_features(df)
    print(f"   ✅ Feature matrix: {X.shape} | Features: {list(X.columns)}")
    print(f"   ✅ Unique motes: {len(set(mote_ids))}")

    if len(X) < 100:
        print("❌ Too few samples for training (need at least 100)")
        sys.exit(1)

    # ── Step 3: Train ──────────────────────────────────────────────
    print(f"\n[3/5] Training Isolation Forest (contamination={args.contamination})...")
    pipeline, metrics = train_anomaly_detector(X, contamination=args.contamination)
    print(f"   ✅ Training complete!")
    print(f"   ✅ Samples: {metrics['n_samples']:,}")
    print(f"   ✅ Anomalies detected: {metrics['n_anomalies_detected']:,} ({metrics['anomaly_ratio']:.1%})")

    # ── Step 4: Save + fix registry paths ─────────────────────────
    print("\n[4/5] Saving model...")
    filename = save_model(pipeline, metrics, tag=args.tag)
    print(f"   ✅ Model saved: src/app/ml/models/{filename}")
    fix_registry_paths(Path("src/app/ml/models/model_registry.json"))

    # ── Step 5: Reload API + test prediction ──────────────────────
    print("\n[5/5] Reloading API & testing prediction...")
    if args.no_reload:
        print("   ⏭️  Skipped (--no-reload flag set)")
    else:
        api_url = get_api_url()
        if api_url:
            print(f"   API found at: {api_url}")
            reload_api_model(api_url)
            test_prediction(api_url)
        else:
            print("   ⚠️  API not reachable at localhost:8000 or sieis-api:8000")
            print("   Run manually: curl -X POST http://localhost:8000/api/v1/ml/model/reload")

    # ── Summary ────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("TRAINING COMPLETE")
    print("=" * 60)
    print(f"  Model file    : src/app/ml/models/{filename}")
    print(f"  Source        : {args.source}")
    print(f"  Samples       : {metrics['n_samples']:,}")
    print(f"  Anomaly ratio : {metrics['anomaly_ratio']:.1%}")
    print(f"  Unique motes  : {len(set(mote_ids))}")
    print("=" * 60)


if __name__ == "__main__":
    main()
