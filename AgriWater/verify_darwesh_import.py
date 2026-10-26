import json
import sqlite3

with sqlite3.connect("database/agriwater_v2.sqlite") as con:
    print("total observations", con.execute("SELECT count(*) FROM literature_trial_observation").fetchone()[0])
    print("new observations", con.execute("SELECT count(*) FROM literature_trial_observation WHERE study_id=?", ("DARWESH_SAKHA_IRRIGATION_DEPTH_INTERVAL_2013_2014",)).fetchone()[0])
    print("new metric counts", con.execute("SELECT metric_name,count(*) FROM literature_trial_observation WHERE study_id=? GROUP BY metric_name ORDER BY metric_name", ("DARWESH_SAKHA_IRRIGATION_DEPTH_INTERVAL_2013_2014",)).fetchall())
    print("study DOI", con.execute("SELECT doi FROM literature_study WHERE study_id=?", ("DARWESH_SAKHA_IRRIGATION_DEPTH_INTERVAL_2013_2014",)).fetchone()[0])
    print("SQLite integrity", con.execute("PRAGMA integrity_check").fetchone()[0])
    print("foreign key violations", len(con.execute("PRAGMA foreign_key_check").fetchall()))
with open("source_registry.json", encoding="utf-8") as f:
    json.load(f)
print("source registry JSON valid")
