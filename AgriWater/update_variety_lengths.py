r"""
update_variety_lengths.py
بيملا season_length_days للأصناف اللي لقيت لها رقم منشور بحقل تجارب سخا.
الباقي (سخا 102 و103 و106 وجيزة 177) بيفضل NULL لحد ما تتأكد.

الضمانات: نسخة احتياطية قبل التعديل، transaction واحدة، ومش بيلمس غير الأصناف دي.

التشغيل:
    .\.venv\Scripts\python.exe update_variety_lengths.py
"""
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

DB = Path("database/agriwater_v2.sqlite")
SRC = "https://ejpb.journals.ekb.eg/article_256163.html"  # EHR3 paper, Egypt. J. Plant Breed.
STATUS = "LITERATURE_VALUE_SAKHA_TRIAL_NEEDS_RRTC_CONFIRMATION"

# القيم دي متوسط مدة النمو من بذر لنضج في تجارب سخا كما وردت في الورقة (مش لصنف مزروع بالضرورة بنفس الظروف عند الفلاح).
UPDATES = [
    ("Sakha 101",         143),   # 142.9
    ("Sakha 104",         135),   # 135
    ("Giza 178",          135),   # 135
    ("Egyptian Hybrid 1", 135),   # 134.9
]


def main():
    if not DB.exists():
        sys.exit(f"مش لاقي القاعدة: {DB.resolve()}")
    backup = DB.with_name(f"agriwater_v2_backup_{datetime.now():%Y%m%d_%H%M%S}.sqlite")
    shutil.copy2(DB, backup)
    print(f"نسخة احتياطية: {backup}")

    con = sqlite3.connect(DB)
    try:
        with con:
            for name, days in UPDATES:
                cur = con.execute(
                    "UPDATE rice_variety SET season_length_days=?, source_url=?, data_status=? "
                    "WHERE name_en=? AND season_length_days IS NULL",
                    (days, SRC, STATUS, name),
                )
                print(f"{name}: {'اتحدّث' if cur.rowcount else 'اتخطّى (فيه قيمة أصلاً أو الاسم مش موجود)'}")
        print()
        for r in con.execute("SELECT variety_id, name_en, season_length_days, data_status FROM rice_variety"):
            print(r)
        print(f"\nintegrity_check: {con.execute('PRAGMA integrity_check').fetchone()[0]}")
    except Exception as e:
        print(f"حصل خطأ ولا حاجة اتغيرت: {e}\nالنسخة الاحتياطية: {backup}")
        raise
    finally:
        con.close()


if __name__ == "__main__":
    main()
