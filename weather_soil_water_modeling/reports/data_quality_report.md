# Data Quality Report — Weather, Soil & Water Modeling

## Weather
- Raw weather table: 1,089,840 records, 38 grid points, 2017-01-01 to 2026-10-25.
- Eight verified parameters: T2M, T2M_MAX, T2M_MIN, RH2M, PRECTOTCORR, WS2M, PS, ALLSKY_SFC_SW_DWN.
- 1,292 missing raw values, concentrated at the end of October 2026.
- 0 exact duplicates and 0 duplicate point-date-parameter keys.
- Wide prepared dataset: 136,230 rows. Clean ET0/rainfall modeling dataset: 136,002 rows; 228 rows excluded for incomplete required inputs.
- Physical checks: 0 RH outside 0–100%, 0 negative rainfall, 0 negative wind speed, 0 Tmin > Tmax, 0 negative solar radiation.
- Rainfall above the 99.9th percentile (64.02 mm/day) was flagged rather than removed: 135 rows.
- Limitation: weather is gridded NASA POWER data, not farm-station measurements.

## Soil / AWC
- Soil: 38 points; AWC: 38 points; grid: 38 points.
- 0 duplicate soil or AWC point IDs.
- 36 complete soil records; 2 excluded points (grid_0002, grid_0028) because of non-soil/water-body/no-data mapping status.
- Clean modeling rows: 36.
- AWC recommendations among retained rows: 19 REVIEW_BEFORE_MODEL_USE and 17 CANDIDATE_AFTER_SPATIAL_CHECK.
- Remaining soil/AWC values are mapped/provisional and not field/laboratory validated.

## Crop/reference data
- Calendar and season references cover 2017–2023.
- Kc and stage-length values are reference values and not locally calibrated.
- Intentional missing values/ranges were preserved rather than imputed.

## Modeling output checks
- ET0: 136,002 rows, 0 missing, 0 negative.
- ETc: 39,900 daily rice-season rows, 0 missing/negative low or high ETc.
- Final irrigation: 266 seasonal rows, 0 missing main low/high requirement, 0 negative requirement, 0 cases where low > high.
