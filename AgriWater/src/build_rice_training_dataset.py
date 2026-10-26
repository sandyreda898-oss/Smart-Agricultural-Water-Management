import csv
import os
from collections import defaultdict
from statistics import mean

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "processed")
REPORTS = os.path.join(ROOT, "reports")
os.makedirs(REPORTS, exist_ok=True)

def read_csv(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def write_csv(path, rows):
    if not rows:
        print("WARNING: No rows to write:", path)
        return
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print("Created:", path, "| rows:", len(rows))

def number(value):
    try:
        if value is None or str(value).strip() == "":
            return None
        return float(value)
    except (ValueError, TypeError):
        return None

def aggregate(values, operation):
    valid = [v for v in values if v is not None]
    if not valid:
        return ""
    if operation == "sum":
        return round(sum(valid), 4)
    if operation == "min":
        return round(min(valid), 4)
    if operation == "max":
        return round(max(valid), 4)
    return round(mean(valid), 4)

weather_path = os.path.join(DATA, "rice_daily_water_demand_2017_2023.csv")
soil_path = os.path.join(DATA, "hwsd2_soil_samples_clean.csv")
calendar_path = os.path.join(DATA, "rice_crop_calendar.csv")
stats_path = os.path.join(DATA, "rice_statistics_2017_2023.csv")

for path in [weather_path, soil_path, calendar_path, stats_path]:
    if not os.path.exists(path):
        raise FileNotFoundError("Required file not found: " + path)

daily = read_csv(weather_path)
soil_rows = read_csv(soil_path)
calendar_rows = read_csv(calendar_path)
stats_rows = read_csv(stats_path)

soil_by_point = {r["point_id"]: r for r in soil_rows}
calendar_by_year = {str(r["season_year"]): r for r in calendar_rows}

groups = defaultdict(list)
for row in daily:
    groups[(str(row["year"]), row["point_id"])].append(row)

variables = [
    ("tmin_c", "mean"),
    ("tmax_c", "mean"),
    ("relative_humidity_pct", "mean"),
    ("wind_speed_m_s", "mean"),
    ("solar_radiation_mj_m2_day", "mean"),
    ("pressure_kpa", "mean"),
    ("rainfall_mm_day", "sum"),
    ("et0_mm_day", "sum"),
    ("estimated_etc_mm_day", "sum"),
]

training_rows = []
for (year, point_id), records in sorted(groups.items()):
    records.sort(key=lambda r: r["date"])
    first = records[0]
    soil = soil_by_point.get(point_id, {})
    calendar = calendar_by_year.get(year, {})

    result = {
        "year": year,
        "point_id": point_id,
        "latitude": first.get("latitude", ""),
        "longitude": first.get("longitude", ""),
        "season_start_date": records[0].get("date", ""),
        "season_end_date": records[-1].get("date", ""),
        "weather_day_count": len(records),
    }

    for variable, operation in variables:
        result[variable.replace("_mm_day", "_season_mm") if operation == "sum"
               and variable.endswith("_mm_day") else variable + "_season_sum"
               if operation == "sum" else variable + "_season_mean"] = aggregate(
            [number(r.get(variable)) for r in records], operation
        )

    etc = sum(number(r.get("estimated_etc_mm_day")) or 0 for r in records)
    rain = sum(number(r.get("rainfall_mm_day")) or 0 for r in records)
    result["estimated_etc_minus_rain_mm"] = round(etc - rain, 4)
    result["water_values_status"] = "MODEL_ESTIMATE_NOT_OBSERVED_IRRIGATION"
    result["water_method"] = "FAO56_PM_WITH_ESTIMATED_SEASONAL_KC"

    result["variety"] = calendar.get("variety", "Not specified")
    result["calendar_status"] = calendar.get("data_status", "")
    result["planting_window"] = calendar.get("planting_date", "")
    result["transplanting_window"] = calendar.get("transplanting_date", "")
    result["harvest_window"] = calendar.get("harvest_date", "")

    for col in [
        "HWSD2_SMU_ID", "top_depth_cm", "bottom_depth_cm",
        "sand_pct", "silt_pct", "clay_pct", "bulk",
        "organic_carbon", "ph_water", "texture_usda",
        "texture_soter", "soil_data_status"
    ]:
        result["soil_" + col] = soil.get(col, "")

    result["soil_missing_properties"] = soil.get("missing_soil_properties", "")
    result["actual_irrigation_m3_per_feddan"] = ""
    result["actual_yield_ton_per_feddan"] = ""
    result["actual_irrigation_label_status"] = "NOT_AVAILABLE"
    result["actual_yield_label_status"] = "NOT_AVAILABLE"
    result["training_readiness"] = "FEATURES_READY_TARGET_LABELS_REQUIRED"

    training_rows.append(result)

features_path = os.path.join(DATA, "rice_field_season_features_2017_2023.csv")
write_csv(features_path, training_rows)

# Keep governorate-level statistics separate; do not assign them to individual fields.
reference_rows = []
for row in stats_rows:
    area = number(row.get("area_feddan"))
    production = number(row.get("production_ton"))
    yield_value = number(row.get("yield_ton_per_feddan"))
    if yield_value is None and area and production:
        yield_value = production / area

    reference_rows.append({
        "year": row.get("year", ""),
        "country": row.get("country", ""),
        "governorate": row.get("governorate", ""),
        "governorate_ar": row.get("governorate_ar", ""),
        "crop": row.get("crop", ""),
        "season": row.get("season", ""),
        "area_feddan": row.get("area_feddan", ""),
        "production_ton": row.get("production_ton", ""),
        "governorate_yield_ton_per_feddan": (
            round(yield_value, 4) if yield_value is not None else ""
        ),
        "data_level": "GOVERNORATE_YEAR_AGGREGATE_NOT_FIELD_LABEL",
    })

reference_path = os.path.join(DATA, "rice_governorate_year_reference_2017_2023.csv")
write_csv(reference_path, reference_rows)

print("\nDONE")
print("Field-season rows:", len(training_rows))
print("Unique points:", len(set(r["point_id"] for r in training_rows)))
print("Years:", ", ".join(sorted(set(r["year"] for r in training_rows))))
print("Original source files were not modified.")
print("IMPORTANT: This creates feature data, not a supervised model with real field targets.")
