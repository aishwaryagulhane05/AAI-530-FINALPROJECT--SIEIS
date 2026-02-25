"""Isolation Forest anomaly detector for SIEIS sensor data."""

import json
import logging
import pickle
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline

from src.app import config

logger = logging.getLogger(__name__)

REGISTRY_FILE = config.MODELS_DIR / "model_registry.json"


def _load_registry() -> Dict:
    if REGISTRY_FILE.exists():
        with open(REGISTRY_FILE) as f:
            return json.load(f)
    return {"models": [], "latest": None}


def _save_registry(registry: Dict):
    config.MODELS_DIR.mkdir(parents=True, exist_ok=True)
    with open(REGISTRY_FILE, "w") as f:
        json.dump(registry, f, indent=2)


def train_anomaly_detector(
    X: pd.DataFrame,
    contamination: float = 0.05,
    n_estimators: int = 100,
    random_state: int = 42,
) -> Tuple[Pipeline, Dict]:
    """Train an Isolation Forest anomaly detector.
    
    Analogy: Imagine a forest of decision trees. Each tree randomly
    partitions data points. Anomalies (outliers) get isolated in fewer
    splits than normal points — like a rotten apple that's easy to spot.
    
    Args:
        X: Feature matrix (temperature, humidity, light, voltage, hour, day_of_week)
        contamination: Expected fraction of anomalies in data (5% default)
        n_estimators: Number of trees in the forest
        random_state: For reproducibility
    
    Returns:
        pipeline: Trained sklearn Pipeline (scaler + model)
        metrics: Training statistics dict
    """
    logger.info(f"Training Isolation Forest: n_samples={len(X)}, contamination={contamination}")

    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("model", IsolationForest(
            n_estimators=n_estimators,
            contamination=contamination,
            random_state=random_state,
            n_jobs=-1,
        )),
    ])

    pipeline.fit(X)

    # Compute training metrics
    predictions = pipeline.predict(X)
    scores = pipeline.decision_function(X)
    n_anomalies = int((predictions == -1).sum())
    anomaly_ratio = n_anomalies / len(X)

    metrics = {
        "n_samples": len(X),
        "n_features": X.shape[1],
        "feature_names": list(X.columns),
        "n_anomalies_detected": n_anomalies,
        "anomaly_ratio": round(anomaly_ratio, 4),
        "contamination": contamination,
        "n_estimators": n_estimators,
        "score_mean": round(float(np.mean(scores)), 4),
        "score_std": round(float(np.std(scores)), 4),
        "trained_at": datetime.utcnow().isoformat(),
    }

    logger.info(f"Training complete: {n_anomalies}/{len(X)} anomalies ({anomaly_ratio:.1%})")
    return pipeline, metrics


def save_model(pipeline: Pipeline, metrics: Dict, tag: Optional[str] = None) -> str:
    """Save trained model and update model registry.
    
    Returns the filename of the saved model.
    """
    config.MODELS_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    tag_suffix = f"_{tag}" if tag else ""
    filename = f"anomaly_detector_{timestamp}{tag_suffix}.pkl"
    filepath = config.MODELS_DIR / filename

    artifact = {
        "pipeline": pipeline,
        "metrics": metrics,
        "version": timestamp,
    }

    with open(filepath, "wb") as f:
        pickle.dump(artifact, f)

    logger.info(f"Model saved: {filepath}")

    # Update registry
    registry = _load_registry()
    registry["models"].append({
        "filename": filename,
        "trained_at": metrics["trained_at"],
        "n_samples": metrics["n_samples"],
        "anomaly_ratio": metrics["anomaly_ratio"],
        "features": metrics["feature_names"],
    })
    registry["latest"] = filename
    _save_registry(registry)

    logger.info(f"Registry updated: latest={filename}")
    return filename


def load_latest_model() -> Optional[Pipeline]:
    """Load the latest trained model from registry."""
    registry = _load_registry()
    latest = registry.get("latest")
    if not latest:
        logger.warning("No model in registry")
        return None

    model_path = config.MODELS_DIR / latest
    if not model_path.exists():
        logger.error(f"Model file not found: {model_path}")
        return None

    with open(model_path, "rb") as f:
        artifact = pickle.load(f)

    logger.info(f"Loaded model: {latest}")
    return artifact["pipeline"]
