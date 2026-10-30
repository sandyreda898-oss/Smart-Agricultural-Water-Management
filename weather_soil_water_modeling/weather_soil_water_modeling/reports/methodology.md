# Methodology — Weather, Soil & Water Modeling

## Pipeline
1. Clean and pivot daily NASA POWER weather data; attach spatial grid metadata.
2. Screen soil/AWC data and exclude explicitly invalid mapped points.
3. Prepare rice growth-stage, Kc and water-management reference tables.
4. Calculate daily FAO-56 Penman–Monteith reference evapotranspiration (ET0).
5. Match 2017–2023 dates to a 150-day rice season and calculate ETc = ET0 × Kc.
6. Calculate seasonal rice irrigation requirement using ETc, effective rainfall, saturation, seepage/percolation and water-layer establishment.
7. Convert depth to m3/feddan and run soil/efficiency sensitivity scenarios.
8. Compare with project scenario tables and published irrigation records.

## ET0
Daily FAO-56 Penman–Monteith is implemented with mean RH for actual vapor pressure, G=0 for daily calculations, and Rso=0.75×Ra as the near-sea-level clear-sky-radiation approximation used in the notebook.

## Kc / ETc
- Initial: 30 days, Kc 1.05.
- Development: 30 days, Kc linearly increases 1.05→1.20.
- Mid-season: 60 days, Kc 1.20.
- Late season: 30 days, Kc linearly declines from 1.20 to 0.60 (low) or 0.90 (high).
- ETc = ET0 × Kc.

## Effective rainfall
Monthly method used in Notebook 06:
- Pe = 0.8P − 25 for P > 75 mm/month.
- Pe = 0.6P − 10 otherwise.
- Pe is clipped to zero and allocated to rainy days in proportion to daily rainfall.

## Net irrigation
Net irrigation = ETc + SAT + PERC + WL − Pe − stored soil water adjustment.
- SAT = 200 mm.
- Main PERC range = 4–8 mm/day × 150 days = 600–1,200 mm.
- WL = 100 mm.
- Stored soil water adjustment = 0 because initial soil moisture was not measured.

## Soil sensitivity
Project sensitivity:
- clay ≥40%: 1–3 mm/day;
- 25%≤clay<40%: 2–5 mm/day;
- clay<25% or no usable soil: 4–8 mm/day.

## Gross irrigation
Gross irrigation = net irrigation / efficiency. Because no site-specific efficiency was measured, 60%, 70% and 80% are presented only as sensitivity scenarios.

## Volume
Water volume (m3) = water depth (mm) × area (feddans) × 4.2.
