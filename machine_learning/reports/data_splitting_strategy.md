# Data splitting strategy

## Current data

- Seasonal feature rows available: 266.
- Current project snapshots cover 38 grid points and 7 rice seasons (2017-2023); the data quality report identifies only five distinct daily weather series across those points.
- There are no verified field-measured irrigation labels, so no train/validation/test split was created and no model score can be calculated.

## Required strategy after field labels arrive

1. Define one row as one measured field-season and attach a stable field/farm identifier, season, and measurement provenance.
2. Keep every row from a farm/field/experiment group together. Use a grouped holdout for final testing; if predicting future seasons, reserve later seasons as well.
3. Fit imputation, encoding, and scaling only inside each training fold using a scikit-learn Pipeline.
4. Tune on training groups only. Reserve the grouped test set until one final evaluation.
5. Report group counts, dates, locations, metrics in the verified target unit, and the limitations caused by too few independent groups.

A random row split is not acceptable for repeated farm, experiment, point, or season observations.
