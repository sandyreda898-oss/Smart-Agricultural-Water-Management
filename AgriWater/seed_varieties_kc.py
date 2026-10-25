r"""
seed_varieties_kc.py
يضيف أسماء الأصناف المرشحة + قيم FAO-56 لأطوال المراحل في agriwater_v2.sqlite

الضمانات:
  1) بيعمل نسخة احتياطية من القاعدة قبل أي تعديل.
  2) آمن لو اتشغل أكتر من مرة (مش بيكرر صفوف).
  3) كله جوه transaction واحدة: لو حصل خطأ، بيرجع كل حاجة زي ما كانت.
  4) مش بيكتب أي مدة موسم للأصناف: لازم تتأكد من نشرات مركز بحوث الأرز.

التشغيل (من فولدر AgriWater_FIXED):
    .\.venv\Scripts\python.exe seed_varieties_kc.py
"""
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

DB = Path("database/agriwater_v2.sqlite")

# أصناف مرشحة لكفر الشيخ. season_length_days فاضية عمدًا.
VARIETIES = [
    ("Sakha 101",       "سخا 101"),
    ("Sakha 102",       "سخا 102"),
    ("Sakha 103",       "سخا 103"),
    ("Sakha 104",       "سخا 104"),
    ("Sakha 106",       "سخا 106"),
    ("Giza 177",        "جيزة 177"),
    ("Giza 178",        "جيزة 178"),
    ("Egyptian Hybrid 1", "هجين مصر 1"),
]
VARIETY_STATUS = "CANDIDATE_NAME_ONLY_SEASON_LENGTH_NEEDS_RRTC_VERIFICATION"

FAO_URL = "https://www.fao.org/4/x0490e/x0490e0b.htm"
FAO_STATUS = "FAO_REFERENCE_NOT_LOCALLY_CALIBRATED"
# أطوال المراحل العامة في FAO-56 (جدول 11) للأرز: 30/30/60/30 = 150 يوم.
# ده مرجع عام، مش لصنف معين.
VALID_COND = ("FAO-56 Table 11 generic rice (150-day season); "
              "adjust per variety using local records")
STAGE_LENGTHS = [
    ("initial",     30),
    ("development", 30),
    ("mid_season",  60),
    ("late_season", 30),
]


def main():
    if not DB.exists():
        sys.exit(f"مش لاقي القاعدة: {DB.resolve()}")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = DB.with_name(f"agriwater_v2_backup_{stamp}.sqlite")
    shutil.copy2(DB, backup)
    print(f"نسخة احتياطية: {backup}")

    con = sqlite3.connect(DB)
    con.execute("PRAGMA foreign_keys = ON")
    try:
        with con:  # transaction: commit لو نجح، rollback لو حصل خطأ
            # --- الأصناف ---
            added_v = 0
            for name_en, name_ar in VARIETIES:
                cur = con.execute(
                    "INSERT OR IGNORE INTO rice_variety "
                    "(name_en, name_ar, season_length_days, source_url, data_status) "
                    "VALUES (?, ?, NULL, NULL, ?)",
                    (name_en, name_ar, VARIETY_STATUS),
                )
                added_v += cur.rowcount

            # --- أطوال المراحل (مرجع FAO عام، variety_id = NULL) ---
            added_p = 0
            for stage, days in STAGE_LENGTHS:
                exists = con.execute(
                    "SELECT 1 FROM crop_water_parameter "
                    "WHERE crop='rice' AND variety_id IS NULL "
                    "AND growth_stage=? AND parameter_name='stage_length'",
                    (stage,),
                ).fetchone()
                if exists:
                    continue
                con.execute(
                    "INSERT INTO crop_water_parameter "
                    "(crop, variety_id, growth_stage, kc, parameter_name, "
                    " parameter_value, unit, valid_conditions, source_url, data_status) "
                    "VALUES ('rice', NULL, ?, NULL, 'stage_length', ?, 'days', ?, ?, ?)",
                    (stage, days, VALID_COND, FAO_URL, FAO_STATUS),
                )
                added_p += 1

        print(f"أصناف اتضافت: {added_v}")
        print(f"صفوف مراحل اتضافت: {added_p}")

        print("\n--- rice_variety ---")
        for r in con.execute("SELECT variety_id, name_en, name_ar, season_length_days, data_status FROM rice_variety"):
            print(r)
        print("\n--- crop_water_parameter ---")
        for r in con.execute("SELECT parameter_id, growth_stage, kc, parameter_name, parameter_value, unit FROM crop_water_parameter"):
            print(r)

        bad = con.execute("PRAGMA foreign_key_check").fetchall()
        print(f"\nforeign_key_check problems: {len(bad)}")
        print(f"integrity_check: {con.execute('PRAGMA integrity_check').fetchone()[0]}")
    except Exception as e:
        print(f"حصل خطأ، ولا حاجة اتغيرت: {e}")
        print(f"لو محتاج ترجع: النسخة الاحتياطية في {backup}")
        raise
    finally:
        con.close()


if __name__ == "__main__":
    main()
