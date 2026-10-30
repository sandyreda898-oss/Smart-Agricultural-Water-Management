"""Water-depth to volume conversion for Egyptian feddans."""
from __future__ import annotations

M3_PER_MM_FEDDAN = 4.2


def water_volume_m3(depth_mm: float, area_feddans: float) -> float:
    """Convert irrigation depth in mm over area in feddans to cubic metres."""
    if depth_mm is None or area_feddans is None:
        raise ValueError("depth_mm and area_feddans are required")
    if depth_mm < 0:
        raise ValueError("depth_mm cannot be negative")
    if area_feddans <= 0:
        raise ValueError("area_feddans must be greater than zero")
    return depth_mm * area_feddans * M3_PER_MM_FEDDAN
