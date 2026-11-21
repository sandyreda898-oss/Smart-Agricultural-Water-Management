"""Load only a model explicitly released after grouped evaluation and reliability review."""
from __future__ import annotations

import json
from pathlib import Path


class ModelUnavailableError(RuntimeError):
    """Raised when no reviewed deployable model artifact is available."""


def load_model(root: str | Path | None = None):
    import joblib

    base = Path(root).resolve() if root else Path(__file__).resolve().parents[1]
    models = base / "models"
    required = [models / "best_model.joblib", models / "model_metadata.json",
                models / "model_metrics.json", models / "feature_schema.json"]
    if not all(path.is_file() for path in required):
        raise ModelUnavailableError("No complete model artifact set is available. Training may be blocked until verified field measurements are supplied.")
    metadata = json.loads(required[1].read_text(encoding="utf-8"))
    metrics = json.loads(required[2].read_text(encoding="utf-8"))
    schema = json.loads(required[3].read_text(encoding="utf-8"))
    if metadata.get("training_status") != "ready" or schema.get("training_status") != "ready":
        raise ModelUnavailableError("The saved model has not passed grouped evaluation and reliability review.")
    if not metrics.get("final_test_metrics"):
        raise ModelUnavailableError("Final held-out test metrics are missing; prediction is disabled.")
    return joblib.load(required[0]), metadata, metrics, schema
