# Model artifacts

No `.joblib` estimator or preprocessing pipeline is included because the database has no measured field-irrigation labels. `model_metadata.json` and `model_metrics.json` record this blocked state. The training script creates deployable artifacts only after measured labels, grouped validation, and a final held-out evaluation are available.
