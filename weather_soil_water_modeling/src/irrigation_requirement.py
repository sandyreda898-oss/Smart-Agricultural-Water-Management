"""Rice net/gross irrigation requirement helpers."""
from __future__ import annotations


def effective_rainfall_monthly(rainfall_mm: float) -> float:
    """Notebook 06 monthly effective-rainfall rule, clipped at zero."""
    if rainfall_mm is None or rainfall_mm < 0:
        raise ValueError("rainfall_mm must be non-negative")
    pe = 0.8 * rainfall_mm - 25.0 if rainfall_mm > 75.0 else 0.6 * rainfall_mm - 10.0
    return max(0.0, pe)


def net_rice_irrigation_mm(etc_mm: float, effective_rain_mm: float, *,
                           saturation_mm: float = 200.0,
                           percolation_mm: float,
                           water_layer_mm: float = 100.0,
                           stored_soil_water_mm: float = 0.0) -> float:
    """Seasonal paddy-rice net field requirement used by Notebook 06."""
    vals = [etc_mm, effective_rain_mm, saturation_mm, percolation_mm, water_layer_mm, stored_soil_water_mm]
    if any(v is None for v in vals):
        raise ValueError("All irrigation components are required")
    if any(v < 0 for v in vals):
        raise ValueError("Irrigation components cannot be negative")
    net = etc_mm + saturation_mm + percolation_mm + water_layer_mm - effective_rain_mm - stored_soil_water_mm
    return max(0.0, net)


def percolation_season_mm(rate_mm_day: float, season_days: int = 150) -> float:
    if rate_mm_day < 0 or season_days <= 0:
        raise ValueError("rate must be non-negative and season_days positive")
    return rate_mm_day * season_days


def soil_seepage_rate_range(clay_pct: float | None) -> tuple[float, float]:
    """Project soil-sensitivity scenario used in Notebook 06."""
    if clay_pct is None:
        return 4.0, 8.0
    if not 0 <= clay_pct <= 100:
        raise ValueError("clay_pct must be 0–100")
    if clay_pct >= 40:
        return 1.0, 3.0
    if clay_pct >= 25:
        return 2.0, 5.0
    return 4.0, 8.0


def gross_irrigation_mm(net_mm: float, efficiency: float) -> float:
    if net_mm < 0:
        raise ValueError("net_mm cannot be negative")
    if not 0 < efficiency <= 1:
        raise ValueError("efficiency must be in (0, 1]")
    return net_mm / efficiency
