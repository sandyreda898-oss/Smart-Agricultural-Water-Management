"""Backup-first migration adding study foreign keys to literature reference tables."""
from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

DB = Path(__file__).resolve().parent / "database" / "agriwater_v2.sqlite"

TABLES = {
    "literature_trial_observation": """CREATE TABLE {table} (
        observation_id INTEGER PRIMARY KEY,
        study_id TEXT NOT NULL REFERENCES literature_study(study_id),
        study_year INTEGER, observation_period TEXT NOT NULL, preceding_crop TEXT,
        puddling TEXT, depth_top_cm REAL, depth_bottom_cm REAL,
        metric_name TEXT NOT NULL, metric_value REAL NOT NULL, unit TEXT NOT NULL,
        aggregation_level TEXT NOT NULL, replicate_count INTEGER,
        source_locator TEXT NOT NULL, data_status TEXT NOT NULL, source_url TEXT NOT NULL)""",
    "literature_evidence": """CREATE TABLE {table} (
        evidence_id INTEGER PRIMARY KEY,
        study_id TEXT NOT NULL REFERENCES literature_study(study_id),
        crop_of_interest TEXT, factor_name TEXT NOT NULL, factor_level TEXT,
        outcome TEXT NOT NULL, result_summary TEXT NOT NULL,
        statistical_result TEXT, study_context TEXT, source_locator TEXT,
        data_status TEXT NOT NULL, source_url TEXT NOT NULL)""",
}


def main():
    backup = DB.with_name(f"{DB.stem}_before_literature_fk_migration_{datetime.now():%Y%m%d_%H%M%S}{DB.suffix}")
    shutil.copy2(DB, backup)
    con = sqlite3.connect(DB)
    try:
        con.execute("PRAGMA foreign_keys=OFF")
        con.execute("BEGIN IMMEDIATE")
        old_name = "literature_soil_observation"
        new_name = "literature_trial_observation"
        old_exists = con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (old_name,)).fetchone()
        new_exists = con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (new_name,)).fetchone()
        if old_exists and not new_exists:
            con.execute(f"ALTER TABLE {old_name} RENAME TO {new_name}")
        for table, ddl in TABLES.items():
            if not con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone():
                continue
            has_fk = any(row[2] == "literature_study" for row in con.execute(f"PRAGMA foreign_key_list({table})"))
            if has_fk:
                continue
            new = f"{table}__fk_new"
            con.execute(f"DROP TABLE IF EXISTS {new}")
            con.execute(ddl.format(table=new))
            cols = [r[1] for r in con.execute(f"PRAGMA table_info({table})")]
            col_sql = ",".join(cols)
            con.execute(f"INSERT INTO {new} ({col_sql}) SELECT {col_sql} FROM {table}")
            con.execute(f"DROP TABLE {table}")
            con.execute(f"ALTER TABLE {new} RENAME TO {table}")
        con.commit()
        con.execute("PRAGMA foreign_keys=ON")
        violations = con.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise RuntimeError(f"foreign-key violations after migration: {violations[:5]}")
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
    print(f"backup={backup}")
    print("literature_reference_foreign_keys=verified")


if __name__ == "__main__":
    main()
