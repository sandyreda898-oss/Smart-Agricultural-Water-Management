import math
import pytest
from src.evapotranspiration import saturation_vapor_pressure, fao56_et0_daily


def test_saturation_vapor_pressure_20c():
    assert saturation_vapor_pressure(20.0) == pytest.approx(2.338, abs=0.01)


def test_et0_returns_finite_positive_value():
    value = fao56_et0_daily(
        tmean_c=25.0, tmax_c=31.0, tmin_c=19.0, rh_mean_pct=60.0,
        wind2_m_s=3.0, pressure_kpa=101.3, solar_mj_m2_day=22.0,
        latitude_deg=31.1, day_of_year=170,
    )
    assert math.isfinite(value)
    assert value > 0
    assert value < 15


def test_et0_rejects_invalid_rh():
    with pytest.raises(ValueError):
        fao56_et0_daily(tmean_c=25, tmax_c=31, tmin_c=19, rh_mean_pct=120,
                        wind2_m_s=3, pressure_kpa=101.3, solar_mj_m2_day=22,
                        latitude_deg=31.1, day_of_year=170)
