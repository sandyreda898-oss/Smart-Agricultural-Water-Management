# Feature Selection Report

**Status: exploratory candidates only; supervised selection is blocked.**

There are no verified field-measured irrigation labels. No target correlation, model-based feature ranking, or supervised feature selection was performed.

## Candidate features produced

| Feature | Unit | Input basis | Availability note |
|---|---|---|---|
| `diurnal_temp_range_c` | °C | Full-season average maximum minus minimum temperature | Retrospective; unavailable at planting |
| `vpd_proxy_season_kpa` | kPa | Temperature proxy and full-season mean relative humidity | Retrospective approximation |
| `season_aridity_index` | Unitless | Full-season rainfall divided by temperature proxy plus 10 | Retrospective |
| `clay_to_sand_ratio` | Unitless | Mapped clay and sand percentages | Static soil map proxy |
| `soil_water_retention_index_mm_per_m` | mm/m | Mapped available water capacity multiplied by clay fraction | Static coarse soil estimate |

ET0, ETc, scenario volumes, IDs, and other target-derived or calculated-water fields are not candidate predictors. The actual cleaned sample has 5 independent weather series, so feature correlations are descriptive and highly dependent. A future feature set must be redefined around information available at the farmer's prediction time.
