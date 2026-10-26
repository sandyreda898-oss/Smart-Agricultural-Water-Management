"""Repair confirmed reference-data quality issues without modifying raw inputs."""
from __future__ import annotations

import csv
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / "database" / "agriwater_v2.sqlite"
SOIL_CSV = ROOT / "data" / "processed" / "hwsd2_soil_samples_clean.csv"
PARAM_CSV = ROOT / "data" / "processed" / "crop_water_parameters.csv"


def repair_soil_csv() -> int:
    with SOIL_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fields = reader.fieldnames
    repaired = 0
    for row in rows:
        props = ("sand_pct", "silt_pct", "clay_pct", "bulk", "organic_carbon", "ph_water")
        if any(row.get(col, "").strip() == "-1" for col in props):
            for col in props:
                if row.get(col, "").strip() == "-1":
                    row[col] = ""
            row["soil_data_status"] = "INCOMPLETE_NODATA_SENTINEL"
            row["missing_soil_properties"] = ";".join(col for col in props if not row.get(col, "").strip())
            repaired += 1
    if repaired:
        with SOIL_CSV.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
    return repaired


def repair_parameter_csv() -> None:
    with PARAM_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fields = list(reader.fieldnames or [])
    for name in ("value_min", "value_max"):
        if name not in fields:
            fields.append(name)
    for row in rows:
        row.setdefault("value_min", "")
        row.setdefault("value_max", "")
        if row.get("parameter_name") == "Kc" and row.get("growth_stage") == "late_season":
            row["kc"] = ""
            row["parameter_value"] = ""
            row["value_min"], row["value_max"] = "0.60", "0.90"
            row["data_status"] = "FAO_REFERENCE_RANGE_NOT_LOCALLY_CALIBRATED"
            row["valid_conditions"] = "FAO-56 range stored in value_min/value_max; depends on crop/harvest conditions; not locally calibrated"
        elif row.get("parameter_name") == "seepage_percolation_rate":
            row["parameter_value"] = ""
            row["value_min"], row["value_max"] = "4", "8"
            row["data_status"] = "LITERATURE_RANGE_NOT_LOCALLY_MEASURED"
            row["valid_conditions"] = "General literature range; depends on soil and field conditions; not a Kafr El Sheikh field measurement"
        elif row.get("parameter_value", "").strip():
            row["value_min"] = row["parameter_value"]
            row["value_max"] = row["parameter_value"]
    with PARAM_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = DB.with_name(f"{DB.stem}_before_quality_repair_{stamp}{DB.suffix}")
    shutil.copy2(DB, backup)
    repaired_csv = repair_soil_csv()
    repair_parameter_csv()
    con = sqlite3.connect(DB)
    try:
        con.execute("BEGIN IMMEDIATE")
        # Sentinel -1 means missing in the processed HWSD2 extract, never a measurement.
        con.execute("""UPDATE soil_point SET sand_pct=NULL, silt_pct=NULL, clay_pct=NULL,
            bulk=NULL, organic_carbon=NULL, ph_water=NULL,
            soil_data_status='INCOMPLETE_NODATA_SENTINEL',
            missing_properties='sand_pct;silt_pct;clay_pct;bulk;organic_carbon;ph_water'
            WHERE point_id='grid_0028' AND
            (sand_pct<0 OR silt_pct<0 OR clay_pct<0 OR bulk<0 OR organic_carbon<0 OR ph_water<0)""")
        columns = {row[1] for row in con.execute("PRAGMA table_info(crop_water_parameter)")}
        if "value_min" not in columns:
            con.execute("ALTER TABLE crop_water_parameter ADD COLUMN value_min REAL")
        if "value_max" not in columns:
            con.execute("ALTER TABLE crop_water_parameter ADD COLUMN value_max REAL")
        con.execute("""UPDATE crop_water_parameter SET value_min=0.60, value_max=0.90,
            kc=NULL, parameter_value=NULL,
            valid_conditions='FAO-56 reference range; stored as min/max, not a single value; exact value depends on harvest and crop conditions'
            WHERE parameter_name='Kc' AND growth_stage='late_season'""")
        con.execute("""UPDATE crop_water_parameter SET value_min=4, value_max=8,
            parameter_value=NULL,
            valid_conditions='General FAO literature range; stored as min/max, not a local measurement; actual seepage depends on soil, land preparation, and water table'
            WHERE parameter_name='seepage_percolation_rate'""")
        con.execute("""UPDATE crop_water_parameter SET value_min=parameter_value,
            value_max=parameter_value WHERE parameter_value IS NOT NULL
            AND value_min IS NULL AND value_max IS NULL""")
        if "source_url" not in {row[1] for row in con.execute("PRAGMA table_info(regional_stats)")}:
            con.execute("ALTER TABLE regional_stats ADD COLUMN source_url TEXT")
        if "source_status" not in {row[1] for row in con.execute("PRAGMA table_info(regional_stats)")}:
            con.execute("ALTER TABLE regional_stats ADD COLUMN source_status TEXT")
        official = {
            2017: ("https://www.agri.gov.eg/uploads/topics/16590155437448.pdf", "PRIMARY_MINISTRY_AREA_PRODUCTION_YIELD_DERIVED"),
            2018: ("https://www.agri.gov.eg/uploads/topics/16590144036403.pdf", "PRIMARY_MINISTRY_AREA_PRODUCTION_YIELD_DERIVED"),
            2019: ("https://www.agri.gov.eg/uploads/topics/16590722424936.pdf", "PRIMARY_MINISTRY_ALL_FIELDS"),
            2020: ("https://www.capmas.gov.eg/pdf/new_Pdf/2022228132150_%D9%86%D8%B4%D8%B1%D8%A9%20%D8%A7%D9%84%D9%85%D8%B3%D8%A7%D8%AD%D8%A7%D8%AA%202020_Compressed.pdf", "PRIMARY_CAPMAS_AREA_PRODUCTION_YIELD_DERIVED"),
            2021: ("https://www.agri.gov.eg/uploads/topics/16692385498467.pdf", "PRIMARY_MINISTRY_OFFICIAL"),
            2022: ("https://www.agri.gov.eg/uploads/topics/17172249083909.pdf", "PRIMARY_MINISTRY_OFFICIAL"),
            2023: ("https://www.agri.gov.eg/uploads/topics/17329628961779.pdf", "PRIMARY_MINISTRY_OFFICIAL"),
        }
        for year, (url, status) in official.items():
            con.execute("UPDATE regional_stats SET source_url=?,source_status=? WHERE season_year=?", (url, status, year))
        capmas_url = official[2020][0]
        con.execute("""INSERT OR IGNORE INTO data_source(name,url,notes)
            SELECT ?,?,? WHERE NOT EXISTS (SELECT 1 FROM data_source WHERE url=?)""",
            ("CAPMAS Agricultural Areas Bulletin 2019/2020", capmas_url,
             "Primary area and production by governorate; yield is computed as production divided by area.", capmas_url))
        rule_columns = {row[1] for row in con.execute("PRAGMA table_info(ministry_rule)")}
        if "source_status" not in rule_columns:
            con.execute("ALTER TABLE ministry_rule ADD COLUMN source_status TEXT")
        if "review_notes" not in rule_columns:
            con.execute("ALTER TABLE ministry_rule ADD COLUMN review_notes TEXT")
        con.execute("""UPDATE ministry_rule SET source_status='SECONDARY_PRESS_UNVERIFIED',
            review_notes='Secondary press-derived rule; no matching primary official notice verified in this project. Retained for traceability and excluded from operational recommendations.'
            WHERE source_status IS NULL OR source_status=''""")
        press_urls = [row[0] for row in con.execute("SELECT DISTINCT source_url FROM ministry_rule WHERE source_url IS NOT NULL")]
        for url in press_urls:
            con.execute("""INSERT OR IGNORE INTO data_source(name,url,notes)
                SELECT ?,?,? WHERE NOT EXISTS (SELECT 1 FROM data_source WHERE url=?)""",
                ("Unverified secondary press source for ministry_rule", url,
                 "Secondary press report retained for traceability only; not an operational official rule.", url))
        con.execute("""UPDATE database_metadata SET details='Numeric ranges use value_min/value_max; parameter_value and kc remain NULL for ranges. Literature references are not locally calibrated.' WHERE item='crop_water_parameter_notes'""")
        con.execute("INSERT OR REPLACE INTO database_metadata(item,details) VALUES (?,?)",
            ("reference_quality_repair", f"{stamp}; corrected negative HWSD2 nodata sentinel; added explicit numeric min/max fields to crop_water_parameter; backup={backup.name}"))
        con.execute("INSERT OR REPLACE INTO database_metadata(item,details) VALUES (?,?)",
            ("ministry_rule_review", "Existing press-derived records are tagged SECONDARY_PRESS_UNVERIFIED and excluded from operational recommendations pending primary official sources."))
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
    print(f"backup={backup}")
    print(f"soil_csv_rows_repaired={repaired_csv}")
    print("database_repairs=soil_nodata_sentinel,crop_water_parameter_numeric_ranges,regional_primary_sources,ministry_rule_provenance_tags")


if __name__ == "__main__":
    main()
