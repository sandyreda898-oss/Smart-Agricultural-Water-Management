r"""
diagnose_district_join.py   (قراءة فقط، مبيكتبش حاجة)
بيشرح ليه نقاط فضلت برة المراكز، وبيعرض مضلعات ADM2 القريبة من كفر الشيخ.

التشغيل:
    .\.venv\Scripts\python.exe diagnose_district_join.py
"""
import math
import sqlite3
from pathlib import Path

from link_points_to_districts import (
    BOUNDS, DB, bbox, in_geom, load_features, pick_name, rep_point, ring_area_centroid, rings_of,
)

KX = 111.0 * math.cos(math.radians(31.1))  # كم لكل درجة طول
KY = 111.0


def seg_dist_km(px, py, ax, ay, bx, by):
    dx, dy = (bx - ax) * KX, (by - ay) * KY
    ex, ey = (px - ax) * KX, (py - ay) * KY
    L = dx * dx + dy * dy
    t = 0 if L == 0 else max(0, min(1, (ex * dx + ey * dy) / L))
    return math.hypot(ex - t * dx, ey - t * dy)


def dist_to_geom_km(px, py, geom):
    best = 1e9
    for ext, _ in rings_of(geom):
        for i in range(len(ext) - 1):
            best = min(best, seg_dist_km(px, py, ext[i][0], ext[i][1], ext[i + 1][0], ext[i + 1][1]))
    return best


def approx_area_km2(geom):
    return sum(ring_area_centroid(e)[0] for e, _ in rings_of(geom)) * KX * KY


adm2_path = next(iter(sorted(BOUNDS.glob("*adm2*.geojson"))))
adm1_path = BOUNDS / "kafr_el_sheikh_adm1.geojson"
kes_feats = load_features(adm1_path)
kes = {"type": "MultiPolygon",
       "coordinates": [p for f in kes_feats for p in
                       ([f["geometry"]["coordinates"]] if f["geometry"]["type"] == "Polygon"
                        else f["geometry"]["coordinates"])]}
kb = bbox(kes)
print(f"حدود كفر الشيخ ADM1: lon {kb[0]:.3f}..{kb[2]:.3f}  lat {kb[1]:.3f}..{kb[3]:.3f}\n")

near = []
for f in load_features(adm2_path):
    g = f.get("geometry")
    if not g:
        continue
    b = bbox(g)
    if b[2] < kb[0] or b[0] > kb[2] or b[3] < kb[1] or b[1] > kb[3]:
        continue
    rp = rep_point(g)
    inside = bool(rp and in_geom(rp[0], rp[1], kes))
    near.append((pick_name(f.get("properties", {})) or "UNNAMED", g, inside, rp))

print("=== (أ) مضلعات ADM2 اللي مربعها بيتقاطع مع كفر الشيخ ===")
print(f"{'الاسم':28} {'جوه كفر الشيخ؟':15} {'المساحة كم2':>12}  النقطة الممثلة (lon, lat)")
for n, g, ins, rp in sorted(near, key=lambda x: (not x[2], x[0])):
    rps = f"({rp[0]:.3f}, {rp[1]:.3f})" if rp else "-"
    print(f"{n:28} {'نعم' if ins else 'لا':15} {approx_area_km2(g):12.0f}  {rps}")

con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
pts = con.execute("SELECT point_id, latitude, longitude FROM grid_point ORDER BY point_id").fetchall()
unassigned = []
for pid, lat, lon in pts:
    if not any(ins and in_geom(lon, lat, g) for _, g, ins, _ in near):
        unassigned.append((pid, lat, lon))

print(f"\n=== (ب) النقاط البرانية ({len(unassigned)}) ===")
print(f"{'النقطة':10} {'lat':>8} {'lon':>8}  {'جوه ADM1؟':10} أقرب مركز (أي مضلع) / المسافة كم")
for pid, lat, lon in unassigned:
    in_kes = in_geom(lon, lat, kes)
    d = sorted((dist_to_geom_km(lon, lat, g), n, ins) for n, g, ins, _ in near)[0]
    d_kes_border = dist_to_geom_km(lon, lat, kes)
    print(f"{pid:10} {lat:8.3f} {lon:8.3f}  {'نعم' if in_kes else 'لا':10} "
          f"{d[1]} ({'جوه' if d[2] else 'برة'} الفلتر) / {d[0]:.1f} كم   [حد ADM1: {d_kes_border:.1f} كم]")
