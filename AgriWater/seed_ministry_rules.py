r"""
seed_ministry_rules.py
بيسجل في ministry_rule أرقام منسوبة لوزارة الموارد المائية والري من تقارير صحفية منشورة.

تنبيه مهم: دي تصريحات صحفية مش قرارات وزارية رسمية، والأرقام بتختلف من مصدر للتاني
(مثلاً 7000 مقابل 9000 م3/فدان). كل صف مكتوب فيه [PRESS_REPORT_NEEDS_OFFICIAL_CONFIRMATION]
في أوله، وتواريخ valid_from/valid_to فاضية عمدًا لأن التواريخ مش مؤكدة.
استخدمها للمقارنة مع القياسات الفعلية، مش كحقائق للموديل.

الضمانات: نسخة احتياطية، transaction واحدة، وآمن لو اتشغل أكتر من مرة.

التشغيل (من فولدر AgriWater_FIXED):
    .\.venv\Scripts\python.exe seed_ministry_rules.py
"""
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

DB = Path("database/agriwater_v2.sqlite")
TAG = "[PRESS_REPORT_NEEDS_OFFICIAL_CONFIRMATION] "
MASRAWY = ("https://www.masrawy.com/news/news_egypt/details/2019/4/13/1549414/"
           "رئيس-قطاع-الري-الأرز-الجاف-البديل-الآمن-لتقليل-استهلاك-المياه-حوار")
WATAN = "https://www.elwatannews.com/news/details/2778502"

# (topic, district_id, rule_text, value_num, unit, source_url)
RULES = [
    ("rice_water_use_conventional", None,
     "رئيس قطاع الري بوزارة الموارد المائية والري (حوار مصراوي، 13 أبريل 2019): فدان الأرز العادي يستهلك حوالي 7000 م3.",
     7000, "m3/feddan", MASRAWY),
    ("rice_water_use_dry_varieties", None,
     "نفس المصدر: الأصناف الجافة (قليلة المياه) تحتاج حوالي 3500 م3 للفدان.",
     3500, "m3/feddan", MASRAWY),
    ("rice_irrigation_interval_dry_varieties", None,
     "نفس المصدر: الأصناف الجافة بتتروى كل 18 يوم.",
     18, "days", MASRAWY),
    ("rice_irrigation_interval_conventional", None,
     "نفس المصدر: الفترة المقارنة للأرز العادي 15 يوم (مذكورة في سياق المقارنة).",
     15, "days", MASRAWY),
    ("rice_water_use_ministry_report", None,
     "الوطن نقلًا عن تقرير لوزارة الموارد المائية والري: فدان الأرز يستهلك قرابة 9000 م3 (تاريخ التقرير غير مؤكد).",
     9000, "m3/feddan", WATAN),
    ("rice_designated_governorates", 1,
     "الوطن نقلًا عن مصادر بوزارة الري: المحافظات المحددة لزراعة الأرز هي الدقهلية والشرقية وبورسعيد ودمياط "
     "وكفر الشيخ والبحيرة، بمساحة إجمالية محددة 1,076,000 فدان لكل المحافظات مجتمعة (مش لكفر الشيخ وحدها).",
     1076000, "feddan_total_all_governorates", WATAN),
    ("rice_violation_fine", None,
     "الوطن نقلًا عن مصادر بوزارة الري: غرامة مخالفة زراعة الأرز 3660 جنيه للفدان في المناطق المروية "
     "مباشرة، وفق قانون الري والصرف 12 لسنة 1984.",
     3660, "EGP/feddan", WATAN),
]


def main():
    if not DB.exists():
        sys.exit(f"مش لاقي القاعدة: {DB.resolve()}")
    backup = DB.with_name(f"agriwater_v2_backup_{datetime.now():%Y%m%d_%H%M%S}.sqlite")
    shutil.copy2(DB, backup)
    print(f"نسخة احتياطية: {backup}")
    con = sqlite3.connect(DB)
    con.execute("PRAGMA foreign_keys = ON")
    try:
        added = 0
        with con:
            for topic, did, text, val, unit, url in RULES:
                if con.execute("SELECT 1 FROM ministry_rule WHERE topic=? AND source_url=? "
                               "AND IFNULL(value_num,-1)=IFNULL(?,-1)", (topic, url, val)).fetchone():
                    continue
                con.execute("INSERT INTO ministry_rule(topic, variety_id, district_id, rule_text, value_num, unit, "
                            "valid_from, valid_to, source_url) VALUES (?,NULL,?,?,?,?,NULL,NULL,?)",
                            (topic, did, TAG + text, val, unit, url))
                added += 1
        print(f"قواعد اتضافت: {added}")
        for r in con.execute("SELECT rule_id, topic, value_num, unit FROM ministry_rule"):
            print(" ", r)
        print(f"foreign_key_check problems: {len(con.execute('PRAGMA foreign_key_check').fetchall())}")
        print(f"integrity_check: {con.execute('PRAGMA integrity_check').fetchone()[0]}")
    except Exception as e:
        print(f"حصل خطأ ولا حاجة اتغيرت: {e}\nالنسخة الاحتياطية: {backup}")
        raise
    finally:
        con.close()


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    main()
