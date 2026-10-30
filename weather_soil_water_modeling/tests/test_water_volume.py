import pytest
from src.water_volume import water_volume_m3


def test_example_from_task_brief():
    assert water_volume_m3(10, 5) == pytest.approx(210.0)


def test_one_mm_one_feddan():
    assert water_volume_m3(1, 1) == pytest.approx(4.2)


def test_invalid_inputs():
    with pytest.raises(ValueError):
        water_volume_m3(-1, 1)
    with pytest.raises(ValueError):
        water_volume_m3(10, 0)
