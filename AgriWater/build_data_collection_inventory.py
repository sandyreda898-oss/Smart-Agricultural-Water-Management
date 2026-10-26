"""Refresh file-level and database-table inventory for the collection phase."""
import csv
import sqlite3
from datetime import date
from pathlib import Path

ROOT=Path(__file__).resolve().parent
DB=ROOT/"database"/"agriwater_v2.sqlite"
OUT=ROOT/"reports"

def main():
    OUT.mkdir(exist_ok=True)
    files=[]
    for base in (ROOT/"data",):
        for p in sorted(base.rglob("*")):
            if p.is_file():
                rel=p.relative_to(ROOT).as_posix()
                files.append({"file":rel,"bytes":p.stat().st_size,"collection_layer":p.parent.name,
                              "format":p.suffix.lower().lstrip("."),"inventory_date":date.today().isoformat()})
    with (OUT/"data_file_inventory_2026-10-25.csv").open("w",newline="",encoding="utf-8-sig") as f:
        w=csv.DictWriter(f,fieldnames=list(files[0]));w.writeheader();w.writerows(files)
    with sqlite3.connect(DB) as con:
        names=[r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        tables=[]
        for name in names:
            count=con.execute('SELECT COUNT(*) FROM "'+name.replace('"','""')+'"').fetchone()[0]
            tables.append({"table_name":name,"row_count":count,"collection_date":date.today().isoformat()})
        fk=len(con.execute("PRAGMA foreign_key_check").fetchall())
        integrity=con.execute("PRAGMA integrity_check").fetchone()[0]
    with (OUT/"database_table_inventory_2026-10-25.csv").open("w",newline="",encoding="utf-8-sig") as f:
        w=csv.DictWriter(f,fieldnames=list(tables[0]));w.writeheader();w.writerows(tables)
    print(f"Data files inventoried: {len(files)}")
    print(f"Database tables inventoried: {len(tables)}")
    print(f"Evidence rows: {dict((x['table_name'],x['row_count']) for x in tables).get('literature_trial_observation',0)}")
    print(f"SQLite integrity: {integrity}; FK violations: {fk}")

if __name__=="__main__": main()
