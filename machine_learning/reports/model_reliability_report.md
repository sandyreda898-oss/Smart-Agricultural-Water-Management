# Model reliability report

**Status: no deployable model.** Uncertainty, calibration, and out-of-distribution behavior cannot be assessed without verified labels and independent grouped evaluation data.

Before release, the model must:

- validate required fields, data types, units, categories, and feature order;
- flag inputs outside the training ranges and refuse unsupported or technically invalid values;
- define when it will abstain or warn about extrapolation;
- provide uncertainty only through a method calibrated on independent groups;
- document geographical, temporal, soil-measurement, and target limitations;
- pass a separate reliability review after the reserved test evaluation.

Do not show a confidence percentage without a valid calibrated statistical interpretation. The prediction interface remains disabled while `training_status` is `blocked` or pending reliability review.
