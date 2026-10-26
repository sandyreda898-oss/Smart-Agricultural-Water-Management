r"""
fill_vegetation_index.py
بيحسب NDVI وEVI لنقاط الـ38 من مشاهد Sentinel-2 المسجلة في القاعدة، ويكتبهم في vegetation_index.
مصدر الصور: Earth Search (AWS) المفتوح. مفيش حساب ولا مفتاح.

الضمانات:
  - بيشتغل افتراضيًا على مشاهد sentinel2_shortlist بس (119)، و --all للـ3775 كلهم.
  - نسخة احتياطية قبل أول كتابة، وبيكتب بعد كل مشهد، فلو وقف تكمل من حيث وقفت.
  - --dry-run: بيجرب ويطبع بس، ولا حاجة بتتكتب.
  - فشل أي مشهد مش بيوقف الباقي، وبيتسجل في reports\ndvi_failures.txt.

التركيب (مرة واحدة):
    .\.venv\Scripts\python.exe -m pip install rasterio numpy

أول تشغيل (تجربة على 3 مشاهد، من غير كتابة):
    .\.venv\Scripts\python.exe fill_vegetation_index.py --limit 3 --dry-run

التشغيل الفعلي:
    .\.venv\Scripts\python.exe fill_vegetation_index.py
"""
import argparse
import json
import shutil
import sqlite3
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

DB = Path("database/agriwater_v2.sqlite")
FAIL_LOG = Path("reports/ndvi_failures.txt")
API = "https://earth-search.aws.element84.com/v1"
COLLECTION = "sentinel-2-l2a"
VALID_SCL = (4, 5)               # 4 = نبات، 5 = تربة عارية. باقي الأكواد (سحاب، ظل، مية...) بتتستبعد
KFS_BBOX = [30.2, 30.8, 31.6, 31.8]
BASELINE_CHANGE = "2022-01-25"   # بعدها الـ DN فيه offset = -0.1 (لو الـ metadata ما قالش)


def http_json(url, body=None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data,
                                 headers={"Content-Type": "application/json", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def parse_bbox(raw):
    try:
        b = json.loads(raw) if isinstance(raw, str) else raw
        if isinstance(b, list) and len(b) == 4 and all(isinstance(v, (int, float)) for v in b):
            return b
    except (TypeError, ValueError):
        pass
    return None


def find_item(scene_id, acquired, tile, bbox):
    """بيدوّر على المشهد بالـ id، ولو مش لاقيه بيدوّر بالتاريخ والـ tile."""
    try:
        return http_json(f"{API}/collections/{COLLECTION}/items/{scene_id}")
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
    dt = datetime.strptime(acquired[:19], "%Y-%m-%dT%H:%M:%S")
    rng = f"{dt - timedelta(minutes=2):%Y-%m-%dT%H:%M:%SZ}/{dt + timedelta(minutes=2):%Y-%m-%dT%H:%M:%SZ}"
    body = {"collections": [COLLECTION], "datetime": rng, "limit": 20, "bbox": bbox or KFS_BBOX}
    feats = http_json(f"{API}/search", body).get("features", [])
    if tile:
        t = tile.upper().lstrip("T")
        feats = [f for f in feats if t in str(f["properties"].get("grid:code", "")).upper() or t in f["id"].upper()]
    return feats[0] if feats else None


def href(item, name):
    h = item["assets"][name]["href"]
    return h.replace("s3://sentinel-cogs/", "https://sentinel-cogs.s3.us-west-2.amazonaws.com/")


def scale_offset(item, name, acquired):
    rb = (item["assets"][name].get("raster:bands") or [{}])[0]
    default_off = -0.1 if acquired[:10] >= BASELINE_CHANGE else 0.0
    return rb.get("scale", 0.0001), rb.get("offset", default_off)


def indices(arr, so):
    """arr: dict red/nir/scl (+blue اختياري) بنفس الشكل. so: (scale, offset) لكل باند.
    بيرجّع (ndvi, evi, valid_pct)."""
    import numpy as np
    red = arr["red"].astype("float32") * so["red"][0] + so["red"][1]
    nir = arr["nir"].astype("float32") * so["nir"][0] + so["nir"][1]
    valid = np.isin(arr["scl"], VALID_SCL) & (arr["red"] > 0) & (arr["nir"] > 0) & ((nir + red) > 0)
    pct = 100.0 * float(valid.sum()) / valid.size
    if not valid.any():
        return None, None, round(pct, 1)
    ndvi = float(np.mean(((nir - red) / (nir + red))[valid]))
    evi = None
    if "blue" in arr:
        blue = arr["blue"].astype("float32") * so["blue"][0] + so["blue"][1]
        den = nir + 6 * red - 7.5 * blue + 1
        ok = valid & (np.abs(den) > 1e-6)
        if ok.any():
            evi = float(np.mean((2.5 * (nir - red) / den)[ok]))
    return round(ndvi, 4), (None if evi is None else round(evi, 4)), round(pct, 1)


def read_points(item, acquired, pts, buf_m, with_evi):
    import numpy as np
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.warp import transform
    from rasterio.windows import from_bounds

    names = ["red", "nir", "scl"] + (["blue"] if with_evi else [])
    so = {n: scale_offset(item, n, acquired) for n in names if n != "scl"}
    srcs = {n: rasterio.open(href(item, n)) for n in names}
    out = []
    try:
        ref = srcs["red"]
        n = max(3, int(round(2 * buf_m / 10)))
        for pid, lat, lon in pts:
            xs, ys = transform("EPSG:4326", ref.crs, [lon], [lat])
            x, y = xs[0], ys[0]
            b = ref.bounds
            if not (b.left <= x <= b.right and b.bottom <= y <= b.top):
                continue
            inside = (x - buf_m >= b.left and x + buf_m <= b.right and y - buf_m >= b.bottom and y + buf_m <= b.top)
            bounds = (x - buf_m, y - buf_m, x + buf_m, y + buf_m)
            arr = {}
            for nm, ds in srcs.items():
                w = from_bounds(*bounds, transform=ds.transform)
                arr[nm] = ds.read(1, window=w, out_shape=(n, n), resampling=Resampling.nearest,
                                  boundless=not inside, fill_value=0)
            ndvi, evi, pct = indices(arr, so)
            out.append((pid, ndvi, evi, pct))
    finally:
        for ds in srcs.values():
            ds.close()
    return out


def export_links(scenes, with_blue):
    """بيكتب روابط الباندات لكل مشهد. مفيش تحميل صور، بس استعلام صغير للكتالوج."""
    import csv
    bands = ["red", "nir", "scl"] + (["blue"] if with_blue else [])
    Path("reports").mkdir(exist_ok=True)
    rows, urls, failed = [], [], 0
    for i, (sid, acq, tile, bbox_raw) in enumerate(scenes, 1):
        try:
            item = find_item(sid, acq, tile, parse_bbox(bbox_raw))
            if item is None:
                raise RuntimeError("المشهد مش موجود في Earth Search")
            links = {b: href(item, b) for b in bands}
            rows.append([sid, acq, tile or ""] + [links[b] for b in bands])
            urls += list(links.values())
            if i % 10 == 0 or i == len(scenes):
                print(f"[{i}/{len(scenes)}] تمام")
        except Exception as e:
            failed += 1
            print(f"[{i}/{len(scenes)}] فشل {sid}: {type(e).__name__}: {e}")
    with open("reports/sentinel2_links.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["scene_id", "acquired_at", "tile_id"] + [f"{b}_url" for b in bands])
        w.writerows(rows)
    Path("reports/sentinel2_urls.txt").write_text("\n".join(urls), encoding="utf-8")
    print(f"\nمشاهد: {len(rows)} | فشلت: {failed} | روابط: {len(urls)}")
    print("الملفات: reports\\sentinel2_links.csv (جدول) و reports\\sentinel2_urls.txt (رابط في كل سطر لبرنامج تنزيل)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="كل المشاهد (3775) بدل الـ shortlist (119)")
    ap.add_argument("--limit", type=int, help="أول N مشهد بس (للتجربة)")
    ap.add_argument("--buffer-m", type=float, default=250, help="نصف ضلع مربع المتوسط حوالين النقطة بالمتر")
    ap.add_argument("--skip-evi", action="store_true")
    ap.add_argument("--redo", action="store_true", help="أعد حساب مشاهد موجودة")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--export-links", action="store_true",
                    help="بيطلّع روابط الصور بس (من غير تحميل أي صورة) في reports\\sentinel2_links.csv وsentinel2_urls.txt")
    a = ap.parse_args()

    if not a.export_links:
        try:
            import numpy  # noqa: F401
            import rasterio  # noqa: F401
        except ImportError:
            sys.exit("ناقص مكتبات. شغّل مرة واحدة:\n  .\\.venv\\Scripts\\python.exe -m pip install rasterio numpy")
    if not DB.exists():
        sys.exit(f"مش لاقي القاعدة: {DB.resolve()}")

    con = sqlite3.connect(DB)
    con.execute("PRAGMA foreign_keys = ON")
    pts = con.execute("SELECT point_id, latitude, longitude FROM grid_point ORDER BY point_id").fetchall()
    sql = ("SELECT s.scene_id, s.acquired_at, s.tile_id, s.bbox_json FROM sentinel2_scene s "
           + ("" if a.all else "JOIN sentinel2_shortlist h ON h.scene_id = s.scene_id ")
           + "ORDER BY s.acquired_at")
    scenes = con.execute(sql).fetchall()
    if not a.redo:
        done = {r[0] for r in con.execute("SELECT DISTINCT scene_id FROM vegetation_index")}
        scenes = [s for s in scenes if s[0] not in done]
    if a.limit:
        scenes = scenes[:a.limit]
    print(f"نقاط: {len(pts)} | مشاهد هتتعالج: {len(scenes)} | buffer: {a.buffer_m} م | "
          f"{'تجربة بدون كتابة' if a.dry_run else 'كتابة فعلية'}")
    if not scenes:
        print("مفيش مشاهد جديدة.")
        return

    if a.export_links:
        export_links(scenes, not a.skip_evi)
        con.close()
        return

    if not a.dry_run:
        backup = DB.with_name(f"agriwater_v2_backup_{datetime.now():%Y%m%d_%H%M%S}.sqlite")
        shutil.copy2(DB, backup)
        print(f"نسخة احتياطية: {backup}")

    import rasterio
    FAIL_LOG.parent.mkdir(exist_ok=True)
    stats = dict(scenes_ok=0, scenes_failed=0, rows=0, null_ndvi=0)
    env = dict(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",
               GDAL_HTTP_MAX_RETRY="3", GDAL_HTTP_RETRY_DELAY="2", GDAL_HTTP_TIMEOUT="60")
    with rasterio.Env(**env):
        for i, (sid, acq, tile, bbox_raw) in enumerate(scenes, 1):
            try:
                item = find_item(sid, acq, tile, parse_bbox(bbox_raw))
                if item is None:
                    raise RuntimeError("المشهد مش موجود في Earth Search")
                rows = read_points(item, acq, pts, a.buffer_m, not a.skip_evi)
                if not a.dry_run:
                    with con:
                        con.executemany(
                            "INSERT OR REPLACE INTO vegetation_index(point_id, scene_id, ndvi, evi, valid_pixel_pct) "
                            "VALUES (?,?,?,?,?)", [(p, sid, nd, ev, pc) for p, nd, ev, pc in rows])
                stats["scenes_ok"] += 1
                stats["rows"] += len(rows)
                stats["null_ndvi"] += sum(1 for r in rows if r[1] is None)
                good = [r for r in rows if r[1] is not None]
                avg = sum(r[1] for r in good) / len(good) if good else float("nan")
                print(f"[{i}/{len(scenes)}] {acq[:10]} {sid}: نقاط {len(rows)}، صالحة {len(good)}، متوسط NDVI {avg:.3f}")
                if a.dry_run and rows:
                    print("   عينة:", rows[:3])
            except Exception as e:
                stats["scenes_failed"] += 1
                msg = f"{datetime.now():%H:%M:%S} {sid} ({acq[:10]}): {type(e).__name__}: {e}"
                print(f"[{i}/{len(scenes)}] فشل: {msg}")
                with open(FAIL_LOG, "a", encoding="utf-8") as f:
                    f.write(msg + "\n")

    print("\n--- الخلاصة ---")
    print(f"مشاهد نجحت: {stats['scenes_ok']} | فشلت: {stats['scenes_failed']} | صفوف: {stats['rows']} "
          f"| صفوف بدون NDVI (سحاب/غير صالحة): {stats['null_ndvi']}")
    if not a.dry_run:
        print("\nمتوسط NDVI حسب الشهر (المفروض يعلى في موسم الأرز):")
        for m, avg, n in con.execute(
                "SELECT substr(s.acquired_at,6,2), ROUND(AVG(v.ndvi),3), COUNT(v.ndvi) FROM vegetation_index v "
                "JOIN sentinel2_scene s ON s.scene_id=v.scene_id WHERE v.ndvi IS NOT NULL GROUP BY 1 ORDER BY 1"):
            print(f"  شهر {m}: {avg}  ({n} قراءة)")
        print(f"foreign_key_check problems: {len(con.execute('PRAGMA foreign_key_check').fetchall())}")
        print(f"integrity_check: {con.execute('PRAGMA integrity_check').fetchone()[0]}")
    con.close()


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    main()
