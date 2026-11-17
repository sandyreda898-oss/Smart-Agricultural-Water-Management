# Feasibility Assessment - Rice Irrigation Water Requirement Prediction

**Component:** Machine Learning - Smart Agricultural Water Management System
**Phase:** 1 (Dataset inspection) - first deliverable required by the task when a supervised target cannot be verified
**Basis:** `AgriWater/database/agriwater_v2.sqlite` (44 tables), inspected with `phase1_inventory.py` and `01_dataset_inspection.ipynb`
**Status:** Draft for team review

---

## 1. Summary

A reliable, measured target for "rice irrigation water requirement" **does not exist in the current project data**.
Input data (weather, soil) exist in useful quantity; real irrigation measurements do not.
Training a model on the 14,364 water scenarios would not predict farm irrigation. It would only reproduce the calculation that generated the scenarios.

**Recommendation:** do not train or present a "water requirement model" yet. Collect real irrigation labels (Section 6), use published trials only as an external sanity check, and agree the path forward with the team (Section 7).

## 2. What is available

| Data | Where | Size | Role for ML |
|---|---|---|---|
| Daily weather (NASA POWER, long format, 8 parameters) | `weather_daily` | 1,089,840 rows, 38 grid points, 2017-01-01 to 2026-10-25 | Input features (gridded estimates, not station measurements) |
| Soil properties (HWSD2) | `soil_point` | 38 rows (some points incomplete) | Input features (coarse global map, no salinity) |
| Season feature table | `point_season_summary` | 266 rows (38 points x 7 years) | Input features |
| Derived ET0 / ETc | `rice_daily_water_demand` | 46,550 rows | Calculated, not measured |
| Water scenarios | `water_scenario` (266), `water_scenario_by_variety` (2,660), `_clay` (2,660), `_v3` (9,044) | 14,364 rows in the three per-variety tables | **Calculated** - see Section 3 |
| Published station trials | `literature_trial_result` (470), `literature_trial_observation` (688), `literature_environmental_measurement` (104) | 15 studies | Reference / benchmark |

## 3. What is missing: a measured target

| Candidate target | Where | Finding |
|---|---|---|
| Real total irrigation, m3/feddan | `field_season.total_irrigation_m3_per_feddan` (marked "TARGET LABEL 1") | **0 rows** - table is empty |
| Irrigation events (volume, duration) | `irrigation_event` | **0 rows** |
| Real labels joined to grid points | view `v_observed_labels` | **0 rows** (depends on `field_season`) |
| Field records | `field`, `crop_history`, `field_operation` | **0 rows** |
| Scenario low/high, m3/feddan or mm | `water_scenario*` | Calculated; `actual_irrigation_status = NOT_MEASURED` |
| `actual_irrigation_m3_per_feddan` in the exported feature file | `rice_field_season_features_2017_2023.csv` | 100% missing; `water_values_status = MODEL_ESTIMATE_NOT_OBSERVED_IRRIGATION` for all 266 rows |

### Why the scenarios cannot be used as labels

- Each scenario is built from ETc (ET0 x Kc, FAO-56) plus assumptions for land preparation, establishment water and seepage. They are theoretical water requirements, not applied irrigation.
- The model inputs (temperature, humidity, wind, radiation, rainfall) are the same variables used to compute ET0 and ETc. A model would learn the formula, and any reported R2 would measure how well it imitates a calculation, not how well it predicts real irrigation.
- The three per-variety tables describe the same points, years and varieties under different assumptions. They are variants, not 14,364 independent observations.
- Only 38 distinct grid points exist, all within one governorate. Rows from the same point and year are strongly dependent, so random splitting would leak information.

## 4. The only measured-style irrigation numbers

Several published research-station experiments (for example Sakha trials, a Northern Delta planting/irrigation study, El-Karada) report irrigation volumes or water productivity per treatment.

Limits:
- Treatment means from experimental stations, not farmer fields.
- A small number of independent studies, so grouped splitting by study leaves too little data to train or evaluate.
- No `point_id`: they cannot be joined to our weather or soil rows.
- Different varieties, planting methods and regimes across studies.

They are suitable as an **external reference range** to sanity-check calculated scenarios, not as a training set.

## 5. Data quality issues found so far (to be handled in Phase 2)

- `nasa_power_daily` file has an empty `unit` column; `nasa_power_daily_units_fixed` contains the units.
- Weather is stored in long format (point, date, parameter, value); needs pivoting.
- Maximum weather value of 485.52 in the 2024-onward part (vs 103.02 in 2017-2023) must be checked against units/parameter before any cleaning decision. Do not remove it automatically.
- 10 exact duplicate rows in `database_metadata`.
- 1,292 missing weather values in the 2024-onward part.
- Gridded/reanalysis weather is not field-station data.

## 6. Data required to build a valid model

Minimum, per field and rice season:

1. **Measured total irrigation** (m3/feddan), from flow meters or pump discharge x run time, with the measurement method recorded.
2. Field location (coordinates or nearest grid point), area (feddan), variety, planting/transplanting dates, establishment method.
3. Irrigation dates and events, if available (`irrigation_event`).
4. Soil information for the field (texture at least; salinity/EC if possible).
5. Season identifier and farm/experiment identifier, so splits can be grouped without leakage.

Volume guide (rough, to be agreed with the team): data from many independent fields over several seasons are needed, not many rows from a few fields. The collection template already exists (`field_survey_template.csv`, `field_survey_irrigation_events_template.csv`).

## 7. Options and recommendation

| Option | Description | Verdict |
|---|---|---|
| A. Collect real irrigation labels, then build the model | Fill `field_season` / `irrigation_event` via field survey, then follow the full ML lifecycle | **Recommended** - the only way to claim a prediction of real irrigation |
| B. Benchmark calculated scenarios against published trials | Compare scenario ranges with station-trial irrigation volumes; no model training | **Recommended now** - cheap, gives scientific credibility |
| C. Surrogate model of the calculation | Train on scenarios to approximate the water-balance formula | Only with explicit team approval and clear labeling as "approximation of a calculated requirement". Never as farm irrigation prediction. Low scientific value |
| D. Train on published treatment means | Use literature trial values as labels | Not recommended - too few independent studies, no joinable features |

**Proposed next steps**
1. Confirm with the Weather, Soil & Water Modeling member the meaning of each scenario table and whether any measured irrigation exists outside the database.
2. Confirm with the project lead whether field data collection (Option A) is planned and when.
3. Meanwhile continue Phase 2 (cleaning) and Phase 4-5 (EDA, features) on input data only, with no target analysis.
4. Do not start model training (Phases 6-10) until a valid target is agreed.

## 8. Statements this project can and cannot make today

**Can say:** weather and soil inputs are available for 38 points in Kafr El Sheikh; calculated water scenarios exist and are clearly marked as estimates.

**Cannot say:** that any ML model predicts actual farm irrigation, or that a model score reflects real field accuracy.
