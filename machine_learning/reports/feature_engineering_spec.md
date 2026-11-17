# Feature Engineering & Data Splitting Specification - Phase 4

**Component:** Machine Learning - Smart Agricultural Water Management System
**Phase:** 4 (Feature Engineering & Leak-Free Data Splitting)
**Script:** `src/feature_engineering.py`
**Output:** `data/processed/features_engineered.csv` & `reports/feature_engineering_report.md`

---

## 1. Engineered Features Summary

All engineered features rely strictly on pre-season or observable climatic and soil properties, avoiding any target or formula leakage from FAO-56 (`ET0` / `ETc`):

| Feature Name | Formula / Logic | Physical / Agronomic Meaning |
|---|---|---|
| `diurnal_temp_range_c` | `tmax_c_season_mean - tmin_c_season_mean` | Captures daily thermal amplitude affecting rice evapotranspiration rates. |
| `vpd_season_kpa` | `es(tmean) * (1 - RH / 100)` | Vapor Pressure Deficit (kPa); primary atmospheric driver of crop water demand. |
| `season_aridity_index` | `rainfall_season_mm / (tmean_c_season_mean + 10)` | De Martonne aridity index quantifying natural moisture supply vs. thermal demand. |
| `clay_to_sand_ratio` | `clay_pct / (sand_pct + 1.0)` | Measures soil water retention vs. deep percolation loss in flooded rice paddies. |
| `soil_water_retention_index` | `awc_mm_per_m * (clay_pct / 100.0)` | Effective plant-available water storage capacity in the root zone. |

---

## 2. Leakage Prevention & Splitting Strategy

1. **Exclusion of Calculated Proxies:** `ET0` and `water_scenario*` variables are excluded so models do not reverse-engineer deterministic FAO-56 equations.
2. **Spatial Group Splitting (`GroupKFold`):** Because the 38 grid points in Kafr El Sheikh map to only **14 distinct NASA POWER weather cells** (`weather_cell_id`), random splitting would leak identical weather sequences across train and validation sets.
3. **5-Fold Group Cross-Validation:**
   - **Folds 1–4 (`train`):** ~80% of spatial weather cells.
   - **Fold 0 (`val`):** ~20% of spatial weather cells held out completely for unbiased spatial generalization testing.
