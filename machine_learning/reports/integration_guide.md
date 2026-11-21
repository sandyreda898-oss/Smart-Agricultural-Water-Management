# Integration guide

## Current state

The prediction interface and input validation code are prepared, but prediction is intentionally disabled because there is no released model. Do not create a fake demonstration prediction.

## After model release

From the repository root, the application can import the function:

```python
from machine_learning.src.predict import predict_water_requirement

result = predict_water_requirement(input_data)
```

`input_data` must contain exactly the feature columns listed in `models/feature_schema.json`. Units and accepted categories are stored with the schema. The return value contains `prediction`, `unit`, `model_version`, `warnings`, and `prediction_status`. Invalid columns or types raise actionable `ValueError`s; out-of-training-range values generate warnings.

The application must load the saved artifacts from the package's `models/` directory. It must not run notebooks or training during a farmer request. Keep relative paths and include the tested library versions in model metadata.

## Release gate

The files `best_model.joblib` and `preprocessing_pipeline.joblib` are generated only from verified field measurements. After grouped test evaluation, reliability review must set the metadata and feature schema to `training_status: ready` before prediction is enabled.
