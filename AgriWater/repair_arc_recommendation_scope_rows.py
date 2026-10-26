"""Repair two misaligned ARC recommendation rows; rebuild the CSV from SQLite."""
import csv
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / "database" / "agriwater_v2.sqlite"
CSV_PATH = ROOT / "data" / "processed" / "rice_recommendations_arc.csv"
ARC_PDF = "https://www.arc.sci.eg/files/9704/Attachment.pdf"
FIELDS = ["topic", "recommendation_text", "value_min", "value_max", "unit", "condition_scope", "variety_scope", "stage_scope", "geography_scope", "publication_date", "source_url", "source_locator", "confidence_status", "notes"]
FIXES = {
    "establishment_method": {
        "condition_scope": "saline_soils", "variety_scope": None,
        "stage_scope": "nursery_or_establishment", "geography_scope": "Egypt_saline_soils",
        "publication_date": "2026-01-26", "source_url": ARC_PDF,
        "source_locator": "PDF indexed excerpt", "confidence_status": "official_pdf_excerpt",
        "notes": "Conditional agronomic guidance; not a recommendation for every parcel.",
    },
    "climate_adapted_variety_group": {
        "condition_scope": None,
        "variety_scope": "Giza 177|Giza 178|Giza 179|Egyptian Hybrid 1|Sakha 104|Sakha 108|Egyptian Jasmine",
        "stage_scope": "planning", "geography_scope": "Egypt", "publication_date": "2026-01-26",
        "source_url": ARC_PDF, "source_locator": "page 50 climate-change recommendations",
        "confidence_status": "official_pdf_excerpt",
        "notes": "National bulletin list; not a Kafr El Sheikh field-specific ranking or current seed-availability confirmation.",
    },
}

stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup = DB.with_name(f"{DB.stem}_before_arc_scope_repair_{stamp}{DB.suffix}")
csv_backup = CSV_PATH.with_name(f"{CSV_PATH.stem}_before_arc_scope_rebuild_{stamp}{CSV_PATH.suffix}")
shutil.copy2(DB, backup)
shutil.copy2(CSV_PATH, csv_backup)

con = sqlite3.connect(DB)
try:
    con.execute("BEGIN IMMEDIATE")
    for topic, values in FIXES.items():
        cur = con.execute(
            "UPDATE agronomy_recommendation SET condition_scope=?,variety_scope=?,stage_scope=?,geography_scope=?,publication_date=?,source_url=?,source_locator=?,confidence_status=?,notes=? WHERE topic=?",
            (values["condition_scope"], values["variety_scope"], values["stage_scope"], values["geography_scope"],
             values["publication_date"], values["source_url"], values["source_locator"], values["confidence_status"], values["notes"], topic),
        )
        if cur.rowcount != 1:
            raise RuntimeError(f"Expected one database row for {topic}, updated {cur.rowcount}")
    assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert not con.execute("PRAGMA foreign_key_check").fetchall()
    rows = [dict(zip(FIELDS, r)) for r in con.execute(
        "SELECT topic,recommendation_text,value_min,value_max,unit,condition_scope,variety_scope,stage_scope,geography_scope,publication_date,source_url,source_locator,confidence_status,notes FROM agronomy_recommendation ORDER BY recommendation_id"
    )]
    if len(rows) != 23:
        raise RuntimeError(f"Expected 23 ARC recommendations; found {len(rows)}")
    con.commit()
finally:
    con.close()

with CSV_PATH.open("w", newline="", encoding="utf-8-sig") as f:
    writer = csv.DictWriter(f, fieldnames=FIELDS)
    writer.writeheader()
    writer.writerows(rows)

print(f"Repaired 2 ARC scope rows and rebuilt {len(rows)} CSV rows from SQLite.")
print(f"Database backup: {backup}")
print(f"Prior CSV snapshot: {csv_backup}")
