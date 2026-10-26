import os, sqlite3

out = open("project_snapshot.txt", "w", encoding="utf-8")
def p(*a):
    print(*a, file=out)

p("===== FILE TREE =====")
skip = {".venv", "__pycache__", ".git", "node_modules"}
for root, dirs, files in os.walk("."):
    dirs[:] = [d for d in dirs if d not in skip]
    level = root.count(os.sep)
    if level > 3:
        continue
    p("  " * level + os.path.basename(root) + "/")
    for f in files:
        size = os.path.getsize(os.path.join(root, f)) / 1024
        p("  " * (level + 1) + f"{f}  ({size:,.0f} KB)")

db = "database/agriwater_v2.sqlite"
c = sqlite3.connect("file:" + db + "?mode=ro", uri=True)
p("\n===== SCHEMA =====")
for name, typ, sql in c.execute("SELECT name, type, sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY type, name"):
    p(f"\n-- [{typ}] {name}")
    p(sql)

p("\n===== ROW COUNTS =====")
for (name,) in c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall():
    n = c.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
    p(f"{name}: {n:,}")

p("\n===== SMALL TABLES CONTENT =====")
for t in ["rice_variety", "crop_water_parameter", "crop_calendar", "district", "season", "data_source"]:
    p(f"\n-- {t}")
    cur = c.execute(f'SELECT * FROM "{t}" LIMIT 20')
    p([d[0] for d in cur.description])
    for r in cur.fetchall():
        p(r)

out.close()
print("Done -> project_snapshot.txt")
