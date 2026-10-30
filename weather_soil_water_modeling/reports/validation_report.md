# Validation Report — Irrigation Requirement

## Internal scenario comparison
The existing `water_scenario.csv` contains 266 rows, all labeled `NOT_MEASURED` and `SCENARIO_ESTIMATE_NOT_FIELD_VALIDATED`. It is therefore a consistency reference only, not ground truth.

Mean new-minus-old differences:
- Low depth: -205.44 mm.
- High depth: -280.01 mm.
- Low volume: -862.84 m3/feddan.
- High volume: -1,176.05 m3/feddan.
- Stage-based ETc versus previous ETc: -119.32 mm/season.

## Independent published benchmark
65 seasonal/total irrigation records were retained from the literature tables and all were converted to mm/season.
- Minimum: 640.5 mm.
- 5th percentile: 678.6 mm.
- Median: 1,176.1 mm.
- Mean: 1,162.1 mm.
- 95th percentile: 1,570.5 mm.
- Maximum: 1,614.3 mm.

## Main model
- Modeled main range: 1,912.3–2,761.4 mm/season.
- Literature 5th–95th range: 678.6–1,570.5 mm/season.
- Literature range overlap: 0% of 266 modeled location-season records.

## Interpretation
The literature benchmark is substantially lower than the FAO-based paddy-water scenario. This discrepancy may reflect different irrigation regimes and experimental treatments, seepage/percolation assumptions, soil conditions, and inclusion of land-preparation and standing-water requirements. The final irrigation results must therefore be labeled scenario-based estimates, not field-validated demand.

## Additional limitations
- No relevant environmental water/percolation measurements were available for independent validation.
- Initial soil moisture was not measured; AWC was not subtracted as actual stored water.
- Irrigation efficiency was not measured; gross values are sensitivity scenarios only.
- Field calibration is recommended before operational farmer-facing use.
