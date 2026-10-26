r"""
update_giza177_length.py
بيسجل مدة موسم جيزة 177 = 125 يوم (قيمة منشورة، محتاجة تأكيد من مركز بحوث الأرز).

- بيحدّث الصنف بس لو season_length_days فاضية (مش بيكتب فوق قيمة موجودة).
- نسخة احتياطية قبل أي تعديل، وtransaction واحدة.

التشغيل (من فولدر AgriWater_FIXED):
    .\.venv\Scripts\python.exe update_giza177_length.py
"""
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

DB = Path("database/agriwater_v2.sqlite")
SOURCE = ("https://ejpb.journals.ekb.eg/article_372796_51dbb52cf64f1e118522c0ec9b8ee716.pdf "
          "(Sakha Super 302 paper, intro: Giza 177 released 1995, duration 125 days, citing Aidy et al. 2004)")
STATUS = "LITERATURE_VALUE_SECONDARY_CITATION_NEEDS_RRTC_CONFIRMATION"


def main():
    if not DB.exists():
        sys.exit(f"مش لاقي القاعدة: {DB.resolve()}")
    backup = DB.with_name(f"agriwater_v2_backup_{datetime.now():%Y%m%d_%H%M%S}.sqlite")
    shutil.copy2(DB, backup)
    print(f"نسخة احتياطية: {backup}")
    con = sqlite3.connect(DB)
    try:
        with con:
            cur = con.execute(
                "UPDATE rice_variety SET season_length_days=125, source_url=?, data_status=? "
                "WHERE name_en='Giza 177' AND season_length_days IS NULL",
                (SOURCE, STATUS))
            print("اتحدّث" if cur.rowcount else "اتخطّى: الصنف مش موجود أو فيه قيمة قبل كده")
        for r in con.execute("SELECT variety_id, name_en, season_length_days, data_status FROM rice_variety"):
            print(r)
        print(f"foreign_key_check problems: {len(con.execute('PRAGMA foreign_key_check').fetchall())}")
        print(f"integrity_check: {con.execute('PRAGMA integrity_check').fetchone()[0]}")
    except Exception as e:
        print(f"حصل خطأ ولا حاجة اتغيرت: {e}\nالنسخة الاحتياطية: {backup}")
        raise
    finally:
        con.close()


if __name__ == "__main__":
    main()
