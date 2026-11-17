"""
Phase 1 - Dataset inspection.
Builds dataset_inventory.xlsx and data_dictionary.xlsx.

How to run (from the folder that contains the "AgriWater" folder):
    python phase1_inventory.py

It reads the SQLite database if the real file is there; otherwise it
falls back to the CSV files in AgriWater/data/processed and tells you so.
Raw files are only READ, never changed.
"""
import re
import sqlite3
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
AGRI = ROOT / "AgriWater"
DB = AGRI / "database" / "agriwater_v2.sqlite"
CSV_DIR = AGRI / "data" / "processed"
OUT = ROOT / "machine_learning" / "reports"
OUT.mkdir(parents=True, exist_ok=True)

UNIT_HINTS = [
    (r"m3_per_feddan", "m3/feddan"), (r"_mm_day", "mm/day"), (r"_mm", "mm"),
    (r"_c(_|$)|temperature|^t2m|tmin|tmax", "degC"), (r"_pct|percent", "%"),
    (r"wind", "m/s"), (r"solar|radiation", "MJ/m2/day"), (r"pressure", "kPa"),
    (r"ton_per_feddan", "ton/feddan"), (r"_cm", "cm"), (r"latitude|longitude", "degrees"),
    (r"bulk", "g/cm3 (verify)"), (r"organic_carbon", "% (verify)"),
]


def guess_unit(col):
    for pat, unit in UNIT_HINTS:
        if re.search(pat, col.lower()):
            return unit
    return ""


def time_coverage(df):
    for c in df.columns:
        lc = c.lower()
        if any(k in lc for k in ("date", "time")):
            d = pd.to_datetime(df[c], errors="coerce")
            if d.notna().any():
                return f"{d.min().date()} -> {d.max().date()}"
    for c in df.columns:
        if c.lower() in ("year", "season_year", "study_year"):
            y = pd.to_numeric(df[c], errors="coerce").dropna()
            if len(y):
                return f"{int(y.min())} -> {int(y.max())}"
    return ""


def geo_coverage(df):
    lat = next((c for c in df.columns if c.lower() in ("latitude", "lat")), None)
    lon = next((c for c in df.columns if c.lower() in ("longitude", "lon")), None)
    parts = []
    if "point_id" in df.columns:
        parts.append(f"{df['point_id'].nunique()} grid points")
    if lat and lon:
        la = pd.to_numeric(df[lat], errors="coerce")
        lo = pd.to_numeric(df[lon], errors="coerce")
        if la.notna().any() and lo.notna().any():
            parts.append(f"lat {la.min():.2f}-{la.max():.2f}, lon {lo.min():.2f}-{lo.max():.2f}")
    return "; ".join(parts)


def suitability(name):
    n = name.lower()
    if "water_scenario" in n or "scenario" in n:
        return "UNSUITABLE as target (calculated scenario, not measured irrigation)"
    if "daily_water_demand" in n or "etc_" in n or "et0" in n:
        return "UNCERTAIN (calculated from weather - leakage risk if used with a derived target)"
    if "literature" in n or "trial" in n or "moursi" in n or "darwesh" in n or "ghazy" in n \
            or "eid_" in n or "abou_el" in n or "sakha" in n:
        return "UNCERTAIN (published station trial, small, not farm data)"
    if "sentinel" in n:
        return "UNSUITABLE for ML component (satellite = Deep Learning member)"
    return "REVIEW (decide manually)"


def load_sources():
    """Yield (name, source_label, dataframe, pk, fk)."""
    if DB.exists() and DB.stat().st_size > 1_000_000:
        print(f"Using real database: {DB}")
        con = sqlite3.connect(DB)
        # Small text file with every table definition (keys included) - easy to share.
        sql_rows = con.execute("select sql from sqlite_master where sql is not null").fetchall()
        (OUT / "db_schema.sql").write_text(";\n\n".join(r[0] for r in sql_rows) + ";\n", encoding="utf-8")
        tables = pd.read_sql("select name from sqlite_master where type='table'", con)["name"]
        for t in tables:
            df = pd.read_sql(f'select * from "{t}"', con)
            info = pd.read_sql(f'PRAGMA table_info("{t}")', con)
            fks = pd.read_sql(f'PRAGMA foreign_key_list("{t}")', con)
            pk = ", ".join(info.loc[info["pk"] > 0, "name"])
            fk = "; ".join(f"{r['from']}->{r['table']}.{r['to']}" for _, r in fks.iterrows())
            yield t, "agriwater_v2.sqlite", df, pk, fk
        con.close()
        return
    print("WARNING: the real .sqlite file was not found (or is only a tiny Git-LFS placeholder).")
    print("Falling back to CSV files in", CSV_DIR)
    print("Download the real database to get the table-level inventory (see instructions).")
    for f in sorted(CSV_DIR.glob("*.csv")):
        if "_OLD_" in f.name or f.stat().st_size < 1000 and f.read_text(errors="ignore").startswith("version https"):
            continue
        try:
            df = pd.read_csv(f, encoding="utf-8-sig", low_memory=False)
        except Exception as e:  # keep going, report it
            print("  could not read", f.name, e)
            continue
        yield f.stem, f"data/processed/{f.name}", df, "", ""


def main():
    if not AGRI.exists():
        sys.exit("Put this script in the folder that contains 'AgriWater' and run it again.")
    inv, dic = [], []
    for name, src, df, pk, fk in load_sources():
        n = len(df)
        miss_total = int(df.isna().sum().sum())
        inv.append({
            "Dataset Name": name, "Source": src, "Number of Records": n,
            "Number of Features": df.shape[1], "Description": "",
            "Units": "; ".join(sorted({u for u in (guess_unit(c) for c in df.columns) if u})),
            "Missing Values": f"{miss_total} ({miss_total / max(df.size, 1) * 100:.1f}%)",
            "Time Coverage": time_coverage(df), "Geographic Coverage": geo_coverage(df),
            "ML Suitability": suitability(name),
            "Notes": "", "Exact duplicate rows": int(df.astype(str).duplicated().sum()) if n < 300000 else "skipped (large)",
            "Primary key": pk, "Foreign keys": fk,
        })
        for c in df.columns:
            s = df[c]
            num = pd.to_numeric(s, errors="coerce")
            is_num = num.notna().sum() > 0.9 * s.notna().sum() and s.notna().any()
            dic.append({
                "Dataset": name, "Column": c, "Data Type": str(s.dtype),
                "Missing %": round(s.isna().mean() * 100, 2), "Unique values": int(s.nunique()),
                "Example": "" if s.dropna().empty else str(s.dropna().iloc[0])[:60],
                "Min": num.min() if is_num else "", "Max": num.max() if is_num else "",
                "Unit (guessed - verify)": guess_unit(c), "Meaning": "", "Source": src,
            })
        print(f"  {name}: {n} rows, {df.shape[1]} cols")

    pd.DataFrame(inv).to_excel(OUT / "dataset_inventory.xlsx", index=False)
    pd.DataFrame(dic).to_excel(OUT / "data_dictionary.xlsx", index=False)
    print("\nDone. Files written to:", OUT)


if __name__ == "__main__":
    main()
