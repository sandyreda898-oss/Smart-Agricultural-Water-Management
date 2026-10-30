"""Soil and AWC preprocessing helpers."""
from __future__ import annotations
import pandas as pd


def prepare_soil(soil: pd.DataFrame, awc: pd.DataFrame, grid: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Merge soil, AWC, and grid tables and exclude rows explicitly marked EXCLUDE."""
    if soil.duplicated("point_id").any() or awc.duplicated("point_id").any():
        raise ValueError("Duplicate soil/AWC point_id detected")
    work = soil.copy()
    required_texture = ["sand_pct", "silt_pct", "clay_pct"]
    if all(c in work.columns for c in required_texture):
        work["texture_total_pct"] = work[required_texture].sum(axis=1, min_count=3)
    prepared = work.merge(awc, on=["point_id", "smu_id"], how="left", validate="one_to_one")
    prepared = prepared.merge(grid, on="point_id", how="left", validate="one_to_one")
    prepared["exclude_from_model"] = prepared["awc_use_recommendation"].eq("EXCLUDE")
    clean = prepared.loc[~prepared["exclude_from_model"]].copy()
    return prepared, clean
