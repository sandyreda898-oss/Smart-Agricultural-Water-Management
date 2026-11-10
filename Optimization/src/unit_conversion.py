"""
Unit Conversion Module
Converts water depths (mm) to volumes (m3) based on Egyptian feddans.
Formula: Water Volume (m3) = Water Depth (mm) * Area (feddan) * 4.2
Author: Sagda Samy
"""
def convert_mm_to_m3(depth_mm, area_feddan):
    return depth_mm * area_feddan * 4.2

def normalize_to_feddan(total_volume_m3, area_feddan):
    if area_feddan == 0:
        return 0
    return total_volume_m3 / area_feddan
