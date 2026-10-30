"""Weather preprocessing helpers used by the modeling notebooks."""
from __future__ import annotations
import pandas as pd

ET0_INPUT_COLUMNS = [
    "T2M", "T2M_MAX", "T2M_MIN", "RH2M", "WS2M", "PS", "ALLSKY_SFC_SW_DWN"
]


def prepare_weather_long_to_wide(weather: pd.DataFrame, grid: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Convert long daily weather to wide form, attach grid metadata, and create a complete modeling subset."""
    required = {"point_id", "obs_date", "parameter", "value"}
    missing = required.difference(weather.columns)
    if missing:
        raise ValueError(f"Missing weather columns: {sorted(missing)}")
    if weather.duplicated(["point_id", "obs_date", "parameter"]).any():
        raise ValueError("Duplicate point-date-parameter records found")

    work = weather.copy()
    work["obs_date"] = pd.to_datetime(work["obs_date"], errors="raise")
    wide = work.pivot(index=["point_id", "obs_date"], columns="parameter", values="value").reset_index()
    wide = wide.merge(grid, on="point_id", how="left", validate="many_to_one")

    missing_inputs = [c for c in ET0_INPUT_COLUMNS if c not in wide.columns]
    if missing_inputs:
        raise ValueError(f"Missing ET0 inputs after pivot: {missing_inputs}")
    if "PRECTOTCORR" not in wide.columns:
        raise ValueError("PRECTOTCORR is required for rainfall modeling")

    wide["et0_inputs_complete"] = wide[ET0_INPUT_COLUMNS].notna().all(axis=1)
    wide["rainfall_available"] = wide["PRECTOTCORR"].notna()
    clean = wide[wide["et0_inputs_complete"] & wide["rainfall_available"]].copy()
    return wide, clean


def add_rainfall_review_flag(weather_clean: pd.DataFrame, quantile: float = 0.999) -> pd.DataFrame:
    """Flag extreme rainfall for review without deleting it."""
    if not 0 < quantile < 1:
        raise ValueError("quantile must be between 0 and 1")
    out = weather_clean.copy()
    threshold = out["PRECTOTCORR"].quantile(quantile)
    out["rainfall_review_flag"] = out["PRECTOTCORR"] > threshold
    return out
