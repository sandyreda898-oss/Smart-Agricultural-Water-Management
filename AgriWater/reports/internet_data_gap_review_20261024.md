# AgriWater internet-data review — 2026-10-24

## Existing data checked

- `database/agriwater_v2.sqlite`: 777,024 daily weather rows, 38 sample points, 3,775 Sentinel-2 scene metadata rows, 119 shortlisted scenes, 266 point-season summaries, 266 modeled water scenarios, and 7 governorate-level rice statistics rows (2017–2023).
- The normalized database had 9 rice-variety rows including the placeholder, but no ARC catalogue trait table. It had no field-season labels, irrigation-event records, or vegetation-index rows.
- Existing Sentinel-2 products are a catalog only; no image pixels are included. Existing soil samples are model/raster-derived point values, not lab measurements. SoilGrids point API requests failed in the last collector report.

## Added from an open source

- Added four cultivar records from the Agricultural Research Center (ARC) Field Crops Research Institute catalogue: Sakha 102, 107, 108, and 109.
- Added published season lengths where listed, yield ranges in tonnes/hectare, and the catalogue's grain, suitability, temperature, and disease notes. Sakha 109 has no season length in the catalogue entry, so the database keeps it blank.
- Added these records to `data/processed/rice_variety_reference_arc.csv` and the normalized database table `rice_variety_reference`. The existing Sakha 102 candidate entry now has the ARC source and catalogue season length.
- Added the table to `schema.sql` and the CSV loader in `build_agriwater_db.py`, so a future database rebuild retains these records.
- Backup created before changing the normalized database: `database/agriwater_v2_before_arc_varieties_20261024_161255.sqlite`.

## Still missing or not safely retrievable online

- No verified open official series beyond the existing 2017–2023 Kafr El Sheikh rice statistics. The Ministry of Agriculture lists 2024/2025 statistical bulletins, but its page requires login to view the files. CAPMAS lists rice area and production indicators, but this review did not retrieve a direct, citable downloadable time series. Do not extend the annual table with secondary or unverified values.
- No field-level irrigation volumes or field-level harvest yields. Satellite evapotranspiration and water-productivity layers can provide modeled/remote-sensing indicators, not the amount of irrigation water delivered to each farm.
- No Sentinel-2 NDVI/EVI values yet. Existing metadata is not image data. No imagery or global soil rasters were downloaded in this pass to avoid large network transfers.
- SoilGrids documentation currently reports its REST API as paused; use small, clipped map/WCS requests only if a needed property cannot be obtained from existing soil layers.

## Sources

- ARC cultivar catalogue: https://www.arc.sci.eg/Products/Search/15?TypeID=1&lang=1
- Ministry of Agriculture statistical bulletins: https://www.agri.gov.eg/library/71
- CAPMAS agricultural indicators: https://old.capmas.gov.eg/Pages/IndicatorsPage.aspx?Ind_id=2370
- FAO WaPOR data and access: https://www.fao.org/in-action/remote-sensing-for-water-productivity/wapor-data/
- FAO Egypt IPAT pilot overview: https://www.fao.org/in-action/remote-sensing-for-water-productivity/country-activities/tools-in-co-development/en
- ISRIC SoilGrids documentation and API status: https://docs.isric.org/globaldata/soilgrids/
