import os, json, csv, struct, pyodbc

root = os.getcwd()
raster = os.path.join(os.environ["USERPROFILE"], "Downloads", "HWSD2_RASTER_TEMP", "HWSD2.bil")
grid = os.path.join(root, "data", "metadata", "sample_grid.geojson")
db = os.path.join(os.environ["USERPROFILE"], "Downloads", "HWSD2_DB_TEMP", "HWSD2.mdb")
outdir = os.path.join(root, "data", "processed")
out = os.path.join(outdir, "hwsd2_soil_samples.csv")

with open(grid, encoding="utf-8") as f:
    features = json.load(f)["features"]

x0, y0, step = -179.995833333333, 89.9958333333333, 0.00833333333333333
rowbytes = 86400
records = []

with open(raster, "rb") as f:
    for feature in features:
        p = feature["properties"]
        lon, lat = feature["geometry"]["coordinates"]
        col = round((lon - x0) / step)
        row = round((y0 - lat) / step)
        if not (0 <= col < 43200 and 0 <= row < 21600):
            raise ValueError(f"Coordinates outside raster: {p.get('point_id')}")
        f.seek(row * rowbytes + col * 2)
        raw = f.read(2)
        if len(raw) != 2:
            raise IOError("Could not read raster cell")
        smu = struct.unpack("<H", raw)[0]
        records.append({
            "point_id": p.get("point_id"),
            "longitude": lon,
            "latitude": lat,
            "raster_row": row,
            "raster_col": col,
            "HWSD2_SMU_ID": smu,
            "nodata": smu == 65535
        })

conn = pyodbc.connect(
    r"DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=" + db
)
cur = conn.cursor()
cur.execute("""
    SELECT HWSD2_SMU_ID, TOPDEP, BOTDEP, SAND, SILT, CLAY,
           BULK, ORG_CARBON, PH_WATER, TEXTURE_USDA, TEXTURE_SOTER
    FROM HWSD2_LAYERS
    WHERE LAYER='D1'
""")
soil = {}
for r in cur.fetchall():
    soil[int(r[0])] = {
        "top_depth_cm": r[1], "bottom_depth_cm": r[2],
        "sand_pct": r[3], "silt_pct": r[4], "clay_pct": r[5],
        "bulk": r[6], "organic_carbon": r[7], "ph_water": r[8],
        "texture_usda": r[9], "texture_soter": r[10]
    }
conn.close()

for rec in records:
    smu = rec["HWSD2_SMU_ID"]
    rec.update(soil.get(smu, {}))
    rec["match_found"] = smu in soil and smu != 65535

os.makedirs(outdir, exist_ok=True)
fields = list(dict.fromkeys(k for r in records for k in r))
with open(out, "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    writer.writerows(records)

print("Sample points:", len(records))
print("Raster NoData points:", sum(r["nodata"] for r in records))
print("Database matches:", sum(r["match_found"] for r in records))
print("Unique soil IDs:", len(set(r["HWSD2_SMU_ID"] for r in records)))
print("Output:", out)
print("First 5 results:")
for r in records[:5]:
    print(r)
