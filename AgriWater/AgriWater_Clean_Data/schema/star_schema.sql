
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
