# Smart Agricultural Water Management - Machine Learning

This folder contains the ML component, notebooks, reusable Python modules, reports, tests, and model metadata for the Smart Agricultural Water Management project.

## Scientific status

The current repository contains weather, mapped soil, crop references, published experiments, and calculated water scenarios. It does **not** contain verified field-measured irrigation labels. The water scenarios and seasonal ETc values are calculated estimates; they are not actual farm irrigation. The model is therefore marked `blocked`, and no fake `.joblib` files or performance scores are included.

The current best deliverable is a documented feasibility assessment and a reusable workflow that will accept verified labels later. This follows the assignment's requirement not to manufacture labels or claim field accuracy without field validation.

## Run in Google Colab

Use the complete GitHub repository because the notebooks read CSV exports under `AgriWater/AgriWater_Clean_Data/data/table_exports/`.

In a fresh Colab runtime, run:

```python
%cd /content
!git clone --depth 1 https://github.com/sandyreda898-oss/Smart-Agricultural-Water-Management.git
%cd /content/Smart-Agricultural-Water-Management
%pip install -r machine_learning/requirements.txt
```

Then open the notebooks from `machine_learning/notebooks/` and run them in order:

1. `01_dataset_inspection.ipynb`
2. `02_data_cleaning.ipynb`
3. `03_eda.ipynb`
4. `04_feature_engineering.ipynb`
5. `05_model_training.ipynb` - currently stops safely because measured labels are missing.
6. `06_hyperparameter_tuning.ipynb` - run only after notebook 05 succeeds.
7. `07_model_evaluation.ipynb` - run only after notebook 06; it evaluates the reserved test groups once.
8. `08_explainable_ai.ipynb` - run only after model evaluation and release review.

The first four notebooks can be run with the current project exports. Notebooks 05-08 are prepared but will report that training, tuning, final evaluation, and SHAP are blocked until the required measured target is supplied and verified. After field data are reviewed, populate `data/processed/training_dataset.csv`, update `config/config.yaml`, and rerun notebooks 01-08 in order. Keep the final test groups untouched until notebook 07.

The first four notebooks can be run with the current project exports. Notebooks 05-08 must not be treated as completed model results while the target remains absent.

## Minimal verified training table

One row must represent one measured rice field-season and include:

- `total_irrigation_m3_per_feddan`: actual applied irrigation, with the project team confirming whether it is net/gross and how it was measured;
- `target_status`: `FIELD_MEASURED` or `VERIFIED_FIELD_MEASUREMENT` after review;
- `measurement_method`: flow meter, calibrated pump discharge x operating time, or another documented method;
- `field_group_id`: stable farm/field identifier for group-safe splitting;
- season/date and location identifiers;
- only features available at the time the prediction is requested, with units and provenance.

Do not enter a theoretical water scenario, ETc estimate, recommendation, or published station mean as a farmer's measured label. The data owner must confirm the target unit and feature availability before setting the verification flags in `config/config.yaml` to `true` and selecting features.

## Reusable command line

Run commands from the repository root:

```bash
python -m machine_learning.src.data_cleaning --root machine_learning
python -m machine_learning.src.feature_engineering --root machine_learning
python -m machine_learning.src.train --root machine_learning --phase compare
python -m machine_learning.src.train --root machine_learning --phase tune
python -m machine_learning.src.evaluate --root machine_learning
```

The training and evaluation commands write a blocked status and stop safely when labels or provenance are absent. They do not train on calculated scenarios.

## Run the included checks

From inside `machine_learning/`:

```bash
python -m unittest discover -s tests -v
```

The checks cover the preprocessing pipeline, feature leakage guard, blocked model loading, input validation, and prediction refusal before model release.

## Upload plan for GitHub

1. Extract this ZIP at the repository root so the folder is named exactly `machine_learning/`.
2. Confirm the full repository still contains the source `AgriWater/` exports.
3. Commit the `machine_learning/` folder, including reports and notebooks. Keep generated raw/intermediate data and model artifacts out of Git unless the project team has reviewed them.
4. The ZIP does not update GitHub automatically; after review, upload or commit the extracted folder to the repository.

