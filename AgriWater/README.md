# AgriWater Intelligence — Kafr El Sheikh Data Collector

Windows-ready Python project to collect and document public boundary, climate, soil-sample, and Sentinel-2 catalog data. It deliberately does **not** invent rice statistics, parcel boundaries, field measurements, or successful downloads.

## Quick start
1. Install Python 3.11 or newer from https://www.python.org/downloads/ (enable **Add Python to PATH**).
2. Extract this ZIP into a folder with write permission.
3. Double-click `RUN_COLLECTOR.bat`.
4. Read `reports/latest_report.json`, `reports/coverage_summary.json`, and `logs/collector.log`.

Or from CMD in this folder:
```bat
RUN_COLLECTOR.bat
```

## What it attempts
- Downloads the geoBoundaries `gbOpen` ADM1 metadata and GeoJSON, then selects the feature matching Kafr El Sheikh.
- Creates a regular sample grid clipped to the retrieved administrative polygon. Grid points are sampling locations, **not field boundaries**.
- Requests NASA POWER daily data by point and by date chunk. The collector validates status codes and JSON error bodies, retries temporary errors, writes raw responses, and resumes completed chunks.
- Queries SoilGrids for a limited number of sample points while respecting its published fair-use guidance. This is **not** a full-coverage soil raster.
- Queries the public Copernicus Data Space STAC catalog for Sentinel-2 L2A scene metadata, paging through results. This does **not** download imagery pixels.
- Creates a field-survey CSV template and metadata/coverage reports.
- Includes a small rice-variety reference table from the Agricultural Research Center product catalogue. Published yield ranges are catalogue figures, not local guarantees.
- Keeps source-specific failures isolated so other collectors can continue.

## NASA POWER 422 troubleshooting
A 422 response is recorded with its response body. The collector splits date ranges into smaller chunks, validates date format, checks parameter names, and records permanent errors without endless retries. If a source rejects a requested parameter, inspect the error log and disable that parameter in `config.json`; do not treat a failed chunk as collected data.

## Data integrity and coverage
- `data/raw/`: original API responses / source files.
- `data/processed/`: normalized CSV/Parquet tables where applicable.
- `data/metadata/`: source, CRS, coverage, units, and limitation notes.
- `data/processed/rice_variety_reference_arc.csv`: curated rice-variety traits from the public ARC catalogue; load into `rice_variety_reference` with the ETL script below or during a database rebuild.
- `data/metadata/arc_rice_variety_extract.json`: provenance, extraction date, and limitations for the curated ARC rice-cultivar extract.
- `import_arc_rice_varieties.py`: repeatable, backup-first ETL for loading that extract into the existing SQLite database without rebuilding unrelated tables.
- `data/processed/rice_irrigation_trial_results.csv`: 48 curated Giza 179 research-station trial results (grain yield and water productivity) from Sakha, 2017–2018; this is not farmer-field data and contains no absolute irrigation volume by treatment.
- `data/metadata/ghazy2019_giza179_trial.json`: trial citation, methods, extraction details, and limitations.
- `import_rice_irrigation_trials.py`: backup-first, repeatable ETL into separate `literature_study` and `literature_trial_result` tables.
- `data/processed/rice_recommendations_arc.csv`: sourced ARC rice recommendation excerpts with scope, unit, source locator, confidence tag, and caveats.
- `data/processed/rice_variety_field_guide_2025.csv`: 13 variety-specific profiles transcribed from the May 2025 extension bulletin (maturity, published yield, spacing, fertilizer and tolerance fields when stated); kept separate from ARC catalogue values.
- `data/metadata/rice_variety_field_guide_2025.json`: provenance, method, and limitations for the dated cultivar guide.
- `data/processed/pump_catalog_suteksan.csv`: frequency-specific SEP 6/7/8-inch pump-series specifications transcribed from Suteksan Egypt. Family bounds are not duty points.
- `data/processed/machinery_inventory_ministry.csv`: one row from the Ministry's 2023 stationary/mobile pump census; its place-level interpretation is explicitly flagged for confirmation.
- `import_reference_data.py`: backup-first, repeatable ETL to `agronomy_recommendation`, `pump_catalog_series`, and `machinery_inventory`.
- `reports/`: source-by-source status and coverage.
- `reports/data_file_inventory_2026-10-25.csv` and `reports/database_table_inventory_2026-10-25.csv`: current file/table-level collection inventory; refresh with `python build_data_collection_inventory.py`.
- `reports/DATA_COLLECTION_INVENTORY_AR.md`: current data coverage, sources already transcribed, public sources still to retrieve, and the stopping criteria for the collection phase.
- `reports/farmer_input_flow_ar.md` and `data/metadata/farmer_advisory_input_form_ar.json`: simplified farmer-facing input flow, optional precision questions, and output limits; satellite imagery/NDVI and WaPOR are deferred.
- `migrate_establishment_method.py`: backup-first migration adding the rice planting method (`transplanted`, `direct_seeded`, `not_sure`) to each field season.
- `data/processed/moursi_sakha_water_requirements_2012_2013.csv`: 144 observations transcribed from a Sakha 2012–2013 water-budget/ET paper, including lysimeter ETa, seasonal water/yield/productivity, and monthly summaries; wind-speed unit ambiguity is preserved.
- `import_moursi_sakha_water_components.py`: repeatable, backup-first ETL for the Moursi and Abdelkhalek Sakha trial.
- `data/processed/ghazy_sakha_sakha106_water_trial_2022_2023.csv`: 22 Table 8 observations of irrigation volume, yield, water saving and WUE for Sakha 106 by irrigation interval.
- `import_ghazy_sakha_2022_2023_water_trial.py`: repeatable, backup-first ETL for the 2022–2023 Sakha 106 experiment.
- `data/processed/eid_north_delta_planting_irrigation_2023_2024.csv`: 54 observations transcribed from the 2023–2024 Northern Nile Delta study comparing traditional, furrow, and bed planting at three irrigation depths; exact site/cultivar not captured in Table 3.
- `import_eid_north_delta_2023_2024_trial.py`: repeatable, backup-first ETL for that regional trial.
- `data/processed/abou_el_hassan_karada_water_deficit_2014_2015.csv`: 36 Table 8 observations from El-Karada in 2014–2015, comparing continuous flooding with 12-day withholding at critical growth stages; the table/abstract water-saving discrepancy is documented.
- `import_abou_el_hassan_karada_2014_2015.py`: repeatable, backup-first ETL for the El-Karada water-deficit study.
- `logs/collector.log`: detailed requests/errors.
- Resume state: `data/metadata/state.json`.
- Raw response files are cached and not requested again when already valid.

Administrative boundary source: geoBoundaries `gbOpen` is an openly licensed administrative reference with attribution requirements. It is not a cadastral dataset. For legal parcel geometry, obtain official land-survey/cadastral records.

NASA POWER provides gridded/reanalysis-derived estimates; values are not direct measurements at each field. SoilGrids REST API is in active development and has a fair-use policy; use official downloadable raster layers for robust full-area soil analysis. Copernicus catalog search returns scene metadata only. To process/download actual Sentinel-2 pixels, set up a Copernicus Data Space account and OAuth client, then add a separately configured authenticated processing workflow.

## Data not automatically fabricated or claimed
The collector does not automatically populate official rice area, production, variety, irrigation volume, sowing/harvest dates, or farmer records. No official stable open API was verified for those tables. Import published government/statistical data with source citations, or collect field observations using `data/processed/field_survey_template.csv`.

### Loading the published Sakha irrigation-trial extract

Run `python import_rice_irrigation_trials.py` from the project root. Research-station outcomes stay in their own literature tables and are not mixed into farmer field-season records. The extracted paper tables report yield and water productivity but no absolute irrigation volumes for each treatment, so these rows cannot supply pump run-time recommendations.

### Loading the ARC rice-cultivar catalogue extract

Run `python import_arc_rice_varieties.py` from the project root. The script backs up `database/agriwater_v2.sqlite`, upserts the curated ARC catalogue rows, records source metadata, and checks SQLite integrity and foreign keys. The catalogue is a cultivar reference, not proof of current seed availability or local yield; it does not provide field irrigation requirements or a Kafr El Sheikh planting calendar. Disputed Sakha 109 traits are intentionally withheld.

### Loading recommendation and pump references

Run `python import_reference_data.py` from the project root. It saves a database backup, loads the CSV extracts, and checks database integrity and foreign keys. ARC rules extracted from the 2026 attachment are tagged `official_pdf_excerpt`; the attachment could not be fully opened by the text parser, so entries require review against the complete bulletin before they are used as instructions. The 2025 variety guide is stored separately from ARC catalogue values; it is a dated extension bulletin repost and its published yield figures are not local guarantees. Saline-soil entries must not be applied to fields without that condition. Pump catalogue maxima are family envelope values; do not calculate run time from maximum flow unless the pump duty point has been established for the actual head and piping. The Ministry census row is aggregate and its administrative level needs confirmation.

### Loading published Kafr El-Sheikh soil and crop-sequence evidence

Run `python import_kfs_rice_previous_crop_trial.py` to load 104 published treatment means from El-Henawy (2013), a 2007 rice experiment at Kafrelsheikh University farm comparing wheat-rice and berseem-rice and puddling treatments. Run `python import_sakha_soil_baseline.py` to load 20 pre-plant soil values reported for Sakha RRTC rice trials in 2016–2017. Both imports save a database backup and create CSV extracts under `data/processed/`; observations go into `literature_trial_observation`, separate from farmer soil values. They are location- and study-specific evidence, not parcel predictions or current nutrient recommendations.

Run `python import_middle_delta_crop_history_evidence.py` to add a 15-site study record from near Sakha comparing prior rice frequency, salinity, drainage and irrigation-water quality. Run `python import_crop_reference.py` to load a seven-crop Arabic/English naming and season taxonomy for normalizing the farmer's last-three-crops input. `import_field_survey.py` preserves the original crop text and adds the matching `crop_code` when known; an unknown crop name remains preserved and produces a warning. Crop groups are features only: the lookup does not assign numerical NPK credits. The qualitative study findings are kept in `literature_evidence` and are not farmer-level training labels.

Run `python import_delta_rotation_trial.py` to load 20 published means from a two-season rice/rotation experiment in Dakahlia. It provides prior-crop N/P/K context for berseem vs wheat and rice yield means, but is explicitly tagged as neighboring-Delta evidence rather than Kafr El-Sheikh data.

## Limits to understand
- The sampling grid is configurable and capped to prevent accidental excessive requests.
- The first run can take time due to API limits and date chunking.
- A successful API response does not prove full coverage. Review each source status, missing chunks, spatial footprint, and date range in the reports.
- Internet access and source availability are required. This package has not been represented as having downloaded data unless the report says so.

## Data quality review (25 October 2026)
- See `reports/AgriWater_Data_Audit_2026-10-25.md` for source coverage, known data-quality issues, irrigation-volume assumptions, and remaining collection work.
- See `reports/input_data_dictionary_and_gaps_ar.md` for the farmer's five inputs, their database links, inferred-data limits, and the recommended order of remaining schema work. The machine-readable gap list is `reports/input_data_gap_register_ar.csv`.
- The current weather archive is complete for its 38 grid points and 2017–2023 date range, but it is gridded climate input rather than farm-station data.
- SoilGrids returned a value for one test point, no value for another, and a multi-property request timed out; no incomplete SoilGrids extract was merged into the database.
- `repair_reference_quality.py` makes a backup, normalizes known nodata/range-value issues, and adds provenance to the regional statistics. The updated `schema.sql` and database rebuild migration preserve numeric min/max ranges.


## Patch notes (October 2026)
- STAC pagination now tracks URL + HTTP method + POST body, because a valid STAC service can reuse the same endpoint URL while changing its page-token body.
- SoilGrids HTTP 504 errors are treated as an upstream gateway timeout: the collector records the remaining points as not requested and proceeds without repeatedly hitting an unavailable service. This does **not** make SoilGrids available or create synthetic soil data. Retry later or use official SoilGrids raster downloads when the REST API is unavailable.
- This project has not been live-tested against external services as part of this patch. Run it and inspect `reports/latest_report.json`; successful syntax checks do not guarantee that remote APIs are available.
