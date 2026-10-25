"""Import a neighboring-Delta rice rotation trial as regional, non-KFS evidence."""
from __future__ import annotations

import csv
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / "database" / "agriwater_v2.sqlite"
OUT = ROOT / "data" / "processed" / "delta_rice_previous_crop_nutrients_2000_2001.csv"
URL = "https://jpp.journals.ekb.eg/article_257186_9c13162afbfa131f3df085f05509a5d2.pdf"
STUDY_ID = "IBRAHIM_TAG_ELEZZ_RICE_PREVIOUS_CROP_2000_2001"


def make_rows():
    rows = []

    def add(year, crop, metric, value, unit, table, period):
        rows.append({
            "study_id": STUDY_ID, "study_year": year, "observation_period": period,
            "preceding_crop": crop, "puddling": None, "depth_top_cm": None,
            "depth_bottom_cm": None, "metric_name": metric, "metric_value": value,
            "unit": unit, "aggregation_level": "published_experimental_factor_mean",
            "replicate_count": 4, "source_locator": table,
            "data_status": "PUBLISHED_NEIGHBORING_DELTA_TRIAL_NOT_KFS_FIELD_PREDICTION",
            "source_url": URL,
        })

    soil = {
        2000: {"berseem": {"available_nitrogen": 54.7, "available_phosphorus": 9.6,
                            "exchangeable_potassium": 329.1, "ph": 7.6},
               "wheat": {"available_nitrogen": 31.9, "available_phosphorus": 13.4,
                         "exchangeable_potassium": 402.3, "ph": 8.1}},
        2001: {"berseem": {"available_nitrogen": 59.7, "available_phosphorus": 10.3,
                            "exchangeable_potassium": 343.0, "ph": 7.5},
               "wheat": {"available_nitrogen": 34.9, "available_phosphorus": 16.1,
                         "exchangeable_potassium": 423.1, "ph": 7.7}},
    }
    units = {"available_nitrogen": "mg/kg", "available_phosphorus": "mg/kg",
             "exchangeable_potassium": "mg/kg", "ph": "pH"}
    for year, crops in soil.items():
        for crop, metrics in crops.items():
            for metric, value in metrics.items():
                add(year, crop, metric, value, units[metric], "Table 7; soil after preceding winter crop", "after_preceding_crop_before_rice")

    yields = {
        2000: {"berseem": 4.274, "wheat": 3.776},
        2001: {"berseem": 4.618, "wheat": 4.161},
    }
    for year, crops in yields.items():
        for crop, value in crops.items():
            add(year, crop, "rice_grain_yield", value, "ton/feddan",
                "Results text; average yield by preceding winter crop", "rice_harvest")
    return rows


def main():
    records = make_rows()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    backup = DB.with_name(f"{DB.stem}_before_delta_rotation_import_{datetime.now():%Y%m%d_%H%M%S}{DB.suffix}")
    shutil.copy2(DB, backup)
    con = sqlite3.connect(DB)
    try:
        con.execute("PRAGMA foreign_keys=ON")
        con.execute("BEGIN IMMEDIATE")
        con.execute("DELETE FROM literature_trial_observation WHERE study_id=?", (STUDY_ID,))
        con.execute("DELETE FROM literature_evidence WHERE study_id=?", (STUDY_ID,))
        con.execute("""INSERT OR IGNORE INTO literature_study(
            study_id,title,authors,publication_year,source_url,location_name,methods_summary,
            limitations,data_status) VALUES(?,?,?,?,?,?,?,?,?)""", (
            STUDY_ID,
            "Effect of preceding winter crops and biological fertilization on growth and yield of rice under different levels of nitrogen fertilization",
            "E. M. Ibrahim", 2002, URL, "Tag El-Ezz Agricultural Research Station, Dakahlia Governorate (neighboring Delta; not Kafr El-Sheikh)",
            "Sakha 101 rice; summers 2000 and 2001; berseem vs wheat preceding crop; nitrogen and Cyriallen treatments; four replications.",
            "Not conducted in Kafr El-Sheikh; older station experiment; treatment means cannot be transferred as current field-specific soil tests or fertilizer doses.",
            "PUBLISHED_NEIGHBORING_DELTA_RICE_ROTATION_TRIAL"))
        con.executemany("""INSERT INTO literature_trial_observation(
            study_id,study_year,observation_period,preceding_crop,puddling,depth_top_cm,
            depth_bottom_cm,metric_name,metric_value,unit,aggregation_level,replicate_count,
            source_locator,data_status,source_url)
            VALUES(:study_id,:study_year,:observation_period,:preceding_crop,:puddling,
            :depth_top_cm,:depth_bottom_cm,:metric_name,:metric_value,:unit,:aggregation_level,
            :replicate_count,:source_locator,:data_status,:source_url)""", records)
        con.execute("""INSERT INTO literature_evidence(
            study_id,crop_of_interest,factor_name,factor_level,outcome,result_summary,
            statistical_result,study_context,source_locator,data_status,source_url)
            VALUES(?,?,?,?,?,?,?,?,?,?,?)""", (
            STUDY_ID, "rice", "preceding_winter_crop", "Egyptian clover (berseem) vs wheat",
            "pre-rice soil available N/P/K and rice grain yield",
            "In this trial, pre-rice available soil N was higher after berseem, while available P and exchangeable K were lower than after wheat; mean rice yield was higher after berseem in both seasons.",
            "The study reports significant preceding-crop effects on rice yield traits; response also depended on nitrogen and biological fertilizer treatments. This is experiment-specific, not a universal nutrient-credit rule.",
            "Tag El-Ezz station in Dakahlia, outside the target governorate; Sakha 101; two seasons; four replications.",
            "Abstract; results text; Table 7", "PUBLISHED_NEIGHBORING_DELTA_EVIDENCE_ONLY", URL))
        con.execute("""INSERT OR IGNORE INTO data_source(name,url,notes) VALUES(?,?,?)""", (
            "Ibrahim 2002 rice after berseem or wheat, Tag El-Ezz station",
            URL,
            "Neighboring Delta research, not Kafr El-Sheikh; includes soil N/P/K after prior crop and rice response; stored only as regional evidence."))
        con.execute("INSERT OR REPLACE INTO database_metadata(item,details) VALUES(?,?)", (
            "tag_el_ezz_previous_crop_trial",
            f"Imported {len(records)} published treatment-factor means from Dakahlia station experiment, 2000-2001; comparator evidence only, not Kafr El-Sheikh parcel values."))
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
    print(f"backup={backup}")
    print(f"imported_observations={len(records)}; csv={OUT}")


if __name__ == "__main__":
    main()
