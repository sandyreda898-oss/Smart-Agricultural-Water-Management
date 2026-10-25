"""Idempotently load the curated ARC rice catalogue extract into SQLite.

Run from the project root:
    python import_arc_rice_varieties.py

The script makes a SQLite-consistent backup, updates only rice variety/source
reference tables and database_metadata, and rolls back if integrity checks fail.
"""
import csv
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / "database" / "agriwater_v2.sqlite"
CSV_PATH = ROOT / "data" / "processed" / "rice_variety_reference_arc.csv"
SOURCE_NAME = "ARC Rice Research Department product catalogue"
SOURCE_URL = "https://www.arc.sci.eg/Products/Search/54?TypeID=1&lang=1"
ACCESS_DATE = "2026-10-25"

TEXT_FIELDS = (
    "name_en", "name_ar", "grain_type", "quality_note", "plant_type_note",
    "lodging_note", "disease_note", "soil_suitability", "source_url", "data_status",
)
NUMERIC_FIELDS = (
    "season_length_days", "expected_yield_min_ton_ha", "expected_yield_max_ton_ha",
    "temperature_min_c", "temperature_max_c",
)
REFERENCE_FIELDS = (
    "expected_yield_min_ton_ha", "expected_yield_max_ton_ha", "grain_type",
    "quality_note", "plant_type_note", "lodging_note", "disease_note",
    "soil_suitability", "temperature_min_c", "temperature_max_c", "source_url", "data_status",
)


def read_extract():
    with CSV_PATH.open(newline="", encoding="utf-8-sig") as source_file:
        reader = csv.DictReader(source_file)
        required = set(TEXT_FIELDS) | set(NUMERIC_FIELDS)
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"CSV columns missing: {sorted(missing)}")
        rows = list(reader)

    seen = set()
    for row_number, row in enumerate(rows, start=2):
        name = (row.get("name_en") or "").strip()
        if not name or name in seen:
            raise ValueError(f"CSV row {row_number}: missing or duplicate name_en={name!r}")
        seen.add(name)
        if not (row.get("source_url") or "").startswith("https://"):
            raise ValueError(f"CSV row {row_number}: an HTTPS source_url is required")
        for field in NUMERIC_FIELDS:
            value = (row.get(field) or "").strip()
            row[field] = int(value) if field == "season_length_days" and value else (
                float(value) if value else None
            )
        for field in TEXT_FIELDS:
            row[field] = (row.get(field) or "").strip() or None
        if not row["data_status"]:
            raise ValueError(f"CSV row {row_number}: data_status is required")
    return rows


def main():
    if not DB.exists():
        sys.exit(f"Database not found: {DB}")
    rows = read_extract()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = DB.with_name(f"{DB.stem}_backup_before_arc_import_{stamp}{DB.suffix}")

    con = sqlite3.connect(DB)
    con.execute("PRAGMA foreign_keys = ON")
    try:
        with sqlite3.connect(backup_path) as backup:
            con.backup(backup)
        con.execute("BEGIN IMMEDIATE")
        con.execute(
            "INSERT INTO data_source(name, url, notes) VALUES (?, ?, ?) "
            "ON CONFLICT(name) DO UPDATE SET url=excluded.url, notes=excluded.notes",
            (SOURCE_NAME, SOURCE_URL,
             "ARC product-catalogue traits; catalogue yields are not field guarantees; "
             "the cultivar catalogue is not an annual seed-approval list."),
        )

        for row in rows:
            con.execute(
                "INSERT INTO rice_variety(name_en, name_ar, season_length_days, source_url, data_status) "
                "VALUES (?, ?, ?, ?, ?) ON CONFLICT(name_en) DO UPDATE SET "
                "name_ar=excluded.name_ar, season_length_days=excluded.season_length_days, "
                "source_url=excluded.source_url, data_status=excluded.data_status",
                (row["name_en"], row["name_ar"], row["season_length_days"],
                 row["source_url"], row["data_status"]),
            )
            variety_id = con.execute(
                "SELECT variety_id FROM rice_variety WHERE name_en=?", (row["name_en"],)
            ).fetchone()[0]
            values = [row[field] for field in REFERENCE_FIELDS]
            con.execute(
                "INSERT INTO rice_variety_reference(variety_id, "
                + ", ".join(REFERENCE_FIELDS)
                + ") VALUES (" + ", ".join("?" for _ in range(len(REFERENCE_FIELDS) + 1)) + ") "
                "ON CONFLICT(variety_id) DO UPDATE SET "
                + ", ".join(f"{field}=excluded.{field}" for field in REFERENCE_FIELDS),
                [variety_id, *values],
            )

        con.execute("DELETE FROM database_metadata WHERE item='rice_variety_reference_arc_import'")
        con.execute(
            "INSERT INTO database_metadata(item, details) VALUES (?, ?)",
            ("rice_variety_reference_arc_import",
             f"Source: {SOURCE_URL}; accessed: {ACCESS_DATE}; "
             f"curated catalogue rows: {len(rows)}; Sakha 109 conflicting catalogue traits withheld."),
        )

        fk_errors = con.execute("PRAGMA foreign_key_check").fetchall()
        integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
        if fk_errors or integrity != "ok":
            raise RuntimeError(f"Integrity checks failed: foreign_keys={fk_errors}, integrity={integrity}")
        con.commit()
        print(f"Imported/updated ARC rice profiles: {len(rows)}")
        print(f"Backup: {backup_path}")
        print(f"SQLite integrity: {integrity}; foreign-key violations: {len(fk_errors)}")
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


if __name__ == "__main__":
    main()
