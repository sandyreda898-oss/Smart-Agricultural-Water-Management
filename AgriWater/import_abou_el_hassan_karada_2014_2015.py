"""Import numeric Table 8 treatment means from Abou El Hassan (2017), El-Karada."""
import csv
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / "database" / "agriwater_v2.sqlite"
OUT = ROOT / "data" / "processed" / "abou_el_hassan_karada_water_deficit_2014_2015.csv"
URL = "https://jssae.journals.ekb.eg/article_37229_e5bf0274832efce6190833e3b1117c5b.pdf"
STUDY = "ABOU_EL_HASSAN_KARADA_WATER_DEFICIT_2014_2015"

# Table 8, water-withholding treatment means. The paper reports area-normalized
# seasonal irrigation in m3/ha and yield in t/ha. Dashes for CF are not zeros.
TABLE = {
    "CF": {
        2014: {"total_water_applied": 14611, "grain_yield": 11.68, "water_use_efficiency": 0.799},
        2015: {"total_water_applied": 14842, "grain_yield": 11.85, "water_use_efficiency": 0.798},
    },
    "W_MT": {
        2014: {"total_water_applied": 13686, "grain_yield": 11.08, "yield_reduction": 5.14, "water_saved": 6.33, "water_use_efficiency": 0.810},
        2015: {"total_water_applied": 13841, "grain_yield": 11.34, "yield_reduction": 4.30, "water_saved": 6.74, "water_use_efficiency": 0.819},
    },
    "W_PI": {
        2014: {"total_water_applied": 13469, "grain_yield": 10.35, "yield_reduction": 11.39, "water_saved": 7.82, "water_use_efficiency": 0.768},
        2015: {"total_water_applied": 13636, "grain_yield": 10.38, "yield_reduction": 12.41, "water_saved": 8.13, "water_use_efficiency": 0.761},
    },
    "W_H": {
        2014: {"total_water_applied": 13956, "grain_yield": 10.61, "yield_reduction": 9.16, "water_saved": 4.48, "water_use_efficiency": 0.760},
        2015: {"total_water_applied": 14141, "grain_yield": 10.84, "yield_reduction": 8.52, "water_saved": 4.72, "water_use_efficiency": 0.767},
    },
}
PERIODS = {"CF": "continuous_flooding", "W_MT": "withhold_12_days_mid_tillering", "W_PI": "withhold_12_days_panicle_initiation", "W_H": "withhold_12_days_heading"}
UNITS = {"total_water_applied": "m3/ha", "grain_yield": "t/ha", "yield_reduction": "%", "water_saved": "%", "water_use_efficiency": "kg/m3"}


def main():
    rows = []
    for treatment, years in TABLE.items():
        for year, metrics in years.items():
            for metric, value in metrics.items():
                rows.append({
                    "study_id": STUDY, "study_year": year, "observation_period": PERIODS[treatment],
                    "preceding_crop": None, "puddling": None, "depth_top_cm": None, "depth_bottom_cm": None,
                    "metric_name": metric, "metric_value": value, "unit": UNITS[metric],
                    "aggregation_level": "water-withholding treatment mean; experiment includes three rice cultivars; cultivar-specific estimates not represented by Table 8",
                    "replicate_count": None, "source_locator": "Table 8",
                    "data_status": "PUBLISHED_EL_KARADA_STATION_TREATMENT_MEAN_NOT_FARM_LABEL", "source_url": URL,
                })
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    backup = DB.with_name(f"{DB.stem}_before_abou_el_hassan_import_{datetime.now():%Y%m%d_%H%M%S}{DB.suffix}")
    shutil.copy2(DB, backup)
    con = sqlite3.connect(DB)
    con.execute("PRAGMA foreign_keys=ON")
    try:
        con.execute("BEGIN IMMEDIATE")
        con.execute("INSERT INTO data_source(name,url,notes) VALUES(?,?,?) ON CONFLICT(name) DO UPDATE SET url=excluded.url,notes=excluded.notes",
                    ("Abou El Hassan (2017), El-Karada rice water-deficit trial", URL, "Table 8 seasonal water, yield, yield reduction, water saving and WUE means; 2014 and 2015."))
        con.execute("INSERT INTO literature_study(study_id,title,authors,publication_year,doi,source_url,location_name,latitude,longitude,methods_summary,limitations,data_status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(study_id) DO UPDATE SET title=excluded.title,authors=excluded.authors,publication_year=excluded.publication_year,doi=excluded.doi,source_url=excluded.source_url,location_name=excluded.location_name,latitude=excluded.latitude,longitude=excluded.longitude,methods_summary=excluded.methods_summary,limitations=excluded.limitations,data_status=excluded.data_status",
                    (STUDY, "Effect of Water Deficit at Critical Physiological Stages of Rice on WUE and Productivity", "W. H. Abou El Hassan", 2017, "10.21608/jssae.2017.37229", URL, "El-Karada Research Station, Kafr El-Sheikh", None, None,
                     "Field experiment in the 2014 and 2015 summer seasons; continuous flooding compared with 12-day water withholding at mid-tillering, panicle initiation, or heading. Table 8 reports seasonal treatment means.",
                     "Station treatment means, not farm records. Table 8 values are irrigation-treatment means across three cultivars; they cannot estimate a specific parcel, cultivar, or pump runtime. The table reports water saving 6.33% for 2014 W_MT; the abstract prints 6.37%, so the table value is retained and the discrepancy is documented.",
                     "PUBLISHED_PRIMARY_RESEARCH_STATION_TRIAL"))
        con.execute("DELETE FROM literature_trial_observation WHERE study_id=?", (STUDY,))
        con.executemany("INSERT INTO literature_trial_observation(study_id,study_year,observation_period,preceding_crop,puddling,depth_top_cm,depth_bottom_cm,metric_name,metric_value,unit,aggregation_level,replicate_count,source_locator,data_status,source_url) VALUES(:study_id,:study_year,:observation_period,:preceding_crop,:puddling,:depth_top_cm,:depth_bottom_cm,:metric_name,:metric_value,:unit,:aggregation_level,:replicate_count,:source_locator,:data_status,:source_url)", rows)
        con.execute("INSERT OR REPLACE INTO database_metadata(item,details) VALUES(?,?)", ("abou_el_hassan_karada_2014_2015", f"Imported {len(rows)} Table 8 treatment means for 2014-2015. Table/abstract discrepancy retained: 2014 W_MT water saving is 6.33% in Table 8 and 6.37% in abstract. Source {URL}"))
        assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert not con.execute("PRAGMA foreign_key_check").fetchall()
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
    print(f"Imported {len(rows)} observations; backup: {backup}")


if __name__ == "__main__":
    main()
