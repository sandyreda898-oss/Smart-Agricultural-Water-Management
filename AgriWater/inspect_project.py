import os, sqlite3, glob, sys
sys.stdout.reconfigure(encoding="utf-8")
SKIP = {".venv", "__pycache__", ".git", "node_modules"}

def tree(path, depth=0, maxdepth=3):
    try:
        items = sorted(os.listdir(path))
    except Exception:
        return
    dirs = [i for i in items if os.path.isdir(os.path.join(path, i))]
    files = [i for i in items if os.path.isfile(os.path.join(path, i))]
    pad = "  " * depth
    shown = files[:25]
    for f in shown:
        kb = os.path.getsize(os.path.join(path, f)) / 1024
        print(f"{pad}{f}  ({kb:.0f} KB)")
    if len(files) > 25:
        print(f"{pad}... و {len(files) - 25} ملف تاني")
    for d in dirs:
        if d in SKIP:
            print(f"{pad}[{d}/] (متخطي)")
            continue
        print(f"{pad}[{d}/]")
        if depth < maxdepth:
            tree(os.path.join(path, d), depth + 1, maxdepth)

print("=" * 60, "\nهيكل المشروع\n" + "=" * 60)
tree(".")

print("\n" + "=" * 60, "\nسكريبتات بايثون (أول سطر توثيق/تعليق)\n" + "=" * 60)
for p in sorted(glob.glob("**/*.py", recursive=True)):
    if any(s in p.split(os.sep) for s in SKIP):
        continue
    try:
        with open(p, encoding="utf-8", errors="ignore") as f:
            lines = f.read().splitlines()
        first = next((l.strip() for l in lines if l.strip().startswith(('"""', "#", "'''"))), "")
        print(f"{p}  [{len(lines)} سطر]  {first[:90]}")
    except Exception as e:
        print(p, "خطأ", e)

dbs = [d for d in glob.glob("database/*.sqlite") if "backup" not in d.lower()]
print("\n" + "=" * 60, "\nقاعدة البيانات:", dbs, "\n" + "=" * 60)
for db in dbs:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    cur = con.cursor()
    objs = cur.execute("select type,name from sqlite_master where type in ('table','view') and name not like 'sqlite_%' order by type,name").fetchall()
    for typ, name in objs:
        cols = cur.execute(f'pragma table_info("{name}")').fetchall()
        try:
            n = cur.execute(f'select count(*) from "{name}"').fetchone()[0]
        except Exception as e:
            n = f"خطأ {e}"
        print(f"\n--- {typ} {name}  ({n} صف)")
        print("   الأعمدة:", ", ".join(f"{c[1]} {c[2]}" for c in cols))
        if isinstance(n, int) and n > 0:
            for r in cur.execute(f'select * from "{name}" limit 2').fetchall():
                print("   عيّنة:", str(r)[:220])
    con.close()
