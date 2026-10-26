import sqlite3
c = sqlite3.connect("file:database/agriwater_v2.sqlite?mode=ro", uri=True)
for t in ("irrigation_method", "pump_type"):
    print(t, c.execute(f"select * from {t}").fetchall())
