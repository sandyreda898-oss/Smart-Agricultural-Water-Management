import csv
import os
from collections import defaultdict
from statistics import mean

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "processed")

INPUT = os.path.join(DATA, "rice_daily_water_demand_2017_2023.csv")
OUTPUT = os.path.join(DATA, "rice_water_scenarios_2017_2023.csv")
SUMMARY = os.path.join(DATA, "rice_water_scenarios_annual_summary.csv")

FEDAN_M2 = 4200
M3_PER_FEDAN_PER_MM = FEDAN_M2 / 1000

LAND_PREPARATION_MM = 200
ESTABLISHMENT_MM = 100
SEEPAGE_LOW_MM_DAY = 4
SEEPAGE_HIGH_MM_DAY = 8

def num(v):
    try:
        return float(v) if v is not None and str(v).strip() else None
    except (TypeError, ValueError):
        return None

with open(INPUT, "r", encoding="utf-8-sig", newline="") as f:
    daily = list(csv.DictReader(f))

groups = defaultdict(list)
for row in daily:
    groups[(row["year"], row["point_id"])].append(row)

results = []
for (year, point), records in sorted(groups.items()):
    etc_values = [num(r.get("estimated_etc_mm_day")) for r in records]
    rain_values = [num(r.get("rainfall_mm_day")) for r in records]

    etc = sum(v for v in etc_values if v is not None)
    rain = sum(v for v in rain_values if v is not None)
    days = len(records)

    # Assumption: all recorded rainfall is treated as effective rainfall.
    # These are scenario estimates, not measured irrigation withdrawals.
    base = etc + LAND_PREPARATION_MM + ESTABLISHMENT_MM - rain
    low_mm = max(0, base + SEEPAGE_LOW_MM_DAY * days)
    high_mm = max(0, base + SEEPAGE_HIGH_MM_DAY * days)

    results.append({
        "year": year,
        "point_id": point,
        "latitude": records[0].get("latitude", ""),
        "longitude": records[0].get("longitude", ""),
        "season_days": days,
        "estimated_etc_season_mm": round(etc, 2),
        "rainfall_season_mm": round(rain, 2),
        "land_preparation_assumption_mm": LAND_PREPARATION_MM,
        "establishment_water_assumption_mm": ESTABLISHMENT_MM,
        "seepage_low_mm_day": SEEPAGE_LOW_MM_DAY,
        "seepage_high_mm_day": SEEPAGE_HIGH_MM_DAY,
        "scenario_low_depth_mm": round(low_mm, 2),
        "scenario_high_depth_mm": round(high_mm, 2),
        "scenario_low_m3_per_feddan": round(low_mm * M3_PER_FEDAN_PER_MM, 2),
        "scenario_high_m3_per_feddan": round(high_mm * M3_PER_FEDAN_PER_MM, 2),
        "actual_irrigation_status": "NOT_MEASURED",
        "assumption_note": "All rainfall treated as effective; Kc, seepage, land preparation and establishment values require local validation.",
        "method_status": "SCENARIO_ESTIMATE_NOT_FIELD_VALIDATED",
    })

with open(OUTPUT, "w", encoding="utf-8-sig", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
    writer.writeheader()
    writer.writerows(results)

annual = []
for year in sorted(set(r["year"] for r in results)):
    subset = [r for r in results if r["year"] == year]
    annual.append({
        "year": year,
        "point_count": len(subset),
        "mean_etc_mm": round(mean(r["estimated_etc_season_mm"] for r in subset), 2),
        "mean_rainfall_mm": round(mean(r["rainfall_season_mm"] for r in subset), 2),
        "mean_low_scenario_m3_per_feddan": round(mean(r["scenario_low_m3_per_feddan"] for r in subset), 2),
        "mean_high_scenario_m3_per_feddan": round(mean(r["scenario_high_m3_per_feddan"] for r in subset), 2),
        "interpretation": "Spatial-point scenario averages; not actual field irrigation measurements",
    })

with open(SUMMARY, "w", encoding="utf-8-sig", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(annual[0].keys()))
    writer.writeheader()
    writer.writerows(annual)

print("DONE")
print("Scenario records:", len(results))
print("Annual summaries:", len(annual))
print("Created:", OUTPUT)
print("Created:", SUMMARY)
print("No original files were modified.")
