"""Validate input schema, units, categories, finite values, and observed feature ranges."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


def validate_frame(data: pd.DataFrame | dict | list[dict], schema: dict) -> tuple[pd.DataFrame, list[str]]:
    if schema.get("training_status") != "ready":
        raise ValueError("Prediction is disabled until a verified and reviewed model is released.")
    features = list(schema.get("features", []))
    if not features:
        raise ValueError("The model feature schema is empty.")
    frame = data.copy() if isinstance(data, pd.DataFrame) else pd.DataFrame(data if isinstance(data, list) else [data])
    missing = [column for column in features if column not in frame.columns]
    extra = [column for column in frame.columns if column not in features]
    if missing or extra:
        raise ValueError(f"Input columns do not match the model schema. Missing: {missing}; unexpected: {extra}.")
    frame = frame.loc[:, features].copy()
    warnings: list[str] = []
    nullable = set(schema.get("nullable_features", []))
    for column in features:
        if column in schema.get("numeric_features", []):
            numeric = pd.to_numeric(frame[column], errors="coerce")
            invalid = frame[column].notna() & numeric.isna()
            if invalid.any():
                raise ValueError(f"{column} must be numeric; found {int(invalid.sum())} non-numeric value(s).")
            finite = numeric.dropna().to_numpy(dtype=float)
            if not np.isfinite(finite).all():
                raise ValueError(f"{column} contains an infinite value.")
            if column not in nullable and numeric.isna().any():
                raise ValueError(f"{column} cannot be missing for this model.")
            frame[column] = numeric
            limits = schema.get("feature_ranges", {}).get(column, {})
            low, high = limits.get("min"), limits.get("max")
            outside = pd.Series(False, index=frame.index)
            if low is not None:
                outside |= numeric < low
            if high is not None:
                outside |= numeric > high
            if outside.any():
                warnings.append(f"{column} is outside the training range; the prediction may extrapolate.")
        else:
            values = frame[column].astype("string")
            known = set(schema.get("categorical_values", {}).get(column, []))
            unknown = sorted(set(values.dropna().astype(str)) - known) if known else []
            if unknown:
                warnings.append(f"{column} contains unseen category value(s): {unknown}.")
            if column not in nullable and values.isna().any():
                raise ValueError(f"{column} cannot be missing for this model.")
            frame[column] = values
    return frame, warnings


def validate_input(data, root: str | Path | None = None) -> tuple[pd.DataFrame, list[str]]:
    base = Path(root).resolve() if root else Path(__file__).resolve().parents[1]
    path = base / "models" / "feature_schema.json"
    if not path.is_file():
        raise ValueError("Feature schema is unavailable; no deployable model exists.")
    return validate_frame(data, json.loads(path.read_text(encoding="utf-8")))
