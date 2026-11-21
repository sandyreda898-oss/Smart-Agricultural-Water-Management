# ML problem definition: rice irrigation requirement

**Status: conditional proposal; target not verified and supervised training blocked.**

## Business and scientific problem

Support irrigation decisions for rice farmers in Kafr El Sheikh and the Nile Delta. A scientifically meaningful predictor must estimate a clearly defined quantity of water actually applied or required for a specified field and time window. Actual irrigation, calculated crop-water requirement, a recommendation, and a published treatment mean are different quantities.

## Proposed objective and prediction unit

- **Conditional objective:** estimate total applied irrigation for one rice field in one season.
- **Prediction unit:** one field-season.
- **Proposed target:** `total_irrigation_m3_per_feddan`, only if it is derived from verified field measurements and the project team confirms net/gross meaning.
- **Proposed output unit:** m3/feddan. The conversion 1 mm = 4.2 m3/feddan applies to a 4,200 m2 feddan, but conversion must not hide differences between depth and volume definitions.
- **Current verified target:** none. The field-season and irrigation-event tables have no observations in the current snapshot.

## Candidate inputs

Potential inputs include location, season and planting dates, rice variety, establishment method, measured or forecast weather available at request time, and field soil measurements or clearly labelled mapped soil proxies. Current seasonal summaries use future information relative to planting; they are not suitable for a prediction made at planting. The prediction-time feature set is intentionally empty in `config/config.yaml` until the project team approves it.

ET0, ETc, water-scenario volumes, recommendation values, identifiers that reveal the target, and any field measured after the prediction time must not be used as predictors.

## Intended users and assumptions

Intended users are farmers/advisers through the web application and the project development team. Initial scope is rice in Kafr El Sheikh. NASA POWER weather and global mapped soil are proxies, not measurements at each farm. No transfer claim to other governorates, crops, or management conditions is supported.

## Data limitations and expected output

Current data include weather, coarse soil, crop references, published experiments, and calculated scenarios, but no verified field irrigation labels. Published trials lack the field-level joins and independent sample coverage needed for this farmer-facing target. The expected prediction contract is `{prediction, unit, model_version, warnings, prediction_status}` only after a model passes grouped evaluation and reliability review. Until then, prediction is disabled.
