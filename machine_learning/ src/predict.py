"""Prediction interface for the web application."""
from __future__ import annotations

from pathlib import Path

from .input_validation import validate_input
from .model_loader import load_model


def predict_water_requirement(input_data, root: str | Path | None = None) -> dict:
    base = Path(root).resolve() if root else Path(__file__).resolve().parents[1]
    model, metadata, _ = load_model(base)
    frame, warnings = validate_input(input_data, base)
    prediction = model.predict(frame)
    if not all(float(value) >= 0 for value in prediction):
        warnings.append("Model returned a negative estimate; verify inputs and model reliability.")
    return {
        "prediction": [float(value) for value in prediction],
        "unit": "m3/feddan",
        "model_version": metadata.get("model_version", "unknown"),
        "warnings": warnings,
        "prediction_status": "estimated",
    }
