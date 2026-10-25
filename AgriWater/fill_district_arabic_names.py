r"""
fill_district_arabic_names.py
بيملا district.name_ar لمراكز كفر الشيخ (المستوى 2).
- نسخة احتياطية قبل التعديل، transaction واحدة.
- بيملا الفاضي بس (name_ar IS NULL)، فمش بيمسح حاجة كتبتها بإيدك.

التشغيل:
    .\.venv\Scripts\python.exe fill_district_arabic_names.py
"""
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

DB = Path("database/agriwater_v2.sqlite")

NAMES = {
    "Al Hamul": "الحامول",
    "Biyalu": "بيلا",
    "Burullus": "البرلس",
    "Disuq": "دسوق",
    "Fuwwa": "فوه",
    "Kafr Al-Shaykh": "كفر الشيخ",
    "Mitubas": "مطوبس",
    "Qillin": "قلين",
    "Riyad": "الرياض",
    "Sidi Salim": "سيدي سالم",
}


def main():
    if not DB.exists():
        sys.exit(f"مش لاقي القاعدة: {DB.resolve()}")
    backup = DB.with_name(f"agriwater_v2_backup_{datetime.now():%Y%m%d_%H%M%S}.sqlite")
    shutil.copy2(DB, backup)
    print(f"نسخة احتياطية: {backup}")
    con = sqlite3.connect(DB)
    try:
        with con:
            for en, ar in NAMES.items():
                cur = con.execute(
                    "UPDATE district SET name_ar=? WHERE name_en=? AND admin_level=2 AND name_ar IS NULL",
                    (ar, en),
                )
                print(f"{en:16} -> {ar:10} {'اتحدّث' if cur.rowcount else 'اتخطّى (موجود أو الاسم مش في القاعدة)'}")
        print()
        for r in con.execute("SELECT district_id, name_en, name_ar, admin_level, parent_id FROM district ORDER BY admin_level, name_en"):
            print(r)
        print(f"\nintegrity_check: {con.execute('PRAGMA integrity_check').fetchone()[0]}")
    except Exception as e:
        print(f"حصل خطأ ولا حاجة اتغيرت: {e}\nالنسخة الاحتياطية: {backup}")
        raise
    finally:
        con.close()


if __name__ == "__main__":
    main()
