"""Validate prediction rows against the trained model's saved schema."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


def validate_frame(data: pd.DataFrame | dict, schema: dict) -> tuple[pd.DataFrame, list[str]]:
    features = schema.get("features", [])
    if schema.get("training_status") == "blocked" or not features:
        raise ValueError("Prediction is disabled until a verified field-measured model is trained.")
    frame = data.copy() if isinstance(data, pd.DataFrame) else pd.DataFrame([data])
    missing = [column for column in features if column not in frame.columns]
    extra = [column for column in frame.columns if column not in features]
    if missing or extra:
        raise ValueError(f"Input columns do not match model schema. Missing: {missing}; unexpected: {extra}.")
    frame = frame[features].copy()
    warnings: list[str] = []
    for column, limits in schema.get("feature_ranges", {}).items():
        values = pd.to_numeric(frame[column], errors="coerce")
        low, high = limits.get("min"), limits.get("max")
        outside = (values < low) if low is not None else pd.Series(False, index=values.index)
        if high is not None:
            outside = outside | (values > high)
        if outside.any():
            warnings.append(f"{column} is outside the observed training range; prediction may extrapolate.")
    for column in features:
        numeric = pd.to_numeric(frame[column], errors="coerce")
        if numeric.isna().any() or not np.isfinite(numeric.to_numpy(dtype=float)).all():
            raise ValueError(f"{column} must contain finite numeric values.")
        frame[column] = numeric
    return frame, warnings


def validate_input(data: pd.DataFrame | dict, root: str | Path | None = None) -> tuple[pd.DataFrame, list[str]]:
    base = Path(root).resolve() if root else Path(__file__).resolve().parents[1]
    schema_path = base / "models" / "feature_schema.json"
    if not schema_path.exists():
        raise ValueError("Feature schema is unavailable because the model has not been trained.")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    return validate_frame(data, schema)
