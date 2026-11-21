# Raw data

Raw project data remain in the repository's existing `AgriWater/` folders and are read without modification. The ML component deliberately does not duplicate large weather files or databases.

For field-measured training labels, add a reviewed `training_dataset.csv` to `data/processed/` only after the project team confirms the label definition, unit, provenance, measurement method, and prediction-time feature set. Do not copy calculated water scenarios into this file as measured labels.
