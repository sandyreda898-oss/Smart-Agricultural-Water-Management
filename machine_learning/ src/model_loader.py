"""Load only models that have passed the held-out evaluation gate."""
from __future__ import annotations

import json
from pathlib import Path


class ModelUnavailableError(RuntimeError):
    pass


def load_model(root: str | Path | None = None):
    import joblib

    base = Path(root).resolve() if root else Path(__file__).resolve().parents[1]
    models = base / "models"
    metadata_path = models / "model_metadata.json"
    model_path = models / "best_model.joblib"
    metrics_path = models / "model_metrics.json"
    if not metadata_path.exists() or not metrics_path.exists() or not model_path.exists():
        raise ModelUnavailableError("No trained model artifacts are present. Training is blocked until verified field labels are supplied.")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    if metadata.get("training_status") != "ready" or not metrics.get("final_test_metrics"):
        raise ModelUnavailableError("The model has not passed final held-out evaluation and is not available for prediction.")
    return joblib.load(model_path), metadata, metrics
