-- =====================================================================
-- AgriWater Intelligence Egypt  -  relational schema v2 (SQLite)
-- Link keys:  point_id  (space)   |   season_year  (time)
--             district_id (admin) |   field_id     (real farms)
-- Tables marked [EMPTY] are the missing data you still need to collect.
-- =====================================================================
PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------
-- 1) Reference / dimension tables
-- ---------------------------------------------------------------------
CREATE TABLE data_source (
    source_id   INTEGER PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    url         TEXT,
    notes       TEXT
);

CREATE TABLE district (                      -- governorate (level 1) and markaz (level 2)
    district_id INTEGER PRIMARY KEY,
    name_en     TEXT NOT NULL,
    name_ar     TEXT,
    admin_level INTEGER NOT NULL DEFAULT 2 CHECK (admin_level IN (1, 2, 3)),
    parent_id   INTEGER REFERENCES district(district_id),
    UNIQUE (name_en, admin_level)
);

CREATE TABLE grid_point (                    -- the 38 NASA/soil sample points
    point_id        TEXT PRIMARY KEY,
    latitude        REAL NOT NULL CHECK (latitude  BETWEEN -90  AND 90),
    longitude       REAL NOT NULL CHECK (longitude BETWEEN -180 AND 180),
    district_id     INTEGER REFERENCES district(district_id),   -- fill after ADM2 spatial join
    spatial_support TEXT
);

CREATE TABLE season (
    season_year INTEGER PRIMARY KEY,
    start_date  TEXT,
    end_date    TEXT
);

CREATE TABLE rice_variety (                  -- rice cultivar reference names and season length
    variety_id          INTEGER PRIMARY KEY,
    name_en             TEXT NOT NULL UNIQUE,
    name_ar             TEXT,
    season_length_days  INTEGER,
    source_url          TEXT,
    data_status         TEXT
);

CREATE TABLE rice_variety_reference (         -- published ARC catalogue traits; not local guarantees
    variety_id              INTEGER PRIMARY KEY REFERENCES rice_variety(variety_id),
    expected_yield_min_ton_ha REAL,
    expected_yield_max_ton_ha REAL,
    grain_type               TEXT,
    quality_note             TEXT,
    plant_type_note          TEXT,
    lodging_note             TEXT,
    disease_note             TEXT,
    soil_suitability         TEXT,
    temperature_min_c        REAL,
    temperature_max_c        REAL,
    source_url               TEXT NOT NULL,
    data_status              TEXT NOT NULL
);

CREATE TABLE rice_variety_field_guide (       -- separate, dated extension-guide claims; don't overwrite ARC catalogue
    guide_row_id          INTEGER PRIMARY KEY,
    variety_id            INTEGER NOT NULL REFERENCES rice_variety(variety_id),
    guide_date             TEXT NOT NULL,
    maturity_days_min      REAL,
    maturity_days_max      REAL,
    yield_min_ton_feddan   REAL,
    yield_max_ton_feddan   REAL,
    planting_spacing_cm    TEXT,
    hills_per_m2           REAL,
    plants_per_hill_min    REAL,
    plants_per_hill_max    REAL,
    urea_bags_per_feddan   REAL,
    suitability_note       TEXT,
    salinity_response      TEXT,
    water_stress_response  TEXT,
    disease_note           TEXT,
    source_url             TEXT NOT NULL,
    source_status          TEXT NOT NULL,
    notes                  TEXT,
    UNIQUE (variety_id, guide_date, source_url)
);

CREATE TABLE crop_calendar (
    calendar_id          INTEGER PRIMARY KEY,
    season_year          INTEGER NOT NULL REFERENCES season(season_year),
    variety_id           INTEGER NOT NULL REFERENCES rice_variety(variety_id),
    growth_stage         TEXT,
    season_start         TEXT,
    season_end           TEXT,
    planting_window      TEXT,
    transplanting_window TEXT,
    harvest_window       TEXT,
    stage_start_date     TEXT,
    stage_end_date       TEXT,
    source_url           TEXT,
    data_status          TEXT
);

CREATE TABLE crop_water_parameter (          -- Kc and other FAO-56 parameters
    parameter_id    INTEGER PRIMARY KEY,
    crop            TEXT NOT NULL,
    variety_id      INTEGER REFERENCES rice_variety(variety_id),
    growth_stage    TEXT,
    kc              REAL,
    parameter_name  TEXT,
    parameter_value REAL,
      value_min      REAL,
      value_max      REAL,
    unit            TEXT,
    valid_conditions TEXT,
    source_url      TEXT,
    data_status     TEXT
);

-- ---------------------------------------------------------------------
-- 3b) Published station trials [research evidence; not farmer-field labels]
-- ---------------------------------------------------------------------
CREATE TABLE literature_study (
    study_id          TEXT PRIMARY KEY,
    title             TEXT NOT NULL,
    authors           TEXT,
    publication_year  INTEGER,
    doi               TEXT UNIQUE,
    source_url        TEXT NOT NULL,
    location_name     TEXT,
    latitude          REAL,
    longitude         REAL,
    methods_summary   TEXT,
    limitations       TEXT,
    data_status       TEXT NOT NULL
);

CREATE TABLE literature_trial_result (
    result_id                INTEGER PRIMARY KEY,
    study_id                 TEXT NOT NULL REFERENCES literature_study(study_id),
    season_year              INTEGER NOT NULL,
    variety_id               INTEGER REFERENCES rice_variety(variety_id),
    irrigation_regime        TEXT NOT NULL,
    irrigation_interval_days REAL,
    row_spacing_cm           REAL,
    hill_spacing_cm          REAL,
    metric_name              TEXT NOT NULL,
    metric_value             REAL NOT NULL,
    unit                     TEXT NOT NULL,
    table_reference          TEXT,
    data_status              TEXT NOT NULL,
    UNIQUE (study_id, season_year, variety_id, irrigation_regime,
            row_spacing_cm, hill_spacing_cm, metric_name)
);

CREATE TABLE literature_trial_observation (
    observation_id     INTEGER PRIMARY KEY,
    study_id           TEXT NOT NULL REFERENCES literature_study(study_id),
    study_year         INTEGER,
    observation_period TEXT NOT NULL,
    preceding_crop     TEXT,
    puddling           TEXT,
    depth_top_cm       REAL,
    depth_bottom_cm    REAL,
    metric_name        TEXT NOT NULL,
    metric_value       REAL NOT NULL,
    unit               TEXT NOT NULL,
    aggregation_level  TEXT NOT NULL,
    replicate_count    INTEGER,
    source_locator     TEXT NOT NULL,
    data_status        TEXT NOT NULL,
    source_url         TEXT NOT NULL
);

-- Long-form physical/chemical samples reported by published field trials.
CREATE TABLE literature_environmental_measurement (
    measurement_id INTEGER PRIMARY KEY,
    study_id TEXT NOT NULL REFERENCES literature_study(study_id),
    sample_kind TEXT NOT NULL CHECK (sample_kind IN ('soil','irrigation_water','other')),
    sample_label TEXT NOT NULL,
    sample_year INTEGER,
    treatment_code TEXT,
    depth_top_cm REAL,
    depth_bottom_cm REAL,
    parameter_name TEXT NOT NULL,
    parameter_value REAL NOT NULL,
    unit TEXT NOT NULL,
    source_locator TEXT NOT NULL,
    data_status TEXT NOT NULL,
    source_url TEXT NOT NULL
);

CREATE TABLE literature_evidence (
    evidence_id        INTEGER PRIMARY KEY,
    study_id           TEXT NOT NULL REFERENCES literature_study(study_id),
    crop_of_interest   TEXT,
    factor_name        TEXT NOT NULL,
    factor_level       TEXT,
    outcome            TEXT NOT NULL,
    result_summary     TEXT NOT NULL,
    statistical_result TEXT,
    study_context      TEXT,
    source_locator     TEXT,
    data_status        TEXT NOT NULL,
    source_url         TEXT NOT NULL
);

CREATE TABLE irrigation_method (
    method_id   INTEGER PRIMARY KEY,
    name_en     TEXT NOT NULL UNIQUE,
    name_ar     TEXT,
    notes       TEXT
);

CREATE TABLE pump_type (                     -- [EMPTY] irrigation machines
    pump_id               INTEGER PRIMARY KEY,
    name_en               TEXT NOT NULL UNIQUE,
    name_ar               TEXT,
    power_hp              REAL,
    discharge_m3_per_hour REAL,
    fuel_type             TEXT,
    notes                 TEXT
);

CREATE TABLE pump_catalog_series (           -- public manufacturer catalogue; not field duty point
    pump_series_id      INTEGER PRIMARY KEY,
    manufacturer        TEXT NOT NULL,
    series_name         TEXT NOT NULL,
    pump_type           TEXT,
    outlet_diameter_in  REAL,
    min_flow_m3_h       REAL,
    max_flow_m3_h       REAL,
    max_head_m          REAL,
    frequency_hz        TEXT,
    power_min_kw        REAL,
    power_max_kw        REAL,
    operating_conditions TEXT,
    source_url          TEXT NOT NULL,
    data_status         TEXT NOT NULL,
    UNIQUE (manufacturer, series_name, frequency_hz)
);

CREATE TABLE machinery_inventory (            -- Ministry census row; aggregate, not a farmer machine list
    inventory_id       INTEGER PRIMARY KEY,
    survey_year        INTEGER NOT NULL,
    source_label       TEXT NOT NULL,
    admin_level_status TEXT NOT NULL,
    mobile_count       INTEGER,
    stationary_count  INTEGER,
    total_count        INTEGER,
    source_url         TEXT NOT NULL,
    data_status        TEXT NOT NULL,
    notes              TEXT,
    UNIQUE (survey_year, source_label, source_url)
);

CREATE TABLE agronomy_recommendation (        -- sourced rule, with scope and season context
    recommendation_id INTEGER PRIMARY KEY,
    crop               TEXT NOT NULL DEFAULT 'rice',
    topic              TEXT NOT NULL,
    recommendation_text TEXT NOT NULL,
    value_min          REAL,
    value_max          REAL,
    unit               TEXT,
    condition_scope    TEXT,
    variety_scope      TEXT,
    stage_scope        TEXT,
    geography_scope    TEXT,
    publication_date   TEXT,
    source_url         TEXT NOT NULL,
    source_locator     TEXT,
    confidence_status  TEXT NOT NULL,
    notes              TEXT,
    UNIQUE (topic, recommendation_text, source_url)
);

-- Plant-protection reference records; these are not pesticide prescriptions.
CREATE TABLE plant_protection_reference (
    reference_id             TEXT PRIMARY KEY,
    crop                     TEXT NOT NULL DEFAULT 'rice',
    target_name_ar           TEXT NOT NULL,
    target_name_en           TEXT,
    issue_type               TEXT NOT NULL,
    symptom_summary_ar       TEXT,
    observation_window_ar    TEXT,
    action_timing_ar         TEXT,
    management_note_ar       TEXT,
    pesticide_product        TEXT,
    active_ingredient        TEXT,
    rate_value               REAL,
    rate_unit                TEXT,
    preharvest_interval_days INTEGER,
    source_year              INTEGER,
    source_page              TEXT,
    source_url               TEXT NOT NULL,
    source_quality           TEXT NOT NULL,
    operational_status       TEXT NOT NULL,
    notes                    TEXT
);

-- ---------------------------------------------------------------------
-- 2) Time series and spatial facts (already collected)
-- ---------------------------------------------------------------------
CREATE TABLE weather_daily (
    point_id  TEXT NOT NULL REFERENCES grid_point(point_id),
    obs_date  TEXT NOT NULL,
    parameter TEXT NOT NULL,
    value     REAL,
    unit      TEXT,
    source_id INTEGER REFERENCES data_source(source_id),
    PRIMARY KEY (point_id, obs_date, parameter)
) WITHOUT ROWID;
CREATE INDEX idx_weather_date_param ON weather_daily(obs_date, parameter);

CREATE TABLE rice_daily_water_demand (       -- derived: FAO-56 PM ET0 x Kc
    point_id             TEXT NOT NULL REFERENCES grid_point(point_id),
    obs_date             TEXT NOT NULL,
    et0_mm_day           REAL,
    estimated_kc         REAL,
    estimated_etc_mm_day REAL,
    method_note          TEXT,
    PRIMARY KEY (point_id, obs_date)
) WITHOUT ROWID;

CREATE TABLE soil_point (                    -- HWSD2 soil properties per point
    point_id           TEXT PRIMARY KEY REFERENCES grid_point(point_id),
    smu_id             INTEGER,
    top_depth_cm       REAL,
    bottom_depth_cm    REAL,
    sand_pct           REAL,
    silt_pct           REAL,
    clay_pct           REAL,
    bulk               REAL,
    organic_carbon     REAL,
    ph_water           REAL,
    texture_usda       TEXT,
    texture_soter      TEXT,
    match_found        TEXT,
    soil_data_status   TEXT,
    missing_properties TEXT
);

CREATE TABLE soil_awc (                      -- available water capacity (not field-validated)
    point_id                TEXT PRIMARY KEY REFERENCES grid_point(point_id),
    smu_id                  INTEGER,
    awc_smu_mm_per_m        REAL,
    awc_rootable_mm_estimate REAL,
    root_depth_class        TEXT,
    awc_component_status    TEXT,
    model_screening_status  TEXT,
    awc_use_recommendation  TEXT,
    review_status           TEXT
);

CREATE TABLE point_season_summary (          -- season aggregates per point (feature table)
    season_year    INTEGER NOT NULL REFERENCES season(season_year),
    point_id       TEXT    NOT NULL REFERENCES grid_point(point_id),
    season_start_date TEXT,
    season_end_date   TEXT,
    weather_day_count INTEGER,
    tmin_c_season_mean   REAL,
    tmax_c_season_mean   REAL,
    relative_humidity_pct_season_mean REAL,
    wind_speed_m_s_season_mean        REAL,
    solar_radiation_mj_m2_day_season_mean REAL,
    pressure_kpa_season_mean REAL,
    rainfall_season_mm   REAL,
    et0_season_mm        REAL,
    estimated_etc_season_mm      REAL,
    estimated_etc_minus_rain_mm  REAL,
    water_values_status  TEXT,
    water_method         TEXT,
    calendar_status      TEXT,
    training_readiness   TEXT,
    PRIMARY KEY (season_year, point_id)
) WITHOUT ROWID;

CREATE TABLE water_scenario (                -- low/high scenario estimates (NOT measured)
    season_year  INTEGER NOT NULL REFERENCES season(season_year),
    point_id     TEXT    NOT NULL REFERENCES grid_point(point_id),
    season_days  INTEGER,
    estimated_etc_season_mm REAL,
    rainfall_season_mm      REAL,
    land_preparation_assumption_mm    REAL,
    establishment_water_assumption_mm REAL,
    seepage_low_mm_day   REAL,
    seepage_high_mm_day  REAL,
    scenario_low_depth_mm  REAL,
    scenario_high_depth_mm REAL,
    scenario_low_m3_per_feddan  REAL,
    scenario_high_m3_per_feddan REAL,
    actual_irrigation_status TEXT,
    assumption_note TEXT,
    method_status   TEXT,
    PRIMARY KEY (season_year, point_id)
) WITHOUT ROWID;

CREATE TABLE regional_stats (                -- governorate / markaz production statistics
    stat_id        INTEGER PRIMARY KEY,
    season_year    INTEGER NOT NULL REFERENCES season(season_year),
    district_id    INTEGER NOT NULL REFERENCES district(district_id),
    crop           TEXT NOT NULL,
    season_label   TEXT,
    area_feddan    REAL,
    production_ton REAL,
    yield_ton_per_feddan REAL,
    data_level     TEXT,
      source_url     TEXT,
      source_status  TEXT,
    UNIQUE (season_year, district_id, crop, season_label)
);

-- ---------------------------------------------------------------------
-- 3) Satellite
-- ---------------------------------------------------------------------
CREATE TABLE sentinel2_scene (               -- lean catalog (no geometry/assets JSON)
    scene_id             TEXT PRIMARY KEY,
    tile_id              TEXT,
    acquired_at          TEXT,
    cloud_cover_percent  REAL,
    collection           TEXT,
    bbox_json            TEXT,
    source_id            INTEGER REFERENCES data_source(source_id)
);
CREATE INDEX idx_s2_date ON sentinel2_scene(acquired_at);

CREATE TABLE sentinel2_shortlist (
    scene_id TEXT PRIMARY KEY REFERENCES sentinel2_scene(scene_id),
    dekad    INTEGER,
    boundary_overlap_percent_approx REAL
);

CREATE TABLE vegetation_index (              -- [EMPTY] NDVI/EVI per point per scene
    point_id   TEXT NOT NULL REFERENCES grid_point(point_id),
    scene_id   TEXT NOT NULL REFERENCES sentinel2_scene(scene_id),
    ndvi       REAL,
    evi        REAL,
    valid_pixel_pct REAL,
    PRIMARY KEY (point_id, scene_id)
) WITHOUT ROWID;

-- ---------------------------------------------------------------------
-- 4) Missing environmental data  [EMPTY]
-- ---------------------------------------------------------------------
CREATE TABLE soil_salinity (
    measure_id  INTEGER PRIMARY KEY,
    point_id    TEXT NOT NULL REFERENCES grid_point(point_id),
    measured_on TEXT,
    depth_cm    REAL,
    ec_ds_m     REAL,
    esp_pct     REAL,
    source_id   INTEGER REFERENCES data_source(source_id)
);

CREATE TABLE groundwater_level (
    measure_id  INTEGER PRIMARY KEY,
    point_id    TEXT REFERENCES grid_point(point_id),
    district_id INTEGER REFERENCES district(district_id),
    measured_on TEXT,
    depth_m     REAL,
    source_id   INTEGER REFERENCES data_source(source_id),
    CHECK (point_id IS NOT NULL OR district_id IS NOT NULL)
);

CREATE TABLE canal_schedule (                -- irrigation rotations (المناوبات)
    schedule_id INTEGER PRIMARY KEY,
    district_id INTEGER NOT NULL REFERENCES district(district_id),
    season_year INTEGER REFERENCES season(season_year),
    canal_name  TEXT,
    start_date  TEXT,
    end_date    TEXT,
    flow_status TEXT CHECK (flow_status IN ('open', 'closed') OR flow_status IS NULL),
    source_id   INTEGER REFERENCES data_source(source_id)
);

CREATE TABLE ministry_rule (                 -- Ministry of Agriculture / Irrigation recommendations
    rule_id     INTEGER PRIMARY KEY,
    topic       TEXT NOT NULL,
    variety_id  INTEGER REFERENCES rice_variety(variety_id),
    district_id INTEGER REFERENCES district(district_id),
    rule_text   TEXT NOT NULL,
    value_num   REAL,
    unit        TEXT,
    valid_from  TEXT,
    valid_to    TEXT,
    source_url  TEXT,
    source_status TEXT,
    review_notes TEXT
);

-- ---------------------------------------------------------------------
-- 5) Real farms and measured labels  [EMPTY]  (this is what the model needs)
-- ---------------------------------------------------------------------
CREATE TABLE field (
    field_id         INTEGER PRIMARY KEY,
    point_id         TEXT REFERENCES grid_point(point_id),     -- nearest grid point
    district_id      INTEGER REFERENCES district(district_id),
    area_feddan      REAL CHECK (area_feddan > 0),
    latitude         REAL,
    longitude        REAL,
    polygon_geojson  TEXT,
    farmer_consent_id TEXT
);

CREATE TABLE crop_history (                  -- last 3 crops per field
    history_id  INTEGER PRIMARY KEY,
    field_id    INTEGER NOT NULL REFERENCES field(field_id),
    season_year INTEGER NOT NULL,
    season_type TEXT,
    crop_name   TEXT NOT NULL,
    crop_code   TEXT REFERENCES crop_reference(crop_code),
    UNIQUE (field_id, season_year, season_type, crop_name)
);

CREATE TABLE crop_reference (
    crop_code          TEXT PRIMARY KEY,
    name_en            TEXT NOT NULL,
    name_ar            TEXT NOT NULL,
    botanical_name     TEXT,
    aliases_ar         TEXT,
    aliases_en         TEXT,
    typical_season     TEXT,
    functional_group   TEXT,
    legume_status      TEXT CHECK (legume_status IN ('yes','no','unknown')),
    source_url         TEXT,
    source_locator     TEXT,
    notes              TEXT
);

CREATE TABLE field_season (                  -- one rice season on one field
    field_season_id  INTEGER PRIMARY KEY,
    field_id         INTEGER NOT NULL REFERENCES field(field_id),
    season_year      INTEGER NOT NULL REFERENCES season(season_year),
    variety_id       INTEGER REFERENCES rice_variety(variety_id),
    irrigation_method_id INTEGER REFERENCES irrigation_method(method_id),
    pump_id          INTEGER REFERENCES pump_type(pump_id),
    establishment_method TEXT CHECK (establishment_method IN ('transplanted','direct_seeded','not_sure')),
    sowing_date      TEXT,
    transplanting_date TEXT,
    harvest_date     TEXT,
    cultivated_area_feddan REAL,
    total_irrigation_m3_per_feddan REAL,    -- TARGET LABEL 1
    harvest_yield_ton_per_feddan   REAL,    -- TARGET LABEL 2
    measurement_method TEXT,
    data_collector   TEXT,
    source_notes     TEXT,
    UNIQUE (field_id, season_year)
);
CREATE INDEX idx_field_season_field ON field_season(field_id);

CREATE TABLE irrigation_event (
    event_id        INTEGER PRIMARY KEY,
    field_season_id INTEGER NOT NULL REFERENCES field_season(field_season_id),
    event_date      TEXT NOT NULL,
    volume_m3       REAL CHECK (volume_m3 >= 0),
    duration_hours  REAL CHECK (duration_hours >= 0),
    measurement_method TEXT
);
CREATE INDEX idx_irrigation_event_fs ON irrigation_event(field_season_id, event_date);

CREATE TABLE field_operation (               -- fertilizer, pesticide, other operations
    op_id           INTEGER PRIMARY KEY,
    field_season_id INTEGER NOT NULL REFERENCES field_season(field_season_id),
    op_date         TEXT,
    op_type         TEXT,
    fertilizer_type TEXT,
    amount_kg       REAL,
    notes           TEXT
);

CREATE TABLE database_metadata (
    item    TEXT,
    details TEXT
);

-- ---------------------------------------------------------------------
-- 6) Seed rows (names only, no agronomic numbers invented)
-- ---------------------------------------------------------------------
INSERT INTO district(district_id, name_en, name_ar, admin_level)
VALUES (1, 'Kafr El Sheikh', 'كفر الشيخ', 1);

INSERT INTO rice_variety(variety_id, name_en, data_status)
VALUES (1, 'NOT_SPECIFIED', 'PLACEHOLDER_FOR_REGIONAL_REFERENCE_ROWS');

INSERT INTO irrigation_method(name_en, name_ar) VALUES
    ('continuous_flooding', 'غمر تقليدي'),
    ('alternate_wetting_drying', 'ري متقطع');

-- ---------------------------------------------------------------------
-- 7) Views
-- ---------------------------------------------------------------------
CREATE VIEW v_weather_daily_wide AS
SELECT point_id, obs_date,
       MAX(CASE WHEN parameter = 'T2M'               THEN value END) AS t2m_c,
       MAX(CASE WHEN parameter = 'T2M_MAX'           THEN value END) AS tmax_c,
       MAX(CASE WHEN parameter = 'T2M_MIN'           THEN value END) AS tmin_c,
       MAX(CASE WHEN parameter = 'RH2M'              THEN value END) AS relative_humidity_pct,
       MAX(CASE WHEN parameter = 'WS2M'              THEN value END) AS wind_speed_m_s,
       MAX(CASE WHEN parameter = 'ALLSKY_SFC_SW_DWN' THEN value END) AS solar_radiation_mj_m2_day,
       MAX(CASE WHEN parameter = 'PS'                THEN value END) AS pressure_kpa,
       MAX(CASE WHEN parameter = 'PRECTOTCORR'       THEN value END) AS rainfall_mm_day
FROM weather_daily
GROUP BY point_id, obs_date;

CREATE VIEW v_point_season_features AS
SELECT pss.season_year, pss.point_id, gp.latitude, gp.longitude, gp.district_id,
       pss.weather_day_count,
       pss.tmin_c_season_mean, pss.tmax_c_season_mean,
       pss.relative_humidity_pct_season_mean, pss.wind_speed_m_s_season_mean,
       pss.solar_radiation_mj_m2_day_season_mean, pss.pressure_kpa_season_mean,
       pss.rainfall_season_mm, pss.et0_season_mm,
       pss.estimated_etc_season_mm, pss.estimated_etc_minus_rain_mm,
       sp.sand_pct, sp.silt_pct, sp.clay_pct, sp.bulk, sp.organic_carbon,
       sp.ph_water, sp.texture_usda,
       sa.awc_rootable_mm_estimate, sa.model_screening_status,
       ws.scenario_low_m3_per_feddan, ws.scenario_high_m3_per_feddan,
       rs.area_feddan AS governorate_area_feddan,
       rs.yield_ton_per_feddan AS governorate_yield_ton_per_feddan
FROM point_season_summary pss
JOIN grid_point gp         ON gp.point_id = pss.point_id
LEFT JOIN soil_point sp    ON sp.point_id = pss.point_id
LEFT JOIN soil_awc sa      ON sa.point_id = pss.point_id
LEFT JOIN water_scenario ws ON ws.season_year = pss.season_year AND ws.point_id = pss.point_id
LEFT JOIN regional_stats rs ON rs.season_year = pss.season_year
                           AND rs.district_id = 1 AND rs.crop = 'Rice';

CREATE VIEW v_observed_labels AS             -- real measurements joined to grid points
SELECT f.point_id, fs.season_year, fs.field_id, fs.variety_id,
       fs.irrigation_method_id, fs.pump_id, f.area_feddan,
       fs.total_irrigation_m3_per_feddan, fs.harvest_yield_ton_per_feddan
FROM field_season fs
JOIN field f ON f.field_id = fs.field_id
WHERE fs.total_irrigation_m3_per_feddan IS NOT NULL;
