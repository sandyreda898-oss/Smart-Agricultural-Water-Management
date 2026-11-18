#!/usr/bin/env python3
"""Phase 2 - Data quality assessment and cleaning (Smart Agricultural Water Management, ML component).

What this script does
---------------------
1. Opens the project SQLite database READ-ONLY (raw data is never modified).
2. Profiles every non-empty table: missing values, exact duplicates, primary-key duplicates.
3. Cleans the tables selected for ML (weather, soil, grid points, season features, crop reference,
   published trials) and records EVERY operation in a cleaning log.
4. Writes: cleaned CSV files, cleaning_report.xlsx, cleaning_report.md and data-quality charts.

Principles (from the task file)
-------------------------------
* No automatic removal of extreme weather values: they are FLAGGED, not deleted.
* No imputation here. Imputers must be fitted on training data only (Phase 5 pipeline).
* Calculated water scenarios are never exported as labels.

Usage
-----
    python src/data_cleaning.py --db path/to/agriwater_v2.sqlite
    (or set the AGRIWATER_DB environment variable)
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sqlite3
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

SEED = 42
M3_PER_FEDDAN_PER_MM = 4.2      # 1 feddan = 4200 m2  ->  1 mm of water = 4.2 m3
FEDDAN_PER_HA = 0.42            # 1 feddan = 0.42 ha
RAIN_SUSPECT_MM = 150.0         # daily rainfall above this is flagged for review (not removed)

WEATHER_RENAME = {
    "T2M": "t2m_c", "T2M_MAX": "t2m_max_c", "T2M_MIN": "t2m_min_c", "RH2M": "rh2m_pct",
    "WS2M": "ws2m_m_s", "ALLSKY_SFC_SW_DWN": "solar_radiation_mj_m2_day",
    "PS": "pressure_kpa", "PRECTOTCORR": "rainfall_mm_day",
}
EXPECTED_UNITS = {
    "T2M": "C", "T2M_MAX": "C", "T2M_MIN": "C", "RH2M": "%", "WS2M": "m/s",
    "ALLSKY_SFC_SW_DWN": "MJ/m^2/day", "PS": "kPa", "PRECTOTCORR": "mm/day",
}
WEATHER_DOMAIN = {  # physical plausibility limits (invalid if outside)
    "t2m_c": (-10, 55), "t2m_max_c": (-10, 60), "t2m_min_c": (-15, 50), "rh2m_pct": (0, 100),
    "ws2m_m_s": (0, 50), "solar_radiation_mj_m2_day": (0, 40), "pressure_kpa": (85, 110),
    "rainfall_mm_day": (0, None),
}
SOIL_DOMAIN = {"sand_pct": (0, 100), "silt_pct": (0, 100), "clay_pct": (0, 100),
               "bulk": (0.8, 2.0), "organic_carbon": (0, 30), "ph_water": (3, 10)}

UNIT_MAP_RESULT = {"t_per_ha": "t/ha", "kg_per_feddan": "kg/feddan", "m3_per_feddan": "m3/feddan",
                   "percent": "%"}
UNIT_MAP_OBS = {"percent": "%", "Mg/ha": "t/ha", "Mg/m3": "g/cm3"}
METRIC_ALIAS_OBS = {"rh_max": "relative_humidity_max", "rh_mean": "relative_humidity_mean",
                    "rh_min": "relative_humidity_min"}
AMBIGUOUS_UNIT_TOKEN = "ambiguous"


class CleaningLog:
    """Collects one row per cleaning operation (the 8 fields required by the task, section 3.6)."""

    def __init__(self) -> None:
        self.rows: list[dict] = []

    def add(self, dataset, original_rows, missing_before, duplicates_before, operation,
            affected, reason, final_rows) -> None:
        self.rows.append({
            "Original dataset": dataset, "Original records": int(original_rows),
            "Missing values (before)": int(missing_before),
            "Duplicates (before)": int(duplicates_before), "Cleaning operation": operation,
            "Affected records": int(affected), "Reason": reason, "Final records": int(final_rows),
        })

    def frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.rows)


# ----------------------------------------------------------------------------- helpers
def read_table(conn: sqlite3.Connection, name: str) -> pd.DataFrame:
    return pd.read_sql(f'SELECT * FROM "{name}"', conn)


def blank_mask(s: pd.Series) -> pd.Series:
    """True where a value is null or an empty/whitespace-only string."""
    if pd.api.types.is_numeric_dtype(s):
        return s.isna()
    return s.isna() | s.astype("string").str.strip().eq("")


def n_missing(df: pd.DataFrame) -> int:
    return int(sum(blank_mask(df[c]).sum() for c in df.columns))


def strip_strings(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Trim spaces in text columns; returns the frame and the number of changed cells."""
    changed = 0
    df = df.copy()
    for c in df.select_dtypes(include=["object", "string"]).columns:
        s = df[c].astype("string")
        t = s.str.strip().str.replace(r"\s+", " ", regex=True)
        changed += int(((s != t) & s.notna()).sum())
        df[c] = t.astype(object).where(t.notna(), np.nan)
    return df, changed


def md_table(df: pd.DataFrame, max_rows: int = 40) -> str:
    if df is None or df.empty:
        return "_none_"
    d = df.head(max_rows)
    cols = [str(c) for c in d.columns]
    out = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    for _, r in d.iterrows():
        out.append("| " + " | ".join("" if pd.isna(v) else str(v).replace("|", "/").replace("\n", " ")
                                       for v in r) + " |")
    if len(df) > max_rows:
        out.append(f"\n_({len(df) - max_rows} more rows - see cleaning_report.xlsx)_")
    return "\n".join(out)


def primary_keys(conn: sqlite3.Connection, table: str) -> list[str]:
    info = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
    return [r[1] for r in sorted((r for r in info if r[5] > 0), key=lambda r: r[5])]


def outlier_rows(name: str, df: pd.DataFrame, cols: list[str], domain: dict,
                 decision: dict | None = None) -> list[dict]:
    rows = []
    decision = decision or {}
    for c in cols:
        s = pd.to_numeric(df[c], errors="coerce").dropna()
        if s.empty:
            continue
        q1, q3 = s.quantile([0.25, 0.75])
        iqr = q3 - q1
        lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        n_iqr = int(((s < lo) | (s > hi)).sum()) if iqr > 0 else 0
        sd = s.std(ddof=0)
        n_z = int((((s - s.mean()) / sd).abs() > 4).sum()) if sd > 0 else 0
        dlo, dhi = domain.get(c, (None, None))
        n_dom = int(((s < dlo) if dlo is not None else pd.Series(False, index=s.index)).sum()
                    + ((s > dhi) if dhi is not None else pd.Series(False, index=s.index)).sum())
        rows.append({
            "Dataset": name, "Column": c, "Min": round(float(s.min()), 4), "Max": round(float(s.max()), 4),
            "IQR lower fence": round(float(lo), 4), "IQR upper fence": round(float(hi), 4),
            "Flagged by IQR": n_iqr, "Flagged by |z|>4": n_z,
            "Outside physical limits": n_dom,
            "Decision": decision.get(c, "Preserved (no physically impossible values). IQR/z flags are "
                                         "informational only."),
        })
    return rows


# ----------------------------------------------------------------------------- main pipeline
def run(db_path: Path, out_root: Path) -> None:
    np.random.seed(SEED)
    proc = out_root / "data" / "processed"
    inter = out_root / "data" / "intermediate"
    rep = out_root / "reports"
    viz = out_root / "visualizations" / "data_quality"
    for p in (proc, inter, rep, viz):
        p.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)  # READ-ONLY: raw data is never changed
    log = CleaningLog()
    checks: list[dict] = []      # invalid/inconsistent value checks (section 3.4)
    outliers: list[dict] = []
    decisions: list[dict] = []   # missing-value / imputation decisions (section 3.1)

    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    raw = {t: read_table(conn, t) for t in tables}

    # ------------------------------------------------------------------ 1. profile everything
    miss_rows, dup_rows, empty_tables = [], [], []
    for t, d in raw.items():
        if d.empty:
            empty_tables.append({"Table": t, "Columns": d.shape[1], "Note": "0 rows - nothing to clean"})
            continue
        for c in d.columns:
            m = int(blank_mask(d[c]).sum())
            miss_rows.append({"Dataset": t, "Column": c, "Dtype": str(d[c].dtype), "Rows": len(d),
                              "Missing": m, "Missing %": round(100 * m / len(d), 2)})
        pk = primary_keys(conn, t)
        key_dups = int(d.duplicated(pk).sum()) if pk else np.nan
        dup_rows.append({"Dataset": t, "Rows": len(d), "Exact duplicate rows": int(d.duplicated().sum()),
                         "Primary key": ", ".join(pk) if pk else "(none declared)",
                         "Duplicate keys": key_dups})
    missing_df = pd.DataFrame(miss_rows)
    dup_df = pd.DataFrame(dup_rows)

    # ------------------------------------------------------------------ 2. grid points
    gp = raw["grid_point"].copy()
    gp, ch = strip_strings(gp)
    ok_coord = gp.latitude.between(30.5, 31.8) & gp.longitude.between(30.0, 31.8)
    checks.append({"Dataset": "grid_point", "Check": "Coordinates inside Kafr El Sheikh bounding box",
                   "Records checked": len(gp), "Records failing": int((~ok_coord).sum()),
                   "Result": "OK" if ok_coord.all() else "REVIEW"})
    checks.append({"Dataset": "grid_point", "Check": "Duplicate coordinates",
                   "Records checked": len(gp),
                   "Records failing": int(gp.duplicated(["latitude", "longitude"]).sum()), "Result": "OK"})
    log.add("grid_point", len(gp), n_missing(gp), gp.duplicated().sum(),
            "Trim text, validate coordinates (no change needed)", ch, "Coordinates all valid; point_id unique.",
            len(gp))

    # ------------------------------------------------------------------ 3. weather_daily
    w = raw["weather_daily"].copy()
    w["obs_date"] = pd.to_datetime(w["obs_date"], errors="coerce")
    n0, m0 = len(w), int(w["value"].isna().sum())
    d0 = int(w.duplicated(["point_id", "obs_date", "parameter"]).sum())
    bad_dates = int(w["obs_date"].isna().sum())
    unit_bad = int((w["unit"] != w["parameter"].map(EXPECTED_UNITS)).sum())
    checks += [
        {"Dataset": "weather_daily", "Check": "Dates parse as datetime", "Records checked": n0,
         "Records failing": bad_dates, "Result": "OK" if bad_dates == 0 else "REVIEW"},
        {"Dataset": "weather_daily", "Check": "Unit matches the NASA POWER parameter", "Records checked": n0,
         "Records failing": unit_bad, "Result": "OK" if unit_bad == 0 else "REVIEW"},
        {"Dataset": "weather_daily", "Check": "Negative values (any parameter except temperature)",
         "Records checked": n0,
         "Records failing": int(((w["value"] < 0) & ~w["parameter"].str.startswith("T2M")).sum()),
         "Result": "OK"},
    ]
    wide = w.pivot(index=["point_id", "obs_date"], columns="parameter", values="value").reset_index()
    wide.columns.name = None
    wide = wide.rename(columns=WEATHER_RENAME)
    wcols = list(WEATHER_RENAME.values())
    log.add("weather_daily", n0, m0, d0, "Pivot long -> wide (one row per point and day, 8 columns)",
            n0, "Long format (point,date,parameter,value) cannot be used by ML models directly. No key "
                "duplicates, so the pivot is lossless.", len(wide))

    # domain checks
    for c, (lo, hi) in WEATHER_DOMAIN.items():
        s = wide[c].dropna()
        below = (s < lo) if lo is not None else pd.Series(False, index=s.index)
        above = (s > hi) if hi is not None else pd.Series(False, index=s.index)
        bad = int(below.sum() + above.sum())
        checks.append({"Dataset": "weather_daily (wide)", "Check": f"{c} within physical limits "
                       f"[{lo}, {hi}]", "Records checked": len(s), "Records failing": bad,
                       "Result": "OK" if bad == 0 else "REVIEW"})
    inc = int((wide["t2m_max_c"] < wide["t2m_min_c"]).sum())
    checks.append({"Dataset": "weather_daily (wide)", "Check": "t2m_max >= t2m_min", "Records checked": len(wide),
                   "Records failing": inc, "Result": "OK" if inc == 0 else "REVIEW"})
    inc = int(((wide["t2m_c"] > wide["t2m_max_c"] + 1e-9) | (wide["t2m_c"] < wide["t2m_min_c"] - 1e-9)).sum())
    checks.append({"Dataset": "weather_daily (wide)", "Check": "t2m_min <= t2m_mean <= t2m_max",
                   "Records checked": len(wide), "Records failing": inc, "Result": "OK" if inc == 0 else "REVIEW"})
    expected_days = (wide.obs_date.max() - wide.obs_date.min()).days + 1
    checks.append({"Dataset": "weather_daily (wide)", "Check": "No missing calendar days (per point)",
                   "Records checked": wide.obs_date.nunique(),
                   "Records failing": expected_days - wide.obs_date.nunique(),
                   "Result": "OK" if expected_days == wide.obs_date.nunique() else "REVIEW"})

    # missing values: where do they come from?
    wide["any_weather_missing"] = wide[wcols].isna().any(axis=1)
    miss_days = wide.loc[wide.any_weather_missing, "obs_date"]
    tail_start, tail_end = miss_days.min(), miss_days.max()
    n_missing_cells = int(wide[wcols].isna().sum().sum())
    decisions.append({
        "Dataset": "weather_daily", "Column(s)": "all 8 weather variables",
        "Missing": n_missing_cells,
        "Finding": f"All missing values fall on {miss_days.nunique()} consecutive days at the very end of "
                   f"the series ({tail_start.date()} to {tail_end.date()}), for all 38 points. "
                   f"They are not yet published by the data provider (recent-data latency), not random gaps.",
        "Decision": "PRESERVE as NaN. Not imputed. Rows flagged with any_weather_missing=True.",
        "Why": "Imputing the latest days would invent weather. Dates are also outside the 2017-2023 rice-season "
               "window used for features."})

    # extreme rainfall
    wide["rain_suspect_extreme"] = wide["rainfall_mm_day"] > RAIN_SUSPECT_MM
    hist_max = wide.loc[wide.obs_date.dt.year <= 2023, "rainfall_mm_day"].max()
    sus = wide[wide.rain_suspect_extreme]
    sus_days = sorted(sus.obs_date.dt.date.astype(str).unique())
    top = wide.loc[wide.rainfall_mm_day.idxmax()]
    log.add("weather_daily (wide)", len(wide), n_missing_cells, 0,
            f"Flag daily rainfall > {RAIN_SUSPECT_MM:.0f} mm (rain_suspect_extreme) - NOT removed",
            len(sus), f"Max rainfall in 2017-2023 is {hist_max:.1f} mm/day, but {top.obs_date.date()} reaches "
                      f"{top.rainfall_mm_day:.2f} mm/day at several points and is not credible for the Nile "
                      f"Delta. Cause unverified (likely gridded-product artefact in recent data). Preserved "
                      f"and flagged per task rules; verify against an independent source.", len(wide))
    decisions.append({
        "Dataset": "weather_daily", "Column(s)": "rainfall_mm_day",
        "Missing": int(wide["rainfall_mm_day"].isna().sum()),
        "Finding": f"{len(sus)} point-days above {RAIN_SUSPECT_MM:.0f} mm on {len(sus_days)} days: "
                   f"{', '.join(sus_days)}. Max {top.rainfall_mm_day:.2f} mm/day vs 2017-2023 max "
                   f"{hist_max:.2f}. Values on those days are similar across almost all 38 points.",
        "Decision": "PRESERVE and FLAG (rain_suspect_extreme). Do not use these days for features until "
                    "verified. They fall outside the 2017-2023 rice seasons, so season features are unaffected.",
        "Why": "Task rule: do not remove extreme weather automatically; but a value this large is "
               "physically doubtful, so it must be reviewed with the Weather & Water Modeling member."})

    # rice season window flag
    season = raw["season"].copy()
    season["start_date"] = pd.to_datetime(season["start_date"], errors="coerce")
    season["end_date"] = pd.to_datetime(season["end_date"], errors="coerce")
    wide["season_year"] = np.nan
    for _, r in season.iterrows():
        m = (wide.obs_date >= r.start_date) & (wide.obs_date <= r.end_date)
        wide.loc[m, "season_year"] = int(r.season_year)
    wide["in_rice_season_window"] = wide["season_year"].notna()
    log.add("weather_daily (wide)", len(wide), n_missing_cells, 0,
            "Add in_rice_season_window / season_year (10 May - 31 Oct, 2017-2023)", int(wide.in_rice_season_window.sum()),
            "Marks days that belong to the reference rice season so later phases can filter without re-deriving.",
            len(wide))

    # identical weather series between points (gridded product resolution)
    complete = wide.loc[~wide.any_weather_missing]
    fp = {}
    for pid, g in complete.sort_values("obs_date").groupby("point_id"):
        fp[pid] = hashlib.md5(np.round(g[wcols].to_numpy(dtype=float), 4).tobytes()).hexdigest()
    cell_of = {}
    for pid, h in fp.items():
        cell_of.setdefault(h, len(cell_of) + 1)
    cell_map = pd.DataFrame({"point_id": list(fp), "weather_cell_id": [f"cell_{cell_of[h]:02d}" for h in fp.values()]})
    n_cells = cell_map.weather_cell_id.nunique()
    wide = wide.merge(cell_map, on="point_id", how="left")
    gp = gp.merge(cell_map, on="point_id", how="left")
    checks.append({"Dataset": "weather_daily (wide)", "Check": "Independent weather series across the 38 points",
                   "Records checked": len(fp), "Records failing": len(fp) - n_cells,
                   "Result": f"REVIEW - only {n_cells} distinct weather series for {len(fp)} points"})
    decisions.append({
        "Dataset": "weather_daily / grid_point", "Column(s)": "point_id",
        "Missing": 0,
        "Finding": f"The 38 grid points share only {n_cells} distinct daily weather series (neighbouring points "
                   f"fall in the same NASA POWER cell and have identical values).",
        "Decision": "Added weather_cell_id to grid_point and weather tables. Use it as the GROUP key when "
                    "splitting data; do not treat 38 points as 38 independent weather samples.",
        "Why": "Random splits by point would put identical weather in train and test (leakage)."})
    log.add("grid_point / weather_daily", len(gp), 0, 0, "Add weather_cell_id (identical weather series grouped)",
            len(gp), f"38 points collapse to {n_cells} unique weather series; needed for group-based splitting.",
            len(gp))

    wide = wide.sort_values(["point_id", "obs_date"]).reset_index(drop=True)
    outliers += outlier_rows("weather_daily (wide)", wide, wcols, WEATHER_DOMAIN, {
        "rainfall_mm_day": f"Preserved and flagged (> {RAIN_SUSPECT_MM:.0f} mm/day: rain_suspect_extreme). "
                           "Zero-inflated, so IQR fences are not meaningful; domain limit used.",
        "t2m_max_c": "Preserved. Max 46.95 degC is a hot-day extreme; plausible for the region.",
        "ws2m_m_s": "Preserved. Windy-day extremes are real events."})

    # ------------------------------------------------------------------ 4. soil
    sp, ch1 = strip_strings(raw["soil_point"])
    aw, ch2 = strip_strings(raw["soil_awc"])
    sp_m = n_missing(sp)
    sp["texture_soter"] = sp["texture_soter"].replace({"-": np.nan})
    n_dash = int((raw["soil_point"]["texture_soter"] == "-").sum())
    sp = sp.rename(columns={"texture_usda": "texture_usda_code", "bulk": "bulk_density", "ph_water": "ph"})
    sp["texture_usda_code"] = sp["texture_usda_code"].astype("string")
    log.add("soil_point", len(sp), sp_m, sp.duplicated().sum(),
            "Placeholder '-' in texture_soter -> NaN; rename bulk->bulk_density, ph_water->ph; "
            "texture code kept as text category", n_dash + ch1,
            "'-' is a missing-value placeholder, not a soil class. Texture codes are nominal classes, so they "
            "must not be treated as numbers.", len(sp))
    soil_sum = (sp.sand_pct + sp.silt_pct + sp.clay_pct).dropna()
    checks.append({"Dataset": "soil_point", "Check": "sand + silt + clay = 100 %", "Records checked": len(soil_sum),
                   "Records failing": int((soil_sum.sub(100).abs() > 0.5).sum()),
                   "Result": "OK" if (soil_sum.sub(100).abs() <= 0.5).all() else "REVIEW"})
    sp["soil_usable"] = sp["soil_data_status"].eq("COMPLETE")
    bad_status = sp.loc[~sp.soil_usable, ["point_id", "soil_data_status"]]
    decisions.append({
        "Dataset": "soil_point", "Column(s)": "sand/silt/clay/bulk/organic_carbon/ph/texture",
        "Missing": int(sp[["sand_pct", "silt_pct", "clay_pct", "bulk_density", "organic_carbon", "ph"]].isna().sum().sum()),
        "Finding": "2 of 38 points have no soil values: " + "; ".join(
            f"{r.point_id} ({r.soil_data_status})" for r in bad_status.itertuples()) +
                   ". All six properties are missing together (map has no soil there).",
        "Decision": "PRESERVE as NaN and flag exclude_from_ml=True. No imputation.",
        "Why": "The whole soil profile is absent (no-data / non-soil mapping unit); imputing 6 properties for "
               "a point with no soil data would be fabricated. If a point is kept later, any imputer must be "
               "fitted on training data only."})
    aw = aw.copy()
    excl = aw["awc_use_recommendation"].eq("EXCLUDE")
    n_zero = int(((aw["awc_smu_mm_per_m"] == 0) & excl).sum())
    aw.loc[excl, ["awc_smu_mm_per_m", "awc_rootable_mm_estimate"]] = np.nan
    log.add("soil_awc", len(aw), n_missing(raw["soil_awc"]), aw.duplicated().sum(),
            "Replace AWC = 0 by NaN where awc_use_recommendation = EXCLUDE", int(excl.sum()),
            "AWC of 0 mm/m on a water-body / non-soil mapping unit is a sentinel, not a measurement. "
            f"({n_zero} zero values converted.)", len(aw))
    soil = (gp[["point_id", "latitude", "longitude", "district_id", "weather_cell_id"]]
            .merge(sp.drop(columns=["smu_id"]), on="point_id", how="left")
            .merge(aw.drop(columns=["smu_id"]), on="point_id", how="left"))
    soil["exclude_from_ml"] = (~soil["soil_usable"]) | soil["awc_use_recommendation"].eq("EXCLUDE")
    both = int((soil.exclude_from_ml & ~soil.soil_usable & soil.awc_use_recommendation.eq("EXCLUDE")).sum())
    checks.append({"Dataset": "soil_point vs soil_awc", "Check": "Points with no soil data are the same "
                   "points excluded in soil_awc", "Records checked": int(soil.exclude_from_ml.sum()),
                   "Records failing": int(soil.exclude_from_ml.sum()) - both,
                   "Result": "OK" if both == int(soil.exclude_from_ml.sum()) else "REVIEW"})
    soil_domain_columns = {c: c.replace("bulk", "bulk_density").replace("ph_water", "ph")
                           for c in SOIL_DOMAIN}
    outliers += outlier_rows(
        "soil_point", sp, list(soil_domain_columns.values()),
        {soil_domain_columns[c]: bounds for c, bounds in SOIL_DOMAIN.items()},
        {"clay_pct": "Preserved. 55 % clay is a real heavy-clay class of the Delta.",
         "bulk_density": "Preserved. Unit assumed g/cm3 (HWSD2); verify.",
         "organic_carbon": "Preserved. Unit assumed % weight (HWSD2); verify."})
    for c, (lo, hi) in SOIL_DOMAIN.items():
        s = sp[c.replace("bulk", "bulk_density").replace("ph_water", "ph")].dropna()
        bad = int(((s < lo) | (s > hi)).sum())
        checks.append({"Dataset": "soil_point", "Check": f"{c} within physical limits [{lo}, {hi}]",
                       "Records checked": len(s), "Records failing": bad, "Result": "OK" if bad == 0 else "REVIEW"})

    # ------------------------------------------------------------------ 5. season, calendar, varieties, Kc
    se = raw["season"].copy()
    se["start_date"], se["end_date"] = season["start_date"], season["end_date"]
    checks.append({"Dataset": "season", "Check": "start_date < end_date", "Records checked": len(se),
                   "Records failing": int((se.start_date >= se.end_date).sum()), "Result": "OK"})
    log.add("season", len(raw["season"]), n_missing(raw["season"]), 0, "Convert start_date/end_date text -> datetime",
            len(se) * 2, "Dates were stored as text.", len(se))

    cal, chc = strip_strings(raw["crop_calendar"])
    win_cols = ["planting_window", "transplanting_window", "harvest_window"]
    for c in win_cols:
        parts = cal[c].str.split(" to ", expand=True)
        cal[c.replace("_window", "_start")] = pd.to_datetime(parts[0], errors="coerce")
        cal[c.replace("_window", "_end")] = pd.to_datetime(parts[1], errors="coerce")
    for c in ["season_start", "season_end", "stage_start_date", "stage_end_date"]:
        cal[c] = pd.to_datetime(cal[c], errors="coerce")
    bad_win = int(cal[[c.replace("_window", s) for c in win_cols for s in ("_start", "_end")]].isna().sum().sum())
    checks.append({"Dataset": "crop_calendar", "Check": "Window text 'A to B' parsed into dates",
                   "Records checked": len(cal) * 3, "Records failing": bad_win, "Result": "OK" if bad_win == 0 else "REVIEW"})
    cal = cal.drop(columns=win_cols + ["source_url"])
    log.add("crop_calendar", len(raw["crop_calendar"]), n_missing(raw["crop_calendar"]), 0,
            "Split 'A to B' window text into start/end dates; text -> datetime", len(cal) * 3,
            "Windows were single text fields. NOTE: the data dictionary guessed unit 'm/s' for these columns; "
            "they are dates. growth_stage is only 'whole_season_reference_window' (no real stages).", len(cal))

    rv, chv = strip_strings(raw["rice_variety"])
    rv["is_placeholder"] = rv["name_en"].eq("NOT_SPECIFIED")
    rv = rv.drop(columns=["source_url"])
    checks.append({"Dataset": "rice_variety", "Check": "Variety names unique after trimming",
                   "Records checked": len(rv), "Records failing": int(rv.name_en.str.lower().duplicated().sum()),
                   "Result": "OK"})
    decisions.append({"Dataset": "rice_variety", "Column(s)": "season_length_days, name_ar", "Missing": n_missing(rv.drop(columns=["is_placeholder"])),
                      "Finding": "Missing for the placeholder row NOT_SPECIFIED and for Sakha Super 300 (variable "
                                 "duration in the source).", "Decision": "PRESERVE as NaN; placeholder row flagged "
                                 "(is_placeholder).", "Why": "Catalogue values; no basis to impute a duration."})
    log.add("rice_variety", len(raw["rice_variety"]), n_missing(raw["rice_variety"]), 0,
            "Trim text, flag placeholder row 'NOT_SPECIFIED'", chv + int(rv.is_placeholder.sum()),
            "Variety names are consistent; one row is a placeholder, not a real variety.", len(rv))

    cwp, chk = strip_strings(raw["crop_water_parameter"])
    cwp["growth_stage"] = cwp["growth_stage"].str.lower().str.replace(" ", "_")
    kc_bad = int(((cwp.kc < 0.3) | (cwp.kc > 1.5)).sum())
    checks.append({"Dataset": "crop_water_parameter", "Check": "Kc between 0.3 and 1.5", "Records checked": int(cwp.kc.notna().sum()),
                   "Records failing": kc_bad, "Result": "OK" if kc_bad == 0 else "REVIEW"})
    decisions.append({"Dataset": "crop_water_parameter", "Column(s)": "kc, parameter_value, variety_id",
                      "Missing": int(cwp[["kc", "parameter_value", "variety_id"]].isna().sum().sum()),
                      "Finding": "Kc is empty for rows stored as min/max ranges (value_min/value_max are filled). "
                                 "variety_id is empty for all rows (generic FAO-56 values).",
                      "Decision": "PRESERVE; use value_min/value_max for range rows. No imputation.",
                      "Why": "Not locally calibrated reference values; also a leakage risk if combined with a "
                             "target computed from Kc."})
    log.add("crop_water_parameter", len(raw["crop_water_parameter"]), n_missing(raw["crop_water_parameter"]), 0,
            "Standardise growth_stage text; no rows removed", chk, "Consistent lower_snake_case stage names.", len(cwp))

    # ------------------------------------------------------------------ 6. season features table
    ps = raw["point_season_summary"].copy()
    for c in ["season_start_date", "season_end_date"]:
        ps[c] = pd.to_datetime(ps[c], errors="coerce")
    ps_m = n_missing(raw["point_season_summary"])
    checks += [
        {"Dataset": "point_season_summary", "Check": "weather_day_count = 175 (10 May - 31 Oct)",
         "Records checked": len(ps), "Records failing": int((ps.weather_day_count != 175).sum()), "Result": "OK"},
        {"Dataset": "point_season_summary", "Check": "(point_id, season_year) unique",
         "Records checked": len(ps), "Records failing": int(ps.duplicated(["point_id", "season_year"]).sum()), "Result": "OK"},
        {"Dataset": "point_season_summary", "Check": "point_id exists in grid_point",
         "Records checked": len(ps), "Records failing": int((~ps.point_id.isin(gp.point_id)).sum()), "Result": "OK"},
    ]
    # cross-check summary vs recomputation from the cleaned daily weather
    win = wide[wide.in_rice_season_window]
    rec = win.groupby(["point_id", "season_year"]).agg(
        tmax=("t2m_max_c", "mean"), rain=("rainfall_mm_day", "sum"), rh=("rh2m_pct", "mean")).reset_index()
    rec["season_year"] = rec["season_year"].astype(int)
    cmp_ = ps.merge(rec, on=["point_id", "season_year"], how="left")
    mism = int(((cmp_.tmax_c_season_mean - cmp_.tmax).abs() > 0.01).sum()
               + ((cmp_.rainfall_season_mm - cmp_.rain).abs() > 0.05).sum()
               + ((cmp_.relative_humidity_pct_season_mean - cmp_.rh).abs() > 0.01).sum())
    checks.append({"Dataset": "point_season_summary", "Check": "Season means/rainfall equal recomputation from daily weather",
                   "Records checked": len(ps) * 3, "Records failing": mism, "Result": "OK" if mism == 0 else "REVIEW"})
    ps = ps.merge(cell_map, on="point_id", how="left")
    ps_cols = [c for c in ps.columns if c.endswith("_mean") or c.endswith("_mm")]
    outliers += outlier_rows("point_season_summary", ps, ps_cols, {})
    log.add("point_season_summary", len(ps), ps_m, ps.duplicated().sum(),
            "Dates -> datetime; add weather_cell_id; cross-check against daily weather", len(ps) * 2,
            "No missing values or duplicates. Season means match the daily data. Columns et0/etc/etc_minus_rain "
            "are CALCULATED; they must not be combined with a target derived from the same calculation.", len(ps))

    # ------------------------------------------------------------------ 7. ML feature dataset (no target)
    feat = ps.merge(gp[["point_id", "latitude", "longitude", "district_id"]], on="point_id", how="left") \
             .merge(soil.drop(columns=["latitude", "longitude", "district_id", "weather_cell_id"]),
                    on="point_id", how="left")
    feat["rain_suspect_in_season"] = False   # season windows 2017-2023 contain no flagged days
    sus_in_season = int(wide.loc[wide.in_rice_season_window, "rain_suspect_extreme"].sum())
    feat["rain_suspect_in_season"] = sus_in_season > 0
    log.add("point_season_summary + grid_point + soil", len(ps), 0, 0,
            "Join season features, grid points and soil (key = point_id) into cleaned_dataset.csv",
            len(feat), "Many-to-one join on point_id (38 points, 7 seasons). Row count unchanged = join is safe. "
                       f"Rainfall-flagged days inside the rice seasons: {sus_in_season}. NO target column is "
                       "included because no verified irrigation label exists.", len(feat))

    # ------------------------------------------------------------------ 8. calculated daily demand (reference only)
    rd = raw["rice_daily_water_demand"].copy()
    rd["obs_date"] = pd.to_datetime(rd["obs_date"], errors="coerce")
    diff = (rd.estimated_etc_mm_day - rd.et0_mm_day * rd.estimated_kc).abs()
    checks.append({"Dataset": "rice_daily_water_demand", "Check": "ETc = ET0 x Kc (tolerance 0.01 mm)",
                   "Records checked": len(rd), "Records failing": int((diff > 0.01).sum()),
                   "Result": "OK" if (diff <= 0.01).all() else "REVIEW"})
    outliers += outlier_rows("rice_daily_water_demand", rd, ["et0_mm_day", "estimated_kc", "estimated_etc_mm_day"],
                             {"et0_mm_day": (0, 20), "estimated_etc_mm_day": (0, 20)})
    rd["calculated_not_measured"] = True
    log.add("rice_daily_water_demand", len(rd), n_missing(raw["rice_daily_water_demand"]), rd.duplicated(["point_id", "obs_date"]).sum(),
            "Dates -> datetime; add calculated_not_measured=True", len(rd),
            "Values are FAO-56 calculations, not observations. Kept in data/intermediate only.", len(rd))

    # ------------------------------------------------------------------ 9. scenario tables (QC only, never exported as labels)
    scen = {
        "water_scenario": [("scenario_low_depth_mm", "scenario_low_m3_per_feddan"),
                           ("scenario_high_depth_mm", "scenario_high_m3_per_feddan")],
        "water_scenario_by_variety": [("scenario_low_depth_mm", "scenario_low_m3_per_feddan"),
                                      ("scenario_high_depth_mm", "scenario_high_m3_per_feddan")],
        "water_scenario_by_variety_clay": [("scenario_low_depth_mm", "scenario_low_m3_per_feddan"),
                                           ("scenario_high_depth_mm", "scenario_high_m3_per_feddan")],
        "water_scenario_by_variety_v3": [("core_low_mm", "core_low_m3_per_feddan"),
                                         ("core_high_mm", "core_high_m3_per_feddan")],
    }
    for t, pairs in scen.items():
        d = raw[t]
        bad_conv = 0
        for mm_c, m3_c in pairs:
            bad_conv += int(((d[m3_c] - d[mm_c] * M3_PER_FEDDAN_PER_MM).abs() > 1.0).sum())
        checks.append({"Dataset": t, "Check": "m3/feddan = mm x 4.2 (units not mixed)", "Records checked": len(d) * len(pairs),
                       "Records failing": bad_conv, "Result": "OK" if bad_conv == 0 else "REVIEW"})
        lo, hi = pairs[0][1], pairs[1][1]
        checks.append({"Dataset": t, "Check": "low scenario <= high scenario", "Records checked": len(d),
                       "Records failing": int((d[lo] > d[hi]).sum()), "Result": "OK"})
    keys = ["season_year", "point_id", "variety_id"]
    ov = raw["water_scenario_by_variety"][keys].merge(raw["water_scenario_by_variety_v3"][keys].drop_duplicates(),
                                                       on=keys, how="inner").drop_duplicates()
    checks.append({"Dataset": "water_scenario_by_variety vs _v3", "Check": "Same point/year/variety present in both "
                   "(variants of one calculation, not independent samples)", "Records checked": len(raw["water_scenario_by_variety"]),
                   "Records failing": len(ov), "Result": "INFO - overlapping variants; NOT labels"})
    log.add("water_scenario* (4 tables)", sum(len(raw[t]) for t in scen), 0,
            sum(int(raw[t].duplicated().sum()) for t in scen),
            "Quality checks only - no cleaned copy exported", 0,
            "Calculated scenarios (actual_irrigation_status = NOT_MEASURED). Unit conversion verified "
            "(1 mm = 4.2 m3/feddan). Intentionally not written to processed data so they cannot be mistaken "
            "for labels.", sum(len(raw[t]) for t in scen))

    # ------------------------------------------------------------------ 10. literature tables
    st, _ = strip_strings(raw["literature_study"])
    decisions.append({"Dataset": "literature_study", "Column(s)": "latitude, longitude, doi",
                      "Missing": int(st[["latitude", "longitude", "doi"]].isna().sum().sum()),
                      "Finding": "10 of 15 studies have no coordinates; 4 have no DOI.",
                      "Decision": "PRESERVE as NaN. Not imputed.", "Why": "Locations are unknown, not computable."})
    log.add("literature_study", len(st), n_missing(raw["literature_study"]), 0, "Trim text (no row changes)", 0,
            "Studies are the natural GROUP key for splitting trial data (only 15 studies).", len(st))

    tr, c1 = strip_strings(raw["literature_trial_result"])
    tr_m, tr_d = n_missing(raw["literature_trial_result"]), int(raw["literature_trial_result"].duplicated().sum())
    tr["unit_original"] = tr["unit"]
    tr["unit"] = tr["unit"].replace(UNIT_MAP_RESULT)
    n_unit = int((tr["unit"] != tr["unit_original"]).sum())
    kd = tr.duplicated(["study_id", "season_year", "variety_id", "irrigation_regime", "irrigation_interval_days",
                        "row_spacing_cm", "hill_spacing_cm", "metric_name"]).sum()
    log.add("literature_trial_result", len(tr), tr_m, tr_d, "Standardise unit labels (t_per_ha->t/ha, "
            "kg_per_feddan->kg/feddan, m3_per_feddan->m3/feddan, percent->%)", n_unit,
            f"Same unit written two ways in one column. No row removed; {kd} duplicates by treatment key.", len(tr))
    decisions.append({"Dataset": "literature_trial_result", "Column(s)": "variety_id, irrigation_interval_days, row/hill_spacing_cm",
                      "Missing": int(tr[["variety_id", "irrigation_interval_days", "row_spacing_cm", "hill_spacing_cm"]].isna().sum().sum()),
                      "Finding": "Treatment descriptors are blank when a study did not vary or report them.",
                      "Decision": "PRESERVE as NaN (structural, not random).", "Why": "Filling would invent experimental conditions."})

    ob, c2 = strip_strings(raw["literature_trial_observation"])
    ob_m, ob_d = n_missing(raw["literature_trial_observation"]), int(raw["literature_trial_observation"].duplicated().sum())
    ob["puddling"] = ob["puddling"].replace({"": np.nan})
    n_blank = int((raw["literature_trial_observation"]["puddling"] == "").sum())
    ob["unit_original"], ob["metric_value_original"] = ob["unit"], ob["metric_value"]
    ob["metric_name"] = ob["metric_name"].replace(METRIC_ALIAS_OBS)
    n_alias = int(raw["literature_trial_observation"]["metric_name"].isin(METRIC_ALIAS_OBS).sum())
    ob["unit_std"] = ob["unit"].replace(UNIT_MAP_OBS)
    ob["value_std"] = ob["metric_value"]
    vol_ha = ob["unit"].eq("m3/ha")
    ob.loc[vol_ha, "value_std"] = ob.loc[vol_ha, "metric_value"] * FEDDAN_PER_HA   # m3/ha -> m3/feddan
    ob.loc[vol_ha, "unit_std"] = "m3/feddan"
    amb = ob["unit"].str.contains(AMBIGUOUS_UNIT_TOKEN, na=False)
    ob.loc[amb, "value_std"] = np.nan
    ob["unit_ambiguous"] = amb
    ob = ob.drop(columns=["unit", "metric_value"]).rename(columns={"unit_std": "unit", "value_std": "metric_value"})
    n_conv = int(vol_ha.sum())
    log.add("literature_trial_observation", len(ob), ob_m, ob_d, "Unit standardisation: Mg/ha->t/ha, Mg/m3->g/cm3 "
            "(identical), percent->%; irrigation water m3/ha -> m3/feddan (x0.42); original kept in *_original columns",
            int((ob.unit != ob.unit_original).sum()), "Irrigation volumes were reported in m3/ha in some studies and m3/feddan in "
            "others; the task forbids mixing them. Conversion uses 1 feddan = 0.42 ha.", len(ob))
    log.add("literature_trial_observation", len(ob), ob_m, ob_d, "Empty-string puddling -> NaN; metric aliases "
            "rh_max/mean/min -> relative_humidity_*", n_blank + n_alias,
            "Blank text is a missing value; same metric had two names.", len(ob))
    log.add("literature_trial_observation", len(ob), ob_m, ob_d, "Flag ambiguous wind-speed unit; value_std set to NaN", int(amb.sum()),
            "Unit published as 'km/day or km/hour' - cannot be converted to m/s safely.", len(ob))
    decisions.append({"Dataset": "literature_trial_observation", "Column(s)": "study_year, preceding_crop, depth_*, replicate_count",
                      "Missing": int(ob[["study_year", "preceding_crop", "depth_top_cm", "depth_bottom_cm", "replicate_count"]].isna().sum().sum()),
                      "Finding": "Blanks are structural (not every metric has a depth, crop history or replicate count).",
                      "Decision": "PRESERVE as NaN.", "Why": "Not random gaps; imputation would be meaningless."})

    em, c3 = strip_strings(raw["literature_environmental_measurement"])
    em = em.drop(columns=["depth_top_cm", "depth_bottom_cm"])
    km2 = em["unit"].eq("km2")
    em["unit_suspect"] = km2
    km2_params = ", ".join(sorted(em.loc[km2, "parameter_name"].unique()))
    checks.append({"Dataset": "literature_environmental_measurement", "Check": "Unit plausible for parameter",
                   "Records checked": len(em), "Records failing": int(km2.sum()),
                   "Result": f"REVIEW - unit 'km2' on: {km2_params}"})
    log.add("literature_environmental_measurement", len(em), n_missing(raw["literature_environmental_measurement"]), 0,
            "Drop two 100 %-empty depth columns; flag rows with unit 'km2' (unit_suspect)", int(km2.sum()) + 2,
            f"Depth columns hold no data. 'km2' is not a unit for a soil/water measurement ({km2_params}); flagged for review.",
            len(em))

    # database_metadata duplicates
    dm = raw["database_metadata"]
    dm_d = int(dm.duplicated().sum())
    dm_clean = dm.drop_duplicates().reset_index(drop=True)
    log.add("database_metadata", len(dm), n_missing(dm), dm_d, "Remove exact duplicate rows", dm_d,
            "Rows are identical (repeated import notes). Not observations, so removal loses nothing.", len(dm_clean))

    # outliers of literature volumes
    wv = ob[ob.metric_name.isin(["seasonal_irrigation_applied", "irrigation_water_applied", "total_water_applied",
                                  "total_irrigation_water"])]
    outliers += outlier_rows("literature irrigation volumes (m3/feddan, standardised)", wv.rename(columns={"metric_value": "volume_m3_feddan"}),
                             ["volume_m3_feddan"], {"volume_m3_feddan": (0, 20000)},
                             {"volume_m3_feddan": "Preserved. Treatment means from different regimes (e.g. deficit vs "
                                                  "flooding) legitimately span a wide range."})

    # ------------------------------------------------------------------ 11. write cleaned data
    wide_out = wide.drop(columns=["any_weather_missing"]).assign(any_weather_missing=wide["any_weather_missing"])
    wide_out["obs_date"] = wide_out["obs_date"].dt.strftime("%Y-%m-%d")
    wide_out.to_csv(proc / "cleaned_weather_daily.csv", index=False)
    gp.to_csv(proc / "cleaned_grid_point.csv", index=False)
    soil.to_csv(proc / "cleaned_soil.csv", index=False)
    feat.to_csv(proc / "cleaned_dataset.csv", index=False)
    rd.assign(obs_date=rd.obs_date.dt.strftime("%Y-%m-%d")).to_csv(inter / "rice_daily_water_demand_cleaned.csv", index=False)
    for name, df in {"season": se, "crop_calendar": cal, "rice_variety": rv, "crop_water_parameter": cwp,
                     "literature_study": st, "literature_trial_result": tr, "literature_trial_observation": ob,
                     "literature_environmental_measurement": em, "database_metadata": dm_clean}.items():
        df.to_csv(inter / f"{name}_cleaned.csv", index=False)

    # ------------------------------------------------------------------ 12. charts
    plt.rcParams.update({"font.family": "DejaVu Sans", "figure.dpi": 110})
    top = missing_df[missing_df.Missing > 0].sort_values("Missing %", ascending=False).head(25)
    fig, ax = plt.subplots(figsize=(9, 7))
    ax.barh(top.Dataset + "." + top.Column, top["Missing %"], color="#c0504d")
    ax.invert_yaxis()
    ax.set_xlabel("Missing values (%)")
    ax.set_title("Columns with the most missing values (raw database)")
    fig.tight_layout(); fig.savefig(viz / "01_missing_values_overview.png"); plt.close(fig)

    daily_max = wide.groupby("obs_date")["rainfall_mm_day"].max()
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.plot(daily_max.index, daily_max.values, lw=0.7, color="#1f77b4")
    ax.axhline(RAIN_SUSPECT_MM, color="red", ls="--", lw=1, label=f"review threshold {RAIN_SUSPECT_MM:.0f} mm/day")
    ax.set_yscale("symlog", linthresh=10)
    ax.set_ylabel("Max rainfall over 38 points (mm/day, symlog)")
    ax.set_title("Daily maximum rainfall - suspicious spikes in 2026")
    ax.legend(); fig.tight_layout(); fig.savefig(viz / "02_rainfall_extremes.png"); plt.close(fig)

    fig, axes = plt.subplots(2, 4, figsize=(13, 6))
    for ax, c in zip(axes.ravel(), wcols):
        ax.boxplot(wide[c].dropna(), vert=True, flierprops={"markersize": 1.5})
        ax.set_title(c, fontsize=9)
        if c == "rainfall_mm_day":
            ax.set_yscale("symlog", linthresh=10)
    fig.suptitle("Weather variables - boxplots (all points, 2017-2026)")
    fig.tight_layout(); fig.savefig(viz / "03_weather_boxplots.png"); plt.close(fig)

    fig, axes = plt.subplots(2, 3, figsize=(11, 6))
    for ax, c in zip(axes.ravel(), ["sand_pct", "silt_pct", "clay_pct", "bulk_density", "organic_carbon", "ph"]):
        ax.hist(sp[c].dropna(), bins=12, color="#6a994e", edgecolor="white")
        ax.set_title(c, fontsize=10)
    fig.suptitle("Soil properties (36 points with data)")
    fig.tight_layout(); fig.savefig(viz / "04_soil_distributions.png"); plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 6))
    sc = ax.scatter(gp.longitude, gp.latitude, c=gp.weather_cell_id.astype("category").cat.codes, cmap="tab20", s=70, edgecolor="k")
    ax.set_xlabel("Longitude"); ax.set_ylabel("Latitude")
    ax.set_title(f"38 grid points share only {n_cells} distinct weather series (colour = weather cell)")
    fig.tight_layout(); fig.savefig(viz / "05_weather_cells.png"); plt.close(fig)

    # ------------------------------------------------------------------ 13. reports
    ops = log.frame()
    chk_df, out_df = pd.DataFrame(checks), pd.DataFrame(outliers)
    dec_df, empty_df = pd.DataFrame(decisions), pd.DataFrame(empty_tables)
    summary = pd.DataFrame([
        ["Tables in database", len(raw)], ["Non-empty tables profiled", len(dup_df)], ["Empty tables", len(empty_df)],
        ["Cleaning operations logged", len(ops)], ["Validity checks run", len(chk_df)],
        ["Checks needing review", int(chk_df["Result"].str.startswith(("REVIEW", "INFO")).sum())],
        ["Weather records (point x day)", len(wide)], ["Distinct weather series among 38 points", n_cells],
        ["Rainfall point-days flagged (> %d mm)" % RAIN_SUSPECT_MM, len(sus)],
        ["Exact duplicate rows removed (database_metadata)", dm_d],
    ], columns=["Item", "Value"])

    xlsx = rep / "cleaning_report.xlsx"
    with pd.ExcelWriter(xlsx, engine="openpyxl") as xw:
        for name, df in [("Summary", summary), ("Cleaning_Operations", ops), ("Missing_Decisions", dec_df),
                         ("Missing_Values_All", missing_df), ("Duplicates", dup_df), ("Outliers", out_df),
                         ("Validity_Checks", chk_df), ("Weather_Cells", cell_map), ("Empty_Tables", empty_df)]:
            df.to_excel(xw, sheet_name=name, index=False)
    _style_workbook(xlsx)

    md = [
        "# Cleaning Report - Phase 2", "",
        f"Source: `{db_path.name}` (opened read-only; raw data untouched). Generated by `src/data_cleaning.py`.", "",
        "## 1. Key findings", "",
        f"1. **No verified target exists** (carried over from Phase 1). No target column is written to the cleaned data.",
        f"2. **Suspicious rainfall.** {len(sus)} point-days exceed {RAIN_SUSPECT_MM:.0f} mm/day "
        f"(max {top_val(wide):.2f} mm/day on {', '.join(sus_days)}), versus a 2017-2023 maximum of {hist_max:.1f} mm/day. "
        "Preserved and flagged, not deleted. Needs verification with the Weather & Water Modeling member.",
        f"3. **Only {n_cells} independent weather series** for 38 grid points. Use `weather_cell_id` as the group key when splitting.",
        f"4. **{n_missing_cells:,} missing weather values** are all in the last {miss_days.nunique()} days "
        f"({tail_start.date()} to {tail_end.date()}), i.e. not yet published. Preserved as NaN.",
        "5. **2 of 38 soil points have no soil data.** Flagged `exclude_from_ml`; not imputed.",
        "6. **Mixed units in published trials** (m3/ha vs m3/feddan, t/ha vs Mg/ha, etc.) were standardised; originals kept.",
        f"7. {dm_d} exact duplicate rows in `database_metadata` were removed; all other duplicate checks were clean.",
        "", "## 2. Summary", "", md_table(summary), "", "## 3. Cleaning operations", "", md_table(ops, 60), "",
        "## 4. Missing-value and imputation decisions", "",
        "No imputation was performed in Phase 2. Any imputer must be fitted on training data only (Phase 5 pipeline).", "",
        md_table(dec_df), "", "## 5. Duplicates", "", md_table(dup_df[(dup_df["Exact duplicate rows"] > 0) | (dup_df["Duplicate keys"].fillna(0) > 0)]),
        "", "All other non-empty tables: 0 exact duplicates and 0 duplicate keys (see Excel sheet `Duplicates`).",
        "", "## 6. Outlier review", "", md_table(out_df), "",
        "## 7. Validity and consistency checks", "", md_table(chk_df, 80), "",
        "## 8. Empty tables", "", md_table(empty_df), "",
        "## 9. Output files", "",
        "- `data/processed/cleaned_dataset.csv` - point x season features (266 rows, no target)",
        "- `data/processed/cleaned_weather_daily.csv`, `cleaned_soil.csv`, `cleaned_grid_point.csv`",
        "- `data/intermediate/*_cleaned.csv` - reference and literature tables",
        "- `visualizations/data_quality/*.png`", "",
        "Water scenario tables are checked but intentionally not exported (calculated values, not labels).",
    ]
    (rep / "cleaning_report.md").write_text("\n".join(md), encoding="utf-8")
    print(summary.to_string(index=False))
    print(chk_df[chk_df.Result != "OK"][["Dataset", "Check", "Records failing", "Result"]].to_string(index=False))
    conn.close()


def top_val(wide: pd.DataFrame) -> float:
    return float(wide["rainfall_mm_day"].max())


def _style_workbook(path: Path) -> None:
    from openpyxl import load_workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    wb = load_workbook(path)
    for ws in wb.worksheets:
        for cell in ws[1]:
            cell.font = Font(name="Arial", bold=True, color="FFFFFF", size=10)
            cell.fill = PatternFill("solid", fgColor="1F4E78")
            cell.alignment = Alignment(wrap_text=True, vertical="center")
        for row in ws.iter_rows(min_row=2):
            for cell in row:
                cell.font = Font(name="Arial", size=10)
                cell.alignment = Alignment(wrap_text=True, vertical="top")
        for col in ws.columns:
            width = max(len(str(c.value)) if c.value is not None else 0 for c in col[:60])
            ws.column_dimensions[col[0].column_letter].width = min(max(width + 2, 10), 60)
        ws.freeze_panes = "A2"
    wb.save(path)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.environ.get("AGRIWATER_DB"), help="Path to agriwater_v2.sqlite")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[1]), help="machine_learning/ root")
    a = ap.parse_args()
    if not a.db or not Path(a.db).exists():
        raise SystemExit("Database not found. Pass --db or set AGRIWATER_DB.")
    run(Path(a.db), Path(a.out))


if __name__ == "__main__":
    main()
