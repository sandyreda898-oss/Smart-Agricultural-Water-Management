"""Add the planting establishment method to existing AgriWater databases."""
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / "database" / "agriwater_v2.sqlite"

con = sqlite3.connect(DB)
try:
    columns = {r[1] for r in con.execute("PRAGMA table_info(field_season)")}
finally:
    con.close()

if "establishment_method" not in columns:
    backup = DB.with_name(f"{DB.stem}_before_establishment_method_{datetime.now():%Y%m%d_%H%M%S}{DB.suffix}")
    shutil.copy2(DB, backup)
    con = sqlite3.connect(DB)
    try:
        con.execute("BEGIN IMMEDIATE")
        con.execute("ALTER TABLE field_season ADD COLUMN establishment_method TEXT CHECK (establishment_method IS NULL OR establishment_method IN ('transplanted','direct_seeded','not_sure'))")
        con.execute("INSERT OR REPLACE INTO database_metadata(item,details) VALUES(?,?)", (
            "establishment_method", "Rice establishment mode captured as transplanted, direct_seeded, or not_sure; nullable for historical records."))
        assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert not con.execute("PRAGMA foreign_key_check").fetchall()
        con.commit()
        print(f"Added field_season.establishment_method; backup: {backup}")
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
else:
    print("field_season.establishment_method already exists; no change made")
