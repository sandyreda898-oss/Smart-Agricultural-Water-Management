"""Leakage-safe preprocessing factories for structured regression data."""
from __future__ import annotations

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


def build_preprocessor(frame: pd.DataFrame, feature_order: list[str] | None = None) -> ColumnTransformer:
    """Build transformers that are fitted only when the enclosing training pipeline is fitted."""
    columns = list(feature_order or frame.columns)
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(f"Requested feature columns are missing: {missing}")
    numeric = [column for column in columns if pd.api.types.is_numeric_dtype(frame[column])]
    categorical = [column for column in columns if column not in numeric]
    transformers = []
    if numeric:
        transformers.append(("numeric", Pipeline([
            ("imputer", SimpleImputer(strategy="median", add_indicator=True)),
            ("scaler", StandardScaler()),
        ]), numeric))
    if categorical:
        transformers.append(("categorical", Pipeline([
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("encoder", OneHotEncoder(handle_unknown="ignore")),
        ]), categorical))
    if not transformers:
        raise ValueError("At least one feature column is required.")
    return ColumnTransformer(transformers, remainder="drop", verbose_feature_names_out=False)


def build_model_pipeline(frame: pd.DataFrame, estimator, feature_order: list[str] | None = None) -> Pipeline:
    columns = list(feature_order or frame.columns)
    return Pipeline([("preprocessing", build_preprocessor(frame, columns)), ("model", estimator)])
