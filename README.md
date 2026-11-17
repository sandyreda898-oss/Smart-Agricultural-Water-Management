# Smart Agricultural Water Management System

An Explainable AI project for agricultural water optimization and crop yield prediction in Egypt, focusing on rice and wheat using data analysis, machine learning, and SHAP for model interpretability.

---

## 📌 Project Phases & Implementation Structure

The project repository is systematically structured inside the `machine_learning/` directory, separating source code and documentation across 5 core phases:

* **Phase 1 & 2: Dataset Inspection & Data Cleaning**
  * `src/data_cleaning.py`: Cleans raw agronomic and climate data, handles missing values, and flags unusable entries.
  * `reports/data_cleaning_report.md`: Summary of data profiling and cleaning steps.
* **Phase 3: Exploratory Data Analysis (EDA) & Problem Definition**
  * `reports/ml_problem_definition.md`: Defines irrigation water requirement forecasting objectives for Egyptian agriculture.
* **Phase 4: Feature Engineering & Spatial Splitting**
  * `src/feature_engineering.py`: Computes pre-season meteorological and soil features (Diurnal Temperature Range, VPD, Aridity Index) without leakage, applying `GroupKFold` split by weather cells.
  * `reports/feature_engineering_report.md`: Detailed engineering specifications.
* **Phase 5: Model Training & Spatial Cross-Validation**
  * `src/model_training.py`: Trains and evaluates baseline and ensemble regression models (Ridge, Random Forest) using spatial cross-validation.
  * `reports/model_training_report.md`: Out-of-fold generalization performance metrics.

---

## ⚙️ Repository Directory Structure

```text
Smart-Agricultural-Water-Management/
│
├── machine_learning/
│   ├── src/                  # Executable Python scripts for all phases
│   │   ├── data_cleaning.py
│   │   ├── feature_engineering.py
│   │   └── model_training.py
│   └── reports/              # Markdown documentation & technical reports
│       ├── data_cleaning_report.md
│       ├── ml_problem_definition.md
│       ├── feature_engineering_report.md
│       └── model_training_report.md
│
└── README.md
