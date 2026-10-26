"""
حساب احتياج الأرز المائي لكل صنف بمدته الحقيقية (سيناريو تقديري غير متحقق حقليًا).

التغييرات عن النسخة السابقة (بناءً على قياسات منشورة في سخا):
- الرشح نطاق افتراضي للتحليل وليس قياسًا محليًا؛ لا يُعرض كتوصية ري مؤكدة.
- المكوّن الأساسي (core) = ETc + رشح - مطر؛ لا توجد حاليًا قيم محلية موثقة للمقارنة.
- تحضير الأرض والتشتيل (200+100 مم) افتراض أدبيات ومكوّن منفصل.
- --kc-scale لاختبار حساسية التبخر حول القيمة المرجعية.
- --wind-scale معامل حساسية اختياري؛ القيمة الافتراضية 1.0 تستخدم WS2M كما هو.
- لا توجد حاليًا قاعدة قابلة للتتبع لقياسات محلية فعلية لحجم مياه الري للمقارنة.

بيقرأ من agriwater_v2.sqlite، ويكتب جدول water_scenario_by_variety_v3 وملف في reports/.
بياخد نسخة احتياطية قبل الكتابة (إلا لو --no-backup). كل النتايج سيناريوهات تقديرية.
"""
import argparse
import csv
import math
import os
import shutil
import sqlite3
from collections import defaultdict
from datetime import date, datetime, timedelta
from statistics import mean

ROOT = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(ROOT, "database", "agriwater_v2.sqlite")
TABLE = "water_scenario_by_variety_v3"
REPORT = os.path.join(ROOT, "reports", "water_scenario_by_variety_summary_v3.csv")

M3_PER_FEDDAN_PER_MM = 4200 / 1000
PREP_MM = 200 + 100  # تحضير الأرض + تشتيل (افتراض، مش من مصدر)

# مراحل الأرز كنسب من مدة الحقل: ابتدائي / تطور / منتصف / نهاية
# FAO-56 generic rice stage lengths: 30/30/60/30 days (20/20/40/20%).
STAGE_END = (0.20, 0.40, 0.80, 1.00)
KC_INI, KC_MID, KC_END = 1.05, 1.20, 0.75

PARAMS = ["T2M_MIN", "T2M_MAX", "RH2M", "WS2M", "ALLSKY_SFC_SW_DWN", "PS", "PRECTOTCORR"]

# No directly traceable local measured irrigation-volume dataset is currently
# available in the project. Do not compare modeled scenarios to unverified values.
PUBLISHED = {}


def sat_vapour(t):
    return 0.6108 * math.exp(17.27 * t / (t + 237.3))


def et0_fao56(tmin, tmax, rh, wind, rs, pressure, latitude, day):
    if any(v is None for v in (tmin, tmax, rh, wind, rs, pressure, latitude)):
        return None
    if pressure <= 0 or rs < 0 or wind < 0:
        return None
    tmean = (tmin + tmax) / 2
    es = (sat_vapour(tmin) + sat_vapour(tmax)) / 2
    ea = es * max(0, min(100, rh)) / 100
    delta = 4098 * sat_vapour(tmean) / ((tmean + 237.3) ** 2)
    gamma = 0.000665 * pressure
    phi = math.radians(latitude)
    dr = 1 + 0.033 * math.cos(2 * math.pi * day / 365)
    decl = 0.409 * math.sin(2 * math.pi * day / 365 - 1.39)
    x = -math.tan(phi) * math.tan(decl)
    ws = math.acos(max(-1, min(1, x)))
    ra = (24 * 60 / math.pi) * 0.0820 * dr * (
        ws * math.sin(phi) * math.sin(decl)
        + math.cos(phi) * math.cos(decl) * math.sin(ws)
    )
    ra = max(0, ra)
    z = 44330 * (1 - (pressure / 101.3) ** 0.1903)
    rso = max(0.1, (0.75 + 2e-5 * z) * ra)
    rns = 0.77 * rs
    ratio = max(0, min(1, rs / rso))
    tk = tmean + 273.16
    rnl = 4.903e-9 * (tk ** 4) * (0.34 - 0.14 * math.sqrt(max(0, ea))) * (1.35 * ratio - 0.35)
    rn = rns - rnl
    res = (0.408 * delta * rn + gamma * (900 / (tmean + 273)) * wind * (es - ea)) / (
        delta + gamma * (1 + 0.34 * wind)
    )
    return max(0, res)


def kc_for(i, n):
    f = (i + 0.5) / n
    ini, dev, mid, _ = STAGE_END
    if f <= ini:
        return KC_INI
    if f <= dev:
        return KC_INI + (KC_MID - KC_INI) * (f - ini) / (dev - ini)
    if f <= mid:
        return KC_MID
    return KC_MID + (KC_END - KC_MID) * (f - mid) / (1 - mid)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sowing", default="05-20", help="تاريخ بذر المشتل MM-DD")
    ap.add_argument("--transplant", default="06-13", help="تاريخ الشتل MM-DD")
    ap.add_argument("--seepage-low", type=float, default=4.0, help="حد أدنى افتراضي من نطاق الأدبيات، وليس قياسًا محليًا")
    ap.add_argument("--seepage-high", type=float, default=8.0, help="حد أعلى افتراضي من نطاق الأدبيات، وليس قياسًا محليًا")
    ap.add_argument("--kc-scale", type=float, default=1.0, help="معامل لضرب Kc (للحساسية، مثلا 0.85)")
    ap.add_argument("--wind-scale", type=float, default=1.0,
                    help="معامل حساسية لسرعة الرياح؛ 1.0 يستخدم قيمة NASA POWER كما هي")
    ap.add_argument("--no-backup", action="store_true")
    args = ap.parse_args()

    sm, sd = map(int, args.sowing.split("-"))
    tm, td = map(int, args.transplant.split("-"))
    nursery_days = (date(2001, tm, td) - date(2001, sm, sd)).days
    if nursery_days <= 0:
        raise SystemExit("تاريخ الشتل لازم يبقى بعد البذر")
    if args.seepage_low > args.seepage_high:
        raise SystemExit("--seepage-low لازم يبقى أقل من أو يساوي --seepage-high")

    if not os.path.exists(DB):
        raise SystemExit(f"مش لاقي القاعدة: {DB}")

    if not args.no_backup:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        bak = os.path.join(ROOT, "database", f"agriwater_v2_backup_{stamp}.sqlite")
        shutil.copy2(DB, bak)
        print("نسخة احتياطية:", bak)

    con = sqlite3.connect(DB)
    cur = con.cursor()

    varieties = cur.execute(
        "select variety_id, name_en, season_length_days from rice_variety "
        "where season_length_days is not null order by variety_id"
    ).fetchall()
    points = {
        r[0]: (r[1], r[2])
        for r in cur.execute("select point_id, latitude, longitude from grid_point")
    }
    excluded = {
        r[0]
        for r in cur.execute(
            "select point_id from soil_awc where model_screening_status like 'EXCLUDE%'"
        )
    }

    print("قراءة الطقس...")
    ph = ",".join("?" * len(PARAMS))
    weather = defaultdict(dict)
    for p, d, par, v in cur.execute(
        f"select point_id, obs_date, parameter, value from weather_daily where parameter in ({ph})",
        PARAMS,
    ):
        weather[(p, d)][par] = v
    if not weather:
        raise SystemExit("جدول weather_daily مفيهوش البارامترات المطلوبة. شغّل: select distinct parameter from weather_daily")

    years = sorted({int(d[:4]) for (_, d) in weather})
    print("السنين:", years, "| الأصناف:", [v[1] for v in varieties])
    print(f"البذر {args.sowing} والشتل {args.transplant} (مشتل {nursery_days} يوم) | "
          f"رشح {args.seepage_low}-{args.seepage_high} مم/يوم | kc-scale {args.kc_scale} | wind-scale {args.wind_scale}")

    et_cache = {}

    def day_values(point, d):
        key = (point, d)
        if key in et_cache:
            return et_cache[key]
        w = weather.get(key)
        if not w:
            et_cache[key] = (None, None)
            return et_cache[key]
        lat = points[point][0]
        doy = datetime.strptime(d, "%Y-%m-%d").timetuple().tm_yday
        wind = w.get("WS2M")
        if wind is not None:
            wind = wind * args.wind_scale
        et0 = et0_fao56(
            w.get("T2M_MIN"), w.get("T2M_MAX"), w.get("RH2M"), wind,
            w.get("ALLSKY_SFC_SW_DWN"), w.get("PS"), lat, doy,
        )
        et_cache[key] = (et0, w.get("PRECTOTCORR"))
        return et_cache[key]

    rows = []
    skipped = 0
    for year in years:
        transplant = date(year, tm, td)
        for point in points:
            for vid, vname, length in varieties:
                for basis, field_days in (
                    ("length_from_sowing", length - nursery_days),
                    ("length_from_transplanting", length),
                ):
                    etc = rain = 0.0
                    missing = 0
                    for i in range(field_days):
                        d = (transplant + timedelta(days=i)).isoformat()
                        et0, pr = day_values(point, d)
                        if et0 is None:
                            missing += 1
                            continue
                        etc += et0 * kc_for(i, field_days) * args.kc_scale
                        rain += pr or 0.0
                    if missing > 0.05 * field_days:
                        skipped += 1
                        continue
                    core_low = max(0, etc - rain + args.seepage_low * field_days)
                    core_high = max(0, etc - rain + args.seepage_high * field_days)
                    rows.append((
                        year, point, vid, basis,
                        transplant.isoformat(),
                        (transplant + timedelta(days=field_days - 1)).isoformat(),
                        field_days, missing,
                        round(etc, 2), round(rain, 2),
                        args.seepage_low, args.seepage_high, args.kc_scale,
                        round(core_low, 2), round(core_high, 2),
                        round(core_low * M3_PER_FEDDAN_PER_MM, 2),
                        round(core_high * M3_PER_FEDDAN_PER_MM, 2),
                        PREP_MM,
                        round((core_low + PREP_MM) * M3_PER_FEDDAN_PER_MM, 2),
                        round((core_high + PREP_MM) * M3_PER_FEDDAN_PER_MM, 2),
                        "SCENARIO_ESTIMATE_NOT_FIELD_VALIDATED",
                        args.wind_scale,
                    ))

    if not rows:
        raise SystemExit("مفيش نتايج. اتأكد إن الطقس بيغطي مواسم الزراعة.")

    cur.execute(f"drop table if exists {TABLE}")
    cur.execute(
        f"""create table {TABLE} (
            season_year INTEGER, point_id TEXT, variety_id INTEGER, duration_basis TEXT,
            transplant_date TEXT, harvest_date TEXT, field_days INTEGER, missing_weather_days INTEGER,
            estimated_etc_mm REAL, rainfall_mm REAL,
            seepage_low_mm_day REAL, seepage_high_mm_day REAL, kc_scale REAL,
            core_low_mm REAL, core_high_mm REAL,
            core_low_m3_per_feddan REAL, core_high_m3_per_feddan REAL,
            prep_establishment_mm REAL,
            with_prep_low_m3_per_feddan REAL, with_prep_high_m3_per_feddan REAL,
            method_status TEXT, wind_scale REAL)"""
    )
    cur.executemany(f"insert into {TABLE} values ({','.join('?' * 22)})", rows)
    con.commit()

    names = {v[0]: v[1] for v in varieties}
    groups = defaultdict(list)
    for r in rows:
        if r[1] in excluded:
            continue
        groups[(r[2], r[3])].append(r)

    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    out = []
    print("\nمتوسط السيناريوهات (م3/فدان). core = ETc + رشح - مطر؛ لا يمثل قياسًا أو توصية ري مؤكدة")
    print(f"{'الصنف':<18}{'الأساس':<27}{'أيام':>5}{'core أدنى':>10}{'core أعلى':>10}"
          f"{'+تحضير أدنى':>12}{'+تحضير أعلى':>12}{'ETc مم':>8}{'مم/يوم':>7}  منشور")
    for (vid, basis), g in sorted(groups.items()):
        nm = names[vid]
        pub = PUBLISHED.get(nm)
        rec = {
            "variety": nm, "duration_basis": basis, "field_days": g[0][6],
            "core_low_m3_per_feddan": round(mean(x[15] for x in g), 0),
            "core_high_m3_per_feddan": round(mean(x[16] for x in g), 0),
            "with_prep_low_m3_per_feddan": round(mean(x[18] for x in g), 0),
            "with_prep_high_m3_per_feddan": round(mean(x[19] for x in g), 0),
            "mean_etc_mm": round(mean(x[8] for x in g), 1),
            "mean_etc_mm_per_day": round(mean(x[8] for x in g) / g[0][6], 2),
            "mean_rain_mm": round(mean(x[9] for x in g), 1),
            "published_m3_per_feddan": f"{pub[0]}-{pub[1]}" if pub else "",
            "n_records": len(g),
        }
        out.append(rec)
        pub_txt = f"{pub[0]}-{pub[1]}" if pub else "-"
        print(f"{nm:<18}{basis:<27}{rec['field_days']:>5}"
              f"{rec['core_low_m3_per_feddan']:>10.0f}{rec['core_high_m3_per_feddan']:>10.0f}"
              f"{rec['with_prep_low_m3_per_feddan']:>12.0f}{rec['with_prep_high_m3_per_feddan']:>12.0f}"
              f"{rec['mean_etc_mm']:>8.1f}{rec['mean_etc_mm_per_day']:>7.2f}  {pub_txt}")
    with open(REPORT, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)

    print("\nالنتائج نطاقات استكشافية مبنية على طقس شبكي وافتراضات FAO/رشح/تجهيز؛ غير متحققة بقياس ري محلي.")
    print(f"صفوف اتكتبت: {len(rows)} | اتخطّت لنقص الطقس: {skipped}")
    print("اتكتب جدول", TABLE, "وملف:", REPORT)
    print("الجداول القديمة ما اتلمستش.")
    print("اختبار سلامة:", cur.execute("pragma integrity_check").fetchone()[0])
    con.close()


if __name__ == "__main__":
    main()
