"""Import published Kafr El-Sheikh rice/previous-crop soil trial summaries.

Values are transcribed from the cited 2007 field experiment and must not be
treated as measurements of a farmer's parcel.
"""
from __future__ import annotations

import csv
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / "database" / "agriwater_v2.sqlite"
OUT = ROOT / "data" / "processed" / "kfs_rice_previous_crop_soil_trial_2007.csv"
URL = "https://journals.ekb.eg/article_50545_e9df9407d8656f4a38c6bfeeb8122da7.pdf"
STUDY_ID = "ELHENAWY_KFS_RICE_PREVIOUS_CROP_2007"


def rows():
    out = []

    def add(period, prev, puddling, top, bottom, metric, value, unit, table, aggregation="treatment_mean"):
        out.append({
            "study_id": STUDY_ID, "study_year": 2007, "observation_period": period,
            "preceding_crop": prev, "puddling": puddling, "depth_top_cm": top,
            "depth_bottom_cm": bottom, "metric_name": metric, "metric_value": value,
            "unit": unit, "aggregation_level": aggregation, "replicate_count": 3,
            "source_locator": table, "data_status": "PUBLISHED_EXPERIMENT_SUMMARY_NOT_FIELD_PREDICTION",
            "source_url": URL,
        })

    # Table 1: soil before the rice experiment, as grouped by the preceding crop.
    baseline = {
        "wheat": {
            "ec_dsm": ([0.412, 0.593, 0.503], "dS/m", "EC 1:5"),
            "ph": ([8.37, 8.48, None], "pH", "pH 1:2.5"),
            "bulk_density": ([1.127, 1.260, 1.194], "Mg/m3", "bulk density"),
            "sand": ([22.6, 20.5, 21.5], "%", "particle-size distribution"),
            "silt": ([27.7, 25.9, 26.8], "%", "particle-size distribution"),
            "clay": ([49.7, 53.6, 51.7], "%", "particle-size distribution"),
            "mean_weight_diameter": ([0.541, 0.416, 0.479], "mm", "mean weight diameter"),
        },
        "berseem": {
            "ec_dsm": ([0.532, 0.659, 0.596], "dS/m", "EC 1:5"),
            "ph": ([8.12, 8.26, None], "pH", "pH 1:2.5"),
            "bulk_density": ([1.107, 1.142, 1.125], "Mg/m3", "bulk density"),
            "sand": ([22.4, 20.9, 21.7], "%", "particle-size distribution"),
            "silt": ([26.2, 25.4, 25.8], "%", "particle-size distribution"),
            "clay": ([51.4, 53.7, 52.5], "%", "particle-size distribution"),
            "mean_weight_diameter": ([0.753, 0.582, 0.668], "mm", "mean weight diameter"),
        },
    }
    for crop, metrics in baseline.items():
        for metric, (vals, unit, locator) in metrics.items():
            for depth, value in zip(((0, 30), (30, 60), (None, None)), vals):
                if value is not None:
                    add("before_rice", crop, None, *depth, metric, value, unit, f"Table 1; {locator}",
                        "published_depth_or_crop_mean")

    # Table 2: soil salinity and pH by previous crop, puddling, and depth.
    t2 = {
        "ec_dsm": ("dS/m", {
            ("wheat", "with", 0, 30): .482, ("wheat", "without", 0, 30): .407,
            ("berseem", "with", 0, 30): .572, ("berseem", "without", 0, 30): .467,
            ("wheat", "with", 30, 60): .529, ("wheat", "without", 30, 60): .509,
            ("berseem", "with", 30, 60): .747, ("berseem", "without", 30, 60): .474,
        }),
        "ph": ("pH", {
            ("wheat", "with", 0, 30): 7.55, ("wheat", "without", 0, 30): 7.74,
            ("berseem", "with", 0, 30): 7.72, ("berseem", "without", 0, 30): 7.74,
            ("wheat", "with", 30, 60): 7.70, ("wheat", "without", 30, 60): 7.82,
            ("berseem", "with", 30, 60): 7.88, ("berseem", "without", 30, 60): 7.90,
        }),
    }
    for metric, (unit, values) in t2.items():
        for (crop, puddling, top, bottom), value in values.items():
            add("after_rice", crop, puddling, top, bottom, metric, value, unit, "Table 2")

    # Table 3: bulk density (depth-specific), infiltration rate and saturated conductivity.
    t3 = {
        "bulk_density": ("Mg/m3", {
            ("wheat", "with", 0, 30): 1.286, ("wheat", "without", 0, 30): 1.167,
            ("berseem", "with", 0, 30): 1.234, ("berseem", "without", 0, 30): 1.112,
            ("wheat", "with", 30, 60): 1.312, ("wheat", "without", 30, 60): 1.258,
            ("berseem", "with", 30, 60): 1.286, ("berseem", "without", 30, 60): 1.183,
        }),
        "infiltration_rate": ("cm/hour", {
            ("wheat", "with"): 2.0, ("wheat", "without"): 2.4,
            ("berseem", "with"): 2.2, ("berseem", "without"): 2.8,
        }),
        "saturated_hydraulic_conductivity": ("cm/day", {
            ("wheat", "with"): 12.7, ("wheat", "without"): 13.9,
            ("berseem", "with"): 14.0, ("berseem", "without"): 15.0,
        }),
    }
    for metric, (unit, values) in t3.items():
        for key, value in values.items():
            crop, puddling, *depth = key
            top, bottom = depth if depth else (None, None)
            add("after_rice", crop, puddling, top, bottom, metric, value, unit, "Table 3")

    # Table 4 aggregate stability: factor-cell means, not individual plots.
    t4 = {
        "water_stable_aggregates_gt_0_25mm": ("%", {
            ("wheat", "with", 0, 30): 57.09, ("wheat", "without", 0, 30): 53.81,
            ("berseem", "with", 0, 30): 60.31, ("berseem", "without", 0, 30): 64.89,
            ("wheat", "with", 30, 60): 50.88, ("wheat", "without", 30, 60): 49.71,
            ("berseem", "with", 30, 60): 53.96, ("berseem", "without", 30, 60): 55.72,
        }),
        "optimum_aggregate_size": ("%", {
            ("wheat", "with", 0, 30): 44.59, ("wheat", "without", 0, 30): 47.42,
            ("berseem", "with", 0, 30): 49.89, ("berseem", "without", 0, 30): 54.44,
            ("wheat", "with", 30, 60): 33.61, ("wheat", "without", 30, 60): 40.10,
            ("berseem", "with", 30, 60): 42.31, ("berseem", "without", 30, 60): 45.96,
        }),
        "mean_weight_diameter": ("mm", {
            ("wheat", "with", 0, 30): .53, ("wheat", "without", 0, 30): .48,
            ("berseem", "with", 0, 30): .63, ("berseem", "without", 0, 30): .72,
            ("wheat", "with", 30, 60): .35, ("wheat", "without", 30, 60): .42,
            ("berseem", "with", 30, 60): .47, ("berseem", "without", 30, 60): .53,
        }),
    }
    for metric, (unit, values) in t4.items():
        for (crop, puddling, top, bottom), value in values.items():
            add("after_rice", crop, puddling, top, bottom, metric, value, unit, "Table 4")

    # Table 5 rice outcomes. The paper says treatment effects were not statistically significant.
    for crop, with_p, without_p, mean in (("wheat", 4.793, 4.850, 4.821),
                                           ("berseem", 4.905, 4.929, 4.917)):
        for puddling, value in (("with", with_p), ("without", without_p)):
            add("rice_harvest", crop, puddling, None, None, "grain_yield", value,
                "Mg/ha", "Table 5; yield treatment mean")
        add("rice_harvest", crop, None, None, None, "grain_yield", mean,
            "Mg/ha", "Table 5; preceding-crop mean", "published_crop_mean")
    for puddling, value in (("with", 4.850), ("without", 4.888)):
        add("rice_harvest", None, puddling, None, None, "grain_yield", value,
            "Mg/ha", "Table 5; puddling mean", "published_factor_mean")

    return out


def main():
    records = rows()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(records[0]))
        w.writeheader()
        w.writerows(records)

    backup = DB.with_name(f"{DB.stem}_before_kfs_trial_import_{datetime.now():%Y%m%d_%H%M%S}{DB.suffix}")
    shutil.copy2(DB, backup)
    con = sqlite3.connect(DB)
    try:
        con.execute("PRAGMA foreign_keys=ON")
        con.execute("BEGIN IMMEDIATE")
        con.execute("""CREATE TABLE IF NOT EXISTS literature_trial_observation (
            observation_id INTEGER PRIMARY KEY,
            study_id TEXT NOT NULL REFERENCES literature_study(study_id),
            study_year INTEGER,
            observation_period TEXT NOT NULL,
            preceding_crop TEXT,
            puddling TEXT,
            depth_top_cm REAL,
            depth_bottom_cm REAL,
            metric_name TEXT NOT NULL,
            metric_value REAL NOT NULL,
            unit TEXT NOT NULL,
            aggregation_level TEXT NOT NULL,
            replicate_count INTEGER,
            source_locator TEXT NOT NULL,
            data_status TEXT NOT NULL,
            source_url TEXT NOT NULL
        )""")
        con.execute("""CREATE TABLE IF NOT EXISTS literature_evidence (
            evidence_id INTEGER PRIMARY KEY, study_id TEXT NOT NULL REFERENCES literature_study(study_id),
            crop_of_interest TEXT, factor_name TEXT NOT NULL, factor_level TEXT,
            outcome TEXT NOT NULL, result_summary TEXT NOT NULL,
            statistical_result TEXT, study_context TEXT, source_locator TEXT,
            data_status TEXT NOT NULL, source_url TEXT NOT NULL
        )""")
        con.execute("DELETE FROM literature_trial_observation WHERE study_id=?", (STUDY_ID,))
        con.execute("DELETE FROM literature_evidence WHERE study_id=?", (STUDY_ID,))
        con.execute("""INSERT OR IGNORE INTO literature_study(
            study_id,title,authors,publication_year,doi,source_url,location_name,latitude,longitude,
            methods_summary,limitations,data_status)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""", (
            STUDY_ID,
            "Effect of soil puddling and previous crop on some soil properties and rice productivity in clay soils",
            "A. S. El-Henawy", 2013, "10.21608/jssae.2014.50545", URL,
            "Faculty of Agriculture farm, Kafrelsheikh University; experiment season 2007",
            31.116667, 30.866667,
            "Four fields; Giza 177 rice; preceding crops wheat or Egyptian clover; puddling vs no puddling; three replicates; soil sampled at 0-30 and 30-60 cm.",
            "Single research-farm site and one season; grouped treatment means rather than plot-level records; not a field-specific soil test or current universal recommendation.",
            "PUBLISHED_LOCAL_EXPERIMENT_SUMMARIES"))
        con.executemany("""INSERT INTO literature_trial_observation(
            study_id,study_year,observation_period,preceding_crop,puddling,depth_top_cm,
            depth_bottom_cm,metric_name,metric_value,unit,aggregation_level,replicate_count,
            source_locator,data_status,source_url)
            VALUES (:study_id,:study_year,:observation_period,:preceding_crop,:puddling,
            :depth_top_cm,:depth_bottom_cm,:metric_name,:metric_value,:unit,:aggregation_level,
            :replicate_count,:source_locator,:data_status,:source_url)""", records)
        con.execute("""INSERT OR IGNORE INTO data_source(name,url,notes)
            VALUES(?,?,?)""", (
            "El-Henawy 2013 Kafr El-Sheikh rice previous-crop and soil trial", URL,
            "Open journal PDF. Experimental means from Kafrelsheikh University farm, season 2007. Stored in literature_trial_observation; not a farmer-field prediction."))
        con.executemany("""INSERT INTO literature_evidence(
            study_id,crop_of_interest,factor_name,factor_level,outcome,result_summary,
            statistical_result,study_context,source_locator,data_status,source_url)
            VALUES(?,?,?,?,?,?,?,?,?,?,?)""", [
            (STUDY_ID, "rice", "preceding_crop", "Egyptian clover vs wheat",
             "soil physical/chemical properties and rice yield",
             "The study reports differences in several soil properties by preceding crop; rice yield was numerically highest after clover without puddling.",
             "Rice yield and yield components were reported as not statistically significantly affected by preceding crop, puddling, or their interaction in this experiment.",
             "Giza 177; one Kafrelsheikh University farm; 2007 summer; three replicates; clay soil; surface and subsurface layers.",
             "Abstract and Table 5", "PUBLISHED_LOCAL_EXPERIMENT_EVIDENCE_ONLY", URL),
            (STUDY_ID, "rice", "puddling", "puddled vs not puddled",
             "soil salinity, bulk density, infiltration, hydraulic conductivity and yield",
             "Puddling increased EC and bulk density in reported comparisons; no-puddling had the highest numeric yield in the clover sequence.",
             "Treatment differences in rice yield were reported as not statistically significant; results are specific to this trial.",
             "Giza 177; one Kafrelsheikh University farm; 2007 summer; three replicates; clay soil.",
             "Abstract; Tables 2, 3 and 5", "PUBLISHED_LOCAL_EXPERIMENT_EVIDENCE_ONLY", URL),
        ])
        con.execute("INSERT OR REPLACE INTO database_metadata(item,details) VALUES(?,?)", (
            "kfs_previous_crop_soil_trial",
            f"Imported {len(records)} published treatment/crop/depth means from El-Henawy (2013), Kafr El-Sheikh experiment season 2007. Research-farm evidence only; not transferable as parcel measurements."))
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
