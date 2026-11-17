# ML Problem Definition - Rice Irrigation Water Requirement

**Component:** Machine Learning - Smart Agricultural Water Management System
**Phase:** 3 (Define the ML problem)
**Status:** Draft for team review. The target variable is **not verified** (see Section 5).
**Based on:** `reports/feasibility_assessment.md` (Phase 1)

---

## 1. Business problem

Rice farmers in Egypt's Nile Delta (study area: Kafr El Sheikh, 38 grid points) irrigate heavily, and water is scarce. The project aims to support irrigation decisions and reduce water waste in rice cultivation.

## 2. Scientific problem

Estimate the irrigation water needed for one rice crop from weather, soil, crop and location information. This is only meaningful if the labels are real irrigation measurements. Calculated (FAO-56) water requirements are a different quantity and must not be mixed with them.

## 3. Prediction objective

**Proposed (conditional) objective:** predict total applied irrigation water for one rice field in one season.

This objective cannot be started today because no measured irrigation labels exist in the project data. Until labels are collected, no model is trained and no model is described as predicting farm irrigation.

## 4. Candidate target variables

| Candidate | Meaning | Unit | Source | Measured / calculated | Suitable for supervised learning? |
|---|---|---|---|---|---|
| `field_season.total_irrigation_m3_per_feddan` | Total applied irrigation per field-season | m3/feddan | Field survey (planned) | Would be measured | Yes, but the table has **0 rows** |
| `irrigation_event` volumes | Per-event applied water | m3/feddan (to confirm) | Field survey (planned) | Would be measured | Yes, but **0 rows** |
| `water_scenario*` low/high (14,364 rows in the 3 per-variety tables) | Theoretical requirement: ETc (ET0 x Kc, FAO-56) plus assumptions for land preparation, establishment and seepage | m3/feddan or mm | Project calculation | **Calculated**, `actual_irrigation_status = NOT_MEASURED` | **No** (see Section 8) |
| Published trial irrigation volumes (470 results, 688 observations, 15 studies) | Treatment means from research stations | study-specific | Literature | Measured on stations, not farmer fields | **No** as training labels (too few independent studies, no `point_id`) |

## 5. Target variable and unit

- **Target (y):** none verified. The proposed target is the measured total irrigation per field-season.
- **Proposed unit:** m3/feddan (1 mm of water = 4.2 m3/feddan, 1 feddan = 4,200 m2). Millimetres, m3 and m3/feddan are never mixed in features, labels or outputs.
- **Decision needed:** the Weather, Soil & Water Modeling member and the project lead must confirm the unit and measurement method (flow meter, pump discharge x run time, other) before any label is accepted.

## 6. Input features (X)

Only features that exist, are reliable, and are available when a farmer requests a prediction.

| Group | Features | Source | Notes |
|---|---|---|---|
| Weather | Temperature (mean, max, min), relative humidity, wind speed, solar radiation, pressure, rainfall | `weather_daily` (NASA POWER, 8 parameters) | Gridded estimates, not station data |
| Soil | Sand, silt, clay, bulk density, organic carbon, pH | `soil_point` (HWSD2, 38 rows, some incomplete) | Coarse global map, no salinity |
| Season summaries | Season-level weather features | `point_season_summary` (266 rows = 38 points x 7 years) | Check that they use only information available at prediction time |
| Crop | Rice variety, growth stage, planting date, days after planting | Field survey / reference tables | Planting information must come from the farmer |
| Location | Latitude, longitude, grid point id | `grid_point` | Within one governorate only |
| ET0 | Reference evapotranspiration | `rice_daily_water_demand` | **Excluded from features for any scenario-based target** (see Section 8) |

**Prediction-time availability (open issue):** a season-total target cannot use weather that has not happened yet at the moment of the request. The team must decide whether the model uses historical climatology, a weather forecast, or predictions made partway through the season.

## 7. Prediction unit

**One field in one rice season** (one row = one field-season). This matches the proposed target. A per-day or per-growth-stage prediction would need irrigation events (`irrigation_event`), which are also empty.

## 8. Why calculated water scenarios are not used as labels

- They are theoretical requirements built from ETc and assumptions, not applied irrigation.
- The weather inputs are the same variables used to compute ET0 and ETc, so a model would learn the formula, and any R2 would measure imitation of a calculation.
- The three per-variety tables describe the same points, years and varieties under different assumptions. They are variants, not 14,364 independent observations.
- Only 38 grid points exist, so rows from the same point and year are strongly dependent.

A surrogate model of the calculation (Option C in the feasibility assessment) is allowed only with explicit team approval and must be labelled "approximation of a calculated requirement", never "farm irrigation prediction".

## 9. Intended users

- **Primary:** farmers and farm advisers, through the Streamlit web application.
- **Secondary:** the project team (Weather/Soil/Water Modeling, Deep Learning, Web Application members) and reviewers.

## 10. Assumptions

- The study area is rice cultivation in Kafr El Sheikh; results do not transfer to other regions or crops.
- Gridded NASA POWER weather and HWSD2 soil are acceptable proxies for field conditions (not verified against stations).
- Field data collection (Option A) will happen with the templates already in the project (`field_survey_template.csv`, `field_survey_irrigation_events_template.csv`).
- Units follow Section 5 once confirmed by the Weather, Soil & Water Modeling member.

## 11. Data limitations

- No measured irrigation labels (0 rows in `field_season`, `irrigation_event`, `v_observed_labels`, `field`).
- Weather is gridded/reanalysis data; soil is a coarse global map without salinity.
- 38 grid points in one governorate, so little spatial diversity.
- Published trials cannot be joined to weather or soil rows (no `point_id`) and come from research stations.
- Splits must be grouped by field, farm or experiment, and by season, to avoid leakage. Too few independent groups will limit what can be claimed.

## 12. Expected model output (once a valid target exists)

```json
{
  "prediction": null,
  "unit": "m3/feddan",
  "model_version": "x.y.z",
  "warnings": [],
  "prediction_status": "estimated"
}
```

`prediction` is a placeholder, not a real value. The output always includes its unit, warnings for out-of-range or unseen inputs, and a statement that it is an estimate. Until labels exist, the prediction interface is not delivered as a working model.

## 13. Decisions needed from the team

1. Confirm what each `water_scenario*` table represents and whether any measured irrigation exists outside the database.
2. Confirm whether and when field data collection (Option A) will happen.
3. Confirm the target unit (m3/feddan) and the prediction unit (field-season).
4. Decide how weather is supplied at prediction time (forecast, climatology, or partial-season).
5. Decide whether Option C (surrogate model, clearly labelled) is wanted.
