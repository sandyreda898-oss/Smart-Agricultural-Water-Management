# Data cleaning report

- Source: project CSV table exports under `AgriWater/AgriWater_Clean_Data/data/table_exports`.
- Joined seasonal rows: 266; columns: 37.
- Missing cells: 350 (retained; no imputation).
- Exact duplicate rows: 0; duplicate join keys: 0.
- Outliers: flagged for review only; not removed automatically.
- Target labels: none created. ET0/ETc and water scenario fields remain calculated quantities, not observed irrigation.
- Output: `data/processed/cleaned_dataset.csv`; raw source files are unchanged.
