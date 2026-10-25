r"""
import_field_survey.py
بيدخل إجابات استبيان الفلاحين في القاعدة (field, field_season, crop_history, pump_type,
irrigation_event) بعد ما يتحقق منها. طريقة الري لازم تكون من المسجلة في irrigation_method.

الوضع الافتراضي: معاينة (dry-run). بيجرب الدخول كله وبعدين بيتراجع، فمفيش حاجة بتتكتب.
للتنفيذ الفعلي أضف --apply (وبيعمل نسخة احتياطية الأول).
لو في أي خطأ في أي صف، مفيش حاجة بتدخل خالص. التحذيرات مش بتمنع الدخول.

التشغيل:
    .\.venv\Scripts\python.exe import_field_survey.py --csv data\field_survey\responses.csv
    .\.venv\Scripts\python.exe import_field_survey.py --csv responses.csv --events events.csv --apply

الصفوف اللي كود الحقل فيها بيبدأ بـ EXAMPLE بتتخطى.
"""
import argparse
import csv
import json
import math
import re
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

DB = Path("database/agriwater_v2.sqlite")
SCHEMA = Path("data/metadata/field_survey_schema.json")
ARABIC = re.compile(r"[\u0600-\u06FF]")
DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩٫٬", "0123456789.,")
# حدود تقريبية لكفر الشيخ مع هامش. أي حقل برة كده غالبًا إحداثياته مقلوبة أو غلط.
LAT_RANGE, LON_RANGE = (30.8, 31.8), (30.2, 31.6)
KX, KY = 111.0 * math.cos(math.radians(31.1)), 111.0


def norm(s):
    return " ".join(str(s).strip().split()).casefold()


def parse(raw, col):
    """بيرجّع (قيمة, خطأ)."""
    v = (raw or "").strip()
    if v == "":
        return None, None
    t = col["type"]
    try:
        if t == "int":
            return int(float(v.translate(DIGITS).replace(",", "."))), None
        if t == "float":
            return float(v.translate(DIGITS).replace(",", ".")), None
        if t == "date":
            v = v.translate(DIGITS)
            datetime.strptime(v, "%Y-%m-%d")
            return v, None
        if t == "enum":
            lv = v.lower()
            if lv not in col["allowed"]:
                return None, f"{col['name']}='{v}' مش من القيم المسموحة {col['allowed']}"
            return lv, None
    except ValueError:
        return None, f"{col['name']}='{v}' مش {t} صحيح" + (" (الصيغة YYYY-MM-DD)" if t == "date" else "")
    return v, None


def read_rows(path, cols, label):
    names = [c["name"] for c in cols]
    errs, warns, rows = [], [], []
    with open(path, newline="", encoding="utf-8-sig") as f:
        rd = csv.DictReader(f)
        head = [h.strip() for h in (rd.fieldnames or [])]
        miss = [n for n in names if n not in head and next(c for c in cols if c["name"] == n)["required"]]
        if miss:
            sys.exit(f"[{label}] أعمدة مطلوبة ناقصة في الهيدر: {miss}")
        extra = [h for h in head if h not in names]
        if extra:
            warns.append(f"[{label}] أعمدة مش معروفة هتتجاهل: {extra}")
        for raw in rd:
            raw = {(k or "").strip(): v for k, v in raw.items()}
            ln = rd.line_num
            if str(raw.get("farmer_code", "")).strip().upper().startswith("EXAMPLE"):
                continue
            if not any((v or "").strip() for v in raw.values()):
                continue
            row, rerr = {"_line": ln}, []
            for c in cols:
                val, e = parse(raw.get(c["name"]), c)
                if e:
                    rerr.append(e)
                elif val is None and c["required"]:
                    rerr.append(f"{c['name']} مطلوب وفاضي")
                row[c["name"]] = val
            errs += [f"[{label}] سطر {ln}: {e}" for e in rerr]
            rows.append(row)
    return rows, errs, warns


def check_main_row(r, errs, warns):
    ln, add = r["_line"], lambda m: errs.append(f"[survey] سطر {r['_line']}: {m}")
    if r["area_feddan"] is not None and r["area_feddan"] <= 0:
        add("area_feddan لازم يكون أكبر من صفر")
    if r["latitude"] is not None and not (LAT_RANGE[0] <= r["latitude"] <= LAT_RANGE[1]):
        add(f"latitude={r['latitude']} برة كفر الشيخ (جرب تتأكد إن خط العرض والطول مش مقلوبين)")
    if r["longitude"] is not None and not (LON_RANGE[0] <= r["longitude"] <= LON_RANGE[1]):
        add(f"longitude={r['longitude']} برة كفر الشيخ")
    if r["season_year"] is not None and not (2000 <= r["season_year"] <= 2100):
        add("season_year مش منطقي")
    ds = [r[k] for k in ("sowing_date", "transplanting_date", "harvest_date") if r[k]]
    if ds != sorted(ds):
        add("ترتيب التواريخ غلط (لازم البذر ≤ الشتل ≤ الحصاد)")
    if r["total_irrigation_m3_per_feddan"] is not None:
        if r["total_irrigation_m3_per_feddan"] <= 0:
            add("total_irrigation_m3_per_feddan لازم > 0")
        if not r["measurement_method"]:
            add("measurement_method مطلوب لما تكتب إجمالي الري")
        elif not (2000 <= r["total_irrigation_m3_per_feddan"] <= 20000):
            warns.append(f"[survey] سطر {ln}: إجمالي الري {r['total_irrigation_m3_per_feddan']} م3/فدان خارج 2000–20000، راجعه")
    y = r["harvest_yield_ton_per_feddan"]
    if y is not None:
        if y <= 0:
            add("harvest_yield_ton_per_feddan لازم > 0")
        elif not (1 <= y <= 8):
            warns.append(f"[survey] سطر {ln}: الإنتاجية {y} طن/فدان خارج 1–8، راجعها")
    if r["cultivated_area_feddan"] is not None and r["area_feddan"] and r["cultivated_area_feddan"] > r["area_feddan"] * 1.001:
        add("المساحة المزروعة أكبر من مساحة القطعة")
    for n in (1, 2, 3):
        if r[f"prev_crop_{n}"] and r[f"prev_crop_{n}_year"] is None:
            add(f"prev_crop_{n}_year مطلوب لما تكتب اسم المحصول")


def lookup(con, table, id_col, cols, value):
    v = norm(value)
    for row in con.execute(f"SELECT {id_col}, {', '.join(cols)} FROM {table}"):
        if any(row[i + 1] and norm(row[i + 1]) == v for i in range(len(cols))):
            return row[0]
    return None


def lookup_crop_code(con, value):
    """Normalize a farmer-entered crop label to the canonical reference code."""
    if not con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='crop_reference'").fetchone():
        return None
    v = norm(value)
    for row in con.execute("SELECT crop_code,name_en,name_ar,aliases_ar,aliases_en FROM crop_reference"):
        labels = [row[1], row[2]]
        labels += (row[3] or "").split(";")
        labels += (row[4] or "").split(";")
        if any(norm(label) == v for label in labels if label):
            return row[0]
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True, help="ملف إجابات الاستبيان")
    ap.add_argument("--events", help="ملف الريّات (اختياري)")
    ap.add_argument("--schema", default=str(SCHEMA))
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    if not DB.exists():
        sys.exit(f"مش لاقي القاعدة: {DB.resolve()}")
    schema = json.load(open(a.schema, encoding="utf-8"))

    rows, errs, warns = read_rows(a.csv, schema["columns"], "survey")
    evrows = []
    if a.events:
        evrows, e2, w2 = read_rows(a.events, schema["irrigation_events_columns"], "events")
        errs += e2
        warns += w2
    seen = {}
    for r in rows:
        check_main_row(r, errs, warns)
        k = (r["farmer_code"], r["season_year"])
        if k in seen:
            errs.append(f"[survey] سطر {r['_line']}: نفس (farmer_code, season_year) موجود في سطر {seen[k]}")
        seen[k] = r["_line"]
    for r in evrows:
        if r["volume_m3"] is not None and r["volume_m3"] < 0:
            errs.append(f"[events] سطر {r['_line']}: volume_m3 سالب")
        if r["duration_hours"] is not None and r["duration_hours"] < 0:
            errs.append(f"[events] سطر {r['_line']}: duration_hours سالب")

    if a.apply and not errs:
        backup = DB.with_name(f"agriwater_v2_backup_{datetime.now():%Y%m%d_%H%M%S}.sqlite")
        shutil.copy2(DB, backup)  # قبل أي كتابة
        print(f"نسخة احتياطية: {backup}")
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    stats = dict(fields_new=0, fields_existing=0, fs_new=0, fs_skipped=0, seasons_new=[], pumps_new=[],
                 methods_new=[], crops=0, events_new=0, events_skipped=0)
    try:
        points = con.execute("SELECT point_id, latitude, longitude FROM grid_point").fetchall()
        for r in rows:
            ln = r["_line"]
            did = lookup(con, "district", "district_id", ["name_en", "name_ar"], r["district"]) if r["district"] else None
            if r["district"] and did is None:
                valid = [x[0] for x in con.execute("SELECT name_ar FROM district WHERE admin_level=2")]
                errs.append(f"[survey] سطر {ln}: المركز '{r['district']}' مش موجود. المتاح: {valid}")
            vid = lookup(con, "rice_variety", "variety_id", ["name_en", "name_ar"], r["variety"]) if r["variety"] else None
            if r["variety"] and vid is None:
                valid = [x[0] for x in con.execute("SELECT name_ar FROM rice_variety WHERE name_ar IS NOT NULL")]
                errs.append(f"[survey] سطر {ln}: الصنف '{r['variety']}' مش موجود. المتاح: {valid}")
            if did is None or vid is None or r["latitude"] is None or r["longitude"] is None:
                continue
            near = min(points, key=lambda p: math.hypot((p["longitude"] - r["longitude"]) * KX,
                                                        (p["latitude"] - r["latitude"]) * KY))
            km = math.hypot((near["longitude"] - r["longitude"]) * KX, (near["latitude"] - r["latitude"]) * KY)
            if km > 15:
                warns.append(f"[survey] سطر {ln}: أقرب نقطة طقس {near['point_id']} على بعد {km:.0f} كم")

            if not con.execute("SELECT 1 FROM season WHERE season_year=?", (r["season_year"],)).fetchone():
                y = r["season_year"]
                con.execute("INSERT INTO season(season_year,start_date,end_date) VALUES (?,?,?)",
                            (y, f"{y}-05-10", f"{y}-10-31"))
                stats["seasons_new"].append(y)

            f = con.execute("SELECT field_id, area_feddan, latitude, longitude FROM field WHERE farmer_consent_id=?",
                            (r["farmer_code"],)).fetchone()
            if f:
                fid = f["field_id"]
                stats["fields_existing"] += 1
                if (abs((f["area_feddan"] or 0) - r["area_feddan"]) > 1e-6
                        or abs((f["latitude"] or 0) - r["latitude"]) > 1e-3
                        or abs((f["longitude"] or 0) - r["longitude"]) > 1e-3):
                    warns.append(f"[survey] سطر {ln}: الحقل {r['farmer_code']} موجود بمساحة/إحداثيات مختلفة، مش هعدّل المخزن")
            else:
                fid = con.execute(
                    "INSERT INTO field(point_id,district_id,area_feddan,latitude,longitude,farmer_consent_id) "
                    "VALUES (?,?,?,?,?,?)",
                    (near["point_id"], did, r["area_feddan"], r["latitude"], r["longitude"], r["farmer_code"])).lastrowid
                stats["fields_new"] += 1

            mid = lookup(con, "irrigation_method", "method_id", ["name_en", "name_ar"], r["irrigation_method"])
            if mid is None:
                valid = [f"{x[0]} / {x[1]}" for x in con.execute("SELECT name_ar, name_en FROM irrigation_method")]
                errs.append(f"[survey] سطر {ln}: طريقة الري '{r['irrigation_method']}' مش موجودة. المتاح: {valid}")
                continue
            pid = lookup(con, "pump_type", "pump_id", ["name_en", "name_ar"], r["pump_type"])
            if pid is None:
                pid = con.execute(
                    "INSERT INTO pump_type(name_en,name_ar,power_hp,discharge_m3_per_hour,fuel_type) VALUES (?,?,?,?,?)",
                    (r["pump_type"], r["pump_type"] if ARABIC.search(r["pump_type"]) else None,
                     r["pump_power_hp"], r["pump_discharge_m3_per_hour"], r["pump_fuel_type"])).lastrowid
                stats["pumps_new"].append(r["pump_type"])

            if con.execute("SELECT 1 FROM field_season WHERE field_id=? AND season_year=?", (fid, r["season_year"])).fetchone():
                stats["fs_skipped"] += 1
                warns.append(f"[survey] سطر {ln}: {r['farmer_code']} موسم {r['season_year']} موجود قبل كده، اتخطى (مش بيتعدّل)")
            else:
                con.execute(
                    "INSERT INTO field_season(field_id,season_year,variety_id,irrigation_method_id,pump_id,establishment_method,sowing_date,"
                    "transplanting_date,harvest_date,cultivated_area_feddan,total_irrigation_m3_per_feddan,"
                    "harvest_yield_ton_per_feddan,measurement_method,data_collector,source_notes) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (fid, r["season_year"], vid, mid, pid, r["establishment_method"], r["sowing_date"], r["transplanting_date"], r["harvest_date"],
                     r["cultivated_area_feddan"], r["total_irrigation_m3_per_feddan"], r["harvest_yield_ton_per_feddan"],
                     r["measurement_method"], r["data_collector"], r["source_notes"]))
                stats["fs_new"] += 1
            for n in (1, 2, 3):
                if r[f"prev_crop_{n}"]:
                    crop_name = r[f"prev_crop_{n}"]
                    crop_code = lookup_crop_code(con, crop_name)
                    if crop_code is None:
                        warns.append(f"[survey] سطر {ln}: اسم المحصول السابق '{crop_name}' محفوظ كما أدخله المستخدم لكنه غير موجود بعد في قاموس crop_reference")
                    cur = con.execute(
                        "INSERT OR IGNORE INTO crop_history(field_id,season_year,season_type,crop_name,crop_code) VALUES (?,?,?,?,?)",
                        (fid, r[f"prev_crop_{n}_year"], r[f"prev_crop_{n}_season"], crop_name, crop_code))
                    stats["crops"] += cur.rowcount

        for r in evrows:
            fs = con.execute(
                "SELECT fs.field_season_id FROM field_season fs JOIN field f ON f.field_id=fs.field_id "
                "WHERE f.farmer_consent_id=? AND fs.season_year=?", (r["farmer_code"], r["season_year"])).fetchone()
            if not fs:
                errs.append(f"[events] سطر {r['_line']}: مفيش موسم لـ {r['farmer_code']} سنة {r['season_year']}")
                continue
            dup = con.execute(
                "SELECT 1 FROM irrigation_event WHERE field_season_id=? AND event_date=? AND IFNULL(volume_m3,-1)=IFNULL(?, -1) "
                "AND IFNULL(duration_hours,-1)=IFNULL(?, -1)",
                (fs[0], r["event_date"], r["volume_m3"], r["duration_hours"])).fetchone()
            if dup:
                stats["events_skipped"] += 1
                continue
            con.execute("INSERT INTO irrigation_event(field_season_id,event_date,volume_m3,duration_hours,measurement_method) "
                        "VALUES (?,?,?,?,?)",
                        (fs[0], r["event_date"], r["volume_m3"], r["duration_hours"], r["measurement_method"]))
            stats["events_new"] += 1

        for w in warns:
            print("تحذير:", w)
        if errs:
            con.rollback()
            print(f"\nفي {len(errs)} خطأ. ولا حاجة اتكتبت:")
            for e in errs:
                print("  خطأ:", e)
            sys.exit(1)

        print(f"\nصفوف الاستبيان: {len(rows)} | ريّات: {len(evrows)}")
        print(f"حقول جديدة: {stats['fields_new']} | حقول موجودة: {stats['fields_existing']}")
        print(f"مواسم حقل جديدة: {stats['fs_new']} | اتخطت (موجودة): {stats['fs_skipped']}")
        print(f"محاصيل سابقة جديدة: {stats['crops']} | ريّات جديدة: {stats['events_new']} (اتخطت {stats['events_skipped']})")
        for k, lbl in (("pumps_new", "أنواع ماكينات جديدة"), ("seasons_new", "سنوات موسم جديدة")):
            if stats[k]:
                print(f"{lbl}: {sorted(set(stats[k]))}")
        if stats["seasons_new"]:
            print("  تنبيه: مفيش طقس NASA POWER في القاعدة للسنين دي لسه.")
        if stats["pumps_new"]:
            print("  راجع الأسماء الجديدة: أي غلطة إملائية بتعمل نوع مكرر.")

        if not a.apply:
            con.rollback()
            print("\nده معاينة بس. ولا حاجة اتكتبت. أضف --apply للتنفيذ.")
            return
        con.commit()
    except SystemExit:
        raise
    except Exception:
        con.rollback()
        raise
    finally:
        pass
    print("\n(اتكتب)")
    print(f"foreign_key_check problems: {len(con.execute('PRAGMA foreign_key_check').fetchall())}")
    print(f"integrity_check: {con.execute('PRAGMA integrity_check').fetchone()[0]}")
    con.close()


if __name__ == "__main__":
    main()
