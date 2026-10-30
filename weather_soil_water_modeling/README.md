# Weather, Soil & Water Modeling

This component of the Smart Agricultural Water Management System provides a reproducible rice water-requirement pipeline for the Egyptian Nile Delta.

## Completed notebooks
1. `notebooks/01_weather_data_analysis.ipynb`
2. `notebooks/02_soil_data_analysis.ipynb`
3. `notebooks/03_rice_crop_parameters.ipynb`
4. `notebooks/04_et0_calculation.ipynb`
5. `notebooks/05_etc_calculation.ipynb`
6. `notebooks/06_irrigation_requirement_validation.ipynb`

## Main outputs
- Clean weather and soil datasets under `data/processed/`.
- Rice parameter/reference tables under `data/reference/`.
- Daily FAO-56 ET0.
- Daily and seasonal rice ETc.
- Seasonal net irrigation requirement, soil sensitivity, and gross-efficiency sensitivity.
- Literature irrigation benchmark and validation summary.

## Important result status
The irrigation estimates are **scenario-based and not field validated**. The main modeled range is 1,912.3–2,761.4 mm/season, while the independent literature 5th–95th percentile benchmark is 678.6–1,570.5 mm/season. The ranges do not overlap, so farmer-facing use requires caution and local field calibration.

## Reusable modules
`src/` contains preprocessing, crop-parameter, ET0, irrigation-requirement and water-volume helpers extracted from the notebook logic.

## Tests
Run from the component root:

```bash
pytest -q
```

## Water-volume conversion
`Water volume (m3) = Water depth (mm) × Area (feddans) × 4.2`

## Integration keys
Use `point_id` with `obs_date` or `season_year` to join modeled weather/water outputs to other project components.
