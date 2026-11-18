# Model Reliability Report

**Status: no deployable model.** Prediction uncertainty and extrapolation checks cannot be calibrated without a valid field-measured training target and independent evaluation groups.

Before deployment, the model must:

- validate required feature names, order, numeric types, and units;
- flag values outside the training ranges and unsupported varieties/locations;
- refuse predictions for missing or non-finite required inputs;
- report the target unit and model version;
- use an uncertainty method calibrated on independent grouped validation data;
- warn that current seasonal aggregates are retrospective and unavailable at planting;
- remain unavailable until the held-out evaluation and reliability review are complete.

Do not display a confidence percentage without a calibrated statistical interpretation.
