"""Add transcription of Tables 13-14 of the Sakha 2022-23 rice trial."""
from pathlib import Path
import csv

ROOT = Path(__file__).resolve().parent
CSV_PATH = ROOT / "data/processed/sakha_water_quality_2022_2023_numeric_results.csv"
URL = "https://journals.ekb.eg/article_410567_1c6b54dd580d5218d7d7f0e16b74b2dd.pdf"
FIELDS = ["study_id","season_year","cultivar","water_quality_treatment","metric_name","metric_value","unit","table_reference","source_url","data_status"]
rows = []

def add_means(table, treatments, metrics):
    # metrics: name => (unit, {treatment: [year1, year2]})
    for treatment, values in treatments.items():
        for metric, (unit, by_treatment) in metrics.items():
            for year, value in zip((2022, 2023), by_treatment[treatment]):
                rows.append({"study_id":"gaber_sakha_water_quality_2022_2023", "season_year":year,
                    "cultivar":"ALL_CULTIVARS", "water_quality_treatment":treatment,
                    "metric_name":metric, "metric_value":value, "unit":unit,
                    "table_reference":table, "source_url":URL, "data_status":"table_transcription_indexed_publisher_pdf"})

water = ["FW","DW","1FW:1DW","2FW:1DW","1FW:2DW"]
cultivars = ["Giza 183","Giza 178","Sakha 106","Sakha 108"]

# Table 13: water-treatment and cultivar main-effect means (2022, 2023).
t13_water = {
 "K_percent":("percent", {"FW":[.47,.47],"DW":[.44,.44],"1FW:1DW":[.37,.38],"2FW:1DW":[.32,.32],"1FW:2DW":[.28,.27]}),
 "Na_percent":("percent", {"FW":[.10,.11],"DW":[.11,.12],"1FW:1DW":[.11,.12],"2FW:1DW":[.12,.16],"1FW:2DW":[.13,.16]}),
 "grain_Zn":("ppm", {"FW":[94.55,96.73],"DW":[92.68,94.85],"1FW:1DW":[76.05,78.88],"2FW:1DW":[69.51,75.47],"1FW:2DW":[68.93,72.56]}),
 "grain_Fe":("ppm", {"FW":[88.5,83.5],"DW":[94.1,87.1],"1FW:1DW":[111.5,109.4],"2FW:1DW":[124.0,124.5],"1FW:2DW":[131.8,128.8]}),
}
for metric, (unit, mapping) in t13_water.items():
    for treatment in water:
        for year, value in zip((2022,2023), mapping[treatment]):
            rows.append({"study_id":"gaber_sakha_water_quality_2022_2023","season_year":year,"cultivar":"ALL_CULTIVARS","water_quality_treatment":treatment,"metric_name":metric,"metric_value":value,"unit":unit,"table_reference":"Table 13","source_url":URL,"data_status":"table_transcription_indexed_publisher_pdf"})
t13_variety = {
 "K_percent":("percent", {"Giza 183":[.38,.38],"Giza 178":[.41,.41],"Sakha 106":[.34,.35],"Sakha 108":[.45,.44]}),
 "Na_percent":("percent", {"Giza 183":[.12,.13],"Giza 178":[.11,.13],"Sakha 106":[.12,.14],"Sakha 108":[.11,.13]}),
 "grain_Zn":("ppm", {"Giza 183":[80.20,84.92],"Giza 178":[85.19,86.06],"Sakha 106":[74.57,75.48],"Sakha 108":[85.57,90.31]}),
 "grain_Fe":("ppm", {"Giza 183":[105.39,103.17],"Giza 178":[113.00,111.94],"Sakha 106":[110.61,103.17],"Sakha 108":[109.94,108.39]}),
}
for metric, (unit, mapping) in t13_variety.items():
    for cultivar in cultivars:
        for year, value in zip((2022,2023), mapping[cultivar]):
            rows.append({"study_id":"gaber_sakha_water_quality_2022_2023","season_year":year,"cultivar":cultivar,"water_quality_treatment":"ALL_WATER_TREATMENTS","metric_name":metric,"metric_value":value,"unit":unit,"table_reference":"Table 13","source_url":URL,"data_status":"table_transcription_indexed_publisher_pdf"})

# Table 14: grain Mn, Ni, Cd and Pb by water treatment and cultivar.
t14_water = {
 "grain_Mn":("ppm", {"FW":[92.75,63.2],"DW":[95.25,115.50],"1FW:1DW":[69.33,68.17],"2FW:1DW":[64.33,64.25],"1FW:2DW":[88.67,101.25]}),
 "grain_Ni":("ppm", {"FW":[.97,1.05],"DW":[1.61,1.69],"1FW:1DW":[1.13,1.25],"2FW:1DW":[1.09,1.17],"1FW:2DW":[1.55,1.63]}),
 "grain_Cd":("ppm", {"FW":[.13,.17],"DW":[.37,.52],"1FW:1DW":[.17,.22],"2FW:1DW":[.16,.21],"1FW:2DW":[.29,.43]}),
 "grain_Pb":("ppm", {"FW":[.60,.45],"DW":[.98,1.18],"1FW:1DW":[.67,.51],"2FW:1DW":[.64,.49],"1FW:2DW":[.92,1.09]}),
}
for metric, (unit, mapping) in t14_water.items():
    for treatment in water:
        for year, value in zip((2022,2023), mapping[treatment]):
            rows.append({"study_id":"gaber_sakha_water_quality_2022_2023","season_year":year,"cultivar":"ALL_CULTIVARS","water_quality_treatment":treatment,"metric_name":metric,"metric_value":value,"unit":unit,"table_reference":"Table 14","source_url":URL,"data_status":"table_transcription_indexed_publisher_pdf"})
t14_variety = {
 "grain_Mn":("ppm", {"Giza 183":[74.56,71.00],"Giza 178":[76.61,82.44],"Sakha 106":[74.99,73.17],"Sakha 108":[81.78,101.06]}),
 "grain_Ni":("ppm", {"Giza 183":[1.39,1.47],"Giza 178":[1.18,1.26],"Sakha 106":[1.62,1.70],"Sakha 108":[.95,1.06]}),
 "grain_Cd":("ppm", {"Giza 183":[.26,.36],"Giza 178":[.19,.29],"Sakha 106":[.25,.35],"Sakha 108":[.18,.28]}),
 "grain_Pb":("ppm", {"Giza 183":[.74,.81],"Giza 178":[.71,.74],"Sakha 106":[.82,.86],"Sakha 108":[.70,.73]}),
}
for metric, (unit, mapping) in t14_variety.items():
    for cultivar in cultivars:
        for year, value in zip((2022,2023), mapping[cultivar]):
            rows.append({"study_id":"gaber_sakha_water_quality_2022_2023","season_year":year,"cultivar":cultivar,"water_quality_treatment":"ALL_WATER_TREATMENTS","metric_name":metric,"metric_value":value,"unit":unit,"table_reference":"Table 14","source_url":URL,"data_status":"table_transcription_indexed_publisher_pdf"})

with CSV_PATH.open(encoding="utf-8-sig", newline="") as f:
    old = list(csv.DictReader(f))
existing_keys = {(r["season_year"],r["cultivar"],r["water_quality_treatment"],r["metric_name"],r["table_reference"]) for r in old}
new = [r for r in rows if (str(r["season_year"]),r["cultivar"],r["water_quality_treatment"],r["metric_name"],r["table_reference"]) not in existing_keys]
with CSV_PATH.open("w",encoding="utf-8-sig",newline="") as f:
    w=csv.DictWriter(f,fieldnames=FIELDS); w.writeheader(); w.writerows(old+new)
print(f"Added {len(new)} rows; total {len(old)+len(new)}")
