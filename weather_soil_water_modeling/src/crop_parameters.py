"""Rice growth-stage and Kc utilities."""
from __future__ import annotations
import numpy as np


def growth_stage(day_in_season: int) -> str:
    """Return the 150-day reference rice growth stage."""
    if 1 <= day_in_season <= 30:
        return "initial"
    if 31 <= day_in_season <= 60:
        return "development"
    if 61 <= day_in_season <= 120:
        return "mid_season"
    if 121 <= day_in_season <= 150:
        return "late_season"
    raise ValueError("day_in_season must be between 1 and 150")


def kc_range(day_in_season: int) -> tuple[float, float]:
    """Return low/high Kc used in Notebook 05 for the 150-day reference rice season."""
    stage = growth_stage(day_in_season)
    if stage == "initial":
        return 1.05, 1.05
    if stage == "development":
        frac = (day_in_season - 30) / 30.0
        kc = 1.05 + frac * (1.20 - 1.05)
        return kc, kc
    if stage == "mid_season":
        return 1.20, 1.20
    frac = (day_in_season - 120) / 30.0
    low = 1.20 + frac * (0.60 - 1.20)
    high = 1.20 + frac * (0.90 - 1.20)
    return float(low), float(high)
