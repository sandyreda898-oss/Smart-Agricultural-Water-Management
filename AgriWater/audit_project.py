r"""
audit_project.py
فحص للقراءة فقط: بيعرض اللي جوه القاعدة والفولدرات ويحسب الناقص.
مش بيكتب ولا بيعدّل أي حاجة في القاعدة.

التشغيل (من فولدر AgriWater_FIXED):
    .\.venv\Scripts\python.exe audit_project.py
التقرير بيتحفظ في: reports\audit_report.txt
"""
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

DB = Path("database/agriwater_v2.sqlite")
OUT = Path("reports/audit_report.txt")
lines = []


def p(s=""):
    lines.append(str(s))
    try:
        print(s)
    except UnicodeEncodeError:
        print(str(s).encode("ascii", "replace").decode())


def q(con, sql, default=None):
    try:
        return con.execute(sql).fetchall()
    except sqlite3.Error as e:
        return default if default is not None else [("ERR: " + str(e),)]


def one(con, sql):
    r = q(con, sql, [(None,)])
    return r[0][0] if r else None


def mb(path):
    return path.stat().st_size / 1024 / 1024


def main():
    if not DB.exists():
        sys.exit(f"مش لاقي القاعدة: {DB.resolve()} (شغّل السكريبت من فولدر المشروع)")
    con = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True)
    missing = []   # (أولوية, وصف)

    p(f"AgriWater audit | {datetime.now():%Y-%m-%d %H:%M}")
    p(f"القاعدة: {DB} ({mb(DB):.1f} MB)")

    # ---------- 1) كل الجداول ----------
    p("\n=== 1) الجداول وعدد الصفوف ===")
    tables = [r[0] for r in q(con, "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    counts = {}
    for t in tables:
        counts[t] = one(con, f'SELECT COUNT(*) FROM "{t}"')
        p(f"{t:32} {counts[t]:>12,}" if isinstance(counts[t], int) else f"{t:32} {counts[t]}")
    empty = [t for t in tables if counts[t] == 0]
    p(f"\nجداول فاضية ({len(empty)}): {empty}")

    # ---------- 2) الطقس ----------
    p("\n=== 2) الطقس (weather_daily) ===")
    p(f"نقاط: {one(con, 'SELECT COUNT(DISTINCT point_id) FROM weather_daily')} | "
      f"بارامترات: {one(con, 'SELECT COUNT(DISTINCT parameter) FROM weather_daily')} | "
      f"من {one(con, 'SELECT MIN(obs_date) FROM weather_daily')} إلى {one(con, 'SELECT MAX(obs_date) FROM weather_daily')}")
    nulls = one(con, "SELECT COUNT(*) FROM weather_daily WHERE value IS NULL")
    p(f"قيم NULL: {nulls}")

    # ---------- 3) المراكز والنقاط ----------
    p("\n=== 3) المراكز والنقاط ===")
    no_d = one(con, "SELECT COUNT(*) FROM grid_point WHERE district_id IS NULL")
    p(f"نقاط من غير مركز: {no_d} من {counts.get('grid_point')}")
    no_ar = one(con, "SELECT COUNT(*) FROM district WHERE admin_level=2 AND name_ar IS NULL")
    p(f"مراكز من غير اسم عربي: {no_ar}")
    for r in q(con, "SELECT d.name_ar, d.name_en, COUNT(g.point_id) FROM district d "
                    "LEFT JOIN grid_point g ON g.district_id=d.district_id "
                    "WHERE d.admin_level=2 GROUP BY d.district_id ORDER BY d.name_en"):
        p(f"  {r[0] or '-':12} {r[1]:18} نقاط: {r[2]}")
    if no_d:
        missing.append((2, f"{no_d} نقطة غير مربوطة بمركز"))

    # ---------- 4) الأصناف و Kc ----------
    p("\n=== 4) الأصناف و Kc ===")
    for r in q(con, "SELECT variety_id, name_en, name_ar, season_length_days, data_status FROM rice_variety"):
        p(f"  {r}")
    no_len = one(con, """SELECT COUNT(*) FROM rice_variety v WHERE v.season_length_days IS NULL
        AND v.name_en<>'NOT_SPECIFIED' AND NOT EXISTS (SELECT 1 FROM rice_variety_field_guide g
        WHERE g.variety_id=v.variety_id AND g.maturity_days_min IS NOT NULL AND g.maturity_days_max IS NOT NULL)""")
    p(f"أصناف بلا مدة مفردة أو نطاق موثق: {no_len}")
    if no_len:
        names = [r[0] for r in q(con, """SELECT v.name_en FROM rice_variety v WHERE v.season_length_days IS NULL
            AND v.name_en<>'NOT_SPECIFIED' AND NOT EXISTS (SELECT 1 FROM rice_variety_field_guide g
            WHERE g.variety_id=v.variety_id AND g.maturity_days_min IS NOT NULL AND g.maturity_days_max IS NOT NULL)""")]
        missing.append((2, f"مدة/نطاق موسم {no_len} صنف غير موثق: {names}"))
    p("\ncrop_water_parameter:")
    for r in q(con, "SELECT parameter_id, growth_stage, kc, parameter_name, parameter_value, unit, data_status "
                    "FROM crop_water_parameter"):
        p(f"  {r}")
    kc_filled = one(con, "SELECT COUNT(*) FROM crop_water_parameter WHERE kc IS NOT NULL")
    p(f"صفوف فيها قيمة Kc: {kc_filled}")
    if not kc_filled:
        missing.append((2, "قيم Kc نفسها ما اتسجلتش في crop_water_parameter (الأطوال بس)"))

    # ---------- 5) الاستبيان والحقول ----------
    p("\n=== 5) بيانات الحقول الحقيقية ===")
    nf, nfs, nev = counts.get("field"), counts.get("field_season"), counts.get("irrigation_event")
    lab = one(con, "SELECT COUNT(*) FROM field_season WHERE total_irrigation_m3_per_feddan IS NOT NULL")
    lab_y = one(con, "SELECT COUNT(*) FROM field_season WHERE harvest_yield_ton_per_feddan IS NOT NULL")
    p(f"حقول: {nf} | مواسم حقل: {nfs} | ريّات: {nev}")
    p(f"مواسم فيها إجمالي ري (الهدف 1): {lab} | فيها إنتاجية (الهدف 2): {lab_y}")
    if not nfs:
        missing.append((1, "لا يوجد أي حقل حقيقي. الموديل لسه ما عندوش بيانات قياس فعلية (أهم نقص)"))
    elif lab < 30:
        missing.append((1, f"مواسم الحقول المقاسة {lab} فقط. محتاج عشرات على الأقل قبل أي تدريب"))

    # ---------- 6) الأقمار الصناعية ----------
    p("\n=== 6) Sentinel-2 ===")
    p(f"مشاهد: {counts.get('sentinel2_scene')} | shortlist: {counts.get('sentinel2_shortlist')} | "
      f"vegetation_index: {counts.get('vegetation_index')}")
    p(f"نطاق المشاهد: {one(con, 'SELECT MIN(acquired_at) FROM sentinel2_scene')} -> {one(con, 'SELECT MAX(acquired_at) FROM sentinel2_scene')}")
    p("ملاحظة: استخراج NDVI/EVI مؤجل حسب نطاق المشروع؛ وجود مشاهد مفهرسة لا يعني وجود قيم مؤشرات.")

    # ---------- 7) الإحصاءات والموسم ----------
    p("\n=== 7) الإحصاءات والمواسم ===")
    p(f"regional_stats: {counts.get('regional_stats')} صف")
    for r in q(con, "SELECT season_year, COUNT(*) FROM regional_stats GROUP BY season_year ORDER BY season_year"):
        p(f"  {r[0]}: {r[1]} صف")
    p(f"point_season_summary: {counts.get('point_season_summary')} | water_scenario: {counts.get('water_scenario')}")
    for r in q(con, "SELECT training_readiness, COUNT(*) FROM point_season_summary GROUP BY training_readiness"):
        p(f"  training_readiness = {r[0]}: {r[1]}")
    for r in q(con, "SELECT actual_irrigation_status, COUNT(*) FROM water_scenario GROUP BY actual_irrigation_status"):
        p(f"  actual_irrigation_status = {r[0]}: {r[1]}")

    # ---------- 8) بيانات بيئية ناقصة ----------
    p("\n=== 8) بيانات بيئية وتنظيمية ===")
    p(f"قياسات تربة/مياه منشورة: {counts.get('literature_environmental_measurement')} | "
      f"دراسات مرتبطة: {counts.get('literature_study')}")
    for t, label in (("soil_salinity", "ملوحة التربة"), ("groundwater_level", "المياه الجوفية"),
                     ("canal_schedule", "مناوبات الري"), ("ministry_rule", "قواعد الوزارة"),
                     ("crop_calendar", "التقويم الزراعي")):
        c = counts.get(t)
        p(f"{label:18} ({t}): {c}")
        if not c:
            if t == "groundwater_level":
                missing.append((3, "لا توجد قياسات جوفية زراعية على مستوى النقاط/الحقول؛ أضيف ملخص خريطة جيوتقنية منشورة 2023 مع تحذير جودة"))
            elif t == "soil_salinity":
                missing.append((3, "لا توجد طبقة ملوحة مكانية لحقول الأرز؛ توجد عينات/دراسات منشورة محدودة في جدول الأدلة البيئية"))
            else:
                missing.append((3, f"{label} ({t}) فاضي"))
    p(f"كتالوج سلاسل المضخات: {counts.get('pump_catalog_series')} | "
      f"أنواع موحدة/نقاط تصرف عند الرفع الفعلي: {counts.get('pump_type')}")
    if not counts.get("pump_type"):
        missing.append((2, "لا توجد بيانات تصرف مؤكدة لموديل المضخة عند الرفع الفعلي؛ الكتالوج الحالي نطاقات سلاسل فقط"))
    p(f"soil_point: {counts.get('soil_point')} | soil_awc: {counts.get('soil_awc')} | نقاط من غير تربة: "
      f"{one(con, 'SELECT COUNT(*) FROM grid_point g LEFT JOIN soil_point s ON s.point_id=g.point_id WHERE s.point_id IS NULL')}")

    # ---------- 9) سلامة القاعدة ----------
    p("\n=== 9) سلامة القاعدة ===")
    p(f"foreign_key_check problems: {len(q(con, 'PRAGMA foreign_key_check', []))}")
    p(f"integrity_check: {one(con, 'PRAGMA integrity_check')}")
    con.close()

    # ---------- 10) الفولدرات ----------
    p("\n=== 10) الملفات والفولدرات ===")
    for d in sorted(x for x in Path(".").iterdir() if x.is_dir() and x.name not in (".venv", "__pycache__", ".git")):
        files = [f for f in d.rglob("*") if f.is_file()]
        size = sum(f.stat().st_size for f in files) / 1024 / 1024
        p(f"{d.name:18} ملفات: {len(files):>5} | {size:9.1f} MB")
    data = Path("data")
    if data.exists():
        p("\nمحتوى data (المستوى الأول):")
        for d in sorted(data.iterdir()):
            if d.is_dir():
                n = sum(1 for f in d.rglob("*") if f.is_file())
                p(f"  {d.name:28} ملفات: {n}")
            else:
                p(f"  {d.name:28} {d.stat().st_size/1024:.0f} KB")
    surv = Path("data/field_survey")
    p(f"\nفولدر data/field_survey موجود: {surv.exists()}"
      + (f" | ملفات CSV: {[f.name for f in surv.glob('*.csv')]}" if surv.exists() else ""))
    backups = sorted(Path("database").glob("*backup*.sqlite"))
    p(f"\nنسخ احتياطية في database: {len(backups)} ({sum(b.stat().st_size for b in backups)/1024/1024:.0f} MB)")
    for b in backups:
        p(f"  {b.name} ({mb(b):.1f} MB)")
    extra = [f for f in ("show_methods.py", "show_schema.py", "make_snapshot.py",
                         "import_field_survey_OLD_20261024_141344.py") if Path(f).exists()]
    p(f"ملفات مساعدة ممكن تتمسح: {extra}")

    # ---------- الخلاصة ----------
    p("\n" + "=" * 60)
    p("الخلاصة: الناقص مرتب بالأولوية (1 = الأهم)")
    p("=" * 60)
    for pr, msg in sorted(missing):
        p(f"[{pr}] {msg}")
    if not missing:
        p("مفيش نواقص واضحة.")

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nالتقرير اتحفظ في: {OUT.resolve()}")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    main()
