"""Prediction interface for downstream application code."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from .input_validation import validate_frame
from .model_loader import load_model


def predict_water_requirement(input_data, root: str | Path | None = None) -> dict:
    """Return a unit-labelled estimate and range warnings; raises when model is not released."""
    model, metadata, _, schema = load_model(root)
    frame, warnings = validate_frame(input_data, schema)
    prediction = np.asarray(model.predict(frame), dtype=float)
    if not np.isfinite(prediction).all():
        raise RuntimeError("Model returned a non-finite prediction; result is rejected.")
    if (prediction < 0).any():
        warnings.append("Model returned a negative irrigation estimate; result needs review.")
    values = [float(value) for value in prediction]
    return {
        "prediction": values[0] if len(values) == 1 else values,
        "unit": metadata.get("target_unit", "unspecified"),
        "model_version": metadata.get("model_version", "unknown"),
        "warnings": warnings,
        "prediction_status": "estimated",
    }
