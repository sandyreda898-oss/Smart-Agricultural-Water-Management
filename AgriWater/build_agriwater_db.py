#!/usr/bin/env python3
"""
build_agriwater_db.py
Builds database/agriwater_v2.sqlite from schema.sql and migrates the data
from the existing database/agriwater_project.sqlite + a few CSV files.
The old database and CSV files are only READ, never modified.

Usage (from the project folder, with the project's venv or any Python with pandas):
    python build_agriwater_db.py
    python build_agriwater_db.py --project "C:\\Users\\D.L\\Desktop\\AgriWater_FIXED" --force
"""
import argparse
import sqlite3
import sys
from pathlib import Path

import pandas as pd


MIGRATE_SQL = """
-- reference
INSERT INTO data_source(name)
    SELECT DISTINCT source FROM old.weather_daily WHERE source IS NOT NULL;

INSERT INTO grid_point(point_id, latitude, longitude, spatial_support)
    SELECT point_id, MIN(latitude), MIN(longitude), MIN(spatial_support)
    FROM old.weather_daily GROUP BY point_id;
INSERT OR IGNORE INTO grid_point(point_id, latitude, longitude)
    SELECT point_id, latitude, longitude FROM old.field_season_features;
INSERT OR IGNORE INTO grid_point(point_id, latitude, longitude)
    SELECT point_id, latitude, longitude FROM old.soil_samples;

INSERT INTO season(season_year, start_date, end_date)
    SELECT season_year, MIN(start_date), MAX(end_date)
    FROM old.crop_calendar GROUP BY season_year;
INSERT OR IGNORE INTO season(season_year)
    SELECT DISTINCT year FROM old.field_season_features;
INSERT OR IGNORE INTO season(season_year)
    SELECT DISTINCT year FROM old.governorate_year_reference;

INSERT OR IGNORE INTO rice_variety(name_en, data_status)
    SELECT DISTINCT variety, 'FROM_OLD_CALENDAR' FROM old.crop_calendar
    WHERE variety IS NOT NULL AND variety NOT LIKE 'Not specified%';

INSERT INTO crop_calendar(season_year, variety_id, growth_stage, season_start, season_end,
                          planting_window, transplanting_window, harvest_window,
                          stage_start_date, stage_end_date, source_url, data_status)
    SELECT c.season_year, COALESCE(v.variety_id, 1), c.growth_stage, c.start_date, c.end_date,
           c.planting_date, c.transplanting_date, c.harvest_date,
           c.stage_start_date, c.stage_end_date, c.source_url, c.data_status
    FROM old.crop_calendar c LEFT JOIN rice_variety v ON v.name_en = c.variety;

INSERT INTO crop_water_parameter(crop, growth_stage, kc, parameter_name, parameter_value,
                                 value_min, value_max, unit, valid_conditions, source_url, data_status)
    SELECT crop, growth_stage,
           CASE WHEN instr(COALESCE(CAST(kc AS TEXT), ''), '-') > 0 THEN NULL ELSE CAST(kc AS REAL) END,
           parameter_name,
           CASE WHEN instr(COALESCE(CAST(parameter_value AS TEXT), ''), '-') > 0 THEN NULL ELSE CAST(parameter_value AS REAL) END,
           CASE WHEN instr(COALESCE(CAST(parameter_value AS TEXT), ''), '-') > 0
                THEN CAST(substr(parameter_value, 1, instr(parameter_value, '-') - 1) AS REAL)
                WHEN instr(COALESCE(CAST(kc AS TEXT), ''), '-') > 0
                THEN CAST(substr(kc, 1, instr(kc, '-') - 1) AS REAL)
                WHEN parameter_value IS NOT NULL THEN CAST(parameter_value AS REAL) ELSE NULL END,
           CASE WHEN instr(COALESCE(CAST(parameter_value AS TEXT), ''), '-') > 0
                THEN CAST(substr(parameter_value, instr(parameter_value, '-') + 1) AS REAL)
                WHEN instr(COALESCE(CAST(kc AS TEXT), ''), '-') > 0
                THEN CAST(substr(kc, instr(kc, '-') + 1) AS REAL)
                WHEN parameter_value IS NOT NULL THEN CAST(parameter_value AS REAL) ELSE NULL END,
           unit, valid_conditions, source_url, data_status
    FROM old.crop_water_parameters;

-- facts
INSERT OR IGNORE INTO weather_daily(point_id, obs_date, parameter, value, unit, source_id)
    SELECT w.point_id, w.date, w.parameter, w.value, w.unit, s.source_id
    FROM old.weather_daily w LEFT JOIN data_source s ON s.name = w.source;

INSERT OR IGNORE INTO rice_daily_water_demand(point_id, obs_date, et0_mm_day, estimated_kc,
                                              estimated_etc_mm_day, method_note)
    SELECT point_id, date, et0_mm_day, estimated_kc, estimated_etc_mm_day, method_note
    FROM old.rice_daily_water_demand;

INSERT INTO soil_point(point_id, smu_id, top_depth_cm, bottom_depth_cm, sand_pct, silt_pct,
                       clay_pct, bulk, organic_carbon, ph_water, texture_usda, texture_soter,
                       match_found, soil_data_status, missing_properties)
    SELECT point_id, HWSD2_SMU_ID, top_depth_cm, bottom_depth_cm, sand_pct, silt_pct,
           clay_pct, bulk, organic_carbon, ph_water, texture_usda, texture_soter,
           match_found, soil_data_status, missing_soil_properties
    FROM old.soil_samples;

INSERT INTO point_season_summary(season_year, point_id, season_start_date, season_end_date,
        weather_day_count, tmin_c_season_mean, tmax_c_season_mean,
        relative_humidity_pct_season_mean, wind_speed_m_s_season_mean,
        solar_radiation_mj_m2_day_season_mean, pressure_kpa_season_mean,
        rainfall_season_mm, et0_season_mm, estimated_etc_season_mm,
        estimated_etc_minus_rain_mm, water_values_status, water_method,
        calendar_status, training_readiness)
    SELECT year, point_id, season_start_date, season_end_date,
        weather_day_count, tmin_c_season_mean, tmax_c_season_mean,
        relative_humidity_pct_season_mean, wind_speed_m_s_season_mean,
        solar_radiation_mj_m2_day_season_mean, pressure_kpa_season_mean,
        rainfall_season_mm, et0_season_mm, estimated_etc_season_mm,
        estimated_etc_minus_rain_mm, water_values_status, water_method,
        calendar_status, training_readiness
    FROM old.field_season_features;

INSERT INTO water_scenario(season_year, point_id, season_days, estimated_etc_season_mm,
        rainfall_season_mm, land_preparation_assumption_mm, establishment_water_assumption_mm,
        seepage_low_mm_day, seepage_high_mm_day, scenario_low_depth_mm, scenario_high_depth_mm,
        scenario_low_m3_per_feddan, scenario_high_m3_per_feddan, actual_irrigation_status,
        assumption_note, method_status)
    SELECT year, point_id, season_days, estimated_etc_season_mm,
        rainfall_season_mm, land_preparation_assumption_mm, establishment_water_assumption_mm,
        seepage_low_mm_day, seepage_high_mm_day, scenario_low_depth_mm, scenario_high_depth_mm,
        scenario_low_m3_per_feddan, scenario_high_m3_per_feddan, actual_irrigation_status,
        assumption_note, method_status
    FROM old.rice_water_scenarios;

INSERT INTO regional_stats(season_year, district_id, crop, season_label, area_feddan,
                           production_ton, yield_ton_per_feddan, data_level)
    SELECT year, 1, crop, season, area_feddan, production_ton,
           governorate_yield_ton_per_feddan, data_level
    FROM old.governorate_year_reference;

INSERT INTO database_metadata(item, details)
    SELECT item, details FROM old.database_metadata;
INSERT INTO database_metadata(item, details)
    VALUES ('schema_version', 'v2 - normalized, built by build_agriwater_db.py');
"""


def table_count(conn, name):
    return conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]


def load_soil_awc(conn, csv_path):
    if not csv_path.exists():
        print(f"  [skip] soil_awc: {csv_path.name} not found")
        return
    d = pd.read_csv(csv_path)
    need = ["point_id", "HWSD2_SMU_ID", "AWC_SMU_source_mm_per_m",
            "AWC_rootable_depth_weighted_mm_estimate", "ROOT_DEPTH_source_class",
            "AWC_component_status", "model_screening_status",
            "awc_use_recommendation", "AWC_review_status"]
    miss = [c for c in need if c not in d.columns]
    if miss:
        print(f"  [skip] soil_awc: missing columns {miss}")
        return
    out = d[need].copy()
    out.columns = ["point_id", "smu_id", "awc_smu_mm_per_m", "awc_rootable_mm_estimate",
                   "root_depth_class", "awc_component_status", "model_screening_status",
                   "awc_use_recommendation", "review_status"]
    out = out.drop_duplicates("point_id")
    known = {r[0] for r in conn.execute("SELECT point_id FROM grid_point")}
    dropped = int((~out.point_id.isin(known)).sum())
    out = out[out.point_id.isin(known)]
    out.to_sql("soil_awc", conn, if_exists="append", index=False)
    print(f"  soil_awc: {len(out)} rows" + (f" ({dropped} dropped: unknown point_id)" if dropped else ""))


def load_variety_reference(conn, csv_path):
    if not csv_path.exists():
        print(f"  [skip] rice_variety_reference: {csv_path.name} not found")
        return
    data = pd.read_csv(csv_path)
    required = ["name_en", "name_ar", "season_length_days", "expected_yield_min_ton_ha",
                "expected_yield_max_ton_ha", "grain_type", "quality_note", "plant_type_note",
                "lodging_note", "disease_note", "soil_suitability", "temperature_min_c",
                "temperature_max_c", "source_url", "data_status"]
    missing = [column for column in required if column not in data.columns]
    if missing:
        print(f"  [skip] rice_variety_reference: missing columns {missing}")
        return

    for row in data[required].itertuples(index=False, name=None):
        (name_en, name_ar, season_days, yield_min, yield_max, grain_type, quality_note,
         plant_type_note, lodging_note, disease_note, soil_suitability, temp_min, temp_max,
         source_url, data_status) = row
        values = [None if pd.isna(value) else value for value in row]
        (name_en, name_ar, season_days, yield_min, yield_max, grain_type, quality_note,
         plant_type_note, lodging_note, disease_note, soil_suitability, temp_min, temp_max,
         source_url, data_status) = values
        conn.execute(
            "INSERT INTO rice_variety(name_en, name_ar, season_length_days, source_url, data_status) "
            "VALUES (?, ?, ?, ?, ?) ON CONFLICT(name_en) DO UPDATE SET "
            "name_ar=excluded.name_ar, season_length_days=excluded.season_length_days, "
            "source_url=excluded.source_url, data_status=excluded.data_status",
            (name_en, name_ar, season_days, source_url, data_status),
        )
        variety_id = conn.execute(
            "SELECT variety_id FROM rice_variety WHERE name_en=?", (name_en,)
        ).fetchone()[0]
        conn.execute(
            "INSERT INTO rice_variety_reference(variety_id, expected_yield_min_ton_ha, "
            "expected_yield_max_ton_ha, grain_type, quality_note, plant_type_note, lodging_note, "
            "disease_note, soil_suitability, temperature_min_c, temperature_max_c, source_url, data_status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(variety_id) DO UPDATE SET "
            "expected_yield_min_ton_ha=excluded.expected_yield_min_ton_ha, "
            "expected_yield_max_ton_ha=excluded.expected_yield_max_ton_ha, grain_type=excluded.grain_type, "
            "quality_note=excluded.quality_note, plant_type_note=excluded.plant_type_note, "
            "lodging_note=excluded.lodging_note, disease_note=excluded.disease_note, "
            "soil_suitability=excluded.soil_suitability, temperature_min_c=excluded.temperature_min_c, "
            "temperature_max_c=excluded.temperature_max_c, source_url=excluded.source_url, "
            "data_status=excluded.data_status",
            (variety_id, yield_min, yield_max, grain_type, quality_note, plant_type_note,
             lodging_note, disease_note, soil_suitability, temp_min, temp_max, source_url, data_status),
        )
    print(f"  rice_variety_reference: {len(data)} catalogue rows")


def load_sentinel(conn, catalog_csv, shortlist_csv):
    if not catalog_csv.exists():
        print(f"  [skip] sentinel2_scene: {catalog_csv.name} not found")
        return
    cols = ["scene_id", "datetime", "cloud_cover_percent", "collection", "bbox_json", "source"]
    total = 0
    for chunk in pd.read_csv(catalog_csv, usecols=cols, chunksize=500):
        for name in chunk["source"].dropna().unique():
            conn.execute("INSERT OR IGNORE INTO data_source(name) VALUES (?)", (name,))
        ids = dict(conn.execute("SELECT name, source_id FROM data_source").fetchall())
        chunk["source_id"] = chunk["source"].map(ids)
        chunk["tile_id"] = chunk["scene_id"].str.split("_").str[5]
        out = chunk.rename(columns={"datetime": "acquired_at"})[
            ["scene_id", "tile_id", "acquired_at", "cloud_cover_percent",
             "collection", "bbox_json", "source_id"]]
        out = out.drop_duplicates("scene_id")
        rows = out.to_records(index=False).tolist()
        conn.executemany(
            "INSERT OR IGNORE INTO sentinel2_scene VALUES (?,?,?,?,?,?,?)", rows)
        total += len(rows)
    print(f"  sentinel2_scene: {table_count(conn, 'sentinel2_scene')} rows (read {total})")

    if shortlist_csv.exists():
        s = pd.read_csv(shortlist_csv)
        need = ["scene_id", "dekad", "boundary_overlap_percent_approx"]
        if all(c in s.columns for c in need):
            s = s[need].drop_duplicates("scene_id")
            known = {r[0] for r in conn.execute("SELECT scene_id FROM sentinel2_scene")}
            dropped = int((~s.scene_id.isin(known)).sum())
            s = s[s.scene_id.isin(known)]
            s.to_sql("sentinel2_shortlist", conn, if_exists="append", index=False)
            print(f"  sentinel2_shortlist: {len(s)} rows"
                  + (f" ({dropped} dropped: scene not in catalog)" if dropped else ""))
    else:
        print(f"  [skip] sentinel2_shortlist: {shortlist_csv.name} not found")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=r"C:\Users\D.L\Desktop\AgriWater_FIXED")
    ap.add_argument("--force", action="store_true", help="overwrite agriwater_v2.sqlite if it exists")
    args = ap.parse_args()

    project = Path(args.project)
    old_db = project / "database" / "agriwater_project.sqlite"
    new_db = project / "database" / "agriwater_v2.sqlite"
    schema = next((p for p in (Path(__file__).with_name("schema.sql"), project / "schema.sql")
                   if p.exists()), None)

    if not old_db.exists():
        sys.exit(f"Old database not found: {old_db}")
    if schema is None:
        sys.exit("schema.sql not found next to this script or in the project folder")
    if new_db.exists():
        if not args.force:
            sys.exit(f"{new_db.name} already exists. Re-run with --force to rebuild it.")
        new_db.unlink()

    print(f"Schema : {schema}")
    print(f"Old DB : {old_db}  (read only)")
    print(f"New DB : {new_db}\n")

    conn = sqlite3.connect(new_db)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(schema.read_text(encoding="utf-8"))
    conn.execute("PRAGMA foreign_keys = ON")

    # sanity: old DB must contain the tables we migrate from
    conn.execute("ATTACH DATABASE ? AS old", (str(old_db),))
    have = {r[0] for r in conn.execute("SELECT name FROM old.sqlite_master WHERE type='table'")}
    need = {"weather_daily", "rice_daily_water_demand", "soil_samples", "field_season_features",
            "rice_water_scenarios", "governorate_year_reference", "crop_calendar",
            "crop_water_parameters", "database_metadata"}
    if need - have:
        sys.exit(f"Old database is missing tables: {sorted(need - have)}")

    print("Migrating tables from the old database ...")
    conn.executescript(MIGRATE_SQL)
    conn.commit()

    print("Loading CSV-based tables ...")
    processed = project / "data" / "processed"
    load_variety_reference(conn, processed / "rice_variety_reference_arc.csv")
    load_soil_awc(conn, processed / "hwsd2_awc_rootable_depth_point_candidates.csv")
    load_sentinel(conn, processed / "sentinel2_scene_catalog.csv",
                  project / "reports" / "sentinel2_rice_shortlist.csv")
    conn.commit()

    # ---------------- checks ----------------
    print("\n=== Row counts: old vs new ===")
    pairs = [("weather_daily", "weather_daily"),
             ("rice_daily_water_demand", "rice_daily_water_demand"),
             ("soil_samples", "soil_point"),
             ("field_season_features", "point_season_summary"),
             ("rice_water_scenarios", "water_scenario"),
             ("governorate_year_reference", "regional_stats"),
             ("crop_calendar", "crop_calendar"),
             ("crop_water_parameters", "crop_water_parameter")]
    ok = True
    for o, n in pairs:
        a = conn.execute(f"SELECT COUNT(*) FROM old.{o}").fetchone()[0]
        b = table_count(conn, n)
        flag = "OK " if a == b else "DIFF"
        ok &= a == b
        print(f"  {flag} {o:30s} {a:>9,d} -> {n:24s} {b:>9,d}")

    print("\n=== Other new tables ===")
    for t in ["grid_point", "season", "data_source", "district", "rice_variety",
              "rice_variety_reference", "soil_awc",
              "sentinel2_scene", "sentinel2_shortlist"]:
        print(f"  {t:24s} {table_count(conn, t):>9,d}")

    print("\n=== Empty tables = data you still need to collect ===")
    for t in ["field", "field_season", "irrigation_event", "crop_history", "field_operation",
              "pump_type", "vegetation_index", "soil_salinity", "groundwater_level",
              "canal_schedule", "ministry_rule"]:
        print(f"  {t:24s} {table_count(conn, t):>9,d}")

    labels = conn.execute(
        "SELECT COUNT(*) FROM old.field_season_features "
        "WHERE actual_irrigation_m3_per_feddan IS NOT NULL OR actual_yield_ton_per_feddan IS NOT NULL"
    ).fetchone()[0]
    if labels:
        print(f"\nWARNING: {labels} rows in the old features table have actual labels; "
              "they were NOT migrated. Tell me and I will map them.")

    fk = conn.execute("PRAGMA foreign_key_check").fetchall()
    ic = conn.execute("PRAGMA integrity_check").fetchone()[0]
    print(f"\nforeign_key_check problems: {len(fk)}")
    print(f"integrity_check: {ic}")
    n_train = table_count(conn, "v_point_season_features")
    print(f"v_point_season_features rows: {n_train:,d}")

    conn.execute("DETACH DATABASE old")
    conn.execute("VACUUM")
    conn.close()
    print(f"\nDone. New database: {new_db}  ({new_db.stat().st_size / 1e6:.1f} MB)")
    if not ok:
        print("Some row counts differ (see DIFF lines). Send me this output.")


if __name__ == "__main__":
    main()
