r"""
link_points_to_districts.py
بيربط نقاط grid_point بمراكز كفر الشيخ (ADM2) بدون أي مكتبات خارجية.

الوضع الافتراضي: معاينة فقط (dry-run)، مش بيكتب أي حاجة في القاعدة.
للتنفيذ الفعلي أضف --apply (وبيعمل نسخة احتياطية قبل الكتابة).

التشغيل:
    .\.venv\Scripts\python.exe link_points_to_districts.py
    .\.venv\Scripts\python.exe link_points_to_districts.py --apply
    .\.venv\Scripts\python.exe link_points_to_districts.py --include Mitubas --snap-km 5
    .\.venv\Scripts\python.exe link_points_to_districts.py --include Mitubas --snap-km 5 --apply
    (--include: يضيف مركز بالاسم حتى لو الفلتر استبعده. --snap-km: يربط النقطة البرانية
     بأقرب مركز مختار لو المسافة أقل من الرقم ده بالكيلومتر.)

بيدوّر لوحده على ملف *adm2*.geojson جوه data\raw\boundaries وعلى
kafr_el_sheikh_adm1.geojson في نفس الفولدر.
"""
import argparse
import csv
import json
import math
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

DB = Path("database/agriwater_v2.sqlite")
BOUNDS = Path("data/raw/boundaries")


# ---------- هندسة ----------
def rings_of(geom):
    """بيرجّع لكل polygon: (exterior_ring, [holes])."""
    t, c = geom["type"], geom["coordinates"]
    if t == "Polygon":
        return [(c[0], c[1:])]
    if t == "MultiPolygon":
        return [(p[0], p[1:]) for p in c]
    return []


def in_ring(x, y, ring):
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def in_geom(x, y, geom):
    for ext, holes in rings_of(geom):
        xs = [p[0] for p in ext]
        ys = [p[1] for p in ext]
        if not (min(xs) <= x <= max(xs) and min(ys) <= y <= max(ys)):
            continue
        if in_ring(x, y, ext) and not any(in_ring(x, y, h) for h in holes):
            return True
    return False


def bbox(geom):
    xs, ys = [], []
    for ext, _ in rings_of(geom):
        xs += [p[0] for p in ext]
        ys += [p[1] for p in ext]
    return min(xs), min(ys), max(xs), max(ys)


def ring_area_centroid(ring):
    a = cx = cy = 0.0
    for i in range(len(ring) - 1):
        x0, y0 = ring[i][0], ring[i][1]
        x1, y1 = ring[i + 1][0], ring[i + 1][1]
        cr = x0 * y1 - x1 * y0
        a += cr
        cx += (x0 + x1) * cr
        cy += (y0 + y1) * cr
    if a == 0:
        return 0.0, ring[0][0], ring[0][1]
    return abs(a) / 2, cx / (3 * a), cy / (3 * a)


def rep_point(geom):
    """نقطة جوه المركز نفسه (مش على حدوده)، بتمثّله."""
    ext = max((e for e, _ in rings_of(geom)), key=lambda r: ring_area_centroid(r)[0])
    _, cx, cy = ring_area_centroid(ext)
    if in_geom(cx, cy, geom):
        return cx, cy
    x0, y0, x1, y1 = bbox(geom)
    for i in range(1, 40):
        for j in range(1, 40):
            x, y = x0 + (x1 - x0) * i / 40, y0 + (y1 - y0) * j / 40
            if in_geom(x, y, geom):
                return x, y
    return None


def mostly_inside(feat_geom, parent_geom):
    """هل النقطة الممثلة للمركز جوه حدود المحافظة؟"""
    rp = rep_point(feat_geom)
    return rp is not None and in_geom(rp[0], rp[1], parent_geom)


KX = 111.0 * math.cos(math.radians(31.1))  # كم لكل درجة طول عند خط عرض كفر الشيخ
KY = 111.0


def _seg_km(px, py, ax, ay, bx, by):
    dx, dy = (bx - ax) * KX, (by - ay) * KY
    ex, ey = (px - ax) * KX, (py - ay) * KY
    L = dx * dx + dy * dy
    t = 0 if L == 0 else max(0, min(1, (ex * dx + ey * dy) / L))
    return math.hypot(ex - t * dx, ey - t * dy)


def dist_km(px, py, geom):
    best = 1e9
    for ext, _ in rings_of(geom):
        for i in range(len(ext) - 1):
            best = min(best, _seg_km(px, py, ext[i][0], ext[i][1], ext[i + 1][0], ext[i + 1][1]))
    return best


def load_features(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)["features"]


def pick_name(props):
    for k in ("shapeName", "name", "NAME_2", "ADM2_EN", "NAME"):
        if props.get(k):
            return str(props[k]).strip()
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--adm2", help="مسار ملف حدود المراكز ADM2 (geojson)")
    ap.add_argument("--adm1", help="مسار حدود كفر الشيخ ADM1 (geojson)")
    ap.add_argument("--include", action="append", default=[], help="اسم مركز يتضاف يدويًا (ممكن تكرره)")
    ap.add_argument("--snap-km", type=float, default=0.0,
                    help="اربط النقط البرانية بأقرب مركز مختار لو أقرب من كده (كم). الافتراضي 0 = مقفول")
    ap.add_argument("--apply", action="store_true", help="نفّذ التعديل فعلاً")
    a = ap.parse_args()

    adm2_path = Path(a.adm2) if a.adm2 else next(iter(sorted(BOUNDS.glob("*adm2*.geojson"))), None)
    adm1_path = Path(a.adm1) if a.adm1 else BOUNDS / "kafr_el_sheikh_adm1.geojson"
    if not adm2_path or not adm2_path.exists():
        sys.exit("مش لاقي ملف ADM2. حطه في data\\raw\\boundaries أو مرره بـ --adm2")
    if not adm1_path.exists():
        sys.exit(f"مش لاقي {adm1_path}")
    if not DB.exists():
        sys.exit(f"مش لاقي القاعدة: {DB.resolve()}")
    print(f"ADM2: {adm2_path}\nADM1: {adm1_path}\nDB  : {DB}\n")

    kes_feats = load_features(adm1_path)
    kes = {"type": "MultiPolygon",
           "coordinates": [p for f in kes_feats for p in
                           ([f["geometry"]["coordinates"]] if f["geometry"]["type"] == "Polygon"
                            else f["geometry"]["coordinates"])]}
    kb = bbox(kes)
    forced = {n.strip().lower() for n in a.include}

    # مراكز ADM2: اللي نقطتها الممثلة جوه كفر الشيخ + المضافة يدويًا. المضلعات بنفس الاسم بتتدمج.
    merged = {}   # name -> [geoms]
    forced_hit = set()
    for f in load_features(adm2_path):
        g = f.get("geometry")
        if not g:
            continue
        name = pick_name(f.get("properties", {})) or "UNNAMED"
        is_forced = name.lower() in forced
        if is_forced:
            forced_hit.add(name.lower())
        else:
            b = bbox(g)
            if b[2] < kb[0] or b[0] > kb[2] or b[3] < kb[1] or b[1] > kb[3]:
                continue
            if not mostly_inside(g, kes):
                continue
        merged.setdefault(name, []).append(g)
    for miss in sorted(forced - forced_hit):
        print(f"تنبيه: --include '{miss}' ملقتش له مضلع بنفس الاسم في ملف ADM2")
    if not merged:
        sys.exit("ولا مركز اتختار. اتأكد إن الملف لمصر ADM2 فعلاً.")

    print(f"المراكز المختارة: {len(merged)}")
    for n, gs in merged.items():
        tag = " (مضاف بـ --include)" if n.lower() in forced else ""
        extra = f" [{len(gs)} مضلعات اتدمجت]" if len(gs) > 1 else ""
        print(f"  - {n}{extra}{tag}")

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    gov = con.execute("SELECT district_id FROM district WHERE admin_level=1 AND name_en='Kafr El Sheikh'").fetchone()
    if not gov:
        sys.exit("مفيش صف كفر الشيخ (admin_level=1) في district")
    gov_id = gov["district_id"]
    points = con.execute("SELECT point_id, latitude, longitude FROM grid_point ORDER BY point_id").fetchall()

    plan, snapped, outside = [], [], []   # snapped: (pid, name, km)
    for p in points:
        x, y = p["longitude"], p["latitude"]
        hit = next((n for n, gs in merged.items() if any(in_geom(x, y, g) for g in gs)), None)
        if hit:
            plan.append((p["point_id"], hit))
            continue
        near_name, near_km = min(((n, min(dist_km(x, y, g) for g in gs)) for n, gs in merged.items()),
                                 key=lambda t: t[1])
        if a.snap_km > 0 and near_km <= a.snap_km:
            plan.append((p["point_id"], near_name))
            snapped.append((p["point_id"], near_name, near_km))
        else:
            outside.append((p["point_id"], near_name, near_km))

    inside_n = len(plan) - len(snapped)
    counts = {}
    for _, n in plan:
        counts[n] = counts.get(n, 0) + 1
    print("\n--- النقاط في كل مركز (شامل المربوطة بالأقرب) ---")
    for n in merged:
        print(f"  {n}: {counts.get(n, 0)} نقطة")
    print(f"\nجوه مضلع مركز: {inside_n}")
    if snapped:
        print(f"اتربطت بأقرب مركز (--snap-km {a.snap_km}): {len(snapped)}")
        for pid, n, km in snapped:
            print(f"    {pid} -> {n}  ({km:.1f} كم)")
    print(f"فضلت NULL: {len(outside)}")
    for pid, n, km in outside:
        print(f"    {pid}  أقرب مركز مختار: {n} ({km:.1f} كم)")

    if not a.apply:
        print("\nده معاينة بس. ولا حاجة اتكتبت. أضف --apply للتنفيذ.")
        return

    backup = DB.with_name(f"agriwater_v2_backup_{datetime.now():%Y%m%d_%H%M%S}.sqlite")
    con.close()
    shutil.copy2(DB, backup)
    print(f"\nنسخة احتياطية: {backup}")
    con = sqlite3.connect(DB)
    con.execute("PRAGMA foreign_keys = ON")
    try:
        with con:
            ids = {}
            for n in merged:
                con.execute("INSERT OR IGNORE INTO district (name_en, name_ar, admin_level, parent_id) "
                            "VALUES (?, NULL, 2, ?)", (n, gov_id))
                ids[n] = con.execute("SELECT district_id FROM district WHERE name_en=? AND admin_level=2",
                                     (n,)).fetchone()[0]
            for pid, n in plan:
                con.execute("UPDATE grid_point SET district_id=? WHERE point_id=?", (ids[n], pid))
        print("اتكتب.")
        print(f"foreign_key_check problems: {len(con.execute('PRAGMA foreign_key_check').fetchall())}")
        print(f"integrity_check: {con.execute('PRAGMA integrity_check').fetchone()[0]}")
    except Exception as e:
        print(f"حصل خطأ ولا حاجة اتغيرت: {e}\nالنسخة الاحتياطية: {backup}")
        raise
    finally:
        con.close()

    # تقرير بالنقاط المربوطة بالأقرب عشان تتراجع لاحقًا
    if snapped or outside:
        rep = Path("reports/district_join_report.csv")
        rep.parent.mkdir(exist_ok=True)
        with open(rep, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["point_id", "status", "district", "distance_km"])
            for pid, n, km in snapped:
                w.writerow([pid, "SNAPPED_TO_NEAREST", n, f"{km:.2f}"])
            for pid, n, km in outside:
                w.writerow([pid, "UNASSIGNED", n, f"{km:.2f}"])
        print(f"تقرير: {rep}")


if __name__ == "__main__":
    main()
