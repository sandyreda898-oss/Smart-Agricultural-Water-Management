import csv, math, os
from datetime import datetime

ROOT = r"C:\Users\D.L\Desktop\AgriWater_FIXED"
WEATHER = os.path.join(ROOT, "data", "processed", "nasa_power_daily_units_fixed.csv")
CALENDAR = os.path.join(ROOT, "data", "processed", "rice_crop_calendar.csv")
OUT = os.path.join(ROOT, "data", "processed", "rice_daily_water_demand_2017_2023.csv")
SUMMARY = os.path.join(ROOT, "reports", "rice_annual_water_summary_2017_2023.csv")

def number(x):
    try:
        v = float(x)
        return v if math.isfinite(v) else None
    except (ValueError, TypeError):
        return None

def sat_vapour(t):
    return 0.6108 * math.exp(17.27 * t / (t + 237.3))

def et0_fao56(tmin, tmax, rh, wind, rs, pressure, latitude, day):
    if any(v is None for v in [tmin,tmax,rh,wind,rs,pressure,latitude]):
        return None
    if pressure <= 0 or rs < 0 or wind < 0:
        return None
    tmean = (tmin + tmax) / 2
    es = (sat_vapour(tmin) + sat_vapour(tmax)) / 2
    ea = es * max(0, min(100, rh)) / 100
    delta = 4098 * sat_vapour(tmean) / ((tmean + 237.3) ** 2)
    gamma = 0.000665 * pressure
    phi = math.radians(latitude)
    dr = 1 + 0.033 * math.cos(2 * math.pi * day / 365)
    decl = 0.409 * math.sin(2 * math.pi * day / 365 - 1.39)
    x = -math.tan(phi) * math.tan(decl)
    ws = math.acos(max(-1, min(1, x)))
    ra = (24 * 60 / math.pi) * 0.0820 * dr * (
        ws * math.sin(phi) * math.sin(decl) +
        math.cos(phi) * math.cos(decl) * math.sin(ws)
    )
    ra = max(0, ra)
    z = 44330 * (1 - (pressure / 101.3) ** 0.1903)
    rso = max(0.1, (0.75 + 2e-5 * z) * ra)
    rns = 0.77 * rs
    ratio = max(0, min(1, rs / rso))
    tk = tmean + 273.16
    rnl = 4.903e-9 * (tk ** 4) * (
        0.34 - 0.14 * math.sqrt(max(0, ea))
    ) * (1.35 * ratio - 0.35)
    rn = rns - rnl
    result = (
        0.408 * delta * rn +
        gamma * (900 / (tmean + 273)) * wind * (es - ea)
    ) / (delta + gamma * (1 + 0.34 * wind))
    return max(0, result)

print("Reading crop calendar...")
seasons = {}
with open(CALENDAR, encoding="utf-8-sig", newline="") as f:
    for r in csv.DictReader(f):
        y = int(r["season_year"])
        seasons[y] = (
            datetime.strptime(r["start_date"], "%Y-%m-%d").date(),
            datetime.strptime(r["end_date"], "%Y-%m-%d").date()
        )

print("Reading daily weather...")
daily = {}
with open(WEATHER, encoding="utf-8-sig", newline="") as f:
    for r in csv.DictReader(f):
        p = r["point_id"]
        d = r["date"]
        if d[:4].isdigit() and int(d[:4]) in seasons:
            daydate = datetime.strptime(d, "%Y-%m-%d").date()
            start, end = seasons[int(d[:4])]
            if not start <= daydate <= end:
                continue
            key = (p, d)
            if key not in daily:
                daily[key] = {
                    "point_id": p, "date": d,
                    "latitude": number(r["latitude"]),
                    "longitude": number(r["longitude"])
                }
            daily[key][r["parameter"]] = number(r["value"])

print("Calculating ET0 and estimated rice ETc...")
rows = []
annual = {}
for (point, date_text), r in daily.items():
    date = datetime.strptime(date_text, "%Y-%m-%d").date()
    year = date.year
    tmin = r.get("T2M_MIN")
    tmax = r.get("T2M_MAX")
    rh = r.get("RH2M")
    wind = r.get("WS2M")
    rs = r.get("ALLSKY_SFC_SW_DWN")
    pressure = r.get("PS")
    rain = r.get("PRECTOTCORR")
    et0 = et0_fao56(
        tmin, tmax, rh, wind, rs, pressure,
        r.get("latitude"), date.timetuple().tm_yday
    )

    start, end = seasons[year]
    season_day = (date - start).days
    season_length = (end - start).days + 1

    # Explicit estimated Kc curve; not locally measured growth-stage data.
    if season_day < 30:
        kc = 1.05
    elif season_day < 60:
        kc = 1.05 + (1.20 - 1.05) * (season_day - 30) / 30
    elif season_day < 120:
        kc = 1.20
    else:
        progress = min(1, (season_day - 120) / max(1, season_length - 120))
        kc = 1.20 + (0.75 - 1.20) * progress

    etc = et0 * kc if et0 is not None else None
    rows.append({
        "year": year, "date": date_text, "point_id": point,
        "latitude": r.get("latitude"), "longitude": r.get("longitude"),
        "tmin_c": tmin, "tmax_c": tmax, "relative_humidity_pct": rh,
        "wind_speed_m_s": wind, "solar_radiation_mj_m2_day": rs,
        "pressure_kpa": pressure, "rainfall_mm_day": rain,
        "et0_mm_day": round(et0, 4) if et0 is not None else "",
        "estimated_kc": round(kc, 4),
        "estimated_etc_mm_day": round(etc, 4) if etc is not None else "",
        "method_note": "FAO56_PM; Kc curve is an explicit seasonal estimate"
    })

fields = list(rows[0].keys()) if rows else []
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    w.writerows(rows)

for r in rows:
    y = r["year"]
    a = annual.setdefault(y, {
        "year": y, "daily_point_records": 0,
        "et0_sum_mm": 0, "etc_sum_mm": 0,
        "rainfall_sum_mm": 0, "valid_et0_records": 0,
        "valid_rainfall_records": 0
    })
    a["daily_point_records"] += 1
    if r["et0_mm_day"] != "":
        a["et0_sum_mm"] += r["et0_mm_day"]
        a["etc_sum_mm"] += r["estimated_etc_mm_day"]
        a["valid_et0_records"] += 1
    if r["rainfall_mm_day"] is not None:
        a["rainfall_sum_mm"] += r["rainfall_mm_day"]
        a["valid_rainfall_records"] += 1

summary_fields = [
    "year", "daily_point_records", "valid_et0_records",
    "et0_sum_mm", "estimated_etc_sum_mm", "rainfall_sum_mm",
    "climatic_deficit_etc_minus_rain_mm", "valid_rainfall_records",
    "interpretation"
]
os.makedirs(os.path.dirname(SUMMARY), exist_ok=True)
with open(SUMMARY, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=summary_fields)
    w.writeheader()
    for y in sorted(annual):
        a = annual[y]
        n = a["valid_et0_records"]
        et0sum = a["et0_sum_mm"]
        etcsum = a["etc_sum_mm"]
        rainsum = a["rainfall_sum_mm"]
        w.writerow({
            "year": y,
            "daily_point_records": a["daily_point_records"],
            "valid_et0_records": n,
            "et0_sum_mm": round(et0sum, 2),
            "estimated_etc_sum_mm": round(etcsum, 2),
            "rainfall_sum_mm": round(rainsum, 2),
            "climatic_deficit_etc_minus_rain_mm": round(etcsum-rainsum, 2),
            "valid_rainfall_records": a["valid_rainfall_records"],
            "interpretation": "Grid-point seasonal sums; climatic deficit is NOT actual irrigation withdrawal"
        })

print("\nDONE")
print("Daily results:", OUT)
print("Annual summary:", SUMMARY)
print("Rows written:", len(rows))
print("Years processed:", ", ".join(map(str, sorted(annual))))
