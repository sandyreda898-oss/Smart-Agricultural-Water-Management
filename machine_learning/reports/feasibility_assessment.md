# ML feasibility assessment

**Status: supervised prediction of farm irrigation is not currently feasible. No model was trained.**

## What the repository contains

The project package includes approximately 1,089,840 NASA POWER daily weather records from 38 grid points, 14,364 calculated water-scenario records, 470 published trial results, 688 trial observations, 104 environmental measurements, mapped soil data, crop references, and seasonal feature summaries. The database report inventories 44 tables, of which 34 are non-empty in the current snapshot.

The weather series span 2017-01-01 through 2026-10-25. The project seasonal summaries cover 38 points across 7 reference seasons (2017-2023), or 266 point-season rows. Several nearby points share weather series; the data-quality report identifies only five distinct daily weather series.

## Target audit

| Candidate | Interpretation | Current decision |
|---|---|---|
| `field_season.total_irrigation_m3_per_feddan` | Actual water applied to one rice field in one season | Suitable only after measured records are collected and verified; current table has 0 rows |
| `irrigation_event` volume | Water applied at one field irrigation event | Potentially useful after measured event records and unit definitions are supplied; current table has 0 rows |
| Water-scenario tables | Calculated requirements under assumptions | Not accepted as ground-truth irrigation labels |
| Published trial results | Treatment outcomes from research stations | Useful as literature context; cannot currently be joined to project weather/soil by field location and are not farmer-field labels |

The project reports `actual_irrigation_status = NOT_FIELD_MEASURED` for model-based scenario outputs. Seasonal `ET0`, `ETc`, and related volumes are calculated. Treating them as observed irrigation would train a surrogate of the existing calculation and could create leakage because the same weather/crop quantities are used to calculate them.

## Decision

Do not train a supervised farm-irrigation model, select a best estimator, report MAE/RMSE/R2, create SHAP values, or serialize a prediction model from the current data. This is the explicit feasibility outcome required when a valid target is absent.

The package prepares inspection, cleaning, EDA, feature engineering, grouped training, evaluation, and prediction code. Training remains locked until verified field measurements and an approved prediction-time feature set are provided.

## Data needed to continue

1. One row per field-season, with actual applied irrigation volume and the definition of the target (net/gross water; whole-field or per-area amount).
2. A documented unit and measurement method, such as a calibrated flow meter or pump discharge multiplied by recorded run time. Keep the raw volume, area, calculation, and quality flags.
3. A stable field/farm/experiment identifier and season/date identifiers so related observations can stay in one validation group.
4. Location, rice variety, planting/transplanting dates, establishment method, and the features that will be known when a farmer requests a prediction.
5. Confirmation from the Weather/Soil/Water team on target definition, any unit conversion, forecast/climatology inputs, and which mapped soil/weather variables are acceptable.
6. Enough independent farms/fields and seasons to support grouped and, if future-season use is intended, temporal holdout evaluation. Ten groups is only the configured minimum for the starter grouped workflow; it is not a guarantee of reliable field performance.

The existing `AgriWater/data/processed/field_survey_template.csv` and irrigation-event template can be used as collection starting points, but they contain no observations in the current project snapshot.
