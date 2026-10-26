"""Load a curated, published Sakha-station rice trial extract into SQLite.

Run from the project root:
    python import_rice_irrigation_trials.py

Research-plot outcomes are stored separately from farmer field-season labels.
The importer is repeatable, backs up the database, and checks relational integrity.
"""
import csv
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / "database" / "agriwater_v2.sqlite"
CSV_PATH = ROOT / "data" / "processed" / "rice_irrigation_trial_results.csv"
META_PATH = ROOT / "data" / "metadata" / "ghazy2019_giza179_trial.json"
SOURCE_NAME = "Journal of Plant Production - Ghazy, Mikhael, and El-Refaee (2019)"

SCHEMA = """
CREATE TABLE IF NOT EXISTS literature_study (
    study_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    authors TEXT,
    publication_year INTEGER,
    doi TEXT UNIQUE,
    source_url TEXT NOT NULL,
    location_name TEXT,
    latitude REAL,
    longitude REAL,
    methods_summary TEXT,
    limitations TEXT,
    data_status TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS literature_trial_result (
    result_id INTEGER PRIMARY KEY,
    study_id TEXT NOT NULL REFERENCES literature_study(study_id),
    season_year INTEGER NOT NULL,
    variety_id INTEGER REFERENCES rice_variety(variety_id),
    irrigation_regime TEXT NOT NULL,
    irrigation_interval_days REAL,
    row_spacing_cm REAL,
    hill_spacing_cm REAL,
    metric_name TEXT NOT NULL,
    metric_value REAL NOT NULL,
    unit TEXT NOT NULL,
    table_reference TEXT,
    data_status TEXT NOT NULL,
    UNIQUE (study_id, season_year, variety_id, irrigation_regime,
            row_spacing_cm, hill_spacing_cm, metric_name)
);
"""


def load_inputs():
    meta = json.loads(META_PATH.read_text(encoding="utf-8"))
    with CSV_PATH.open(newline="", encoding="utf-8-sig") as source_file:
        reader = csv.DictReader(source_file)
        required = {
            "study_id", "season_year", "variety", "irrigation_regime",
            "irrigation_interval_days", "row_spacing_cm", "hill_spacing_cm",
            "metric_name", "metric_value", "unit", "table_reference", "data_status",
        }
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"CSV columns missing: {sorted(missing)}")
        rows = list(reader)
    if not rows:
        raise ValueError("Trial extract is empty")
    unique = set()
    for line, row in enumerate(rows, start=2):
        if row["study_id"] != meta["study_id"]:
            raise ValueError(f"CSV line {line}: unexpected study_id")
        if row["metric_name"] not in {"grain_yield", "water_productivity"}:
            raise ValueError(f"CSV line {line}: unsupported metric {row['metric_name']!r}")
        if row["metric_name"] == "grain_yield" and row["unit"] != "t/ha":
            raise ValueError(f"CSV line {line}: unexpected grain-yield unit")
        if row["metric_name"] == "water_productivity" and row["unit"] != "kg/m3":
            raise ValueError(f"CSV line {line}: unexpected water-productivity unit")
        for key in ("season_year", "row_spacing_cm", "hill_spacing_cm", "metric_value"):
            row[key] = float(row[key])
        row["season_year"] = int(row["season_year"])
        row["row_spacing_cm"] = int(row["row_spacing_cm"])
        row["hill_spacing_cm"] = int(row["hill_spacing_cm"])
        row["irrigation_interval_days"] = (
            float(row["irrigation_interval_days"]) if row["irrigation_interval_days"] else None
        )
        key = (row["season_year"], row["variety"], row["irrigation_regime"],
               row["row_spacing_cm"], row["hill_spacing_cm"], row["metric_name"])
        if key in unique:
            raise ValueError(f"CSV line {line}: duplicate result key {key}")
        unique.add(key)
    return meta, rows


def main():
    if not DB.exists():
        sys.exit(f"Database not found: {DB}")
    meta, rows = load_inputs()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = DB.with_name(f"{DB.stem}_backup_before_trial_import_{stamp}{DB.suffix}")
    con = sqlite3.connect(DB)
    con.execute("PRAGMA foreign_keys = ON")
    try:
        with sqlite3.connect(backup_path) as backup:
            con.backup(backup)
        con.executescript(SCHEMA)
        con.execute("BEGIN IMMEDIATE")
        con.execute(
            "INSERT INTO data_source(name, url, notes) VALUES (?, ?, ?) "
            "ON CONFLICT(name) DO UPDATE SET url=excluded.url, notes=excluded.notes",
            (SOURCE_NAME, meta["source_url"],
             "Research-station treatment data; not farmer-field labels; no absolute irrigation volumes in extracted tables."),
        )
        methods = meta["trial_details"]
        methods_summary = (
            f"Seasons {meta['seasons']}; cultivar {meta['variety']}; 30-day seedlings; "
            f"sowing dates {methods['sowing_dates']}; N={methods['fertilizer_n_kg_ha']} kg/ha; "
            f"{methods['soil_texture']} soil; water measured with {methods['water_measurement']}."
        )
        con.execute(
            "INSERT INTO literature_study(study_id,title,authors,publication_year,doi,source_url,"
            "location_name,latitude,longitude,methods_summary,limitations,data_status) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(study_id) DO UPDATE SET "
            "title=excluded.title,authors=excluded.authors,publication_year=excluded.publication_year,"
            "doi=excluded.doi,source_url=excluded.source_url,location_name=excluded.location_name,"
            "latitude=excluded.latitude,longitude=excluded.longitude,methods_summary=excluded.methods_summary,"
            "limitations=excluded.limitations,data_status=excluded.data_status",
            (meta["study_id"], meta["title"], meta["authors"], meta["publication_year"],
             meta["doi"], meta["source_url"], meta["location_name"], meta["latitude"],
             meta["longitude"], methods_summary, " ".join(meta["limitations"]), meta["data_status"]),
        )

        for row in rows:
            variety = con.execute(
                "SELECT variety_id FROM rice_variety WHERE name_en=?", (row["variety"],)
            ).fetchone()
            if not variety:
                raise ValueError(f"Rice variety not found in rice_variety: {row['variety']}")
            con.execute(
                "INSERT INTO literature_trial_result(study_id,season_year,variety_id,irrigation_regime,"
                "irrigation_interval_days,row_spacing_cm,hill_spacing_cm,metric_name,metric_value,unit,"
                "table_reference,data_status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(study_id,season_year,variety_id,irrigation_regime,row_spacing_cm,"
                "hill_spacing_cm,metric_name) DO UPDATE SET irrigation_interval_days=excluded.irrigation_interval_days,"
                "metric_value=excluded.metric_value,unit=excluded.unit,table_reference=excluded.table_reference,"
                "data_status=excluded.data_status",
                (row["study_id"], row["season_year"], variety[0], row["irrigation_regime"],
                 row["irrigation_interval_days"], row["row_spacing_cm"], row["hill_spacing_cm"],
                 row["metric_name"], row["metric_value"], row["unit"], row["table_reference"],
                 row["data_status"]),
            )

        con.execute("DELETE FROM database_metadata WHERE item='ghazy2019_giza179_trial_import'")
        con.execute(
            "INSERT INTO database_metadata(item,details) VALUES (?,?)",
            ("ghazy2019_giza179_trial_import",
             f"DOI: {meta['doi']}; source: {meta['source_url']}; curated observations: {len(rows)}; "
             "research-station results only; absolute treatment irrigation volumes are not in this extract."),
        )
        fk_errors = con.execute("PRAGMA foreign_key_check").fetchall()
        integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
        if fk_errors or integrity != "ok":
            raise RuntimeError(f"Integrity checks failed: foreign_keys={fk_errors}, integrity={integrity}")
        con.commit()
        print(f"Study loaded: {meta['study_id']}; result rows: {len(rows)}")
        print(f"Backup: {backup_path}")
        print(f"SQLite integrity: {integrity}; foreign-key violations: {len(fk_errors)}")
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


if __name__ == "__main__":
    main()
