
"""Main entry point for the Smart Agricultural Water Management model."""

from __future__ import annotations

from typing import Any

try:
    from .evapotranspiration import fao56_et0_daily
    from .crop_parameters import growth_stage, kc_range
    from .irrigation_requirement import (
        effective_rainfall_monthly,
        gross_irrigation_mm,
        net_rice_irrigation_mm,
        percolation_season_mm,
        soil_seepage_rate_range,
    )
    from .water_volume import water_volume_m3

except ImportError:
    from evapotranspiration import fao56_et0_daily
    from crop_parameters import growth_stage, kc_range
    from irrigation_requirement import (
        effective_rainfall_monthly,
        gross_irrigation_mm,
        net_rice_irrigation_mm,
        percolation_season_mm,
        soil_seepage_rate_range,
    )
    from water_volume import water_volume_m3


def calculate_daily_rice_water(
    *,
    tmean_c,
    tmax_c,
    tmin_c,
    rh_mean_pct,
    wind2_m_s,
    pressure_kpa,
    solar_mj_m2_day,
    latitude_deg,
    day_of_year,
    day_in_season,
):
    """Calculate ET0, Kc and ETc for one day."""

    et0 = fao56_et0_daily(
        tmean_c=tmean_c,
        tmax_c=tmax_c,
        tmin_c=tmin_c,
        rh_mean_pct=rh_mean_pct,
        wind2_m_s=wind2_m_s,
        pressure_kpa=pressure_kpa,
        solar_mj_m2_day=solar_mj_m2_day,
        latitude_deg=latitude_deg,
        day_of_year=day_of_year,
    )

    stage = growth_stage(day_in_season)

    kc_low, kc_high = kc_range(
        day_in_season
    )

    return {
        "growth_stage": stage,
        "et0_mm_day": et0,
        "kc_low": kc_low,
        "kc_high": kc_high,
        "etc_low_mm_day": et0 * kc_low,
        "etc_high_mm_day": et0 * kc_high,
    }


def calculate_seasonal_irrigation(
    *,
    etc_low_mm,
    etc_high_mm,
    effective_rain_mm,
    season_days=150,
    percolation_low_mm_day=4.0,
    percolation_high_mm_day=8.0,
    saturation_mm=200.0,
    water_layer_mm=100.0,
    stored_soil_water_mm=0.0,
    area_feddans=1.0,
    irrigation_efficiency=None,
):
    """Calculate seasonal rice irrigation requirement."""

    perc_low_mm = percolation_season_mm(
        percolation_low_mm_day,
        season_days
    )

    perc_high_mm = percolation_season_mm(
        percolation_high_mm_day,
        season_days
    )

    net_low_mm = net_rice_irrigation_mm(
        etc_mm=etc_low_mm,
        effective_rain_mm=effective_rain_mm,
        saturation_mm=saturation_mm,
        percolation_mm=perc_low_mm,
        water_layer_mm=water_layer_mm,
        stored_soil_water_mm=stored_soil_water_mm,
    )

    net_high_mm = net_rice_irrigation_mm(
        etc_mm=etc_high_mm,
        effective_rain_mm=effective_rain_mm,
        saturation_mm=saturation_mm,
        percolation_mm=perc_high_mm,
        water_layer_mm=water_layer_mm,
        stored_soil_water_mm=stored_soil_water_mm,
    )

    result = {
        "net_irrigation_low_mm": net_low_mm,
        "net_irrigation_high_mm": net_high_mm,
        "net_water_low_m3": water_volume_m3(
            net_low_mm,
            area_feddans
        ),
        "net_water_high_m3": water_volume_m3(
            net_high_mm,
            area_feddans
        ),
        "model_status": (
            "SCENARIO_ESTIMATE_NOT_FIELD_MEASURED"
        ),
    }

    if irrigation_efficiency is not None:

        gross_low_mm = gross_irrigation_mm(
            net_low_mm,
            irrigation_efficiency
        )

        gross_high_mm = gross_irrigation_mm(
            net_high_mm,
            irrigation_efficiency
        )

        result[
            "gross_irrigation_low_mm"
        ] = gross_low_mm

        result[
            "gross_irrigation_high_mm"
        ] = gross_high_mm

        result[
            "gross_water_low_m3"
        ] = water_volume_m3(
            gross_low_mm,
            area_feddans
        )

        result[
            "gross_water_high_m3"
        ] = water_volume_m3(
            gross_high_mm,
            area_feddans
        )

    return result


def soil_adjusted_percolation_range(
    clay_pct
):
    """Return low/high seepage range based on clay percentage."""

    return soil_seepage_rate_range(
        clay_pct
    )
