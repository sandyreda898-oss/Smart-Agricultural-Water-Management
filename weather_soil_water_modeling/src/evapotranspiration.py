"""FAO-56 Penman-Monteith daily reference evapotranspiration."""
from __future__ import annotations
import math

GSC = 0.0820
SIGMA = 4.903e-9


def saturation_vapor_pressure(temp_c: float) -> float:
    return 0.6108 * math.exp((17.27 * temp_c) / (temp_c + 237.3))


def fao56_et0_daily(*, tmean_c: float, tmax_c: float, tmin_c: float, rh_mean_pct: float,
                    wind2_m_s: float, pressure_kpa: float, solar_mj_m2_day: float,
                    latitude_deg: float, day_of_year: int) -> float:
    """Calculate daily ET0 (mm/day) using the same assumptions as Notebook 04.

    Mean RH estimates actual vapor pressure; G=0; Rso=0.75*Ra (near-sea-level approximation).
    """
    vals = [tmean_c, tmax_c, tmin_c, rh_mean_pct, wind2_m_s, pressure_kpa, solar_mj_m2_day, latitude_deg]
    if any(v is None for v in vals):
        raise ValueError("All ET0 inputs are required")
    if not 0 <= rh_mean_pct <= 100:
        raise ValueError("Relative humidity must be 0–100%")
    if wind2_m_s < 0 or solar_mj_m2_day < 0:
        raise ValueError("Wind speed and solar radiation must be non-negative")
    if not 1 <= day_of_year <= 366:
        raise ValueError("day_of_year must be 1–366")

    es_tmax = saturation_vapor_pressure(tmax_c)
    es_tmin = saturation_vapor_pressure(tmin_c)
    es = (es_tmax + es_tmin) / 2.0
    ea = es * rh_mean_pct / 100.0
    vpd = es - ea
    delta = 4098.0 * saturation_vapor_pressure(tmean_c) / ((tmean_c + 237.3) ** 2)
    gamma = 0.000665 * pressure_kpa

    phi = math.radians(latitude_deg)
    j = day_of_year
    dr = 1.0 + 0.033 * math.cos(2 * math.pi * j / 365.0)
    solar_declination = 0.409 * math.sin((2 * math.pi * j / 365.0) - 1.39)
    acos_arg = -math.tan(phi) * math.tan(solar_declination)
    acos_arg = min(1.0, max(-1.0, acos_arg))
    ws = math.acos(acos_arg)
    ra = ((24 * 60 / math.pi) * GSC * dr *
          (ws * math.sin(phi) * math.sin(solar_declination) +
           math.cos(phi) * math.cos(solar_declination) * math.sin(ws)))
    rs = solar_mj_m2_day
    rso = 0.75 * ra
    ratio = 0.0 if rso <= 0 else min(1.0, max(0.0, rs / rso))
    rns = 0.77 * rs
    tmax_k, tmin_k = tmax_c + 273.16, tmin_c + 273.16
    rnl = (SIGMA * ((tmax_k**4 + tmin_k**4) / 2.0) *
           (0.34 - 0.14 * math.sqrt(max(0.0, ea))) *
           (1.35 * ratio - 0.35))
    rn = rns - rnl
    g = 0.0
    et0 = ((0.408 * delta * (rn - g) +
            gamma * (900.0 / (tmean_c + 273.0)) * wind2_m_s * vpd) /
           (delta + gamma * (1.0 + 0.34 * wind2_m_s)))
    return float(et0)
