import pytest
from src.irrigation_requirement import (
    effective_rainfall_monthly, percolation_season_mm, net_rice_irrigation_mm,
    soil_seepage_rate_range, gross_irrigation_mm,
)


def test_effective_rainfall_rules():
    assert effective_rainfall_monthly(0) == 0
    assert effective_rainfall_monthly(50) == pytest.approx(20.0)
    assert effective_rainfall_monthly(100) == pytest.approx(55.0)


def test_percolation_reference_range_for_150_days():
    assert percolation_season_mm(4, 150) == 600
    assert percolation_season_mm(8, 150) == 1200


def test_net_irrigation_balance():
    # ETc 1100 + SAT 200 + PERC 600 + WL 100 - Pe 50 = 1950 mm
    assert net_rice_irrigation_mm(1100, 50, percolation_mm=600) == pytest.approx(1950)


def test_soil_sensitivity_classes():
    assert soil_seepage_rate_range(45) == (1.0, 3.0)
    assert soil_seepage_rate_range(30) == (2.0, 5.0)
    assert soil_seepage_rate_range(20) == (4.0, 8.0)
    assert soil_seepage_rate_range(None) == (4.0, 8.0)


def test_gross_irrigation_efficiency():
    assert gross_irrigation_mm(2000, 0.8) == pytest.approx(2500)
    with pytest.raises(ValueError):
        gross_irrigation_mm(2000, 0)
