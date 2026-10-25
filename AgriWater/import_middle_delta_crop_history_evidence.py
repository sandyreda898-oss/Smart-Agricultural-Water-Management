"""Import published categorical evidence about rice history and soil salinity near Sakha."""
from __future__ import annotations

import csv
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / "database" / "agriwater_v2.sqlite"
OUT = ROOT / "data" / "processed" / "middle_delta_previous_rice_history_evidence.csv"
URL = "https://www.jstage.jst.go.jp/article/jdsa/8/2/8_119/_pdf/-char/en"
STUDY_ID = "YAGETA_SAKHA_PREVIOUS_RICE_SALINITY_2010"
ROW = {
    "study_id": STUDY_ID,
    "crop_of_interest": "soil salinity in rice-growing fields",
    "factor_name": "previous_rice_cultivation_count_in_prior_two_years",
    "factor_level": "0, 1, or 2 rice seasons in 2008-2009",
    "outcome": "surface-soil salinity, exchangeable sodium, and soil properties",
    "result_summary": "Across 15 sites (one ARC site and 14 nearby private farms), previous-rice frequency had little/no statistically significant effect on surface-soil salt accumulation. Area, subsurface-drainage condition, and irrigation-water quality were more important in these sites.",
    "statistical_result": "No significant group differences by previous-rice frequency; significant differences were reported by area and drainage for some salt indicators.",
    "study_context": "Middle Nile Delta sites within 5 km of Sakha RRTC; soil sampled at 0-20 cm in May 2010; 15 farms/sites; grouped categories based on two-year rice history.",
    "source_locator": "Abstract; Methods sections 2.1-2.3; Results 3.1-3.3; Table 3",
    "data_status": "PUBLISHED_NEAR_SAKHA_OBSERVATIONAL_EVIDENCE_NOT_FIELD_PREDICTION",
    "source_url": URL,
}


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(ROW))
        w.writeheader()
        w.writerow(ROW)
    backup = DB.with_name(f"{DB.stem}_before_middle_delta_evidence_{datetime.now():%Y%m%d_%H%M%S}{DB.suffix}")
    shutil.copy2(DB, backup)
    con = sqlite3.connect(DB)
    try:
        con.execute("PRAGMA foreign_keys=ON")
        con.execute("BEGIN IMMEDIATE")
        con.execute("""CREATE TABLE IF NOT EXISTS literature_evidence (
            evidence_id INTEGER PRIMARY KEY, study_id TEXT NOT NULL REFERENCES literature_study(study_id),
            crop_of_interest TEXT, factor_name TEXT NOT NULL, factor_level TEXT,
            outcome TEXT NOT NULL, result_summary TEXT NOT NULL,
            statistical_result TEXT, study_context TEXT, source_locator TEXT,
            data_status TEXT NOT NULL, source_url TEXT NOT NULL)""")
        con.execute("DELETE FROM literature_evidence WHERE study_id=?", (STUDY_ID,))
        con.execute("""INSERT OR IGNORE INTO literature_study(
            study_id,title,authors,publication_year,doi,source_url,location_name,latitude,longitude,
            methods_summary,limitations,data_status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""", (
            STUDY_ID,
            "Effects of Previous Rice Cropping History on Salt Accumulation of Surface Soils in the Middle Nile Delta, Egypt",
            "Y. Yageta; T. Higashi; Z. A. Bassiouni; N. El Sayed Saad; M. Satoh",
            2013, "10.11178/jdsa.8.119", URL,
            "15 study sites within 5 km of the Rice Research and Training Center, Sakha, Kafr El-Sheikh",
            31.091944, 30.933417,
            "Soil and irrigation-water samples from one ARC site and 14 nearby private farms; sites grouped by rice cultivation frequency during the two preceding years; soil sampled at 0-20 cm in May 2010.",
            "Small observational study from 2010 with grouped site comparisons; no public parcel-level coordinates or farmer-level raw table. The result is specific to the sampled area and drainage/water conditions.",
            "PUBLISHED_NEAR_SAKHA_OBSERVATIONAL_EVIDENCE"))
        con.execute("""INSERT INTO literature_evidence(
            study_id,crop_of_interest,factor_name,factor_level,outcome,result_summary,
            statistical_result,study_context,source_locator,data_status,source_url)
            VALUES(:study_id,:crop_of_interest,:factor_name,:factor_level,:outcome,:result_summary,
            :statistical_result,:study_context,:source_locator,:data_status,:source_url)""", ROW)
        con.execute("""INSERT OR IGNORE INTO data_source(name,url,notes) VALUES(?,?,?)""", (
            "Yageta et al. 2013 previous rice history and salinity near Sakha",
            URL,
            "15-site observational study: history of rice in the prior two years was not a significant salt-accumulation factor in the sample; site area, drainage and irrigation-water quality mattered."))
        con.execute("INSERT OR REPLACE INTO database_metadata(item,details) VALUES(?,?)", (
            "sakha_previous_rice_history_evidence",
            "One published 15-site study-level evidence record from near Sakha; not farmer field predictions or plot-level labels."))
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
    print(f"backup={backup}")
    print(f"imported_evidence=1; csv={OUT}")


if __name__ == "__main__":
    main()
