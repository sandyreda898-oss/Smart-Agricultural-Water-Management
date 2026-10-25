"""Idempotently import public rice references collected on 2026-10-25.

APC pest/disease records are secondary transcriptions for reference only.
No pesticide product/rate is supplied. The Sakha trial data are abstract-level.
"""
from pathlib import Path
import csv
import shutil
import sqlite3
from datetime import datetime

ROOT = Path(__file__).resolve().parent
DB = ROOT / "database" / "agriwater_v2.sqlite"
PROTECTION_CSV = ROOT / "data" / "processed" / "plant_protection_rice_apc2025_transcribed.csv"
TRIAL_CSV = ROOT / "data" / "processed" / "sakha_2012_2013_sowing_trial_summary.csv"
WATER_QUALITY_CSV = ROOT / "data" / "processed" / "sakha_irrigation_water_quality_2022_2023_abstract.csv"
KARADA_CSV = ROOT / "data" / "processed" / "el_karada_planting_methods_2006_2007.csv"
WATER_QUALITY_NUMERIC_CSV = ROOT / "data" / "processed" / "sakha_water_quality_2022_2023_numeric_results.csv"

def rows(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def main():
    backup = DB.with_name(f"{DB.stem}_before_public_reference_additions_{datetime.now():%Y%m%d_%H%M%S}.sqlite")
    shutil.copy2(DB, backup)
    con = sqlite3.connect(DB)
    try:
        con.execute("PRAGMA foreign_keys=ON")
        con.execute("""
        CREATE TABLE IF NOT EXISTS plant_protection_reference (
            reference_id TEXT PRIMARY KEY, crop TEXT NOT NULL DEFAULT 'rice',
            target_name_ar TEXT NOT NULL, target_name_en TEXT, issue_type TEXT NOT NULL,
            symptom_summary_ar TEXT, observation_window_ar TEXT, action_timing_ar TEXT,
            management_note_ar TEXT, pesticide_product TEXT, active_ingredient TEXT,
            rate_value REAL, rate_unit TEXT, preharvest_interval_days INTEGER,
            source_year INTEGER, source_page TEXT, source_url TEXT NOT NULL,
            source_quality TEXT NOT NULL, operational_status TEXT NOT NULL, notes TEXT
        )
        """)
        with con:
            con.execute("DELETE FROM literature_evidence WHERE study_id IN (?,?)",
                        ("kfsu_rehan_2012_2013", "gaber_sakha_water_quality_2022_2023"))
            for r in rows(PROTECTION_CSV):
                con.execute("""INSERT OR REPLACE INTO plant_protection_reference
                (reference_id,crop,target_name_ar,issue_type,symptom_summary_ar,observation_window_ar,
                 action_timing_ar,management_note_ar,source_year,source_page,source_url,source_quality,
                 operational_status,notes)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
                    r["reference_id"], r["crop"], r["target_name_ar"], r["issue_type"],
                    r["symptom_summary_ar"], r["observation_window_ar"], r["action_timing_ar"],
                    r["management_note_ar"], int(r["source_year"]), r["source_page"],
                    r["source_url"], r["source_quality"], r["operational_status"], r["notes"]))

            study_url = "https://kfs.edu.eg/post/pdf/98201523335246.pdf"
            con.execute("""INSERT OR IGNORE INTO literature_study
            (study_id,title,authors,publication_year,source_url,location_name,methods_summary,limitations,data_status)
            VALUES (?,?,?,?,?,?,?,?,?)""", (
                "kfsu_rehan_2012_2013",
                "Evaluation rice varieties under different sowing dates and planting methods",
                "Amgad Ahmed Essa Rehan", 2013, study_url,
                "Sakha Agriculture Research Station, Kafr El-Sheikh",
                "Two summer-season experiments (2012, 2013); varieties/lines GZ 7112, GZ 9057 and Sakha 105; sowing dates 15 April, 1 May and 15 May; transplanting and drill sowing.",
                "Only abstract values transcribed; GZ 9057 result is from a DUS experiment and is not a commercial farmer-field yield guarantee.",
                "abstract_transcription"))
            for r in rows(TRIAL_CSV):
                con.execute("""INSERT OR IGNORE INTO literature_evidence
                (study_id,crop_of_interest,factor_name,factor_level,outcome,result_summary,
                 study_context,source_locator,data_status,source_url)
                VALUES (?,?,?,?,?,?,?,?,?,?)""", (
                    r["study_id"], "rice", "cultivar_sowing_method_date",
                    f"{r['cultivar']}; {r['planting_method']}; {r['sowing_date']}",
                    "grain_yield_t_per_feddan", r["grain_yield_t_per_feddan"],
                    f"{r['location']}; season {r['season_year']}; abstract-level DUS trial result",
                    r["source_locator"], r["data_status"], r["source_url"]))
            con.execute("""INSERT OR IGNORE INTO literature_study
            (study_id,title,authors,publication_year,doi,source_url,location_name,methods_summary,limitations,data_status)
            VALUES (?,?,?,?,?,?,?,?,?,?)""", (
                "gaber_sakha_water_quality_2022_2023",
                "Impact of Various Irrigation Water Types on Soil Quality, Grain Heavy Metals Concentration and Productivity of Some Rice Varieties",
                "A. A. Gaber; Amira M. Okasha; M. M. Abdelhamed; B. A. Zayed", 2025,
                "10.21608/jpp.2025.351258.1428", "https://journals.ekb.eg/article_410567_0.html",
                "Sakha Agriculture Research Station, Kafr El-Sheikh",
                "Two summer-season field trials (2022 and 2023), strip-plot design with four replicates; FW, DW, 1FW:1DW, 2FW:1DW, 1FW:2DW; Giza 183, Giza 178, Sakha 106 and Sakha 108. Tables 10-14 transcribed for yield, grain traits and grain mineral/heavy-metal composition.",
                "Water chemistry and soil chemical/metal tables remain untranscribed. Grain concentrations are experimental treatment means and are not by themselves a food-safety determination or farmer-field prediction.",
                "tables_10_14_transcription"))
            con.execute("""UPDATE literature_study
            SET title=?, authors=?, publication_year=?, doi=?, source_url=?, location_name=?,
                methods_summary=?, limitations=?, data_status=?
            WHERE study_id=?""", (
                "Impact of Various Irrigation Water Types on Soil Quality, Grain Heavy Metals Concentration and Productivity of Some Rice Varieties",
                "A. A. Gaber; Amira M. Okasha; M. M. Abdelhamed; B. A. Zayed", 2025,
                "10.21608/jpp.2025.351258.1428", "https://journals.ekb.eg/article_410567_0.html",
                "Sakha Agriculture Research Station, Kafr El-Sheikh",
                "Two summer-season field trials (2022 and 2023), strip-plot design with four replicates; FW, DW, 1FW:1DW, 2FW:1DW, 1FW:2DW; Giza 183, Giza 178, Sakha 106 and Sakha 108. Tables 10-14 transcribed.",
                "Water chemistry and soil chemical/metal tables remain untranscribed. Grain concentrations are experimental treatment means, not a food-safety determination, universal blend recommendation or farmer-field prediction.",
                "tables_10_14_transcription", "gaber_sakha_water_quality_2022_2023"))
            for r in rows(WATER_QUALITY_CSV):
                con.execute("""INSERT OR IGNORE INTO literature_evidence
                (study_id,crop_of_interest,factor_name,factor_level,outcome,result_summary,
                 study_context,source_locator,data_status,source_url)
                VALUES (?,?,?,?,?,?,?,?,?,?)""", (
                    r["study_id"], "rice", r["factor_name"], r["factor_level"],
                    r["outcome"], r["result_summary"],
                    f"{r['location']}; seasons {r['seasons']}; cultivars {r['cultivars']}; water treatments {r['water_treatments']}; {r['design']} design, {r['replications']} replicates",
                    r["source_locator"], r["data_status"], r["source_url"]))
            con.execute("DELETE FROM literature_trial_result WHERE study_id=?",
                        ("gaber_sakha_water_quality_2022_2023",))
            variety_ids = {name:vid for vid,name in con.execute(
                "SELECT variety_id,name_en FROM rice_variety")}
            for r in rows(WATER_QUALITY_NUMERIC_CSV):
                variety_id = variety_ids.get(r["cultivar"])
                if r["cultivar"] == "ALL_CULTIVARS":
                    treatment = f"water_quality={r['water_quality_treatment']}; mean across tested cultivars"
                elif r["cultivar"] == "ALL_WATER_TREATMENTS":
                    treatment = f"cultivar={r['cultivar']}; mean across water treatments"
                else:
                    treatment = f"water_quality={r['water_quality_treatment']}"
                con.execute("""INSERT INTO literature_trial_result
                (study_id,season_year,variety_id,irrigation_regime,metric_name,metric_value,unit,table_reference,data_status)
                VALUES (?,?,?,?,?,?,?,?,?)""", (
                    r["study_id"], int(r["season_year"]), variety_id, treatment,
                    r["metric_name"], float(r["metric_value"]), r["unit"],
                    r["table_reference"], r["data_status"]))
            con.execute("""INSERT OR IGNORE INTO literature_study
            (study_id,title,authors,publication_year,doi,source_url,location_name,methods_summary,limitations,data_status)
            VALUES (?,?,?,?,?,?,?,?,?,?)""", (
                "el_karada_planting_methods_2006_2007",
                "Irrigation Water Management of Rice Crop in North Delta",
                "E. M. El-Hadidi; M. E. Meleha; M. A. A. Elbialy", 2008, "10.21608/jssae.2008.200433",
                "https://journals.ekb.eg/article_200433_76a9db2dced671a18307c7539bdfef08.pdf",
                "El-Karada Water Requirements Research Station, Kafr El-Sheikh",
                "Two summer seasons (2006, 2007); Sakha 104; randomized complete block with three replicates; six transplanting layouts; irrigation water volume and grain yield reported.",
                "Research-station trial, not farm observations or a current universal recommendation. Tables were transcribed from indexed author-copy/full-text; linked ResearchGate page identifies the study, and the exact table values are cross-checkable in the indexed full text.",
                "table_transcription"))
            con.execute("""UPDATE literature_study
            SET title=?, authors=?, publication_year=?, doi=?, source_url=?, location_name=?,
                methods_summary=?, limitations=?, data_status=?
            WHERE study_id=?""", (
                "Irrigation Water Management of Rice Crop in North Delta",
                "E. M. El-Hadidi; M. E. Meleha; M. A. A. Elbialy", 2008, "10.21608/jssae.2008.200433",
                "https://journals.ekb.eg/article_200433_76a9db2dced671a18307c7539bdfef08.pdf",
                "El-Karada Water Requirements Research Station, Kafr El-Sheikh",
                "Two summer seasons (2006, 2007); Sakha 104; randomized complete block with three replicates; six transplanting layouts; irrigation water volume and grain yield reported.",
                "Research-station trial, not farm observations or a current universal recommendation. Tables were transcribed from indexed author-copy/full-text; do not conflate with another similarly themed Meleha et al. study.",
                "table_transcription", "el_karada_planting_methods_2006_2007"))
            con.execute("DELETE FROM literature_trial_result WHERE study_id=?",
                        ("el_karada_planting_methods_2006_2007",))
            variety_id = con.execute("SELECT variety_id FROM rice_variety WHERE name_en='Sakha 104'").fetchone()[0]
            for r in rows(KARADA_CSV):
                method = f"{r['method_code']} - {r['planting_method']}"
                for metric, value, unit in (
                    ("grain_yield", float(r["grain_yield_kg_per_feddan"]), "kg_per_feddan"),
                    ("irrigation_water_applied", float(r["irrigation_water_m3_per_feddan"]), "m3_per_feddan"),
                ):
                    con.execute("""INSERT INTO literature_trial_result
                    (study_id,season_year,variety_id,irrigation_regime,metric_name,metric_value,unit,table_reference,data_status)
                    VALUES (?,?,?,?,?,?,?,?,?)""", (
                        r["study_id"], int(r["season_year"]), variety_id, method, metric,
                        value, unit, r["source_locator"], r["data_status"]))
        print("Imported plant-protection references:", con.execute("SELECT COUNT(*) FROM plant_protection_reference").fetchone()[0])
        print("Imported Sakha abstract evidence:", con.execute("SELECT COUNT(*) FROM literature_evidence WHERE study_id='kfsu_rehan_2012_2013'").fetchone()[0])
        print("Imported irrigation-water abstract evidence:", con.execute("SELECT COUNT(*) FROM literature_evidence WHERE study_id='gaber_sakha_water_quality_2022_2023'").fetchone()[0])
        print("Imported irrigation-water numeric results:", con.execute("SELECT COUNT(*) FROM literature_trial_result WHERE study_id='gaber_sakha_water_quality_2022_2023'").fetchone()[0])
        print("Imported El-Karada planting method results:", con.execute("SELECT COUNT(*) FROM literature_trial_result WHERE study_id='el_karada_planting_methods_2006_2007'").fetchone()[0])
        print("Integrity:", con.execute("PRAGMA integrity_check").fetchone()[0])
        print("Foreign-key violations:", len(con.execute("PRAGMA foreign_key_check").fetchall()))
        print("Backup:", backup)
    finally:
        con.close()

if __name__ == "__main__":
    main()
