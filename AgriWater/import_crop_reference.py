"""Load a small crop-name and rotation taxonomy for common Kafr El-Sheikh crops."""
from __future__ import annotations

import csv
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / "database" / "agriwater_v2.sqlite"
OUT = ROOT / "data" / "processed" / "crop_reference_kafr_el_sheikh.csv"
URL = "https://www.jstage.jst.go.jp/article/jdsa/8/2/8_119/_pdf/-char/en"
ROWS = [
    ("RICE", "Rice", "الأرز", "Oryza sativa L.", "رز;أرز", "rice;paddy", "summer", "cereal", "no", "Study sites describe rice as a main summer crop. Crop group is not a numeric nutrient credit."),
    ("WHEAT", "Wheat", "القمح", "Triticum aestivum L.", "قمح", "wheat", "winter", "cereal", "no", "Study sites describe wheat as a main winter crop. Crop group is not a numeric nutrient credit."),
    ("BERSEEM", "Egyptian clover (berseem)", "البرسيم المصري", "Trifolium alexandrinum L.", "برسيم;برسيم فحل", "berseem;egyptian clover;fahl berseem", "winter", "legume", "yes", "Local rice trial compares berseem with wheat as preceding crops. Nitrogen residue amount is not inferred from this label."),
    ("MAIZE", "Maize", "الذرة", "Zea mays L.", "ذرة;ذرة شامية", "maize;corn", "summer", "cereal", "no", "Study sites describe maize as a main summer crop. Crop group is not a numeric nutrient credit."),
    ("COTTON", "Cotton", "القطن", "Gossypium hirsutum L.", "قطن", "cotton", "summer", "fiber_crop", "no", "Listed as a main summer crop in the local study-area description."),
    ("SUGAR_BEET", "Sugar beet", "بنجر السكر", "Beta vulgaris L.", "بنجر;بنجر السكر", "sugar beet", "winter", "root_crop", "no", "Listed as a main winter crop in the local study-area description."),
    ("BARLEY", "Barley", "الشعير", "Hordeum vulgare L.", "شعير", "barley", "winter", "cereal", "no", "Included because Sakha rice trials document barley as a preceding crop."),
]


def main():
    fields = ["crop_code", "name_en", "name_ar", "botanical_name", "aliases_ar", "aliases_en",
              "typical_season", "functional_group", "legume_status", "source_url", "source_locator", "notes"]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in ROWS:
            code, en, ar, botanical, aliases_ar, aliases_en, season, group, legume, note = row
            writer.writerow(dict(zip(fields, [code, en, ar, botanical, aliases_ar, aliases_en, season,
                                               group, legume, URL, "Local crop context, Introduction; local trial sources",
                                               note])))
    backup = DB.with_name(f"{DB.stem}_before_crop_reference_{datetime.now():%Y%m%d_%H%M%S}{DB.suffix}")
    shutil.copy2(DB, backup)
    con = sqlite3.connect(DB)
    try:
        con.execute("BEGIN IMMEDIATE")
        con.execute("""CREATE TABLE IF NOT EXISTS crop_reference (
            crop_code TEXT PRIMARY KEY, name_en TEXT NOT NULL, name_ar TEXT NOT NULL,
            botanical_name TEXT, aliases_ar TEXT, aliases_en TEXT, typical_season TEXT,
            functional_group TEXT, legume_status TEXT, source_url TEXT, source_locator TEXT, notes TEXT)""")
        crop_history_columns = {r[1] for r in con.execute("PRAGMA table_info(crop_history)")}
        if "crop_code" not in crop_history_columns:
            con.execute("ALTER TABLE crop_history ADD COLUMN crop_code TEXT REFERENCES crop_reference(crop_code)")
        con.executemany("""INSERT OR REPLACE INTO crop_reference VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""", [
            (code, en, ar, botanical, aliases_ar, aliases_en, season, group, legume, URL,
             "Local crop context, Introduction; local trial sources", note)
            for code, en, ar, botanical, aliases_ar, aliases_en, season, group, legume, note in ROWS
        ])
        con.execute("""INSERT OR IGNORE INTO data_source(name,url,notes) VALUES(?,?,?)""", (
            "Local crop names and seasonal context near Sakha",
            URL,
            "Used only to normalize crop history labels and typical summer/winter groups; does not assign nutrient credits."))
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
    print(f"backup={backup}")
    print(f"crop_reference_rows={len(ROWS)}; csv={OUT}")


if __name__ == "__main__":
    main()
