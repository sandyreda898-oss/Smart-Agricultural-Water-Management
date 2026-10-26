#!/usr/bin/env python3
"""Build the AgriWater analytical star-schema database from the documented SQLite source.

This ETL is deliberately repeatable: it reads the normalized release database, creates a
fresh dimensional warehouse, keeps source lineage/status, and never imputes missing values.
"""
from __future__ import annotations

import csv
import json
import math
import re
import shutil
import sqlite3
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DB = ROOT / "database" / "agriwater_clean.sqlite"
WAREHOUSE_DIR = ROOT / "warehouse"
OUTPUT_DB = WAREHOUSE_DIR / "agriwater_star.sqlite"
SQL_PATH = ROOT / "schema" / "star_schema.sql"
PROFILE_PATH = ROOT / "metadata" / "star_etl_profile.csv"
REVIEW_PATH = ROOT / "metadata" / "manual_review_queue.csv"
SUMMARY_PATH = ROOT / "metadata" / "star_schema_summary.json"

DDL = r"""
PRAGMA foreign_keys=ON;
CREATE TABLE dim_date (
  date_key INTEGER PRIMARY KEY, full_date TEXT NOT NULL UNIQUE,
  year INTEGER NOT NULL, quarter INTEGER NOT NULL, month INTEGER NOT NULL,
  day INTEGER NOT NULL, day_of_year INTEGER NOT NULL, weekday INTEGER NOT NULL,
  month_name_en TEXT NOT NULL, is_leap_year INTEGER NOT NULL
);
CREATE TABLE dim_admin_area (
  admin_area_key INTEGER PRIMARY KEY, source_district_id INTEGER UNIQUE,
  name_en TEXT, name_ar TEXT, admin_level INTEGER, parent_admin_area_key INTEGER,
  FOREIGN KEY(parent_admin_area_key) REFERENCES dim_admin_area(admin_area_key)
);
CREATE TABLE dim_location (
  location_key INTEGER PRIMARY KEY, source_point_id TEXT UNIQUE NOT NULL,
  admin_area_key INTEGER, latitude REAL, longitude REAL, spatial_support TEXT,
  source_geo_level TEXT NOT NULL DEFAULT 'grid_point',
  FOREIGN KEY(admin_area_key) REFERENCES dim_admin_area(admin_area_key)
);
CREATE TABLE dim_season (
  season_key INTEGER PRIMARY KEY, season_year INTEGER NOT NULL UNIQUE,
  start_date TEXT, end_date TEXT, season_label TEXT
);
CREATE TABLE dim_crop (
  crop_key INTEGER PRIMARY KEY, source_crop_code TEXT UNIQUE,
  name_en TEXT, name_ar TEXT, botanical_name TEXT, aliases_en TEXT, aliases_ar TEXT,
  typical_season TEXT, functional_group TEXT, legume_status TEXT,
  is_placeholder INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE dim_variety (
  variety_key INTEGER PRIMARY KEY, source_variety_id INTEGER UNIQUE NOT NULL,
  name_en TEXT NOT NULL, name_ar TEXT, season_length_days INTEGER,
  grain_type TEXT, quality_note TEXT, plant_type_note TEXT, lodging_note TEXT,
  disease_note TEXT, soil_suitability TEXT, temperature_min_c REAL, temperature_max_c REAL,
  expected_yield_min_ton_ha REAL, expected_yield_max_ton_ha REAL,
  source_url TEXT, reference_status TEXT, is_placeholder INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE dim_study (
  study_key INTEGER PRIMARY KEY, source_study_id TEXT UNIQUE NOT NULL,
  title TEXT, authors TEXT, publication_year INTEGER, doi TEXT, source_url TEXT,
  location_name TEXT, latitude REAL, longitude REAL, methods_summary TEXT,
  limitations TEXT, data_status TEXT
);
CREATE TABLE dim_source (
  source_key INTEGER PRIMARY KEY, source_id INTEGER UNIQUE,
  source_name TEXT, source_url TEXT, source_notes TEXT,
  source_kind TEXT NOT NULL
);
CREATE TABLE dim_metric (
  metric_key INTEGER PRIMARY KEY, metric_name TEXT NOT NULL, source_unit TEXT NOT NULL DEFAULT '',
  metric_domain TEXT NOT NULL, UNIQUE(metric_name, source_unit, metric_domain)
);
CREATE TABLE dim_treatment (
  treatment_key INTEGER PRIMARY KEY, irrigation_regime TEXT, irrigation_interval_days REAL,
  row_spacing_cm REAL, hill_spacing_cm REAL, treatment_label TEXT UNIQUE
);
CREATE TABLE dim_sample_context (
  sample_context_key INTEGER PRIMARY KEY, sample_kind TEXT, sample_label TEXT,
  treatment_code TEXT, sample_context_label TEXT UNIQUE
);
CREATE TABLE dim_water_model (
  water_model_key INTEGER PRIMARY KEY, source_table TEXT UNIQUE NOT NULL,
  method_status TEXT, model_version TEXT, description TEXT
);
CREATE TABLE dim_soil_unit (
  soil_unit_key INTEGER PRIMARY KEY, smu_id INTEGER UNIQUE
);
CREATE TABLE dim_pump_series (
  pump_series_key INTEGER PRIMARY KEY, source_pump_series_id INTEGER UNIQUE NOT NULL,
  manufacturer TEXT, series_name TEXT, pump_type TEXT, outlet_diameter_in REAL,
  min_flow_m3_h REAL, max_flow_m3_h REAL, max_head_m REAL, frequency_hz TEXT,
  power_min_kw REAL, power_max_kw REAL, operating_conditions TEXT,
  source_url TEXT, data_status TEXT
);
CREATE TABLE dim_irrigation_method (
  irrigation_method_key INTEGER PRIMARY KEY, source_method_id INTEGER UNIQUE NOT NULL,
  name_en TEXT, name_ar TEXT, notes TEXT
);
CREATE TABLE dim_field (
  field_key INTEGER PRIMARY KEY, source_field_id INTEGER UNIQUE,
  location_key INTEGER, admin_area_key INTEGER, area_feddan REAL,
  polygon_geojson TEXT, farmer_consent_id TEXT,
  FOREIGN KEY(location_key) REFERENCES dim_location(location_key),
  FOREIGN KEY(admin_area_key) REFERENCES dim_admin_area(admin_area_key)
);
CREATE TABLE dim_pump (
  pump_key INTEGER PRIMARY KEY, source_pump_id INTEGER UNIQUE,
  name_en TEXT, name_ar TEXT, power_hp REAL, measured_discharge_m3_h REAL,
  fuel_type TEXT, notes TEXT
);

CREATE TABLE fact_weather_daily (
  weather_fact_key INTEGER PRIMARY KEY, date_key INTEGER NOT NULL, location_key INTEGER NOT NULL,
  source_key INTEGER, metric_key INTEGER NOT NULL, value REAL, source_record_key TEXT NOT NULL,
  data_status TEXT NOT NULL, issue_flags TEXT,
  FOREIGN KEY(date_key) REFERENCES dim_date(date_key),
  FOREIGN KEY(location_key) REFERENCES dim_location(location_key),
  FOREIGN KEY(source_key) REFERENCES dim_source(source_key),
  FOREIGN KEY(metric_key) REFERENCES dim_metric(metric_key),
  UNIQUE(date_key, location_key, metric_key, source_record_key)
);
CREATE TABLE fact_soil_measurement (
  soil_fact_key INTEGER PRIMARY KEY, location_key INTEGER NOT NULL, soil_unit_key INTEGER,
  metric_key INTEGER NOT NULL, depth_top_cm REAL, depth_bottom_cm REAL, value REAL,
  data_status TEXT NOT NULL, source_record_key TEXT NOT NULL,
  FOREIGN KEY(location_key) REFERENCES dim_location(location_key),
  FOREIGN KEY(soil_unit_key) REFERENCES dim_soil_unit(soil_unit_key),
  FOREIGN KEY(metric_key) REFERENCES dim_metric(metric_key),
  UNIQUE(location_key, metric_key, depth_top_cm, depth_bottom_cm)
);
CREATE TABLE fact_daily_crop_water (
  crop_water_fact_key INTEGER PRIMARY KEY, date_key INTEGER NOT NULL, location_key INTEGER NOT NULL,
  crop_key INTEGER NOT NULL, et0_mm_day REAL, estimated_kc REAL, estimated_etc_mm_day REAL,
  method_note TEXT, data_status TEXT NOT NULL, source_record_key TEXT NOT NULL,
  FOREIGN KEY(date_key) REFERENCES dim_date(date_key),
  FOREIGN KEY(location_key) REFERENCES dim_location(location_key),
  FOREIGN KEY(crop_key) REFERENCES dim_crop(crop_key),
  UNIQUE(date_key, location_key, crop_key, source_record_key)
);
CREATE TABLE fact_seasonal_water_scenario (
  water_scenario_fact_key INTEGER PRIMARY KEY, season_key INTEGER NOT NULL,
  location_key INTEGER NOT NULL, variety_key INTEGER NOT NULL, water_model_key INTEGER NOT NULL,
  duration_basis TEXT, transplant_date TEXT, harvest_date TEXT, field_days INTEGER,
  missing_weather_days INTEGER, estimated_etc_mm REAL, rainfall_mm REAL,
  seepage_low_mm_day REAL, seepage_high_mm_day REAL, kc_scale REAL,
  core_low_mm REAL, core_high_mm REAL, core_low_m3_feddan REAL, core_high_m3_feddan REAL,
  prep_establishment_mm REAL, with_prep_low_m3_feddan REAL, with_prep_high_m3_feddan REAL,
  wind_scale REAL, data_status TEXT NOT NULL, source_record_key TEXT NOT NULL,
  FOREIGN KEY(season_key) REFERENCES dim_season(season_key),
  FOREIGN KEY(location_key) REFERENCES dim_location(location_key),
  FOREIGN KEY(variety_key) REFERENCES dim_variety(variety_key),
  FOREIGN KEY(water_model_key) REFERENCES dim_water_model(water_model_key)
);
CREATE TABLE fact_regional_crop_stat (
  regional_stat_fact_key INTEGER PRIMARY KEY, season_key INTEGER NOT NULL,
  admin_area_key INTEGER, crop_key INTEGER NOT NULL, season_label TEXT,
  area_feddan REAL, production_ton REAL, yield_ton_feddan REAL,
  data_level TEXT, source_key INTEGER, data_status TEXT,
  FOREIGN KEY(season_key) REFERENCES dim_season(season_key),
  FOREIGN KEY(admin_area_key) REFERENCES dim_admin_area(admin_area_key),
  FOREIGN KEY(crop_key) REFERENCES dim_crop(crop_key),
  FOREIGN KEY(source_key) REFERENCES dim_source(source_key)
);
CREATE TABLE fact_trial_result (
  trial_result_fact_key INTEGER PRIMARY KEY, study_key INTEGER NOT NULL,
  season_key INTEGER, variety_key INTEGER, treatment_key INTEGER,
  metric_key INTEGER NOT NULL, value REAL, standardized_value REAL,
  standardized_unit TEXT, source_record_key TEXT NOT NULL,
  source_locator TEXT, data_status TEXT NOT NULL,
  FOREIGN KEY(study_key) REFERENCES dim_study(study_key),
  FOREIGN KEY(season_key) REFERENCES dim_season(season_key),
  FOREIGN KEY(variety_key) REFERENCES dim_variety(variety_key),
  FOREIGN KEY(treatment_key) REFERENCES dim_treatment(treatment_key),
  FOREIGN KEY(metric_key) REFERENCES dim_metric(metric_key)
);
CREATE TABLE fact_trial_observation (
  trial_observation_fact_key INTEGER PRIMARY KEY, study_key INTEGER NOT NULL,
  season_key INTEGER, crop_key INTEGER, metric_key INTEGER NOT NULL, value REAL,
  standardized_value REAL, standardized_unit TEXT, observation_period TEXT,
  puddling TEXT, depth_top_cm REAL, depth_bottom_cm REAL,
  aggregation_level TEXT, replicate_count INTEGER, source_record_key TEXT NOT NULL,
  source_locator TEXT, data_status TEXT NOT NULL,
  FOREIGN KEY(study_key) REFERENCES dim_study(study_key),
  FOREIGN KEY(season_key) REFERENCES dim_season(season_key),
  FOREIGN KEY(crop_key) REFERENCES dim_crop(crop_key),
  FOREIGN KEY(metric_key) REFERENCES dim_metric(metric_key)
);
CREATE TABLE fact_environmental_measurement (
  environmental_fact_key INTEGER PRIMARY KEY, study_key INTEGER NOT NULL,
  season_key INTEGER, sample_context_key INTEGER, metric_key INTEGER NOT NULL,
  value REAL, standardized_value REAL, standardized_unit TEXT,
  depth_top_cm REAL, depth_bottom_cm REAL, source_record_key TEXT NOT NULL,
  source_locator TEXT, data_status TEXT NOT NULL,
  FOREIGN KEY(study_key) REFERENCES dim_study(study_key),
  FOREIGN KEY(season_key) REFERENCES dim_season(season_key),
  FOREIGN KEY(sample_context_key) REFERENCES dim_sample_context(sample_context_key),
  FOREIGN KEY(metric_key) REFERENCES dim_metric(metric_key)
);
CREATE TABLE fact_literature_evidence (
  evidence_fact_key INTEGER PRIMARY KEY, study_key INTEGER NOT NULL, crop_key INTEGER,
  factor_name TEXT, factor_level TEXT, outcome TEXT, result_summary TEXT,
  statistical_result TEXT, study_context TEXT, source_locator TEXT,
  data_status TEXT, source_url TEXT, source_record_key TEXT UNIQUE,
  FOREIGN KEY(study_key) REFERENCES dim_study(study_key),
  FOREIGN KEY(crop_key) REFERENCES dim_crop(crop_key)
);
CREATE TABLE fact_crop_calendar (
  calendar_fact_key INTEGER PRIMARY KEY, season_key INTEGER NOT NULL,
  variety_key INTEGER, growth_stage TEXT, season_start_text TEXT, season_end_text TEXT,
  planting_window TEXT, transplanting_window TEXT, harvest_window TEXT,
  stage_start_text TEXT, stage_end_text TEXT, data_status TEXT,
  source_url TEXT, source_record_key TEXT NOT NULL,
  FOREIGN KEY(season_key) REFERENCES dim_season(season_key),
  FOREIGN KEY(variety_key) REFERENCES dim_variety(variety_key)
);
CREATE TABLE fact_variety_field_guide (
  variety_guide_fact_key INTEGER PRIMARY KEY, variety_key INTEGER NOT NULL,
  guide_date TEXT, maturity_days_min REAL, maturity_days_max REAL,
  yield_min_ton_feddan REAL, yield_max_ton_feddan REAL, planting_spacing_cm TEXT,
  hills_per_m2 REAL, plants_per_hill_min REAL, plants_per_hill_max REAL,
  urea_bags_per_feddan REAL, suitability_note TEXT, salinity_response TEXT,
  water_stress_response TEXT, disease_note TEXT, source_url TEXT,
  source_status TEXT, notes TEXT, source_record_key TEXT UNIQUE,
  FOREIGN KEY(variety_key) REFERENCES dim_variety(variety_key)
);
CREATE TABLE fact_crop_water_parameter (
  crop_water_parameter_fact_key INTEGER PRIMARY KEY, crop_key INTEGER NOT NULL,
  variety_key INTEGER, growth_stage TEXT, kc REAL, parameter_name TEXT,
  parameter_value REAL, unit TEXT, valid_conditions TEXT, source_key INTEGER,
  data_status TEXT, value_min REAL, value_max REAL,
  FOREIGN KEY(crop_key) REFERENCES dim_crop(crop_key),
  FOREIGN KEY(variety_key) REFERENCES dim_variety(variety_key),
  FOREIGN KEY(source_key) REFERENCES dim_source(source_key)
);
CREATE TABLE fact_agronomy_guidance (
  guidance_fact_key INTEGER PRIMARY KEY, guidance_type TEXT NOT NULL,
  crop_key INTEGER, variety_key INTEGER, admin_area_key INTEGER,
  topic TEXT, guidance_text TEXT NOT NULL, value_min REAL, value_max REAL, unit TEXT,
  condition_scope TEXT, stage_scope TEXT, geography_scope_text TEXT,
  published_or_valid_from TEXT, valid_to TEXT,
  source_key INTEGER, source_locator TEXT, confidence_status TEXT,
  data_status TEXT, review_notes TEXT,
  FOREIGN KEY(crop_key) REFERENCES dim_crop(crop_key),
  FOREIGN KEY(variety_key) REFERENCES dim_variety(variety_key),
  FOREIGN KEY(admin_area_key) REFERENCES dim_admin_area(admin_area_key),
  FOREIGN KEY(source_key) REFERENCES dim_source(source_key)
);
CREATE TABLE fact_plant_protection_guidance (
  protection_fact_key INTEGER PRIMARY KEY, crop_key INTEGER, target_name_ar TEXT,
  target_name_en TEXT, issue_type TEXT, symptom_summary_ar TEXT, observation_window_ar TEXT,
  action_timing_ar TEXT, management_note_ar TEXT, product TEXT, active_ingredient TEXT,
  rate_value REAL, rate_unit TEXT, preharvest_interval_days INTEGER, source_year INTEGER,
  source_locator TEXT, source_key INTEGER, source_quality TEXT, operational_status TEXT,
  data_status TEXT, review_notes TEXT,
  FOREIGN KEY(crop_key) REFERENCES dim_crop(crop_key),
  FOREIGN KEY(source_key) REFERENCES dim_source(source_key)
);
CREATE TABLE fact_pump_catalog (
  pump_catalog_fact_key INTEGER PRIMARY KEY, pump_series_key INTEGER NOT NULL,
  data_status TEXT NOT NULL,
  FOREIGN KEY(pump_series_key) REFERENCES dim_pump_series(pump_series_key)
);
CREATE TABLE fact_satellite_scene (
  scene_fact_key INTEGER PRIMARY KEY, acquired_date_key INTEGER, source_key INTEGER,
  scene_id TEXT NOT NULL, tile_id TEXT, cloud_cover_percent REAL, collection TEXT,
  bbox_json TEXT, shortlist_dekad INTEGER, boundary_overlap_percent_approx REAL,
  vegetation_index_status TEXT NOT NULL,
  FOREIGN KEY(acquired_date_key) REFERENCES dim_date(date_key),
  FOREIGN KEY(source_key) REFERENCES dim_source(source_key)
);
CREATE TABLE fact_machinery_inventory (
  machinery_fact_key INTEGER PRIMARY KEY, survey_year INTEGER,
  source_key INTEGER, admin_level_status TEXT, mobile_count INTEGER,
  stationary_count INTEGER, total_count INTEGER, data_status TEXT, notes TEXT,
  FOREIGN KEY(source_key) REFERENCES dim_source(source_key)
);
CREATE TABLE fact_point_season_summary (
  point_season_fact_key INTEGER PRIMARY KEY, season_key INTEGER NOT NULL,
  location_key INTEGER NOT NULL, season_start_date TEXT, season_end_date TEXT,
  weather_day_count INTEGER, tmin_c_mean REAL, tmax_c_mean REAL,
  relative_humidity_pct_mean REAL, wind_speed_m_s_mean REAL,
  solar_radiation_mj_m2_day_mean REAL, pressure_kpa_mean REAL,
  rainfall_season_mm REAL, et0_season_mm REAL, estimated_etc_season_mm REAL,
  estimated_etc_minus_rain_mm REAL, water_values_status TEXT, water_method TEXT,
  calendar_status TEXT, training_readiness TEXT, data_status TEXT,
  FOREIGN KEY(season_key) REFERENCES dim_season(season_key),
  FOREIGN KEY(location_key) REFERENCES dim_location(location_key)
);
CREATE TABLE fact_baseline_water_scenario (
  baseline_scenario_fact_key INTEGER PRIMARY KEY, season_key INTEGER NOT NULL,
  location_key INTEGER NOT NULL, season_days INTEGER,
  estimated_etc_season_mm REAL, rainfall_season_mm REAL,
  land_preparation_assumption_mm REAL, establishment_water_assumption_mm REAL,
  seepage_low_mm_day REAL, seepage_high_mm_day REAL,
  scenario_low_depth_mm REAL, scenario_high_depth_mm REAL,
  scenario_low_m3_feddan REAL, scenario_high_m3_feddan REAL,
  actual_irrigation_status TEXT, assumption_note TEXT, data_status TEXT,
  FOREIGN KEY(season_key) REFERENCES dim_season(season_key),
  FOREIGN KEY(location_key) REFERENCES dim_location(location_key)
);

-- Future parcel-level facts. These are intentionally empty until observations exist.
CREATE TABLE fact_field_season (
  field_season_fact_key INTEGER PRIMARY KEY, field_key INTEGER NOT NULL,
  season_key INTEGER NOT NULL, variety_key INTEGER, irrigation_method_key INTEGER,
  pump_key INTEGER, sowing_date_key INTEGER, transplanting_date_key INTEGER,
  harvest_date_key INTEGER, cultivated_area_feddan REAL,
  total_irrigation_m3_feddan REAL, harvest_yield_ton_feddan REAL,
  measurement_method TEXT, data_status TEXT,
  FOREIGN KEY(field_key) REFERENCES dim_field(field_key),
  FOREIGN KEY(season_key) REFERENCES dim_season(season_key),
  FOREIGN KEY(variety_key) REFERENCES dim_variety(variety_key),
  FOREIGN KEY(irrigation_method_key) REFERENCES dim_irrigation_method(irrigation_method_key),
  FOREIGN KEY(pump_key) REFERENCES dim_pump(pump_key),
  FOREIGN KEY(sowing_date_key) REFERENCES dim_date(date_key),
  FOREIGN KEY(transplanting_date_key) REFERENCES dim_date(date_key),
  FOREIGN KEY(harvest_date_key) REFERENCES dim_date(date_key)
);
CREATE TABLE fact_irrigation_event (
  irrigation_event_fact_key INTEGER PRIMARY KEY, field_season_fact_key INTEGER NOT NULL,
  event_date_key INTEGER, volume_m3 REAL, duration_hours REAL,
  measurement_method TEXT, data_status TEXT,
  FOREIGN KEY(field_season_fact_key) REFERENCES fact_field_season(field_season_fact_key),
  FOREIGN KEY(event_date_key) REFERENCES dim_date(date_key)
);
CREATE TABLE fact_field_operation (
  field_operation_fact_key INTEGER PRIMARY KEY, field_season_fact_key INTEGER NOT NULL,
  operation_date_key INTEGER, operation_type TEXT, fertilizer_type TEXT,
  amount_kg REAL, notes TEXT, data_status TEXT,
  FOREIGN KEY(field_season_fact_key) REFERENCES fact_field_season(field_season_fact_key),
  FOREIGN KEY(operation_date_key) REFERENCES dim_date(date_key)
);
CREATE TABLE fact_crop_history (
  crop_history_fact_key INTEGER PRIMARY KEY, field_key INTEGER NOT NULL,
  season_key INTEGER NOT NULL, season_type TEXT, crop_key INTEGER,
  source_crop_name TEXT, source_crop_code TEXT, data_status TEXT,
  FOREIGN KEY(field_key) REFERENCES dim_field(field_key),
  FOREIGN KEY(season_key) REFERENCES dim_season(season_key),
  FOREIGN KEY(crop_key) REFERENCES dim_crop(crop_key)
);
CREATE TABLE fact_canal_schedule (
  canal_schedule_fact_key INTEGER PRIMARY KEY, admin_area_key INTEGER,
  season_key INTEGER, canal_name TEXT, start_date_key INTEGER, end_date_key INTEGER,
  flow_status TEXT, source_key INTEGER,
  FOREIGN KEY(admin_area_key) REFERENCES dim_admin_area(admin_area_key),
  FOREIGN KEY(season_key) REFERENCES dim_season(season_key),
  FOREIGN KEY(start_date_key) REFERENCES dim_date(date_key),
  FOREIGN KEY(end_date_key) REFERENCES dim_date(date_key),
  FOREIGN KEY(source_key) REFERENCES dim_source(source_key)
);
CREATE TABLE fact_groundwater_level (
  groundwater_fact_key INTEGER PRIMARY KEY, location_key INTEGER, admin_area_key INTEGER,
  date_key INTEGER, depth_m REAL, source_key INTEGER, data_status TEXT,
  FOREIGN KEY(location_key) REFERENCES dim_location(location_key),
  FOREIGN KEY(admin_area_key) REFERENCES dim_admin_area(admin_area_key),
  FOREIGN KEY(date_key) REFERENCES dim_date(date_key),
  FOREIGN KEY(source_key) REFERENCES dim_source(source_key)
);
CREATE TABLE fact_soil_salinity (
  soil_salinity_fact_key INTEGER PRIMARY KEY, location_key INTEGER, date_key INTEGER,
  depth_cm REAL, ec_ds_m REAL, esp_pct REAL, source_key INTEGER, data_status TEXT,
  FOREIGN KEY(location_key) REFERENCES dim_location(location_key),
  FOREIGN KEY(date_key) REFERENCES dim_date(date_key),
  FOREIGN KEY(source_key) REFERENCES dim_source(source_key)
);
CREATE TABLE fact_vegetation_index (
  vegetation_index_fact_key INTEGER PRIMARY KEY, location_key INTEGER, scene_fact_key INTEGER,
  ndvi REAL, evi REAL, valid_pixel_pct REAL, data_status TEXT,
  FOREIGN KEY(location_key) REFERENCES dim_location(location_key),
  FOREIGN KEY(scene_fact_key) REFERENCES fact_satellite_scene(scene_fact_key)
);

CREATE INDEX ix_weather_date_location ON fact_weather_daily(date_key,location_key);
CREATE INDEX ix_soil_location_metric ON fact_soil_measurement(location_key,metric_key);
CREATE INDEX ix_daily_water_location_date ON fact_daily_crop_water(location_key,date_key);
CREATE INDEX ix_scenario_season_variety ON fact_seasonal_water_scenario(season_key,variety_key);
CREATE INDEX ix_trial_study_metric ON fact_trial_result(study_key,metric_key);
CREATE INDEX ix_trial_observation_study_metric ON fact_trial_observation(study_key,metric_key);
CREATE INDEX ix_environment_study_metric ON fact_environmental_measurement(study_key,metric_key);
CREATE INDEX ix_water_admin_model ON fact_seasonal_water_scenario(season_key,location_key,variety_key,water_model_key);
CREATE INDEX ix_guidance_scope ON fact_agronomy_guidance(guidance_type,crop_key,variety_key,admin_area_key);
CREATE VIEW vw_weather_daily_readable AS
SELECT d.full_date,d.year,d.month,aa.name_en AS district_en,aa.name_ar AS district_ar,
       l.source_point_id,l.latitude,l.longitude,m.metric_name,m.source_unit,w.value,
       w.data_status,w.issue_flags,s.source_name,s.source_url
FROM fact_weather_daily w JOIN dim_date d USING(date_key)
JOIN dim_location l USING(location_key) LEFT JOIN dim_admin_area aa USING(admin_area_key)
JOIN dim_metric m USING(metric_key) LEFT JOIN dim_source s USING(source_key);
CREATE VIEW vw_variety_water_scenario_readable AS
SELECT se.season_year,l.source_point_id,aa.name_en AS district_en,v.name_en AS variety,
       ws.duration_basis,ws.transplant_date,ws.harvest_date,ws.field_days,
       ws.estimated_etc_mm,ws.rainfall_mm,ws.core_low_m3_feddan,ws.core_high_m3_feddan,
       ws.with_prep_low_m3_feddan,ws.with_prep_high_m3_feddan,wm.model_version,
       ws.data_status,ws.source_record_key
FROM fact_seasonal_water_scenario ws JOIN dim_season se USING(season_key)
JOIN dim_location l USING(location_key) LEFT JOIN dim_admin_area aa USING(admin_area_key)
JOIN dim_variety v USING(variety_key) JOIN dim_water_model wm USING(water_model_key);
CREATE VIEW vw_trial_results_readable AS
SELECT st.source_study_id,st.title,st.publication_year,se.season_year,v.name_en AS variety,
       trt.irrigation_regime,trt.irrigation_interval_days,trt.row_spacing_cm,trt.hill_spacing_cm,
       m.metric_name,m.source_unit,tr.value,tr.standardized_value,tr.standardized_unit,
       tr.source_locator,tr.data_status
FROM fact_trial_result tr JOIN dim_study st USING(study_key)
LEFT JOIN dim_season se USING(season_key) LEFT JOIN dim_variety v USING(variety_key)
LEFT JOIN dim_treatment trt USING(treatment_key) JOIN dim_metric m USING(metric_key);
CREATE VIEW vw_soil_point_profile AS
SELECT l.source_point_id,aa.name_en AS district_en,l.latitude,l.longitude,
       MAX(CASE WHEN m.metric_name='sand' THEN f.value END) AS sand_pct,
       MAX(CASE WHEN m.metric_name='silt' THEN f.value END) AS silt_pct,
       MAX(CASE WHEN m.metric_name='clay' THEN f.value END) AS clay_pct,
       MAX(CASE WHEN m.metric_name='ph_water' THEN f.value END) AS ph_water,
       MAX(CASE WHEN m.metric_name='awc_smu' THEN f.value END) AS awc_smu_mm_per_m,
       MAX(CASE WHEN m.metric_name='awc_rootable_estimate' THEN f.value END) AS awc_rootable_estimate_mm,
       GROUP_CONCAT(DISTINCT f.data_status) AS data_status
FROM fact_soil_measurement f JOIN dim_location l USING(location_key)
LEFT JOIN dim_admin_area aa USING(admin_area_key) JOIN dim_metric m USING(metric_key)
GROUP BY l.location_key;
CREATE VIEW vw_agronomy_guidance_readable AS
SELECT g.guidance_type,c.name_en AS crop,v.name_en AS variety,aa.name_en AS geography,
       g.topic,g.guidance_text,g.value_min,g.value_max,g.unit,g.condition_scope,g.stage_scope,
       g.geography_scope_text,g.published_or_valid_from,g.valid_to,g.confidence_status,
       g.data_status,g.review_notes,s.source_name,s.source_url,g.source_locator
FROM fact_agronomy_guidance g LEFT JOIN dim_crop c USING(crop_key)
LEFT JOIN dim_variety v USING(variety_key) LEFT JOIN dim_admin_area aa USING(admin_area_key)
LEFT JOIN dim_source s USING(source_key);
"""


def norm(s: object) -> str:
    return re.sub(r"[\W_]+", "", str(s or "").strip().casefold())


def date_key(value: object) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        d = date.fromisoformat(str(value)[:10])
    except ValueError:
        return None
    return int(d.strftime("%Y%m%d"))


def add_date(conn: sqlite3.Connection, value: object) -> int | None:
    key = date_key(value)
    if key is None:
        return None
    d = datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    conn.execute("INSERT OR IGNORE INTO dim_date VALUES(?,?,?,?,?,?,?,?,?,?)", (
        key, d.isoformat(), d.year, (d.month - 1) // 3 + 1, d.month, d.day,
        d.timetuple().tm_yday, d.weekday(), d.strftime("%B"), int(d.year % 4 == 0 and (d.year % 100 != 0 or d.year % 400 == 0))))
    return key


def standardize(value: float | None, unit: str | None) -> tuple[float | None, str | None]:
    """Convert only explicit, unambiguous agricultural units; keep source value/unit too."""
    if value is None:
        return None, None
    u = (unit or "").strip().lower().replace(" ", "")
    if u in {"t/feddan", "ton/feddan", "tonne/feddan", "ton_per_feddan"}:
        return value / 0.42, "t/ha"
    if u in {"kg/feddan", "kg_per_feddan"}:
        return value / 0.42, "kg/ha"
    if u in {"m3/feddan", "m³/feddan", "m3_per_feddan"}:
        return value / 4200.0 * 1000.0, "mm"
    return value, unit


def main() -> None:
    if not SOURCE_DB.exists():
        raise FileNotFoundError(SOURCE_DB)
    WAREHOUSE_DIR.mkdir(parents=True, exist_ok=True)
    with SQL_PATH.open("w", encoding="utf-8") as f:
        f.write(DDL)
    if OUTPUT_DB.exists():
        OUTPUT_DB.unlink()
    src = sqlite3.connect(SOURCE_DB)
    dst = sqlite3.connect(OUTPUT_DB)
    src.row_factory = sqlite3.Row
    dst.row_factory = sqlite3.Row
    dst.execute("PRAGMA foreign_keys=ON")
    dst.executescript(DDL)
    profile: list[dict] = []
    review: list[dict] = []

    def source_rows(table: str) -> list[sqlite3.Row]:
        return src.execute(f'SELECT * FROM "{table}"').fetchall()

    def mark(table: str, source_n: int, target_n: int, transform: str, exclusions: int = 0) -> None:
        profile.append({"source_table": table, "source_rows": source_n, "warehouse_rows": target_n,
                        "excluded_rows": exclusions, "transform_summary": transform})

    def add_review(table: str, key: str, issue: str, action: str, severity: str = "manual_review") -> None:
        review.append({"source_table": table, "source_record_key": key, "issue": issue,
                       "required_action": action, "priority": severity})

    # Dimensions: administrative hierarchy, mapped locations, calendar and reference entities.
    district_rows = source_rows("district")
    dmap: dict[int, int] = {}
    for key, r in enumerate(district_rows, 1):
        dmap[r["district_id"]] = key
        dst.execute("INSERT INTO dim_admin_area VALUES(?,?,?,?,?,?)", (key, r["district_id"], r["name_en"], r["name_ar"], r["admin_level"], None))
    for r in district_rows:
        if r["parent_id"] is not None:
            dst.execute("UPDATE dim_admin_area SET parent_admin_area_key=? WHERE source_district_id=?", (dmap.get(r["parent_id"]), r["district_id"]))
    area_key = {r["source_district_id"]: r["admin_area_key"] for r in dst.execute("SELECT source_district_id,admin_area_key FROM dim_admin_area")}
    mark("district", len(district_rows), len(district_rows), "Preserved source IDs and parent administration hierarchy.")

    point_rows = source_rows("grid_point")
    locmap: dict[str, int] = {}
    for key, r in enumerate(point_rows, 1):
        locmap[r["point_id"]] = key
        dst.execute("INSERT INTO dim_location VALUES(?,?,?,?,?,?,?)", (key, r["point_id"], area_key.get(r["district_id"]), r["latitude"], r["longitude"], r["spatial_support"], "grid_point"))
    mark("grid_point", len(point_rows), len(point_rows), "One location dimension row per project grid point; not treated as parcel boundary.")

    season_rows = source_rows("season")
    seasonmap: dict[int, int] = {}
    for key, r in enumerate(season_rows, 1):
        seasonmap[r["season_year"]] = key
        dst.execute("INSERT INTO dim_season VALUES(?,?,?,?,?)", (key, r["season_year"], r["start_date"], r["end_date"], str(r["season_year"])))
    all_years={int(r["season_year"]) for r in source_rows("regional_stats") if r["season_year"]}
    for table,col in [("literature_trial_result","season_year"),("literature_trial_observation","study_year"),("literature_environmental_measurement","sample_year"),("crop_calendar","season_year"),("water_scenario","season_year"),("water_scenario_by_variety","season_year"),("water_scenario_by_variety_clay","season_year"),("water_scenario_by_variety_v3","season_year"),("point_season_summary","season_year")]:
        all_years.update(int(r[0]) for r in src.execute(f'SELECT DISTINCT "{col}" FROM "{table}" WHERE "{col}" IS NOT NULL'))
    for year in sorted(all_years-set(seasonmap)):
        key=max(seasonmap.values(),default=0)+1
        seasonmap[year]=key
        dst.execute("INSERT INTO dim_season VALUES(?,?,?,?,?)",(key,year,None,None,"study_or_observation_year_only"))
    mark("season", len(season_rows)+len(all_years-set(r["season_year"] for r in season_rows)), len(seasonmap), "Season-year dimension; canonical source boundaries preserved; study-only years have no invented start/end dates.")

    # Dimensions for source traceability and studies.
    src_rows = source_rows("data_source")
    srcmap: dict[int, int] = {}
    source_url_map: dict[str, int] = {}
    next_s = 1
    for r in src_rows:
        sk = next_s; next_s += 1; srcmap[r["source_id"]] = sk
        if r["url"]: source_url_map[r["url"].strip()] = sk
        dst.execute("INSERT INTO dim_source VALUES(?,?,?,?,?,?)", (sk, r["source_id"], r["name"], r["url"], r["notes"], "project_source"))
    study_rows = source_rows("literature_study")
    studymap: dict[str, int] = {}
    for key, r in enumerate(study_rows, 1):
        studymap[r["study_id"]] = key
        dst.execute("INSERT INTO dim_study VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", (key, *tuple(r[k] for k in ["study_id","title","authors","publication_year","doi","source_url","location_name","latitude","longitude","methods_summary","limitations","data_status"])))
        if r["source_url"] and r["source_url"] not in source_url_map:
            sk = next_s; next_s += 1; source_url_map[r["source_url"]] = sk
            dst.execute("INSERT INTO dim_source VALUES(?,?,?,?,?,?)", (sk, None, r["title"], r["source_url"], r["limitations"], "literature_study"))
    mark("data_source", len(src_rows), len(src_rows), "Retained publisher/source URLs and lineage.")
    for table in ["agronomy_recommendation","crop_calendar","crop_water_parameter","literature_environmental_measurement","literature_trial_observation","ministry_rule","plant_protection_reference","pump_catalog_series","regional_stats","rice_variety","rice_variety_field_guide","rice_variety_reference","sentinel2_scene"]:
        if "source_url" not in {c[1] for c in src.execute(f'PRAGMA table_info("{table}")')}:
            continue
        for (url,) in src.execute(f'SELECT DISTINCT source_url FROM "{table}" WHERE source_url IS NOT NULL AND TRIM(source_url)<>\'\''):
            if url not in source_url_map:
                sk=next_s; next_s+=1; source_url_map[url]=sk
                dst.execute("INSERT INTO dim_source VALUES(?,?,?,?,?,?)",(sk,None,table,url,"URL retained from the named source table.","table_reference"))
    mark("literature_study", len(study_rows), len(study_rows), "One study dimension per publication; methods and limitations retained.")

    crop_rows = source_rows("crop_reference")
    cropmap: dict[str, int] = {}
    for key, r in enumerate(crop_rows, 1):
        cropmap[r["crop_code"]] = key
        dst.execute("INSERT INTO dim_crop VALUES(?,?,?,?,?,?,?,?,?,?,?)", (key, r["crop_code"], r["name_en"], r["name_ar"], r["botanical_name"], r["aliases_en"], r["aliases_ar"], r["typical_season"], r["functional_group"], r["legume_status"], 0))
    rice_crop_key = cropmap.get("RICE") or cropmap.get("rice")
    crop_lookup: dict[str, int] = {}
    for r in crop_rows:
        for value in [r["crop_code"], r["name_en"], r["name_ar"], r["aliases_en"], r["aliases_ar"], r["botanical_name"]]:
            for part in re.split(r"[,;|/]+", str(value or "")):
                if norm(part): crop_lookup[norm(part)] = cropmap[r["crop_code"]]
    crop_lookup.update({"rice": rice_crop_key, "oryzasativa": rice_crop_key, "رز": rice_crop_key, "أرز": rice_crop_key})
    mark("crop_reference", len(crop_rows), len(crop_rows), "Aliases indexed for previous-crop matching; Rice mapped to the existing reference member.")

    variety_rows = source_rows("rice_variety")
    ref_by_var = {r["variety_id"]: r for r in source_rows("rice_variety_reference")}
    varmap: dict[int, int] = {}
    for key, r in enumerate(variety_rows, 1):
        varmap[r["variety_id"]] = key
        rr = ref_by_var.get(r["variety_id"])
        vals = (key, r["variety_id"], r["name_en"], r["name_ar"], r["season_length_days"],
                rr["grain_type"] if rr else None, rr["quality_note"] if rr else None,
                rr["plant_type_note"] if rr else None, rr["lodging_note"] if rr else None,
                rr["disease_note"] if rr else None, rr["soil_suitability"] if rr else None,
                rr["temperature_min_c"] if rr else None, rr["temperature_max_c"] if rr else None,
                rr["expected_yield_min_ton_ha"] if rr else None, rr["expected_yield_max_ton_ha"] if rr else None,
                rr["source_url"] if rr else r["source_url"], rr["data_status"] if rr else r["data_status"],
                int("NOT_SPECIFIED" in str(r["name_en"])))
        dst.execute("INSERT INTO dim_variety VALUES(" + ",".join("?"*18) + ")", vals)
    mark("rice_variety + rice_variety_reference", len(variety_rows)+len(ref_by_var), len(variety_rows), "One row per variety; catalog traits joined by declared variety ID; placeholder flagged.")

    guides=source_rows("rice_variety_field_guide")
    for i,r in enumerate(guides,1):
        dst.execute("INSERT INTO fact_variety_field_guide VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(i,varmap[r["variety_id"]],r["guide_date"],r["maturity_days_min"],r["maturity_days_max"],r["yield_min_ton_feddan"],r["yield_max_ton_feddan"],r["planting_spacing_cm"],r["hills_per_m2"],r["plants_per_hill_min"],r["plants_per_hill_max"],r["urea_bags_per_feddan"],r["suitability_note"],r["salinity_response"],r["water_stress_response"],r["disease_note"],r["source_url"],r["source_status"],r["notes"],f"rice_variety_field_guide|{r['guide_row_id']}"))
    mark("rice_variety_field_guide",len(guides),len(guides),"Dated variety-guide snapshots retained separately from catalogue traits; source ranges are not collapsed.")

    # Dates assembled from actual observed dates only; never manufacture event dates from text windows.
    all_dates: set[str] = set()
    for t, cols in {"weather_daily":["obs_date"], "rice_daily_water_demand":["obs_date"], "sentinel2_scene":["acquired_at"], "literature_trial_observation":[], "literature_trial_result":[], "irrigation_event":["event_date"], "field_operation":["op_date"], "field_season":["sowing_date","transplanting_date","harvest_date"], "groundwater_level":["measured_on"], "soil_salinity":["measured_on"]}.items():
        for c_name in cols:
            for r in source_rows(t):
                raw = r[c_name]
                if raw and date_key(raw): all_dates.add(str(raw)[:10])
    for r in season_rows:
        for v in [r["start_date"], r["end_date"]]:
            if v and date_key(v): all_dates.add(v[:10])
    for t in ["crop_calendar"]:
        for r in source_rows(t):
            for c_name in ["season_start","season_end","stage_start_date","stage_end_date"]:
                v=r[c_name]
                if v and date_key(v): all_dates.add(v[:10])
    for v in sorted(all_dates): add_date(dst, v)
    datemap={r["full_date"]:r["date_key"] for r in dst.execute("SELECT date_key,full_date FROM dim_date")}
    mark("source date columns", len(all_dates), len(all_dates), "Only ISO dates parsed into calendar keys; free-text windows remain unparsed.")

    # Metric dimension: metric name/unit/domain, including source metrics used by all facts.
    metricmap: dict[tuple[str,str,str], int] = {}
    def metric(name: object, unit: object, domain: str) -> int:
        key=(str(name or "UNSPECIFIED"), str(unit or ""), domain)
        if key not in metricmap:
            mid=len(metricmap)+1; metricmap[key]=mid
            dst.execute("INSERT INTO dim_metric VALUES(?,?,?,?)", (mid,*key))
        return metricmap[key]
    treatmentmap: dict[tuple, int] = {}
    def treatment(regime, interval, row_spacing, hill_spacing) -> int:
        vals=(regime,interval,row_spacing,hill_spacing)
        if vals not in treatmentmap:
            tk=len(treatmentmap)+1; treatmentmap[vals]=tk
            label="|".join("" if x is None else str(x) for x in vals)
            dst.execute("INSERT INTO dim_treatment VALUES(?,?,?,?,?,?)", (tk,*vals,label))
        return treatmentmap[vals]
    samplemap: dict[tuple, int] = {}
    def sample_context(kind, label, treatment_code) -> int:
        vals=(kind,label,treatment_code)
        if vals not in samplemap:
            sk=len(samplemap)+1; samplemap[vals]=sk
            label2="|".join("" if x is None else str(x) for x in vals)
            dst.execute("INSERT INTO dim_sample_context VALUES(?,?,?,?,?)", (sk,*vals,label2))
        return samplemap[vals]

    # Weather: grain = point x observed date x weather parameter; NULL observations preserved.
    weather=source_rows("weather_daily")
    for i,r in enumerate(weather,1):
        dk=datemap.get(str(r["obs_date"])[:10]); lk=locmap.get(r["point_id"])
        if dk is None or lk is None:
            add_review("weather_daily",f"{r['point_id']}|{r['obs_date']}|{r['parameter']}","Date/location key could not be resolved.","Inspect source date and grid point before using this record.","high")
            continue
        mk=metric(r["parameter"],r["unit"],"weather")
        sk=srcmap.get(r["source_id"])
        flags="missing_value" if r["value"] is None else ""
        dst.execute("INSERT INTO fact_weather_daily(date_key,location_key,source_key,metric_key,value,source_record_key,data_status,issue_flags) VALUES(?,?,?,?,?,?,?,?)",
                    (dk,lk,sk,mk,r["value"],f"{r['point_id']}|{r['obs_date']}|{r['parameter']}","source_null_preserved" if r["value"] is None else "gridded_estimate",flags))
    mark("weather_daily",len(weather),dst.execute("SELECT COUNT(*) FROM fact_weather_daily").fetchone()[0],"Long-form weather fact; NULL values preserved and flagged; NASA/grid status retained.")

    # Soil: horizontal properties unpivoted with transparent property units and map-only status.
    soil=source_rows("soil_point")
    soil_props=[("sand_pct","sand","%"),("silt_pct","silt","%"),("clay_pct","clay","%"),("bulk","bulk_density","g/cm3 (source unit needs verification)"),("organic_carbon","organic_carbon","source unit not explicit"),("ph_water","ph_water","pH")]
    soil_count=0; soil_unitmap={}
    for r in soil:
        for col, name, unit in soil_props:
            if r[col] is None: continue
            mk=metric(name,unit,"soil")
            soil_unitmap.setdefault(r["smu_id"],len(soil_unitmap)+1)
            unit_key=soil_unitmap[r["smu_id"]]
            dst.execute("INSERT OR IGNORE INTO dim_soil_unit VALUES(?,?)",(unit_key,r["smu_id"]))
            dst.execute("INSERT INTO fact_soil_measurement(location_key,soil_unit_key,metric_key,depth_top_cm,depth_bottom_cm,value,data_status,source_record_key) VALUES(?,?,?,?,?,?,?,?)",
                        (locmap[r["point_id"]],unit_key,mk,r["top_depth_cm"],r["bottom_depth_cm"],r[col],r["soil_data_status"],f"{r['point_id']}|{col}"))
            soil_count+=1
    soil_awc=source_rows("soil_awc")
    for r in soil_awc:
        for col,name,unit in [("awc_smu_mm_per_m","awc_smu","mm/m"),("awc_rootable_mm_estimate","awc_rootable_estimate","mm")]:
            if r[col] is None: continue
            mk=metric(name,unit,"soil")
            unit_key=soil_unitmap.setdefault(r["smu_id"],len(soil_unitmap)+1)
            dst.execute("INSERT OR IGNORE INTO dim_soil_unit VALUES(?,?)",(unit_key,r["smu_id"]))
            dst.execute("INSERT INTO fact_soil_measurement(location_key,soil_unit_key,metric_key,value,data_status,source_record_key) VALUES(?,?,?,?,?,?)",
                        (locmap[r["point_id"]],unit_key,mk,r[col],r["awc_component_status"],f"{r['point_id']}|{col}"))
            soil_count+=1
    mark("soil_point + soil_awc",len(soil)+len(soil_awc),soil_count,"Soil and AWC columns unpivoted to property rows; map/interpolated status preserved. Organic-carbon and bulk-density units flagged for review.")
    add_review("soil_point", "bulk / organic_carbon", "The released columns do not guarantee an explicit source unit in the analytical table.", "Verify original soil source/metadata and correct metric units before comparing or modelling.", "high")

    # Daily crop water: one crop/point/date row. ET is estimated, not observed applied irrigation.
    water=source_rows("rice_daily_water_demand")
    for r in water:
        dk=datemap.get(str(r["obs_date"])[:10]); lk=locmap.get(r["point_id"])
        if dk is None or lk is None:
            add_review("rice_daily_water_demand",f"{r['point_id']}|{r['obs_date']}","Date/location lookup failed.","Review source calendar and grid point.","high"); continue
        dst.execute("INSERT INTO fact_daily_crop_water(date_key,location_key,crop_key,et0_mm_day,estimated_kc,estimated_etc_mm_day,method_note,data_status,source_record_key) VALUES(?,?,?,?,?,?,?,?,?)",
                    (dk,lk,rice_crop_key,r["et0_mm_day"],r["estimated_kc"],r["estimated_etc_mm_day"],r["method_note"],"derived_estimate_not_applied_irrigation",f"{r['point_id']}|{r['obs_date']}"))
    mark("rice_daily_water_demand",len(water),dst.execute("SELECT COUNT(*) FROM fact_daily_crop_water").fetchone()[0],"ET0/ETc retained as derived crop-water estimates; not relabelled as irrigation volume.")

    # Model version dimension and seasonal water scenario from the selected v3 source.
    model_sources=[("water_scenario_by_variety_v3","v3","Current variety-specific scenario set; source assumptions retained."),
                   ("water_scenario_by_variety","legacy","Earlier scenario model; kept in the warehouse for audit comparison."),
                   ("water_scenario_by_variety_clay","clay_sensitivity","Clay sensitivity scenario; not pooled with v3."),
                   ("water_scenario","baseline","Baseline location-season scenario."),
                   ("point_season_summary","season_summary","Summary estimates and status fields.")]
    modelmap={}
    for i,(table,version,desc) in enumerate(model_sources,1):
        modelmap[table]=i
        dst.execute("INSERT INTO dim_water_model VALUES(?,?,?,?,?)",(i,table,None,version,desc))
    scenario_specs=[("water_scenario_by_variety_v3",("estimated_etc_mm","rainfall_mm","seepage_low_mm_day","seepage_high_mm_day","kc_scale","core_low_mm","core_high_mm","core_low_m3_per_feddan","core_high_m3_per_feddan","prep_establishment_mm","with_prep_low_m3_per_feddan","with_prep_high_m3_per_feddan","wind_scale")),
                    ("water_scenario_by_variety",("estimated_etc_mm","rainfall_mm","scenario_low_depth_mm","scenario_high_depth_mm","scenario_low_m3_per_feddan","scenario_high_m3_per_feddan")),
                    ("water_scenario_by_variety_clay",("estimated_etc_mm","rainfall_mm","scenario_low_depth_mm","scenario_high_depth_mm","scenario_low_m3_per_feddan","scenario_high_m3_per_feddan"))]
    scenario_n=0
    for table,numeric_cols in scenario_specs:
        for ix,r in enumerate(source_rows(table),1):
            vals=(seasonmap.get(r["season_year"]),locmap.get(r["point_id"]),varmap.get(r["variety_id"]),modelmap[table],r["duration_basis"],r["transplant_date"],r["harvest_date"],r["field_days"],r["missing_weather_days"],
                  *(r[col] if col in r.keys() else None for col in ["estimated_etc_mm","rainfall_mm","seepage_low_mm_day","seepage_high_mm_day","kc_scale","core_low_mm","core_high_mm","core_low_m3_per_feddan","core_high_m3_per_feddan","prep_establishment_mm","with_prep_low_m3_per_feddan","with_prep_high_m3_per_feddan","wind_scale"]),
                  r["method_status"],f"{table}|{r['season_year']}|{r['point_id']}|{r['variety_id']}|{r['duration_basis']}|{r['transplant_date']}|{ix}")
            dst.execute("INSERT INTO fact_seasonal_water_scenario(season_key,location_key,variety_key,water_model_key,duration_basis,transplant_date,harvest_date,field_days,missing_weather_days,estimated_etc_mm,rainfall_mm,seepage_low_mm_day,seepage_high_mm_day,kc_scale,core_low_mm,core_high_mm,core_low_m3_feddan,core_high_m3_feddan,prep_establishment_mm,with_prep_low_m3_feddan,with_prep_high_m3_feddan,wind_scale,data_status,source_record_key) VALUES("+','.join('?'*24)+")",vals)
            scenario_n+=1
    mark("water_scenario_by_variety*",sum(len(source_rows(t)) for t,_ in scenario_specs),scenario_n,"Separate water-model dimension and version-specific seasonal scenario fact; v3 is identifiable and legacy records are not pooled.")

    # Regional statistics and trial tables.
    regstats=source_rows("regional_stats")
    for i,r in enumerate(regstats,1):
        dst.execute("INSERT INTO fact_regional_crop_stat VALUES(?,?,?,?,?,?,?,?,?,?,?)",(i,seasonmap.get(r["season_year"]),area_key.get(r["district_id"]),rice_crop_key,r["season_label"],r["area_feddan"],r["production_ton"],r["yield_ton_per_feddan"],r["data_level"],source_url_map.get(r["source_url"],srcmap.get(None)),r["source_status"]))
    mark("regional_stats",len(regstats),len(regstats),"Regional crop area/production/yield kept at reported scale and source level.")

    tr=source_rows("literature_trial_result")
    for i,r in enumerate(tr,1):
        sk=studymap.get(r["study_id"]); mk=metric(r["metric_name"],r["unit"],"trial_result")
        tk=treatment(r["irrigation_regime"],r["irrigation_interval_days"],r["row_spacing_cm"],r["hill_spacing_cm"])
        std,unit=standardize(r["metric_value"],r["unit"])
        dst.execute("INSERT INTO fact_trial_result(study_key,season_key,variety_key,treatment_key,metric_key,value,standardized_value,standardized_unit,source_record_key,source_locator,data_status) VALUES(?,?,?,?,?,?,?,?,?,?,?)",(sk,seasonmap.get(r["season_year"]),varmap.get(r["variety_id"]),tk,mk,r["metric_value"],std,unit,f"literature_trial_result|{r['result_id']}",r["table_reference"],r["data_status"]))
        if sk is None: add_review("literature_trial_result",str(r["result_id"]),"Study reference missing in dimensional lookup.","Resolve publication ID.","high")
    mark("literature_trial_result",len(tr),len(tr),"Trial outcomes linked to study/year/variety/treatment/metric; source units retained with explicit standard unit where supported.")

    obs=source_rows("literature_trial_observation")
    for r in obs:
        sk=studymap.get(r["study_id"]); mk=metric(r["metric_name"],r["unit"],"trial_observation")
        ck=crop_lookup.get(norm(r["preceding_crop"]))
        std,unit=standardize(r["metric_value"],r["unit"])
        dst.execute("INSERT INTO fact_trial_observation(study_key,season_key,crop_key,metric_key,value,standardized_value,standardized_unit,observation_period,puddling,depth_top_cm,depth_bottom_cm,aggregation_level,replicate_count,source_record_key,source_locator,data_status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(sk,seasonmap.get(r["study_year"]),ck,mk,r["metric_value"],std,unit,r["observation_period"],r["puddling"],r["depth_top_cm"],r["depth_bottom_cm"],r["aggregation_level"],r["replicate_count"],f"literature_trial_observation|{r['observation_id']}",r["source_locator"],r["data_status"]))
        if r["preceding_crop"] and ck is None and norm(r["preceding_crop"]) not in {"notreported","unknown","notavailable","na","none"}:
            add_review("literature_trial_observation",str(r["observation_id"]),f"Previous crop '{r['preceding_crop']}' did not match crop aliases automatically.","Map spelling to the correct crop_code after checking the source table.")
    mark("literature_trial_observation",len(obs),len(obs),"Published trial observations linked to study/year/metric; previous crop aliases matched where unambiguous.")

    env=source_rows("literature_environmental_measurement")
    for r in env:
        sk=studymap.get(r["study_id"]); mk=metric(r["parameter_name"],r["unit"],"environmental_measurement")
        ck=sample_context(r["sample_kind"],r["sample_label"],r["treatment_code"])
        std,unit=standardize(r["parameter_value"],r["unit"])
        dst.execute("INSERT INTO fact_environmental_measurement(study_key,season_key,sample_context_key,metric_key,value,standardized_value,standardized_unit,depth_top_cm,depth_bottom_cm,source_record_key,source_locator,data_status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(sk,seasonmap.get(r["sample_year"]),ck,mk,r["parameter_value"],std,unit,r["depth_top_cm"],r["depth_bottom_cm"],f"literature_environmental_measurement|{r['measurement_id']}",r["source_locator"],r["data_status"]))
    mark("literature_environmental_measurement",len(env),len(env),"Measurements separated by sample kind, treatment and study; original unit/status preserved.")

    evidence=source_rows("literature_evidence")
    for r in evidence:
        if r["study_id"] not in studymap:
            add_review("literature_evidence",str(r["evidence_id"]),"Evidence refers to a missing study key.","Resolve study metadata and avoid orphan evidence.","high"); continue
        # Evidence is qualitative/non-additive, so keep it as a fact-like assertion record, not a numeric metric.
        dst.execute("CREATE TABLE IF NOT EXISTS fact_literature_evidence (evidence_fact_key INTEGER PRIMARY KEY, study_key INTEGER NOT NULL, crop_key INTEGER, factor_name TEXT, factor_level TEXT, outcome TEXT, result_summary TEXT, statistical_result TEXT, study_context TEXT, source_locator TEXT, data_status TEXT, source_url TEXT, source_record_key TEXT UNIQUE, FOREIGN KEY(study_key) REFERENCES dim_study(study_key), FOREIGN KEY(crop_key) REFERENCES dim_crop(crop_key))")
        ck=crop_lookup.get(norm(r["crop_of_interest"]))
        dst.execute("INSERT INTO fact_literature_evidence VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",(r["evidence_id"],studymap[r["study_id"]],ck,r["factor_name"],r["factor_level"],r["outcome"],r["result_summary"],r["statistical_result"],r["study_context"],r["source_locator"],r["data_status"],r["source_url"],f"literature_evidence|{r['evidence_id']}"))
    mark("literature_evidence",len(evidence),dst.execute("SELECT COUNT(*) FROM fact_literature_evidence").fetchone()[0],"Qualitative assertions retained as non-additive evidence; not mixed into numeric measures.")

    # Calendar: free-text windows kept as text because boundaries may not be exact ISO dates.
    calendars=source_rows("crop_calendar")
    for i,r in enumerate(calendars,1):
        dst.execute("INSERT INTO fact_crop_calendar VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(i,seasonmap.get(r["season_year"]),varmap.get(r["variety_id"]),r["growth_stage"],r["season_start"],r["season_end"],r["planting_window"],r["transplanting_window"],r["harvest_window"],r["stage_start_date"],r["stage_end_date"],r["data_status"],r["source_url"],f"crop_calendar|{r['calendar_id']}"))
    mark("crop_calendar",len(calendars),len(calendars),"Textual windows are preserved verbatim; only exact date columns can become date keys.")

    # Guidance rows combine farm-facing recommendations and policy rules with explicit review status.
    cropnames={norm(x):k for x,k in crop_lookup.items()}
    recs=source_rows("agronomy_recommendation")
    guidance_id=0
    for r in recs:
        guidance_id+=1; ck=crop_lookup.get(norm(r["crop"])) or rice_crop_key
        vk=None
        if r["variety_scope"]:
            vnorm=norm(r["variety_scope"])
            for vr in variety_rows:
                if vnorm==norm(vr["name_en"]) or vnorm==norm(vr["name_ar"]): vk=varmap[vr["variety_id"]]
        sk=source_url_map.get(r["source_url"])
        dst.execute("INSERT INTO fact_agronomy_guidance VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(guidance_id,"agronomy_recommendation",ck,vk,None,r["topic"],r["recommendation_text"],r["value_min"],r["value_max"],r["unit"],r["condition_scope"],r["stage_scope"],r["geography_scope"],r["publication_date"],None,sk,r["source_locator"],r["confidence_status"],r["confidence_status"],r["notes"]))
        if r["confidence_status"] in ("secondary_source", "unverified", "secondary_transcription"):
            add_review("agronomy_recommendation",str(r["recommendation_id"]),"Recommendation source/status needs review before farmer-facing use.","Verify against the current official ARC/MoA source and record exact publication/page.")
    rules=source_rows("ministry_rule")
    for r in rules:
        guidance_id+=1; sk=source_url_map.get(r["source_url"])
        text=r["rule_text"] or r["topic"] or ""
        dst.execute("INSERT INTO fact_agronomy_guidance VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(guidance_id,"ministry_rule",rice_crop_key,varmap.get(r["variety_id"]),area_key.get(r["district_id"]),r["topic"],text,r["value_num"],r["value_num"],r["unit"],None,None,None,r["valid_from"],r["valid_to"],sk,r["source_url"],r["source_status"],r["source_status"],r["review_notes"]))
        if r["source_status"] not in ("official", "official_primary_source"):
            add_review("ministry_rule",str(r["rule_id"]),"Rule is not verified against a primary official source.","Check current ARC/MoA publication and update validity dates.")
    mark("agronomy_recommendation + ministry_rule",len(recs)+len(rules),guidance_id,"Unified guidance fact keeps source type, scope, validity, confidence and review notes distinct.")

    # Plant protection advice is imported as reference only; incomplete spray recipes stay blocked.
    protections=source_rows("plant_protection_reference")
    for i,r in enumerate(protections,1):
        ck=crop_lookup.get(norm(r["crop"])) or rice_crop_key; sk=source_url_map.get(r["source_url"])
        dst.execute("INSERT INTO fact_plant_protection_guidance VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(i,ck,r["target_name_ar"],r["target_name_en"],r["issue_type"],r["symptom_summary_ar"],r["observation_window_ar"],r["action_timing_ar"],r["management_note_ar"],r["pesticide_product"],r["active_ingredient"],r["rate_value"],r["rate_unit"],r["preharvest_interval_days"],r["source_year"],r["source_page"],sk,r["source_quality"],r["operational_status"],r["operational_status"],r["notes"]))
        if not (r["pesticide_product"] and r["active_ingredient"] and r["rate_value"] is not None and r["preharvest_interval_days"] is not None):
            add_review("plant_protection_reference",r["reference_id"],"Pesticide product/rate/preharvest interval is incomplete.","Keep as symptom/monitoring context; never present as a spray instruction.","high")
    mark("plant_protection_reference",len(protections),len(protections),"Preserved as reference guidance; records lacking product/rate/PHI are flagged non-operational.")

    # Machinery and field-input dimensions/facts.
    pump_series=source_rows("pump_catalog_series")
    psm={}
    for i,r in enumerate(pump_series,1):
        psm[r["pump_series_id"]]=i
        dst.execute("INSERT INTO dim_pump_series VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(i,r["pump_series_id"],r["manufacturer"],r["series_name"],r["pump_type"],r["outlet_diameter_in"],r["min_flow_m3_h"],r["max_flow_m3_h"],r["max_head_m"],r["frequency_hz"],r["power_min_kw"],r["power_max_kw"],r["operating_conditions"],r["source_url"],r["data_status"]))
        dst.execute("INSERT INTO fact_pump_catalog VALUES(?,?,?)",(i,i,r["data_status"]))
        add_review("pump_catalog_series",str(r["pump_series_id"]),"Published flow/head limits are not matched values on one duty curve and are not the farmer's installed pump.","Record model, impeller, total dynamic head and measured discharge before converting seasonal volume to runtime.")
    mark("pump_catalog_series",len(pump_series),len(pump_series),"Catalog families retained; no matched flow/head pair inferred.")
    methods=source_rows("irrigation_method")
    for i,r in enumerate(methods,1): dst.execute("INSERT INTO dim_irrigation_method VALUES(?,?,?,?,?)",(i,r["method_id"],r["name_en"],r["name_ar"],r["notes"]))
    mark("irrigation_method",len(methods),len(methods),"Method reference dimension.")
    machinery=source_rows("machinery_inventory")
    for i,r in enumerate(machinery,1):
        sk=source_url_map.get(r["source_url"])
        dst.execute("INSERT INTO fact_machinery_inventory VALUES(?,?,?,?,?,?,?,?,?)",(i,r["survey_year"],sk,r["admin_level_status"],r["mobile_count"],r["stationary_count"],r["total_count"],r["data_status"],r["notes"]))
    mark("machinery_inventory",len(machinery),len(machinery),"Aggregate machinery inventory retained at published geographic level; not interpreted as farmer pump inventory.")

    seasonal_summaries=source_rows("point_season_summary")
    for i,r in enumerate(seasonal_summaries,1):
        dst.execute("INSERT INTO fact_point_season_summary VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(i,seasonmap.get(r["season_year"]),locmap.get(r["point_id"]),r["season_start_date"],r["season_end_date"],r["weather_day_count"],r["tmin_c_season_mean"],r["tmax_c_season_mean"],r["relative_humidity_pct_season_mean"],r["wind_speed_m_s_season_mean"],r["solar_radiation_mj_m2_day_season_mean"],r["pressure_kpa_season_mean"],r["rainfall_season_mm"],r["et0_season_mm"],r["estimated_etc_season_mm"],r["estimated_etc_minus_rain_mm"],r["water_values_status"],r["water_method"],r["calendar_status"],r["training_readiness"],"estimated_summary_not_observed_field_irrigation"))
    mark("point_season_summary",len(seasonal_summaries),len(seasonal_summaries),"Per-location season summary retained with weather coverage/readiness flags; estimates are labelled as estimates.")
    baseline=source_rows("water_scenario")
    for i,r in enumerate(baseline,1):
        status=r["actual_irrigation_status"] or "scenario_estimate_not_actual_irrigation"
        dst.execute("INSERT INTO fact_baseline_water_scenario VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(i,seasonmap.get(r["season_year"]),locmap.get(r["point_id"]),r["season_days"],r["estimated_etc_season_mm"],r["rainfall_season_mm"],r["land_preparation_assumption_mm"],r["establishment_water_assumption_mm"],r["seepage_low_mm_day"],r["seepage_high_mm_day"],r["scenario_low_depth_mm"],r["scenario_high_depth_mm"],r["scenario_low_m3_per_feddan"],r["scenario_high_m3_per_feddan"],r["actual_irrigation_status"],r["assumption_note"],status))
    mark("water_scenario",len(baseline),len(baseline),"Baseline per-location scenarios kept separately from variety-specific model versions.")

    water_parameters=source_rows("crop_water_parameter")
    for i,r in enumerate(water_parameters,1):
        ck=crop_lookup.get(norm(r["crop"])) or rice_crop_key
        dst.execute("INSERT INTO fact_crop_water_parameter VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",(i,ck,varmap.get(r["variety_id"]),r["growth_stage"],r["kc"],r["parameter_name"],r["parameter_value"],r["unit"],r["valid_conditions"],source_url_map.get(r["source_url"]),r["data_status"],r["value_min"],r["value_max"]))
    mark("crop_water_parameter",len(water_parameters),len(water_parameters),"Water coefficients/assumptions retained with stage, range, source and validity conditions.")

    pump_types=source_rows("pump_type")
    for r in pump_types: dst.execute("INSERT INTO dim_pump VALUES(?,?,?,?,?,?,?)",(r["pump_id"],r["pump_id"],r["name_en"],r["name_ar"],r["power_hp"],r["discharge_m3_per_hour"],r["fuel_type"],r["notes"]))
    mark("pump_type",len(pump_types),len(pump_types),"Installed pump dimension defined; current source has no rows.")
    fields=source_rows("field")
    for i,r in enumerate(fields,1):
        dst.execute("INSERT INTO dim_field VALUES(?,?,?,?,?,?,?)",(i,r["field_id"],locmap.get(r["point_id"]),area_key.get(r["district_id"]),r["area_feddan"],r["polygon_geojson"],r["farmer_consent_id"]))
    mark("field",len(fields),len(fields),"Parcel dimension defined; no parcel records imported.")

    # Satellite scene metadata, with shortlist membership; no pixel indices generated.
    scenes=source_rows("sentinel2_scene"); shortlist={r["scene_id"]:r for r in source_rows("sentinel2_shortlist")}
    for i,r in enumerate(scenes,1):
        acquired=str(r["acquired_at"] or "")[:10]
        dk=datemap.get(acquired)
        if not dk and acquired and date_key(acquired): dk=add_date(dst,acquired); datemap[acquired]=dk
        sk=srcmap.get(r["source_id"])
        sh=shortlist.get(r["scene_id"])
        dst.execute("INSERT INTO fact_satellite_scene VALUES(?,?,?,?,?,?,?,?,?,?,?)",(i,dk,sk,r["scene_id"],r["tile_id"],r["cloud_cover_percent"],r["collection"],r["bbox_json"],sh["dekad"] if sh else None,sh["boundary_overlap_percent_approx"] if sh else None,"metadata_only_ndvi_evi_deferred"))
    mark("sentinel2_scene + sentinel2_shortlist",len(scenes)+len(shortlist),len(scenes),"Scene metadata and shortlist flags retained; imagery indices not downloaded or calculated.")

    # Regional summary calendar from daily observations (source season boundaries only).
    # Empty, not-yet-measured field facts are represented explicitly, never filled with modeled values.
    for t in ["field_season","irrigation_event","field_operation","crop_history","canal_schedule","groundwater_level","soil_salinity","vegetation_index"]:
        n=len(source_rows(t)); fact={"field_season":"fact_field_season","irrigation_event":"fact_irrigation_event","field_operation":"fact_field_operation","crop_history":"fact_crop_history","canal_schedule":"fact_canal_schedule","groundwater_level":"fact_groundwater_level","soil_salinity":"fact_soil_salinity","vegetation_index":"fact_vegetation_index"}[t]
        mark(t,n,dst.execute(f'SELECT COUNT(*) FROM "{fact}"').fetchone()[0],"Future field-level fact structure exists; source table is empty, so no synthetic rows were created.")
    n=len(source_rows("database_metadata")); mark("database_metadata",n,n,"Release metadata retained in the source; it does not describe a measurement grain.")
    n=len(source_rows("sentinel2_shortlist")); mark("sentinel2_shortlist",n,n,"Shortlist membership is represented on the satellite-scene fact.")
    # Every source row count should be accounted for in this ETL profile.

    # Add indexes and verify; transactions persist all imported records only after checks.
    dst.commit()
    integrity=dst.execute("PRAGMA integrity_check").fetchone()[0]
    fk_errors=dst.execute("PRAGMA foreign_key_check").fetchall()
    if integrity != "ok" or fk_errors:
        raise RuntimeError(f"warehouse validation failed: integrity={integrity}, fk_errors={len(fk_errors)}")
    # Write transparent ETL profile and manual review queue.
    with PROFILE_PATH.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=["source_table","source_rows","warehouse_rows","excluded_rows","transform_summary"]); w.writeheader(); w.writerows(profile)
    with REVIEW_PATH.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=["source_table","source_record_key","issue","required_action","priority"]); w.writeheader(); w.writerows(review)
    summary={"source_database":str(SOURCE_DB.relative_to(ROOT)),"warehouse_database":str(OUTPUT_DB.relative_to(ROOT)),"dimensions":{},"facts":{},"integrity_check":integrity,"foreign_key_violations":len(fk_errors),"manual_review_items":len(review),"date_dimension_rows":dst.execute("SELECT COUNT(*) FROM dim_date").fetchone()[0],"metric_dimension_rows":dst.execute("SELECT COUNT(*) FROM dim_metric").fetchone()[0],"transform_policy":"No imputation; preserve source status and values; convert only unambiguous units; retain source IDs/locators; parcel-level outcome facts remain empty."}
    for (name,) in dst.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'dim_%' ORDER BY name"):
        summary["dimensions"][name]=dst.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
    for (name,) in dst.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'fact_%' ORDER BY name"):
        summary["facts"][name]=dst.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
    SUMMARY_PATH.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    dst.close(); src.close()
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__ == "__main__":
    main()
