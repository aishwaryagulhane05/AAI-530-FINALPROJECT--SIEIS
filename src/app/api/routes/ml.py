"""ML inference endpoints - anomaly detection."""

import logging
import os
from typing import List

from fastapi import APIRouter, HTTPException

from src.app.api.schemas import AnomalyInput, AnomalyResult
from src.app import config

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ml", tags=["ml"])

# Global model cache (loaded once on first use)
_model = None
_model_path = None


def _load_model():
    """Load the latest anomaly detection model from models directory."""
    global _model, _model_path
    import pickle
    import json

    registry_path = config.MODELS_DIR / "model_registry.json"
    if not registry_path.exists():
        return None, None

    with open(registry_path) as f:
        registry = json.load(f)

    latest = registry.get("latest")
    if not latest:
        return None, None

    model_file = config.MODELS_DIR / latest
    if not model_file.exists():
        return None, None

    with open(model_file, "rb") as f:
        artifact = pickle.load(f)

    # Artifact is a dict {"pipeline": ..., "metrics": ..., "version": ...}
    if isinstance(artifact, dict) and "pipeline" in artifact:
        model = artifact["pipeline"]
    else:
        model = artifact  # backwards compat for plain pipeline pickles

    return model, str(model_file)


def _get_model():
    global _model, _model_path
    if _model is None:
        _model, _model_path = _load_model()
    return _model


def _score_to_severity(score: float) -> str:
    """Map anomaly score to human-readable severity.

    The anomaly_score is computed as:  0.5 - decision_function_score / 2
    So the natural split points are:
      < 0.50  → IsolationForest decision_function > 0  → model says normal
      0.50–0.65 → mild anomaly
      >= 0.65   → clear anomaly
    """
    if score >= 0.65:
        return "critical"
    elif score >= 0.5:
        return "warning"
    return "normal"


@router.post("/predict/anomaly", response_model=AnomalyResult, summary="Predict if a reading is anomalous")
def predict_anomaly(body: AnomalyInput):
    """Run anomaly detection on a single sensor reading.
    
    Returns an anomaly score (0=normal, 1=anomaly) and severity label.
    Falls back to a rule-based heuristic if no model is loaded.
    """
    model = _get_model()

    if model is not None:
        import numpy as np
        import pandas as pd
        from datetime import datetime

        # Build feature vector matching training: temperature, humidity, light, voltage, hour, day_of_week
        now = datetime.utcnow()
        X = pd.DataFrame([{
            "temperature": body.temperature,
            "humidity": body.humidity,
            "light": body.light,
            "voltage": body.voltage,
            "hour": now.hour,
            "day_of_week": now.weekday(),
        }])
        # Isolation Forest: predict returns -1 (anomaly) or 1 (normal)
        raw_pred = model.predict(X)[0]
        score_arr = model.decision_function(X)[0]
        # Convert decision function score to 0-1 range (higher = more anomalous)
        anomaly_score = float(max(0.0, min(1.0, 0.5 - score_arr / 2.0)))
        is_anomaly = raw_pred == -1
    else:
        # Rule-based fallback when no model is trained yet
        anomaly_score = 0.0
        flags = []
        if not (15 <= body.temperature <= 45):
            flags.append("temperature"); anomaly_score += 0.4
        if not (20 <= body.humidity <= 90):
            flags.append("humidity"); anomaly_score += 0.3
        if body.light < 0 or body.light > 2000:
            flags.append("light"); anomaly_score += 0.2
        if not (2.0 <= body.voltage <= 3.5):
            flags.append("voltage"); anomaly_score += 0.3
        anomaly_score = min(1.0, anomaly_score)
        is_anomaly = anomaly_score > 0.3

    return AnomalyResult(
        mote_id=body.mote_id,
        anomaly_score=round(anomaly_score, 4),
        is_anomaly=is_anomaly,
        severity=_score_to_severity(anomaly_score),
        input=body,
    )


@router.get("/model/info", summary="Get info about the currently loaded model")
def model_info():
    """Return metadata about the loaded anomaly detection model."""
    import json
    registry_path = config.MODELS_DIR / "model_registry.json"
    if registry_path.exists():
        with open(registry_path) as f:
            registry = json.load(f)
    else:
        registry = {}

    model = _get_model()
    return {
        "model_loaded": model is not None,
        "model_path": _model_path,
        "registry": registry,
        "fallback_mode": model is None,
    }


@router.post("/model/reload", summary="Reload model from disk")
def reload_model():
    """Force-reload the latest model from the models directory."""
    global _model, _model_path
    _model, _model_path = _load_model()
    return {
        "reloaded": True,
        "model_loaded": _model is not None,
        "model_path": _model_path,
    }
