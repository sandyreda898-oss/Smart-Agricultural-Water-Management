# Machine Learning Technical Report

## 1. Purpose

The ML component is intended to support rice-irrigation decisions in Egypt's Nile Delta. The target must be actual measured irrigation for a defined field and time interval. Calculated water requirements and farmer-applied irrigation are not interchangeable.

## 2. Data inventory and target feasibility

The repository provides approximately 1,089,840 NASA POWER weather records for 38 grid points, seasonal summaries for 2017-2023, mapped soil records, rice references, 470 published trial results, 688 trial observations, 104 environmental measurements, and 14,364 calculated water-scenario records. The current database report describes 44 tables, 34 non-empty. The available summaries are useful for feature inspection and descriptive analysis.

The field-season and irrigation-event tables contain no observed records in the current project snapshot. Water-scenario outputs are calculated with ETc and assumptions, carry statuses such as `NOT_FIELD_MEASURED`, and are not field-measured labels. Published trials are from research stations and do not currently join to project weather/soil as farmer field-season outcomes. Supervised farm-irrigation training is therefore blocked.

## 3. Cleaning and EDA

The package reads raw source files without changing them, validates join keys, trims strings, parses dates, profiles missing values and duplicate keys, and flags suspicious ranges. It does not silently remove extreme values or impute missing values. Imputation, encoding, and scaling are fitted within a training pipeline only after valid labels exist. EDA is restricted to candidate inputs; target analyses are omitted.

## 4. Features and leakage policy

Candidate inputs include weather, mapped soil, location, variety, and planting/season context. Current seasonal weather summaries are retrospective and unavailable at planting. ET0, ETc, calculated water scenarios, target-derived values, and post-request future weather are excluded from predictors. Feature engineering reports keep candidates distinct from an approved prediction schema.

## 5. Model methodology and evaluation

Once field labels are collected, the workflow compares a median baseline, Ridge, decision tree, random forest, and gradient boosting using grouped cross-validation. The group holdout preserves farms/fields/experiments; temporal holdout should also be used for future-season predictions. Hyperparameter search uses training groups only, and the final test groups remain untouched until one final evaluation.

No model metrics are reported now because no valid target exists. A future evaluation must report MAE, MSE, RMSE, and R2 in the verified target definition, compare with the baseline, analyze residuals and subgroup performance, and avoid claiming field accuracy without independent field validation.

## 6. Explainability and reliability

Feature importance and SHAP are deferred until a valid model exists. Any future explanation is associative, not causal. Prediction ranges, unsupported categories, uncertainty calibration, and refusal conditions require independent grouped validation.

## 7. Deployment and current conclusion

Reusable data, cleaning, feature, training, evaluation, validation, model-loading, and prediction modules are included. Model metadata marks training as blocked, and no model `.joblib` artifact is included. Before training, the team must supply verified field-measured irrigation values, units, measurement methods, group identifiers, enough independent groups, and an approved feature set that exists at prediction time.
