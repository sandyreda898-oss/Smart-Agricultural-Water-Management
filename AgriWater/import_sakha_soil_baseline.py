"""Import published pre-plant soil baselines from rice trials at Sakha, Kafr El-Sheikh."""
from __future__ import annotations

import csv
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / "database" / "agriwater_v2.sqlite"
OUT = ROOT / "data" / "processed" / "sakha_rice_soil_baseline_2016_2017.csv"
URL = "https://jssae.journals.ekb.eg/article_35762_34ca5e21488d038f6d7de5b2469c83b6.pdf"
STUDY_ID = "GEWAILY_SAKHA_RICE_SOIL_BASELINE_2016_2017"

VALUES = {
    "clay": (55.7, 55.3, "%", "Table 1; particle-size distribution"),
    "silt": (31.7, 32.3, "%", "Table 1; particle-size distribution"),
    "sand": (12.6, 12.4, "%", "Table 1; particle-size distribution"),
    "ph": (8.25, 8.15, "pH", "Table 1; 1:2.5 soil suspension"),
    "ec": (2.30, 2.55, "dS/m", "Table 1; soil paste extract"),
    "organic_matter": (1.60, 1.51, "%", "Table 1"),
    "total_nitrogen": (0.0065, 0.0052, "%", "Table 1; value/unit transcribed as published"),
    "available_phosphorus": (12.8, 11.2, "mg/kg", "Table 1; available P"),
    "available_potassium": (340, 360, "mg/kg", "Table 1; available K"),
    "available_zinc": (0.40, 0.58, "mg/kg", "Table 1; available Zn"),
}


def main():
    records = []
    for metric, (v2016, v2017, unit, locator) in VALUES.items():
        for year, value in ((2016, v2016), (2017, v2017)):
            records.append({
                "study_id": STUDY_ID, "study_year": year, "observation_period": "before_rice",
                "preceding_crop": None, "puddling": None,
                "depth_top_cm": None, "depth_bottom_cm": None,
                "metric_name": metric, "metric_value": value, "unit": unit,
                "aggregation_level": "published_experimental_site_baseline",
                "replicate_count": None, "source_locator": locator,
                "data_status": "PUBLISHED_SAKHA_STATION_BASELINE_NOT_FIELD_ESTIMATE",
                "source_url": URL,
            })
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)

    backup = DB.with_name(f"{DB.stem}_before_sakha_soil_import_{datetime.now():%Y%m%d_%H%M%S}{DB.suffix}")
    shutil.copy2(DB, backup)
    con = sqlite3.connect(DB)
    try:
        con.execute("PRAGMA foreign_keys=ON")
        con.execute("BEGIN IMMEDIATE")
        con.execute("""CREATE TABLE IF NOT EXISTS literature_trial_observation (
            observation_id INTEGER PRIMARY KEY, study_id TEXT NOT NULL REFERENCES literature_study(study_id),
            study_year INTEGER, observation_period TEXT NOT NULL, preceding_crop TEXT,
            puddling TEXT, depth_top_cm REAL, depth_bottom_cm REAL,
            metric_name TEXT NOT NULL, metric_value REAL NOT NULL, unit TEXT NOT NULL,
            aggregation_level TEXT NOT NULL, replicate_count INTEGER,
            source_locator TEXT NOT NULL, data_status TEXT NOT NULL, source_url TEXT NOT NULL)""")
        con.execute("""INSERT OR IGNORE INTO literature_study(
            study_id,title,authors,publication_year,source_url,location_name,methods_summary,
            limitations,data_status) VALUES(?,?,?,?,?,?,?,?,?)""", (
            STUDY_ID,
            "Effects of Soil Fertilization on Sakha 105 Rice Cultivar Productivity, NPK Uptake and Soil Nutrient",
            "E. E. Gewaily; A. M. Ghoneim; Howida B. I. Elhabet", 2018, URL,
            "Rice Research and Training Center experimental farm, Sakha, Kafr El-Sheikh",
            "Published pre-plant soil baseline for 2016 and 2017 rice fertilizer trials.",
            "One station/site; no parcel-specific sampling coordinates or sampling depth reported in the table; baseline values are not a current farmer soil test and do not establish nutrient sufficiency thresholds.",
            "PUBLISHED_SAKHA_STATION_SOIL_BASELINE"))
        con.execute("DELETE FROM literature_trial_observation WHERE study_id=?", (STUDY_ID,))
        con.executemany("""INSERT INTO literature_trial_observation(
            study_id,study_year,observation_period,preceding_crop,puddling,depth_top_cm,
            depth_bottom_cm,metric_name,metric_value,unit,aggregation_level,replicate_count,
            source_locator,data_status,source_url)
            VALUES (:study_id,:study_year,:observation_period,:preceding_crop,:puddling,
            :depth_top_cm,:depth_bottom_cm,:metric_name,:metric_value,:unit,:aggregation_level,
            :replicate_count,:source_locator,:data_status,:source_url)""", records)
        con.execute("""INSERT OR IGNORE INTO literature_study(
            study_id,title,authors,publication_year,source_url,location_name,methods_summary,
            limitations,data_status) VALUES(?,?,?,?,?,?,?,?,?)""", (
            STUDY_ID,
            "Effects of Soil Fertilization on Sakha 105 Rice Cultivar Productivity, NPK Uptake and Soil Nutrient",
            "E. E. Gewaily; A. M. Ghoneim; Howida B. I. Elhabet", 2018, URL,
            "Rice Research and Training Center experimental farm, Sakha, Kafr El-Sheikh",
            "Published pre-plant soil baseline for 2016 and 2017 rice fertilizer trials; four experimental replicates.",
            "One station/site; no parcel-specific sampling coordinates or sampling depth reported in the table; baseline values are not a current farmer soil test and do not establish nutrient sufficiency thresholds.",
            "PUBLISHED_SAKHA_STATION_SOIL_BASELINE"))
        con.execute("""INSERT OR IGNORE INTO data_source(name,url,notes) VALUES(?,?,?)""", (
            "Gewaily et al. 2018 Sakha rice soil nutrient baseline", URL,
            "Published soil baseline from RRTC Sakha trials, 2016–2017; reference observations only, not parcel predictions."))
        con.execute("INSERT OR REPLACE INTO database_metadata(item,details) VALUES(?,?)", (
            "sakha_soil_baseline_2016_2017",
            f"Imported {len(records)} published soil property/nutrient values from Sakha RRTC site; not field-specific."))
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
    print(f"backup={backup}")
    print(f"imported_observations={len(records)}")
    print(f"csv={OUT}")


if __name__ == "__main__":
    main()
