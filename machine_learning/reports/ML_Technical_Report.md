# Machine Learning Technical Report

**Project:** Smart Agricultural Water Management System  
**Status:** Data preparation completed; supervised training blocked pending field measurements.

## 1. Objective

The intended business goal is to support rice-irrigation decisions in Kafr El Sheikh, Egypt. The proposed prediction unit is one field in one rice season, with applied irrigation volume in m3/feddan. The model is not currently able to make this prediction because no measured target labels are present.

## 2. Data inventory and suitability

The SQLite database is healthy and contains 44 tables: 34 non-empty and 10 empty. It contains 1,089,840 daily NASA POWER weather rows for 38 grid points, 38 soil-point records, and 266 point-season summaries for 2017-2023. Only five distinct daily weather series occur across the 38 points. Two points have no usable soil data, leaving 252 point-season feature rows.

The database has zero rows in `field_season`, `irrigation_event`, and `v_observed_labels`. The 14,364 water-scenario rows are calculated outputs based on ETc and assumptions, with status indicating they were not measured. They cannot be treated as applied irrigation. Published treatment results are from research-station experiments and are not row-wise joinable to the grid-weather features.

## 3. Data preparation

The read-only cleaning script profiled all tables, converted the long weather table to one row per point and day, preserved missing values, and flagged suspicious daily rainfall without removing it. It left the raw database unchanged. The run recorded 22 cleaning operations and 44 checks; three checks need review. The 1,292 missing weather values are in the last six provider-latency days. Two soil points were excluded instead of imputing nonexistent profiles. Ten exact duplicate metadata rows were removed.

Six weather values around 485.52 mm/day were flagged for source review. The run observed only five independent weather series, so grouped splitting is required and remains statistically weak with the available extract.

## 4. EDA and feature preparation

EDA covers 252 usable point-season rows, weather trends, soil texture, literature ranges, and input distributions. The literature values are benchmarks only. Five retrospective candidate features were generated: temperature range, VPD proxy, aridity index, clay-to-sand ratio, and soil-water-retention index. ET0, ETc, and scenario columns are excluded from model inputs.

The weather inputs include complete-season summaries. They are retrospective and are not available to a farmer at planting. A deployment design must use forecasts, climatology, or partial-season observations and must be validated for that exact prediction time.

## 5. Modeling and validation status

No model, preprocessing object, hyperparameter search, held-out test score, SHAP value, uncertainty interval, or prediction has been produced. The package's training script accepts only rows marked `MEASURED_FIELD`, with target unit m3/feddan and an independent field group ID. Until such rows exist, training writes a blocked-status report and does not create `.joblib` files.

Once labels are collected, model selection must use grouped cross-validation by field/farm/experiment. Keep test groups untouched until after tuning. Report MAE, MSE, RMSE, and R² in the target's scientific units and disclose the small group count. Evaluate once on the test set and inspect error bias and subgroup performance.

## 6. Prediction and deployment

`predict_water_requirement` validates schema and units, loads a model only after a final evaluation/reliability gate, returns predictions with unit/version/warnings, and otherwise refuses to predict. No web application should present calculated scenario outputs as model estimates.

## 7. Next data required

For each independent field-season, collect measured applied irrigation volume, measurement method, field/farm identifier, area, location, variety, planting dates, and season. Include event records where possible. Validate units and provenance with the field team. Then rerun the training and evaluation lifecycle.
